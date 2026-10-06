# O contexto auxiliar backend_source é utilizado apenas para collectstatic.
FROM python:3.13-slim AS collector
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /build/backend
COPY --from=backend_source requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=backend_source manage.py ./
COPY --from=backend_source config ./config
COPY --from=backend_source accounts ./accounts
COPY --from=backend_source pacientes ./pacientes
COPY --from=backend_source medicos ./medicos
COPY --from=backend_source coordenador ./coordenador
COPY --from=backend_source consultas ./consultas
COPY static /frontend/static
RUN DJANGO_SECRET_KEY=collectstatic-build-only POSTGRES_DB=unused POSTGRES_USER=unused \
    POSTGRES_PASSWORD=unused POSTGRES_HOST=unused POSTGRES_PORT=5432 \
    DJANGO_STATIC_SOURCE=/frontend/static DJANGO_STATIC_ROOT=/static-dist \
    python manage.py collectstatic --noinput

FROM nginx:1.30.5-alpine
COPY --from=collector /static-dist/ /usr/share/nginx/html/static/
COPY default.conf.template /etc/nginx/templates/default.conf.template
