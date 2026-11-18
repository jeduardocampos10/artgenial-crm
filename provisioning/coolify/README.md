# Instalação SaaS isolada no Coolify — homologação

Esta topologia cria **uma instalação por recurso Compose do Coolify**. Ela é exclusiva para homologação e não substitui `provisioning/commercial/`, não altera produção e não deve apontar para `main`.

## Barreiras obrigatórias

- Recurso Coolify, namespace Compose, rede, volumes e variáveis exclusivos por instalação.
- Branch `develop` somente depois da integração por PR; nunca `main`.
- Nenhuma porta de host, volume externo, rede externa, Caddy ou MailHog.
- Somente seis serviços recebem domínio no proxy do Coolify:
  - `evo-frontend:80`
  - `evo-crm:3000` (inclui `/cable`)
  - `evo-auth:3001`
  - `evo-core:5555`
  - `evo-processor:8000`
  - `evo-flow:3334`
- PostgreSQL, Redis, RabbitMQ, ClickHouse, Bot Runtime e Evolution API permanecem privados.
- `redact_all_env_values_in_logs=true`, submodules habilitados e auto-deploy desabilitado durante a prova operacional.

## Identidade da instalação

Gere fora do Git:

- `INSTALLATION_KEY`: UUID canônico novo e imutável;
- `INSTALLATION_NAME`, `ADMIN_NAME`, `ADMIN_EMAIL`;
- `POSTGRES_DATABASE` e `FLOW_DATABASE` exclusivos;
- seis origens HTTPS exclusivas;
- segredos aleatórios novos, sem reutilizar qualquer valor de outra instalação.

Como algumas credenciais são incorporadas em URLs internas sem percent-encoding, `POSTGRES_USERNAME`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `RABBITMQ_DEFAULT_USER` e `RABBITMQ_DEFAULT_PASS` devem usar exclusivamente `[A-Za-z0-9_-]`. Gere valores longos com alfabeto URL-safe; não use `@`, `:`, `/`, `?`, `#`, `%`, espaços ou `$`.

O namespace de volumes é fornecido pelo UUID do recurso Compose do Coolify. Não defina `name:`, `container_name`, volumes `external` ou redes `external`.

## Variáveis públicas e domínios

Configure as origens completas:

- `FRONTEND_URL` e `APP_URL`: frontend;
- `BACKEND_URL`, `CORS_ORIGINS`, `VITE_API_URL` e `VITE_WS_URL`: CRM API;
- `AUTH_SERVICE_URL` e `VITE_AUTH_API_URL`: Auth API;
- `VITE_EVOAI_API_URL`: Core API;
- `API_URL` e `VITE_AGENT_PROCESSOR_URL`: Processor API;
- `VITE_EVOFLOW_API_URL`: Flow API;
- `FRONTEND_HOST`: hostname do frontend, sem esquema ou porta;
- `MEDIA_HOST_ALLOWLIST`: hostname da CRM API, sem esquema ou porta.

As seis variáveis `VITE_*` são build args e runtime settings. O frontend converte a origem HTTPS de `VITE_WS_URL` para WSS e acrescenta `/cable`.

## Segredos

Todos os valores abaixo são exclusivos da instalação e cadastrados somente no cofre de variáveis do recurso:

- `POSTGRES_PASSWORD`, `REDIS_PASSWORD`;
- `JWT_SECRET_KEY`, `SECRET_KEY_BASE`, `ENCRYPTION_KEY`;
- `DOORKEEPER_JWT_SECRET_KEY`, `BOT_RUNTIME_SECRET`;
- `EVOAI_CRM_API_TOKEN`, `AUTH_APIKEY_INTEGRATION_LOCAL`;
- `EVOLUTION_ADMIN_SECRET`, `EVOLUTION_WEBHOOK_SECRET`;
- `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`;
- `CLICKHOUSE_PASSWORD`;
- `SMTP_USERNAME`, `SMTP_PASSWORD`.

Também configure os valores técnicos não secretos exigidos pelo Compose, incluindo SMTP, nomes de banco/usuário e ClickHouse.

## Bootstrap idempotente

Antes dos serviços permanentes, três jobs idempotentes preparam o banco compartilhado: `crm-schema-init` carrega o schema mestre somente quando o banco está vazio e rejeita banco existente sem ledger; `auth-migration-stamp` registra as migrations Auth já contidas no schema; `flow-db-init` cria o banco Flow somente se ausente.

No primeiro deploy, defina temporariamente `ADMIN_BOOTSTRAP_PASSWORD`. Depois da preparação, o Auth executa migrations incrementais, aplica `bootstrap_auth.rb` sob advisory lock e só cria conta/administrador quando ausentes. O CRM executa migrations pelo entrypoint e aplica `artgenial.base` v1 pelo ledger oficial antes de iniciar o servidor.

Depois de comprovar login, conta e Base:

1. remova `ADMIN_BOOTSTRAP_PASSWORD` do Coolify;
2. redeploy manualmente o mesmo commit;
3. confirme que o bootstrap retorna ao estado existente sem criar outro usuário ou reaplicar a Base.

Conflito de conta, administrador ou `installation_key` deve interromper o startup.

### Recuperação controlada da senha do administrador

O bootstrap é deliberadamente idempotente: se o administrador já existe, ele valida identidade e papel, mas **não redefine sua senha**. Reintroduzir `ADMIN_BOOTSTRAP_PASSWORD` e redeployar, sem uma operação explícita, não modifica o usuário existente.

Este procedimento é exclusivo para homologação e recuperação supervisionada. Ele não autoriza alterações em produção.

1. Mantenha a mesma release imutável e cadastre temporariamente uma **nova** `ADMIN_BOOTSTRAP_PASSWORD` no cofre do recurso Coolify, disponível em runtime. Nunca reutilize uma senha exibida em log, terminal, captura ou conversa.
2. Salve a variável e faça **redeploy**, não apenas restart. Se o Coolify mostrar `Changes pending`, o container atual ainda não recebeu a configuração.
3. Feche terminais anteriores e abra uma sessão no novo container `evo-auth`, identificado pelo timestamp mais recente. Confirme a presença sem imprimir o valor:

   ```sh
   if [ -n "${ADMIN_PASSWORD:-}" ]; then
     echo "OK: ADMIN_PASSWORD disponível"
   else
     echo "ERRO: ADMIN_PASSWORD ausente"
   fi
   ```

4. Somente após a confirmação, execute no `evo-auth` o runner fail-closed:

   ```sh
   cd /rails && bundle exec rails runner 'email=ENV.fetch("ADMIN_EMAIL").downcase; user=User.from_email(email); raise "Administrador não encontrado" unless user; raise "Usuário não possui super_admin" unless user.has_role?("super_admin"); password=ENV.fetch("ADMIN_PASSWORD"); raise "A senha deve ter pelo menos 16 caracteres" if password.length < 16; user.update!(password: password, password_confirmation: password); puts "OK: senha redefinida para #{email}"'
   ```

5. Valide o login pelo domínio da instalação. Depois, remova imediatamente `ADMIN_BOOTSTRAP_PASSWORD`, redeploye novamente a mesma release e confirme que o sistema permanece saudável.

Se o runner retornar `key not found: "ADMIN_PASSWORD"`, não o adapte para inserir a senha na linha de comando. Isso significa que o segredo não chegou ao container — normalmente por mudanças pendentes, ausência em runtime ou terminal ainda conectado ao container anterior. Como `ENV.fetch` ocorre antes de `user.update!`, essa falha específica não altera a senha.

A redefinição da senha não deve ser tratada como prova de revogação de tokens ou sessões já emitidos. Essa revogação exige validação separada do mecanismo de autenticação antes de qualquer ação.

**Aceite obrigatório:** runner confirma a atualização, login funciona com a senha nova, a senha nunca aparece nas evidências, o segredo temporário é removido e o redeploy idempotente permanece saudável.

## Primeiro deploy

1. Execute os testes locais e valide o Compose renderizado sem imprimir valores.
2. Crie um novo recurso Compose no projeto de homologação e aponte para `develop` e `provisioning/coolify/compose.yaml`.
3. Desabilite auto-deploy inicialmente e fixe o commit aprovado.
4. Cadastre variáveis exclusivas e os seis bindings de domínio por serviço.
5. Faça o deploy manual e aguarde todos os health checks.
6. Valide frontend, APIs, conta autenticada, assets Vite e WebSocket.
7. Remova a senha temporária e repita o deploy idempotente.

## Prova de isolamento

Registre sem segredos:

- UUID do recurso e `INSTALLATION_KEY`;
- nomes finais da rede e dos nove volumes;
- identificadores dos containers;
- banco, Flow DB, prefixo Redis e cliente Evolution;
- tentativa negativa de resolução/acesso entre as duas instalações;
- hashes de configuração sem valores de segredo.

Nenhum volume ou rede deve ser compartilhado com `artgenial-crm-dev` ou com produção.

## Backup e restore

A prova só é válida com execução real:

1. pausar entradas e workers;
2. criar backup consistente de PostgreSQL (incluindo Flow/schema Evolution), Redis, RabbitMQ, ClickHouse, Auth storage, CRM storage e sessões Evolution;
3. criptografar e enviar a destino externo;
4. registrar SHA-256 e inventário;
5. restaurar em **terceiro recurso** `recovery_test`, com rede, volumes, domínios e segredos próprios;
6. manter webhooks/WhatsApp/SMTP de saída desabilitados no alvo;
7. validar login, conta, Base, arquivos, filas, bancos e health checks;
8. emitir recibo compatível com a política de recuperação específica do Coolify.

`crm_cache` e `processor_logs` são reconstruíveis. Cópia de volume ativo não comprova consistência.

## Upgrade e rollback

- Salve commit e inventário de imagens da release N.
- Faça backup e restore de ensaio antes de N → N+1.
- Valide migrations e todos os checks na N+1.
- Rollback de imagem só é permitido se o schema for compatível.
- Caso contrário, restaure o backup pré-upgrade em recurso isolado e então reative a release N.

Nenhuma dessas provas libera produção ou o piloto WhatsApp automaticamente.
# Coolify homologation topology

This topology is pull-only: Coolify must never build application source. The
application images are published by CI only from `develop` or
`artgenial/develop`; pull requests never receive registry credentials.

Before changing the homologation resource, copy the successful workflow image
references into Coolify. Prefer the digest shown by GHCR; a full 40-character
commit tag is also accepted. Validate an exported, non-secret env file locally:

```sh
python3 provisioning/coolify/validate_images.py /path/to/coolify-images.env
python3 -m unittest provisioning.tests.test_coolify
```

Required image variables are `AUTH_IMAGE`, `CRM_IMAGE`, `FRONTEND_IMAGE`,
`CORE_IMAGE`, `PROCESSOR_IMAGE`, `BOT_RUNTIME_IMAGE`, `EVOLUTION_API_IMAGE`, and
`FLOW_IMAGE`. `CRM_IMAGE` is deliberately shared by schema-init, web, and
Sidekiq; `AUTH_IMAGE` is shared by migration-stamp, web, and Sidekiq.

Do not point this file at the production `artgenial-crm` resource or
`crm.artgenial.com.br`. Promotion is a separate, reviewed operation after all
component workflows and the root CI are green.
