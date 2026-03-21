# Especificação: End-to-End Wiring — AgentRuntime + Builtin Tools + Config-Driven Flows

| Campo      | Valor                          |
|------------|--------------------------------|
| Data       | 2026-03-20                     |
| Autor      | Claude (Arquiteto)             |
| Status     | Em Revisão (v2 — pós-review)   |
| Spec ID    | 008                            |

---

## Contrato de Prompt (G/C/FC)

### 🎯 Goal (Objetivo)

> Fechar o loop end-to-end do MiniAutoGen: `mag init` → configure agents/engines/flows em YAML → `mag run` executa com AgentRuntimes reais (tools, memory, prompt.md, delegation). Atualmente `_build_agent_runtimes()` é dead code — nunca é chamado. Esta spec conecta todas as peças existentes e adiciona os componentes faltantes (BuiltinToolRegistry, CompositeToolRegistry, config-driven flow execution).

### 🚧 Constraint (Restrição)

> 1. Zero breaking changes nos coordination runtimes (Workflow, Deliberation, AgenticLoop, Composite).
> 2. Isolamento de adapters: builtin tools usam apenas `anyio.Path` (stdlib), nunca dependências externas.
> 3. PipelineRunner continua sendo o único executor oficial.
> 4. AnyIO canônico: todo I/O é async — inclui prompt.md loading e tool execution.
> 5. FileSystemToolRegistry não contém lógica de builtin tools (separação de responsabilidades).

### 🛑 Failure Condition (Condição de Falha)

> 1. `mag init && mag run main` com flow config-driven (mode + participants, sem target Python) não produz output de agentes.
> 2. Builtin tool `read_file` não retorna conteúdo real de um arquivo dentro do sandbox.
> 3. `PersistentMemoryProvider` não persiste memória entre execuções.
> 4. Testes existentes (488 CLI + 159 SDK) regridem.
> 5. `search_codebase` com pattern começando por `-` é interpretado como flag do grep.

---

## User Stories

- Como **desenvolvedor**, quero executar `mag init && mag run main` sem escrever Python, para que possa prototipar fluxos multi-agente apenas com configuração YAML.
- Como **desenvolvedor**, quero que agentes API (OpenAI, Anthropic, Google) possam ler arquivos e buscar código via builtin tools, para que tenham capacidades de filesystem sem depender de tools nativos do provider.
- Como **desenvolvedor**, quero que a memória do agente persista entre execuções, para que o agente mantenha contexto entre sessões.
- Como **desenvolvedor**, quero definir um `prompt.md` por agente que sobrescreva o system prompt gerado, para que tenha controle total sobre o comportamento do agente.

---

## Critérios de Aceitação

- [ ] CA-1: `_build_agent_runtimes()` é chamado pelo fluxo de execução quando flow tem `mode` + `participants`
- [ ] CA-2: Config-driven flow execution cria coordination runtime (Workflow/Deliberation/AgenticLoop) a partir do YAML via `_build_plan_from_config()`
- [ ] CA-3: `BuiltinToolRegistry` implementa `read_file`, `search_codebase`, `list_directory` com handlers reais (anyio.Path)
- [ ] CA-4: `CompositeToolRegistry` encadeia múltiplos registries (Builtin + FileSystem) sob `ToolRegistryProtocol`
- [ ] CA-5: `FileSystemToolRegistry` não contém lógica de builtin (hack `if builtin` removido)
- [ ] CA-6: Factory usa `PersistentMemoryProvider` em vez de `InMemoryMemoryProvider`
- [ ] CA-7: Factory carrega `prompt.md` de `.miniautogen/agents/{name}/prompt.md` como override do system prompt (async via anyio.Path)
- [ ] CA-8: Factory recebe `run_id` real (não placeholder "pending"), `_build_agent_runtimes()` é `async def`
- [ ] CA-9: Builtin tools respeitam `AgentFilesystemSandbox.can_read()` e impõem limites de recurso
- [ ] CA-10: Callable-based flows (target Python) continuam funcionando sem mudança
- [ ] CA-11: `search_codebase` usa `--` separator para prevenir argument injection, `--max-count` para limitar output
- [ ] CA-12: AgentRuntimes são inicializados (`initialize()`) e fechados (`close()`) no `run_from_config()`
- [ ] CA-13: `FlowConfig` schema atualizado com `mode`, `participants`, e campos mode-specific
- [ ] CA-14: `load_agent_specs()` definido e implementado para descobrir e parsear agent YAMLs
- [ ] CA-15: Testes unitários passam a 100%, nenhuma regressão nos testes existentes

---

## Invariantes Afetadas

- [x] **Isolamento de Adapters** — Builtin tools usam apenas `anyio.Path`, sem dependências externas no core
- [x] **Microkernel / PipelineRunner** — Config-driven path executa dentro do PipelineRunner (único executor)
- [x] **Assincronismo Canônico (AnyIO)** — Todos os handlers são async via anyio, incluindo factory (`async def _build_agent_runtimes`)
- [x] **Policies Event-Driven** — Sem mudança no policy chain; AgentRuntime já emite eventos tipados

Notas:
> - BuiltinToolRegistry está em `core/runtime/` e usa apenas stdlib + anyio (sem adapters)
> - CompositeToolRegistry é um compositor puro — delega para registries injetados
> - Config-driven execution cria coordination runtimes que já existem — não cria novos executors

---

## Arquitetura

### 1. Novos Componentes

#### 1.1 BuiltinToolRegistry (`miniautogen/core/runtime/builtin_tools.py`)

```python
class BuiltinToolRegistry:
    """Registry de tools fornecidos pelo runtime (não pelo provider)."""

    # Resource limits
    MAX_FILE_READ_BYTES = 1_048_576      # 1 MB max per read_file call
    MAX_DIRECTORY_ENTRIES = 1_000        # Max entries returned by list_directory
    MAX_SEARCH_RESULTS = 200             # Hard cap on search_codebase results
    MAX_SEARCH_LINE_LENGTH = 500         # Truncate long match lines

    def __init__(
        self,
        workspace_root: Path,
        sandbox: AgentFilesystemSandbox | None = None,
        timeout: float = 30.0,
    ) -> None: ...

    def list_tools(self) -> list[ToolDefinition]: ...
    def has_tool(self, name: str) -> bool: ...
    async def execute_tool(self, call: ToolCall) -> ToolResult: ...
```

**Tools:**

| Tool | Params | Retorno | Sandbox | Limits |
|------|--------|---------|---------|--------|
| `read_file` | `path: str`, `offset?: int`, `limit?: int` | Conteúdo (linhas numeradas) | `can_read()` | 1 MB max sem limit; check `stat.st_size` antes de ler |
| `search_codebase` | `pattern: str`, `glob?: str`, `max_results?: int` | Matches com path:line:content | `can_read()` | `--max-count=200`, lines truncadas a 500 chars |
| `list_directory` | `path: str` | Entradas com tipo (file/dir) | `can_read()` | Max 1000 entradas |

**Implementação:**

`read_file`:
```python
async def _read_file(self, params: dict) -> ToolResult:
    path = params.get("path", "")
    offset = params.get("offset", 0)
    limit = params.get("limit")

    resolved = (self._workspace_root / path).resolve()

    # Sandbox check
    if self._sandbox and not self._sandbox.can_read(resolved):
        return ToolResult(success=False, error="Sandbox denied read access")

    # Reject symlinks pointing outside workspace
    apath = anyio.Path(resolved)
    if not await apath.is_file():
        return ToolResult(success=False, error=f"File not found: {path}")

    # Size check before reading
    stat = await apath.stat()
    if stat.st_size > self.MAX_FILE_READ_BYTES and limit is None:
        return ToolResult(
            success=False,
            error=f"File too large ({stat.st_size} bytes). Use offset/limit params.",
        )

    content = await apath.read_text()
    lines = content.splitlines()
    selected = lines[offset:offset + limit] if limit else lines[offset:]
    numbered = [f"{i + offset + 1:>6}\t{line}" for i, line in enumerate(selected)]
    return ToolResult(success=True, output="\n".join(numbered))
```

`search_codebase`:
```python
async def _search_codebase(self, params: dict) -> ToolResult:
    pattern = params.get("pattern", "")
    glob_filter = params.get("glob", "*")
    max_results = min(params.get("max_results", 50), self.MAX_SEARCH_RESULTS)

    if not pattern:
        return ToolResult(success=False, error="Pattern is required")

    # Validate glob doesn't contain traversal
    if ".." in glob_filter or glob_filter.startswith("/"):
        return ToolResult(success=False, error="Invalid glob pattern")

    search_root = self._workspace_root.resolve()
    if self._sandbox and not self._sandbox.can_read(search_root):
        return ToolResult(success=False, error="Sandbox denied access")

    cmd = [
        "grep", "-rn",
        "--max-count", str(max_results),
        "--include", glob_filter,
        "--",          # Prevents pattern from being interpreted as flag
        pattern,
        str(search_root),
    ]

    try:
        with anyio.fail_after(self._timeout):
            result = await anyio.run_process(cmd)
        lines = result.stdout.decode(errors="replace").splitlines()[:max_results]
        truncated = [
            line[:self.MAX_SEARCH_LINE_LENGTH] + "..." if len(line) > self.MAX_SEARCH_LINE_LENGTH else line
            for line in lines
        ]
        return ToolResult(success=True, output="\n".join(truncated))
    except TimeoutError:
        return ToolResult(success=False, error=f"Search timed out after {self._timeout}s")
    except Exception:
        # grep returns exit code 1 when no matches found
        return ToolResult(success=True, output="No matches found")
```

`list_directory`:
```python
async def _list_directory(self, params: dict) -> ToolResult:
    path = params.get("path", ".")
    resolved = (self._workspace_root / path).resolve()

    if self._sandbox and not self._sandbox.can_read(resolved):
        return ToolResult(success=False, error="Sandbox denied read access")

    apath = anyio.Path(resolved)
    if not await apath.is_dir():
        return ToolResult(success=False, error=f"Not a directory: {path}")

    entries = []
    count = 0
    async for entry in apath.iterdir():
        if count >= self.MAX_DIRECTORY_ENTRIES:
            entries.append(f"... truncated at {self.MAX_DIRECTORY_ENTRIES} entries")
            break
        entry_type = "dir" if await entry.is_dir() else "file"
        # Resolve symlinks for type but show original name
        entries.append(f"{entry_type}\t{entry.name}")
        count += 1

    return ToolResult(success=True, output="\n".join(sorted(entries)))
```

#### 1.2 CompositeToolRegistry (`miniautogen/core/runtime/composite_tool_registry.py`)

```python
class CompositeToolRegistry:
    """Encadeia múltiplos registries sob uma interface unificada.

    Primeiro registry que contém o tool vence (first-match).
    Quando um user tool tem o mesmo nome de um builtin, o user tool
    tem precedência — e um warning é emitido via logging.
    """

    def __init__(self, registries: Sequence[ToolRegistryProtocol]) -> None:
        self._registries = list(registries)

    def list_tools(self) -> list[ToolDefinition]:
        tools = []
        seen: set[str] = set()
        for reg in self._registries:
            for tool in reg.list_tools():
                if tool.name not in seen:
                    tools.append(tool)
                    seen.add(tool.name)
                else:
                    logger.warning("Tool '%s' shadowed by earlier registry", tool.name)
        return tools

    def has_tool(self, name: str) -> bool:
        return any(r.has_tool(name) for r in self._registries)

    async def execute_tool(self, call: ToolCall) -> ToolResult:
        for reg in self._registries:
            if reg.has_tool(call.tool_name):
                return await reg.execute_tool(call)
        return ToolResult(success=False, error=f"Unknown tool: {call.tool_name}")
```

Composição padrão:
```
CompositeToolRegistry([
    FileSystemToolRegistry(tools.yml),  # user tools primeiro (podem override builtin)
    BuiltinToolRegistry(workspace_root, sandbox),
])
```

### 2. Schema Changes

#### 2.1 FlowConfig — Campos config-driven

**Atual:**
```python
class FlowConfig(BaseModel):
    target: str
```

**Novo:**
```python
class FlowConfig(BaseModel):
    target: str | None = None          # Python callable path (existing)
    mode: str | None = None            # workflow | deliberation | loop | composite
    participants: list[str] = Field(default_factory=list)
    input_text: str | None = None      # Default input text for the flow

    # Mode-specific options
    leader: str | None = None          # deliberation: leader agent
    max_rounds: int = 3                # deliberation: max review rounds
    max_turns: int = 20                # agentic loop: max turns
    router: str | None = None          # agentic loop: router agent name
    chain_flows: list[str] = Field(default_factory=list)  # composite: sub-flow names

    @model_validator(mode="after")
    def validate_flow(self) -> FlowConfig:
        if not self.target and not self.mode:
            raise ValueError("Flow must have either 'target' or 'mode'")
        if self.mode and not self.participants:
            raise ValueError("Config-driven flow requires 'participants'")
        if self.mode == "deliberation" and not self.leader:
            raise ValueError("Deliberation mode requires 'leader'")
        if self.mode == "loop" and not self.router:
            raise ValueError("Loop mode requires 'router'")
        return self
```

Backward compatible: `FlowConfig` com alias `PipelineConfig` continua funcionando.

#### 2.2 load_agent_specs() — Agent discovery

```python
# miniautogen/cli/services/agent_ops.py (adicionar)

def load_agent_specs(project_root: Path) -> dict[str, AgentSpec]:
    """Discover and parse agent definitions from workspace.

    Agent specs are loaded from two sources (merged, agents/ takes precedence):
    1. agents/*.yaml files in project root
    2. .miniautogen/agents/{name}/agent.yaml per-agent config dirs

    Returns:
        Mapping of agent_name -> AgentSpec.

    Raises:
        ConfigurationError: If agent YAML is malformed.
    """
    specs: dict[str, AgentSpec] = {}

    # Source 1: agents/*.yaml (workspace-level definitions)
    agents_dir = project_root / "agents"
    if agents_dir.is_dir():
        for yaml_file in sorted(agents_dir.glob("*.yaml")):
            data = yaml.safe_load(yaml_file.read_text()) or {}
            name = yaml_file.stem
            specs[name] = AgentSpec(**data, id=name)

    return specs
```

### 3. Componentes Modificados

#### 3.1 FileSystemToolRegistry — Remover hack builtin

**Antes (linhas 88-92 de execute_tool):**
```python
if cfg.get("builtin"):
    return ToolResult(
        success=False,
        error=f"Builtin tool '{call.tool_name}' not yet implemented",
    )
```

**Depois:** Remover esse bloco de `execute_tool()`.

**Na `_load()` (linhas 43-58):** Adicionar skip para tools com `builtin: true`:
```python
if tool_cfg.get("builtin"):
    continue  # Handled by BuiltinToolRegistry
```

#### 3.2 PipelineRunner._build_agent_runtimes() — Factory real (async)

```python
async def _build_agent_runtimes(
    self,
    *,
    agent_specs: dict[str, AgentSpec],
    workspace: Path,
    config: WorkspaceConfig,
    run_id: str,
) -> dict[str, AgentRuntime]:
    """Build AgentRuntime instances from workspace config.

    This is the SOLE point where AgentRuntime instances are created.
    Each agent gets its own fresh driver, composite tool registry,
    persistent memory, and delegation router.
    """
    from miniautogen.backends.engine_resolver import EngineResolver
    from miniautogen.core.contracts.run_context import RunContext
    from miniautogen.core.runtime.agent_runtime import AgentRuntime
    from miniautogen.core.runtime.agent_sandbox import AgentFilesystemSandbox
    from miniautogen.core.runtime.builtin_tools import BuiltinToolRegistry
    from miniautogen.core.runtime.composite_tool_registry import CompositeToolRegistry
    from miniautogen.core.runtime.delegation_router import ConfigDelegationRouter
    from miniautogen.core.runtime.filesystem_tool_registry import FileSystemToolRegistry
    from miniautogen.core.runtime.persistent_memory import PersistentMemoryProvider

    resolver = self._engine_resolver or EngineResolver()

    # Build delegation router
    delegation_configs: dict[str, dict[str, Any]] = {}
    for agent_name, spec in agent_specs.items():
        delegation_configs[agent_name] = {
            "allow_delegation": spec.delegation.allow_delegation,
            "can_delegate_to": list(spec.delegation.can_delegate_to),
            "context_isolation": spec.delegation.context_isolation,
        }
    delegation_router = ConfigDelegationRouter(delegation_configs)

    run_context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )

    runtimes: dict[str, AgentRuntime] = {}

    for agent_name, spec in agent_specs.items():
        config_dir = workspace / ".miniautogen" / "agents" / agent_name

        # 1. Fresh driver per agent
        engine_profile = spec.engine_profile or "default"
        driver = resolver.create_fresh_driver(engine_profile, config)

        # 2. Sandbox (uses actual constructor signature)
        sandbox = AgentFilesystemSandbox(
            agent_name=agent_name,
            workspace=workspace,
        )

        # 3. Composite tool registry: user tools (FileSystem) > builtin tools
        fs_registry = FileSystemToolRegistry(
            config_dir / "tools.yml", workspace, sandbox
        )
        builtin_registry = BuiltinToolRegistry(workspace, sandbox)
        tool_registry = CompositeToolRegistry([fs_registry, builtin_registry])

        # 4. Persistent memory
        memory = PersistentMemoryProvider(config_dir / "memory")

        # 5. System prompt: prompt.md override or spec fields (ASYNC I/O)
        prompt_path = anyio.Path(config_dir / "prompt.md")
        if await prompt_path.is_file():
            system_prompt = await prompt_path.read_text()
        else:
            system_prompt = _build_prompt_from_spec(spec)

        # 6. Compose AgentRuntime
        rt = AgentRuntime(
            agent_id=agent_name,
            driver=driver,
            run_context=run_context,
            event_sink=self.event_sink,
            system_prompt=system_prompt,
            hooks=[],
            memory=memory,
            tool_registry=tool_registry,
            delegation=delegation_router,
        )
        runtimes[agent_name] = rt

    # Register agents in delegation router
    for agent_name, rt in runtimes.items():
        delegation_router.register_agent(agent_name, rt)

    return runtimes


def _build_prompt_from_spec(spec: AgentSpec) -> str | None:
    """Build system prompt from AgentSpec fields (role, goal, backstory)."""
    parts: list[str] = []
    if spec.role:
        parts.append(f"Role: {spec.role}")
    if spec.goal:
        parts.append(f"Goal: {spec.goal}")
    if spec.backstory:
        parts.append(f"Backstory: {spec.backstory}")
    return "\n".join(parts) or None
```

#### 3.3 PipelineRunner.run_from_config() — Config-driven flow execution

```python
async def run_from_config(
    self,
    *,
    flow_config: FlowConfig,
    agent_specs: dict[str, AgentSpec],
    workspace: Path,
    config: WorkspaceConfig,
    pipeline_input: str | None = None,
    run_id: str | None = None,
) -> RunResult:
    """Execute a flow defined entirely in YAML config.

    This is the config-driven execution path. When a FlowConfig has
    `mode` + `participants` (instead of `target`), this method:
    1. Builds AgentRuntimes from agent specs
    2. Constructs a coordination plan from config
    3. Creates and runs the appropriate coordination runtime
    """
    run_id = run_id or str(uuid4())

    # Validate participants exist in agent_specs
    for name in flow_config.participants:
        if name not in agent_specs:
            raise ConfigurationError(
                f"Flow participant '{name}' not found in agent specs. "
                f"Available: {list(agent_specs.keys())}"
            )

    # Build agent runtimes (async)
    runtimes = await self._build_agent_runtimes(
        agent_specs=agent_specs,
        workspace=workspace,
        config=config,
        run_id=run_id,
    )

    try:
        # Initialize all runtimes (start sessions, load memory)
        for rt in runtimes.values():
            await rt.initialize()

        # Build coordination plan and runtime from config
        plan, runtime = _build_coordination_from_config(
            flow_config=flow_config,
            runtimes=runtimes,
            event_sink=self.event_sink,
            pipeline_input=pipeline_input,
        )

        # Emit run_started event
        await self.event_sink.emit(ExecutionEvent(
            event_type=EventType.RUN_STARTED,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            payload={"mode": flow_config.mode, "participants": flow_config.participants},
        ))

        # Execute the coordination runtime
        result = await runtime.run(plan)

        # Emit run_completed event
        await self.event_sink.emit(ExecutionEvent(
            event_type=EventType.RUN_COMPLETED,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            payload={"status": "completed"},
        ))

        return RunResult(status=RunStatus.COMPLETED, output=result)

    except Exception as exc:
        await self.event_sink.emit(ExecutionEvent(
            event_type=EventType.RUN_FAILED,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            payload={"error": str(exc)},
        ))
        raise
    finally:
        # Close all runtimes (persist memory, close sessions)
        for rt in runtimes.values():
            await rt.close()
```

#### 3.4 _build_coordination_from_config() — Plan factory

```python
def _build_coordination_from_config(
    *,
    flow_config: FlowConfig,
    runtimes: dict[str, AgentRuntime],
    event_sink: EventSink,
    pipeline_input: str | None = None,
) -> tuple[Any, Any]:
    """Build a coordination plan and runtime from FlowConfig.

    Returns:
        (plan, runtime) tuple ready for runtime.run(plan).
    """
    mode = flow_config.mode
    participants = [runtimes[name] for name in flow_config.participants]

    if mode == "workflow":
        from miniautogen.core.contracts.coordination import WorkflowPlan, WorkflowStep

        steps = [
            WorkflowStep(
                agent_id=name,
                task=pipeline_input or f"Execute task as {name}",
            )
            for name in flow_config.participants
        ]
        plan = WorkflowPlan(steps=steps)

        from miniautogen.core.runtime.workflow_runtime import WorkflowRuntime
        runtime = WorkflowRuntime(
            agents={name: runtimes[name] for name in flow_config.participants},
            event_sink=event_sink,
        )
        return plan, runtime

    elif mode == "deliberation":
        from miniautogen.core.contracts.coordination import DeliberationPlan

        plan = DeliberationPlan(
            topic=pipeline_input or "Deliberate on the given task",
            max_rounds=flow_config.max_rounds,
            participants=flow_config.participants,
            leader=flow_config.leader,
        )

        from miniautogen.core.runtime.deliberation_runtime import DeliberationRuntime
        runtime = DeliberationRuntime(
            agents={name: runtimes[name] for name in flow_config.participants},
            event_sink=event_sink,
        )
        return plan, runtime

    elif mode == "loop":
        from miniautogen.core.contracts.coordination import AgenticLoopPlan

        plan = AgenticLoopPlan(
            router=flow_config.router,
            participants=flow_config.participants,
            max_turns=flow_config.max_turns,
            initial_message=pipeline_input or "Begin the task",
        )

        from miniautogen.core.runtime.agentic_loop_runtime import AgenticLoopRuntime
        runtime = AgenticLoopRuntime(
            agents={name: runtimes[name] for name in flow_config.participants},
            event_sink=event_sink,
        )
        return plan, runtime

    elif mode == "composite":
        raise NotImplementedError("Composite config-driven flows require sub-flow resolution — use target callable")

    else:
        raise ConfigurationError(f"Unknown flow mode: {mode}. Valid: workflow, deliberation, loop, composite")
```

#### 3.5 run_pipeline.py — Wire config-driven path

```python
async def execute_pipeline(config, pipeline_name, root, *, timeout, verbose, pipeline_input, resume_run_id):
    flow = config.flows.get(pipeline_name)
    if not flow:
        raise FlowNotFoundError(f"Flow '{pipeline_name}' not found")

    runner = PipelineRunner(
        event_sink=event_sink,
        run_store=run_store,
        engine_resolver=EngineResolver(),
        # ... existing params
    )

    if flow.target:
        # Existing callable path — NO CHANGE
        target_fn = resolve_pipeline_target(flow.target, root)
        return await runner.run_pipeline(target_fn, state)
    else:
        # Config-driven path — NEW
        from miniautogen.cli.services.agent_ops import load_agent_specs
        agent_specs = load_agent_specs(root)
        return await runner.run_from_config(
            flow_config=flow,
            agent_specs=agent_specs,
            workspace=root,
            config=config,
            pipeline_input=pipeline_input,
        )
```

### 4. Diagrama de Dependências

```
run_pipeline.py
  └─ PipelineRunner
       ├─ run_from_config() [NOVO]
       │   ├─ _build_agent_runtimes() [ASYNC, ATUALIZADO]
       │   │   ├─ EngineResolver.create_fresh_driver()    [existente]
       │   │   ├─ CompositeToolRegistry                   [NOVO]
       │   │   │   ├─ FileSystemToolRegistry               [modificado]
       │   │   │   └─ BuiltinToolRegistry                  [NOVO]
       │   │   ├─ PersistentMemoryProvider                 [existente]
       │   │   ├─ AgentFilesystemSandbox                   [existente]
       │   │   └─ AgentRuntime                             [existente]
       │   ├─ _build_coordination_from_config()            [NOVO]
       │   │   └─ WorkflowRuntime | DeliberationRuntime | AgenticLoopRuntime [existentes]
       │   └─ AgentRuntime lifecycle: initialize() → run → close()
       └─ run_pipeline() [existente, callable path, SEM MUDANÇA]
```

---

## Segurança

### Builtin Tool Security Controls

| Controle | Implementação |
|---|---|
| **Path traversal** | `path.resolve()` + `sandbox.can_read()` antes de qualquer I/O |
| **Symlink escape** | `resolve()` segue symlinks e verifica destino final contra sandbox |
| **Grep argument injection** | `--` separator obrigatório antes do pattern |
| **Grep glob traversal** | Rejeita `..` e paths absolutos no parâmetro `glob` |
| **Resource exhaustion (read)** | `MAX_FILE_READ_BYTES = 1MB` — check `stat.st_size` antes de ler |
| **Resource exhaustion (search)** | `--max-count=200`, `MAX_SEARCH_LINE_LENGTH=500` |
| **Resource exhaustion (list)** | `MAX_DIRECTORY_ENTRIES = 1000` |
| **Timeout** | `anyio.fail_after(timeout)` em todas as operações I/O |
| **Tool shadowing** | Warning via logging quando user tool sobrescreve builtin |

### Testes de Segurança Requeridos

```python
# Argument injection prevention
async def test_search_rejects_flag_pattern(registry):
    result = await registry.execute_tool(ToolCall(
        tool_name="search_codebase", call_id="1",
        params={"pattern": "--include=*.env -r /etc"}
    ))
    assert "/etc/passwd" not in (result.output or "")

# Symlink escape
async def test_read_file_rejects_symlink_outside(registry, tmp_path):
    link = tmp_path / "workspace" / "escape"
    link.symlink_to("/etc/passwd")
    result = await registry.execute_tool(ToolCall(
        tool_name="read_file", call_id="1", params={"path": str(link)}
    ))
    assert not result.success

# File size limit
async def test_read_file_rejects_oversized(registry, tmp_path):
    huge = tmp_path / "workspace" / "huge.bin"
    huge.write_bytes(b"x" * 2_000_000)
    result = await registry.execute_tool(ToolCall(
        tool_name="read_file", call_id="1", params={"path": str(huge)}
    ))
    assert not result.success
    assert "too large" in result.error.lower()

# Directory entry cap
async def test_list_caps_entries(registry, tmp_path):
    d = tmp_path / "workspace" / "big"
    d.mkdir()
    for i in range(2000):
        (d / f"f{i}.txt").touch()
    result = await registry.execute_tool(ToolCall(
        tool_name="list_directory", call_id="1", params={"path": str(d)}
    ))
    assert len(result.output.splitlines()) <= 1001  # 1000 + truncation message
```

---

## Dependências

| Dependência | Tipo | Estado |
|---|---|---|
| AgentRuntime compositor | Interna | Implementado (Tasks 1-6) |
| PersistentMemoryProvider | Interna | Implementado |
| FileSystemToolRegistry | Interna | Implementado (precisa refactor) |
| AgentFilesystemSandbox | Interna | Implementado |
| EngineResolver.create_fresh_driver() | Interna | Implementado |
| Coordination runtimes (4) | Interna | Implementados |
| anyio | Externa (pip) | >=4.0 (já instalado) |

---

## Fases de Implementação

| Fase | Componente | Dependência |
|---|---|---|
| 1 | BuiltinToolRegistry + testes (incl. security tests) | Nenhuma |
| 2 | CompositeToolRegistry + testes | Fase 1 |
| 3 | Refactor FileSystemToolRegistry (remover hack builtin, skip builtin na _load) | Fase 2 |
| 4 | FlowConfig schema update + validation + testes | Nenhuma (paralelo) |
| 5 | load_agent_specs() + testes | Nenhuma (paralelo) |
| 6 | PipelineRunner factory atualizado (async, Composite, PersistentMemory, prompt.md, sandbox) | Fases 1-3 |
| 7 | _build_coordination_from_config() + testes | Fase 4 |
| 8 | PipelineRunner.run_from_config() com lifecycle (initialize/close) | Fases 6-7 |
| 9 | run_pipeline.py wiring (config-driven path) | Fases 5, 8 |
| 10 | Testes de integração E2E (mag init → mag run config-driven) | Fase 9 |
| 11 | Atualizar exports em api.py + docs | Fase 10 |

---

## Notas Adicionais

- **Sem novos EventTypes:** Os 69 existentes cobrem todo o ciclo (AGENT_INITIALIZED, AGENT_MEMORY_LOADED, etc.)
- **Sem novos errors:** `ConfigurationError` já existe na taxonomia canônica
- **LiteLLM driver:** Fora do escopo — feature separada
- **MCP integration:** Fora do escopo — futuro registry no CompositeToolRegistry
- **Composite mode:** Config-driven composite requer resolução de sub-flows — fora do escopo MVP, usar target callable
- **`search_codebase` usa grep externo:** Cross-platform (macOS/Linux nativo, Git for Windows inclui grep)
- **Referências:** [agent-runtime-compositor.md](.specs/agent-runtime-compositor.md), [architecture/07-agent-anatomy.md](docs/pt/architecture/07-agent-anatomy.md)
