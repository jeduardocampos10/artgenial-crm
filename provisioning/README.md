# Fundação do Provisionador ArtGenial

Esta pasta contém **somente um contrato de instalação, catálogo, checks futuros, validador local e dry-run**. Nenhum comando aqui instala serviços, executa migrations/seeds, grava banco, cria cliente, chama Coolify ou acessa a internet. O `setup.sh` da raiz continua sendo uma ferramenta de desenvolvimento local; ele não é o provisionador comercial.

## Instalação isolada

Cada cliente terá uma instalação, dados e configuração próprios, operados pela ArtGenial. O cliente recebe apenas o CRM. `installation_key` é um UUID estável e exclusivo fornecido na preparação; não pode ser copiado do exemplo nem derivado do nome editável do cliente. O exemplo é fictício e usa domínios `.example.test`. Não é um arquivo de produção.

O formato escolhido é JSON para permitir validação com a biblioteca padrão do Python, sem instalar parser YAML ou dependências no projeto. `config/installation.contract.json` define os campos, ambientes, domínios públicos e referências de secrets exigidos. `config/services.json` espelha os 14 serviços e suas portas/dependências/volumes relevantes no `docker-compose.yml` atual. `checks/required.json` descreve as verificações obrigatórias futuras. A configuração real deve ser fornecida em runtime, fora do repositório.

## Comandos locais

Na raiz do repositório:

```text
python provisioning/scripts/provision.py validate --config provisioning/config/installation.example.json
python provisioning/scripts/provision.py plan --config provisioning/config/installation.example.json
python -m unittest discover -s provisioning/tests -v
```

`validate` verifica os campos obrigatórios, slug, UUID canônico, ambiente, seis domínios distintos, administrador sem senha, conjunto completo de serviços e referências `runtime:NOME_DA_VARIAVEL`. Para `production`, rejeita domínios HTTP, localhost, domínios de exemplo/teste, identidade e UUID do exemplo e outros placeholders óbvios. Esse filtro não substitui revisão humana nem comprova que os domínios pertencem ao cliente. JSON com chaves duplicadas também é rejeitado.

`plan` primeiro valida e depois imprime as cinco fases, em ordem fixa: **PREPARAÇÃO → INFRAESTRUTURA → INICIALIZAÇÃO → VALIDAÇÃO → ENTREGA**. Exibe domínios e nomes de serviço, sem valores ou referências de secrets. Não faz consultas HTTP nem escrita. `VITE_WS_URL` é modelada no mesmo domínio público do CRM API, com protocolo `wss`/`ws` e caminho `/cable`; portanto, não requer um sétimo domínio. Se a topologia real usar outro host WebSocket, o contrato deverá ser versionado antes de aplicar.

## Fluxo futuro e barreiras de entrega

1. **Preparação:** registrar identidade, UUID, domínios, referências a secrets exclusivos e administrador inicial. Senha do administrador e secrets entram apenas no runtime seguro; nunca no JSON, Git, log ou saída do dry-run.
2. **Infraestrutura:** criar a instalação isolada, serviços, volumes, rede interna, domínios públicos e variáveis no Coolify. O catálogo atual reproduz o Compose de desenvolvimento, incluindo MailHog. Uma implantação comercial precisa decidir o provedor de e-mail antes de ativar esse serviço em produção.
3. **Inicialização:** executar migrations apenas na nova instalação; verificar e inicializar **idempotentemente** `RuntimeConfig.account` no Auth; criar o administrador inicial; chamar o Applier ArtGenial existente para `artgenial.base` v1 usando `installation_key`. A Base 6/62/29 não é duplicada aqui. Não chamar `SetupBootstrapService` cegamente em instalações existentes.
4. **Validação:** provar disponibilidade externa do frontend e dos cinco serviços API, seus health checks, `GET /api/v1/account` autenticado com payload válido, vínculo das seis variáveis `VITE_*` e upgrade WebSocket. Um container healthy não comprova publicação do domínio. O incidente real de Core/Flow sem endpoint público e o 404 `Account not configured` são falhas que bloqueiam entrega.
5. **Entrega:** liberar acesso ao cliente **somente** depois que todos os checks obrigatórios tiverem passado. Nenhum check é executado nesta fase.

## Integrações posteriores

A integração com Coolify precisará de uma credencial operacional segura, mapeamento de serviços/portas/domínios, isolamento por instalação, gestão de secrets, observação de estado e tratamento de falhas. A inicialização Auth/account precisará de uma API ou comando interno autorizado, com leitura do estado existente, criação somente se ausente, idempotência e validação da resposta. A criação do administrador exigirá uma interface Auth autorizada que receba a credencial apenas em runtime. O Applier do backend CRM deve ser invocado após migrations, com ator explícito e UUID da instalação, sem copiar manifesto ou lógica de aplicação.

Uma futura integração com `artadmin.artgenial.com.br` poderá orquestrar esse fluxo e guardar estado/auditoria. Esta fundação não oferece endpoint, tarefa remota nem credencial de ArtAdmin.
