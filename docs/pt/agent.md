# Módulo `agent.py`

Para a visão arquitetural completa, consulte [C4 Nível 3: Componentes internos](architecture/03-componentes.md).

## Visão geral

`Agent` representa um participante da conversa. No estado atual do código, sua principal responsabilidade é encapsular identidade, papel e o pipeline que será usado para produzir respostas.

## Responsabilidades

- armazenar `agent_id`, `name` e `role`;
- manter um `pipeline` opcional;
- expor `generate_reply` como ponto de execução do pipeline do agente;
- permitir criação a partir de JSON com `from_json`.

## Comportamento atual

Quando possui pipeline, o agente:

1. executa `pipeline.run(state)`;
2. espera que o estado final contenha a chave `reply`;
3. devolve esse valor como resposta.

Quando o pipeline não existe, o agente retorna uma resposta padrão informando que está ativo, mas sem pipeline configurado.

## Dependências principais

- `Pipeline`
- `ChatPipelineState`

## Uso típico

```python
from miniautogen.agent.agent import Agent

agent = Agent(
    agent_id="assistant",
    name="Assistant",
    role="Helpful assistant",
    pipeline=agent_pipeline,
)
```
