from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Lecture seule dans /admin/, en écho à l'immuabilité déjà imposée par
    `AuditLog.save()`/`delete()` : les trois `has_*_permission` ci-dessous
    retirent les boutons ajouter/modifier/supprimer de l'UI (le modèle
    refuserait de toute façon, mais autant ne pas laisser un staff cliquer
    dans le vide). Écriture réelle uniquement via `apps.audit.services.record`.
    """

    list_display = ["created_at", "action", "actor_email", "target_user_email", "ip_address"]
    list_filter = ["action"]
    search_fields = ["actor_email", "target_user_email", "ip_address"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
