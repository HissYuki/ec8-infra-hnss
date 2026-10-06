param([ValidateSet('prepare','up','dev','down','status','test')][string]$Action = 'up')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$envPath = Join-Path $PSScriptRoot '.env'
$tlsPath = Join-Path $PSScriptRoot 'tls'
$utf8 = New-Object System.Text.UTF8Encoding($false)
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker falhou: $($args[0])" }
}
function Compose-Internal {
    Invoke-Docker compose --project-name hospital-interna --env-file $envPath -f "$projectRoot/rede-interna/docker-compose.yml" -f "$projectRoot/rede-interna/compose.local.yaml" @args
}
function Compose-Dmz {
    Invoke-Docker compose --project-name hospital-dmz --env-file $envPath -f "$projectRoot/dmz/docker-compose.yml" -f "$projectRoot/dmz/compose.local.yaml" @args
}
function Set-TestDatabasePermission {
    param([ValidateSet('CREATEDB','NOCREATEDB')][string]$Permission)
    # Envia o script pelo stdin: evita aspas SQL aninhadas nos argumentos do Windows.
    $roleScript = [IO.File]::ReadAllText("$PSScriptRoot/test-db-role.sh").Replace("`r`n", "`n")
    # O pipeline do PowerShell 5.1 acrescenta CRLF; normaliza também dentro do container.
    $roleScript | & docker compose --project-name hospital-interna --env-file $envPath -f "$projectRoot/rede-interna/docker-compose.yml" -f "$projectRoot/rede-interna/compose.local.yaml" exec -T postgresql sh -c 'tr -d \\r | sh -s -- $1' -- $Permission
    if ($LASTEXITCODE -ne 0) { throw "Falha ao ajustar a permissão de testes: $Permission" }
}
if ($Action -in @('prepare','up','dev')) {
    if (!(Test-Path $envPath)) {
        $content = [IO.File]::ReadAllText("$projectRoot/.env.example")
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        foreach ($key in @('DJANGO_SECRET_KEY','POSTGRES_PASSWORD','INFRA_POSTGRES_PASSWORD','KEYCLOAK_DB_PASSWORD','KEYCLOAK_ADMIN_PASSWORD')) {
            $randomBytes = New-Object byte[] 32
            $rng.GetBytes($randomBytes)
            $value = [BitConverter]::ToString($randomBytes).Replace('-','').ToLowerInvariant()
            $content = [regex]::Replace($content, "(?m)^$key=.*$", "$key=$value")
        }
        $rng.Dispose()
        $content = [regex]::Replace($content, '(?m)^TLS_DIR=.*$', 'TLS_DIR=' + $tlsPath.Replace('\','/'))
        [IO.File]::WriteAllText($envPath, $content, $utf8)
    }
    New-Item -ItemType Directory -Force $tlsPath | Out-Null
    Invoke-Docker run --rm --mount "type=bind,source=$tlsPath,target=/certs" --mount "type=bind,source=$PSScriptRoot/certificates.sh,target=/certificates.sh,readonly" alpine:3.22 sh -c 'apk add --no-cache openssl >/dev/null && sh /certificates.sh'
    # Listar não gera erro quando a rede ainda não existe (PowerShell 5.1).
    $localNetworks = & docker network ls --format '{{.Name}}'
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível consultar as redes Docker.' }
    if ($localNetworks -notcontains 'hospital-local-transit') { Invoke-Docker network create --internal hospital-local-transit }
}
switch ($Action) {
    prepare { Write-Host 'Configuração local preparada. Chaves e .env fora do Git.' }
    { $_ -in @('up','dev') } {
        Compose-Internal up -d --build --wait postgresql
        Compose-Internal build backend
        Compose-Internal run --rm --no-deps backend python manage.py migrate --noinput
        if ($Action -eq 'dev') {
            Invoke-Docker compose --project-name hospital-interna --env-file $envPath -f "$projectRoot/rede-interna/docker-compose.yml" -f "$projectRoot/rede-interna/compose.local.yaml" -f "$projectRoot/rede-interna/compose.dev.yaml" up -d --force-recreate --wait backend
        } else {
            Compose-Internal up -d --force-recreate --wait backend
        }
        # Vault, Keycloak e seu banco pertencem à infraestrutura padrão.
        if ($Action -eq 'dev') {
            Invoke-Docker compose --project-name hospital-interna --env-file $envPath -f "$projectRoot/rede-interna/docker-compose.yml" -f "$projectRoot/rede-interna/compose.local.yaml" -f "$projectRoot/rede-interna/compose.dev.yaml" up -d --wait --wait-timeout 180
        } else {
            Compose-Internal up -d --wait --wait-timeout 180
        }
        Compose-Dmz up -d --build --force-recreate --wait
        Write-Host 'Aplicação: https://localhost:8443 (CA de teste em integration/tls/ca.crt).'
    }
    down {
        Compose-Dmz down
        Compose-Internal down
        Write-Host 'Containers encerrados. Volumes e certificados preservados.'
    }
    status { Compose-Internal ps; Compose-Dmz ps }
    test {
        Compose-Internal exec -T backend python manage.py check
        Compose-Internal exec -T backend python manage.py makemigrations --check --dry-run
        # Banco de testes separado; somente durante esta execução recebe CREATEDB.
        try {
            Set-TestDatabasePermission CREATEDB
            Compose-Internal exec -T backend python manage.py test --noinput --settings=config.test_settings
        }
        finally { Set-TestDatabasePermission NOCREATEDB }
    }
}
