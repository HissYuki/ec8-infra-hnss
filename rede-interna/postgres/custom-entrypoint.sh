#!/bin/bash
set -euo pipefail

# Prepara apenas o repositório; nunca altera/apaga PGDATA.
install -d -o postgres -g postgres -m 750 /var/lib/pgbackrest /var/log/pgbackrest
# A readiness só é anunciada depois de validar stanza, WAL e backup inicial.
/usr/local/bin/init-pgbackrest.sh &

# Executa o entrypoint original do PostgreSQL com todos os parâmetros do docker-compose
exec docker-entrypoint.sh "$@"
