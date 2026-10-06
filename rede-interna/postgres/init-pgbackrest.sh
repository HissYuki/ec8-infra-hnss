#!/bin/bash
set -euo pipefail
trap 'touch /tmp/pgbackrest.error; echo "pgBackRest: inicializacao falhou; consulte os logs." >&2' ERR
# Ignora o servidor temporário de initdb, que não escuta TCP.
until su-exec postgres pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -q; do
  sleep 2
done
stanza=hospital
backup() { su-exec postgres pgbackrest --config=/etc/pgbackrest.conf --stanza="$stanza" "$@"; }
# Idempotente: não recria o banco nem restaura backups.
backup stanza-create
backup check
if ! backup info | grep -q 'status: ok'; then
  echo 'pgBackRest: criando primeiro backup completo do cluster existente.'
  backup backup --type=full
fi
touch /tmp/pgbackrest.ready
echo 'pgBackRest: stanza, WAL e repositorio validados; dados preservados.'
