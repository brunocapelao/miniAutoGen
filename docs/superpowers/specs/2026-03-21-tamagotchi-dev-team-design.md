# E2E Demo: AI Dev Team Builds a Terminal Tamagotchi

## Contrato de Prompt (G/C/FC)

- **Goal:** Criar `examples/tamagotchi-dev-team/` — exemplo e2e onde 4 agentes AI (Gemini CLI) desenvolvem um Tamagotchi de terminal, demonstrando os 3 modos de coordenacao, event system, e policies.
- **Constraint:** Nenhuma modificacao em `miniautogen/core/`. Consumidor puro do SDK. PipelineRunner como unico executor.
- **Failure Condition:** Se `python workspace/tamagotchi.py` nao rodar, ou se algum dos 3 modos de coordenacao nao for exercitado.

## Success Criteria

- [ ] `python run.py` executa o pipeline completo sem erros
- [ ] `python workspace/tamagotchi.py` inicia um jogo funcional (responde a pelo menos 3 inputs: feed, play, sleep)
- [ ] Workflow mode exercitado (Architect -> Developer -> Tester sequencial)
- [ ] Deliberation mode exercitado (3 agentes revisam em ciclo)
- [ ] Outer loop itera ate Tech Lead aprovar (max 3 iteracoes)
- [ ] Event stream impresso com pelo menos RUN_STARTED, COMPONENT_FINISHED, RUN_FINISHED
- [ ] Funciona com Gemini CLI como unico engine

---

## Architecture

### Agents

| Agent | Role | Coordination Role |
|-------|------|-------------------|
| **Architect** | Designs the game structure, modules, API | Workflow step 1, Deliberation participant |
| **Developer** | Writes Python code for the Tamagotchi | Workflow step 2, Deliberation participant |
| **Tester** | Writes and runs tests, reports bugs | Workflow step 3, Deliberation participant |
| **Tech Lead** | Reviews consolidated report, approves or requests changes | Quality gate (outer loop decision) |

### Coordination Flow

```
OUTER LOOP (manual loop in run.py, max 3 iterations)
│
├── Iteration N:
│   │
│   ├── PHASE 1: Build (Workflow Mode via WorkflowRuntime)
│   │   Step 1: Architect → design spec / improvement plan
│   │   Step 2: Developer → implement code based on spec + TL feedback
│   │   Step 3: Tester → write tests, run them, report results
│   │
│   ├── PHASE 2: Review (Deliberation Mode via DeliberationRuntime)
│   │   Participants: Architect, Developer, Tester
│   │   Each reviews the current state from their perspective
│   │   Leader (Architect) consolidates into a review report
│   │
│   └── PHASE 3: Decision (Tech Lead — direct agent call)
│       Receives: review report + test results + workspace file contents
│       Output: JSON { "verdict": "APPROVED"|"NEEDS_WORK", "feedback": "..." }
│       If NEEDS_WORK → feedback injected into next iteration context
│
└── Exit: Tech Lead verdict == APPROVED → done
```

### Outer Loop Implementation Strategy

**Approach: Manual loop in `run.py`** (not AgenticLoopRuntime, not CompositeRuntime)

Rationale: The outer loop composes Workflow + Deliberation + a single agent call per iteration. Neither `AgenticLoopRuntime` (designed for flat agent routing) nor `CompositeRuntime` (no iteration) fits this pattern. A manual `for` loop in `run.py` that calls `PipelineRunner` per phase is the simplest, most readable, and most compliant approach. Each phase still uses PipelineRunner as the sole executor.

```python
for iteration in range(MAX_ITERATIONS):
    # Phase 1: Workflow — build
    build_result = await runner.run(workflow_pipeline, build_context)

    # Phase 2: Deliberation — review
    review_result = await runner.run(deliberation_pipeline, review_context)

    # Phase 3: Tech Lead — single agent turn
    tl_decision = await tech_lead_agent.evaluate(review_result)

    if tl_decision.verdict == "APPROVED":
        break
    # else: inject feedback into next iteration's context
```

### Data Flow: How Agents Read/Write Files

**Mechanism: Gemini CLI writes files directly** (via its own shell/file capabilities)

```
run.py sets CWD for agent sessions to workspace/
    │
    ├── Architect: reads nothing (first iteration) or reads current code
    │   → outputs design spec as text in agent response
    │
    ├── Developer: receives Architect's spec + TL feedback as prompt context
    │   → Gemini CLI writes tamagotchi.py directly to workspace/
    │   → agent response confirms what was written
    │
    ├── Tester: receives Developer's report
    │   → Gemini CLI writes test_tamagotchi.py and runs `python test_tamagotchi.py`
    │   → agent response includes test results (pass/fail + output)
    │
    └── Between iterations: run.py reads workspace/ files
        → injects current file contents into next iteration's context
        → this ensures all agents see the latest state
```

**Key**: `run.py` reads `workspace/tamagotchi.py` and `workspace/test_tamagotchi.py` between phases to inject into agent prompts. This ensures context propagation without depending on agent memory.

### Engine Configuration

```yaml
# miniautogen.yaml
project:
  name: tamagotchi-dev-team
  version: "0.1.0"
defaults:
  engine: gemini
engines:
  gemini:
    provider: gemini-cli
    model: gemini-2.5-pro
    timeout_seconds: 120
```

### Policies

| Policy | SDK Mapping | Configuration |
|--------|-------------|---------------|
| **Timeout** | `anyio.fail_after()` wrapping each phase | 2 min per agent turn, 10 min total |
| **Budget tracking** | `InMemoryEventSink` + post-run token count from events | Log per-phase, display total at end |
| **Max iterations** | `range(3)` in `run.py` outer loop | Hard limit, force-stop with warning |

Note: The Tech Lead's decision is NOT an `ApprovalGate` policy (which expects human-in-the-loop). It is a direct agent call that returns a structured verdict. The relevant events are `COMPONENT_STARTED`/`COMPONENT_FINISHED` for the Tech Lead step, not `APPROVAL_*`.

### Event Observability

Events captured per phase:
- `RUN_STARTED` / `RUN_FINISHED` — per PipelineRunner.run() call
- `COMPONENT_STARTED` / `COMPONENT_FINISHED` — per agent step in workflow
- `AGENT_REPLIED` — with agent output content
- `DELIBERATION_ROUND_COMPLETED` — during review phase
- `BACKEND_TURN_STARTED` / `BACKEND_TURN_COMPLETED` — Gemini CLI turns

Final summary printed:
```
=== Development Complete ===
Iterations: 2/3
Total events: 47
Total time: 4m 23s
Phases: build x2, review x2, tech-lead x2
Result: APPROVED
Play your game: python workspace/tamagotchi.py
```

---

## Agent Prompt Templates

### Architect (iteration 1)

```
You are a software architect designing a terminal Tamagotchi game in Python.

Design a simple terminal Tamagotchi game with these features:
- A pet with stats: hunger, happiness, energy (0-100, start at 50)
- Actions: feed (+20 hunger), play (+20 happiness, -10 energy), sleep (+30 energy, -10 hunger)
- Stats decay by 5 each turn
- Game over when any stat hits 0
- ASCII art for pet states (happy, hungry, tired, dead)
- Turn-based loop: show status → player chooses action → update stats → repeat

Output a clear design document with:
1. Module structure (single file tamagotchi.py)
2. Classes/functions needed
3. Game loop pseudocode
4. ASCII art specs
```

### Architect (iteration N > 1)

```
You are a software architect. The Tech Lead reviewed the current Tamagotchi implementation and requested changes.

Current code:
{workspace/tamagotchi.py contents}

Current tests:
{workspace/test_tamagotchi.py contents}

Tech Lead feedback:
{tech_lead_feedback}

Review report:
{review_report}

Create an updated design plan addressing the feedback. Focus only on what needs to change.
```

### Developer

```
You are a Python developer. Implement the Tamagotchi game based on the architect's design.

Design spec:
{architect_output}

{if iteration > 1: "Previous code:\n{workspace/tamagotchi.py contents}\n\nTech Lead feedback:\n{feedback}"}

Write the complete tamagotchi.py file to the workspace/ directory. The file must:
- Be runnable with `python tamagotchi.py`
- Include all game logic in a single file
- Handle invalid input gracefully
- Exit cleanly on Ctrl+C

Write the file now.
```

### Tester

```
You are a QA engineer. Test the Tamagotchi game that was just implemented.

Current code:
{workspace/tamagotchi.py contents}

1. Write test_tamagotchi.py to workspace/ with unit tests covering:
   - Pet initialization (stats start at 50)
   - Feed action increases hunger
   - Play action increases happiness, decreases energy
   - Sleep action increases energy, decreases hunger
   - Stats decay each turn
   - Game over when stat hits 0

2. Run the tests: python workspace/test_tamagotchi.py

3. Report results: which tests pass, which fail, any errors.
```

### Tech Lead

```
You are a Tech Lead evaluating the team's work on a Tamagotchi game.

Review report:
{review_report}

Test results:
{tester_output}

Current code:
{workspace/tamagotchi.py contents}

Evaluate the work. Respond with ONLY a JSON object:
{
  "verdict": "APPROVED" or "NEEDS_WORK",
  "feedback": "specific actionable feedback if NEEDS_WORK, or congratulations if APPROVED"
}

Criteria for APPROVED:
- Code runs without errors
- At least 4/6 core tests pass
- Game loop works (feed, play, sleep actions functional)
- Code is clean and readable

If ANY test crashes or the game doesn't start, verdict MUST be NEEDS_WORK.
```

---

## File Structure

```
examples/tamagotchi-dev-team/
├── miniautogen.yaml          # Project config (Gemini CLI engine)
├── agents/
│   ├── architect.yaml        # Design agent config
│   ├── developer.yaml        # Code agent config
│   ├── tester.yaml           # QA agent config
│   └── tech_lead.yaml        # Quality gate agent config
├── run.py                    # Entry point — orchestrates the full pipeline
└── workspace/                # Working directory (created at runtime)
    ├── tamagotchi.py          # (generated) The game
    └── test_tamagotchi.py     # (generated) Tests
```

Note: `flows/build-tamagotchi.yaml` removed — the orchestration is fully in `run.py` using SDK primitives directly. This is intentional: the demo shows the SDK's Python API, not YAML-driven flows.

---

## Error Handling

| Error | Strategy |
|-------|----------|
| Gemini CLI not installed | Pre-flight check in run.py, clear error message |
| Gemini CLI not authenticated | Pre-flight check, link to auth docs |
| Agent produces unparseable output | Retry once, then skip to next phase with warning |
| Tests crash Python | Tester catches subprocess errors, reports as test failure |
| Tech Lead returns invalid JSON | Default to NEEDS_WORK with "invalid response" feedback |
| Max iterations reached | Force exit with "Max iterations reached" warning |
| Total timeout exceeded | `anyio.fail_after()` kills the run, prints partial results |

---

## Constraints

- No modifications to `miniautogen/core/` — pure SDK consumer
- All agent work happens in `workspace/` directory
- Gemini CLI must be installed and authenticated (`gemini` command available)
- Self-contained (no external deps beyond miniautogen + gemini)
- Agent prompts specific enough for Gemini CLI to produce working code
- Outer loop MUST terminate (max 3 iterations)

## Non-Goals

- No TUI integration (standalone script)
- No persistence across runs (fresh workspace each time)
- No multi-model comparison (Gemini only)
- No complex game features (keep Tamagotchi simple)

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| miniautogen | current (SDK) | Orchestration framework |
| anyio | >=4.0 | Async runtime |
| gemini CLI | latest | Backend engine for all agents |
