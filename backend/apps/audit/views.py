from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics

from apps.accounts.permissions import IsSuperAdmin

from .models import AuditAction, AuditLog
from .serializers import AuditLogSerializer

TAG_AUDIT = "Audit"


@extend_schema(
    tags=[TAG_AUDIT],
    summary="Journal d'audit",
    description=(
        "Réservé à `super_admin`. Lecture seule — une entrée d'audit ne "
        "peut être ni modifiée ni supprimée (immuabilité imposée aussi au "
        "niveau du modèle)."
    ),
    parameters=[
        OpenApiParameter(
            "action",
            str,
            description="Filtrer par type d'événement (ex. `login_failed`).",
            enum=[choice.value for choice in AuditAction],
            required=False,
        ),
        OpenApiParameter(
            "target_user",
            str,
            description="Filtrer par UUID du compte visé par l'action.",
            required=False,
        ),
    ],
)
class AuditLogListView(generics.ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        queryset = AuditLog.objects.all()
        action = self.request.query_params.get("action")
        target_user = self.request.query_params.get("target_user")
        if action:
            queryset = queryset.filter(action=action)
        if target_user:
            queryset = queryset.filter(target_user__pk=target_user)
        return queryset
