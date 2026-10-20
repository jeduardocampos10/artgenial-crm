# ArtGenial — implementação controlada para revisão

## Escopo e estado

Alterações locais, sem commit, push, deploy, mudanças de infraestrutura, banco ou arquitetura. O workspace já continha alterações em 13 arquivos do frontend e 10 arquivos do backend; elas foram preservadas e completadas. O diff final inclui essas alterações anteriores.

Nenhuma mudança funcional no provider `evolution_go`. Apenas seus nomes e ícones apresentados em componentes compartilhados receberam a identidade ArtGenial.

## Branding

- Nome: ArtGenial CRM; conexão gerenciada: ArtGenial WhatsApp; opção Go: ArtGenial WhatsApp Go.
- Logo central compartilhado, cabeçalho, login, setup, onboarding, ícones de canal, prévia do widget e notificações.
- Título HTML, application-name, description, theme-color, favicon e apple-touch-icon.
- Textos visíveis em en, es, fr, it, pt e pt-BR, nos namespaces channels, layout, oauth, onboarding, products, profile, setup, tours, tutorials e whatsapp. Chaves de tradução e identificadores técnicos foram mantidos. Não houve substituição global no repositório.
- Tutorial externo da Evolution substituído por orientação local com link de criação de canal. Links de documentação comercial e WhatsApp de suporte da marca anterior retirados da navegação; nenhum contato oficial ArtGenial foi inventado.
- Azul oficial #0F2A6E como primária clara e laranja oficial #FF5A1F como destaque, foco e primária escura. Texto branco sobre azul e #111827 sobre laranja. Onboarding deixou de usar #00FFA7. A paleta do widget trocou #00D4AA por #0F2A6E, sem sobrescrever configurações já salvas.
- Tipografia: Segoe UI, Arial, sans-serif, incluindo onboarding. Não há arquivo de fonte oficial nas pastas autorizadas; não foi baixada ou inventada uma fonte de marca. Logotipo preserva sua tipografia original.
- Fundo branco para legibilidade do logo original no tema escuro e no onboarding escuro.

## Assets oficiais

Originais mantidos intactos. Cópias em `evo-ai-frontend-community/public/ArtGenial/CRM` e `Favicon`, necessárias ao build Vite. A comparação SHA-256 de cada cópia com a origem passou.

| Asset | Dimensões | Uso |
| --- | --- | --- |
| CRM/login-logo.png | 320 × 81 | Login/setup e logo compartilhado |
| CRM/login-logo@2x.png | 640 × 163 | srcSet de alta densidade |
| CRM/sidebar-logo-h32.png | 126 × 32 | Cabeçalho/navegação |
| CRM/sidebar-logo-h32@2x.png | 252 × 64 | srcSet de navegação |
| CRM/sidebar-icone-32.png | 32 × 32 | Prévia do widget |
| CRM/sidebar-icone@2x-64.png | 64 × 64 | Ícone dos canais gerenciados |
| Favicon/favicon.ico | ICO | Favicon multiformato |
| Favicon/favicon-32.png | 32 × 32 | Favicon PNG |
| Favicon/apple-touch-icon-180.png | 180 × 180 | Atalho Apple |
| Favicon/favicon-48.png | 48 × 48 | Notificações |
| Favicon/favicon-16.png | 16 × 16 | Cópia oficial disponível, sem referência direta |

Também examinados: master horizontal PNG 2361 × 600; ícone master PNG 1024 × 1024; SVG vetorial com viewBox 6 6 88 88 e cores #0F2A6E / #FF5A1F. Foram preferidos os PNGs específicos de CRM para as dimensões de interface, sem redesenhar logos ou modificar os masters/PDFs.

## /channels/new e credenciais server-side

- O formulário `evolution` mostra telefone, proxy e configurações funcionais da instância; não pede API URL, Base URL, API Key, Admin Token ou Admin Secret.
- Sem configuração global, informa indisponibilidade e orienta procurar o administrador. A validação rejeita a criação mesmo com credenciais manuais antigas no estado.
- Teste e criação enviam nome, telefone, proxy e opções da instância às rotas existentes. Credenciais antigas não entram nos payloads.
- `EvolutionService` deixou de aceitar/transmitir URL e hash nos métodos de QR Code, proxy e settings; o health check consulta o backend sem URL manual.
- `ConfigurationForm` oculta Connection Settings para `evolution`; o ramo Go foi preservado.
- A resolução existente por `GlobalConfigService` / `EvolutionConcern` mantém `EVOLUTION_API_URL` e `EVOLUTION_ADMIN_SECRET` no servidor. Nenhuma credencial foi adicionada a VITE, bundle, localStorage ou sessionStorage.
- Removidos URL/token Evolution da configuração legada enviada ao navegador; exposto apenas booleano de presença.
- Respostas Jbuilder e InboxSerializer removem URL, admin token/secret, API keys/hash e tokens da instância para `evolution`, preservando nome e configurações funcionais.
- Autorização devolve apenas instanceName, instanceId e status do objeto da instância, sem hash upstream. Listagem de instâncias deixa de devolver api_url.
- Atualização do canal mescla as opções recebidas com a configuração server-side existente para não apagar credenciais legadas ocultas da interface.
- Mantidos endpoints, lógica de QR Code, conexão/status, mensagens, configurações, desconexão e backend Evolution. Não reescrito o ciclo de provisionamento.

## Segurança e licença

- Logs de parâmetros, headers, corpos e respostas potencialmente sensíveis do fluxo Evolution foram filtrados; logs de exceções usam classe em vez de texto potencialmente contendo dados do upstream.
- Acrescentados apikey, apiKey e EVOLUTION_ADMIN_SECRET ao filtro de parâmetros Rails; api_hash/admin_token já estavam cobertos.
- Nenhuma remoção de LICENSE, NOTICE, copyright, marcas em identificadores técnicos ou dependências. A atribuição original à Evolution Foundation permanece literalmente em uma seção expansível “Avisos legais”. Configurações administrativas internas e documentos legais de origem foram preservados. Isso não representa parecer jurídico sobre possibilidade de remoção de atribuições.

## Limites e pendências

- Validar em homologação o ciclo real WhatsApp: criar canal, QR Code, conectar, status, enviar/receber, editar configurações e desconectar. Não foram feitas chamadas à infraestrutura ou instâncias reais nesta execução.
- Testes Rails não podem ser executados neste ambiente sem Ruby/Bundler e serviços de teste. Foram acrescentados specs de autorização e serialização para execução no ambiente apropriado.
- Contato oficial de suporte, documentação completa e eventual arquivo oficial de fonte ArtGenial não foram fornecidos.
- Riscos arquiteturais da auditoria, autorização e ciclo de provisionamento ficam para etapa futura, conforme instrução. O teste de conexão mantém o comportamento backend pré-existente, inclusive seu ciclo de provisionamento.
- O controlador legado de dashboard ainda possui configurações sensíveis de OUTROS providers; não foram refatoradas para respeitar este escopo e a restrição sobre evolution_go. O filtro aplicado nesta execução cobre as credenciais Evolution solicitadas.
- Para leitura do Git, foram adicionados safe.directory apenas para raiz, frontend e CRM após aprovação da ferramenta. Nenhuma mudança de commit, branch ou remotes.

## Validação

Resultados finais acrescentados abaixo após término dos processos.

## Arquivos alterados e novos (estado final do workspace)

### Frontend
 M index.html
 M src/components/AppLogo.tsx
 M src/components/channels/ChannelIcon.tsx
 M src/components/channels/forms/whatsapp/EvolutionForm.tsx
 M src/components/channels/settings/ConfigurationForm.tsx
 M src/components/channels/settings/helpers/widgetHelpers.ts
 M src/components/channels/settings/widget/WidgetContainer.tsx
 M src/components/layout/components/Header.tsx
 M src/components/layout/components/Sidebar.tsx
 M src/contexts/NotificationsContext.tsx
 M src/hooks/channels/useChannelForm.ts
 M src/hooks/channels/useChannelSubmission.spec.ts
 M src/hooks/channels/useChannelSubmission.ts
 M src/hooks/channels/useChannelValidation.spec.ts
 M src/hooks/channels/useChannelValidation.ts
 M src/i18n/locales/_lib/allowlist.ts
 M src/i18n/locales/en/channels.json
 M src/i18n/locales/en/layout.json
 M src/i18n/locales/en/oauth.json
 M src/i18n/locales/en/onboarding.json
 M src/i18n/locales/en/products.json
 M src/i18n/locales/en/profile.json
 M src/i18n/locales/en/setup.json
 M src/i18n/locales/en/tours.json
 M src/i18n/locales/en/tutorials.json
 M src/i18n/locales/en/whatsapp.json
 M src/i18n/locales/en/widget.json
 M src/i18n/locales/es/channels.json
 M src/i18n/locales/es/layout.json
 M src/i18n/locales/es/oauth.json
 M src/i18n/locales/es/onboarding.json
 M src/i18n/locales/es/products.json
 M src/i18n/locales/es/profile.json
 M src/i18n/locales/es/setup.json
 M src/i18n/locales/es/tours.json
 M src/i18n/locales/es/tutorials.json
 M src/i18n/locales/es/whatsapp.json
 M src/i18n/locales/es/widget.json
 M src/i18n/locales/fr/channels.json
 M src/i18n/locales/fr/layout.json
 M src/i18n/locales/fr/oauth.json
 M src/i18n/locales/fr/onboarding.json
 M src/i18n/locales/fr/products.json
 M src/i18n/locales/fr/profile.json
 M src/i18n/locales/fr/setup.json
 M src/i18n/locales/fr/tours.json
 M src/i18n/locales/fr/tutorials.json
 M src/i18n/locales/fr/whatsapp.json
 M src/i18n/locales/fr/widget.json
 M src/i18n/locales/it/channels.json
 M src/i18n/locales/it/layout.json
 M src/i18n/locales/it/oauth.json
 M src/i18n/locales/it/onboarding.json
 M src/i18n/locales/it/products.json
 M src/i18n/locales/it/profile.json
 M src/i18n/locales/it/setup.json
 M src/i18n/locales/it/tours.json
 M src/i18n/locales/it/tutorials.json
 M src/i18n/locales/it/whatsapp.json
 M src/i18n/locales/it/widget.json
 M src/i18n/locales/pt-BR/channels.json
 M src/i18n/locales/pt-BR/layout.json
 M src/i18n/locales/pt-BR/oauth.json
 M src/i18n/locales/pt-BR/onboarding.json
 M src/i18n/locales/pt-BR/products.json
 M src/i18n/locales/pt-BR/profile.json
 M src/i18n/locales/pt-BR/setup.json
 M src/i18n/locales/pt-BR/tours.json
 M src/i18n/locales/pt-BR/tutorials.json
 M src/i18n/locales/pt-BR/whatsapp.json
 M src/i18n/locales/pt-BR/widget.json
 M src/i18n/locales/pt/channels.json
 M src/i18n/locales/pt/layout.json
 M src/i18n/locales/pt/oauth.json
 M src/i18n/locales/pt/onboarding.json
 M src/i18n/locales/pt/products.json
 M src/i18n/locales/pt/profile.json
 M src/i18n/locales/pt/setup.json
 M src/i18n/locales/pt/tours.json
 M src/i18n/locales/pt/tutorials.json
 M src/i18n/locales/pt/whatsapp.json
 M src/i18n/locales/pt/widget.json
 M src/pages/Customer/Channels/ChannelSettings.tsx
 M src/pages/Customer/Channels/NewChannel/NewChannel.spec.tsx
 M src/pages/Customer/Tutorials/index.tsx
 M src/pages/Setup/OnboardingPage.tsx
 M src/pages/Shared/Marketplace/Marketplace.tsx
 M src/services/channels/evolutionService.ts
 M src/styles/globals.css
 M src/types/channels/inbox.ts
?? public/ArtGenial/
?? src/components/channels/forms/whatsapp/EvolutionForm.spec.tsx
public/ArtGenial/CRM/login-logo.png
public/ArtGenial/CRM/login-logo@2x.png
public/ArtGenial/CRM/sidebar-icone-32.png
public/ArtGenial/CRM/sidebar-icone@2x-64.png
public/ArtGenial/CRM/sidebar-logo-h32.png
public/ArtGenial/CRM/sidebar-logo-h32@2x.png
public/ArtGenial/Favicon/apple-touch-icon-180.png
public/ArtGenial/Favicon/favicon-16.png
public/ArtGenial/Favicon/favicon-32.png
public/ArtGenial/Favicon/favicon-48.png
public/ArtGenial/Favicon/favicon.ico
src/components/channels/forms/whatsapp/EvolutionForm.spec.tsx
### Backend CRM
 M app/controllers/api/v1/evolution/authorizations_controller.rb
 M app/controllers/api/v1/evolution/instances_controller.rb
 M app/controllers/api/v1/evolution/privacy_controller.rb
 M app/controllers/api/v1/evolution/profile_controller.rb
 M app/controllers/api/v1/evolution/proxies_controller.rb
 M app/controllers/api/v1/evolution/qrcodes_controller.rb
 M app/controllers/api/v1/evolution/settings_controller.rb
 M app/controllers/api/v1/inboxes_controller.rb
 M app/controllers/dashboard_controller.rb
 M app/serializers/inbox_serializer.rb
 M app/services/whatsapp/providers/evolution_service.rb
 M app/views/api/v1/models/_inbox.json.jbuilder
 M config/initializers/filter_parameter_logging.rb
 M spec/serializers/inbox_serializer_connection_state_spec.rb
?? spec/controllers/api/v1/evolution/
spec/controllers/api/v1/evolution/authorizations_controller_spec.rb

## git diff --stat

### Raiz (submódulos com alterações locais)
 evo-ai-crm-community      | 0
 evo-ai-frontend-community | 0
 2 files changed, 0 insertions(+), 0 deletions(-)
### Frontend
 index.html                                         | 11 +++-
 src/components/AppLogo.tsx                         | 26 ++++++---
 src/components/channels/ChannelIcon.tsx            |  4 +-
 .../channels/forms/whatsapp/EvolutionForm.tsx      | 22 +------
 .../channels/settings/ConfigurationForm.tsx        |  6 +-
 .../channels/settings/helpers/widgetHelpers.ts     |  2 +-
 .../channels/settings/widget/WidgetContainer.tsx   |  8 +--
 src/components/layout/components/Header.tsx        |  4 +-
 src/components/layout/components/Sidebar.tsx       | 27 ++-------
 src/contexts/NotificationsContext.tsx              |  2 +-
 src/hooks/channels/useChannelForm.ts               |  4 +-
 src/hooks/channels/useChannelSubmission.spec.ts    | 54 +++++++++++++++++
 src/hooks/channels/useChannelSubmission.ts         | 68 ++--------------------
 src/hooks/channels/useChannelValidation.spec.ts    | 14 +++++
 src/hooks/channels/useChannelValidation.ts         | 10 +---
 src/i18n/locales/_lib/allowlist.ts                 |  1 +
 src/i18n/locales/en/channels.json                  |  8 +--
 src/i18n/locales/en/layout.json                    |  3 +-
 src/i18n/locales/en/oauth.json                     |  4 +-
 src/i18n/locales/en/onboarding.json                |  4 +-
 src/i18n/locales/en/products.json                  |  2 +-
 src/i18n/locales/en/profile.json                   |  2 +-
 src/i18n/locales/en/setup.json                     |  2 +-
 src/i18n/locales/en/tours.json                     |  2 +-
 src/i18n/locales/en/tutorials.json                 |  4 +-
 src/i18n/locales/en/whatsapp.json                  | 23 ++++----
 src/i18n/locales/en/widget.json                    |  2 +-
 src/i18n/locales/es/channels.json                  |  8 +--
 src/i18n/locales/es/layout.json                    |  3 +-
 src/i18n/locales/es/oauth.json                     |  4 +-
 src/i18n/locales/es/onboarding.json                |  4 +-
 src/i18n/locales/es/products.json                  |  2 +-
 src/i18n/locales/es/profile.json                   |  2 +-
 src/i18n/locales/es/setup.json                     |  2 +-
 src/i18n/locales/es/tours.json                     |  2 +-
 src/i18n/locales/es/tutorials.json                 |  4 +-
 src/i18n/locales/es/whatsapp.json                  | 23 ++++----
 src/i18n/locales/es/widget.json                    |  2 +-
 src/i18n/locales/fr/channels.json                  |  8 +--
 src/i18n/locales/fr/layout.json                    |  3 +-
 src/i18n/locales/fr/oauth.json                     |  4 +-
 src/i18n/locales/fr/onboarding.json                |  4 +-
 src/i18n/locales/fr/products.json                  |  2 +-
 src/i18n/locales/fr/profile.json                   |  2 +-
 src/i18n/locales/fr/setup.json                     |  2 +-
 src/i18n/locales/fr/tours.json                     |  2 +-
 src/i18n/locales/fr/tutorials.json                 |  4 +-
 src/i18n/locales/fr/whatsapp.json                  | 23 ++++----
 src/i18n/locales/fr/widget.json                    |  2 +-
 src/i18n/locales/it/channels.json                  |  8 +--
 src/i18n/locales/it/layout.json                    |  3 +-
 src/i18n/locales/it/oauth.json                     |  4 +-
 src/i18n/locales/it/onboarding.json                |  4 +-
 src/i18n/locales/it/products.json                  |  2 +-
 src/i18n/locales/it/profile.json                   |  2 +-
 src/i18n/locales/it/setup.json                     |  2 +-
 src/i18n/locales/it/tours.json                     |  2 +-
 src/i18n/locales/it/tutorials.json                 |  4 +-
 src/i18n/locales/it/whatsapp.json                  | 23 ++++----
 src/i18n/locales/it/widget.json                    |  2 +-
 src/i18n/locales/pt-BR/channels.json               |  8 +--
 src/i18n/locales/pt-BR/layout.json                 |  3 +-
 src/i18n/locales/pt-BR/oauth.json                  |  4 +-
 src/i18n/locales/pt-BR/onboarding.json             |  4 +-
 src/i18n/locales/pt-BR/products.json               |  2 +-
 src/i18n/locales/pt-BR/profile.json                |  2 +-
 src/i18n/locales/pt-BR/setup.json                  |  2 +-
 src/i18n/locales/pt-BR/tours.json                  |  2 +-
 src/i18n/locales/pt-BR/tutorials.json              |  4 +-
 src/i18n/locales/pt-BR/whatsapp.json               | 23 ++++----
 src/i18n/locales/pt-BR/widget.json                 |  2 +-
 src/i18n/locales/pt/channels.json                  |  8 +--
 src/i18n/locales/pt/layout.json                    |  3 +-
 src/i18n/locales/pt/oauth.json                     |  4 +-
 src/i18n/locales/pt/onboarding.json                |  4 +-
 src/i18n/locales/pt/products.json                  |  2 +-
 src/i18n/locales/pt/profile.json                   |  2 +-
 src/i18n/locales/pt/setup.json                     |  2 +-
 src/i18n/locales/pt/tours.json                     |  2 +-
 src/i18n/locales/pt/tutorials.json                 |  4 +-
 src/i18n/locales/pt/whatsapp.json                  | 29 ++++-----
 src/i18n/locales/pt/widget.json                    |  2 +-
 src/pages/Customer/Channels/ChannelSettings.tsx    |  4 +-
 .../Channels/NewChannel/NewChannel.spec.tsx        |  5 +-
 src/pages/Customer/Tutorials/index.tsx             | 14 ++---
 src/pages/Setup/OnboardingPage.tsx                 | 38 ++++++------
 src/pages/Shared/Marketplace/Marketplace.tsx       | 13 -----
 src/services/channels/evolutionService.ts          | 23 ++------
 src/styles/globals.css                             | 22 +++++++
 src/types/channels/inbox.ts                        |  2 -
 90 files changed, 366 insertions(+), 360 deletions(-)
### Backend CRM
 .../api/v1/evolution/authorizations_controller.rb  | 66 +++++++++++-----------
 .../api/v1/evolution/instances_controller.rb       | 23 ++++----
 .../api/v1/evolution/privacy_controller.rb         | 16 +++---
 .../api/v1/evolution/profile_controller.rb         | 52 ++++++++---------
 .../api/v1/evolution/proxies_controller.rb         | 26 ++++-----
 .../api/v1/evolution/qrcodes_controller.rb         | 16 +++---
 .../api/v1/evolution/settings_controller.rb        | 28 ++++-----
 app/controllers/api/v1/inboxes_controller.rb       |  6 +-
 app/controllers/dashboard_controller.rb            |  4 +-
 app/serializers/inbox_serializer.rb                |  5 ++
 .../whatsapp/providers/evolution_service.rb        | 18 +++---
 app/views/api/v1/models/_inbox.json.jbuilder       |  8 ++-
 config/initializers/filter_parameter_logging.rb    |  2 +-
 .../inbox_serializer_connection_state_spec.rb      | 13 +++++
 14 files changed, 153 insertions(+), 130 deletions(-)

## Resultados de testes e verificações

- `npm ci --ignore-scripts --no-audit --no-fund`: concluído, 535 pacotes; lockfiles sem alterações.
- `npm run lint`: passou (exit 0).
- ESLint direcionado aos últimos ajustes em AppLogo, Marketplace, mock de NewChannel e allowlist: passou (exit 0).
- `npm test -- src/hooks/channels src/components/channels/forms/whatsapp/EvolutionForm.spec.tsx src/pages/Customer/Channels src/pages/Setup src/i18n`: primeira execução com 306 testes aprovados e 10 falhas em 2 suítes. Corrigidos o mock preexistente sem useLocation e a allowlist de nomes de marca para ArtGenial.
- Reexecução somente de NewChannel.spec.tsx e i18n-parity.spec.ts: 185/185 passaram (exit 0). Total dos casos selecionados cobertos após correções: 316 em 14 arquivos; não foi executada a suíte integral do monorepo.
- Os testes incluem ausência de credenciais no formulário, rejeição sem configuração global, payloads de criação/teste sem credenciais antigas, preservação do fluxo Go, status ao vivo, configurações do canal, setup/onboarding e paridade das traduções.
- `git diff --check`: passou na raiz, frontend e backend; `git status` e `git diff --stat` executados nos três repositórios.
- Cópias dos 11 assets: SHA-256 idêntico aos originais.
- Ruby indisponível (`ruby --version`: comando não encontrado). Specs Rails acrescentados, mas NÃO executados.

Warnings: dependência @icons-pack/react-simple-icons pede Node >=24, mas ambiente usa Node 22.16; whatwg-encoding obsoleto; mock existente de ChannelSettings repassa `loading` booleano para elemento DOM; avisos Git de LF/CRLF; npm ignorou flags de workers na repetição, que mesmo assim passou. Nenhuma atualização de versão ou lockfile foi feita para contornar esses avisos.

Complementos finais de branding: título padrão do widget público atualizado nos seis idiomas; oferta simulada “EvoAI Team” retirada do marketplace, sem atribuir autoria a ArtGenial. Lista de nomes de marca dos testes de tradução atualizada.

O `git diff --stat` acima contabiliza apenas arquivos rastreados: frontend 90 arquivos (+366/-360), backend 14 arquivos (+153/-130). Assets copiados, novos specs e este relatório são arquivos novos e aparecem na lista de status, não nesses totais.

### Build final

`npm run build` passou: TypeScript (`tsc -b`) e Vite concluídos, 10.493 módulos transformados. Assets oficiais presentes em `dist/ArtGenial`, com SHA-256 idêntico às fontes. Favicon ICO contém quadros 16 × 16, 32 × 32 e 48 × 48.

Warnings do Vite: imports estáticos e dinâmicos simultâneos em audioNotificationUtils e widgetService; chunks acima de 500 kB (principal aproximadamente 8,23 MB / 2,08 MB gzip). Não alterado o particionamento de bundle ou arquitetura nesta etapa.

Estado final: aguardando revisão do usuário. Nenhum commit, push ou deploy executado. Scripts temporários removidos; originais de branding, backups e arquivos não relacionados preservados.
