"""Point d'entrée unique pour écrire dans le journal d'audit.

`apps.audit` est un modèle/service partagé, pas un journal par module métier :
la forme d'une entrée (acteur/cible/ip/métadonnées, immuable) ne dépend pas de
qui l'écrit, et une table unique donne un seul endroit (`GET /api/v1/audit/
logs/`) pour consulter tout l'historique au lieu de N journaux fragmentés.
Toute future app (`patients`, `consultations`...) doit appeler `record(...)`
d'ici plutôt que définir son propre modèle de log.
"""
from .models import AuditLog


def get_client_ip(request):
    """Adresse IP du client.

    Pas de reverse proxy/load balancer devant l'app à ce stade (voir
    CLAUDE.md "Explicitly deferred" §10) : REMOTE_ADDR est fiable tel quel.
    Ne pas lire X-Forwarded-For tant qu'aucun proxy de confiance n'est
    configuré — un client pourrait sinon usurper son IP dans le journal.
    """
    return request.META.get("REMOTE_ADDR") if request is not None else None


def record(action, *, actor=None, actor_email="", target_user=None, request=None, **metadata):
    """Écrit une entrée d'audit. Best-effort : ne doit jamais faire échouer
    l'action métier qu'elle journalise (voir appelants — appelée après coup,
    une fois la vraie opération déjà en succès)."""
    if actor is not None and getattr(actor, "is_authenticated", False):
        actor_email = actor.email
    else:
        actor = None

    AuditLog.objects.create(
        action=action,
        actor=actor,
        actor_email=actor_email,
        target_user=target_user,
        target_user_email=target_user.email if target_user is not None else "",
        ip_address=get_client_ip(request),
        metadata=metadata,
    )
