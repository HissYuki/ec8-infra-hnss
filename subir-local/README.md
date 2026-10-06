# Integração da aplicação com DMZ e Rede Interna

## Fluxo implementado

```text
Browser HTTPS → nginx-proxy → ModSecurity WAF → nginx-web
                                                 │ HTTPS + mTLS, TCP 8444
                                                 ▼
                                      Gunicorn / Django → PostgreSQL
                                           VLAN 20        rede db_app
```

O frontend na DMZ entrega CSS, JavaScript, imagens e arquivos estáticos do Django
Admin; encaminha as requisições dinâmicas. Os templates continuam renderizados
no Django da Rede Interna. Esta é a opção A: preserva formulários, sessões, CSRF,
MFA e autorização. Não é uma SPA nem uma camada de apresentação independente.
Os Dockerfiles de rede-interna/backend/ e dmz/frontend/ são construídos do mesmo
commit. O contexto adicional backend_source fornece ao coletor os estáticos
do Admin. A imagem frontend contém apenas Nginx e o resultado de
`collectstatic`, sem código Python, templates, dependências Python ou segredos.

O antigo Compose isolado da raiz foi removido; estes dois projetos Compose
são a arquitetura vigente.
O PostgreSQL integrado é o serviço `postgresql` já definido na Rede Interna,
mantendo PostgreSQL 15 e seu ponto de montagem. Não foi criado outro serviço de
banco para a aplicação. O banco `hospital` e seu proprietário sem SUPERUSER,
CREATEDB ou CREATEROLE são provisionados na primeira inicialização do volume.
Esse proprietário pode aplicar migrations no próprio banco. Sessões e MFA ficam
no PostgreSQL; nenhuma sessão depende de arquivos locais do backend.

## Teste local no Windows

Docker Desktop com containers Linux e Compose v2. Na raiz do repositório:

```powershell
./subir-local/local.ps1 up
./subir-local/local.ps1 status
./subir-local/local.ps1 test
./subir-local/local.ps1 monitoring-test
```

Acesse **https://localhost:8443**. HTTP em `http://localhost:18080` redireciona
para HTTPS. A porta 8080 do computador já estava ocupada durante a integração.
A CA é exclusivamente de teste e expira em 30 dias. O navegador exibirá um aviso
de certificado até que você confie na CA local. Não use esses certificados em
servidores. O script não instala uma CA na máquina e não substitui chaves
existentes automaticamente. `prepare` somente gera configuração/certificados.
Para regenerar uma CA local expirada, execute explicitamente o script
`certificates.sh --regenerate` no container auxiliar e reinicie os serviços TLS.

O script gera `subir-local/.env` com senhas aleatórias e arquivos em
`subir-local/tls/`, todos ignorados pelo Git. A configuração antiga fica em
subir-local/legacy/.env (ignorada). Não apaga `hospital-git_postgres_data`. O volume integrado é
`hospital-interna_postgres_data`. O banco novo inicia sem os usuários e consultas
anteriores, conforme autorizado. As migrations preservadas criam o esquema e os
nove exames padrão. Nenhum dump ou importação foi executado.

Comandos Django, executados na raiz:

```powershell
docker compose -p hospital-interna --env-file subir-local/.env -f rede-interna/docker-compose.yml -f rede-interna/compose.local.yaml exec backend python manage.py createsuperuser
docker compose -p hospital-interna --env-file subir-local/.env -f rede-interna/docker-compose.yml -f rede-interna/compose.local.yaml exec backend python manage.py migrate
docker compose -p hospital-interna --env-file subir-local/.env -f rede-interna/docker-compose.yml -f rede-interna/compose.local.yaml exec backend python manage.py makemigrations
docker compose -p hospital-interna --env-file subir-local/.env -f rede-interna/docker-compose.yml -f rede-interna/compose.local.yaml logs -f backend
```

A subida padrão da Rede Interna inclui backend, PostgreSQL da aplicação, Vault,
PostgreSQL do Keycloak e Keycloak, sem necessidade de profiles. No ambiente local:

- Keycloak: http://localhost:8180/admin/ (porta configurável por KEYCLOAK_PORT).
- Vault: http://localhost:8200/ui/.
- Wazuh: https://localhost:9443 (usuário `admin`; senha em `WAZUH_INDEXER_ADMIN_PASSWORD`).

A central Wazuh também faz parte da subida padrão. Os três agentes Docker são
de laboratório; a implantação nos servidores exige agentes nativos por máquina.
Consulte [a configuração e os limites dos testes locais](../rede-interna/wazuh/README.md).

As credenciais administrativas do Keycloak ficam nas variáveis KEYCLOAK_ADMIN e
KEYCLOAK_ADMIN_PASSWORD de subir-local/.env. Em um volume Vault novo, o servidor
inicia não inicializado e selado; inicialização e unseal são operações próprias,
sem geração automática de tokens/chaves pelo script. A interface disponível não
significa que o cofre esteja desbloqueado.

O superusuário deverá configurar MFA no primeiro acesso ao Admin. E-mails locais
são enviados ao console do backend: esses logs incluem o código solicitado e
devem ser tratados como sensíveis. Servidores devem usar SMTP via variáveis de
ambiente, nunca o backend de console.

Para parar sem apagar dados:

```powershell
./subir-local/local.ps1 down
```

Não acrescente `--volumes`/`-v` aos comandos de encerramento. A rede externa
`hospital-local-transit` é usada apenas localmente, por frontend e backend.
Proxy, WAF e PostgreSQL não participam dela. Não use os arquivos
`compose.local.yaml` nos servidores. O teste Django usa um banco temporário:
o script concede CREATEDB durante o teste e o revoga no `finally`; não rode testes
contra bancos de produção. Se o processo for encerrado à força, revogue CREATEDB
explicitamente antes de continuar. `config.test_settings` desativa apenas o
redirecionamento HTTPS porque o Client testa views diretamente por HTTP.

Teste de navegador adicional, com Node, Playwright e Chrome disponíveis:

```powershell
node subir-local/browser_test.cjs 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node dmz/frontend/tests/calendar_browser.cjs 'C:/Program Files/Google/Chrome/Application/chrome.exe'
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "${PWD}:/workspace:ro" -w /workspace -e HOSPITAL_HOST_ROOT="${PWD}" docker:27-cli sh -c "apk add --no-cache python3 >/dev/null && python3 subir-local/isolation_test.py"
```

O primeiro cria e remove usuários/dados sintéticos com prefixo único e valida
os quatro perfis, CSRF, MFA inicial, QR sem cache, calendários, anotações,
Meus Dados, novo e-mail na recuperação, arquivos estáticos e logout pela DMZ.
Ele aceita a CA de teste apenas no contexto do navegador. O segundo verifica
as redes, ausência de portas públicas do banco/backend local, bloqueio de
conexões indevidas e rejeição de clientes sem certificado. Ambos são
exclusivamente locais. Os testes Django existentes cobrem códigos errados,
expirados/usados, MFA de recuperação e autorização entre médicos.

## Implantação em duas máquinas

A automação separada está em [subir-servidor](../subir-servidor/README.md), com
um script e um exemplo de ambiente por máquina. Use esses scripts e preserve
os nomes de projeto `hospital-interna` e `hospital-dmz`. Os exemplos Compose
diretos abaixo explicam o mecanismo; acrescente `--project-name` correspondente
se os executar manualmente para não selecionar volumes de outro projeto.

As redes `vlan10`, `vlan20`, `vlan30` e `vlan40` são **bridges locais**.
Elas não criam interfaces 802.1Q, rotas entre máquinas ou regras no pfSense.
As faixas Docker foram movidas para `172.28.*` para evitar coincidência com
as VLANs físicas `192.168.*`; confirme ausência de conflito com VPN/redes reais.
Não é necessário macvlan/ipvlan para esta abordagem. A publicação do backend na
interface física e a rota/firewall entre VLANs fazem a comunicação entre hosts.

1. Configure as interfaces VLAN 10 e VLAN 20, endereços, rota e DNS nos
   servidores/rede. Não invente uma rede Docker compartilhada entre as máquinas.
2. Copie somente as variáveis necessárias para cada host. A DMZ precisa das
   variáveis públicas/TLS/upstream/rede; não precisa de SECRET_KEY, senhas de banco
   ou SMTP. A Rede Interna precisa das variáveis Django/banco/SMTP/TLS/rede.
   O exemplo conjunto destina-se ao teste local. Use arquivos externos ao Git
   com permissões restritas. Não copie o `.env` local para produção.
   O arquivo da Rede Interna também deve definir as senhas do Keycloak e de seu
   banco: esses serviços e Vault fazem parte da infraestrutura padrão.
3. Na DMZ: `DMZ_BIND_IP` deve ser o IP da interface VLAN 10; portas públicas 80 e
   443; `PUBLIC_HTTPS_SUFFIX` vazio; `PUBLIC_ORIGIN=https://seu-dominio`.
   `BACKEND_URL=https://nome-ou-IP-da-rede-interna:8444` e `BACKEND_TLS_NAME` deve
   corresponder ao SAN do certificado do backend. Não use `hospital-backend`
   local sem configurar seu DNS. O Nginx usa o DNS interno Docker, que encaminha
   consultas externas; verifique resolução nos containers.
4. Na Rede Interna: `BACKEND_BIND_IP` deve ser o IP da interface VLAN 20.
   Use `docker-compose.yml` + `compose.server.yaml`; publique **somente 8444**
   para o backend. PostgreSQL não tem `ports` e participa somente de `db_app`.
   `POSTGRES_HOST` é configurável e tem padrão `postgresql`; porta padrão 5432.
5. Forneça certificados reais e mantenha chaves privadas fora das imagens.
   Backend recebe apenas `backend.crt`, `backend.key`, `client-ca.crt`.
   Nginx Web recebe `backend-ca.crt`, `frontend.crt`, `frontend.key`.
   Proxy recebe `public.crt`, `public.key` (cadeia pública completa).
   A CA de clientes deve emitir apenas o certificado autorizado do frontend,
   separado da CA pública. Não distribua a chave privada da CA a nenhum serviço.
   O backend exige cliente certificado; o frontend verifica CA e SAN do servidor.
   Permita leitura da chave backend ao UID 10001, sem permissões públicas.
6. Construa/distribua as imagens correspondentes ao mesmo commit. Inicie banco,
   aplique migrations com `compose run --rm backend python manage.py migrate`,
   depois inicie backend e DMZ. Migrations não são executadas em cada boot no
   servidor. Em volumes existentes, o init script não roda automaticamente:
   execute `sh /docker-entrypoint-initdb.d/10-app.sh` explicitamente no serviço
   PostgreSQL para provisionar o banco/role, após conferir os valores desejados.
   Ele não apaga dados nem troca senhas de roles existentes.

Exemplo de invocação, na raiz de cada checkout, com arquivos de ambiente externos:

```sh
# Rede Interna (máquina 2)
docker compose --env-file /etc/hospital/backend.env -f rede-interna/docker-compose.yml -f rede-interna/compose.server.yaml up -d --build postgresql
docker compose --env-file /etc/hospital/backend.env -f rede-interna/docker-compose.yml -f rede-interna/compose.server.yaml build backend
docker compose --env-file /etc/hospital/backend.env -f rede-interna/docker-compose.yml -f rede-interna/compose.server.yaml run --rm backend python manage.py migrate --noinput
docker compose --env-file /etc/hospital/backend.env -f rede-interna/docker-compose.yml -f rede-interna/compose.server.yaml up -d --wait
# DMZ (máquina 1)
docker compose --env-file /etc/hospital/dmz.env -f dmz/docker-compose.yml up -d --build --wait
```

Volumes Compose pertencem ao nome do projeto. Ao utilizar um volume já existente,
mantenha o nome do projeto anterior ou faça um override explícito com `external`
e `name` apontando para o volume correto. Nunca monte PGDATA de PostgreSQL 17 na
imagem 15; migração de versões exige procedimento próprio. As senhas dos roles
existentes não mudam ao editar variáveis Docker: rotação requer ALTER ROLE e
atualização coordenada do segredo dos clientes, sem recriar o volume.

## Regras obrigatórias na rede e nos servidores

| Origem | Destino | Permitir |
|---|---|---|
| Internet | Interface DMZ / proxy | TCP 443; TCP 80 para redirect/ACME |
| Nginx Web DMZ | Interface VLAN 20 / backend | TCP 8444 HTTPS com mTLS |
| Backend | PostgreSQL na rede privada Docker | TCP 5432 |
| Backend | SMTP configurado | Apenas destino/porta do provedor |
| Containers/hosts | Resolvedores definidos | DNS conforme política |

Bloqueie Internet → Rede Interna, Internet/DMZ → PostgreSQL, proxy/WAF → backend,
VLAN 30/40 → PostgreSQL da aplicação e conexões novas iniciadas da Rede Interna
para a DMZ. Permita retorno de conexões estabelecidas. Administração dos hosts
fica na rede/VPN de gestão, fora desse fluxo.

No pfSense/roteador: regra da VLAN 10 com origem máquina DMZ, destino IP específico
da VLAN 20 e porta 8444, seguida de bloqueio dos demais destinos internos.
No host DMZ, restrinja também tráfego encaminhado do subnet
`FRONTEND_EGRESS_SUBNET` ao destino backend:8444 e bloqueie outros containers
para redes internas. Após SNAT, o firewall físico vê o IP do host e não distingue
Nginx Web de WAF/proxy: **o filtro de encaminhamento do host é necessário**.
No host interno, limite a porta publicada 8444 à origem DMZ autorizada.

Docker pode encaminhar portas publicadas antes de regras comuns do INPUT/UFW.
Com backend iptables, aplique a política em `DOCKER-USER` (levando em conta DNAT);
com nftables, use as cadeias de encaminhamento e prioridades apropriadas ao
backend do Docker. Não copie regras cegamente: nomes de interfaces, faixas,
origens, rotas, NAT e backend do firewall dependem dos dois servidores reais.
Essas regras **não foram aplicadas no Windows** nem em servidores nesta etapa.
A segmentação Docker e mTLS já estão configurados; o isolamento físico depende
da aplicação e validação dessas regras antes da publicação.

As imagens web usam Nginx 1.30.5, conforme as correções publicadas nos
[avisos oficiais de segurança](https://nginx.org/en/security_advisories.html).
Gunicorn 26.2.0 é fixado nas dependências, da série atualmente suportada segundo
a [política oficial](https://github.com/benoitc/gunicorn/security).
O WAF foi fixado pelo digest da imagem validada (Nginx 1.30.5).

## Componentes preservados e limites

Vault, banco do Keycloak e Keycloak são componentes obrigatórios e sobem junto
com backend e PostgreSQL na subida padrão, sem profiles opcionais. Removeram-se
senhas literais e limitaram-se portas de gestão a loopback por padrão. O arquivo
Vault HCL foi preservado. Vault ainda precisa TLS, endereço anunciado correto,
unseal, políticas e operação de produção; Keycloak ainda está em `start-dev`.
Eles não participam da autenticação Django nesta integração. As tags `latest`
originais de Vault/Keycloak foram preservadas, mas devem ser fixadas após uma
validação própria antes do uso nos servidores. Não houve alterações nos outros
componentes do diagrama nem implementação de Kubernetes/pentest.

Vault poderá fornecer segredos com Agent e arquivos temporários ou injeção de
ambiente no deploy, com políticas por serviço e renovação/rotação coordenada.
Não há integração automática com Vault nesta entrega. Não envie credenciais do
banco à DMZ. Docker environment é configuração externa, não um cofre: usuários
administradores do Docker podem inspecioná-lo.

O WAF permanece em modo de bloqueio. Logs de acesso/auditoria/erro do WAF foram
desativados para evitar captura de senhas, tokens e dados clínicos nos valores
das regras. Antes de integrar SIEM, defina um formato restrito e sanitizado;
não habilite captura integral de requests/responses. Não existe bypass para
login, MFA, Admin ou recuperação. Se houver falso positivo, crie uma exceção
específica após avaliar a regra e o parâmetro, mantendo a proteção restante.
Gunicorn não registra URLs de acesso; logs de exceções ainda exigem controle
de acesso e retenção. Monitoramento detalhado é uma etapa separada.

FullCalendar continua usando a versão existente no CDN jsDelivr. Os browsers
precisam alcançá-lo; isso não é uma conexão backend → Internet para calendários.
SMTP real, ACME, DNS externo, firewall físico e duas máquinas não podem ser
validados sem os servidores/domínio/provedor. Ative HSTS após confirmar HTTPS
real e renovação dos certificados; cookies seguros e DEBUG=False já estão ativos.


## Organização física e desenvolvimento

Não há ambiente Python local nem Compose da aplicação na raiz. Código Python,
templates, testes Django e migrations ficam em rede-interna/backend/. CSS,
JavaScript, imagens, configuração Nginx Web e testes de calendário ficam em
dmz/frontend/. Não há uma segunda cópia das fontes.

Compose >= 2.17 e BuildKit são necessários para o contexto adicional backend_source
do build frontend. O coletor acessa o código backend somente durante o build;
a imagem Nginx final recebe apenas os estáticos coletados. O backend em execução
não depende de arquivos fora de sua pasta. Templates não são movidos à DMZ:
continuam renderizados pelo Django com sessão, URLs e CSRF.

Use ./subir-local/local.ps1 dev para montar rede-interna/backend em /app com
reload, preservando o restante da infraestrutura. Assim makemigrations grava
os arquivos no repositório. Reconstrua o frontend depois de alterar seus estáticos.
A função hospital e os comandos de desenvolvimento estão no README da raiz.
subir-local/ mantém uma função real: preparação local de TLS/segredos, execução
dos dois projetos, testes de navegador e isolamento. Certificados/.env são ignorados.
