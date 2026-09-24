import uuid

from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    LOGIN_SUCCESS = "login_success", "Connexion réussie"
    LOGIN_FAILED = "login_failed", "Connexion échouée"
    LOGOUT = "logout", "Déconnexion"
    PASSWORD_CHANGED = "password_changed", "Mot de passe changé"
    PASSWORD_RESET_REQUESTED = "password_reset_requested", "Réinitialisation demandée"
    PASSWORD_RESET_CONFIRMED = "password_reset_confirmed", "Réinitialisation confirmée"
    USER_CREATED = "user_created", "Compte créé"
    USER_UPDATED = "user_updated", "Compte modifié (rôle/statut)"
    USER_DELETED = "user_deleted", "Compte supprimé définitivement"


class AuditLog(models.Model):
    """Journal d'audit des événements sensibles du module accounts.

    Immuable par construction (voir save()/delete() ci-dessous) : c'est une
    protection au niveau applicatif, pas une contrainte DB (pas de trigger
    Postgres/permissions read-only en base à ce stade — infra pas encore en
    place, voir CLAUDE.md "Explicitly deferred" §10). Suffisant pour l'usage
    actuel (API + admin Django), à durcir si un jour un accès DB direct existe.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=32, choices=AuditAction.choices, db_index=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_actions",
        help_text="Qui a déclenché l'action. Null si non authentifié (ex. tentative de login échouée).",
    )
    # Dénormalisé : reste lisible même si le compte `actor` est supprimé plus tard.
    actor_email = models.EmailField(blank=True)

    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_targets",
        help_text="Compte visé par l'action, si différent de l'acteur (ex. admin modifiant un tiers).",
    )
    target_user_email = models.EmailField(blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "entrée du journal d'audit"
        verbose_name_plural = "journal d'audit"

    def __str__(self):
        return f"{self.get_action_display()} — {self.actor_email or 'anonyme'} — {self.created_at:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
            raise ValueError("Un AuditLog est immuable : modification interdite après création.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Un AuditLog est immuable : suppression interdite.")
