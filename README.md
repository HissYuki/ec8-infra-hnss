# Hospital — aplicação e infraestrutura

A aplicação roda em containers. Desenvolvimento, testes, migrations e comandos
Django usam o serviço `backend`; não é necessário um ambiente virtual local.

## Estrutura

```text
dmz/
  docker-compose.yml       # proxy, WAF e nginx-web
  compose.local.yaml       # comunicação entre projetos apenas no teste local
  frontend/
    Dockerfile
    .dockerignore
    default.conf.template
    static/                # única fonte de CSS, JavaScript e imagens
    tests/                 # teste de navegador dos calendários
  proxy/                   # configuração e Dockerfile do proxy
rede-interna/
  docker-compose.yml       # backend, dois PostgreSQL, Vault e Keycloak
  compose.local.yaml       # trânsito local frontend/backend
  compose.dev.yaml         # montagem do backend e reload para desenvolvimento
  compose.server.yaml      # publicação restrita do backend na interface interna
  backend/
    Dockerfile
    .dockerignore
    manage.py
    requirements.txt
    accounts/, config/, consultas/, coordenador/, medicos/, pacientes/
    templates/             # templates dinâmicos renderizados pelo Django
  postgres/                # provisionamento inicial da aplicação
  vault/                   # configuração existente preservada
integration/               # execução e validação conjunta LOCAL; certificados
.env.example               # exemplo global, sem credenciais reais
```

Os testes Python e as migrations permanecem nos respectivos apps do backend.
Os templates dependem de sessões, CSRF, contexto e URLs Django e ficam no backend.
A DMZ serve os estáticos e encaminha o HTML dinâmico; a aplicação mantém sua
renderização no servidor. Não existem cópias dos apps ou estáticos na raiz.

O fluxo permanece: **HTTPS → Nginx Proxy → ModSecurity → Nginx Web → backend
Django → PostgreSQL**. O backend usa Python 3.13, Django 5.2.17 e Gunicorn com
TLS mútuo. O PostgreSQL da aplicação tem rede privada e não publica portas.
Vault, Keycloak e o PostgreSQL exclusivo do Keycloak são serviços obrigatórios.
A organização de arquivos não muda as redes, os volumes ou as regras de acesso.

## Iniciar, desenvolver e parar

Requisitos: Docker Desktop com containers Linux e Docker Compose >= 2.17
(com suporte a `additional_contexts`). Execute na raiz:

```powershell
./integration/local.ps1 up
./integration/local.ps1 status
```

Site: https://localhost:8443; Keycloak: http://localhost:8180/admin/;
Vault: http://localhost:8200/ui/. A CA HTTPS é de teste; detalhes e limitações
estão no [guia de integração](integration/README.md).

O script prepara `integration/.env` a partir do exemplo global somente quando
ele não existe, com senhas aleatórias, e preserva certificados e volumes
existentes. Não gere um novo arquivo de segredos para um banco já inicializado.

Para editar Python/templates e gerar migrations no diretório do repositório:

```powershell
./integration/local.ps1 dev
```

Esse modo monta `rede-interna/backend/` em `/app` e ativa reload do Gunicorn.
Alterações de dependências exigem rebuild. Para publicar alterações de CSS/JS
na imagem frontend, execute novamente `./integration/local.ps1 dev`.
`up` usa imagens sem a montagem de desenvolvimento.

Para parar preservando os bancos e o Vault:

```powershell
./integration/local.ps1 down
```

Não remova volumes. O ambiente antigo de dois serviços na raiz foi aposentado;
seu volume PostgreSQL antigo não foi apagado.

## Comandos Django no container

Na raiz, defina uma função PowerShell para não repetir as opções:

```powershell
function hospital { docker compose -p hospital-interna --env-file integration/.env -f rede-interna/docker-compose.yml -f rede-interna/compose.local.yaml @args }
hospital exec backend python manage.py check
hospital exec backend python manage.py makemigrations --check --dry-run
hospital exec backend python manage.py showmigrations
hospital exec backend python manage.py migrate
hospital exec backend python manage.py createsuperuser
hospital logs -f backend
```

Para gravar novas migrations no repositório, inicie o modo `dev` antes de:

```powershell
hospital exec backend python manage.py makemigrations
```

Execute a suíte pelo script; ele cria um banco de testes separado e concede/
revoga temporariamente CREATEDB à role da aplicação:

```powershell
./integration/local.ps1 test
```

Para rodar diretamente o runner, a mesma permissão de banco de testes precisa
estar preparada; não execute testes em produção:

```powershell
hospital exec backend python manage.py test --noinput --settings=config.test_settings
```

O script executa também `check` e `makemigrations --check --dry-run`.
As migrations existentes são preservadas; não há fallback para SQLite.
A conexão usa POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER e
POSTGRES_PASSWORD, fornecidos pelo ambiente.

## Funcionalidades preservadas

- Login de paciente, médico, coordenador e administrador, com MFA obrigatório
  inclusive no Admin; TOTP e códigos de recuperação de uso único por django-otp.
- Logout POST com CSRF, redirecionado ao login correspondente ao perfil.
- Recuperação pública somente de pacientes, por código enviado ao e-mail atual:
  resposta genérica, validade de dez minutos, cinco tentativas e hash Django.
  Redefinir senha preserva MFA. No teste local o e-mail aparece nos logs do backend;
  SMTP real deve usar as variáveis EMAIL_* do arquivo de ambiente.
- Consultas, exames, disponibilidades, conflitos e calendários. Anotações de
  consulta são exclusivas do médico responsável e não são expostas ao paciente.
- Nove exames iniciais por data migration idempotente, editáveis pelo Admin.
- Meus Dados salva de forma transacional e apresenta mensagem após sucesso.

`templates/base.html` usa `extra_css`, `extra_js` e referências `{% static %}`.
Os arquivos compartilhados estão em `dmz/frontend/static/css/base.css` e
`dmz/frontend/static/js/base.js`; módulos de contas, agendas, calendários e
disponibilidades mantêm a divisão existente.

Os estáticos do Admin vêm do Django instalado durante o estágio de
`collectstatic` do build frontend. Esse estágio lê o contexto adicional
`rede-interna/backend/`; a imagem final contém somente Nginx e estáticos,
sem código Python ou segredos. Construa frontend e backend do mesmo commit.

## Validação adicional e implantação

Com Node, Playwright e Chrome disponíveis apenas como ferramentas de teste:

```powershell
node integration/browser_test.cjs 'C:/Program Files/Google/Chrome/Application/chrome.exe'
node dmz/frontend/tests/calendar_browser.cjs 'C:/Program Files/Google/Chrome/Application/chrome.exe'
```

A validação de isolamento usa um script Python de orquestração Docker, que também
pode ser executado em um container auxiliar, sem instalar Python/.venv local:

```powershell
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "${PWD}:/workspace:ro" -w /workspace -e HOSPITAL_HOST_ROOT="${PWD}" docker:27-cli sh -c "apk add --no-cache python3 >/dev/null && python3 integration/isolation_test.py"
```

Não use esse container auxiliar nos servidores; ele recebe acesso ao Docker
somente para inspecionar a arquitetura local. Os testes de navegador criam e
removem dados sintéticos; o teste de calendário usa eventos simulados.

As bridges Docker simulam a segmentação local, sem criar VLANs físicas.
As configurações para duas máquinas, portas, mTLS, firewall, segredos e limites
operacionais estão em [integration/README.md](integration/README.md).
Vault mantém sua configuração e armazenamento; um volume novo exige inicialização
e unseal explícitos. Keycloak ainda usa start-dev e não substitui o login Django.

## Revisar antes do commit

```sh
git status
git diff --stat
git diff
```

Arquivos novos aparecem em `git status` e precisam ser revisados também;
`git diff` sem stage mostra apenas arquivos já rastreados. Não inclua arquivos
.env, certificados privados, caches ou bancos no commit.
