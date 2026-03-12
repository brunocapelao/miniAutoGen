# Plano de Migração do Código Atual

## Objetivo

Transformar a arquitetura alvo em plano de migração do código real com risco controlado.

## Princípio geral

A migração deve evitar os dois extremos mais perigosos:

- reescrever tudo cedo demais;
- manter tudo antigo e empilhar novas camadas em cima sem corte.

## Inventário do estado atual

### `miniautogen/chat/chat.py`

Papel atual:

- núcleo conversacional;
- gestão de agentes;
- persistência delegada ao repositório;
- manutenção de `ChatState`.

Destino arquitetural:

- preservar como facade de alto nível no curto prazo;
- gradualmente deslocar semântica de execução para `RunContext` e `PipelineRunner`;
- manter responsabilidade principal em histórico e registro de participantes.

### `miniautogen/agent/agent.py`

Papel atual:

- identidade do agente;
- vínculo com pipeline;
- geração de resposta.

Destino arquitetural:

- evoluir para facade orientada a `AgentSpec`;
- preservar compatibilidade do construtor inicial;
- reduzir dependência implícita de estado dinâmico não tipado.

### `miniautogen/chat/chatadmin.py`

Papel atual:

- coordenador do ciclo;
- controle de rodadas;
- execução do pipeline administrativo.

Destino arquitetural:

- deixar de ser o local principal da mecânica de execução;
- tornar-se facade ou orchestrator de alto nível sobre `PipelineRunner`;
- manter compatibilidade transitória com o loop atual até o corte.

### `miniautogen/pipeline/pipeline.py`

Papel atual:

- composição sequencial de componentes;
- estado dinâmico por dicionário.

Destino arquitetural:

- preservar como eixo de composição;
- introduzir `PipelineRunner` ao lado de `Pipeline`;
- endurecer contratos de estado e resultado antes de remover o modelo atual.

### `miniautogen/pipeline/components/*`

Papel atual:

- blocos concretos de execução.

Destino arquitetural:

- preservar como principal ponto de extensão;
- adaptar gradualmente para contratos mais fortes;
- evitar quebra ampla em todos os componentes de uma vez.

### `miniautogen/storage/*`

Papel atual:

- abstração inicial de repositório de mensagens.

Destino arquitetural:

- evoluir para family de stores mais explícitos;
- manter repositório atual como compatibilidade enquanto `MessageStore` amadurece.

## Mapeamento classe atual → responsabilidade alvo

| Atual | Papel transitório | Papel alvo |
| --- | --- | --- |
| `Chat` | facade de conversa | facade sobre histórico, contexto e stores |
| `Agent` | facade de participante | spec + executor associado a runner |
| `ChatAdmin` | orchestrator transitório | fachada sobre `PipelineRunner` |
| `Pipeline` | composição declarativa | composição declarativa preservada |
| `ChatPipelineState` | estado dinâmico transitório | `RunContext` e envelopes tipados |
| `ChatRepository` | store inicial de mensagens | `MessageStore` ou family de stores |

## Tabela de substituição de API

| API atual | API ou conceito substituto | Status esperado | Remoção |
| --- | --- | --- | --- |
| `ChatPipelineState` | `RunContext` + envelopes tipados | transição controlada | após compatibilidade comprovada |
| `ChatAdmin.run()` como centro da mecânica | `PipelineRunner` com `ChatAdmin` como facade | transição controlada | após runner estabilizado |
| `ChatRepository` como abstração única | family de stores (`MessageStore`, `RunStore`, `CheckpointStore`) | convivência temporária | após stores de referência |
| estado dinâmico implícito por dicionário | contratos explícitos de contexto e resultado | adoção incremental | sem corte único abrupto |

## Estratégia de migração recomendada

### Etapa 1. Congelar comportamento atual

- criar golden tests do fluxo atual;
- documentar saídas esperadas;
- registrar compatibilidades públicas que precisam sobreviver à transição inicial.

### Etapa 2. Introduzir novos contratos ao lado dos antigos

- adicionar `RunContext`, `RunResult` e `ExecutionEvent`;
- não remover imediatamente `ChatPipelineState`;
- criar funções de adaptação entre o estado atual e os envelopes novos.

### Etapa 3. Introduzir `PipelineRunner`

- executar `Pipeline` existente via runner novo;
- manter `ChatAdmin.run()` delegando internamente ao runner quando pronto;
- preservar assinatura pública inicial sempre que possível.

### Etapa 4. Extrair semântica operacional de `ChatAdmin`

- mover timeout, cancelamento e lifecycle para o runner;
- manter `ChatAdmin` como facade e ponto de entrada compatível;
- marcar APIs antigas como transitórias quando necessário.

### Etapa 5. Formalizar stores

- manter `ChatRepository` como ponte temporária;
- introduzir `MessageStore` e demais stores;
- adicionar adapters entre o contrato antigo e os novos stores.

### Etapa 6. Cortes e depreciações

- remover caminhos paralelos só depois de telemetria, testes e documentação estabilizados;
- cortar APIs antigas com janela explícita de depreciação.

## Compatibilidade temporária

Durante a migração, deve existir uma política explícita de convivência:

- classes atuais podem virar facades;
- contratos novos entram primeiro como complementares;
- comportamento antigo deve ser preservado por wrappers, adapters ou facades;
- a remoção só deve acontecer após medição e validação.

## Política de depreciação sugerida

1. marcar API como transitória ou deprecated em documentação e release notes;
2. manter compatibilidade por pelo menos um ciclo relevante de versão;
3. oferecer caminho de migração explícito;
4. remover apenas quando existir substituto estável.

## Critérios de corte

Um caminho legado só deve ser removido quando:

- houver substituto estável;
- houver cobertura automatizada suficiente;
- a compatibilidade temporária tiver sido exercitada;
- a taxonomia de eventos e erros já cobrir o fluxo novo;
- a documentação estiver alinhada.

## Riscos principais da migração

- duplicação longa demais entre runtime antigo e novo;
- introdução de contratos sem uso real;
- runner novo sem preservação do pipeline atual;
- store novo antes de semântica de persistência fechada;
- depreciação implícita sem comunicação.

## Resultado esperado

Ao final da migração, o projeto deve ter:

- pipeline preservado;
- runtime centralizado;
- facades legadas minimizadas;
- compatibilidade tratada explicitamente;
- semântica mais forte sem ruptura desnecessária.
