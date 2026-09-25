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

# Sécurisé par défaut (True) : redirection HTTPS, cookies secure, HSTS.
# Doit être temporairement mis à False (DJANGO_SECURE_SSL_REDIRECT=False côté
# serveur) tant que le déploiement tourne en IP nue sans domaine/TLS devant
# nginx (voir DEPLOY.md) — à repasser à True (ou supprimer la variable) dès
# qu'un certificat est en place, sans toucher au code.
_use_tls = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_SSL_REDIRECT = _use_tls
SESSION_COOKIE_SECURE = _use_tls
CSRF_COOKIE_SECURE = _use_tls
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = 31536000 if _use_tls else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _use_tls
SECURE_HSTS_PRELOAD = _use_tls
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Requis dès que l'admin Django (session+CSRF, contrairement à l'API qui est
# en JWT) est servi derrière un reverse proxy / sur une origine explicite.
# Ex. DJANGO_CSRF_TRUSTED_ORIGINS=http://169.58.78.224 (http:// tant que
# _use_tls est False, https:// une fois le certificat en place).
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
