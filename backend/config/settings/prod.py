"""
Environnement de production.

Important : ce fichier pose les headers/flags de sécurité *transport*
(TLS, HSTS, cookies). Il ne suffit pas à lui seul pour être conforme au
cahier des charges complet — voir CLAUDE.md > "Backend Django — état
d'avancement" pour la liste de ce qui reste à faire avant un vrai
déploiement en production sur des données patients réelles (CSP,
chiffrement applicatif au repos, gestion de secrets via KMS/Vault, CI/CD
sécurité, monitoring/alerting...).
"""
from .base import *  # noqa: F401,F403

DEBUG = False

# ALLOWED_HOSTS doit être fourni explicitement en prod (pas de valeur par
# défaut ici) : voir DJANGO_ALLOWED_HOSTS dans base.py.
if not ALLOWED_HOSTS:
    raise RuntimeError(
        "DJANGO_ALLOWED_HOSTS doit être défini explicitement en production."
    )

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
