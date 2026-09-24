from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Lecture seule (`read_only_fields = fields`) : le journal ne s'écrit
    jamais via l'API, uniquement via `apps.audit.services.record` côté
    serveur — voir `views.py` (`AuditLogListView`)."""

    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "created_at",
            "action",
            "action_display",
            "actor",
            "actor_email",
            "target_user",
            "target_user_email",
            "ip_address",
            "metadata",
        ]
        read_only_fields = fields
