"""
Settings communs à tous les environnements.

Principe 12-factor : aucune valeur sensible n'est codée en dur ici.
Tout secret (SECRET_KEY, mots de passe DB...) vient de variables
d'environnement / d'un fichier .env local non versionné (voir .env.example).

État d'avancement de ce fichier : voir CLAUDE.md > "Backend Django — état
d'avancement" pour ce qui est volontairement absent à ce stade (MFA,
chiffrement au repos/KMS, CSP, throttling, django-axes, audit log...).
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

# --------------------------------------------------------------------------
# Sécurité de base
# --------------------------------------------------------------------------
# Pas de valeur par défaut : on échoue bruyamment si le secret n'est pas
# fourni, plutôt que de démarrer avec une clé faible/prévisible.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # Nécessaire pour invalider les refresh tokens (logout, rotation).
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "apps.accounts",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Juste après SecurityMiddleware : sert /static/ (admin, docs OpenAPI en
    # dev) directement depuis Gunicorn, sans conteneur/volume nginx dédié.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        # Requis par django.contrib.admin, pas par l'API (l'API est pure DRF/JSON).
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------------------------------
# Base de données
# --------------------------------------------------------------------------
# DATABASE_URL doit pointer vers PostgreSQL en production
# (ex. postgres://user:pass@host:5432/medirophe). Le fallback SQLite ne sert
# qu'au démarrage local immédiat, tant que l'infra Postgre/Docker n'est pas
# encore mise en place (voir CLAUDE.md).
_database_url = env("DATABASE_URL", default="") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASES = {"default": environ.Env.db_url_config(_database_url)}

AUTH_USER_MODEL = "accounts.User"

# --------------------------------------------------------------------------
# Mots de passe
# --------------------------------------------------------------------------
# Argon2 en premier = utilisé pour tout nouveau hash. Les entrées suivantes
# ne servent qu'à *vérifier* d'anciens hashs si jamais on migre des comptes
# depuis un autre système ; Django ne s'en sert jamais pour créer un hash.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# DRF — refus par défaut : toute vue qui ne déclare pas explicitement ses
# permissions exige quand même une authentification (pas d'accès anonyme
# implicite).
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # voir apps/accounts/throttling.py (freinage brute-force par IP sur le
    # login et les demandes de reset de mot de passe). Cache par défaut =
    # LocMemCache (par processus, suffisant pour un seul worker dev) — un
    # cache partagé (Redis) sera nécessaire pour une limite globale en
    # production multi-instance.
    "DEFAULT_THROTTLE_RATES": {"login": "5/min", "password-reset": "3/min"},
}

# --------------------------------------------------------------------------
# Email ("mot de passe oublié")
# --------------------------------------------------------------------------
# Backend par défaut = console (affiche l'email dans les logs du serveur de
# dev, n'envoie jamais rien réellement) : un `.env` sans configuration SMTP
# ne doit jamais planter ni tenter d'envoyer un vrai email par erreur.
# Renseigner EMAIL_HOST_USER/EMAIL_HOST_PASSWORD dans `.env` pour activer un
# envoi réel (ex. SMTP Gmail : EMAIL_HOST=smtp.gmail.com, EMAIL_PORT=587,
# EMAIL_HOST_PASSWORD=un "app password" Gmail, pas le mot de passe du compte).
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER or "no-reply@medirophe.local")

# Durée de validité d'un token de reset de mot de passe (secondes). Lu par
# `django.contrib.auth.tokens.PasswordResetTokenGenerator`, réutilisé tel
# quel par apps/accounts/password_reset.py.
PASSWORD_RESET_TIMEOUT = 60 * 60  # 1h

# Pas encore de frontend déployé : ce champ documente juste où le lien de
# reset devra pointer une fois qu'il existera (voir CLAUDE.md). Port 4200 =
# défaut Angular CLI (`ng serve`), le frontend étant prévu en Angular.
FRONTEND_PASSWORD_RESET_URL = env(
    "FRONTEND_PASSWORD_RESET_URL",
    default="http://localhost:4200/reset-password",
)

# Doc OpenAPI/Swagger — les URLs qui la servent (voir config/urls.py) ne sont
# montées que si DEBUG=True, donc absentes en production (settings/prod.py
# force DEBUG=False) : "documentation OpenAPI désactivée en production".
SPECTACULAR_SETTINGS = {
    "TITLE": "MediRophe API",
    "DESCRIPTION": "API backend MediRophe (Clinique & Labo + Ministère de la Santé).",
    "VERSION": "0.1.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SCHEMA_PATH_PREFIX": "/api/v1/",
}

# JWT courte durée de vie + rotation/blacklist du refresh token : un refresh
# token volé et rejoué après rotation est rejeté (BLACKLIST_AFTER_ROTATION).
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Abidjan"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Manifest + compression : purge le cache navigateur automatiquement à
    # chaque déploiement (nom de fichier haché) sans configuration serveur.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Comportement identique en dev et prod : seul un reverse proxy (nginx) place
# ce header en prod ; en local il est simplement absent, donc ignoré.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
