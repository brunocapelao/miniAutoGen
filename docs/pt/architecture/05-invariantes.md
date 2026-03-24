# Invariantes e taxonomias

## Visão geral

Este documento é a referência normativa para as invariantes estruturais e as taxonomias canônicas do MiniAutoGen. Invariantes são regras invioláveis que os contratos Pydantic e os runtimes devem respeitar em qualquer estado do sistema. Taxonomias são vocabulários fechados que classificam erros e eventos de forma uniforme.

---

## Invariantes por entidade

### Message

Modelo: `miniautogen/core/contracts/message.py`

- `sender_id` é obrigatório e não vazio. Identifica univocamente o agente emissor.
- `content` é obrigatório. Representa o conteúdo textual da mensagem.
- `timestamp` possui valor padrão via `datetime.now`. Toda Message possui marca temporal.
- `additional_info` é um dicionário de metadados extensíveis. Não pode conter estruturas específicas de provedor (OpenAI, Gemini, etc.).
- Message é serializável para JSON via Pydantic. Nenhuma dependência de vendor pode existir na sua definição.

### RunContext

Modelo: `miniautogen/core/contracts/run_context.py`

- `run_id` é obrigatório. Identifica univocamente a execução.
- `correlation_id` é obrigatório. Permite rastreio entre componentes e eventos.
- `started_at` é obrigatório. Registra o início da execução.
- `execution_state` é um dicionário mutável durante a execução. Utilizado para estado transitório entre componentes.
- `input_payload` transporta a entrada da execução. Pode ser `None`.
- `timeout_seconds` define o tempo máximo de execução. Quando presente, o runtime deve respeitar este limite.
- `with_previous_result()` retorna um novo RunContext com o resultado anterior injetado em `input_payload` e registado em `metadata["previous_result"]`. Não altera a instância original.

### RunResult

Modelo: `miniautogen/core/contracts/run_result.py`

- `run_id` é obrigatório. Corresponde ao `run_id` do RunContext que originou a execução.
- `status` é um enum `RunStatus` com quatro valores terminais: `finished`, `failed`, `cancelled`, `timed_out`. Todo RunResult deve expressar um destes estados.
- `output` contém o resultado da execução em caso de sucesso. Pode ser `None`.
- `error` contém a descrição do erro em caso de falha. Pode ser `None`.
- `metadata` é extensível e não deve conter informações essenciais para a lógica de negócio.

### ExecutionEvent

Modelo: `miniautogen/core/contracts/events.py`

- `type` é obrigatório. Deve corresponder a um dos 72 valores do enum `EventType`.
- `timestamp` possui valor padrão em UTC. Todos os eventos possuem marca temporal.
- `run_id` pode ser inferido do `payload` via `model_validator`. Se o payload contém `run_id`, este é promovido para o campo de topo.
- `correlation_id` permite agrupar eventos de uma mesma execução ou sub-execução.
- `scope` identifica o contexto emissor (runtime, policy, adapter).
- `payload` é um dicionário livre. O seu schema depende do `type` do evento.
- Suporta alias de compatibilidade: `event_type` para `type`, `created_at` para `timestamp`.

### Conversation

Modelo: `miniautogen/core/contracts/conversation.py`

- Segue o padrão de imutabilidade lógica. `add_message()` retorna uma nova instância de Conversation.
- `messages` é uma lista de Message. A lista original não é alterada em `add_message()`.
- `last_n(n)` e `by_sender(sender_id)` são consultas de leitura sem efeitos colaterais.
- `id` identifica a conversação. Pode ser vazio por padrão.

### Checkpoint

- Um checkpoint deve estar associado a um `run_id` específico.
- O schema do checkpoint deve ser versionável para permitir migração entre versões do framework.
- Todo checkpoint deve ser restaurável: os dados persistidos devem ser suficientes para retomar a execução.
- A operação de restauração é registada via evento `CHECKPOINT_RESTORED`.

### Agent Runtime [IMPLEMENTADO]

> **Status:** Implementado. O Agent Runtime (AgentHook, MemoryProvider) está implementado. As invariantes abaixo aplicam-se à implementação atual.

Invariantes aplicáveis ao Agent Runtime e aos seus componentes (ver [`07-agent-anatomy.md`](07-agent-anatomy.md)):

- **Hooks DEVEM ser async.** Todos os hooks do `AgentHook` protocol (`before_turn`, `after_turn`, `on_error`) são coroutines AnyIO. Hooks síncronos são considerados defeitos de implementação. Isto garante que o runtime nunca bloqueia o event loop, mesmo em operações de I/O nos hooks.
- **Engine isolation.** O Agent Runtime NUNCA vaza tipos específicos do Engine para o `core/`. Toda comunicação entre o runtime local e o engine ocorre via protocolos tipados (`LLMProviderProtocol`, `AgentDriver`). Tipos internos do provedor (OpenAI message formats, Gemini response objects, etc.) são transformados por adapters na fronteira.
- **MemoryProvider é injetável e opcional.** O agente opera normalmente sem `MemoryProvider`. Quando presente, o provider injeta contexto antes de cada turno mas não altera o fluxo principal de execução.

### RuntimeInterceptor [IMPLEMENTADO]

> **Status:** Implementado. O protocolo RuntimeInterceptor está implementado via `InterceptorPipeline`. As invariantes abaixo aplicam-se à implementação atual.

Invariantes aplicáveis ao protocolo `RuntimeInterceptor`:

- **Interceptors DEVEM ser composíveis.** Cada interceptor opera de forma independente, sem estado global partilhado. A composição é feita por registo sequencial, e a ordem de registo determina a ordem de execução.
- **Interceptors não reescrevem a semântica do domínio.** Tal como as policies, interceptors observam e transformam -- não substituem a lógica de coordenação. Um interceptor pode modificar inputs/outputs e decidir bail, mas não pode alterar o modo de coordenação.
- **Bail é determinístico.** Quando `should_execute` retorna `False`, o passo é incondicionalmente ignorado. Não há mecanismo de override posterior.

---

## Taxonomia canônica de erros

O MiniAutoGen define oito categorias canônicas de erro. Toda exceção ou falha no sistema deve ser classificada numa destas categorias. Erros fora desta taxonomia são considerados defeitos de implementação.

| Categoria | Descrição | Recuperável |
|-----------|-----------|-------------|
| `transient` | Falha potencialmente recuperável. Elegível para retry automático. | Sim |
| `permanent` | Falha que não melhora com repetição. Requer intervenção. | Não |
| `validation` | Violação de contrato, schema ou regra semântica. | Não |
| `timeout` | Tempo excedido num escopo conhecido. | Condicional |
| `cancellation` | Interrupção deliberada de execução ou sub-escopo. | N/A |
| `adapter` | Falha na fronteira de integração externa (LLM, store, backend). | Condicional |
| `configuration` | Configuração ausente, inválida ou inconsistente. | Não |
| `state_consistency` | Violação de invariante ou estado impossível detectado. | Não |

Notas:

- Erros `transient` são os únicos candidatos a retry automático via `RetryPolicy`.
- Erros `timeout` podem ser recuperáveis se o escopo permitir re-execução.
- Erros `adapter` podem ser transient ou permanent dependendo da natureza da falha externa.
- Erros `state_consistency` indicam um bug no framework e devem ser tratados como críticos.

---

## Taxonomia canônica de eventos

O enum `EventType` em `core/events/types.py` define 72 tipos de evento organizados em 13 categorias.

### Ciclo de vida do run (5)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `RUN_STARTED` | `run_started` | Início de uma execução |
| `RUN_FINISHED` | `run_finished` | Execução concluída com sucesso |
| `RUN_FAILED` | `run_failed` | Execução terminada com erro |
| `RUN_CANCELLED` | `run_cancelled` | Execução cancelada deliberadamente |
| `RUN_TIMED_OUT` | `run_timed_out` | Execução excedeu o tempo limite |

### Componentes (4)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `COMPONENT_STARTED` | `component_started` | Início de execução de um componente |
| `COMPONENT_FINISHED` | `component_finished` | Componente concluído |
| `COMPONENT_SKIPPED` | `component_skipped` | Componente ignorado por condição |
| `COMPONENT_RETRIED` | `component_retried` | Componente re-executado após falha |

### Ferramentas (3)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `TOOL_INVOKED` | `tool_invoked` | Ferramenta invocada |
| `TOOL_SUCCEEDED` | `tool_succeeded` | Ferramenta executada com sucesso |
| `TOOL_FAILED` | `tool_failed` | Ferramenta falhou |

### Armazenamento (2)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `CHECKPOINT_SAVED` | `checkpoint_saved` | Checkpoint persistido |
| `CHECKPOINT_RESTORED` | `checkpoint_restored` | Checkpoint restaurado |

### Políticas (3)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `POLICY_APPLIED` | `policy_applied` | Política transversal aplicada |
| `VALIDATION_FAILED` | `validation_failed` | Validação de política falhou |
| `BUDGET_EXCEEDED` | `budget_exceeded` | Orçamento de execução excedido |

### Adaptadores (1)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `ADAPTER_FAILED` | `adapter_failed` | Falha no adaptador externo |

### Loop agêntico (5)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `AGENTIC_LOOP_STARTED` | `agentic_loop_started` | Início do loop agêntico |
| `ROUTER_DECISION` | `router_decision` | Router selecionou próximo agente |
| `AGENT_REPLIED` | `agent_replied` | Agente emitiu resposta |
| `AGENTIC_LOOP_STOPPED` | `agentic_loop_stopped` | Loop agêntico encerrado |
| `STAGNATION_DETECTED` | `stagnation_detected` | Estagnação detectada na conversa |

### Deliberação (4)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `DELIBERATION_STARTED` | `deliberation_started` | Início de deliberação |
| `DELIBERATION_ROUND_COMPLETED` | `deliberation_round_completed` | Ronda de deliberação concluída |
| `DELIBERATION_FINISHED` | `deliberation_finished` | Deliberação finalizada |
| `DELIBERATION_FAILED` | `deliberation_failed` | Deliberação falhou |

### Backend drivers (11)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `BACKEND_SESSION_STARTED` | `backend_session_started` | Sessão de backend iniciada |
| `BACKEND_TURN_STARTED` | `backend_turn_started` | Turno de backend iniciado |
| `BACKEND_MESSAGE_DELTA` | `backend_message_delta` | Fragmento de mensagem recebido |
| `BACKEND_MESSAGE_COMPLETED` | `backend_message_completed` | Mensagem de backend completa |
| `BACKEND_TOOL_CALL_REQUESTED` | `backend_tool_call_requested` | Backend solicitou chamada de ferramenta |
| `BACKEND_TOOL_CALL_EXECUTED` | `backend_tool_call_executed` | Chamada de ferramenta executada |
| `BACKEND_ARTIFACT_EMITTED` | `backend_artifact_emitted` | Artefato emitido pelo backend |
| `BACKEND_WARNING` | `backend_warning` | Aviso do backend |
| `BACKEND_ERROR` | `backend_error` | Erro do backend |
| `BACKEND_TURN_COMPLETED` | `backend_turn_completed` | Turno de backend concluído |
| `BACKEND_SESSION_CLOSED` | `backend_session_closed` | Sessão de backend encerrada |

### Aprovação (4)

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `APPROVAL_REQUESTED` | `approval_requested` | Aprovação solicitada |
| `APPROVAL_GRANTED` | `approval_granted` | Aprovação concedida |
| `APPROVAL_DENIED` | `approval_denied` | Aprovação negada |
| `APPROVAL_TIMEOUT` | `approval_timeout` | Aprovação expirou por timeout |

### Agent Runtime (4)

Eventos do ciclo de vida do Agent Runtime, associados à anatomia do agente (ver [`07-agent-anatomy.md`](07-agent-anatomy.md)):

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `AGENT_TURN_STARTED` | `agent_turn_started` | Início de um turno de agente no runtime local |
| `AGENT_TURN_COMPLETED` | `agent_turn_completed` | Turno de agente concluído |
| `AGENT_HOOK_EXECUTED` | `agent_hook_executed` | Hook do AgentHook protocol executado (before_turn, after_turn) |
| `AGENT_TOOL_INVOKED` | `agent_tool_invoked` | Ferramenta invocada pelo agente via tool registry local |

### Interceptors (3)

Eventos emitidos durante a execução de `RuntimeInterceptor`s:

| Evento | Valor | Descrição |
|--------|-------|-----------|
| `INTERCEPTOR_BEFORE_STEP` | `interceptor_before_step` | Interceptor executou hook before_step |
| `INTERCEPTOR_AFTER_STEP` | `interceptor_after_step` | Interceptor executou hook after_step |
| `INTERCEPTOR_BAIL` | `interceptor_bail` | Interceptor retornou bail em should_execute, passo ignorado |

---

## Classificação de modelos

Os modelos Pydantic do MiniAutoGen classificam-se em três categorias funcionais conforme o seu papel no sistema.

### Entity (entidade de domínio)

Possuem identidade de domínio e são persistíveis. Representam conceitos fundamentais do sistema.

| Modelo | Justificação |
|--------|-------------|
| `Message` | Identidade própria (`id`, `sender_id`). Persistida em MessageStore. Representa uma unidade de comunicação entre agentes. |
| `Conversation` | Agregado de Messages com identidade (`id`). Persistível como histórico de interação. |

### Envelope (envelope de transporte)

Transportam dados entre partes do runtime. Não possuem identidade de domínio própria -- derivam-na do contexto de execução.

| Modelo | Justificação |
|--------|-------------|
| `RunContext` | Transporta estado de execução entre componentes. O `run_id` é atribuído pelo runtime, não pelo modelo. |
| `RunResult` | Encapsula o resultado terminal de uma execução. Referencia o `run_id` do RunContext de origem. |
| `ExecutionEvent` | Transporta factos observáveis entre o runtime e os sinks de eventos. |
| `CoordinationPlan` | Transporta a especificação de execução para um modo de coordenação. |

### DTO (Data Transfer Object)

Payloads de fronteira que existem para comunicação com sistemas externos. Nunca devem penetrar no domínio interno (`core/`).

| Exemplo | Justificação |
|---------|-------------|
| Payloads de provedores LLM | Estruturas específicas de OpenAI, Gemini, LiteLLM. Transformados por adapters antes de entrar no core. |
| Requests/responses de ferramentas | Payloads de invocação de ferramentas externas. Convertidos em `ToolResult` na fronteira. |
| Respostas HTTP de backends | Payloads JSON de endpoints externos. Convertidos em eventos canônicos pelos drivers. |

---

## Regras de mutabilidade

### Entidades persistentes

Entidades de domínio favorecem imutabilidade lógica. `Conversation.add_message()` retorna uma nova instância em vez de alterar a existente. Esta abordagem elimina efeitos colaterais em cenários de concorrência e simplifica rastreio de estado.

### Envelopes de runtime

Envelopes possuem mutabilidade controlada. `RunContext.execution_state` é um dicionário mutável por design -- componentes escrevem estado transitório durante a execução. `ExecutionEvent` infere `run_id` a partir do payload via `model_validator`, alterando o próprio estado durante a construção, mas permanecendo imutável após validação.

### DTOs de fronteira

DTOs são transformacionais. Existem apenas na fronteira entre o sistema e o exterior. Adapters e drivers convertem DTOs em contratos internos (Message, ExecutionEvent, ToolResult). DTOs nunca devem ser referenciados por módulos em `core/` ou `policies/`.
