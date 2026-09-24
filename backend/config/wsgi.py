import os

from django.core.wsgi import get_wsgi_application

# Entrée de production : nécessite DJANGO_SETTINGS_MODULE=config.settings.prod
# explicite dans l'environnement de déploiement (le fallback ci-dessous ne
# sert qu'à éviter un crash silencieux si la variable est oubliée en local).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()
