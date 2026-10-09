"""Vues API du module prescriptions (MVP `docs/MVP.md` §3 tâche 6, construit
sans découpage MVP — voir CLAUDE.md "2026-09-28"). Mêmes patterns que
`apps.consultations.views` : permissions par rôle (`permissions.py`), audit
via `apps.audit.services.record` après coup, serializer à champs explicites,
pas de restriction objet par créateur (voir `models.py`). Contrairement à
Consultation, l'écriture (POST/PATCH) est ouverte à médecin ET biologiste —
voir `permissions.py`."""
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics

from apps.accounts.permissions import IsSuperAdmin
from apps.audit.models import AuditAction
from apps.audit.services import record

from .models import Examen, Prescription, StatutPrescription
from .permissions import IsCliniqueStaffOrSuperAdmin
from .serializers import ExamenSerializer, PrescriptionSerializer
from .throttling import PrescriptionRateThrottle

TAG_PRESCRIPTIONS = "Prescriptions d'examens"


@extend_schema_view(
    get=extend_schema(tags=[TAG_PRESCRIPTIONS], summary="Consulter une demande d'examen"),
    patch=extend_schema(
        tags=[TAG_PRESCRIPTIONS],
        summary="Modifier une demande d'examen",
        description=(
            "Réservé au médecin, au biologiste ou à `super_admin`. Le passage de `statut` à "
            "`valide`/`rejete` est journalisé sous une action dédiée "
            "(`prescription_examen_validee`/`prescription_examen_rejetee`)."
        ),
    ),
    delete=extend_schema(
        tags=[TAG_PRESCRIPTIONS],
        summary="Supprimer définitivement une demande d'examen",
        description="Réservé à `super_admin`. Suppression physique et irréversible.",
    ),
)
class PrescriptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    queryset = Prescription.objects.select_related("patient", "consultation", "cree_par").prefetch_related(
        "examens_prescrits__examen"
    )
    serializer_class = PrescriptionSerializer
    throttle_classes = [PrescriptionRateThrottle]

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsSuperAdmin()]
        return [IsCliniqueStaffOrSuperAdmin()]

    def retrieve(self, request, *args, **kwargs):
        # Journalisé même si rien n'est modifié : donnée de santé, voir
        # ConsultationDetailView.retrieve pour le même raisonnement.
        response = super().retrieve(request, *args, **kwargs)
        record(
            AuditAction.PRESCRIPTION_EXAMEN_VIEWED,
            actor=request.user,
            request=request,
            prescription_id=str(kwargs["pk"]),
        )
        return response

    def perform_update(self, serializer):
        instance = serializer.instance
        previous_statut = instance.statut
        tracked_fields = [
            field
            for field in serializer.validated_data
            # Exclu du diff avant/après : sous-ressource imbriquée
            # (examens_prescrits), même raison que
            # ConsultationDetailView.perform_update.
            if field != "examens_prescrits"
        ]
        before = {field: getattr(instance, field) for field in tracked_fields}

        prescription = serializer.save()

        changed = {
            field: getattr(prescription, field)
            for field in tracked_fields
            if before[field] != getattr(prescription, field)
        }

        if prescription.statut != previous_statut and prescription.statut == StatutPrescription.VALIDE:
            action = AuditAction.PRESCRIPTION_EXAMEN_VALIDEE
        elif prescription.statut != previous_statut and prescription.statut == StatutPrescription.REJETE:
            action = AuditAction.PRESCRIPTION_EXAMEN_REJETEE
        else:
            action = AuditAction.PRESCRIPTION_EXAMEN_UPDATED

        record(
            action,
            actor=self.request.user,
            request=self.request,
            prescription_id=str(prescription.pk),
            patient_id=str(prescription.patient_id),
            before={field: before[field] for field in changed},
            after=changed,
        )

    def perform_destroy(self, instance):
        record(
            AuditAction.PRESCRIPTION_EXAMEN_DELETED,
            actor=self.request.user,
            request=self.request,
            prescription_id=str(instance.pk),
            patient_id=str(instance.patient_id),
        )
        instance.delete()


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_PRESCRIPTIONS],
        summary="Lister les demandes d'examen",
        parameters=[
            OpenApiParameter(name="patient", type=str, required=False, description="Filtrer par patient (UUID)"),
            OpenApiParameter(
                name="consultation", type=str, required=False, description="Filtrer par consultation (UUID)"
            ),
            OpenApiParameter(
                name="statut",
                type=str,
                required=False,
                description="Filtrer par statut (saisie/validation/valide/urgent/recommande/rejete)",
            ),
        ],
    ),
    post=extend_schema(
        tags=[TAG_PRESCRIPTIONS], summary="Créer une demande d'examen (médecin ou biologiste)"
    ),
)
class PrescriptionListView(generics.ListCreateAPIView):
    serializer_class = PrescriptionSerializer
    permission_classes = [IsCliniqueStaffOrSuperAdmin]
    throttle_classes = [PrescriptionRateThrottle]

    def get_queryset(self):
        queryset = Prescription.objects.select_related("patient", "consultation", "cree_par").prefetch_related(
            "examens_prescrits__examen"
        )
        patient_id = self.request.query_params.get("patient")
        consultation_id = self.request.query_params.get("consultation")
        statut = self.request.query_params.get("statut")
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        if consultation_id:
            queryset = queryset.filter(consultation_id=consultation_id)
        if statut:
            queryset = queryset.filter(statut=statut)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record(
            AuditAction.PRESCRIPTION_EXAMEN_LIST_VIEWED,
            actor=request.user,
            request=request,
            patient_id=request.query_params.get("patient", ""),
            statut=request.query_params.get("statut", ""),
            result_count=response.data.get("count"),
        )
        return response

    def perform_create(self, serializer):
        prescription = serializer.save(cree_par=self.request.user)
        record(
            AuditAction.PRESCRIPTION_EXAMEN_CREATED,
            actor=self.request.user,
            request=self.request,
            prescription_id=str(prescription.pk),
            patient_id=str(prescription.patient_id),
        )


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_PRESCRIPTIONS],
        summary="Lister le référentiel des examens de laboratoire",
        description=(
            "Catalogue statique (103 examens répartis en 17 catégories) utilisé pour la "
            "sélection des examens à prescrire. Lecture seule — géré via l'admin, pas "
            "d'endpoint de création/modification."
        ),
    ),
)
class ExamenListView(generics.ListAPIView):
    queryset = Examen.objects.all()
    serializer_class = ExamenSerializer
    permission_classes = [IsCliniqueStaffOrSuperAdmin]
    pagination_class = None

    def get_queryset(self):
        queryset = Examen.objects.all()
        categorie = self.request.query_params.get("categorie")
        search = self.request.query_params.get("search")
        if categorie:
            queryset = queryset.filter(categorie=categorie)
        if search:
            queryset = queryset.filter(nom__icontains=search)
        return queryset
