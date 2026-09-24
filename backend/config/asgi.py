import os

from django.core.asgi import get_asgi_application

# Non utilisé actuellement (runserver/WSGI en dev, voir wsgi.py) — présent
# pour compatibilité si un serveur ASGI est adopté plus tard (ex. websockets).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_asgi_application()
