# Execução separada nos servidores

Scripts Bash para hosts Linux com Docker Engine e Compose v2. O ambiente local
Windows continua usando `../subir-local/local.ps1`. Não execute estes scripts
de servidor no laboratório: os nomes de projeto são iguais para preservar a
identidade dos volumes, mas redes e configurações são diferentes.

Cada script controla somente o Compose da sua máquina, a partir de qualquer
diretório. Não usa `compose.local.yaml`, não cria bridges entre hosts, não
instala agentes Docker de laboratório, não gera certificados nem senhas e não
inicializa/unseala o Vault. `down` preserva volumes. O padrão sem argumento é
`status`, para evitar iniciar serviços acidentalmente.

## Preparação

1. Use o mesmo commit do repositório nas duas máquinas. No build atual do
   frontend, `backend_source` lê o código do backend para coletar estáticos do
   Admin. Portanto, mantenha o checkout completo para construir a imagem; a
   imagem final do frontend não contém o backend. Alternativamente, construa
   imagens em CI e adapte o Compose para distribuí-las com versões fixas.
2. Em cada máquina, copie apenas seu `.env.example` para `servidor.env` na pasta
   privada `senha-rede-interna/` ou `senha-dmz/` da raiz do checkout. Preencha os
   valores e aplique `chmod 600` ao arquivo. Não reutilize o `.env` local.
   `ENV_FILE=/etc/hospital/dmz.env` ou `/etc/hospital/interna.env` permite manter
   segredos fora do checkout. Use valores dotenv literais, sem referências a
   outras variáveis. Os scripts não executam `.env` como código.
3. Defina interfaces/IPs existentes, domínio/DNS, horário sincronizado, rotas
   e firewall. As bridges Docker não representam VLANs físicas. Ajuste subnets
   que conflitem com redes reais/VPN. Publique backend apenas na interface VLAN
   20; Manager na VLAN 30; painéis apenas na gestão/VPN ou via túnel local.
4. Provisione os certificados em `TLS_DIR`. Rede Interna: `backend.crt`,
   `backend.key`, `client-ca.crt`. DMZ: `public.crt` (cadeia completa),
   `public.key`, `backend-ca.crt`, `frontend.crt`, `frontend.key`.
   Configure SAN/CA/validade/renovação e permissões. O backend UID 10001 precisa
   ler sua chave; não distribua chaves privadas das CAs.
5. Prepare Wazuh no caminho `WAZUH_RUNTIME_DIR`: certificados `root-ca.pem`,
   `wazuh.manager.pem`, `wazuh.manager-key.pem`, `wazuh.indexer.pem`,
   `wazuh.indexer-key.pem`, `wazuh.dashboard.pem`, `wazuh.dashboard-key.pem`,
   `admin.pem`, `admin-key.pem` sob `certs/`, e arquivos `authd.pass`,
   `internal_users.yml` e `wazuh.yml`. Use as ferramentas oficiais Wazuh e
   certificados da implantação, não o gerador de certificados locais de 30 dias.
   Hashes bcrypt, senha de enrollment e credenciais API/Indexer/Dashboard devem
   corresponder ao `.env`; configuração de DN/SAN deve corresponder aos arquivos
   em `rede-interna/wazuh/config/`. Preserve permissões necessárias aos UIDs
   dos serviços. Veja também [o guia Wazuh](../rede-interna/wazuh/README.md).
   Configure `vm.max_map_count >= 262144` no host do Docker.
6. Configure SMTP e valide envio real. Garanta backup/restauração, capacidade
   de disco, rotação dos logs e retenção dos índices antes de usar dados reais.
7. Prepare `VAULT_CONFIG_FILE` como arquivo privado absoluto. O exemplo do
   colega `rede-interna/vault/vault.hcl.example` prevê Transit/KMS; o token
   restrito vem de `VAULT_TRANSIT_SEAL_TOKEN`. Nenhum script faz init/unseal ou
   migração de seal. O KMS recebe a configuração `kms.hcl` e volume persistente;
   habilitar Transit/chave/política depende de procedimento administrativo.
   Defina `PROMETHEUS_BIND_IP`/`KMS_BIND_IP` somente na gestão/VPN ou loopback.
   Consulte [os detalhes da integração](../rede-interna/README-integracao.md).

**Pendências da configuração herdada:** Keycloak ainda usa `start-dev` e imagem
`latest`; Vault tem TLS desativado e precisa de inicialização/unseal controlados.
Esses scripts preservam os serviços, mas não corrigem automaticamente tais
pendências. A implantação definitiva exige ajustes específicos, inclusive a
associação Keycloak/banco às redes e binds administrativos separados se necessário.
`check` valida estrutura e arquivos; não certifica prontidão para produção.

## Ordem dos comandos

Na raiz do checkout da **Rede Interna**:

```bash
mkdir -p senha-rede-interna
cp 'subir-servidor/Rede Interna/.env.example' senha-rede-interna/servidor.env
# Preencha o .env e provisione os certificados antes de continuar.
chmod 600 senha-rede-interna/servidor.env
bash 'subir-servidor/Rede Interna/subir.sh' check
# Primeira instalação/atualização: faça backup antes das migrations.
bash 'subir-servidor/Rede Interna/subir.sh' migrate
bash 'subir-servidor/Rede Interna/subir.sh' up
bash 'subir-servidor/Rede Interna/subir.sh' status
```

Em volume PostgreSQL novo, o init script provisiona o banco da aplicação.
Em volume existente, confirme banco/role e senhas antes: variáveis de ambiente
não alteram senhas de roles já criados. Não recrie o volume para corrigir isso.

Depois, na raiz do checkout da **DMZ**:

```bash
mkdir -p senha-dmz
cp subir-servidor/DMZ/.env.example senha-dmz/servidor.env
# Preencha o .env e provisione os certificados antes de continuar.
chmod 600 senha-dmz/servidor.env
bash subir-servidor/DMZ/subir.sh check
bash subir-servidor/DMZ/subir.sh up
bash subir-servidor/DMZ/subir.sh status
```

Para logs: substitua `status` por `logs`. Logs administrativos podem conter
informações sensíveis; não os publique. Para encerrar: `down` na DMZ, depois
`down` na Rede Interna. Nunca acrescente `-v`, nem remova volumes.

## Validação nas máquinas reais

Os testes de automação estão em `tests/test_scripts.py` e usam um Docker falso:
verificam separação dos projetos, ausência dos overrides locais, migrations
explícitas, rejeição de placeholders/flags extras e preservação de volumes.
Não substituem a execução nas duas máquinas reais. Para executá-los em container:

```bash
docker run --rm --network none -v "$PWD:/workspace:ro" -w /workspace python:3.13-slim python subir-servidor/tests/test_scripts.py
```

Permita DMZ/frontend → backend TCP 8444 com mTLS; agentes autorizados → Manager
TCP 1514 e TCP 1515 apenas durante cadastro; painel Wazuh somente gestão/VPN.
PostgreSQL não é publicado e não deve ficar acessível pela DMZ/Internet.
Valide também os filtros de encaminhamento do host Docker, não só o pfSense.
Instale agentes Wazuh nativos em cada máquina; os scripts não os instalam.
Para métricas, permita Prometheus/VLAN 30 → exporters TCP 9100 (ou a porta
configurada) nas VLANs 10, 20 e 40, sem exposição pública. Configure os targets
por IP/FQDN e instale exporters nas estações. Veja
[o guia do Prometheus](../rede-interna/prometheus/README.md).

Teste HTTPS, login dos quatro perfis, CSRF, MFA, Admin, recuperação via SMTP,
consultas/exames/agendas, eventos Wazuh, persistência e restauração de backups.
Ferramentas novas do colega deverão ser adicionadas aos Compose da máquina
correspondente e homologadas; não existe integração automática com elas.
