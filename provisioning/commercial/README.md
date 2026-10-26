# Instalação comercial portátil (Fase 2.5.5)

Esta implantação usa Docker Compose em infraestrutura nova. Não usa o Compose local, `setup.sh`, Coolify ou recursos preexistentes. O catálogo oficial contém 14 serviços; MailHog é apenas desenvolvimento e fica fora da implantação production. Os outros 13 serviços ficam na rede privada `private`; somente o ingress Caddy publica 80/443. PostgreSQL, Redis, RabbitMQ e ClickHouse usam volumes nomeados do projeto, sem host ports. Caddy usa volumes para certificados. O nome do projeto deriva do slug validado, isolando redes e volumes.

## Pré-requisitos

- Host Linux com Git, Python 3.10+, Docker Engine e Docker Compose v2 com `up --wait`.
- DNS A/AAAA dos seis hosts públicos apontando ao host; portas 80 e 443 acessíveis para TLS automático do Caddy.
- Provedor SMTP externo com autenticação e TLS. Esta implantação exige SMTP real; MailHog não participa.
- Recursos suficientes para compilar e executar Ruby, Node, Python, Go, PostgreSQL, Redis, RabbitMQ, ClickHouse e Caddy.
- Repositório e submodules acessíveis pelo GitHub. O Core também é compilado do submodule fixado pelo checkout.

Clone com submodules:

```sh
git clone --recurse-submodules https://github.com/jeduardocampos10/artgenial-crm.git
cd artgenial-crm
```

Crie o JSON de instalação fora do repositório a partir de `provisioning/config/installation.example.json`. Defina `environment=production`, nome, slug, UUID novo, nome/e-mail do administrador e seis origens HTTPS distintas. Mantenha `required_services` e as referências `runtime:*` do contrato. O exemplo `.example.test` nunca passa na validação production. `VITE_WS_URL` será a origem HTTPS de `crm_api`; o frontend forma `wss://.../cable` por conta própria.

Crie um arquivo runtime fora do repositório, com permissão `0600`, no formato `NOME=valor` (uma linha por nome, sem aspas). Exemplo apenas dos **nomes** requeridos:

```text
POSTGRES_PASSWORD=
REDIS_PASSWORD=
JWT_SECRET_KEY=
SECRET_KEY_BASE=
ENCRYPTION_KEY=
DOORKEEPER_JWT_SECRET_KEY=
BOT_RUNTIME_SECRET=
EVOAI_CRM_API_TOKEN=
AUTH_APIKEY_INTEGRATION_LOCAL=
RABBITMQ_DEFAULT_USER=
RABBITMQ_DEFAULT_PASS=
CLICKHOUSE_PASSWORD=
SMTP_ADDRESS=
SMTP_PORT=
SMTP_USERNAME=
SMTP_PASSWORD=
MAILER_SENDER_EMAIL=
```

Preencha todos os valores com credenciais exclusivas. `AUTH_APIKEY_INTEGRATION_LOCAL` é obrigatório em production. Para SMTP em 465, acrescente `SMTP_SSL=true` e `SMTP_ENABLE_STARTTLS_AUTO=false`; para STARTTLS use o modo padrão. Os segredos usados em URLs internas (`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, usuário/senha RabbitMQ) devem conter somente letras, números, `_` e `-`; gere valores longos com alfabeto URL seguro. O parser rejeita `$`, que o Compose interpolaria de forma ambígua. A senha do administrador **não** entra neste arquivo ou no JSON: o instalador a solicita sem eco no terminal. O instalador cria arquivos `env_file` temporários, com permissão 0600 e um subconjunto de credenciais por serviço, em diretório 0700 fora do repositório; remove o diretório ao terminar. Frontend e Caddy não recebem arquivo de credenciais. O estado do Executor também fica fora do repositório, sem valores de segredos. Limite acesso ao host e a operadores Docker autorizados.

Execute na raiz:

```sh
chmod 600 /caminho/seguro/artgenial-runtime.env
python provisioning/commercial/install.py \
  --config /caminho/seguro/installation.json \
  --runtime-env /caminho/seguro/artgenial-runtime.env \
  --state /caminho/seguro/executor-state.json
```

O instalador valida contrato, catálogo de serviços, catálogo de variáveis e política comercial; gera o manifesto em memória e vincula o estado pelo fingerprint. Ele compila as imagens, inicia infraestrutura privada e carrega o schema mestre do CRM **somente em banco vazio**. Em seguida registra as versões Auth já contidas no schema, cria o banco Flow se ausente, inicia os serviços e executa migrations idempotentes de CRM, Auth, Processor e Flow. O bootstrap Auth cria explicitamente `RuntimeConfig.account` se ausente, exige identidade compatível se já existir, cria somente o administrador inicial e se recusa a modificar um banco com outro usuário. A Base usa o Loader e Applier oficiais `artgenial.base` v1 e o `installation_key`, preservando checksum e ledger. Não usa `SetupBootstrapService` nem seeds de dados de exemplo.

O instalador verifica login do administrador, `GET /api/v1/account`, healths públicos, bindings VITE nos assets e upgrade HTTP → WebSocket de `/cable` segundo `provisioning/checks/required.json`. Um check reprovado impede `ENTREGA`. Atestações e fases são gravadas atomicamente no estado do Executor; uma nova execução retoma a fase pendente/falhada com o mesmo manifesto. Alterar configuração que mude o fingerprint exige revisão explícita; não edite o estado manualmente. O instalador nunca executa `down`, remove volume ou recria banco existente.

## Limites operacionais

A autenticação SMTP prova conexão TLS e login, mas não comprova entrega de uma mensagem a uma caixa externa. Faça essa prova operacional antes de liberar clientes. Um Docker daemon indisponível, DNS não propagado, certificado TLS pendente, submodule inacessível, imagem não publicada ou falta de recursos bloqueia o processo sem marcar entrega. Não substitua o arquivo runtime por `.env` versionado. Não use os Compose de desenvolvimento para production.
