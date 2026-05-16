# Plano Técnico: TeamRuntime — coordenação peer-to-peer estilo Agent Teams

| Campo         | Valor       |
|---------------|-------------|
| Spec ID       | 015         |
| Data          | 2026-05-16  |
| Complexidade  | Medium      |

---

## Arquitetura Proposta

O `TeamRuntime` é introduzido como **quarto modo canônico de coordenação**, paralelo a `WorkflowRuntime`, `DeliberationRuntime` e `AgenticLoopRuntime`. Reaproveita 100% do ciclo `run_from_config` do `PipelineRunner`: o dispatcher central (`_build_coordination_from_config`) ganha um ramo `mode == "team"` que retorna `(TeamPlan, TeamRuntime)` exatamente como os outros modos.

Concorrência é estruturada via **um único `anyio.create_task_group`** aninhado dentro do escopo do `run()` do runtime. Esse escopo é o ponto único de cancelamento — cancelar o `run_id` do team (via `ExecutionPolicy.cancel_run` futuro ou `CancelScope` aninhado de um composite) propaga atomicamente para todos os teammates ativos. Política `on_teammate_failure="abort_team"` é implementada chamando `task_group.cancel_scope.cancel()` no primeiro `TEAMMATE_FAILED` recebido; `"isolate"` simplesmente captura a exceção dentro da coroutine do teammate e converte em `ContributionSummary` de erro.

Cada teammate roda como uma chamada `agent_runtime.process(prompt)` (não um `run_from_config` aninhado — isso seria spec 016). Isolamento de contexto é garantido porque cada `AgentRuntime` mantém seu próprio `Conversation`/`session_id` e nunca compartilha estado com o lead — basta não passar o conversation do lead nem como input nem como prompt.

O lead roda **depois** da fase concorrente, recebendo um dict `{teammate_name: ContributionSummary}` como `input_payload`. A v1 não exige que o lead seja um `AgentRuntime` separado do registry — qualquer agente declarado em `agent_specs` serve.

### Módulos Afetados

| Módulo / Caminho                                                | Tipo de Alteração |
|------------------------------------------------------------------|--------------------|
| `miniautogen/core/contracts/coordination.py`                     | Alterado (+`CoordinationKind.TEAM`, +`TeamPlan`, +`ContributionSummary`) |
| `miniautogen/core/contracts/run_context.py`                      | Alterado (+`parent_run_id: str \| None = None`, manter `frozen`) |
| `miniautogen/core/events/types.py`                               | Alterado (+6 `TEAM_*` `EventType` + set agregador `TEAM_EVENT_TYPES`) |
| `miniautogen/core/runtime/team_runtime.py`                       | **Novo** — `TeamRuntime` |
| `miniautogen/core/runtime/pipeline_runner.py`                    | Alterado — `_build_coordination_from_config` ganha ramo `mode == "team"` |
| `miniautogen/cli/config.py`                                      | Alterado — `FlowConfig` aceita `mode="team"` + novos campos `lead`, `teammates`, `on_teammate_failure`, `max_concurrent_teammates`, `lead_prompt`, `teammate_prompts` |
| `miniautogen/cli/commands/run.py`                                | Alterado — gate `MINIAUTOGEN_EXPERIMENTAL_TEAMS` quando flow resolve para `mode="team"`; mensagem de erro clara |
| `miniautogen/cli/services/run_pipeline.py`                       | **INTOCADO** (já roteia por `flow.mode` genérico) |
| `tests/core/runtime/test_team_runtime_bootstrap.py`              | **Novo** |
| `tests/core/runtime/test_team_runtime_parallel.py`               | **Novo** |
| `tests/core/runtime/test_team_runtime_isolation.py`              | **Novo** |
| `tests/core/runtime/test_team_runtime_failure_isolate.py`        | **Novo** |
| `tests/core/runtime/test_team_runtime_failure_abort.py`          | **Novo** |
| `tests/core/runtime/test_team_runtime_cancellation.py`           | **Novo** |
| `tests/core/runtime/test_team_runtime_events.py`                 | **Novo** |
| `tests/cli/test_team_command.py`                                 | **Novo** |
| `tests/architecture/test_team_runtime_isolation.py`              | **Novo** (lint arquitetural — sem imports de adapters) |
| `miniautogen/core/runtime/agent_runtime.py`                      | **INTOCADO** (consumido como caixa-preta) |
| `miniautogen/core/runtime/workflow_runtime.py`                   | **INTOCADO** |
| `miniautogen/core/runtime/deliberation_runtime.py`               | **INTOCADO** |
| `miniautogen/core/runtime/agentic_loop_runtime.py`               | **INTOCADO** |
| `miniautogen/policies/**`                                        | **INTOCADO** |
| `miniautogen/adapters/**`, `miniautogen/backends/**`             | **INTOCADO** |
| `miniautogen/schemas.py`                                         | **INTOCADO** (schema do YAML vive em `cli/config.py`) |

### Diagrama de fluxo

```
                          PipelineRunner.run_from_config
                                      │
                                      ▼
                _build_coordination_from_config(flow.mode == "team")
                                      │
                                      ▼
                           TeamRuntime.run(...)
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       ▼                              ▼                              ▼
   emit TEAM_STARTED          validate TeamPlan          build per-teammate
                              (lead/teammates           RunContext (parent_run_id=team.run_id)
                               in registry, no dup)
                                      │
                                      ▼
                       async with anyio.create_task_group() as tg:
                       (CancelScope = team-wide structured concurrency)
                                      │
              ┌──────────────────┬────┴────┬──────────────────┐
              ▼                  ▼         ▼                  ▼
        teammate_a()       teammate_b()   …            optional Semaphore
        emit SPAWNED       emit SPAWNED                (max_concurrent)
        await rt.process   await rt.process
        emit FINISHED      emit FAILED ──┐
        store summary      store summary │
              │                  │       │
              └─────────┬────────┘       │
                        ▼                ▼
            collect {name: ContributionSummary}
                        │                │
        on_teammate_failure="abort_team" │
                        │  ◄─cancel scope on first FAILED
                        ▼                ▼
                    lead runs               (lead skipped)
                    process(summaries)      emit TEAM_FAILED
                        │                       ▲
                        ▼                       │
                  emit TEAM_FINISHED ────────────
                        │
                        ▼
                   return RunResult
```

---

## Contratos e Interfaces

### `CoordinationKind` + `TeamPlan` (em `core/contracts/coordination.py`)

```python
class CoordinationKind(str, Enum):
    WORKFLOW = "workflow"
    DELIBERATION = "deliberation"
    AGENTIC_LOOP = "agentic_loop"
    TEAM = "team"  # NEW

class ContributionSummary(BaseModel):
    teammate: str
    status: Literal["finished", "failed", "cancelled"]
    output: Any = None
    error_category: ErrorCategory | None = None
    error_message: str | None = None

class TeamPlan(CoordinationPlan):
    lead_agent: str
    teammates: list[str] = Field(min_length=1)
    lead_prompt: str | None = None
    teammate_prompts: dict[str, str] = Field(default_factory=dict)
    on_teammate_failure: Literal["isolate", "abort_team"] = "isolate"
    max_concurrent_teammates: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _no_dup_no_self(self) -> "TeamPlan":
        if len(set(self.teammates)) != len(self.teammates):
            raise ValueError("teammates must be unique")
        if self.lead_agent in self.teammates:
            raise ValueError("lead_agent cannot also be a teammate")
        return self
```

### `RunContext` (em `core/contracts/run_context.py`)

```python
class RunContext(MiniAutoGenBaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    started_at: datetime
    correlation_id: str
    state: FrozenState = Field(default_factory=FrozenState)
    input_payload: Any = None
    timeout_seconds: float | None = None
    namespace: str | None = None
    metadata: tuple[tuple[str, Any], ...] = ()
    parent_run_id: str | None = None  # NEW — optional for retro-compat

    def model_copy(self, *, update=None, **kwargs):
        allowed = {"state", "metadata", "input_payload", "parent_run_id"}  # extend allowlist
        ...
```

**Trade-off resolvido:** o campo é `Optional[str] = None` para não quebrar nenhum construtor existente. O `model_copy` allowlist é estendida para permitir derivar contextos filhos sem código defensivo nos call sites legados.

### Novos `EventType` (em `core/events/types.py`)

```python
class EventType(str, Enum):
    ...
    # Team coordination events
    TEAM_STARTED = "team_started"
    TEAMMATE_SPAWNED = "teammate_spawned"
    TEAMMATE_FINISHED = "teammate_finished"
    TEAMMATE_FAILED = "teammate_failed"
    TEAM_FINISHED = "team_finished"
    TEAM_FAILED = "team_failed"

TEAM_EVENT_TYPES: set[EventType] = {
    EventType.TEAM_STARTED,
    EventType.TEAMMATE_SPAWNED,
    EventType.TEAMMATE_FINISHED,
    EventType.TEAMMATE_FAILED,
    EventType.TEAM_FINISHED,
    EventType.TEAM_FAILED,
}
```

### `TeamRuntime` esqueleto (em `core/runtime/team_runtime.py`)

```python
class TeamRuntime:
    kind: CoordinationKind = CoordinationKind.TEAM

    def __init__(
        self,
        runner: PipelineRunner,
        agent_registry: dict[str, Any] | None = None,
        timeout_policy: TimeoutPolicy | None = None,
    ) -> None:
        self._runner = runner
        self._registry = agent_registry or {}
        self._timeout_policy = timeout_policy
        self._logger = get_logger(__name__)

    async def run(
        self, agents: list[Any], context: RunContext, plan: TeamPlan,
    ) -> RunResult:
        # 1. validate (CONFIGURATION error → RunResult.FAILED + TEAM_FAILED)
        # 2. emit TEAM_STARTED
        # 3. concurrently spawn teammates inside one task_group
        # 4. depending on on_teammate_failure: collect or cancel
        # 5. invoke lead with {teammate: ContributionSummary}
        # 6. emit TEAM_FINISHED / TEAM_FAILED + return RunResult
        ...
```

### Boundary explícito de `team_runtime.py`

| Permitido importar                                         | Proibido importar                              |
|-------------------------------------------------------------|------------------------------------------------|
| `anyio`                                                     | `litellm`, `openai`, `google.generativeai`, … |
| `miniautogen.core.contracts.*`                              | `miniautogen.adapters.*`                       |
| `miniautogen.core.events.types`                             | `miniautogen.backends.*`                       |
| `miniautogen.core.runtime.pipeline_runner` (tipo)           | `miniautogen.cli.*`                            |
| `miniautogen.core.runtime.classifier` (classify_error)      | `jinja2`, `langchain`, etc.                    |
| `miniautogen.observability.get_logger`                      | `miniautogen.schemas` (esquema YAML)           |
| `miniautogen.policies.timeout_policy` (já consumida pelos peers) |                                                |

Reforço via teste arquitetural (`tests/architecture/test_team_runtime_isolation.py`) que faz AST scan de `team_runtime.py` e falha se houver `import` fora da allowlist.

### CLI — gating experimental

```python
# miniautogen/cli/commands/run.py (trecho novo logo após resolver flow)
flow = config.flows[pipeline_name]
if flow.mode == "team" and os.environ.get("MINIAUTOGEN_EXPERIMENTAL_TEAMS") != "1":
    raise click.UsageError(
        "Team runtime is experimental. "
        "Set MINIAUTOGEN_EXPERIMENTAL_TEAMS=1 to enable."
    )
```

### `FlowConfig` — extensão YAML

```yaml
flows:
  review_team:
    mode: team
    participants: [orchestrator, legal_reviewer, security_reviewer, architect_reviewer]
    lead: orchestrator
    teammates: [legal_reviewer, security_reviewer, architect_reviewer]
    on_teammate_failure: isolate
    teammate_prompts:
      legal_reviewer: "Analise compliance LGPD do PR."
      security_reviewer: "Procure CVEs e secrets vazados."
      architect_reviewer: "Verifique se há violação dos invariantes do CLAUDE.md."
```

Validação Pydantic adicional em `FlowConfig`:

```python
@model_validator(mode="after")
def validate_team_mode(self) -> "FlowConfig":
    if self.mode == "team":
        if not self.lead:
            raise ValueError("Team mode requires 'lead'")
        if not self.teammates:
            raise ValueError("Team mode requires 'teammates' (>=1)")
    return self
```

**Trade-off resolvido:** introduzir campos novos em `FlowConfig` em vez de uma sub-classe `TeamFlowConfig` mantém o roteamento atual de `flow.mode` sem refactor amplo do `run_pipeline.py`. Custo: `FlowConfig` fica polimórfica — aceitável dado que já o é para `workflow|deliberation|loop`.

---

## Riscos e Mitigações

| Risco                                                                 | Impacto | Mitigação                                                                                                  |
|------------------------------------------------------------------------|---------|------------------------------------------------------------------------------------------------------------|
| `parent_run_id` em `RunContext` quebra serialização cacheada por terceiros | Médio   | Adicionar como `Optional[str] = None`; estender allowlist de `model_copy`; novo teste de serialização `model_dump()` para garantir retrocompatibilidade do payload |
| Cancelamento de task group mascara erros reais quando `on_teammate_failure="abort_team"` | Alto    | Capturar `Exception` original dentro da coroutine do teammate ANTES de chamar `cancel_scope.cancel()`; passar `error_category` + `message` no `TEAM_FAILED`; `BaseExceptionGroup` desempacotado igual ao padrão de `workflow_runtime` |
| Teammate "vaza" o histórico do lead via `agent_runtime` compartilhado    | Alto    | Cada agent declarado em YAML resolve para **uma instância distinta** já hoje (`_build_agent_runtimes`); teste explícito `test_team_runtime_isolation.py` injeta "SEGREDO" no lead e varre conversations dos teammates |
| `max_concurrent_teammates` deadlock se semáforo for mal posicionado     | Médio   | Usar `anyio.Semaphore(n)` adquirido **dentro** da coroutine (não fora do `task_group.start_soon`); teste com `n=1` e 3 teammates valida sequenciamento sem deadlock |
| Eventos `TEAMMATE_SPAWNED` chegam fora de ordem por preempção do scheduler | Baixo   | Spec não prescreve ordem entre teammates; teste `test_team_runtime_events.py` valida apenas (a) cardinalidade, (b) que cada SPAWNED precede seu FINISHED do mesmo `sub_run_id`, (c) TEAM_STARTED é o primeiro e TEAM_FINISHED é o último |
| Lead recebe `dict[teammate, ContributionSummary]` mas espera string/Conversation | Médio   | Documentar contrato no docstring do `TeamPlan.lead_prompt`; expor helper `_format_contributions_for_lead()` privado que serializa para string compatível com `agent_runtime.process()`; cobrir em `test_team_runtime_parallel.py` |
| Composição (workflow → team → workflow) reaproveita `run_id` errado     | Médio   | Plano explícito: o `RunContext` passado ao `TeamRuntime` tem o `run_id` do team-level; teammates derivam `parent_run_id = context.run_id`. Smoke test composto adiado para spec separada, mas teste atual valida que o context filho tem `parent_run_id` correto |
| Falta de gate experimental permite produção acidental                  | Baixo   | Gate na CLI + warning na `CoordinationKind.TEAM` docstring marcando como `.. stability:: experimental` (mesma convenção de `SubrunRequest`) |
| `_build_coordination_from_config` cresce a cada modo novo               | Baixo   | Manter padrão atual (if-chain); refactor para registry só quando tivermos o 5º modo |

---

## Estimativa de Complexidade

| Aspecto              | Estimativa                                                          |
|----------------------|---------------------------------------------------------------------|
| Ficheiros novos      | 10 (1 runtime + 8 testes + 1 arch test)                             |
| Ficheiros alterados  | 5 (`coordination.py`, `run_context.py`, `events/types.py`, `pipeline_runner.py`, `cli/config.py`, `cli/commands/run.py`) |
| Linhas adicionadas   | ~900 (runtime ~350, testes ~450, contratos/glue ~100)               |
| Testes novos         | ~18 (bootstrap 3, parallel 2, isolation 2, failure-isolate 2, failure-abort 2, cancellation 2, events 3, cli 2) |
| Esforço estimado     | **Medium (3-4 dias)** — runtime em si é pequeno; complexidade está em garantir os 7 invariantes de eventos/cancelamento sob AnyIO |

---

## Sequência de Implementação

Test-First obrigatório. Cada bloco "Test" abaixo deve **falhar** ao rodar antes da implementação correspondente existir. A ordem é desenhada para que cada teste novo passe a vermelho com mensagem clara (`ImportError`, `AttributeError`, etc.) e vire verde após o módulo correspondente.

1. **Test arquitetural primeiro:** `tests/architecture/test_team_runtime_isolation.py` que falha com `FileNotFoundError` (módulo `team_runtime.py` ainda não existe). Esse teste fixa o boundary antes de qualquer linha de produção.
2. **Test-first contrato:** `tests/core/runtime/test_team_runtime_bootstrap.py` — espera importar `TeamPlan`, `CoordinationKind.TEAM`, `TeamRuntime`. Falha em `ImportError`.
3. **Test-first eventos:** `tests/core/runtime/test_team_runtime_events.py` — espera os 6 `EventType.TEAM_*` no enum + `TEAM_EVENT_TYPES`. Falha em `AttributeError`.
4. **Test-first parent_run_id:** estender um teste em `tests/core/contracts/test_run_context.py` (ou criar novo `test_run_context_parent.py`) para validar que `RunContext(parent_run_id="...")` aceita e serializa. Falha em `ValidationError` até o campo existir.
5. **Test-first runtime concorrente:** `tests/core/runtime/test_team_runtime_parallel.py` — 3 fakes que dormem 100/200/300ms; total < 350ms (paralelismo real). Usa `MockAgentRuntime` em memória — sem adapter.
6. **Test-first isolamento:** `tests/core/runtime/test_team_runtime_isolation.py` — lead injeta "SEGREDO" no seu Conversation; valida que nenhum teammate vê a string.
7. **Test-first failure isolate:** `tests/core/runtime/test_team_runtime_failure_isolate.py` — 1 teammate em 3 levanta `ValidationError`; os outros 2 terminam; lead recebe summary com `error_category=VALIDATION`.
8. **Test-first failure abort:** `tests/core/runtime/test_team_runtime_failure_abort.py` — `on_teammate_failure="abort_team"`; primeira falha cancela; lead não é invocado; `TEAM_FAILED` emitido com a categoria do erro.
9. **Test-first cancelamento:** `tests/core/runtime/test_team_runtime_cancellation.py` — `CancelScope` externo cancela em <1s; todos teammates emitem `TEAMMATE_FINISHED` com `status="cancelled"`.
10. **Test-first CLI:** `tests/cli/test_team_command.py` — (a) sem env var → `UsageError`; (b) com env var → executa e retorna `RunResult.FINISHED`. Usa workspace fixture mínimo (`teams: review_team`).
11. **Rodar suíte → tudo vermelho.** Confirma que estamos genuinamente test-first.
12. **Implementação 1 (contratos):** adicionar `parent_run_id` em `RunContext` + allowlist de `model_copy`. Roda o teste do passo 4 → verde.
13. **Implementação 2 (enum + plan):** adicionar `CoordinationKind.TEAM`, `ContributionSummary`, `TeamPlan` em `coordination.py`. Os testes 2 e 3 ficam parcialmente verdes (imports OK).
14. **Implementação 3 (eventos):** adicionar os 6 `EventType.TEAM_*` + set agregador. Teste 3 verde.
15. **Implementação 4 (runtime esqueleto):** criar `team_runtime.py` com `validate`, `_emit`, `_spawn_teammate`, `_run_lead`. Aplicar `anyio.create_task_group` + opcional `Semaphore`. Implementar política `isolate` primeiro. Testes 5, 6, 7 verdes. Teste arquitetural (passo 1) também verde se boundary respeitado.
16. **Implementação 5 (abort_team):** adicionar branch que captura primeira exceção real, chama `cancel_scope.cancel()`, e propaga `TEAM_FAILED`. Teste 8 verde.
17. **Implementação 6 (cancelamento):** garantir propagação correta via `with CancelScope() as scope`; emitir `TEAMMATE_FINISHED status=cancelled` em handler `finally` da coroutine. Teste 9 verde.
18. **Implementação 7 (dispatcher):** estender `_build_coordination_from_config` com ramo `mode == "team"`. Reusa `agent_specs` existentes; mapeia campos `flow.lead`, `flow.teammates`, `flow.teammate_prompts`, `flow.on_teammate_failure` para `TeamPlan`.
19. **Implementação 8 (FlowConfig + CLI gate):** estender `cli/config.py` com campos + validator; adicionar gate em `cli/commands/run.py`. Teste 10 verde.
20. **Verde global:** rodar `pytest tests/core/runtime/test_team_runtime_*.py tests/cli/test_team_command.py tests/architecture/test_team_runtime_isolation.py`. Tudo verde + cobertura ≥85% no `team_runtime.py`.
21. **Regressão:** rodar a suíte completa (script equivalente a `run_anyio_tests.sh`). Zero regressões.
22. **Lint + types:** `ruff check`, `mypy miniautogen/core/runtime/team_runtime.py`. Verde.
23. **Smoke manual:** criar `examples/team_review/` com `miniautogen.yaml` + agents; rodar `MINIAUTOGEN_EXPERIMENTAL_TEAMS=1 miniautogen run review_team --input "PR #42"` e validar logs canônicos.
24. **Commits atômicos** seguindo a sequência: (a) contratos, (b) eventos, (c) runtime + testes paralelos/isolamento, (d) políticas failure/cancel, (e) dispatcher + CLI, (f) docs/exemplo.

---

## Notas

- **Por que `parent_run_id` em vez de `team_run_id`?** Decisão herdada da spec. Em código: o campo é genérico o suficiente para servir futuras composições (composite_runtime, sub-agentes como tool, spec 016/017). Custo zero de generalização.
- **Por que lead roda depois (v1)?** Spec 015 entrega o padrão "fan-out + consolidação". Lead-antes (delegação) exige task list compartilhada (spec 016). Implementar lead-depois é ~⅓ da complexidade.
- **Por que `_build_agent_runtimes` não muda?** A função já cria uma `AgentRuntime` por agent declarado no YAML, com `Conversation` própria. Isolamento de contexto é uma propriedade emergente da arquitetura existente — `TeamRuntime` só precisa **não** compartilhar conversation entre lead e teammates, o que é o default ao chamar `process()` em instâncias distintas.
- **Por que não criar um `SubAgentTool` como em Claude Code?** A spec é explícita: teammates aqui não são "tools" do lead, são peers cujo lifecycle é gerenciado pelo runtime. Expor como tool acoplaria ao tool registry e quebraria o modelo "lead consolida ao final".
- **Trade-off do dispatcher:** preferir if-chain em `_build_coordination_from_config` em vez de registry plugin-based mantém alinhamento com os outros 3 ramos existentes. Refactor para registry quando o 5º modo entrar (não nesta spec).
- **Trade-off de `FlowConfig` polimórfico:** evitar `TeamFlowConfig` subclasse reduz blast-radius no `run_pipeline.py` e em validators downstream. Aceitamos um `FlowConfig` mais largo até o esquema YAML ser refatorado para `discriminated union` (futuro).
- **Specs futuras (não cobertas aqui):** `016` (TaskListStore + lead-antes), `017` (MailboxStore peer-to-peer + plan approval), TUI split-pane, persistência/retomada de team runs.
- **Boundary contract reforçado por CI:** o teste arquitetural não-negociável — qualquer PR que adicione `import litellm`, `import openai`, etc. dentro de `team_runtime.py` é bloqueado antes do code review humano.
