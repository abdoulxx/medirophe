"""Vues API du module consultations (MVP `docs/MVP.md` §3 tâche 5, étendu
sans découpage MVP — voir CLAUDE.md "2026-09-28"). Mêmes patterns que
`apps.patients.views` : permissions par rôle (`permissions.py`), audit via
`apps.audit.services.record` après coup, serializer à champs explicites,
pas de restriction objet par créateur (voir `models.py`)."""
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics

from apps.accounts.permissions import IsSuperAdmin
from apps.audit.models import AuditAction
from apps.audit.services import record

from .models import Consultation, Service, StatutConsultation
from .permissions import IsCliniqueStaffOrSuperAdmin, IsMedecinOrSuperAdmin
from .serializers import ConsultationSerializer, ServiceSerializer
from .throttling import ConsultationRateThrottle

TAG_CONSULTATIONS = "Consultations"


@extend_schema_view(
    get=extend_schema(tags=[TAG_CONSULTATIONS], summary="Consulter une consultation"),
    patch=extend_schema(
        tags=[TAG_CONSULTATIONS],
        summary="Modifier une consultation (réservé au médecin)",
        description=(
            "Réservé au médecin ou à `super_admin`. Le passage de `statut` à "
            "`terminee`/`annulee` est journalisé sous une action dédiée "
            "(`consultation_terminee`/`consultation_annulee`)."
        ),
    ),
    delete=extend_schema(
        tags=[TAG_CONSULTATIONS],
        summary="Supprimer définitivement une consultation",
        description="Réservé à `super_admin`. Suppression physique et irréversible.",
    ),
)
class ConsultationDetailView(generics.RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    queryset = Consultation.objects.select_related("patient", "medecin", "medecin_oriente").prefetch_related(
        "prescriptions", "rendez_vous_suivi", "conseils_patient", "services_orientation"
    )
    serializer_class = ConsultationSerializer
    throttle_classes = [ConsultationRateThrottle]

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsSuperAdmin()]
        if self.request.method == "PATCH":
            return [IsMedecinOrSuperAdmin()]
        return [IsCliniqueStaffOrSuperAdmin()]

    def retrieve(self, request, *args, **kwargs):
        # Journalisé même si rien n'est modifié : donnée de santé, la
        # consultation d'un dossier doit être traçable (même logique que
        # PatientDetailView.retrieve).
        response = super().retrieve(request, *args, **kwargs)
        record(
            AuditAction.CONSULTATION_VIEWED,
            actor=request.user,
            request=request,
            consultation_id=str(kwargs["pk"]),
        )
        return response

    def perform_update(self, serializer):
        instance = serializer.instance
        previous_statut = instance.statut
        tracked_fields = [
            field
            for field in serializer.validated_data
            # Exclus du diff avant/après : sous-ressources imbriquées
            # (prescriptions/rendez_vous_suivi/conseils_patient) et relation
            # M2M (services_orientation) — un manager M2M n'est jamais égal à
            # lui-même entre deux lectures, ce qui fausserait le diff.
            if field not in ("prescriptions", "rendez_vous_suivi", "conseils_patient", "services_orientation")
        ]
        before = {field: getattr(instance, field) for field in tracked_fields}

        consultation = serializer.save()

        changed = {
            field: getattr(consultation, field)
            for field in tracked_fields
            if before[field] != getattr(consultation, field)
        }

        if consultation.statut != previous_statut and consultation.statut == StatutConsultation.TERMINEE:
            action = AuditAction.CONSULTATION_TERMINEE
        elif consultation.statut != previous_statut and consultation.statut == StatutConsultation.ANNULEE:
            action = AuditAction.CONSULTATION_ANNULEE
        else:
            action = AuditAction.CONSULTATION_UPDATED

        record(
            action,
            actor=self.request.user,
            request=self.request,
            consultation_id=str(consultation.pk),
            patient_id=str(consultation.patient_id),
            before={field: before[field] for field in changed},
            after=changed,
        )

    def perform_destroy(self, instance):
        record(
            AuditAction.CONSULTATION_DELETED,
            actor=self.request.user,
            request=self.request,
            consultation_id=str(instance.pk),
            patient_id=str(instance.patient_id),
        )
        instance.delete()


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_CONSULTATIONS],
        summary="Lister les consultations",
        parameters=[
            OpenApiParameter(name="patient", type=str, required=False, description="Filtrer par patient (UUID)"),
            OpenApiParameter(
                name="statut", type=str, required=False, description="Filtrer par statut (en_cours/terminee/annulee)"
            ),
        ],
    ),
    post=extend_schema(tags=[TAG_CONSULTATIONS], summary="Créer une consultation (réservé au médecin)"),
)
class ConsultationListView(generics.ListCreateAPIView):
    serializer_class = ConsultationSerializer
    throttle_classes = [ConsultationRateThrottle]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsMedecinOrSuperAdmin()]
        return [IsCliniqueStaffOrSuperAdmin()]

    def get_queryset(self):
        queryset = Consultation.objects.select_related("patient", "medecin", "medecin_oriente").prefetch_related(
            "prescriptions", "rendez_vous_suivi", "conseils_patient", "services_orientation"
        )
        patient_id = self.request.query_params.get("patient")
        statut = self.request.query_params.get("statut")
        if patient_id:
            queryset = queryset.filter(patient_id=patient_id)
        if statut:
            queryset = queryset.filter(statut=statut)
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record(
            AuditAction.CONSULTATION_LIST_VIEWED,
            actor=request.user,
            request=request,
            patient_id=request.query_params.get("patient", ""),
            statut=request.query_params.get("statut", ""),
            result_count=response.data.get("count"),
        )
        return response

    def perform_create(self, serializer):
        consultation = serializer.save(medecin=self.request.user)
        record(
            AuditAction.CONSULTATION_CREATED,
            actor=self.request.user,
            request=self.request,
            consultation_id=str(consultation.pk),
            patient_id=str(consultation.patient_id),
        )


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_CONSULTATIONS],
        summary="Lister le référentiel des services d'orientation",
        description=(
            "Catalogue statique (47 services répartis en 4 catégories) utilisé pour l'étape "
            "« Admission & Pré-consultation » (champ `services_orientation` de Consultation). "
            "Lecture seule — géré via l'admin, pas d'endpoint de création/modification."
        ),
    ),
)
class ServiceListView(generics.ListAPIView):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsCliniqueStaffOrSuperAdmin]
    pagination_class = None
