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

    En déploiement Docker (voir docker-compose.yml), nginx est l'unique
    reverse proxy devant l'app et *remplace* (n'ajoute pas à) X-Forwarded-For
    par $remote_addr avant de transmettre à Gunicorn (voir deploy/nginx.conf)
    — un client ne peut donc pas usurper cette valeur, elle est fiable telle
    quelle. Fallback sur REMOTE_ADDR pour le dev local (pas de proxy devant
    `runserver`, X-Forwarded-For y est absent).
    """
    if request is None:
        return None
    return request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR")


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
