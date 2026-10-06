# Wazuh — central e agentes

Esta configuração adapta o single-node oficial do Wazuh 4.14.8. A central faz
parte da subida padrão da Rede Interna, sem profiles opcionais. A configuração
original está em https://github.com/wazuh/wazuh-docker/tree/v4.14.8/single-node;
a licença do upstream foi preservada em `UPSTREAM-LICENSE`.

## Topologia

Manager e Dashboard pertencem à VLAN 30. Indexer fica na rede privada
`wazuh_core`, junto aos dois, sem porta publicada. Essa rede isola a camada de
indexação na máquina de serviços; não representa outra VLAN física.

Somente o override local cria `hospital-wazuh-transit`, uma bridge interna para
simular o transporte dos agentes das VLANs 10, 20 e 40 até o Manager. Ela não
conecta a DMZ ao banco da aplicação. O Manager não pertence à rede `db_app`.

Os três agentes Docker são de laboratório: monitoram os arquivos montados,
o inventário do próprio container e eventos sanitizados. Não equivalem a agentes
instalados nos servidores ou nas estações. Nenhum recebe socket Docker, mount
da raiz do host ou modo privilegiado. Na implantação real, instale um agente
nativo em cada servidor/estação monitorada, depois de definir seus sistemas
operacionais. Um agente por VLAN não monitora automaticamente toda a VLAN.

## Execução local

Na raiz do repositório, usando PowerShell:

```powershell
./subir-local/local.ps1 up
./subir-local/local.ps1 status
./subir-local/local.ps1 test
./subir-local/local.ps1 monitoring-test
./subir-local/local.ps1 down
```

Painel: https://localhost:9443. Usuário `admin`; senha na variável
`WAZUH_INDEXER_ADMIN_PASSWORD` de `subir-local/.env`. A CA de teste está em
`subir-local/wazuh-runtime/certs/root-ca.pem`. Os certificados locais valem
30 dias e não substituem certificados de implantação.

O bootstrap gera senhas aleatórias, hashes bcrypt nativos e certificados por
OpenSSL em `subir-local/wazuh-runtime/`, ignorado pelo Git. Preserva senhas,
certificados e volumes existentes. Alterar uma senha apenas no `.env` não
rotaciona contas já inicializadas: a rotação precisa ser coordenada com os
serviços. A chave privada da CA não é montada nos serviços nem nos agentes.
Agentes verificam a CA do Manager no cadastro e utilizam senha de enrollment;
depois utilizam as chaves individuais geradas pelo Wazuh.

Indexer e Dashboard verificam certificados. O Indexer não expõe 9200 e a API
do Manager não expõe 55000. O painel e as portas de agentes ficam publicados
somente em `127.0.0.1` por padrão. Credenciais não devem ir para o Git.

O Wazuh recomenda ao menos 4 CPUs, 8 GB de RAM e 50 GB para a central Docker.
Como aqui também rodam os demais serviços hospitalares, reserve RAM adicional
(preferencialmente 12–16 GB para o conjunto) e acompanhe `docker stats`.
O host Linux/WSL precisa de `vm.max_map_count >= 262144`. Ajuste no host correto,
não no container da aplicação. Os limites/heap atuais são para desenvolvimento.

## Coleta e privacidade

O backend escreve JSON em um volume próprio: eventos de senha aceita/rejeitada,
logout, configuração/verificação/falha de MFA e uso de recuperação MFA. Senha
aceita não significa MFA concluído. Os eventos contêm somente categoria e tipo
de perfil; não contêm identidade, e-mail, IP, token, senha, código MFA ou dados
clínicos. O agente `lab-dados` lê esse volume como somente leitura.

FIM monitora configurações públicas e arquivos de validação, com
`report_changes=no`; não coleta conteúdo de alterações. Não monitora os
diretórios de dados PostgreSQL, `.env`, certificados ou material privado.
Os logs completos de requisições do WAF continuam desativados para não coletar
informações sensíveis. Integrar alertas sanitizados do WAF é uma etapa posterior.
Active Response está desativado: a implantação não executa bloqueios automáticos
nas máquinas hospitalares.

Os arquivos `canary/*/events.jsonl` permitem testes benignos de coleta:
uma linha JSON com `source= hospital.security` e `event= monitoring_test`
produz a regra 100110. Não coloque informações pessoais nesses arquivos.
Os eventos reais do backend são coletados independentemente desses testes.
Configure rotação externa do arquivo de auditoria no servidor: o backend usa
`WatchedFileHandler`, que acompanha a troca de arquivo por logrotate.

## Validação local realizada

Foram validados: subida dos 14 serviços, login HTTPS no painel, três agentes
ativos, ingestão TLS, FIM sem conteúdo dos arquivos e eventos reais de
autenticação/MFA com somente os campos `source`, `event` e `role`.
Os 67 testes Django passaram, os checks não apontaram problemas e não há
models sem migration. O teste pelo navegador cobriu os quatro perfis, CSRF,
MFA, recuperação de senha, calendários e anotações de consultas.
Os identificadores dos dois clusters PostgreSQL permaneceram os mesmos após
o reinício da máquina; nenhum volume foi removido.

No Docker Compose 2.24, as conexões do frontend usam prioridades explícitas
para conectar também a rede local antes de resolver o hostname do backend.
O teste de isolamento verifica essas conexões e o bloqueio das rotas ao banco.

## Servidores e firewall

Bridge Docker é local ao host. Nos servidores, use o endereço roteável da VLAN
30 em `WAZUH_BIND_IP`; configure cada agente nativo com esse endereço/FQDN.
O Manager não precisa participar diretamente das VLANs 10, 20 ou 40.
O roteamento entre VLANs e as regras abaixo pertencem aos hosts/firewall:

| Origem | Destino | Porta | Política |
|---|---|---|---|
| Hosts monitorados VLAN 10/20/40 | Manager VLAN 30 | TCP 1514 | Eventos, somente IPs autorizados |
| Hosts em cadastro VLAN 10/20/40 | Manager VLAN 30 | TCP 1515 | Enrollment autenticado, restringir à janela de cadastro |
| Administradores via VPN/rede de gestão | Dashboard | TCP 9443 configurável | HTTPS administrativo |
| Dashboard / Manager | Indexer | TCP 9200 | Apenas rede privada Docker |
| Dashboard | Manager API | TCP 55000 | Apenas rede privada Docker |
| Internet / DMZ | PostgreSQL | TCP 5432 | Bloqueado; sem publicação |
| Internet | Wazuh | Todas | Bloqueado |

Defina `WAZUH_DASHBOARD_BIND_IP` em uma interface administrativa, nunca exponha
o painel indiscriminadamente. Certificados reais devem incluir os FQDNs corretos.
TLS, regras de firewall e instalação dos agentes nativos precisam ser validados
nas duas máquinas reais; o teste local não aplica essas regras físicas.

Após definir os sistemas operacionais, siga a instalação oficial para cada host:
https://documentation.wazuh.com/current/installation-guide/wazuh-agent/index.html.
Configure endereço/FQDN do Manager na VLAN 30, protocolo TCP/porta 1514,
enrollment TCP/1515 com CA e arquivo de senha entregue por canal seguro,
nome único da máquina e grupo `dmz`, `dados` ou `endpoints`. Confirme que o host
aparece como `Active` no painel e teste uma alteração benigna de arquivo
monitorado. Adapte as fontes de logs/FIM ao sistema operacional; não copie
`agent-lab.conf` sem adaptação, pois seus caminhos pertencem aos mounts Docker.

Persistem em volumes separados: índices, configuração/API/chaves dos agentes,
fila, logs e dados Filebeat. `down` preserva esses volumes. Não execute `down -v`,
`docker volume rm` ou limpeza de volumes. Backup e retenção devem ser definidos
para os servidores antes do uso com dados reais.

Referências: https://documentation.wazuh.com/current/deployment-options/docker/wazuh-container.html
e https://documentation.wazuh.com/current/user-manual/agent/agent-enrollment/security-options/index.html.
