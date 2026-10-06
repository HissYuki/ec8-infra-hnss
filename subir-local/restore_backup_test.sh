#!/bin/bash
# Executar somente no container isolado descrito no README, com repo read-only
# e /restore em tmpfs. Nunca montar PGDATA da aplicação aqui.
set -euo pipefail
test "$(stat -f -c %T /restore)" = tmpfs || { echo 'FAIL: /restore precisa ser tmpfs.' >&2; exit 1; }
install -d -o postgres -g postgres -m 700 /restore/data
su-exec postgres pgbackrest --config=/etc/pgbackrest.conf --stanza=hospital \
  --pg1-path=/restore/data restore >/tmp/restore-pgbackrest.log
trap 'su-exec postgres pg_ctl -D /restore/data -m fast -w stop >/dev/null 2>&1 || true' EXIT
su-exec postgres pg_ctl -D /restore/data \
  -o "-c listen_addresses='' -c port=5433 -c archive_mode=off" -w start >/tmp/restore-postgres.log
query() { su-exec postgres psql -p 5433 -U "$RESTORE_DB_USER" -d "$RESTORE_APP_DB" -At -v ON_ERROR_STOP=1 -c "$1"; }
test "$(query 'SELECT system_identifier FROM pg_control_system()')" = "$EXPECTED_SYSTEM_ID"
test "$(query 'SELECT count(*) FROM django_migrations')" -ge "$EXPECTED_MIGRATIONS"
test "$(query "SELECT to_regclass('accounts_user') IS NOT NULL AND to_regclass('consultas_consulta') IS NOT NULL AND to_regclass('consultas_exame') IS NOT NULL")" = t
echo 'PASS: backup restaurado em tmpfs isolado; identidade do cluster e tabelas Django verificadas.'
