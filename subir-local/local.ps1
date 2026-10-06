param([ValidateSet('prepare','up','dev','down','status','test','monitoring-test')][string]$Action = 'up')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$envPath = Join-Path $PSScriptRoot '.env'
$tlsPath = Join-Path $PSScriptRoot 'tls'
$wazuhPath = Join-Path $PSScriptRoot 'wazuh-runtime'
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
    # Acrescenta somente as novas configurações, preservando segredos existentes.
    $content = [IO.File]::ReadAllText($envPath)
    $content = [regex]::Replace($content, '(?m)^TLS_DIR=[^\r\n]*', 'TLS_DIR=' + $tlsPath.Replace('\','/'))
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    foreach ($key in @('WAZUH_INDEXER_ADMIN_PASSWORD','WAZUH_DASHBOARD_PASSWORD','WAZUH_API_PASSWORD','WAZUH_ENROLLMENT_PASSWORD')) {
        if ($content -notmatch "(?m)^$key=(?!SUBSTITUA)[^\r\n]+") {
            $bytes = New-Object byte[] 20
            $rng.GetBytes($bytes)
            $value = 'Aa1!' + [BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
            if ($content -match "(?m)^$key=") { $content = [regex]::Replace($content, "(?m)^$key=[^\r\n]*", "$key=$value") }
            else { $content += "`n$key=$value`n" }
        }
    }
    $rng.Dispose()
    if ($content -match '(?m)^WAZUH_RUNTIME_DIR=') {
        $content = [regex]::Replace($content, '(?m)^WAZUH_RUNTIME_DIR=[^\r\n]*', 'WAZUH_RUNTIME_DIR=' + $wazuhPath.Replace('\','/'))
    } else { $content += "`nWAZUH_RUNTIME_DIR=$($wazuhPath.Replace('\','/'))`n" }
    [IO.File]::WriteAllText($envPath, $content, $utf8)
    New-Item -ItemType Directory -Force $wazuhPath | Out-Null
    Invoke-Docker build -t hospital-wazuh-prepare "$projectRoot/rede-interna/wazuh/prepare"
    Invoke-Docker run --rm --network none --mount "type=bind,source=$envPath,target=/setup.env,readonly" --mount "type=bind,source=$wazuhPath,target=/runtime" hospital-wazuh-prepare
    Invoke-Docker run --rm --mount "type=bind,source=$tlsPath,target=/certs" --mount "type=bind,source=$PSScriptRoot/certificates.sh,target=/certificates.sh,readonly" alpine:3.22 sh -c 'if [ ! -e /certs/public.key ]; then apk add --no-cache openssl >/dev/null; fi; sh /certificates.sh'
    # Listar não gera erro quando a rede ainda não existe (PowerShell 5.1).
    $localNetworks = & docker network ls --format '{{.Name}}'
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível consultar as redes Docker.' }
    if ($localNetworks -notcontains 'hospital-local-transit') { Invoke-Docker network create --internal hospital-local-transit }
    if ($localNetworks -notcontains 'hospital-wazuh-transit') { Invoke-Docker network create --internal hospital-wazuh-transit }
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
        Compose-Internal up -d --wait --wait-timeout 600 wazuh-indexer wazuh-manager
        foreach ($group in @('dmz','dados','endpoints')) {
            Compose-Internal exec -T wazuh-manager sh -c 'test -d /var/ossec/etc/shared/$1 || /var/ossec/bin/agent_groups -a -g $1 -q' -- $group
        }
        if ($Action -eq 'dev') {
            Invoke-Docker compose --project-name hospital-interna --env-file $envPath -f "$projectRoot/rede-interna/docker-compose.yml" -f "$projectRoot/rede-interna/compose.local.yaml" -f "$projectRoot/rede-interna/compose.dev.yaml" up -d --wait --wait-timeout 600
        } else {
            Compose-Internal up -d --wait --wait-timeout 600
        }
        Compose-Dmz up -d --build --force-recreate --wait --wait-timeout 600
        Write-Host 'Aplicação: https://localhost:8443 (CA de teste em subir-local/tls/ca.crt).'
        Write-Host 'Wazuh: https://localhost:9443; usuário admin, senha WAZUH_INDEXER_ADMIN_PASSWORD de subir-local/.env.'
    }
    down {
        Compose-Dmz down
        Compose-Internal down
        Write-Host 'Containers encerrados. Volumes e certificados preservados.'
    }
    status { Compose-Internal ps; Compose-Dmz ps }
    monitoring-test {
        $marker = [Guid]::NewGuid().ToString('N')
        foreach ($area in @('dmz','dados','endpoints')) {
            $line = @{ source='hospital.security'; event='monitoring_test'; test_id=$marker } | ConvertTo-Json -Compress
            [IO.File]::AppendAllText("$wazuhPath/canary/$area/events.jsonl", "$line`n", $utf8)
            [IO.File]::AppendAllText("$wazuhPath/canary/$area/baseline.txt", "test:$marker`n", $utf8)
        }
        $testScript = [IO.File]::ReadAllText("$PSScriptRoot/wazuh_test.py").Replace("`r`n", "`n")
        $testScript | & docker compose --project-name hospital-interna --env-file $envPath -f "$projectRoot/rede-interna/docker-compose.yml" -f "$projectRoot/rede-interna/compose.local.yaml" exec -T wazuh-manager /var/ossec/framework/python/bin/python3 - $marker
        if ($LASTEXITCODE -ne 0) { throw 'Falha na validacao Wazuh.' }
    }
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
