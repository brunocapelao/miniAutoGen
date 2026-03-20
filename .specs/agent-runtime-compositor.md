# Spec: AgentRuntime — O Compositor de Superpoderes

> **Data:** 2026-03-20
> **Status:** Draft
> **Scope:** Core runtime + contracts + events + PipelineRunner refactor
> **Invariantes respeitados:** Isolamento de adapters, PipelineRunner como unico executor, AnyIO canonico, Policies laterais

---

## Contrato de Prompt

- 🎯 **Goal:** Implementar AgentRuntime como compositor que une Engine + superpoderes (hooks, tools, memory, delegation), materializing a tese "o agente e commodity, o runtime e o produto".
- 🚧 **Constraint:** Isolamento de adapters (core nao importa backends), PipelineRunner como unico executor, AnyIO canonico, Policies laterais. Zero breaking changes nos 4 coordination runtimes.
- 🛑 **Failure Condition:** AgentRuntime nao satisfaz isinstance check para os 3 protocols; hooks/tools/memory nao executam durante coordenacao; testes existentes dos runtimes falham.

## Criterios de Aceitacao

- [ ] `AgentRuntime` satisfaz `WorkflowAgent`, `ConversationalAgent`, `DeliberationAgent` via duck typing
- [ ] `_execute_turn()` emite `AGENT_TURN_STARTED` e `AGENT_TURN_COMPLETED` em todos os paths
- [ ] Tools de `tools.yml` sao injectados no request do driver
- [ ] Memory persiste entre sessions (close → re-initialize recupera contexto)
- [ ] Delegation respeita allowlist e max_depth
- [ ] Testes existentes dos 4 runtimes passam SEM alteracao
- [ ] Agent names validados com regex (sem path traversal)
- [ ] Script tools executam sem `shell=True`, params via stdin
- [ ] Tool params validados contra JSON Schema antes de execucao
- [ ] Filesystem sandbox impede acesso cross-agent a config/memory

## Invariantes Afetadas

- [x] Isolamento de Adapters — AgentRuntime vive em `core/runtime/`, importa `AgentDriver` como bridge (mesmo pattern do PipelineRunner)
- [x] PipelineRunner unico executor — factory de AgentRuntimes vive no PipelineRunner
- [x] AnyIO canonico — todos os metodos async, timeouts via `fail_after`, cleanup via `shield=True`
- [x] Policies laterais — AgentRuntime emite eventos, policies observam via EventSink

## Dependencias

| Dependencia | Tipo | Status |
|-------------|------|--------|
| `core/contracts/agent.py` (3 protocols) | Existente, sem alteracao | Verificado |
| `core/contracts/memory_provider.py` | Existente, sem alteracao | Verificado |
| `core/contracts/tool.py` | Existente, sem alteracao | Verificado |
| `core/events/types.py` (EventType enum) | Existente, +6 novos eventos | A implementar |
| `backends/engine_resolver.py` | Existente, +1 metodo novo | A implementar |
| `backends/resolver.py` (BackendResolver) | Existente, +1 metodo publico | A implementar |

---

## 1. Problema

Os 4 coordination runtimes (Workflow, AgenticLoop, Deliberation, Composite) falam directamente com `AgentDriver`. Isso significa que:

- Hooks nao disparam durante a coordenacao
- Tools unificados nao sao injectados
- Memory nao e consultada nem actualizada
- Delegation nao e controlada
- Lifecycle events nao sao emitidos

O Layer 3 (Agent Runtime) descrito na arquitectura existe em pecas (AgentSpec, AgentHook, 3 hooks built-in) mas nao ha um compositor que as una. A tese "Engine + superpoderes" nao se materializa no codigo.

---

## 2. Solucao

Criar `AgentRuntime` como compositor que **implementa os 3 agent protocols existentes** (`WorkflowAgent`, `ConversationalAgent`, `DeliberationAgent`). O PipelineRunner constroi AgentRuntimes a partir do YAML e passa-os aos coordination runtimes. Os runtimes **nao mudam a sua interface** — continuam a chamar `agent.process()`, `agent.reply()`, etc. Mas agora esses metodos passam pelo compositor que aplica hooks, tools, memory e delegation antes de chamar o driver subjacente.

### 2.1 Modelo de Instancias

```
Engine "claude" (template no YAML — define tipo + defaults)
    │
    ├── AgentRuntime "architect"
    │   └── DriverInstance A (sessao/processo PROPRIO)
    │       ├── prompt: .miniautogen/agents/architect/prompt.md
    │       ├── tools: .miniautogen/agents/architect/tools.yml
    │       └── memory: .miniautogen/agents/architect/memory/
    │
    └── AgentRuntime "reviewer"
        └── DriverInstance B (sessao/processo PROPRIO)
            ├── prompt: .miniautogen/agents/reviewer/prompt.md
            ├── tools: .miniautogen/agents/reviewer/tools.yml
            └── memory: .miniautogen/agents/reviewer/memory/
```

**Regra:** Cada AgentRuntime cria a sua propria instancia do driver. O engine no YAML e uma template. Cada agente instancia a partir da template com configs proprias.

**Optimizacao por tipo:**

| Tipo | Instancia | Recurso partilhado |
|------|-----------|-------------------|
| CLI | Processo separado obrigatorio | Nenhum |
| API | Sessao logica separada | HTTP client partilhado |
| Gateway | Canal/sala separada | WebSocket partilhado (roadmap) |

### 2.2 Configuracao Per-Agent no Filesystem

```
my-project/
├── miniautogen.yml
└── .miniautogen/
    └── agents/
        ├── architect/
        │   ├── prompt.md        ← system prompt (injectado no initialize)
        │   ├── tools.yml        ← tools disponiveis (scoped, DeerFlow pattern)
        │   └── memory/          ← memoria persistente cross-session
        ├── developer/
        │   ├── prompt.md
        │   ├── tools.yml
        │   └── memory/
        └── shared/
            ├── memory/          ← memoria partilhada entre agentes
            └── workspace/       ← outputs intermediarios (filesystem-first)
```

---

## 3. Contratos

### 3.1 AgentRuntime implements existing agent protocols

O `AgentRuntime` implementa os 3 protocols existentes em `core/contracts/agent.py`.
Os coordination runtimes **nao mudam a sua interface** — continuam a usar os protocols que ja conhecem.

```python
@runtime_checkable
class WorkflowAgent(Protocol):
    async def process(self, input: Any) -> Any: ...

@runtime_checkable
class ConversationalAgent(Protocol):
    async def reply(self, message: str, context: dict[str, Any]) -> str: ...
    async def route(self, conversation_history: list[Any]) -> RouterDecision: ...

@runtime_checkable
class DeliberationAgent(Protocol):
    async def contribute(self, topic: str) -> Contribution: ...
    async def review(self, target_id: str, contribution: Contribution) -> Review: ...
```

O `AgentRuntime` satisfaz **todos os tres** via duck typing. Internamente, cada metodo
delega a `_execute_turn()` (metodo INTERNO) que aplica hooks/tools/memory/delegation:

```python
class AgentRuntime:
    """Compositor: Engine + superpoderes.
    Implements WorkflowAgent, ConversationalAgent, DeliberationAgent."""

    @property
    def spec(self) -> AgentSpec: ...

    @property
    def agent_id(self) -> str: ...

    async def initialize(self) -> None:
        """Cria sessao no driver, carrega memory, regista tools."""
        ...

    async def close(self) -> None:
        """Persiste memory, fecha sessao no driver."""
        ...

    # --- WorkflowAgent protocol ---
    async def process(self, input: Any) -> Any:
        """Wraps _execute_turn for workflow coordination."""
        request = self._build_request_from_input(input)
        result = await self._execute_turn(request)
        return result.output

    # --- ConversationalAgent protocol ---
    async def reply(self, message: str, context: dict[str, Any]) -> str:
        """Wraps _execute_turn for conversational coordination."""
        request = self._build_request_from_message(message, context)
        result = await self._execute_turn(request)
        return result.text

    async def route(self, conversation_history: list[Any]) -> RouterDecision:
        """Router logic — delegates to driver or config-based routing."""
        ...

    # --- DeliberationAgent protocol ---
    async def contribute(self, topic: str) -> Contribution:
        """Wraps _execute_turn for deliberation contributions."""
        request = self._build_request_from_topic(topic)
        result = await self._execute_turn(request)
        return Contribution.model_validate(result.structured)

    async def review(self, target_id: str, contribution: Contribution) -> Review:
        """Wraps _execute_turn for deliberation reviews."""
        request = self._build_review_request(target_id, contribution)
        result = await self._execute_turn(request)
        return Review.model_validate(result.structured)

    # --- Internal compositor engine ---
    async def _execute_turn(self, request: SendTurnRequest) -> TurnResult:
        """INTERNAL. Full turn: hooks before → enrich → driver → tool loop → hooks after → memory."""
        ...
```

**Principio chave:** `_execute_turn()` e INTERNO. A interface publica sao os metodos
dos protocols existentes. Os coordination runtimes nao sabem que estao a falar com
um compositor — veem apenas um agente que satisfaz o protocol esperado.

### 3.2 ToolRegistry Protocol

```python
@runtime_checkable
class ToolRegistryProtocol(Protocol):
    """Registo de tools per-agent. Carregado de tools.yml."""

    def list_tools(self) -> list[ToolDefinition]: ...
    async def execute_tool(self, call: ToolCall) -> ToolResult: ...
    def has_tool(self, name: str) -> bool: ...
```

### 3.3 MemoryProvider — extending the existing protocol

O `MemoryProvider` existente em `core/contracts/memory_provider.py` ja define:

```python
@runtime_checkable
class MemoryProvider(Protocol):
    async def get_context(self, agent_id: str, context: RunContext, max_tokens: int | None = None) -> list[dict[str, Any]]: ...
    async def save_turn(self, messages: list[dict[str, Any]], context: RunContext) -> None: ...
    async def distill(self, agent_id: str) -> None: ...
```

O AgentRuntime usa o MemoryProvider existente **sem alteracoes**. Para suportar
cross-session persistence e search (filesystem-backed), criamos uma subclasse concreta
que ESTENDE o protocol existente com metodos adicionais:

```python
class PersistentMemoryProvider(InMemoryMemoryProvider):
    """Extends existing MemoryProvider with filesystem persistence and search.

    Satisfaz o MemoryProvider protocol existente (get_context, save_turn, distill)
    e adiciona metodos para persistencia cross-session.
    """

    def __init__(self, memory_dir: Path) -> None: ...

    # --- Existing MemoryProvider protocol (inherited + overridden) ---
    # get_context() — loads from filesystem if in-memory is empty
    # save_turn()   — persists to filesystem after in-memory save
    # distill()     — writes distilled summary to memory_dir/context.json

    # --- Additional methods for AgentRuntime lifecycle ---
    async def load_from_disk(self) -> None:
        """Called by AgentRuntime.initialize(). Hydrates in-memory store from filesystem."""
        ...

    async def persist_to_disk(self) -> None:
        """Called by AgentRuntime.close(). Flushes in-memory store to filesystem."""
        ...

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Keyword search over persisted entries. Returns matching messages."""
        ...
```

```python
@runtime_checkable
class PersistableMemory(Protocol):
    """Protocol for memory providers that support filesystem persistence."""
    async def load_from_disk(self) -> None: ...
    async def persist_to_disk(self) -> None: ...
```

**Mapeamento entre metodos existentes e uso no AgentRuntime:**

| Metodo existente | Chamado por | Quando |
|------------------|------------|--------|
| `get_context(agent_id, ctx)` | `_execute_turn()` | Enrich request com memoria |
| `save_turn(messages, ctx)` | `_execute_turn()` | Apos turn completado |
| `distill(agent_id)` | `close()` | Antes de persistir ao disco |

| Metodo novo | Chamado por | Quando |
|-------------|------------|--------|
| `load_from_disk()` | `initialize()` | Startup — hydrate from filesystem |
| `persist_to_disk()` | `close()` | Shutdown — flush to filesystem |
| `search(query)` | Tool interno `memory_search` | Agente procura na propria memoria |

### 3.4 DelegationRouter Protocol

```python
@runtime_checkable
class DelegationRouterProtocol(Protocol):
    """Controla quem pode delegar a quem. Tracks depth to prevent infinite loops."""

    def can_delegate(self, from_agent: str, to_agent: str) -> bool: ...

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        input_data: Any,
        current_depth: int = 0,
    ) -> Any:
        """Delegate work to another agent. Returns the target agent's output.
        Uses the same input/output types as the agent protocols (Any for Workflow,
        str for Conversational, typed models for Deliberation).
        Raises DelegationDepthExceededError if current_depth >= max_depth."""
        ...
```

### 3.5 Error Taxonomy Mapping

Novos erros DEVEM pertencer a taxonomia canonica (`ErrorCategory`):

| Erro | Categoria | Justificacao |
|------|-----------|-------------|
| `DelegationDepthExceededError` | `validation` | Regra de validacao configurada (max_depth) |
| `AgentClosedError` | `state_consistency` | Violacao de estado (chamar agente fechado) |
| `ToolExecutionError` | `adapter` | Falha de tool externo |
| `ToolTimeoutError` | `timeout` | Timeout de tool |
| `SecurityError` | `permanent` | Violacao de seguranca (path traversal, injection) |

Todos herdam de `MiniAutoGenError` com `error_category` explicito.

### 3.6 TurnResult (internal)

```python
class TurnResult(BaseModel):
    """Resultado interno de _execute_turn(). NAO e parte da interface publica."""
    output: Any = None                    # WorkflowAgent.process() return
    text: str = ""                        # ConversationalAgent.reply() return
    structured: dict[str, Any] = Field(default_factory=dict)  # For Pydantic parsing
    messages: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    tool_calls: list[ToolCall] = Field(default_factory=list)
```

### 3.7 Tool types — reference existing ToolProtocol

O `ToolProtocol` e `ToolResult` existentes em `core/contracts/tool.py` sao reutilizados:

```python
# Existing — DO NOT REDEFINE
@runtime_checkable
class ToolProtocol(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    async def execute(self, params: dict[str, Any]) -> ToolResult: ...

class ToolResult(BaseModel):
    success: bool
    output: Any = None
    error: str | None = None
```

Tipos adicionais necessarios para o ToolRegistry:

```python
class ToolDefinition(BaseModel):
    """Serializable tool definition for injection into driver prompts."""
    name: str
    description: str
    parameters: dict[str, Any] | None = None  # JSON Schema

    @classmethod
    def from_protocol(cls, tool: ToolProtocol) -> ToolDefinition:
        """Extract definition from a ToolProtocol implementation."""
        ...

class ToolCall(BaseModel):
    """A tool invocation request from the driver."""
    tool_name: str
    call_id: str
    params: dict[str, Any]
```

O `ToolRegistryProtocol` (seccao 3.2) usa estes tipos:
- `list_tools()` retorna `list[ToolDefinition]`
- `execute_tool(call: ToolCall)` retorna `ToolResult` (existente)

---

## 4. Implementacao: AgentRuntime

```python
class AgentRuntime:
    """Compositor: Engine + superpoderes.

    Implements WorkflowAgent, ConversationalAgent, DeliberationAgent.
    Coordination runtimes see it as a regular agent via the protocols.
    """

    def __init__(
        self,
        spec: AgentSpec,
        driver: AgentDriver,
        hooks: list[AgentHook],
        tools: ToolRegistryProtocol,
        memory: MemoryProvider,           # existing protocol from core/contracts
        delegation: DelegationRouterProtocol | None,
        policies: list[Policy],
        event_sink: EventSink,
        config_dir: Path | None,
    ) -> None: ...

    async def initialize(self) -> None:
        """
        1. driver.start_session() — processo/sessao propria
        2. Inject system prompt de config_dir/prompt.md
        3. Carregar tools de config_dir/tools.yml
        4. memory.load_from_disk() (if PersistentMemoryProvider)
        5. Emit agent_turn_started (initialization turn)
        """

    # --- WorkflowAgent protocol ---
    async def process(self, input: Any) -> Any:
        """Build request from input, run _execute_turn, return output."""

    # --- ConversationalAgent protocol ---
    async def reply(self, message: str, context: dict[str, Any]) -> str:
        """Build request from message, run _execute_turn, return text."""

    async def route(self, conversation_history: list[Any]) -> RouterDecision:
        """Router logic via driver or config."""

    # --- DeliberationAgent protocol ---
    async def contribute(self, topic: str) -> Contribution:
        """Build request from topic, run _execute_turn, return Contribution."""

    async def review(self, target_id: str, contribution: Contribution) -> Review:
        """Build review request, run _execute_turn, return Review."""

    # --- Internal compositor engine ---
    async def _execute_turn(self, request: SendTurnRequest) -> TurnResult:
        """
        INTERNAL. Full turn with compositor pipeline:
        1. Emit AGENT_TURN_STARTED
        2. Run before_turn hooks
        3. Enrich request: memory.get_context() + tool definitions
        4. driver.send_turn(enriched_request)
        5. Process tool calls via ToolRegistry (loop until no more calls)
        6. Run after_turn hooks
        7. memory.save_turn(turn_messages)
        8. Emit AGENT_TURN_COMPLETED (com token usage)
        Returns TurnResult with .output, .text, .structured accessors.
        """

    async def close(self) -> None:
        """
        1. memory.distill(agent_id)
        2. memory.persist_to_disk() (if PersistentMemoryProvider)
        3. driver.close_session()
        4. Emit agent_closed
        """
```

---

## 5. Implementacoes Concretas MVP

### 5.1 FileSystemToolRegistry

Carrega tools de `config_dir/tools.yml`:

```yaml
# .miniautogen/agents/architect/tools.yml
tools:
  - name: read_file
    description: Read a file from the workspace
    builtin: true
  - name: search_codebase
    description: Search for patterns in code
    builtin: true
  - name: create_spec
    description: Create a spec document
    script: scripts/create-spec.sh
```

Tipos de tools:
- `builtin: true` — tools fornecidos pelo MiniAutoGen (file ops, search, etc.)
- `script: path` — script externo executado no workspace
- `mcp: server_name` — tool via MCP server (roadmap)

### 5.2 PersistentMemoryProvider

Persiste em `config_dir/memory/`:

```
memory/
├── context.json          ← resumo actual (injectado no prompt)
├── entries/              ← entradas individuais (append-only)
│   ├── 2026-03-20T10-00.json
│   └── 2026-03-20T14-30.json
└── index.json            ← indice para search
```

### 5.3 ConfigDelegationRouter

Baseado na config do AgentSpec:

```yaml
# miniautogen.yml
agents:
  architect:
    engine: claude
    delegation:
      can_delegate_to: [developer, reviewer]
      max_depth: 2
  developer:
    engine: gemini
    delegation:
      can_delegate_to: []  # leaf agent — nao delega
```

### 5.4 InMemoryToolRegistry / InMemoryMemoryProvider

Para testes e uso programatico sem filesystem.

---

## 6. Impacto nos Coordination Runtimes

**Os coordination runtimes NAO precisam de refactor.** Como `AgentRuntime` implementa
os mesmos protocols (`WorkflowAgent`, `ConversationalAgent`, `DeliberationAgent`) que
os runtimes ja usam, a substituicao e transparente via duck typing.

### Exemplo: WorkflowRuntime (sem alteracoes)

```python
class WorkflowRuntime:
    async def execute(self, agents: dict[str, WorkflowAgent], ...):
        for step in plan.steps:
            agent = agents[step.agent_name]
            result = await agent.process(input_data)
            # Antes: chamava driver.process() directamente
            # Agora: AgentRuntime.process() aplica hooks/tools/memory automaticamente
            # MAS O RUNTIME NAO SABE DISSO — mesma interface
            ...
```

### Exemplo: AgenticLoopRuntime (sem alteracoes)

```python
class AgenticLoopRuntime:
    async def execute(self, agents: dict[str, ConversationalAgent], ...):
        agent = agents[current_speaker]
        response = await agent.reply(message, context)
        decision = await agent.route(history)
        # Transparente — AgentRuntime satisfaz ConversationalAgent
```

### Exemplo: DeliberationRuntime (sem alteracoes)

```python
class DeliberationRuntime:
    async def execute(self, agents: dict[str, DeliberationAgent], ...):
        contribution = await agent.contribute(topic)
        review = await reviewer.review(agent_id, contribution)
        # Transparente — AgentRuntime satisfaz DeliberationAgent
```

**Impacto nos runtimes:** ZERO linhas de refactor. A mudanca esta APENAS no PipelineRunner
(que constroi AgentRuntimes em vez de passar drivers crus) e nos type hints dos
runtimes (que podem aceitar `WorkflowAgent` em vez de `AgentDriver` — mas isto e
uma melhoria de tipos, nao uma mudanca de comportamento).

---

## 7. PipelineRunner como Factory

O PipelineRunner e o UNICO local que muda. Usa `EngineResolver` (existente em
`miniautogen/backends/engine_resolver.py`) e `BackendResolver` (existente em
`miniautogen/backends/resolver.py`) para resolver engines em drivers.

**API existente do EngineResolver:**
- `EngineResolver.resolve(profile_name, config) -> AgentDriver` — cached, shared
- `EngineResolver.resolve_with_fallbacks(profile_name, config) -> AgentDriver` — com fallback chain
- Internamente usa `BackendResolver` que cacheia drivers por `backend_id`

**Problema:** `BackendResolver.get_driver()` cacheia uma unica instancia por backend_id.
Para AgentRuntime precisamos de uma instancia FRESCA por agente (sessao/processo proprio).

**Solucao:** Adicionar `EngineResolver.create_fresh_driver(profile_name, config) -> AgentDriver`
que bypassa o cache do `BackendResolver` e cria uma nova instancia via factory.

```python
class PipelineRunner:
    def __init__(
        self,
        # ... existing params ...
        engine_resolver: EngineResolver | None = None,
    ) -> None:
        # ... existing init ...
        self._engine_resolver = engine_resolver or EngineResolver()

    async def _build_agent_runtimes(
        self,
        plan: Any,
        config: ProjectConfig,
        workspace: Path,
    ) -> dict[str, AgentRuntime]:
        runtimes: dict[str, AgentRuntime] = {}
        delegation = ConfigDelegationRouter(plan.agents)

        for agent_name, agent_config in plan.agents.items():
            # 1. Create FRESH driver via EngineResolver (not cached)
            #    Uses resolve_with_fallbacks for resilience
            driver = self._engine_resolver.create_fresh_driver(
                agent_config.engine, config,
            )

            # 2. Load per-agent config directory
            config_dir = workspace / ".miniautogen" / "agents" / agent_name

            # 3. Build components (filesystem-backed or in-memory fallback)
            if config_dir.exists():
                tools = FileSystemToolRegistry(config_dir / "tools.yml")
                memory = PersistentMemoryProvider(config_dir / "memory")
            else:
                tools = InMemoryToolRegistry()
                memory = InMemoryMemoryProvider()

            hooks = self._resolve_hooks(agent_config)
            policies = self._resolve_policies(agent_config)

            # 4. Compose AgentRuntime
            runtimes[agent_name] = AgentRuntime(
                spec=agent_config.spec,
                driver=driver,
                hooks=hooks,
                tools=tools,
                memory=memory,
                delegation=delegation,
                policies=policies,
                event_sink=self.event_sink,
                config_dir=config_dir if config_dir.exists() else None,
            )
        return runtimes
```

**Mudanca necessaria em EngineResolver:**

```python
class EngineResolver:
    def create_fresh_driver(
        self, profile_name: str, config: ProjectConfig,
    ) -> AgentDriver:
        """Create a NEW driver instance (not cached). For per-agent sessions."""
        engine = config.engine_profiles.get(profile_name)
        if engine is None:
            msg = f"Engine profile '{profile_name}' not found"
            raise BackendUnavailableError(msg)

        backend_config = self._engine_to_backend(
            f"{profile_name}_{uuid4().hex[:8]}", engine,
        )
        return self._resolver.create_driver(backend_config)
```

**Mudanca necessaria em BackendResolver:**

```python
class BackendResolver:
    def create_driver(self, config: BackendConfig) -> AgentDriver:
        """Create a NEW driver instance (not cached). Public factory method."""
        factory = self._factories.get(config.driver)
        if factory is None:
            msg = f"No factory for driver type '{config.driver.value}'"
            raise BackendUnavailableError(msg)
        return factory(config)
```

---

## 8. Reconciliacao de Eventos com EventType existente

O enum `EventType` em `core/events/types.py` tem actualmente **63 membros** em 13 categorias de eventos (Run, Component, Tool, Checkpoint, Adapter/Validation/Policy/Budget, AgenticLoop, Deliberation, Backend, Approval, Effect, Supervision, AgentRuntime, Interceptor/RunState).

### Eventos que JA EXISTEM (nao re-adicionar)

A categoria "Agent Runtime events (Phase B)" ja existe com 4 eventos:

| Evento existente | Valor | Uso no AgentRuntime |
|------------------|-------|---------------------|
| `AGENT_TURN_STARTED` | `agent_turn_started` | `_execute_turn()` inicio |
| `AGENT_TURN_COMPLETED` | `agent_turn_completed` | `_execute_turn()` fim |
| `AGENT_HOOK_EXECUTED` | `agent_hook_executed` | Cada hook before/after |
| `AGENT_TOOL_INVOKED` | `agent_tool_invoked` | ToolRegistry.execute_tool() |

Nota: `AGENT_TURN_COMPLETED` cobre o que antes chamavamos `agent_turn_finished`.

### Eventos VERDADEIRAMENTE NOVOS (a adicionar)

| Evento | Valor | Categoria | Emitido por |
|--------|-------|-----------|-------------|
| `AGENT_INITIALIZED` | `agent_initialized` | AgentRuntime | initialize() completo |
| `AGENT_CLOSED` | `agent_closed` | AgentRuntime | close() completo |
| `AGENT_MEMORY_LOADED` | `agent_memory_loaded` | AgentRuntime | initialize() apos load |
| `AGENT_MEMORY_SAVED` | `agent_memory_saved` | AgentRuntime | close() apos persist |
| `AGENT_DELEGATED` | `agent_delegated` | AgentRuntime | DelegationRouter.delegate() |
| `AGENT_DELEGATION_DEPTH_EXCEEDED` | `agent_delegation_depth_exceeded` | AgentRuntime | delegate() depth check |

**Total apos implementacao:** 63 existentes + 6 novos = **69 eventos em 13 categorias**.

Actualizar `AGENT_RUNTIME_EVENT_TYPES` set:

```python
AGENT_RUNTIME_EVENT_TYPES: set[EventType] = {
    # Existing
    EventType.AGENT_TURN_STARTED,
    EventType.AGENT_TURN_COMPLETED,
    EventType.AGENT_HOOK_EXECUTED,
    EventType.AGENT_TOOL_INVOKED,
    # New
    EventType.AGENT_INITIALIZED,
    EventType.AGENT_CLOSED,
    EventType.AGENT_MEMORY_LOADED,
    EventType.AGENT_MEMORY_SAVED,
    EventType.AGENT_DELEGATED,
    EventType.AGENT_DELEGATION_DEPTH_EXCEEDED,
}
```

---

## 9. Correcoes de Docs Incluidas

| Item | Ficheiros | Acao |
|------|-----------|------|
| Event count | `docs/pt/README.md`, `docs/pt/architecture/05-invariantes.md`, `docs/competitive-landscape.md` | Actualizar para "69 eventos em 13 categorias" |
| Gateway/WebSocket | `docs/pt/README.md` (seccao Engines), `docs/pt/architecture/07-agent-anatomy.md` | Marcar como "(roadmap)" explicitamente |
| EngineProfile.kind | `miniautogen/core/contracts/engine_profile.py` | Manter `Literal["api", "cli"]` ate gateway driver existir |
| Agent anatomy (Layer 3) | `docs/pt/architecture/07-agent-anatomy.md` | Actualizar com referencia ao AgentRuntime compositor |

---

## 10. Failure Conditions

A implementacao FALHA se:

1. `AgentRuntime` nao satisfizer `isinstance` check para os 3 protocols (`WorkflowAgent`, `ConversationalAgent`, `DeliberationAgent`)
2. `_execute_turn()` nao emitir `AGENT_TURN_STARTED` e `AGENT_TURN_COMPLETED`
3. Tools definidos em `tools.yml` nao forem injectados no request do driver
4. Memory nao persistir entre sessions (close → re-initialize deve recuperar contexto)
5. Delegation permitir routing nao autorizado (agente A delega a B sem permissao)
6. Delegation sem depth tracking permitir loops infinitos
7. Testes existentes dos 4 runtimes passarem SEM alteracao (prova de backward compat)

---

## 11. Ordem de Implementacao

**Legenda:** S = Small (1-2 dias), M = Medium (3-5 dias)

| Fase | Entrega | Dependencia | Estimativa |
|------|---------|-------------|------------|
| 1 | Protocols (ToolRegistry, DelegationRouter) + tipos (ToolDefinition, ToolCall) | Nenhuma | S |
| 2 | AgentRuntime class (implements 3 protocols) + InMemory impls | Fase 1 | M |
| 3 | 6 novos EventTypes + actualizar AGENT_RUNTIME_EVENT_TYPES | Fase 1 | S |
| 4 | EngineResolver.create_fresh_driver() | Nenhuma | S |
| 5 | PipelineRunner factory (_build_agent_runtimes) | Fases 1-4 | M |
| 6 | PersistentMemoryProvider (extends InMemoryMemoryProvider) | Fase 2 | M |
| 7 | FileSystemToolRegistry | Fase 1 | S |
| 8 | `mag init` scaffold da pasta .miniautogen/agents/ | Fases 6-7 | S |
| 9 | Docs: event count (69), gateway roadmap, agent anatomy update | Fase 3 | S |
| 10 | Security: AgentSpec.id validation + AgentFilesystemSandbox + ToolExecutionPolicy | Fase 7 | M |

**Nota:** Fase 4 dos runtimes (antigo "Refactor 4 runtimes") foi REMOVIDA.
Os coordination runtimes nao precisam de alteracao porque AgentRuntime satisfaz
os mesmos protocols que ja usam. Estimativa total reduzida.

---

## 12. Error Handling e Edge Cases

### 12.1 Concurrent Delegation

Quando dois agentes delegam simultaneamente ao mesmo agente target:

- Cada `AgentRuntime` tem a sua propria instancia de driver (sessao/processo proprio)
- Delegacoes concorrentes criam turns separados no target — nao ha race condition no driver
- O `DelegationRouter` deve ser thread-safe (read-only config, sem estado mutavel)
- Se o target estiver `close()`-ed, `delegate()` raises `AgentClosedError`

### 12.2 Memory Save Failure durante close()

```python
async def close(self) -> None:
    try:
        await self._memory.distill(self.agent_id)
        if isinstance(self._memory, PersistableMemory):
            await self._memory.persist_to_disk()
    except Exception as exc:
        # Log but don't prevent driver cleanup
        await self._event_sink.publish(ExecutionEvent(
            type=EventType.AGENT_MEMORY_SAVED.value,  # with error payload
            payload={"error": str(exc), "success": False},
            ...
        ))
        logger.error("memory_persist_failed", agent_id=self.agent_id, error=str(exc))
    finally:
        # Driver cleanup MUST happen even if memory fails
        await self._driver.close_session()
        await self._event_sink.publish(ExecutionEvent(
            type=EventType.AGENT_CLOSED.value, ...
        ))
```

### 12.3 Config Directory Missing (fallback behavior)

- Se `config_dir` nao existir: usar `InMemoryToolRegistry` (sem tools) e `InMemoryMemoryProvider`
- Se `config_dir/prompt.md` nao existir: nao injectar system prompt (agente opera sem)
- Se `config_dir/tools.yml` nao existir: `FileSystemToolRegistry` retorna lista vazia
- Se `config_dir/memory/` nao existir: `PersistentMemoryProvider` cria o directorio no primeiro `persist_to_disk()`
- Log warning para cada fallback activado

### 12.4 Tool Execution Timeout

```python
async def _execute_tool_with_timeout(self, call: ToolCall) -> ToolResult:
    tool_timeout = self._spec.tool_timeout_seconds or 30.0  # default 30s
    try:
        with anyio.fail_after(tool_timeout):
            return await self._tools.execute_tool(call)
    except TimeoutError:
        await self._event_sink.publish(ExecutionEvent(
            type=EventType.AGENT_TOOL_INVOKED.value,
            payload={"tool": call.tool_name, "error": "timeout", "timeout_seconds": tool_timeout},
            ...
        ))
        return ToolResult(success=False, error=f"Tool '{call.tool_name}' timed out after {tool_timeout}s")
```

### 12.5 Cancellation Propagation via AnyIO

O `AgentRuntime` respeita o cancelamento estruturado do AnyIO:

- `_execute_turn()` e `async` — cancellation propagates naturalmente
- Se o `CancelScope` pai for cancelado durante `driver.send_turn()`, o driver
  deve fazer cleanup (fechar processo CLI, abort HTTP request)
- Hook execution wrapped em `anyio.move_on_after()` para evitar que um hook lento
  bloqueie a cancellation
- `close()` NUNCA e cancelavel — usa `anyio.open_cancel_scope(shield=True)` para
  garantir cleanup mesmo durante cancellation:

```python
async def close(self) -> None:
    async with anyio.open_cancel_scope(shield=True):
        # Memory persist + driver cleanup cannot be interrupted
        ...
```

### 12.6 Delegation Depth Exceeded

```python
async def delegate(self, from_agent, to_agent, input_data, current_depth=0):
    max_depth = self._agent_configs[from_agent].delegation.max_depth
    if current_depth >= max_depth:
        await self._event_sink.publish(ExecutionEvent(
            type=EventType.AGENT_DELEGATION_DEPTH_EXCEEDED.value,
            payload={"from": from_agent, "to": to_agent, "depth": current_depth, "max": max_depth},
            ...
        ))
        raise DelegationDepthExceededError(
            f"Agent '{from_agent}' exceeded max delegation depth {max_depth}"
        )
    # Proceed with delegation, passing current_depth + 1
    ...
```

---

## 13. Security Model

### 13.1 Agent Name Validation (CRIT-2 fix)

`AgentSpec.id` DEVE ser validado com regex estrito. Adicionar `field_validator` ao modelo existente:

```python
import re
from pydantic import field_validator

class AgentSpec(BaseModel):
    id: str

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$", v):
            raise ValueError(
                f"Agent ID must be alphanumeric with .-_ only, "
                f"1-64 chars, no path separators: {v!r}"
            )
        return v
```

Adicionalmente, no `PipelineRunner._build_agent_runtimes()`, verificar containment:

```python
config_dir = (workspace / ".miniautogen" / "agents" / agent_name).resolve()
agents_root = (workspace / ".miniautogen" / "agents").resolve()
if not config_dir.is_relative_to(agents_root):
    raise SecurityError(f"Agent name causes path traversal: {agent_name}")
```

### 13.2 Script Tool Execution Security (CRIT-1 fix)

Script tools NUNCA executam com `shell=True`. Parametros sao passados via stdin (JSON), nunca como argumentos de linha de comando.

```python
class FileSystemToolRegistry:
    async def _execute_script(self, script_rel: str, params: dict) -> ToolResult:
        # 1. Validar path relativo sem traversal
        script_path = (self._workspace_root / script_rel).resolve()
        if not script_path.is_relative_to(self._workspace_root):
            raise SecurityError("Script path traversal detected")
        if not script_path.is_file():
            raise SecurityError(f"Script not found: {script_rel}")

        # 2. Executar SEM shell, params via stdin
        async with await anyio.open_process(
            [str(script_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            stdout, stderr = await proc.communicate(
                json.dumps(params).encode()
            )
            return ToolResult(
                success=proc.returncode == 0,
                output=stdout.decode(),
                error=stderr.decode() if proc.returncode != 0 else None,
            )
```

Validacao de `script` path no YAML:

```python
class ScriptToolConfig(BaseModel):
    script: str

    @field_validator("script")
    @classmethod
    def validate_script_path(cls, v: str) -> str:
        if v.startswith("/") or ".." in Path(v).parts:
            raise ValueError(f"Script path must be relative without traversal: {v}")
        return v
```

### 13.3 Tool Parameter Validation (CRIT-3 fix)

Todos os tool calls sao validados contra JSON Schema ANTES de execucao:

```python
class ToolRegistry:
    async def execute_tool(self, call: ToolCall) -> ToolResult:
        tool_def = self._definitions.get(call.tool_name)
        if tool_def is None:
            return ToolResult(success=False, error=f"Unknown tool: {call.tool_name}")

        # 1. Validar params contra JSON Schema
        if tool_def.parameters:
            try:
                jsonschema.validate(call.params, tool_def.parameters)
            except jsonschema.ValidationError as e:
                return ToolResult(success=False, error=f"Invalid params: {e.message}")

        # 2. Sandboxar paths de filesystem
        if "path" in call.params:
            resolved = (self._workspace_root / call.params["path"]).resolve()
            if not resolved.is_relative_to(self._workspace_root):
                return ToolResult(success=False, error="Path traversal blocked")

        # 3. Executar com timeout
        return await self._execute_with_timeout(call)
```

### 13.4 Filesystem Isolation Between Agents (HIGH-3 fix)

Built-in filesystem tools (read_file, write_file, search_codebase) DEVEM enforcar per-agent sandboxing:

- Agente pode ler/escrever: seu proprio `config_dir/` + `shared/` + workspace root (source code)
- Agente NAO pode ler/escrever: `.miniautogen/agents/{outro_agente}/`
- Agente NAO pode escrever: `.miniautogen/agents/{self}/prompt.md` (imutavel apos load)

```python
class AgentFilesystemSandbox:
    """Enforces per-agent filesystem boundaries."""

    def __init__(self, agent_name: str, workspace: Path):
        self._allowed_read = [
            workspace,                                              # source code
            workspace / ".miniautogen" / "agents" / agent_name,    # own config
            workspace / ".miniautogen" / "shared",                  # shared
        ]
        self._denied_write = [
            workspace / ".miniautogen" / "agents",                  # other agents
        ]
        self._immutable = [
            workspace / ".miniautogen" / "agents" / agent_name / "prompt.md",
        ]

    def can_read(self, path: Path) -> bool:
        resolved = path.resolve()
        return any(resolved.is_relative_to(d) for d in self._allowed_read)

    def can_write(self, path: Path) -> bool:
        resolved = path.resolve()
        if any(resolved == f for f in self._immutable):
            return False
        if any(resolved.is_relative_to(d) for d in self._denied_write):
            # Only allow writing to own agent dir
            own_dir = self._allowed_read[1]  # own config dir
            return resolved.is_relative_to(own_dir)
        return True
```

### 13.5 Prompt Integrity Protection (HIGH-2 fix)

`prompt.md` e carregado em `initialize()` e verificado por hash antes de cada turn:

```python
async def initialize(self) -> None:
    if self._config_dir:
        prompt_path = self._config_dir / "prompt.md"
        if prompt_path.exists():
            content = prompt_path.read_text()
            self._system_prompt = content
            self._prompt_hash = hashlib.sha256(content.encode()).hexdigest()
```

A verificacao de integridade e feita no `_execute_turn()` — se o hash mudou, o turn e rejeitado com `SecurityError`.

### 13.6 Delegation Permission Propagation (HIGH-1 fix)

Delegacoes transitivas usam permissoes do MINIMO da cadeia:

```python
class ConfigDelegationRouter:
    async def delegate(self, from_agent, to_agent, input_data, current_depth=0):
        # 1. Check direct allowlist
        if not self.can_delegate(from_agent, to_agent):
            raise SecurityError(f"Delegation not allowed: {from_agent} -> {to_agent}")

        # 2. Check depth
        max_depth = self._configs[from_agent].delegation.max_depth
        if current_depth >= max_depth:
            raise DelegationDepthExceededError(...)

        # 3. Propagate restrictions: target agent inherits the MINIMUM permissions
        #    of the entire chain (from_agent's restrictions apply to to_agent)
        ...
```

### 13.7 Tool Execution Resource Limits (HIGH-4 fix)

```python
class ToolExecutionPolicy(BaseModel):
    """Limites de recurso para execucao de tools por turn."""
    timeout_per_tool: float = 30.0
    max_concurrent_tools: int = 5
    max_tool_calls_per_turn: int = 20
    max_cumulative_tool_time: float = 120.0
```

Script tools DEVEM fazer cleanup de subprocessos em timeout:

```python
try:
    with anyio.fail_after(timeout):
        async with await anyio.open_process(cmd) as proc:
            ...
except TimeoutError:
    proc.kill()
    await proc.wait()  # Ensure subprocess is reaped
```
