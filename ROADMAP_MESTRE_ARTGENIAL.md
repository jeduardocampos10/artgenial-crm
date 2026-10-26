# ROADMAP MESTRE — ARTGENIAL CRM + EQUIPE DIGITAL DE IA

## Objetivo

Transformar a ArtGenial em uma plataforma completa de atendimento, vendas, relacionamento e automação empresarial, combinando:

- CRM
- WhatsApp
- memória unificada do cliente
- inteligência artificial
- agentes especializados
- automações
- supervisão humana
- métricas e ROI
- voz futuramente
- ERP futuramente

Princípio arquitetural:

**O cliente é único.**

WhatsApp, ligações, pipelines, agentes de IA, compras, suporte, follow-ups e demais interações devem alimentar a mesma memória e o mesmo histórico do cliente.

---

# FASE 1 — FUNDAÇÃO DO CRM

**Status: EM ANDAMENTO / BASE PRINCIPAL CONSTRUÍDA**

Objetivo: estabelecer a infraestrutura operacional da ArtGenial antes da autonomia das IAs.

### 1.1 CRM

- [x] CRM base funcionando
- [x] Pipelines ArtGenial definidos
- [x] 6 pipelines oficiais
- [x] 62 estágios
- [x] 29 etiquetas universais
- [x] Base ArtGenial v1
- [x] Ledger de instalação
- [x] Aplicação idempotente da Base
- [x] Base aplicada em homologação
- [x] Base aplicada em produção

### 1.2 WhatsApp

- [x] Evolution API integrada
- [x] Criação de canal
- [x] QR Code
- [x] Conexão de número
- [x] Recebimento de mensagens validado
- [ ] Validar fluxo completo de envio de mensagens
- [ ] Validar reconexão
- [ ] Validar recuperação após indisponibilidade
- [ ] Consolidar experiência simplificada de criação de canal

### 1.3 Experiência de criação de canal

Ao criar um canal, oferecer:

- [ ] Modo Recomendado ArtGenial
- [ ] Modo Personalizado

No **Modo Recomendado ArtGenial**, o sistema deverá configurar automaticamente os componentes necessários para o funcionamento padrão.

---

# FASE 2 — PROVISIONAMENTO ARTGENIAL

**Status: EM ANDAMENTO**

Objetivo: tornar uma nova instalação ArtGenial reproduzível, segura, auditável e futuramente automatizada.

## 2.5.1 — Fundação do Provisionador

**Status: CONCLUÍDA**

- [x] Contrato de instalação
- [x] Catálogo de serviços
- [x] Catálogo de verificações
- [x] Validação de configuração
- [x] Plano determinístico
- [x] Proteção contra secrets no manifesto
- [x] Testes automatizados

## 2.5.2 — Manifesto de Implantação

**Status: CONCLUÍDA**

- [x] Deployment Manifest
- [x] Variáveis classificadas
- [x] Domain bindings
- [x] Internal service bindings
- [x] Secret references
- [x] Environment settings
- [x] Checklist de inicialização
- [x] Checklist de validação

## 2.5.3 — Template Comercial

**Status: CONCLUÍDA**

- [x] Política de runtime comercial
- [x] Valores seguros de produção
- [x] Configurações derivadas
- [x] Banco por instalação
- [x] Proibição de defaults inseguros
- [x] Separação entre desenvolvimento e produção

## 2.5.4 — Executor Seguro

**Status: CONCLUÍDA**

- [x] Máquina de estados
- [x] Fingerprint do manifesto
- [x] Evidências
- [x] Auditoria
- [x] Controle de fases
- [x] Bloqueio de avanço incompleto
- [x] Controle de secrets
- [x] Controle de checks
- [x] Regra de entrega
- [x] Testes automatizados

## 2.5.5 — Instalação Comercial Portável

**Status: EM VALIDAÇÃO**

Objetivo: permitir instalar uma nova ArtGenial a partir do GitHub sem depender especificamente da VPS ou do Coolify atual.

- [x] Criar template comercial oficial de implantação
- [x] Separar completamente configurações locais/dev
- [x] Remover dependência de portas específicas da VPS ArtGenial
- [x] Garantir redes privadas para bancos e serviços internos
- [x] Garantir volumes persistentes
- [x] Configurar secrets somente em runtime
- [x] Configurar domínios por instalação
- [ ] Configurar SMTP comercial
- [ ] Criar processo de bootstrap
- [ ] Executar migrations
- [ ] Criar RuntimeConfig.account
- [ ] Criar administrador inicial
- [ ] Aplicar Base ArtGenial v1
- [ ] Executar verificações obrigatórias
- [ ] Testar instalação limpa partindo exclusivamente do GitHub
- [x] Documentar procedimento oficial

Resultado esperado:

**GitHub → plataforma Docker → configuração → deploy → inicialização → Base ArtGenial → validação → CRM funcionando.**

## 2.5.6 — Adaptador Coolify

**Status: PENDENTE**

- [ ] Ler manifesto
- [ ] Consultar estado do Coolify
- [ ] Criar/configurar recursos necessários
- [ ] Configurar domínios
- [ ] Configurar volumes
- [ ] Configurar variáveis
- [ ] Inserir secrets sem armazená-los no manifesto
- [ ] Executar deploy
- [ ] Capturar evidências
- [ ] Alimentar Executor Seguro
- [ ] Implementar idempotência
- [ ] Permitir retry seguro

## 2.5.7 — Provisionamento pelo ArtAdmin

**Status: FUTURO**

Fluxo desejado:

**Novo Cliente → Configurar → Provisionar → Validar → Entregar**

O ArtAdmin será o orquestrador visual do provisionamento.

---

# FASE 3 — MEMÓRIA UNIFICADA DO CLIENTE

**Status: PENDENTE**

Objetivo: criar uma visão única e persistente de cada cliente.

## 3.1 Customer Identity

- [ ] Identidade única do cliente
- [ ] Telefones
- [ ] WhatsApp
- [ ] E-mail
- [ ] Identificadores externos
- [ ] Deduplicação
- [ ] Merge seguro de contatos

## 3.2 Customer Memory

Registrar:

- [ ] histórico de conversas
- [ ] pipelines
- [ ] estágios
- [ ] etiquetas
- [ ] interesses
- [ ] produtos/serviços
- [ ] objeções
- [ ] compras
- [ ] propostas
- [ ] follow-ups
- [ ] reclamações
- [ ] suporte
- [ ] preferências
- [ ] consentimentos
- [ ] resumos
- [ ] fatos relevantes
- [ ] última interação
- [ ] próxima ação

## 3.3 Memória temporal

A IA deverá distinguir:

- fatos atuais
- fatos históricos
- preferências
- eventos
- hipóteses
- informações confirmadas
- informações desatualizadas

## 3.4 Memória compartilhada

Todos os agentes autorizados devem consultar a mesma memória do cliente.

**Não criar memórias isoladas por agente.**

---

# FASE 4 — INTENT ENGINE ARTGENIAL

**Status: PENDENTE**

Objetivo: compreender o que o cliente realmente pretende fazer.

Não utilizar apenas palavras-chave.

Analisar:

- [ ] mensagem atual
- [ ] contexto da conversa
- [ ] histórico
- [ ] pipeline atual
- [ ] estágio
- [ ] comportamento anterior
- [ ] produto de interesse
- [ ] sentimento
- [ ] urgência

## Intenções iniciais

- [ ] informação
- [ ] interesse
- [ ] compra
- [ ] orçamento
- [ ] negociação
- [ ] agendamento
- [ ] suporte
- [ ] reclamação
- [ ] cancelamento
- [ ] reativação
- [ ] pós-venda

Resultado estruturado esperado:

- intenção
- subintenção
- confiança
- produto/serviço
- objeção
- urgência
- sentimento
- pipeline sugerido
- estágio sugerido
- ação sugerida

---

# FASE 5 — NEXT BEST ACTION ENGINE

**Status: PENDENTE**

Objetivo:

Responder à pergunta:

**"Qual é a melhor próxima ação para este cliente?"**

Possíveis ações:

- [ ] responder
- [ ] fazer pergunta
- [ ] enviar informação
- [ ] apresentar produto
- [ ] enviar proposta
- [ ] solicitar documento
- [ ] agendar
- [ ] criar follow-up
- [ ] alterar estágio
- [ ] adicionar etiqueta
- [ ] encaminhar para outro agente
- [ ] transferir para humano
- [ ] oferecer benefício
- [ ] sugerir upsell
- [ ] sugerir cross-sell
- [ ] iniciar reativação
- [ ] não fazer nada

Toda decisão deverá registrar justificativa e contexto.

---

# FASE 6 — POLICY + APPROVAL ENGINE

**Status: PENDENTE**

Objetivo: controlar o que a IA pode ou não fazer.

## Níveis de autonomia

### Nível 1 — Sugerir

A IA analisa e apresenta uma recomendação.

Não executa.

### Nível 2 — Aprovação

A IA prepara a ação.

O cliente/gestor revisa e aprova ou rejeita.

### Nível 3 — Automático dentro das regras

A IA pode executar automaticamente ações previamente autorizadas.

Mesmo nesse nível, o cliente deverá poder configurar:

- ações automáticas
- ações que exigem aprovação
- ações proibidas

## Regras

- [ ] limites de desconto
- [ ] valores
- [ ] horários
- [ ] produtos
- [ ] campanhas
- [ ] mensagens
- [ ] brindes
- [ ] follow-ups
- [ ] cancelamentos
- [ ] escalonamento
- [ ] ações sensíveis

Todas as decisões deverão ser auditáveis.

---

# FASE 7 — HANDOFF IA → HUMANO

**Status: PENDENTE**

Objetivo: permitir transferência inteligente e segura.

A IA deverá identificar situações como:

- [ ] solicitação explícita de humano
- [ ] baixa confiança
- [ ] reclamação crítica
- [ ] negociação fora das regras
- [ ] situação sensível
- [ ] risco de cancelamento
- [ ] falha repetida
- [ ] regra configurada pelo cliente

Na transferência gerar:

- motivo
- intenção
- sentimento
- produto/serviço
- resumo da conversa
- ações realizadas
- informações importantes
- próxima ação sugerida
- prioridade

Após o humano assumir:

**a IA não deverá continuar respondendo automaticamente sem autorização.**

Também deverá existir processo de devolução:

**Humano → IA**

---

# FASE 8 — ORQUESTRADOR DE IA

**Status: PENDENTE**

Objetivo: criar o gestor da Equipe Digital ArtGenial.

O Orquestrador deverá decidir:

- qual especialista deve atuar
- quando trocar especialista
- quando solicitar aprovação
- quando chamar humano
- quais ferramentas utilizar
- qual contexto entregar ao próximo agente

O Orquestrador não deve substituir os especialistas.

Ele coordena.

---

# FASE 9 — EQUIPE DIGITAL DE AGENTES

**Status: PENDENTE**

## Comercial

- [ ] Prospector
- [ ] SDR / Qualificação
- [ ] Atendimento / Consultor
- [ ] Closer
- [ ] Follow-up
- [ ] Reativação

## Pós-venda

- [ ] Customer Success
- [ ] Onboarding
- [ ] Suporte Técnico

## Personas

Permitir apresentação amigável ao cliente, por exemplo:

- Ana — Atendimento
- Lucas — SDR
- Bia — Follow-up
- Carlos — Reativação
- Julia — Pós-venda

A persona visual não deve criar memória isolada.

Todos utilizam a infraestrutura e a memória unificada ArtGenial.

---

# FASE 10 — AUTOMAÇÃO OPERACIONAL

**Status: PENDENTE**

- [ ] gatilhos
- [ ] cadências
- [ ] timers
- [ ] follow-up 1D
- [ ] follow-up 5D
- [ ] follow-up 15D
- [ ] follow-up 30D
- [ ] abandono
- [ ] reativação
- [ ] mudança automática de estágio
- [ ] etiquetas automáticas
- [ ] tarefas
- [ ] notificações
- [ ] agendamentos
- [ ] campanhas
- [ ] escalonamento
- [ ] auditoria

---

# FASE 11 — EVENTOS E ATRIBUIÇÃO

**Status: PENDENTE**

Objetivo: saber exatamente o que a ArtGenial fez e qual resultado foi produzido.

Registrar eventos como:

- [ ] lead recebido
- [ ] mensagem respondida
- [ ] lead qualificado
- [ ] proposta enviada
- [ ] follow-up executado
- [ ] cliente recuperado
- [ ] agendamento criado
- [ ] oportunidade criada
- [ ] venda realizada
- [ ] upsell
- [ ] cross-sell
- [ ] cliente retido
- [ ] cancelamento evitado
- [ ] transferência humana

Relacionar quando possível:

**Cliente → Evento → Agente → Ação → Pipeline → Resultado → Receita**

---

# FASE 12 — PAINEL DE ROI ARTGENIAL

**Status: PENDENTE**

Objetivo: mostrar resultado empresarial, não consumo técnico de IA.

Dashboard principal:

### Sua Equipe Digital

- clientes atendidos
- conversas resolvidas
- leads qualificados
- follow-ups realizados
- leads recuperados
- clientes reativados
- oportunidades criadas
- propostas
- agendamentos
- vendas
- retenções
- upsells
- cross-sells

### Resultado financeiro

- receita atribuída
- receita influenciada
- oportunidades recuperadas
- ticket médio
- conversão
- valor do pipeline influenciado
- ROI estimado

Nunca apresentar receita como causada pela IA sem evidência suficiente.

Separar:

**Atribuído à ArtGenial**

de:

**Influenciado pela ArtGenial**

---

# FASE 13 — IA PROATIVA

**Status: PENDENTE**

Esta é a evolução da IA que aprende sobre a operação e passa a sugerir ações.

A IA deverá analisar continuamente:

- clientes
- histórico
- vendas
- comportamento
- produtos
- frequência
- inatividade
- oportunidades
- reclamações
- satisfação
- resultados anteriores

E poderá sugerir:

- entrar em contato
- fazer follow-up
- oferecer outro serviço
- oferecer recompra
- oferecer upsell
- oferecer cross-sell
- oferecer benefício
- conceder brinde permitido
- recuperar cliente
- prevenir cancelamento

Sempre passando pelo **Policy + Approval Engine**.

---

# FASE 14 — VOZ ARTGENIAL

**Status: FUTURO**

Objetivo: adicionar voz como novo canal da mesma inteligência.

Não criar uma IA separada para telefone.

Arquitetura:

**WhatsApp + Voz → mesma identidade → mesma memória → mesmo Intent Engine → mesmos agentes → mesmas políticas.**

Implementar:

- [ ] chamadas inbound
- [ ] chamadas outbound
- [ ] transcrição
- [ ] identificação do cliente
- [ ] memória compartilhada
- [ ] qualificação
- [ ] agendamento
- [ ] follow-up por voz
- [ ] transferência para humano
- [ ] resumo da ligação
- [ ] registro no CRM
- [ ] atualização de pipeline
- [ ] atribuição de resultados

---

# FASE 15 — ERP ARTGENIAL

**Status: FUTURO**

Após CRM + IA estarem maduros.

Módulos previstos:

- [ ] financeiro
- [ ] contas a pagar
- [ ] contas a receber
- [ ] pedidos
- [ ] produtos
- [ ] serviços
- [ ] estoque
- [ ] faturamento
- [ ] fiscal
- [ ] gestão
- [ ] relatórios

A memória e os agentes poderão futuramente utilizar dados autorizados do ERP.

---

# REGRA ARQUITETURAL PRINCIPAL

A ArtGenial não deverá evoluir para um conjunto de IAs independentes.

A arquitetura alvo é:

**Cliente Único**

↓

**Memória Unificada**

↓

**Intent Engine**

↓

**Next Best Action**

↓

**Policy + Approval Engine**

↓

**Orquestrador**

↓

**Agente Especialista**

↓

**Executor de Ações**

↓

**Eventos + Atribuição**

↓

**ROI**

WhatsApp e futuramente Voz são **canais dessa inteligência**, não sistemas independentes.

---

# ORDEM DE EXECUÇÃO ATUAL

Não pular etapas apenas para adicionar funcionalidades visualmente interessantes.

Ordem:

1. [ ] Finalizar Fundação/WhatsApp
2. [ ] Finalizar Provisionamento ArtGenial
3. [ ] Construir Instalação Comercial Portável
4. [ ] Validar instalação limpa partindo do GitHub
5. [ ] Construir Memória Unificada
6. [ ] Construir Intent Engine
7. [ ] Construir Next Best Action
8. [ ] Construir Policy + Approval Engine
9. [ ] Construir Handoff IA → Humano
10. [ ] Construir Orquestrador
11. [ ] Construir Agentes Especializados
12. [ ] Construir Automação Operacional
13. [ ] Construir Eventos e Atribuição
14. [ ] Construir Painel de ROI
15. [ ] Construir IA Proativa
16. [ ] Adicionar Voz
17. [ ] Evoluir posteriormente para ERP

---

# REGRA PARA O CODEX

Antes de iniciar qualquer etapa:

1. Mapear a arquitetura existente relacionada à etapa.
2. Ler integralmente os arquivos que serão modificados.
3. Não substituir funcionalidades existentes sem necessidade.
4. Não alterar infraestrutura ou produção fora do escopo.
5. Não expor secrets.
6. Implementar somente a etapa atual.
7. Criar testes específicos.
8. Executar os testes relacionados.
9. Registrar problemas encontrados.
10. Gerar relatório da implementação.
11. Marcar no roadmap somente itens realmente concluídos.
12. Não marcar uma fase como concluída se houver requisito obrigatório pendente.
13. Parar ao final da etapa para revisão humana antes de avançar.

## Regra de status

Cada etapa deve possuir um dos estados:

- `PENDENTE`
- `EM ANÁLISE`
- `EM IMPLEMENTAÇÃO`
- `BLOQUEADA`
- `EM VALIDAÇÃO`
- `CONCLUÍDA`

O Codex deve atualizar o status conforme o trabalho avança.

**Nenhuma etapa futura deve ser iniciada automaticamente apenas porque a anterior foi concluída.**
