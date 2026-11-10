# Validação da jornada de atendimento v1 — homologação

## Escopo autorizado

Aprovação do responsável para concluir a fundação, publicar branches e validar exclusivamente em homologação. Produção, `main`, autonomia operacional e ativação automática continuam fora do escopo.

## Estado da implementação

| Repositório | Branch | Commit local |
|---|---|---|
| raiz ArtGenial CRM | `feat/whatsapp-human-support-foundation` | `7bcdded` |
| Core | `artgenial/feat-human-service-skill` | `3d38a00` |
| Frontend | `artgenial/feat-human-service-skill` | `fdbe082` |
| Processor | `artgenial/feat-human-service-skill` | `86d0143` |

## Controles de segurança confirmados

- registro fechado e versionado de oito skills;
- configuração não aceita texto livre como prompt de skill;
- pacote completo não registra tools nem concede autoridade;
- suporte, reclamação, cobrança, cancelamento, privacidade, segurança e pedido de humano prevalecem sobre conversão;
- venda, cross-sell e upsell ficam bloqueados enquanto houver resolução pendente;
- cancelamento não é tratado como objeção e não admite dark patterns;
- handoff aceita somente destinos previamente configurados;
- resposta de handoff não expõe corpo de erro upstream ao modelo;
- todos os toggles novos ficam desabilitados por padrão no Frontend e no Processor;
- produção e `main` não foram alterados.

## Validações executadas

### Processor

Comando:

```bash
python -m unittest -v \
  tests.unit.test_human_service_skill \
  tests.unit.test_customer_journey_eval_catalog \
  tests.unit.test_handoff_skill \
  tests.unit.test_transfer_to_human_safe
```

Resultado: **32 testes aprovados, 0 falhas**.

Também aprovados:

- `python -m compileall -q src tests`;
- parsing dos JSONs de skills/evals;
- `git diff --check`.

### Frontend

Validações estáticas aprovadas:

- parsing dos seis arquivos JSON de tradução;
- persistência dos toggles nos quatro fluxos de salvamento;
- valores padrão revisados para `false`;
- `git diff --check`.

A suíte Vitest/TypeScript não foi executada porque Node/npm não estão disponíveis no runtime atual. Foi criado teste específico para o painel e os defaults, mas ele ainda precisa rodar no CI ou em ambiente com Node.

### Core

Validações estáticas aprovadas:

- os dez campos de configuração estão na allowlist;
- teste Go cobre preservação dos toggles e IDs versionados;
- `git diff --check`.

A suíte Go e `gofmt` não foram executados porque Go não está disponível no runtime atual. Precisam rodar no CI ou em ambiente com Go 1.24.4.

## Bloqueio de publicação e deploy

As quatro tentativas de `git push` foram bloqueadas porque o runtime não possui credencial HTTPS nem chave SSH para GitHub. Portanto:

- os commits estão íntegros apenas no clone local;
- não foi possível abrir PRs para `develop`;
- não foi possível acionar CI;
- não foi possível implantar a revisão em homologação de maneira rastreável;
- nenhum deploy foi realizado.

O próximo passo seguro é disponibilizar autenticação GitHub ao runtime ou publicar manualmente os quatro commits/branches. Depois disso, executar CI de Frontend/Core, abrir PRs para `develop`, integrar primeiro os subprojetos e por último atualizar os ponteiros no repositório raiz. Só então executar deploy e smoke test na homologação.

## Critério para encerrar a homologação

A fundação só pode ser marcada como homologada após:

1. branches publicadas e PRs revisáveis para `develop`;
2. Vitest/TypeScript e testes Go verdes;
3. CI do repositório raiz verde;
4. deploy apenas no ambiente de homologação;
5. smoke test confirmando toggles desligados por padrão;
6. ativação controlada em agente sintético de homologação;
7. execução do catálogo adversarial com respostas reais do modelo;
8. ausência de regressão de handoff e confirmação humana do aceite.
