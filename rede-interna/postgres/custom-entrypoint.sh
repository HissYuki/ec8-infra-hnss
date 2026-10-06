#!/bin/bash
set -e

# Dispara a nossa automação em background (usando o & no final)
/usr/local/bin/init-pgbackrest.sh &

# Executa o entrypoint original do PostgreSQL com todos os parâmetros do docker-compose
exec docker-entrypoint.sh "$@"