FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

# libpq5 : bibliothèque client PostgreSQL requise à l'exécution par psycopg
# (psycopg[binary] embarque déjà son propre libpq, mais l'image de base ne
# l'a pas — gunicorn/manage.py plantent au premier import sans ce paquet).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY . .

EXPOSE 8000

# collectstatic/migrate tournent ici (au démarrage du conteneur), pas au
# build de l'image : ils ont besoin des vraies variables d'environnement
# (DJANGO_SECRET_KEY, DATABASE_URL...) fournies par docker-compose, qui ne
# sont pas disponibles pendant `docker build`.
# migrate au démarrage suppose un seul réplica web (c'est le cas ici) — avec
# plusieurs instances, migrer depuis un job séparé pour éviter les conflits.
CMD ["sh", "-c", "python manage.py collectstatic --noinput && python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
