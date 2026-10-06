#!/bin/sh
set -eu
# Executado automaticamente SOMENTE na primeira inicialização do volume.
# Também pode ser executado explicitamente em um banco existente, sem apagar dados.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 --set=app_user="$APP_USER" \
  --set=app_password="$APP_PASSWORD" --set=app_db="$APP_DB" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
              :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user')
\gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'app_db', :'app_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'app_db')
\gexec
SQL
