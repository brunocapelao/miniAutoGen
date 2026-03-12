# Módulo `pipeline.py`

Para a visão arquitetural completa, consulte [C4 Nível 2: Containers lógicos](architecture/02-containers.md), [C4 Nível 3: Componentes internos](architecture/03-componentes.md) e [Fluxos de execução](architecture/04-fluxos.md).

## Visão geral

O pipeline é o principal mecanismo de composição do MiniAutoGen. Ele encadeia componentes assíncronos que leem e atualizam um estado compartilhado.

## Elementos centrais

### `Pipeline`

- mantém uma lista ordenada de componentes;
- valida novos componentes em `add_component`;
- executa `process(state)` de cada componente em sequência.

### `PipelineState`

- define o contrato abstrato de leitura e atualização de estado.

### `ChatPipelineState`

- implementação concreta baseada em dicionário mutável;
- carrega dados como `group_chat`, `chat_admin`, `selected_agent`, `prompt` e `reply`.

### `PipelineComponent`

- interface base para qualquer extensão do pipeline;
- exige a implementação de `async def process(self, state)`.

## Papel arquitetural

O pipeline aparece em dois níveis:

- no `ChatAdmin`, para controlar o turno da conversa;
- no `Agent`, para gerar a resposta do agente.

## Exemplo resumido

```python
from miniautogen.pipeline.pipeline import Pipeline, ChatPipelineState

state = ChatPipelineState(group_chat=chat, chat_admin=admin)

pipeline = Pipeline([
    component_a,
    component_b,
])

final_state = await pipeline.run(state)
```
