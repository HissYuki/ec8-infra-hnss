# Aplicação hospitalar — Django e PostgreSQL

O projeto `config` reúne as configurações e URLs. `accounts` cuida da autenticação
e do usuário personalizado; `pacientes`, `medicos` e `coordenador` organizam as
áreas de cada perfil. `consultas` contém os modelos de consultas, disponibilidades,
exames e agendamentos. Os templates e arquivos estáticos ficam em `templates/`
e `static/`. A lógica funcional e as migrations existentes foram preservadas.

## Ambiente local com Docker Compose

Pré-requisito: Docker com suporte a containers Linux e Docker Compose v2.
Execute os comandos na raiz deste repositório (branch `site`).

1. Copie `.env.example` para `.env`:

   ```powershell
   Copy-Item .env.example .env
   ```

   No Linux/macOS: `cp .env.example .env`.

2. Edite `.env`, substituindo `DJANGO_SECRET_KEY` e `POSTGRES_PASSWORD` por valores
   aleatórios próprios. `.env` já está fora do Git e do contexto de build.
   Para gerar um valor, pode usar `python -c "import secrets; print(secrets.token_hex(32))"`.

3. Inicie o ambiente:

   ```sh
   docker compose up --build
   ```

4. Acesse <http://localhost:8000>. Em outro terminal, crie um administrador:

   ```sh
   docker compose exec web python manage.py createsuperuser
   ```

O serviço `db` executa somente PostgreSQL 17. O serviço `web` utiliza Python 3.13
e Django 5.2.17. O Compose aguarda o healthcheck do banco e executa
`migrate --noinput` antes de iniciar o servidor de desenvolvimento com autoreload.
Isso cria o esquema usando as migrations existentes. O Django utiliza somente
PostgreSQL, sem fallback para SQLite. O antigo `db.sqlite3` foi removido do
projeto e continua ignorado no Git e no build. Seus dados não foram importados
automaticamente. O volume PostgreSQL existente é preservado.

Os diretórios da aplicação são montados no container: alterações em Python,
templates e arquivos estáticos não exigem rebuild. Alterações nas dependências
ou no Dockerfile exigem `docker compose up --build`. Após alterar `.env`, execute
`docker compose up -d` para recriar os serviços com a configuração atualizada.

## Comandos e validação

```sh
docker compose exec web python manage.py check
docker compose exec web python manage.py migrate
docker compose exec web python manage.py showmigrations
docker compose exec web python manage.py makemigrations --check --dry-run
docker compose exec web python manage.py test
docker compose exec web python manage.py makemigrations
docker compose logs web db
```

`makemigrations --check --dry-run` verifica se models e migrations estão alinhados
sem gerar arquivos. Use `makemigrations` apenas depois de mudanças intencionais
nos models; os novos arquivos serão gravados no repositório através das montagens.
Os arquivos de testes originais eram esqueletos. `consultas/test_postgresql.py`
adiciona testes de integração de conexão real, cadastro, login, perfis, agendas,
administração, agendamento/cancelamento e conflitos. O runner cria e remove
`test_<POSTGRES_DB>` separado do banco local; o usuário precisa de permissão
para criar bancos (o usuário inicial do serviço `db` local possui essa permissão).

Foi necessário um ajuste de compatibilidade em `pacientes/views.py`: o bloqueio
do agendamento de exames usa `select_for_update(of=("self",))`, preservando o
bloqueio do horário e as validações de médico e coordenador opcionais, sem tentar
bloquear relações nulas no PostgreSQL. Veja a
[documentação do Django](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update).

Para confirmar o banco efetivamente utilizado:

```sh
docker compose exec web python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print(connection.vendor); c = connection.cursor(); c.execute('SELECT current_database(), version()'); print(c.fetchone()); c.close()"
```

O resultado deve mostrar `postgresql`, o nome configurado e a versão do servidor.

## Persistência e conexão

O volume nomeado `postgres_data` guarda os dados do PostgreSQL.
`docker compose stop` e `docker compose down` preservam o volume.
**`docker compose down -v` apaga o banco local**; não o use se precisar dos dados.
As variáveis de usuário, senha e nome do banco inicializam apenas um volume novo.
Em um volume existente, mudanças dessas variáveis não alteram automaticamente as
credenciais ou o banco: faça a alteração administrativa correspondente no PostgreSQL.

O PostgreSQL não publica portas no host. A aplicação se conecta pela rede privada
do Compose e o site é publicado somente em `127.0.0.1:8000`.

| Variável | Finalidade |
| --- | --- |
| `POSTGRES_DB` | Nome do banco |
| `POSTGRES_USER` | Usuário do banco |
| `POSTGRES_PASSWORD` | Senha do banco |
| `POSTGRES_HOST` | Endereço DNS ou IP do PostgreSQL |
| `POSTGRES_PORT` | Porta de conexão ao PostgreSQL |
| `DJANGO_SECRET_KEY` | Chave secreta do Django |
| `DJANGO_DEBUG` | `True` no desenvolvimento; padrão do Django aqui é `False` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos, separados por vírgulas |

O Django exige todas as variáveis do banco e a chave secreta, sem credenciais
embutidas ou fallback para SQLite. O Compose lê `.env` e fornece as variáveis aos
containers; o Django não carrega esse arquivo por conta própria. Para executar
fora do Compose, forneça as variáveis no ambiente do processo.

A imagem Django não contém PostgreSQL nem exige o nome `db`. `POSTGRES_HOST=db`
serve para o Compose local; um IP como `10.x.x.x` ou DNS como `postgresql-service`
também pode ser usado sem editar o código, desde que haja conectividade e permissão
no servidor PostgreSQL. `POSTGRES_PORT` deve corresponder à porta desse servidor;
o serviço `db` deste Compose usa a porta padrão 5432.

Este Compose descreve apenas o ambiente local com os dois serviços. Fora dele,
a mesma imagem web pode receber as variáveis por outro mecanismo e executar
comandos Django normalmente. A dependência de healthcheck e a aplicação automática
das migrations estão no Compose local, não no Dockerfile. O comando padrão da
imagem usa `runserver`, adequado ao desenvolvimento; um ambiente de produção
exigirá configuração própria de servidor e execução controlada das migrations.

As pastas `dmz/` e `rede-interna/` não fazem parte deste ambiente, não são enviadas
no build nem montadas no container. A integração com essas infraestruturas e com
outros componentes está fora desta etapa.

## Organização dos arquivos estáticos

`templates/base.html` carrega apenas `css/base.css` e `js/base.js`, com os blocos
`extra_css` e `extra_js` para as dependências de cada página. Use `{% load static %}`
e `{% static %}` ao adicionar referências a arquivos locais.

| Arquivo | Responsabilidade |
| --- | --- |
| `css/base.css` | Layout, navegação, campos, tabelas, cards e mensagens compartilhados |
| `css/accounts.css` | Login, cadastro e campos de senha |
| `css/inicio.css` | Página inicial pública |
| `css/pacientes.css` | Seletores e opções da área do paciente |
| `css/calendarios.css` | Ajustes compartilhados dos calendários |
| `css/disponibilidade.css` | Filtros, grade semanal e listagem compartilhados |
| `css/coordenador/agenda.css` | Aparência específica da agenda do coordenador |
| `css/coordenador/disponibilidade.css` | Ajustes específicos da disponibilidade de exames |
| `js/base.js` | Confirmações de ações e submissão de filtros |
| `js/accounts.js` | Mostrar/ocultar senha no cadastro |
| `js/calendarios.js` | Opções comuns do FullCalendar |
| `js/agendas.js` | Agendas do médico e do coordenador |
| `js/agendamentos.js` | Calendários, agendamento e abas de consultas e exames do paciente |
| `js/disponibilidade.js` | Alternância diária/semanal e filtro de data |

URLs continuam sendo resolvidas com `{% url %}` nos templates e entregues aos
scripts por atributos `data-*`. Os tokens CSRF permanecem nos formulários.
As confirmações usam `data-confirm-click` ou `data-confirm-submit`, mantendo
o evento original. As diferenças entre consultas e exames são configuradas
no HTML, sem duplicar os scripts.

`templates/includes/fullcalendar_js.html` centraliza a dependência CDN já usada
(FullCalendar 6.1.19) e carrega as opções compartilhadas antes do script da página.
Na versão 6, o próprio JavaScript fornece o CSS da biblioteca; não é necessário
um `<link>` para `index.global.min.css`, conforme a
[documentação do FullCalendar](https://legacy.fullcalendar.io/v6/upgrading-from-v5#script-tag-usage).

## Autenticação, MFA e recuperação de senha

Todos os perfis, incluindo usuários staff e superusuários do Django Admin,
precisam concluir MFA antes de acessar qualquer view protegida. A autenticação
continua usando senhas e hashing nativos do Django. As regras ficam em `accounts/`:
forms por perfil, middleware obrigatório, views de MFA e recuperação e AdminSite.

No primeiro login, escaneie o QR Code com Google Authenticator, Microsoft
Authenticator, Authy ou outro aplicativo TOTP e confirme um código de seis
dígitos. O dispositivo só fica ativo depois dessa confirmação. Nos próximos
logins, informe a senha e o código do autenticador. O QR é gerado localmente,
exige sessão autenticada e não é disponibilizado depois da ativação.

Após configurar o MFA, guarde os dez códigos de recuperação apresentados uma
única vez em local seguro. Se perder o autenticador, faça login com a senha,
clique em **Perdi acesso ao autenticador** e informe um desses códigos. Cada
código pode ser consumido apenas uma vez. Antes de acessar o sistema, será
necessário configurar e confirmar um novo autenticador; o anterior e os códigos
antigos serão substituídos. Sem autenticador e sem códigos, procure o responsável
pelo sistema para tratar a recuperação após verificar sua identidade.

O MFA utiliza `django-otp[segno]` 1.7.3: TOTP, proteção contra repetição,
limitação de tentativas e tokens estáticos de uso único são fornecidos pela
biblioteca. A versão suporta Django 5.2 conforme seu
[histórico oficial](https://django-otp-official.readthedocs.io/en/latest/changes.html).
As migrations dos plugins `otp_totp` e `otp_static` são aplicadas pelo comando
normal `migrate`; nenhuma migration anterior foi removida. Contas existentes
configuram o MFA no próximo login. Sessões antigas sem MFA não liberam acesso.

**Esqueci minha senha** existe apenas no login do paciente. O fluxo utiliza
um código numérico de seis dígitos enviado por e-mail e `SetPasswordForm` do
Django para a nova senha. Somente pacientes ativos, com senha utilizável e sem
privilégios administrativos recebem o e-mail. Contas de outros perfis e e-mails
inexistentes recebem a mesma página de confirmação genérica. Redefinir a senha
não remove o MFA e não autentica automaticamente o usuário.

No desenvolvimento, o e-mail e o código de recuperação aparecem no console do
container; o backend de console não envia mensagens reais:

```sh
docker compose logs -f web
```

Abra **Esqueci minha senha**, informe o e-mail de um paciente e digite o código
mostrado no log. Para SMTP, configure no `.env` `EMAIL_BACKEND` como
`django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`,
`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, `EMAIL_USE_TLS`
e `EMAIL_USE_SSL`. Use TLS ou SSL conforme o servidor, sem ativar ambos.
Credenciais devem permanecer fora do Git. Depois execute `docker compose up -d`.

`PASSWORD_RESET_TIMEOUT` controla a validade do código e da etapa de nova senha
(padrão: 600 segundos). São permitidas cinco tentativas por código e um envio por
minuto por paciente, com contadores persistidos no PostgreSQL. O código usa
`secrets`, é armazenado somente como hash pelo Django e é invalidado ao ser
confirmado; a autorização para definir a senha permanece restrita à sessão e
à mesma expiração. Nova solicitação após o intervalo substitui o código anterior.
Alterações de senha, e-mail ou perfil invalidam a recuperação pendente. O envio
sempre utiliza o e-mail atual de `accounts.User`; endereços compartilhados por
mais de um paciente elegível exigem regularização do cadastro antes de recuperar.
`MFA_LOGIN_TIMEOUT` limita a etapa entre senha e confirmação MFA (padrão: 600
segundos). `OTP_TOTP_ISSUER` define o nome do hospital exibido no autenticador.
Esses valores estão documentados em `.env.example`.

Logout utiliza POST com CSRF e URLs nomeadas: paciente retorna ao login do
paciente, médico/coordenador ao login dos profissionais e staff/superusuário a
`admin:login`, inclusive ao sair pela interface nativa do Django Admin.

Para validar autenticação e os fluxos hospitalares no container:

```sh
docker compose exec web python manage.py test accounts consultas --noinput
```

Os testes usam banco temporário separado e e-mails em memória; não alteram as
contas nem configuram MFA para usuários do banco local.

## Agenda médica, observações e exames iniciais

O médico vê seus horários de consulta livres, consultas agendadas e reservas de
exames em cores distintas. Horários ocupados não são duplicados como disponíveis.
Clicar numa consulta abre seus detalhes e permite editar `Consulta.observacoes`,
campo que já existia. Somente o médico responsável tem acesso a essa página.
Ela também mostra os atendimentos anteriores do mesmo paciente com esse médico;
as observações não são incluídas nos templates nem no JSON destinados ao paciente.

Os calendários compartilham clique no dia e no número do dia para abrir a visão
diária. Os botões Mês, Dia, próximo, anterior e Hoje continuam disponíveis, assim
como Semana para médico/coordenador. Altura automática evita uma segunda barra
de rolagem interna; a navegação principal e a coluna de horários são mantidas.

A data migration `consultas.0006_exames_padrao` cadastra os nove exames iniciais
com `get_or_create` pelo nome único. Ela não sobrescreve exames existentes nem
edições administrativas, não é um seed executado a cada inicialização e seu
rollback não apaga cadastros. `accounts.0004_patient_password_reset_code` cria
a estrutura de recuperação numérica sem modificar o model de usuário existente.

“Meus Dados” salva usuário e paciente na mesma transação e mostra **Informações
atualizadas com sucesso.** somente após salvar. Erros são exibidos junto aos campos.

`tests/calendar_browser.cjs` valida a navegação real dos três calendários com
eventos simulados, sem acessar dados clínicos. Para executá-lo, disponibilize
Node.js e o módulo Playwright no ambiente de testes (ou via `NODE_PATH`) e informe
o caminho de um navegador Chromium/Chrome/Edge instalado:

```sh
node tests/calendar_browser.cjs "caminho/do/navegador"
```

Esse teste usa o site local em `localhost:8000` e precisa acessar o CDN do
FullCalendar já utilizado pelos templates. Playwright não é dependência da imagem Django.
