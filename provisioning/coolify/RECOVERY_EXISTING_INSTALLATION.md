# Recuperação de uma instalação existente no Coolify

Este roteiro serve para recuperar uma instalação cujo recurso Coolify voltou a apontar para o `docker-compose.yml` de desenvolvimento e perdeu serviços ou variáveis definidos no Compose homologado. Ele **não autoriza deploy em produção** e não substitui backup, revisão e homologação.

## Sintoma de referência

- O recurso público continua parcialmente funcional, mas a Evolution API desaparece.
- A busca de variáveis mostra apenas `EVOLUTION_BASE_URL`.
- O recurso aponta para `/docker-compose.yml`.
- O status pode aparecer como `Running (no healthcheck)`.

`EVOLUTION_BASE_URL` liga o Core ao CRM; ela não substitui `EVOLUTION_API_URL`.

## 1. Congelar e identificar

1. Desabilite auto-deploy e não use `Reload Compose`.
2. Registre, sem valores secretos:
   - recurso, UUID, domínio, repositório, branch, commit e caminho do Compose;
   - namespace Compose atual;
   - containers, redes e volumes existentes;
   - release e referências imutáveis das oito imagens;
   - último deployment saudável e deployment que introduziu o incidente.
3. Não altere `INSTALLATION_KEY`, nomes de volumes ou namespace.

## 2. Proteger os dados

Antes da troca de topologia:

1. registre inventário e faça backup consistente de PostgreSQL, Redis, RabbitMQ, ClickHouse, Auth storage, CRM storage e sessões Evolution existentes;
2. valide integridade e SHA-256 dos artefatos;
3. ensaie o restore em recurso isolado, com saídas de WhatsApp, webhooks e SMTP desabilitadas;
4. confirme compatibilidade de schema entre a release atual e a release candidata.

Não use cópia de volume ativo como única prova de recuperação.

## 3. Verificar compatibilidade dos volumes

O Compose homologado reutiliza estes nomes persistentes:

- `postgres_data`;
- `redis_data`;
- `clickhouse_data`;
- `auth_storage`;
- `crm_storage`;
- `crm_cache`;
- `processor_logs`.

E exige também:

- `rabbitmq_data`;
- `evolution_instances`.

A troca do caminho do Compose só preserva os volumes se o Coolify mantiver o mesmo namespace do recurso. Confirme os nomes finais renderizados antes do deploy. Não marque volumes antigos como `external` e não crie outro recurso apontando para os mesmos volumes.

## 4. Validar o contrato da Evolution

No cofre do próprio ambiente, sem imprimir valores:

- `EVOLUTION_ADMIN_SECRET` deve conter a chave de licença/API emitida pela Evolution Foundation;
- `EVOLUTION_WEBHOOK_SECRET` deve ser separado, aleatório e ter pelo menos 32 bytes;
- `EVOLUTION_API_URL` permanece privada: `http://evolution-api:8080`.

Mapeamento obrigatório:

- CRM web e Sidekiq: `EVOLUTION_ADMIN_SECRET`;
- Evolution API: `AUTHENTICATION_API_KEY` usando o mesmo valor;
- Evolution API webhook por instância: `headers.jwt_key` usando `EVOLUTION_WEBHOOK_SECRET`.

Não use `EVOLUTION_API_KEY` como substituta no CRM.

## 5. Reconciliar configuração persistida

`GlobalConfig` e `provider_config` de canais antigos podem prevalecer sobre o ENV em alguns caminhos. Antes do corte:

1. detecte apenas presença e divergência por fingerprint, sem imprimir credenciais;
2. identifique canais com `api_url`, `admin_token` ou `api_hash` persistidos;
3. preserve configurações realmente customizadas;
4. reconcilie referências obsoletas de modo auditável;
5. confirme que nenhum log contém o conteúdo de `provider_config`.

Um redeploy isolado não corrige automaticamente valores antigos no banco.

## 6. Reconciliar webhooks existentes

Instâncias já criadas podem não possuir `headers.jwt_key`, ou podem possuir a chave anterior. Antes de exigir o novo segredo no receptor:

1. inventarie instâncias sem revelar tokens ou QR Codes;
2. atualize o webhook de cada instância de forma idempotente;
3. faça rotação coordenada, mantendo sobreposição no verificador quando aplicável;
4. envie uma entrega de teste autenticada e confirme processamento durável;
5. só então remova a chave anterior.

Não recrie instâncias e não apague `evolution_instances`, Redis ou schema `evolution_api` como tentativa genérica.

## 7. Gates antes do deploy

- PRs dos componentes integrados nas branches de homologação corretas.
- Root CI e testes de provisioning verdes.
- Oito imagens por digest SHA-256 ou tag de commit completo.
- Pull real das imagens comprovado.
- Todas as variáveis exigidas presentes no recurso correto.
- Jobs na ordem `crm-schema-init` → `auth-migration-stamp`, com `flow-db-init` após Postgres.
- Apenas `evo-crm` web com `RUN_MIGRATIONS=true`; Sidekiq com `false`.
- Rollback documentado e compatível com o schema.

## 8. Aceite operacional

1. `evolution-api` só fica saudável quando `/license/status` retorna `status=active`.
2. CRM resolve `http://evolution-api:8080` na rede privada.
3. Uma rota autenticada da Evolution aceita o header `apikey` sem expor seu valor.
4. Criação de instância registra webhook autenticado.
5. Entrega de teste chega ao CRM uma única vez e entra na fila durável.
6. Login, frontend, CRM, Auth, Core, Processor, Flow, assets e WSS `/cable` permanecem saudáveis.
7. Novo deploy manual do mesmo commit comprova idempotência.

A promoção para o recurso principal só pode ocorrer após todos esses gates e autorização separada.