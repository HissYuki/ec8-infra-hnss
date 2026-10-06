# Entrega dos arquivos privados

Estas duas pastas ficam na raiz do checkout, são inteiramente ignoradas pelo Git
e não participam dos contextos de build. Envie-as por um canal seguro.

```text
senha-rede-interna/
  .env                       senhas/configuração do laboratório
  tls/                       certificado/chave do backend e CA de clientes
  wazuh-runtime/             PEMs, chaves e configurações privadas da central
  vault.hcl                  configuração privada local
  pki-local/                 autoridade certificadora do laboratório
  legacy/                    configuração antiga preservada, não utilizada
  servidor.env.example       modelo de implantação sem segredos
senha-dmz/
  .env                       configuração DMZ e inscrição do agente local
  tls/                       HTTPS público e certificado/chave cliente mTLS
  wazuh-runtime/             CA pública e arquivos de teste do agente DMZ
  servidor.env.example       modelo de implantação sem segredos
```

A DMZ não recebe senhas dos bancos, Django, Keycloak ou administradores Wazuh,
nem chaves privadas das autoridades certificadoras. A senha de inscrição do
agente é compartilhada com a central para o cadastro local. `pki-local` é material
administrativo de teste; não implante essa CA em produção.

## Teste local do colega

Use o mesmo commit, coloque **as duas pastas completas** na raiz do checkout e
inicie o Docker Desktop. No PowerShell:

```powershell
./subir-local/local.ps1 up
./subir-local/local.ps1 status
./subir-local/local.ps1 prometheus-test
./subir-local/local.ps1 monitoring-test
```

O script corrige os caminhos absolutos para o novo checkout, reaproveita segredos
e certificados existentes e reconstrói o `.env` da DMZ com uma lista explícita
de variáveis. Gera material somente quando ausente. Não execute `.env` como script
e não use `git add -f` nas pastas privadas.

Essas pastas **não transferem volumes, dados do banco ou o estado do Vault**.
Se o colega já tem volumes, as credenciais devem corresponder às usadas na criação
deles. Trocar o `.env` não troca senhas dos bancos, Keycloak ou Wazuh existentes.
Não apague volumes para resolver divergências; faça rotação/restauração coordenada.

## Máquinas reais

Envie apenas `senha-dmz` ao servidor DMZ e apenas `senha-rede-interna` ao interno.
Em cada pasta crie `servidor.env` a partir de `servidor.env.example`; esse é o
arquivo padrão dos scripts de servidor. O `.env` local não é usado por eles.

Ajuste IPs, DNS, targets Prometheus, SMTP e os caminhos absolutos `TLS_DIR`,
`WAZUH_RUNTIME_DIR` e `VAULT_CONFIG_FILE`. Provisione certificados para os nomes
reais e configure o firewall. Certificados locais usam localhost e curta validade;
copiar as pastas não prepara HTTPS de produção. Vault mantém o estado anterior;
esta organização não o inicializa nem dessela. Os limites de implantação continuam
documentados em `subir-servidor/README.md`.

Em Linux limite o acesso ao administrador e aos UIDs dos serviços que precisam
ler as chaves (Gunicorn 10001, indexer/dashboard 1000). Preserve permissões dos
guias; não aplique chmod recursivo indiscriminadamente.
