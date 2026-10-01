"""Vues API du module patients (MVP `docs/MVP.md` §3 tâche 4 : création/
édition/recherche, sans dédoublonnage avancé). Mêmes patterns que
`apps.accounts.views` : permissions par rôle (`permissions.py`), audit via
`apps.audit.services.record` après coup, serializer à champs explicites."""
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import generics

from apps.accounts.permissions import IsSuperAdmin
from apps.audit.models import AuditAction
from apps.audit.services import record

from .models import Patient
from .permissions import IsCliniqueStaffOrSuperAdmin
from .serializers import PatientSerializer
from .throttling import PatientRateThrottle

TAG_PATIENTS = "Patients"


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_PATIENTS],
        summary="Consulter un dossier patient",
    ),
    patch=extend_schema(
        tags=[TAG_PATIENTS],
        summary="Modifier un dossier patient (archivage/réactivation inclus)",
        description=(
            "Tout le personnel clinique peut modifier n'importe quel dossier, y "
            "compris son statut `is_active` — l'archivage d'un dossier "
            "(`{\"is_active\": false}`) est réversible et journalisé "
            "séparément (`patient_archived`/`patient_reactivated`)."
        ),
    ),
    delete=extend_schema(
        tags=[TAG_PATIENTS],
        summary="Supprimer définitivement un dossier",
        description=(
            "Réservé à `super_admin`. Suppression physique et irréversible — "
            "préférer `PATCH {\"is_active\": false}` (archivage, réversible, "
            "ouvert à tout le personnel clinique) dans la quasi-totalité des cas."
        ),
    ),
)
class PatientDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Pas de restriction objet par créateur : tout le personnel clinique
    partage le même dossier patient (voir permissions.py). L'écriture (PATCH)
    reste ouverte à tout le personnel clinique, y compris pour archiver un
    dossier (`is_active`) ; seule la suppression physique (`DELETE`,
    irréversible) est resserrée à `super_admin` (`get_permissions`), même
    logique que `UserDetailView` côté accounts."""

    http_method_names = ["get", "patch", "delete", "head", "options"]
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsCliniqueStaffOrSuperAdmin]
    throttle_classes = [PatientRateThrottle]

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsSuperAdmin()]
        return [IsCliniqueStaffOrSuperAdmin()]

    def retrieve(self, request, *args, **kwargs):
        # Journalisé même si rien n'est modifié : donnée de santé, la
        # consultation d'un dossier doit être traçable, pas seulement son
        # édition (utile en cas d'investigation post-incident).
        response = super().retrieve(request, *args, **kwargs)
        record(
            AuditAction.PATIENT_VIEWED,
            actor=request.user,
            request=request,
            patient_id=str(kwargs["pk"]),
            numero_dossier=response.data.get("numero_dossier", ""),
        )
        return response

    def perform_update(self, serializer):
        instance = serializer.instance
        was_active = instance.is_active
        # Seuls les champs réellement soumis (hors sous-objet imbriqué) sont
        # comparés avant/après — pas la totalité du modèle.
        tracked_fields = [field for field in serializer.validated_data if field != "antecedents_familiaux"]
        before = {field: getattr(instance, field) for field in tracked_fields}

        patient = serializer.save()

        changed = {
            field: getattr(patient, field) for field in tracked_fields if before[field] != getattr(patient, field)
        }

        if patient.is_active != was_active:
            action = AuditAction.PATIENT_REACTIVATED if patient.is_active else AuditAction.PATIENT_ARCHIVED
        else:
            action = AuditAction.PATIENT_UPDATED

        record(
            action,
            actor=self.request.user,
            request=self.request,
            patient_id=str(patient.pk),
            numero_dossier=patient.numero_dossier,
            before={field: before[field] for field in changed},
            after=changed,
        )

    def perform_destroy(self, instance):
        # Journalisé avant suppression effective, comme UserDetailView côté
        # accounts — le patient_id reste lisible dans le journal même une
        # fois la ligne supprimée.
        record(
            AuditAction.PATIENT_DELETED,
            actor=self.request.user,
            request=self.request,
            patient_id=str(instance.pk),
            numero_dossier=instance.numero_dossier,
        )
        instance.delete()


@extend_schema_view(
    get=extend_schema(
        tags=[TAG_PATIENTS],
        summary="Lister / rechercher des patients",
        description=(
            "`?search=` filtre sur nom, prénom, numéro de dossier, CNI, "
            "téléphone et email (insensible à la casse, sans dédoublonnage "
            "avancé)."
        ),
        parameters=[
            OpenApiParameter(
                name="search",
                type=str,
                required=False,
                description="Nom, prénom, numéro de dossier, CNI, téléphone ou email",
            )
        ],
    ),
    post=extend_schema(
        tags=[TAG_PATIENTS],
        summary="Créer un dossier patient",
    ),
)
class PatientListView(generics.ListCreateAPIView):
    serializer_class = PatientSerializer
    permission_classes = [IsCliniqueStaffOrSuperAdmin]
    throttle_classes = [PatientRateThrottle]

    def get_queryset(self):
        queryset = Patient.objects.all()
        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(numero_dossier__icontains=search)
                | Q(cni__icontains=search)
                | Q(telephone__icontains=search)
                | Q(email__icontains=search)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        record(
            AuditAction.PATIENT_LIST_VIEWED,
            actor=request.user,
            request=request,
            search=request.query_params.get("search", "").strip(),
            result_count=response.data.get("count"),
        )
        return response

    def perform_create(self, serializer):
        patient = serializer.save(created_by=self.request.user)
        record(
            AuditAction.PATIENT_CREATED,
            actor=self.request.user,
            request=self.request,
            patient_id=str(patient.pk),
            numero_dossier=patient.numero_dossier,
        )
