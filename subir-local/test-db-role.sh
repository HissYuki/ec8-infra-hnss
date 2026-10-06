#!/bin/sh
set -eu
# Used only for the separate local test database; never changes stored data.
case "${1:-}" in
    CREATEDB|NOCREATEDB) permission="$1" ;;
    *) echo 'Expected CREATEDB or NOCREATEDB' >&2; exit 2 ;;
esac
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set=ON_ERROR_STOP=1 --set=app_user="$APP_USER" <<SQL
SELECT format('ALTER ROLE %I $permission', :'app_user')
\gexec
SQL
