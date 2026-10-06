#!/usr/bin/env bash
set -e

ACTION="${1:-up}"
PROJECT_ROOT="$(dirname "$(realpath "$0")")"
ENV_PATH="$PROJECT_ROOT/.env"

invoke_docker() {
    docker "$@" || { echo "Docker falhou: $1"; exit 1; }
}

compose_dmz() {
    invoke_docker compose --project-name dmz --env-file "$ENV_PATH" -f "$PROJECT_ROOT/dmz/docker-compose.yml" -f "$PROJECT_ROOT/dmz/compose.local.yaml" "$@"
}

if [ ! -f "$ENV_PATH" ] && [[ "$ACTION" =~ ^(up|dev)$ ]]; then
    echo "ERRO CRÍTICO: Arquivo .env não encontrado."
    echo "Você deve copiar o .env e a pasta TLS da Máquina Interna para esta máquina DMZ antes de iniciar."
    exit 1
fi

case "$ACTION" in
    up|dev)
        compose_dmz up -d --build --force-recreate --wait
        echo "DMZ online e aguardando conexões."
        ;;
    down)
        compose_dmz down
        echo "DMZ encerrada."
        ;;
    status) compose_dmz ps ;;
    *) echo "Ação inválida. Use: up, dev, down, status"; exit 1 ;;
esac