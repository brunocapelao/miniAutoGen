# Módulo `components.py`

Para a visão arquitetural completa, consulte [C4 Nível 3: Componentes internos](architecture/03-componentes.md).

## Visão geral

`components.py` reúne implementações prontas de `PipelineComponent` para os fluxos mais comuns do MiniAutoGen.

## Componentes disponíveis

### `UserResponseComponent`

- lê entrada humana pelo terminal;
- grava o texto capturado como `reply` no estado.

### `NextAgentSelectorComponent`

- consulta o histórico recente do chat;
- aplica uma rotação simples de agentes baseada no último remetente;
- grava o agente selecionado em `selected_agent`.

### `AgentReplyComponent`

- recupera o agente selecionado do estado;
- executa `agent.generate_reply(state)`;
- persiste a resposta no `Chat`.

### `TerminateChatComponent`

- inspeciona a última mensagem;
- chama `chat_admin.stop()` quando encontra `TERMINATE`.

### `LLMResponseComponent`

- lê `prompt` do estado;
- chama o cliente LLM configurado;
- grava a saída textual em `reply`.

### `Jinja2SingleTemplateComponent`

- constrói o prompt a partir do histórico e de variáveis adicionais;
- renderiza o template com Jinja2;
- salva o resultado em `prompt`.

## Papel arquitetural

Os componentes são o ponto de extensão mais importante da solução. Em vez de codificar o fluxo dentro de classes monolíticas, o MiniAutoGen distribui comportamento em componentes pequenos e encadeáveis.
