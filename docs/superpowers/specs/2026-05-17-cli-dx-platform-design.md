# CLI Developer Experience Platform

**Date:** 2026-05-17
**Status:** Draft
**Approach:** C — Full DX Platform (Config Shell + AI Assistant + Dev Mode + Profiling)

## 1. Vision

Transform the MiniAutoGen CLI into the **best developer experience for building multi-agent systems**. The current CLI is functional but has friction: complex YAML configs without guidance, weak validation, no live feedback loop, and limited debugging tools.

The platform is built in **4 independent modules**, each delivering value on its own. Implementation order matters: Config Shell first (solves the biggest pain), then AI Assistant, then Dev Mode, then Profiling.

## 2. Module 1: Config Shell (`miniautogen config`)

### 2.1 Subcommands

| Command | Description |
|---|---|
| `init` | Interactive wizard: project name, template, provider, API key, agents |
| `shell` | REPL with tab completion: set/get/show/validate/save/diff |
| `doctor` | Static analysis: warnings, suggestions, auto-fix |
| `validate` | Fast validation against Pydantic schema |
| `schema` | Export JSON Schema for IDE integration |
| `show` | Formatted views (agents, flows, engines, tree) |
| `diff` | Show pending/staged changes vs saved |
| `migrate` | Upgrade configs from old formats |

### 2.2 Architecture

```
miniautogen/cli/services/config/
├── __init__.py
├── shell.py           # prompt_toolkit REPL
├── wizard.py          # Rich interactive init
├── doctor.py          # Static analysis engine
├── schema_export.py   # JSON Schema generation
├── diff_engine.py     # Config comparison
├── migration.py       # Format migration
└── models.py          # Config model extensions
```

Dependencies: `prompt_toolkit`, `rich`, `pydantic`, `watchfiles`, `pyyaml`

### 2.3 Init Wizard Flow

1. Detect workspace (empty dir / existing project)
2. Prompt: project name (validated slug)
3. Prompt: template selection (Quickstart | Research Team | Deliberation | Workflow | Blank)
4. Prompt: provider (OpenAI | Anthropic | Gemini | OpenCompat | Local CLI)
5. Prompt: API key (stored in .env, masked input)
6. Show config preview → confirm
7. Write: `miniautogen.yaml`, `.env`, `agents/*.yaml`, `.gitignore`

### 2.4 Shell REPL Design

Built on `prompt_toolkit` with:
- **Tab completion**: context-aware (field names, valid values, agent names)
- **Syntax highlighting**: YAML keys vs values, validation errors colored
- **Multi-line editing**: for complex values
- **Command history**: persisted across sessions
- **Dynamic suggestions**: based on current config state

Commands:
- `get <path>` — read a config value
- `set <path> <value>` — mutate (validated instantly)
- `show [agents|flows|engines|tree]` — formatted views
- `validate` — run Pydantic validation
- `diff` — pending changes
- `save` — persist to disk
- `load [path]` — load a different config
- `ai <query>` — inline AI assistant
- `help [command]` — context-sensitive help
- `exit` / `quit`

### 2.5 Doctor Analysis Rules

| Code | Severity | Rule |
|---|---|---|
| WRN-001 | Warning | Agent has no tools assigned |
| WRN-002 | Warning | Model is not latest (e.g. gpt-4 instead of gpt-4o) |
| WRN-003 | Warning | Flow has no timeout configured |
| WRN-004 | Warning | Duplicate agent IDs across flows |
| WRN-005 | Warning | Engine defined but not referenced |
| WRN-006 | Warning | Agent references undefined engine |
| WRN-007 | Info | Memory profile not configured |
| WRN-008 | Info | No .env file found |
| ERR-001 | Error | Invalid YAML syntax |
| ERR-002 | Error | Schema validation failed |
| ERR-003 | Error | Cycle detected in task DAG |

Each rule includes a human-readable explanation and a machine-actionable fix command.

## 3. Module 2: AI Config Assistant (`miniautogen ai`)

### 3.1 Subcommands

| Command | Description |
|---|---|
| `init "<description>"` | Generate full config from natural language |
| `add "<description>"` | Add agent/tool/flow to existing config |
| `explain` | Explain current config in plain English |
| `fix` | Analyze and auto-fix config issues |

### 3.2 Architecture

```
miniautogen/cli/services/ai_assistant/
├── __init__.py
├── nlp_parser.py      # NL → structured config
├── config_generator.py # Structured → WorkspaceConfig
├── config_explainer.py # WorkspaceConfig → NL
├── auto_fixer.py       # Doctor issues → fixes
└── provider.py         # LLM provider abstraction
```

### 3.3 Implementation Strategy

**Phase 1 (template matching):**
- Pattern match common phrases → template parameters
- "team of N agents" → TeamPlan with N agents
- "web search", "research" → web_search tool
- No LLM dependency required
- Covers ~80% of common use cases

**Phase 2 (LLM-powered):**
- Uses configured engine to interpret complex requests
- Structured output parsing into WorkspaceConfig
- Falls back to Phase 1 if LLM unavailable
- System prompt ensures valid schema-compliant output

### 3.4 Config Shell Integration

The AI assistant is available both as:
- Standalone: `miniautogen ai init "..."` 
- Inline: `config> ai "add a reviewer agent"`

Both paths use the same core logic.

## 4. Module 3: Dev Mode (`miniautogen dev`)

### 4.1 Commands

| Command | Description |
|---|---|
| `dev` | Development mode with watch + hot-reload + run |

### 4.2 Architecture

```
miniautogen/cli/services/dev_mode/
├── __init__.py
├── watcher.py         # watchfiles-based file monitor
├── hot_reloader.py    # Config → runtime rebuild
├── live_session.py    # Active run session + output
└── keybinds.py        # Keyboard shortcuts
```

### 4.3 Behavior

1. Loads config and displays flow selector
2. Watches config files + agent YAMLs for changes
3. On change: re-validates, hot-reloads, shows diff
4. Keyboard shortcuts: `r` run, `w` watch, `p` profile, `q` quit
5. Live streaming of agent output during run
6. Exit status and duration after completion

### 4.4 Hot-Reload Strategy

Not true runtime hot-reload (agents are stateless between runs). Instead:
- File change → re-validate config
- Show validation result + diff
- User presses `r` to re-run with new config
- Previous run output remains visible for comparison

This avoids the complexity of live state migration while giving near-instant iteration.

## 5. Module 4: Profiling (`miniautogen profile` / `miniautogen inspect`)

### 5.1 Subcommands

| Command | Description |
|---|---|
| `profile [run-id]` | Execution timing, tool usage, token stats |
| `inspect [run-id]` | Deep agent state and event log |

### 5.2 Architecture

```
miniautogen/cli/services/profiling/
├── __init__.py
├── profiler.py        # Aggregates run events into stats
├── charts.py          # Rich progress bars and tables
└── inspector.py       # Event log viewer
```

### 5.3 Data Sources

Leverages existing `ExecutionEvent` system:
- Agent turn timing: `AGENT_TURN_STARTED` → `AGENT_TURN_COMPLETED`
- Tool calls: `TOOL_INVOKED` → `TOOL_SUCCEEDED` / `TOOL_FAILED`
- Token usage: `MESSAGE_COMPLETED` payload (model, input_tokens, output_tokens)
- Agent states: `TEAMMATE_FINISHED`, `TASK_COMPLETED`, etc.

All data is event-sourced — no new instrumentation needed.

### 5.4 Profile Output

```
Agent Timing
  tech_lead    ████████████████░░░░░  8.2s  32%
  researcher   ██████████████████████  12.4s 48%
  writer       █████░░░░░░░░░░░░░░░░  3.1s  12%
  idle         ██░░░░░░░░░░░░░░░░░░░  2.0s   8%
                     ─────    ─────
                    25.7s    100%

Tool Usage
  web_search    ████████████████░░░  14 calls  1.2s avg
  task_list     ██████░░░░░░░░░░░░░   5 calls  0.1s avg
  file_write    ██░░░░░░░░░░░░░░░░░   1 call   0.8s avg

Token Usage
  gpt-4o        input:  8,420  output:  2,150  $0.15
  gpt-4-turbo   input: 15,800  output:  3,400  $0.38
                                Total:       $0.53
```

### 5.5 Inspect Output

```
Run: research_team #2026-05-17T10:30:00Z
Status: FINISHED  Duration: 25.7s

Agent States
  tech_lead:    consolidated  3 tasks created
  researcher:   completed     2 tasks done
  writer:       completed     1 task done

Event Log (last 10)
  10:30:01  TEAM_STARTED         research_team
  10:30:02  TASK_ADDED           "Research quantum..."
  10:35:12  TASK_COMPLETED       researcher
  10:38:04  TASK_COMPLETED       writer
  10:38:07  TEAM_FINISHED        research_team
```

## 6. Implementation Order

### Sprint 1: Config Shell (Foundation)
1. `miniautogen/config/` service directory structure
2. `config shell` — prompt_toolkit REPL with set/get/show/save/diff
3. `config init` — interactive wizard (rich prompts)
4. `config validate` — fast Pydantic validation
5. `config doctor` — static analysis rules engine
6. `config schema` — JSON Schema export
7. `config show` — formatted views (agents, flows, engines)
8. `config diff` — pending changes visualization
9. `config migrate` — format migration

### Sprint 2: AI Assistant
1. `miniautogen/ai_assistant/` service directory
2. Phase 1 template matching engine
3. `ai init` — NL to config generation
4. `ai add` — incremental config mutation
5. `ai explain` — config → plain English
6. `ai fix` — auto-fix from doctor output
7. Phase 2 LLM integration (optional backend)
8. Integration: inline `config> ai ...` in shell

### Sprint 3: Dev Mode + Profiling
1. `miniautogen/dev_mode/` service directory
2. `dev` command: file watcher + keyboard shortcuts
3. Hot-reload cycle: edit → validate → re-run
4. `miniautogen/profiling/` service directory
5. `profile` command: timing bars, tool stats, tokens
6. `inspect` command: run state + event log viewer
7. Integration: `dev` mode launches profile automatically

## 7. Testing Strategy

### Unit Tests
- Config shell: parse commands, validate mutations
- Doctor: each rule independently tested
- AI assistant: pattern matching edge cases
- Profiling: event aggregation math

### Integration Tests
- Wizard: full init flow → valid config → loadable
- Shell: set → validate → save → reload → verify
- Dev mode: file change → detection → re-validate

### Snapshot Tests
- Schema export: golden file comparison
- Profile output: formatted string snapshot

## 8. Non-Goals

- Not a web UI (CLI-only focus)
- Not replacing TUI (separate product)
- Not distributed/multi-machine agents
- Not real-time runtime hot-reload of running agents
- Not a plugin system for third-party tools
