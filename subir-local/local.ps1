param([ValidateSet('prepare','up','dev','down','status','test','monitoring-test','backup-test','prometheus-test')][string]$Action = 'up')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$internalSecrets = Join-Path $projectRoot 'senha-rede-interna'
$dmzSecrets = Join-Path $projectRoot 'senha-dmz'
$envPath = Join-Path $internalSecrets '.env'
$dmzEnvPath = Join-Path $dmzSecrets '.env'
$tlsPath = Join-Path $internalSecrets 'tls'
$pkiPath = Join-Path $internalSecrets 'pki-local'
$dmzTlsPath = Join-Path $dmzSecrets 'tls'
$wazuhPath = Join-Path $internalSecrets 'wazuh-runtime'
$dmzWazuhPath = Join-Path $dmzSecrets 'wazuh-runtime'
$utf8 = New-Object System.Text.UTF8Encoding($false)
function Invoke-Docker {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Docker falhou: $($args[0])" }
}
function Compose-Internal {
    Invoke-Docker compose --project-name hospital-interna --env-file $envPath -f "$projectRoot/rede-interna/docker-compose.yml" -f "$projectRoot/rede-interna/compose.local.yaml" @args
}
function Compose-Dmz {
    Invoke-Docker compose --project-name hospital-dmz --env-file $dmzEnvPath -f "$projectRoot/dmz/docker-compose.yml" -f "$projectRoot/dmz/compose.local.yaml" @args
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
    foreach ($directory in @($internalSecrets,$dmzSecrets,$tlsPath,$pkiPath,$dmzTlsPath,$dmzWazuhPath)) {
        New-Item -ItemType Directory -Force $directory | Out-Null
    }
    if (!(Test-Path "$internalSecrets/servidor.env.example")) { Copy-Item -LiteralPath "$projectRoot/subir-servidor/Rede Interna/.env.example" -Destination "$internalSecrets/servidor.env.example" }
    if (!(Test-Path "$dmzSecrets/servidor.env.example")) { Copy-Item -LiteralPath "$projectRoot/subir-servidor/DMZ/.env.example" -Destination "$dmzSecrets/servidor.env.example" }
    # Migração única das localizações anteriores; nunca sobrescreve material existente.
    foreach ($pair in @(@("$PSScriptRoot/.env",$envPath),@("$PSScriptRoot/tls",$pkiPath),@("$PSScriptRoot/wazuh-runtime",$wazuhPath))) {
        $source = [IO.Path]::GetFullPath($pair[0]); $destination = [IO.Path]::GetFullPath($pair[1])
        if (!$source.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar) -or !$destination.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar)) { throw 'Migração fora do repositório bloqueada.' }
        if (Test-Path $source) {
            if ((Test-Path $destination) -and ((Get-Item $destination).PSIsContainer) -and !(Get-ChildItem -Force $destination)) { Remove-Item -LiteralPath $destination }
            if ((Get-Item -LiteralPath $source).PSIsContainer) {
                # Docker Desktop pode impedir um rename de diretório montado.
                # Copia e confere cada arquivo antes de remover somente a origem privada antiga.
                foreach ($file in @(Get-ChildItem -LiteralPath $source -Recurse -File -Force)) {
                    $relative = $file.FullName.Substring($source.Length + 1)
                    $target = Join-Path $destination $relative
                    New-Item -ItemType Directory -Force (Split-Path $target -Parent) | Out-Null
                    if (Test-Path $target) {
                        if ((Get-FileHash -LiteralPath $target).Hash -ne (Get-FileHash -LiteralPath $file.FullName).Hash) { throw 'Arquivos privados divergentes; migração interrompida sem sobrescrever.' }
                    } else { Copy-Item -LiteralPath $file.FullName -Destination $target -Force }
                    if ((Get-FileHash -LiteralPath $target).Hash -ne (Get-FileHash -LiteralPath $file.FullName).Hash) { throw 'Falha na conferência da cópia privada.' }
                }
                Remove-Item -LiteralPath $source -Recurse -Force
            } else {
                if (Test-Path $destination) { throw 'Há material privado nas duas localizações; reconcilie-o antes de continuar.' }
                Move-Item -LiteralPath $source -Destination $destination -Force
            }
        }
    }
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
    # DNS de laboratório; nos servidores os targets são IPs/FQDNs roteáveis.
    foreach ($entry in @('PROMETHEUS_TARGET_VLAN10=node-exporter-dmz:9100','PROMETHEUS_TARGET_VLAN20=node-exporter-dados:9100','PROMETHEUS_TARGET_VLAN40=node-exporter-endpoints:9100')) {
        $key = $entry.Split('=')[0]
        if ($content -match "(?m)^$key=") { $content = [regex]::Replace($content, "(?m)^$key=[^\r\n]*", $entry) }
        else { $content += "`n$entry`n" }
    }
    $content = [regex]::Replace($content, '(?m)^TLS_DIR=[^\r\n]*', 'TLS_DIR=' + $tlsPath.Replace('\','/'))
    $privateVault = Join-Path $internalSecrets 'vault.hcl'
    if (!(Test-Path $privateVault)) { Copy-Item -LiteralPath "$projectRoot/rede-interna/vault/vault.local.hcl" -Destination $privateVault }
    $vaultConfig = $privateVault.Replace('\','/')
    if ($content -match '(?m)^VAULT_CONFIG_FILE=') {
        $content = [regex]::Replace($content, '(?m)^VAULT_CONFIG_FILE=[^\r\n]*', 'VAULT_CONFIG_FILE=' + $vaultConfig)
    } else { $content += "`nVAULT_CONFIG_FILE=$vaultConfig`n" }
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
    $requiredTls = @("$tlsPath/backend.crt","$tlsPath/backend.key","$tlsPath/client-ca.crt","$dmzTlsPath/public.crt","$dmzTlsPath/public.key","$dmzTlsPath/frontend.crt","$dmzTlsPath/frontend.key","$dmzTlsPath/backend-ca.crt")
    $presentTls = @($requiredTls | Where-Object { Test-Path $_ })
    if ($presentTls.Count -ne $requiredTls.Count) {
        if ($presentTls.Count -gt 0 -and !(Test-Path "$pkiPath/public.crt")) { throw 'Entrega TLS incompleta; copie as duas pastas privadas completas antes de continuar.' }
        Invoke-Docker run --rm --mount "type=bind,source=$pkiPath,target=/certs" --mount "type=bind,source=$PSScriptRoot/certificates.sh,target=/certificates.sh,readonly" alpine:3.22 sh -c 'if [ ! -e /certs/ca.key ]; then apk add --no-cache openssl >/dev/null; fi; sh /certificates.sh'
    }
    foreach ($name in @('backend.crt','backend.key','client-ca.crt')) {
        $source = Join-Path $pkiPath $name
        if (Test-Path $source) {
            if ($name.EndsWith('.key')) { if (!(Test-Path "$tlsPath/$name")) { Move-Item -LiteralPath $source -Destination "$tlsPath/$name" } }
            else { if (!(Test-Path "$tlsPath/$name")) { Copy-Item -LiteralPath $source -Destination "$tlsPath/$name" } }
        }
    }
    foreach ($name in @('public.crt','public.key','frontend.crt','frontend.key','backend-ca.crt','ca.crt')) {
        $source = Join-Path $pkiPath $name
        if (Test-Path $source) {
            if ($name.EndsWith('.key')) { if (!(Test-Path "$dmzTlsPath/$name")) { Move-Item -LiteralPath $source -Destination "$dmzTlsPath/$name" } }
            else { if (!(Test-Path "$dmzTlsPath/$name")) { Copy-Item -LiteralPath $source -Destination "$dmzTlsPath/$name" } }
        }
    }
    if (@($requiredTls | Where-Object { !(Test-Path $_) }).Count -gt 0) { throw 'Material TLS incompleto; nenhuma chave existente foi substituída.' }
    New-Item -ItemType Directory -Force "$dmzWazuhPath/certs" | Out-Null
    Copy-Item -LiteralPath "$wazuhPath/certs/root-ca.pem" -Destination "$dmzWazuhPath/certs/root-ca.pem" -Force
    if (!(Test-Path "$dmzWazuhPath/canary/dmz")) {
        New-Item -ItemType Directory -Force "$dmzWazuhPath/canary" | Out-Null
        Copy-Item -LiteralPath "$wazuhPath/canary/dmz" -Destination "$dmzWazuhPath/canary/dmz" -Recurse
    }
    # Lista explícita: nunca distribui senhas do backend/central à DMZ.
    $dmzKeys = @('PUBLIC_HOST','PUBLIC_ORIGIN','DMZ_BIND_IP','PUBLIC_HTTP_PORT','PUBLIC_HTTPS_PORT','PUBLIC_HTTPS_SUFFIX','BACKEND_URL','BACKEND_TLS_NAME','DMZ_DOCKER_SUBNET','FRONTEND_EGRESS_SUBNET','WAZUH_ENROLLMENT_PASSWORD','NODE_EXPORTER_BIND_IP','DMZ_NODE_EXPORTER_PORT')
    $dmzLines = @([IO.File]::ReadAllLines($envPath) | Where-Object { $dmzKeys -contains ($_ -split '=',2)[0] })
    $dmzLines += 'TLS_DIR=' + $dmzTlsPath.Replace('\','/')
    $dmzLines += 'WAZUH_RUNTIME_DIR=' + $dmzWazuhPath.Replace('\','/')
    [IO.File]::WriteAllLines($dmzEnvPath,$dmzLines,$utf8)
    # Listar não gera erro quando a rede ainda não existe (PowerShell 5.1).
    $localNetworks = & docker network ls --format '{{.Name}}'
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível consultar as redes Docker.' }
    if ($localNetworks -notcontains 'hospital-local-transit') { Invoke-Docker network create --internal hospital-local-transit }
    if ($localNetworks -notcontains 'hospital-wazuh-transit') { Invoke-Docker network create --internal hospital-wazuh-transit }
    if ($localNetworks -notcontains 'hospital-monitoring-transit') { Invoke-Docker network create --internal hospital-monitoring-transit }
}
switch ($Action) {
    prepare { Write-Host 'Configuração local preparada. Chaves e .env fora do Git.' }
    { $_ -in @('up','dev') } {
        Compose-Internal up -d --build --wait --wait-timeout 600 postgresql
        Compose-Internal build backend
        $migrationPlan = Compose-Internal run --rm --no-deps backend python manage.py migrate --plan
        Compose-Internal run --rm --no-deps backend python manage.py migrate --noinput
        if (($migrationPlan -join "`n") -notmatch 'No planned migration operations') {
            Compose-Internal exec -T postgresql su-exec postgres pgbackrest --config=/etc/pgbackrest.conf --stanza=hospital backup --type=diff
        }
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
        Write-Host 'Aplicação: https://localhost:8443 (CA de teste em senha-dmz/tls/ca.crt).'
        Write-Host 'Wazuh: https://localhost:9443; usuário admin, senha WAZUH_INDEXER_ADMIN_PASSWORD de senha-rede-interna/.env.'
    }
    down {
        Compose-Dmz down
        Compose-Internal down
        Write-Host 'Containers encerrados. Volumes e certificados preservados.'
    }
    status { Compose-Internal ps; Compose-Dmz ps }
    prometheus-test {
        $targets = (Invoke-RestMethod 'http://127.0.0.1:9090/api/v1/targets').data.activeTargets
        foreach ($job in @('prometheus','node_exporter_vlan10','node_exporter_vlan20','node_exporter_vlan40')) {
            $matches = @($targets | Where-Object { $_.labels.job -eq $job })
            if ($matches.Count -ne 1 -or $matches[0].health -ne 'up') { throw "Target $job não está UP." }
            Write-Host "$job : UP"
        }
        $metrics = (Invoke-RestMethod 'http://127.0.0.1:9090/api/v1/query?query=node_uname_info').data.result
        foreach ($vlan in @('10','20','40')) {
            if (!($metrics | Where-Object { $_.metric.vlan -eq $vlan })) { throw "Métricas ausentes na VLAN $vlan." }
        }
        Write-Host 'Coleta das VLANs 10, 20 e 40 validada (laboratório Docker).'
    }
    backup-test {
        $adminRole = (Compose-Internal exec -T postgresql printenv POSTGRES_USER).Trim()
        $appDatabase = (Compose-Internal exec -T postgresql printenv APP_DB).Trim()
        $control = Compose-Internal exec -T postgresql pg_controldata /var/lib/postgresql/data
        $systemId = ($control | Where-Object { $_ -match '^Database system identifier:' }) -replace '^Database system identifier:\s*',''
        $migrationCount = ('SELECT count(*) FROM django_migrations;' | & docker compose --project-name hospital-interna --env-file $envPath -f "$projectRoot/rede-interna/docker-compose.yml" -f "$projectRoot/rede-interna/compose.local.yaml" exec -T postgresql psql -U $adminRole -d $appDatabase -At).Trim()
        if ($LASTEXITCODE -ne 0 -or $systemId -notmatch '^\d+$' -or $migrationCount -notmatch '^\d+$') { throw 'Falha ao consultar metadados do banco.' }
        $image = (& docker inspect dados-postgres --format '{{.Image}}').Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao identificar imagem PostgreSQL.' }
        Invoke-Docker run --rm --network none --tmpfs '/restore:rw,size=512m' --tmpfs '/var/lib/postgresql/data:rw,size=16m' --mount 'type=volume,source=hospital-interna_pgbackrest_data,target=/var/lib/pgbackrest,readonly' --mount "type=bind,source=$projectRoot/rede-interna/pgbackrest/pgbackrest-dados.conf,target=/etc/pgbackrest.conf,readonly" --mount "type=bind,source=$PSScriptRoot/restore_backup_test.sh,target=/test.sh,readonly" -e "RESTORE_DB_USER=$adminRole" -e "RESTORE_APP_DB=$appDatabase" -e "EXPECTED_SYSTEM_ID=$systemId" -e "EXPECTED_MIGRATIONS=$migrationCount" --entrypoint /bin/bash $image /test.sh
    }
    monitoring-test {
        $marker = [Guid]::NewGuid().ToString('N')
        foreach ($area in @('dmz','dados','endpoints')) {
            $canaryRoot = $wazuhPath
            if ($area -eq 'dmz') { $canaryRoot = $dmzWazuhPath }
            $line = @{ source='hospital.security'; event='monitoring_test'; test_id=$marker } | ConvertTo-Json -Compress
            [IO.File]::AppendAllText("$canaryRoot/canary/$area/events.jsonl", "$line`n", $utf8)
            [IO.File]::AppendAllText("$canaryRoot/canary/$area/baseline.txt", "test:$marker`n", $utf8)
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
