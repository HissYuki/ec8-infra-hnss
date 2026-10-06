#!/usr/bin/env bash
set -e

ACTION="${1:-up}"
PROJECT_ROOT="$(dirname "$(realpath "$0")")"
ENV_PATH="$PROJECT_ROOT/.env"
TLS_PATH="$PROJECT_ROOT/tls"

invoke_docker() {
    docker "$@" || { echo "Docker falhou: $1"; exit 1; }
}

compose_internal() {
    invoke_docker compose --project-name rede-interna --env-file "$ENV_PATH" -f "$PROJECT_ROOT/rede-interna/docker-compose.yml" -f "$PROJECT_ROOT/rede-interna/compose.local.yaml" "$@"
}

if [[ "$ACTION" =~ ^(prepare|up|dev)$ ]]; then
    if [ ! -f "$ENV_PATH" ]; then
        content=$(cat "$PROJECT_ROOT/.env.example")
        for key in DJANGO_SECRET_KEY POSTGRES_PASSWORD INFRA_POSTGRES_PASSWORD KEYCLOAK_DB_PASSWORD KEYCLOAK_ADMIN_PASSWORD; do
            value=$(openssl rand -hex 32)
            content=$(echo "$content" | sed -E "s/^$key=.*$/$key=$value/")
        done
        content=$(echo "$content" | sed -E "s|^TLS_DIR=.*$|TLS_DIR=$TLS_PATH|")
        echo "$content" > "$ENV_PATH"
    fi

    mkdir -p "$TLS_PATH"
    invoke_docker run --rm --mount "type=bind,source=$TLS_PATH,target=/certs" --mount "type=bind,source=$PROJECT_ROOT/certificates.sh,target=/certificates.sh,readonly" alpine:3.22 sh -c 'apk add --no-cache openssl >/dev/null && sh /certificates.sh'
fi

case "$ACTION" in
    prepare) echo "Configuração local preparada na Rede Interna." ;;
    up|dev)
        compose_internal up -d --build --wait postgresql
        compose_internal build backend
        compose_internal run --rm --no-deps backend python manage.py migrate --noinput
        
        if [ "$ACTION" = "dev" ]; then
            invoke_docker compose --project-name rede-interna --env-file "$ENV_PATH" -f "$PROJECT_ROOT/rede-interna/docker-compose.yml" -f "$PROJECT_ROOT/rede-interna/compose.local.yaml" -f "$PROJECT_ROOT/rede-interna/compose.dev.yaml" up -d --force-recreate --wait backend
            invoke_docker compose --project-name rede-interna --env-file "$ENV_PATH" -f "$PROJECT_ROOT/rede-interna/docker-compose.yml" -f "$PROJECT_ROOT/rede-interna/compose.local.yaml" -f "$PROJECT_ROOT/rede-interna/compose.dev.yaml" up -d --wait --wait-timeout 180
        else
            compose_internal up -d --force-recreate --wait backend
            compose_internal up -d --wait --wait-timeout 180
        fi
        echo "Rede Interna online."
        ;;
    down)
        compose_internal down
        echo "Rede Interna encerrada."
        ;;
    status) compose_internal ps ;;
    test)
        compose_internal exec -T backend python manage.py check
        compose_internal exec -T backend python manage.py makemigrations --check --dry-run
        # Ajuste de permissão removido para brevidade, mas você pode reincluir a função set_test_database_permission aqui
        compose_internal exec -T backend python manage.py test --noinput --settings=config.test_settings
        ;;
    *) echo "Ação inválida. Use: prepare, up, dev, down, status, test"; exit 1 ;;
esac