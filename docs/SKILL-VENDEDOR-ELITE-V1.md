# Skill Vendedor Elite ArtGenial v1

## Estado

**Fundação implementada em branch de trabalho, desabilitada por padrão e ainda não autorizada para deploy.**

Identificador fechado: `artgenial.elite-sales.v1`

Configuração do agente:

```json
{
  "elite_sales_skill_enabled": true
}
```

A ativação compila a skill versionada no prompt do agente. Ela não registra ferramentas novas e não aumenta a autoridade operacional do agente.

## Objetivo da primeira versão

Conduzir conversas comerciais consultivas de baixo risco, com supervisão humana para decisões comerciais vinculantes. O agente pode diagnosticar, qualificar, apresentar capacidades aprovadas, investigar objeções e sugerir o próximo passo. Ele não pode inventar nem conceder preço, desconto, condição, proposta, prazo, contrato, disponibilidade ou exceção.

## Fluxo comercial

A skill orienta o agente a inferir, sem expor ao cliente, um dos seguintes estados:

1. `opening`
2. `discovery`
3. `qualification`
4. `decision_criteria`
5. `personalized_presentation`
6. `validation`
7. `objection_discovery`
8. `negotiation`
9. `next_step`
10. `follow_up`
11. `human_handoff`
12. `won`
13. `lost`
14. `nurture`

Os estados são orientação de decisão, não um roteiro obrigatório. A conversa pode pular estados, voltar para diagnóstico ou terminar sem venda.

## Técnicas incorporadas

- diagnóstico antes da apresentação;
- descoberta dos dois ou três critérios de decisão;
- apresentação seletiva, sem catálogo de funcionalidades;
- validação por etapas;
- uso responsável do silêncio e de respostas mornas;
- objeção investigada antes de ser respondida;
- experiência negativa transformada em novos critérios verificáveis;
- custo da espera baseado apenas em impactos confirmados;
- preço separado entre orçamento, valor percebido, condição e outras barreiras;
- isolamento da objeção antes de qualquer negociação;
- follow-up contextual;
- fechamento pelo próximo passo proporcional à prontidão do cliente;
- desqualificação respeitosa quando não existe aderência.

## Memória comercial definida no contrato da skill

A skill instrui o agente a acompanhar somente fatos relevantes e sustentados pela conversa:

- `current_stage`
- `customer_problem`
- `problem_cause`
- `reported_impact`
- `desired_outcome`
- `decision_criteria`
- `fit`
- `priority`
- `constraints`
- `objection_label`
- `objection_root_cause`
- `decision_participants`
- `approved_evidence_used`
- `agreed_next_step`
- `next_step_timing`
- `human_handoff_required`

### Limitação atual

Essa memória ainda é contexto lógico do modelo, não um registro comercial durável e auditável. Não há nesta etapa uma ferramenta para gravar esses campos no CRM. Persistência deve ser implementada em incremento separado, com esquema validado, origem de cada fato, limites de PII, autorização e trilha de auditoria. Até lá, não se deve alegar continuidade garantida entre sessões ou após reinício.

## Guardrails

A skill proíbe:

- preço, desconto, condição, prazo ou escassez inventados;
- garantia de resultado;
- caso, métrica, ROI, integração ou capacidade não comprovados;
- falsa urgência, medo, culpa ou exploração de vulnerabilidade;
- personificação humana;
- alegação de ação, proposta, agendamento, aprovação ou handoff sem confirmação de ferramenta;
- uso da skill como autorização implícita para ferramentas de CRM;
- insistência depois de recusa ou opt-out.

Exige atendimento humano para:

- pedido explícito;
- baixa confiança material;
- exceção de preço ou política;
- concessão não autorizada;
- contrato ou questão jurídica;
- julgamento financeiro sensível;
- reclamação grave ou frustração crescente;
- compromisso vinculante fora da autoridade configurada.

## Integração implementada

### Processor

- registro fechado da skill;
- ativação por `elite_sales_skill_enabled`;
- composição com `artgenial.human-service.v1` sem duplicação;
- testes do conteúdo mínimo de segurança e do registro.

### Core

- preservação de `elite_sales_skill_enabled` durante o processamento da configuração;
- teste de preservação das duas skills versionadas.

### Frontend

- controle “Vendedor Elite ArtGenial” no painel de comportamento;
- desabilitado por padrão;
- carregamento e persistência da configuração em todos os fluxos de salvamento do agente;
- traduções em `pt-BR`, `pt`, `en`, `es`, `fr` e `it`;
- teste do controle e callback.

## Validação desta etapa

Disponível no ambiente atual:

```bash
python -m unittest -v \
  tests.unit.test_human_service_skill \
  tests.unit.test_handoff_skill \
  tests.unit.test_transfer_to_human_safe
```

Também devem ser executados `compileall`, validação JSON e `git diff --check`.

Não disponíveis neste ambiente: Node/npm para Vitest/TypeScript e Go/gofmt para os testes do Core. Esses testes continuam obrigatórios antes de homologação.

## Próximos incrementos antes de qualquer autonomia

1. Criar suíte de avaliações comerciais com diálogos bons, ruins e adversariais.
2. Implementar modo copiloto real, com sugestão privada e aprovação do vendedor, separado da resposta pública do agente.
3. Criar memória comercial durável com proveniência e auditoria.
4. Criar catálogo aprovado de produtos, preços, evidências e políticas.
5. Implementar matriz de autoridade e aprovação para concessões.
6. Medir diagnóstico, qualidade do próximo passo, desconto, margem, handoff e opt-out.
7. Validar em homologação com conversas sintéticas antes de qualquer piloto real.

## Regra de implantação

A existência do toggle não autoriza ativação em produção. A prioridade operacional e o Gate WhatsApp do roadmap permanecem válidos. Esta fundação pode ser revisada e testada isoladamente, mas não deve ampliar autonomia, executar ações comerciais ou ser apresentada como skill comercial concluída sem as validações e controles acima.
