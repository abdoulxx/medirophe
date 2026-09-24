from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Freine le brute-force sur `/api/v1/auth/token/` : limite par IP,
    taux dans `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login"]` (5/min).

    Volontairement par IP et non par compte visé : un lockout par compte
    permettrait à un attaquant de verrouiller le compte d'un tiers rien
    qu'en connaissant son email (DoS applicatif). Limite de portée connue :
    le cache par défaut (LocMemCache) est par processus — avec plusieurs
    workers/instances en production, il faudra un cache partagé (Redis) pour
    que la limite soit globale et pas juste par processus.
    """

    scope = "login"


class PasswordResetRateThrottle(AnonRateThrottle):
    """Limite les demandes de "mot de passe oublié" par IP : évite à la fois
    de spammer d'emails un tiers (une IP qui redemande en boucle un reset
    pour un email qui n'est pas le sien) et l'énumération de comptes par
    volume/timing. Taux dans `DEFAULT_THROTTLE_RATES["password-reset"]`."""

    scope = "password-reset"
