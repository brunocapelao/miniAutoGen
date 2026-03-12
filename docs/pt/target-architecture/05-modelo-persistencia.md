# Modelo Conceitual de Persistência

## Objetivo

Definir a semântica de persistência antes da implementação técnica detalhada de stores, evitando abstrações genéricas prematuras.

## Princípio central

Antes de decidir classes concretas de store, é necessário responder:

- o que é persistido;
- com que finalidade;
- em que granularidade;
- com que semântica de atualização;
- como esse dado participa de replay, auditoria e recuperação.

## Entidades persistidas recomendadas

### `MessageRecord`

Finalidade:

- histórico conversacional;
- auditoria de entradas e saídas do fluxo.

Semântica:

- append-only;
- não deve ser reescrita como prática normal;
- correções devem gerar novo registro ou metadado explícito.

### `RunRecord`

Finalidade:

- representar uma execução do framework;
- servir de âncora para correlação operacional.

Semântica:

- criado no início do run;
- atualizado com status terminal;
- relaciona mensagens, checkpoints, eventos e resultados.

### `CheckpointRecord`

Finalidade:

- capturar estado recuperável de execução.

Semântica:

- pertence a um `RunRecord`;
- representa um ponto restaurável;
- deve ser versionado por schema;
- não substitui auditoria completa de eventos.

### `ExecutionEventRecord`

Finalidade:

- auditoria técnica;
- análise operacional;
- suporte futuro a replay ou investigação.

Semântica:

- append-only;
- ordenado temporalmente;
- associado a um run e, quando aplicável, a component, tool ou adapter.

## Unidade transacional recomendada

### Mensagens

- transação por append de mensagem;
- consistência local da escrita é mais importante que batch precoce.

### Run state

- transação por mudança de estado do run;
- início e fechamento devem ser observáveis de forma consistente.

### Checkpoints

- transação por checkpoint completo;
- checkpoint parcial não deve ser considerado válido.

### Eventos

- append com consistência suficiente para investigação operacional;
- podem ser desacoplados de writes de negócio quando houver estratégia clara de tolerância.

## Ordering semantics recomendada

Para evitar ambiguidade operacional, a ordem canônica mínima de persistência deve seguir esta lógica:

1. criar `RunRecord` no início do run;
2. persistir `ExecutionEventRecord` de início do run;
3. persistir `MessageRecord` e `ExecutionEventRecord` de execução conforme os fatos ocorram;
4. persistir `CheckpointRecord` apenas quando o snapshot estiver completo;
5. atualizar o estado terminal do `RunRecord`;
6. persistir evento terminal correspondente.

## Must persist vs best effort

### Must persist

- criação do `RunRecord`;
- estado terminal do `RunRecord`;
- `MessageRecord` quando fizer parte do resultado funcional da execução.

### Best effort

- parte da telemetria operacional detalhada;
- eventos auxiliares não essenciais ao estado terminal;
- traces derivados para observabilidade externa.

## Falha de persistência e impacto no run

Regras recomendadas:

- falha ao criar `RunRecord` deve impedir o início formal do run;
- falha ao persistir estado terminal do run deve ser tratada como erro crítico de consistência;
- falha em evento best effort não deve, por padrão, invalidar um run funcionalmente concluído;
- falha em persistência de mensagem funcional deve falhar o run ou marcá-lo explicitamente como inconsistente.

## Idempotência em cenário de retry

- append de mensagens e eventos deve ter chave lógica ou correlação suficiente para evitar duplicação silenciosa;
- updates de estado terminal do run devem ser idempotentes ou protegidos por semântica de transição;
- checkpoints devem poder detectar repetição do mesmo snapshot lógico.

## Estratégia de checkpoint

Antes de implementar `CheckpointStore`, o projeto deve decidir explicitamente:

- checkpoint é por run, não por mensagem isolada;
- checkpoints podem ser gerados em marcos de pipeline ou componentes estratégicos;
- o estado persistido precisa ser suficiente para restauração útil, não apenas debug superficial;
- checkpoint e replay não são sinônimos.

## Estratégia de replay

Replay pode ter três níveis possíveis:

### 1. Replay de auditoria

Reconstitui a sequência de fatos registrados para investigação.

### 2. Replay de reconstrução

Reconstrói estado interno a partir de mensagens e eventos persistidos.

### 3. Replay executável

Reexecuta trechos da lógica do sistema.

## Recomendação

No curto prazo, o MiniAutoGen deve mirar:

- auditoria confiável;
- reconstrução limitada;
- sem prometer replay executável completo cedo demais.

## Append-only como padrão

As seguintes classes de dado devem ser tratadas preferencialmente como append-only:

- mensagens;
- eventos;
- histórico de transição de estado relevante.

Isso reduz ambiguidade histórica e melhora auditabilidade.

## Multi-tenant e isolamento

Mesmo que multi-tenant não seja implementado no curto prazo, o modelo deve prever:

- identificador de tenant ou namespace;
- separação lógica por run;
- filtros de acesso por escopo.

## Versionamento de schema persistido

Todo payload persistido relevante deve carregar:

- versão de schema;
- origem do produtor;
- timestamp consistente;
- identificador de correlação.

## Relação entre stores recomendados

- `MessageStore`: persistência de mensagens append-only;
- `RunStore`: lifecycle do run;
- `CheckpointStore`: snapshots restauráveis;
- `EventStore`: eventos de domínio e operacionais.

## O que evitar

- store genérico demais sem semântica;
- checkpointing antes da definição de restauração;
- misturar auditoria com cache transitório;
- acoplamento do domínio à estrutura ORM concreta.
