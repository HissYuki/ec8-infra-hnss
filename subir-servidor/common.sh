#!/usr/bin/env bash
# Shared orchestration only. Never sources .env as executable shell code.
set -Eeuo pipefail

die() { printf 'Erro: %s\n' "$*" >&2; exit 1; }
REPO_ROOT="$(cd -- "$DEPLOY_DIR/../.." && pwd)"
if [[ "$DEPLOY_AREA" == interna ]]; then SECRET_DIR="$REPO_ROOT/senha-rede-interna"; else SECRET_DIR="$REPO_ROOT/senha-dmz"; fi
ENV_FILE="${ENV_FILE:-$SECRET_DIR/servidor.env}"
ACTION="${1:-status}"
[[ "$#" -le 1 ]] || die 'Forneça somente uma ação; flags adicionais não são aceitas.'
case "$ACTION" in check|up|down|status|logs|migrate) ;; *) die 'Use check, up, down, status, logs ou migrate (somente Rede Interna).' ;; esac
[[ "$DEPLOY_AREA" == interna || "$ACTION" != migrate ]] || die 'Migrations pertencem somente à Rede Interna.'
command -v docker >/dev/null || die 'Docker não encontrado.'
[[ -f "$ENV_FILE" ]] || die "Prepare $ENV_FILE a partir do .env.example desta máquina."

# Values used for validation must be literal, single-line dotenv values.
read_env() {
    local value
    value="$(awk -v key="$1" 'index($0,key "=")==1 {sub("^[^=]*=", ""); sub("\r$", ""); print; exit}' "$ENV_FILE")"
    value="${value#\"}"; value="${value%\"}"
    value="${value#\'}"; value="${value%\'}"
    printf '%s' "$value"
}
require_env() {
    local value
    value="$(read_env "$1")"
    [[ -n "$value" && "$value" != *SUBSTITUA* && "$value" != *CHANGE_ME* ]] || die "Configure $1 no arquivo de ambiente."
}
check_interface() {
    require_env "$1"
    case "$(read_env "$1")" in 0.0.0.0|::|127.*|localhost) die "$1 deve indicar a interface específica do servidor, fora do loopback." ;; esac
}
check_file() { [[ -f "$1" && -s "$1" ]] || die "Arquivo necessário ausente ou vazio: $1"; }

COMPOSE=(docker compose --env-file "$ENV_FILE")
if [[ "$DEPLOY_AREA" == interna ]]; then
    COMPOSE+=(--project-name hospital-interna -f "$REPO_ROOT/rede-interna/docker-compose.yml" -f "$REPO_ROOT/rede-interna/compose.server.yaml")
else
    COMPOSE+=(--project-name hospital-dmz -f "$REPO_ROOT/dmz/docker-compose.yml")
fi
compose() { "${COMPOSE[@]}" "$@"; }

check_configuration() {
    local key tls runtime certificate
    docker compose version >/dev/null
    for key in PUBLIC_HOST PUBLIC_ORIGIN TLS_DIR; do require_env "$key"; done
    case "$(read_env PUBLIC_HOST)" in localhost|127.*) die 'PUBLIC_HOST ainda aponta para o laboratório.' ;; esac
    [[ "$(read_env PUBLIC_ORIGIN)" == https://* ]] || die 'PUBLIC_ORIGIN precisa usar HTTPS.'
    tls="$(read_env TLS_DIR)"
    [[ "$tls" == /* ]] || die 'TLS_DIR deve ser um caminho absoluto Linux.'
    if [[ "$DEPLOY_AREA" == interna ]]; then
        for key in PROMETHEUS_TARGET_VLAN10 PROMETHEUS_TARGET_VLAN20 PROMETHEUS_TARGET_VLAN40; do require_env "$key"; done
        check_interface NODE_EXPORTER_BIND_IP
        for key in DJANGO_SECRET_KEY POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD INFRA_POSTGRES_PASSWORD KEYCLOAK_DB_PASSWORD KEYCLOAK_ADMIN_PASSWORD WAZUH_RUNTIME_DIR WAZUH_INDEXER_ADMIN_PASSWORD WAZUH_DASHBOARD_PASSWORD WAZUH_API_PASSWORD WAZUH_ENROLLMENT_PASSWORD; do require_env "$key"; done
        check_interface BACKEND_BIND_IP
        check_interface WAZUH_BIND_IP
        require_env WAZUH_DASHBOARD_BIND_IP
        require_env SECURITY_BIND_IP
        require_env VAULT_CONFIG_FILE
        check_file "$(read_env VAULT_CONFIG_FILE)"
        [[ "$(read_env EMAIL_BACKEND)" == django.core.mail.backends.smtp.EmailBackend ]] || die 'Configure SMTP; o backend de console é somente local.'
        for key in EMAIL_HOST DEFAULT_FROM_EMAIL; do require_env "$key"; done
        if [[ -n "$(read_env EMAIL_HOST_USER)" || -n "$(read_env EMAIL_HOST_PASSWORD)" ]]; then
            require_env EMAIL_HOST_USER
            require_env EMAIL_HOST_PASSWORD
        fi
        for certificate in backend.crt backend.key client-ca.crt; do check_file "$tls/$certificate"; done
        runtime="$(read_env WAZUH_RUNTIME_DIR)"
        [[ "$runtime" == /* ]] || die 'WAZUH_RUNTIME_DIR deve ser um caminho absoluto Linux.'
        for certificate in root-ca.pem wazuh.manager.pem wazuh.manager-key.pem wazuh.indexer.pem wazuh.indexer-key.pem wazuh.dashboard.pem wazuh.dashboard-key.pem admin.pem admin-key.pem; do check_file "$runtime/certs/$certificate"; done
        for certificate in authd.pass internal_users.yml wazuh.yml; do check_file "$runtime/$certificate"; done
        if [[ -f /proc/sys/vm/max_map_count ]]; then
            [[ "$(cat /proc/sys/vm/max_map_count)" -ge 262144 ]] || die 'Configure vm.max_map_count >= 262144 no host Linux do Docker.'
        fi
        printf '%s\n' 'Atenção: Keycloak ainda usa start-dev e Vault tem TLS desativado no Compose/configuração atual. Este script não os converte para produção.'
    else
        check_interface NODE_EXPORTER_BIND_IP
        check_interface DMZ_BIND_IP
        for key in BACKEND_URL BACKEND_TLS_NAME; do require_env "$key"; done
        [[ "$(read_env BACKEND_URL)" == https://* ]] || die 'BACKEND_URL precisa usar HTTPS com mTLS.'
        case "$(read_env BACKEND_URL)" in https://hospital-backend:*|https://localhost*|https://127.*) die 'BACKEND_URL ainda aponta para o laboratório; configure IP/FQDN da Rede Interna.' ;; esac
        for certificate in public.crt public.key backend-ca.crt frontend.crt frontend.key; do check_file "$tls/$certificate"; done
    fi
    # Structural validation without printing interpolated secrets.
    compose config --quiet
    printf '%s\n' 'Configuração estrutural validada. Certificados, firewall, DNS, backups e fluxos reais exigem homologação.'
}

case "$ACTION" in
    check) check_configuration ;;
    up)
        check_configuration
        if [[ "$DEPLOY_AREA" == interna ]]; then
            compose up -d --wait --wait-timeout 600 wazuh-indexer wazuh-manager
            for group in dmz dados endpoints; do
                compose exec -T wazuh-manager sh -c 'test -d /var/ossec/etc/shared/$1 || /var/ossec/bin/agent_groups -a -g $1 -q' -- "$group"
            done
        fi
        compose up -d --build --wait --wait-timeout 600
        compose ps
        [[ "$DEPLOY_AREA" != interna ]] || printf '%s\n' 'Migrations não são automáticas. Aplique migrate na primeira instalação e em atualizações planejadas.'
        ;;
    migrate)
        check_configuration
        compose up -d --wait postgresql
        compose build backend
        compose run --rm --no-deps backend python manage.py migrate --noinput
        # Garante um ponto de recuperação contendo o esquema recém-migrado.
        compose exec -T postgresql su-exec postgres pgbackrest --config=/etc/pgbackrest.conf --stanza=hospital backup --type=diff
        ;;
    down) compose down; printf '%s\n' 'Containers deste projeto encerrados. Volumes preservados.' ;;
    status) compose ps ;;
    logs) compose logs --tail 100 -f ;;
esac
