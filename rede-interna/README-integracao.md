# Integração da main com a aplicação e Wazuh

Foram preservados os serviços da main: Prometheus, Node Exporter, pgBackRest e
KMS/Vault, junto à aplicação, seus bancos, Keycloak e Wazuh. Grafana não consta
na main integrada; não foi criado um serviço novo para substituir o trabalho
do colega. Os projetos continuam `hospital-interna` e `hospital-dmz`; mudar
esses nomes seleciona outros volumes. Não use `down -v` nem remova volumes.

## Execução local

```powershell
./subir-local/local.ps1 up
./subir-local/local.ps1 status
./subir-local/local.ps1 test
./subir-local/local.ps1 monitoring-test
./subir-local/local.ps1 prometheus-test
./subir-local/local.ps1 backup-test
./subir-local/local.ps1 down
```

Prometheus: http://localhost:9090; targets `prometheus`, `node_exporter_vlan10`,
`node_exporter_vlan20` e `node_exporter_vlan40` devem estar `UP`. Seu volume
persiste métricas; retenção por tempo/tamanho é configurável. Exporters locais
publicam portas somente em loopback. Consulte [a implantação entre VLANs](prometheus/README.md).
Em Linux
real, os mounts de `/proc`, `/sys` e `/` pertencem ao host Docker. No laboratório
Docker Desktop, `/proc`/`/sys` são da VM Linux e `/rootfs` usa um volume vazio:
não equivale a monitorar o Windows e evita compartilhar toda sua raiz.

PostgreSQL continua na versão principal 15, com `pgbackrest` instalado na imagem
criada pelo colega. Configuração, stanza `hospital`, `archive_command` e volume
do repositório foram alinhados. Readiness exige validar WAL e backup inicial.
`pgbackrest-repo` preserva o container do colega como observador read-only do
volume compartilhado; não é um servidor remoto pgBackRest. As redes atribuídas
a ele não tornam o repositório remoto: isso exige transporte/configuração própria.

`backup-test` restaura em tmpfs num container sem rede, montando o repositório
read-only. Não monta o PGDATA original, não apaga volumes e não imprime registros
de pacientes. Verifica a identidade do cluster, migrations e tabelas Django.
Se o backup estiver desatualizado após alteração de esquema, o teste falha:
faça um backup novo. Localmente, migrations pendentes geram um backup diferencial
após aplicação; no servidor, a ação explícita `migrate` também gera um diferencial.
Boot normal não cria repetidamente backups completos. Agendamento periódico,
retenção, cópia fora do host e proteção dos backups ainda precisam de definição.

## Vault e KMS: preservação do estado

Vault: http://localhost:8200/ui/. KMS: http://localhost:8201/ui/.
O listener do KMS usa 8200 internamente, coerente com a publicação 8201:8200.
Ambos usam volumes persistentes. Podem subir selados/não inicializados: isso é
diferente de estarem prontos para fornecer segredos. Nenhum script faz init,
unseal, migração de seal ou grava chaves/root token nos logs.

O laboratório usa `vault.local.hcl` (Shamir), preservando o estado anterior.
`VAULT_CONFIG_FILE` seleciona o arquivo montado no Vault. A configuração privada
do colega `vault.hcl` continua ignorada; o exemplo Transit foi preservado sem
token embutido. Depois de configurar chave `autounseal`, política restrita e
token no KMS, o Vault pode usar `VAULT_TRANSIT_SEAL_TOKEN` conforme o mecanismo
nativo. Não use root token como credencial de auto-unseal. Não troque o seal de
um volume inicializado sem planejar a migração e custodiar as chaves necessárias.
Inicialização deve salvar material de recuperação por canal privado, não em
Git, logs Docker ou mensagens. Um token real removido do Git precisa ser revogado
ou rotacionado: remover o arquivo não elimina o segredo do histórico remoto.

Não ativamos auto-unseal no volume local nem buscamos senhas do banco no Vault.
Essa ligação depende da configuração privada/KMS e foi anteriormente adiada.
Nos servidores, configure TLS no Vault/KMS, anúncios de endereço, acesso via
gestão/VPN e auditoria. A simulação HTTP local não é a implantação definitiva.

Referências oficiais:
- https://pgbackrest.org/user-guide.html
- https://developer.hashicorp.com/vault/docs/configuration/seal/transit
- https://developer.hashicorp.com/vault/docs/concepts/seal
- https://prometheus.io/docs/guides/node-exporter/

## Scripts consolidados

Os scripts Linux `integration/interna.sh` e `integration/dmz.sh` da main foram
consolidados nos scripts por máquina já presentes em `subir-servidor/`. Não
mantemos uma segunda pasta `integration`, nem scripts que carregam overrides
locais entre servidores. A aplicação e seus estáticos continuam nas mesmas
pastas, sem refatoração de regras de negócio. Veja o README de `subir-servidor`
para pré-requisitos, ambiente privado, certificados e ordem de implantação.
