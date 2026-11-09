# Auditoria da homologação — WhatsApp, IA e atendimento humano

## Escopo

Varredura do `develop` e dos submódulos de frontend, CRM, autenticação, Core, Processor, Bot Runtime, Evo Flow e provisionamento.

A análise foi realizada em clone limpo porque o checkout anterior tinha worktrees de submódulos materialmente vazios. O clone limpo fixa os commits apontados por `develop` e serve como baseline desta implementação.

## Parecer executivo

A plataforma já contém uma base extensa:

- CRM, contatos, conversas, pipelines, etiquetas e automações;
- canais WhatsApp, e-mail, Instagram, Facebook, Telegram e widget;
- agentes LLM e compostos, custom tools, MCP e integrações;
- debounce, mídia, chamada A2A e postback;
- handoff IA → humano e Humano → IA;
- analytics operacional;
- fundação temporal de identidade, eventos e memória do cliente.

O problema principal não é ausência de recursos. É a diferença entre **código existente**, **capacidade segura**, **capacidade validada em homologação** e **capacidade pronta para autonomia**.

O WhatsApp ainda está `EM VALIDAÇÃO`. Não há evidência suficiente para declará-lo 100% dos critérios, e o próprio roadmap mantém envio completo, reconexão e recuperação pendentes.

## Decisões de produto

1. Lead Capture existente fica congelado: apenas correções críticas, segurança e integridade.
2. Gestão de Documentos fica adiada; anexos de mensagens não constituem gestão documental.
3. Nenhuma das duas recebe evolução antes da aprovação do Gate WhatsApp.
4. Depois do gate, a prioridade é suporte multicanal com ownership humano, analytics e automação supervisionada.
5. As entregas são incrementos de duas semanas, sempre encerrados por aceite humano.

## Mapa do fluxo WhatsApp atual

```text
Telefone
  → Evolution API/Go
  → webhook Rails CRM
  → Sidekiq
  → contato + conversa + mensagem
  → AgentBotListener
  → BotRuntime::DelegationService
  → Bot Runtime / Redis / debounce
  → Processor / agente / modelo / tools
  → postback CRM
  → mensagem de saída
  → Evolution
  → telefone
```

## Capacidades confirmadas

### Frontend

- Criação e configuração de canal Evolution.
- QR Code, status ao vivo, proxy, settings e logout.
- Configuração de agentes, comportamento, tools, integrações e regras.
- Arquivos principais:
  - `evo-ai-frontend-community/src/hooks/channels/useChannelSubmission.ts`
  - `evo-ai-frontend-community/src/services/channels/evolutionService.ts`
  - `evo-ai-frontend-community/src/components/agents/configuration/BehaviorPanel.tsx`

### CRM Rails

- Ingestão e envio de texto, imagem, áudio, vídeo e documento.
- Providers Evolution, Evolution Go, Cloud, Notificame e Z-API.
- Conversas, handoff, retorno ao bot, timeline e eventos de reporting.
- Fundação de memória com fatos, inferências, evidências, validade e supersessão.
- Arquivos principais:
  - `app/controllers/webhooks/whatsapp_controller.rb`
  - `app/services/whatsapp/incoming_message_evolution_service.rb`
  - `app/services/whatsapp/providers/evolution_service.rb`
  - `app/models/conversation.rb`
  - `app/models/concerns/bot_handoff_activity_message_handler.rb`
  - `db/migrate/20261027120000_create_customer_memory_foundation.rb`

### Core e Processor

- Agentes LLM, workflow, task, A2A, sequenciais, paralelos e externos.
- Prompts com role, goal, contexto, timezone, pipelines e catálogo.
- Custom HTTP tools, MCP, Calendar, Sheets e Knowledge Nexus.
- Tools de CRM para handoff, notas, contato, pipeline, etiquetas e vendas.
- Arquivos principais:
  - `evo-ai-core-service-community/pkg/agent/service/processor/config_processor.go`
  - `evo-ai-processor-community/src/services/adk/agents/llm_agent_builder.py`
  - `evo-ai-processor-community/src/services/adk/tool_builder.py`
  - `evo-ai-processor-community/src/services/adk/tools/evo_crm/`

### Bot Runtime e automação

- Autenticação por segredo interno.
- Redis, lock, debounce, anexos, retry de IA e segmentação.
- Evo Flow com eventos, segmentos, jornadas, campanhas e ações CRM.
- Arquivos principais:
  - `evo-bot-runtime/pkg/pipeline/handler/handler.go`
  - `evo-bot-runtime/pkg/pipeline/service/pipeline_service.go`
  - `evo-bot-runtime/pkg/dispatch/service/dispatch_engine.go`

## Bloqueadores do Gate WhatsApp

### Críticos

1. **Webhook Evolution sem autenticação verificável de POST**
   - O handshake GET não protege eventos POST.
   - Risco: spoofing, mensagens falsas, consumo indevido de IA e alteração de histórico.

2. **Teste de conexão com efeito destrutivo**
   - O endpoint usado como teste pode excluir e recriar instância.
   - Deve haver separação entre probe, criação, recriação e exclusão.

3. **Aceite do Bot Runtime antes da durabilidade integral**
   - O handler responde `202` enquanto parte essencial do evento ainda depende da goroutine em memória.
   - Um crash nessa janela pode deixar mensagem sem resposta.

4. **Postback sem retry durável**
   - Uma resposta pode ser gerada pela IA e não chegar ao CRM/WhatsApp.
   - Necessário outbox ou retry idempotente.

5. **Resposta em voo após handoff**
   - Uma geração iniciada antes do humano assumir pode terminar depois.
   - O postback precisa validar `turn_id`, versão de ownership e elegibilidade atual.

### Altos

- Falta de idempotência global de webhook.
- `api_url` com risco de SSRF em rotas administrativas.
- Payloads/PII excessivos em logs.
- Credenciais em JSONB/Redis exigem endurecimento operacional.
- Timeouts externos inconsistentes.
- Apenas o primeiro anexo é enviado em parte do fluxo.
- Evolution não integra o compose principal e depende de infraestrutura externa.
- Custom HTTP tools precisam de política de egress/SSRF.
- Não existe Policy + Approval Engine central; flags booleanas liberam tools mutáveis.

## Gate WhatsApp — aceite objetivo

O canal prioritário só pode ser declarado aprovado quando houver evidência para:

### Instalação

- clone limpo reproduzível;
- matriz de commits e imagens;
- migrations e seeds sem erro;
- serviços healthy após restart;
- provider Evolution declarado e homologado.

### Canal

- criação sem credenciais administrativas no navegador;
- probe somente leitura;
- QR, expiração e renovação;
- conexão e status reais;
- nome de instância consistente entre frontend, CRM e provider.

### Entrada e saída

- texto, imagem, áudio, vídeo e documento;
- IDs remotos e estados enviado/entregue/lido/falhou;
- webhook inválido rejeitado;
- redelivery sem duplicação;
- retry classificado para 429/5xx;
- timeout em todas as chamadas externas.

### IA

- exatamente um turno por mensagem elegível;
- evento durável antes do aceite;
- restart durante debounce e geração;
- postback idempotente e repetível;
- bloqueio de resposta depois do handoff;
- falha da IA sem bloquear atendimento manual.

### Resiliência

- reinício de CRM, Sidekiq, Redis, Bot Runtime, Processor e Evolution;
- perda de rede entre os serviços;
- sessão inválida e novo QR explícito;
- fila recuperável, DLQ/replay e alertas;
- soak test sem Sev-1/Sev-2 aberto.

## Atendimento humano moderno

### Princípios

- responder no idioma do cliente, com PT-BR natural quando aplicável;
- compreender a necessidade antes de oferecer opções;
- reconhecer emoção sem teatralidade;
- fazer uma pergunta essencial por vez;
- não repetir dados já disponíveis;
- não inventar preço, política, prazo, disponibilidade ou ação executada;
- não fingir ser humano;
- confirmar ações sensíveis;
- transferir por pedido explícito, baixa confiança, falha repetida, frustração, reclamação crítica, cancelamento, risco ou exceção de política.

### Ownership

Estado alvo:

```text
AI_SUGGESTING
AWAITING_HUMAN_APPROVAL
AI_EXECUTING_ALLOWED_ACTION
HUMAN_OWNED
AWAITING_CUSTOMER
RESOLVED
```

Durante `HUMAN_OWNED`:

- IA pode sugerir internamente;
- IA não envia mensagem externa;
- automações externas ficam suspensas;
- timers podem criar tarefa, não mensagem;
- toda tentativa bloqueada é auditada.

## Primeira fatia implementada nesta branch

### Skill `artgenial.human-service.v1`

Skill versionada e compilada a partir de registro fechado, sem permitir prompt arbitrário pela configuração. Ela define:

- linguagem natural e transparente;
- uso do contexto;
- concisão apropriada ao WhatsApp;
- honestidade sobre incerteza e identidade virtual;
- confirmação de ações sensíveis;
- critérios de escalonamento;
- checklist antes de cada resposta.

É habilitada explicitamente pelo novo controle de comportamento e também acompanha o toggle de transferência para humano como padrão seguro de compatibilidade.

### Handoff endurecido

- somente destinos configurados são aceitos;
- IDs arbitrários escolhidos pelo modelo são rejeitados;
- múltiplos destinos exigem escolha explícita autorizada;
- nota privada estruturada e escapada contém solicitação, resumo, ações, fatos, próxima ação e prioridade;
- automação é interrompida antes da atribuição;
- falha de atribuição deixa a conversa em estado humano para supervisão, sem retorno enganoso de sucesso completo.

### Interface e configuração

- toggle “Atendimento humano ArtGenial” no painel de comportamento;
- configuração preservada pelo Core;
- traduções nos seis idiomas existentes;
- todas as skills novas permanecem desabilitadas por padrão; ativação exige decisão explícita do operador na homologação.

## Próxima fatia recomendada

### Copiloto PT-BR — somente rascunho

Reutilizar o endpoint de draft existente no CRM para produzir sugestão revisável pelo atendente:

- sem autoenvio;
- sem tools mutáveis;
- sem escrita em memória;
- invalidação quando chega nova mensagem;
- feedback enviar sem edição, editar e enviar, ou rejeitar;
- prompt versionado e logs sem PII;
- métricas de aceitação, edição, rejeição e latência.

Essa fatia deve ser iniciada somente depois da revisão desta fundação e não substitui os bloqueadores do Gate WhatsApp.

## Ordem executável

```text
Baseline reproduzível
→ Gate WhatsApp
→ ownership humano + Copiloto PT-BR
→ suporte multicanal
→ eventos e analytics reconciliados
→ automação supervisionada
→ identidade e memória
→ intenção e recomendação
→ Policy + Approval
→ orquestrador e especialista piloto
→ atribuição e ROI
→ backlog condicionado
```

## Regra de avanço

Nenhuma fase futura começa automaticamente. Ao final de cada ciclo devem existir:

- diff revisável;
- testes executados e limitações explícitas;
- evidências de homologação;
- riscos residuais;
- aprovação humana para o próximo ciclo.
