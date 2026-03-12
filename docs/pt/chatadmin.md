# Módulo `chatadmin.py`

Para a visão arquitetural completa, consulte [C4 Nível 2: Containers lógicos](architecture/02-containers.md), [C4 Nível 3: Componentes internos](architecture/03-componentes.md) e [Fluxos de execução](architecture/04-fluxos.md).

## Visão geral

`ChatAdmin` é o coordenador do ciclo de execução. Embora herde de `Agent`, sua função prática é administrar rodadas, iniciar e encerrar a execução e acionar o pipeline administrativo.

## Responsabilidades

- iniciar o loop de execução com `run`;
- montar o `ChatPipelineState` com `group_chat` e `chat_admin`;
- executar rodadas até atingir `max_rounds` ou ser interrompido;
- controlar o estado `running`.

## Estado relevante

- `group_chat`: referência ao objeto `Chat`;
- `goal`: objetivo textual do chat;
- `round`: rodada atual;
- `max_rounds`: limite de iterações;
- `running`: indica se a execução deve continuar.

## Fluxo atual

1. `run()` chama `start()`;
2. cria um `ChatPipelineState`;
3. executa `execute_round(state)` enquanto houver rodadas disponíveis;
4. `execute_round` delega a lógica ao pipeline administrativo;
5. o ciclo termina por limite de rodadas ou por `stop()`.

## Pipeline administrativo típico

```python
Pipeline([
    NextAgentSelectorComponent(),
    AgentReplyComponent(),
    TerminateChatComponent(),
])
```
