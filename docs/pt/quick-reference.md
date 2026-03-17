# Referência rápida dos módulos

Este documento descreve os módulos ativos do MiniAutoGen e as suas responsabilidades. Serve como mapa de navegação para desenvolvedores que precisam localizar rapidamente onde cada funcionalidade reside.

---

## Núcleo

### `core/contracts/`

Contratos tipados (Pydantic models e Protocol definitions) que definem a interface pública do framework:

- **Tipos base:** `Message`, `RunContext`, `RunResult`, `ExecutionEvent`, `Conversation`
- **Protocolos de agente:** `WorkflowAgent`, `DeliberationAgent`, `ConversationalAgent`
- **Planos de coordenação:** `WorkflowPlan`, `WorkflowStep`, `DeliberationPlan`, `AgenticLoopPlan`, `CoordinationPlan`
- **Coordenação:** `CoordinationKind`, `SubrunRequest`, `CompositionStep`
- **Agentic loop:** `RouterDecision`, `ConversationPolicy`, `AgenticLoopState`
- **Deliberação:** `Contribution`, `Review`
- **Especificações:** `AgentSpec`, `EngineProfile`, `MemoryProfile`, `SkillSpec`, `ToolSpec`, `McpServerBinding`
- **Protocolos de integração:** `StoreProtocol`, `ToolProtocol`, `ToolResult`

### `core/runtime/`

Runtime oficial da biblioteca. O `PipelineRunner` centraliza execução, timeout, run lifecycle, checkpoint e publicação de eventos.

Runtimes de coordenação:

- `WorkflowRuntime` -- execução sequencial de steps
- `DeliberationRuntime` -- ciclos de contribuição e revisão entre agentes
- `AgenticLoopRuntime` -- loop conversacional com roteamento dinâmico
- `CompositeRuntime` -- composição de subruns heterogêneos

Helpers deliberativos: `summarize_peer_reviews`, `build_follow_up_tasks`, `apply_leader_review`, `render_final_document_markdown`, `detect_stagnation`, `should_stop_loop`.

### `core/events/`

Taxonomia de 42 tipos de evento (`EventType` enum) organizados em grupos: run lifecycle, component lifecycle, tool execution, checkpoint, policy, agentic loop, deliberation, backend driver e approval. Sinks disponíveis: `CompositeEventSink`, `FilteredEventSink`, `InMemoryEventSink`. Filtros: `EventFilter`, `TypeFilter`, `RunFilter`, `CompositeFilter`.

---

## Composição

### `pipeline/`

Mecanismo de composição por pipeline sequencial.

- `Pipeline` -- orquestrador de componentes
- `PipelineComponent` -- classe base para componentes executáveis
- `DynamicChatPipeline` -- pipeline com roteamento dinâmico de chat
- Componentes prontos em `pipeline/components/components.py`

---

## Policies

### `policies/`

Oito policies transversais que operam lateralmente ao fluxo principal:

- `BudgetTracker` / `BudgetExceededError` -- controlo de custos e tokens
- `ApprovalPolicy` -- aprovação humana no loop
- `RetryPolicy` -- retentativas com backoff configurável
- `TimeoutPolicy` -- limites de tempo por componente
- `ValidationPolicy` -- validação de inputs e outputs
- `PermissionPolicy` -- controlo de permissões de agentes
- `ExecutionPolicy` -- regras compostas de execução
- `PolicyChain` -- encadeamento de múltiplas policies

---

## Persistência

### `stores/`

Três stores especializados por responsabilidade, cada um com duas implementações:

| Store | InMemory | SQLAlchemy |
|-------|----------|------------|
| `MessageStore` | `in_memory.py` | `sqlalchemy.py` |
| `RunStore` | `in_memory_run_store.py` | `sqlalchemy_run_store.py` |
| `CheckpointStore` | `in_memory_checkpoint_store.py` | `sqlalchemy_checkpoint_store.py` |

---

## Adapters

### `adapters/llm/`

Três providers LLM desacoplados do core:

- `OpenAIProvider` -- cliente direto para a API OpenAI
- `LiteLLMProvider` -- proxy multi-provider via LiteLLM
- `OpenAICompatibleProvider` -- cliente HTTP genérico para endpoints compatíveis com OpenAI

Protocolo base: `LLMProvider` (em `protocol.py`).

### `adapters/templates/`

- `JinjaRenderer` -- renderização de templates Jinja2 para prompts

---

## Backend drivers

### `backends/`

Camada unificada de drivers para agentes externos.

| Módulo | Responsabilidade |
|--------|-----------------|
| `driver.py` | `AgentDriver` ABC -- interface unificada (start_session, send_turn, cancel_turn, list_artifacts, close_session, capabilities) |
| `models.py` | Modelos de domínio: `BackendCapabilities`, requests, events, artifacts |
| `errors.py` | Hierarquia de erros do driver layer |
| `sessions.py` | `SessionManager` -- state machine de sessões (7 estados) |
| `config.py` | `BackendConfig` -- configuração declarativa |
| `resolver.py` | `BackendResolver` -- resolução config-driven com factory registry |
| `agentapi/` | `AgentAPIDriver` -- driver HTTP para endpoints OpenAI-compatible |

---

## Observabilidade

### `observability/`

- `LoggingEventSink` -- sink de eventos baseado em structlog para integração com sistemas de logging existentes

---

## CLI

### `cli/`

Interface de linha de comando baseada em Click.

Comandos:

- `init` -- scaffolding de projeto com `miniautogen.yml` e exemplos opcionais
- `check` -- validação da configuração do projeto
- `run` -- execução de pipeline nomeado em modo headless
- `sessions list` -- listagem de runs com filtros
- `sessions clean` -- remoção de runs antigos por idade

Serviços correspondentes em `cli/services/`: `init_project`, `check_project`, `run_pipeline`, `session_ops`.

---

## Aplicação

### `app/`

Configuração e bootstrap da aplicação:

- `settings.py` -- configurações centralizadas
- `provider_factory.py` -- factory de providers LLM
- `notebook_cache.py` -- cache para notebooks e demos longas com Gemini CLI

---

## Gemini CLI

### `gemini_cli_gateway/`

Gateway local compatível com `/v1/chat/completions` para usar Gemini CLI sem acoplar subprocessos ao core do framework. Permite que o `OpenAICompatibleProvider` comunique com o Gemini CLI através de HTTP padrão.

---

## Módulos legados

Módulos mantidos apenas por compatibilidade. Não devem ser utilizados em código novo.

- `chat/` -- infraestrutura de chat anterior ao runtime atual
- `agent/` -- implementações de agentes anteriores aos contratos tipados
- `compat/` -- shims de compatibilidade (public_api, state_bridge)
- `llms/` -- abstrações LLM anteriores aos adapters atuais

---

## Onde aprofundar

- [Arquitetura (C4)](architecture/README.md)
- [Decisões arquiteturais e roadmap](architecture/06-decisoes.md)
- [Guia do Gemini CLI Gateway](guides/gemini-cli-gateway.md)
- [API pública (54 exports)](../../miniautogen/api.py)
