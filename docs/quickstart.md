# Quickstart Guide

Get from install to your first multi-agent run in 5 minutes.

## 1. Install

```bash
pip install miniautogen
```

## 2. Create a Project

```bash
miniautogen init my-project
cd my-project
```

This scaffolds the following structure:

```
my-project/
  miniautogen.yaml   # Project config (engines, flows, defaults)
  agents/            # Agent definitions (YAML)
  pipelines/         # Pipeline entry points
  skills/            # Reusable skill packages
  tools/             # Tool definitions
  memory/            # Memory profiles
  mcp/               # MCP server configs
  .env               # Environment variables (API keys)
```

By default, the project is configured with OpenAI (`gpt-4o-mini`). You can
change the provider and model at init time:

```bash
# Use a different model
miniautogen init my-project --provider openai --model gpt-4o

# Use Gemini CLI as the backend
miniautogen init my-project --provider gemini-cli --model gemini-2.5-pro
```

## 3. Configure Your Engine

The generated `miniautogen.yaml` includes a default engine:

```yaml
engines:
  default_api:
    kind: api
    provider: "openai"
    model: "gpt-4o-mini"
    temperature: 0.2
```

For OpenAI, set your API key in `.env`:

```
OPENAI_API_KEY=sk-...
```

To use Gemini CLI instead, change the engine to:

```yaml
engines:
  gemini:
    kind: cli
    provider: "gemini-cli"
    model: "gemini-2.5-pro"
    command: "gemini"
```

You can also add or manage engines with the CLI:

```bash
miniautogen engine create my-engine --provider openai --model gpt-4o
```

## 4. Create Agents

Agents live as YAML files in the `agents/` directory. The scaffold includes an
example agent. Here is what a typical agent looks like:

```yaml
# agents/researcher.yaml
id: researcher
name: Research Specialist
role: Research Specialist
goal: >
  Investigate topics, locate reliable sources, and produce structured summaries.

engine_profile: default_api

tool_access:
  mode: allowlist
  allow:
    - web_search

runtime:
  max_turns: 10
  timeout_seconds: 300
```

Create additional agents with the CLI:

```bash
miniautogen agent create writer --engine default_api --role "Technical Writer"
```

## 5. Define a Flow

Flows define how agents coordinate. The scaffold creates a `main` flow in
`miniautogen.yaml` that references a pipeline builder function:

```yaml
flows:
  main:
    target: pipelines.main:build_pipeline
```

The `target` points to a Python function (`build_pipeline` in
`pipelines/main.py`) that constructs and returns a pipeline using the SDK.
This gives you full programmatic control over agent orchestration.

You can also define flows declaratively with a mode and participants list:

```yaml
flows:
  build:
    mode: workflow
    participants:
      - architect
      - developer
      - tester

  review:
    mode: deliberation
    participants:
      - architect
      - developer
      - tester
    leader: architect
```

MiniAutoGen supports three declarative flow modes:

| Mode | Description |
|------|-------------|
| **workflow** | Sequential execution -- agents run in order |
| **deliberation** | Multi-round discussion -- agents contribute and review |
| **loop** | Router-driven agentic loop with dynamic routing |

Create flows with the CLI:

```bash
miniautogen flow create research --mode workflow
```

## 6. Validate and Run

Before running, validate your project configuration:

```bash
miniautogen check
```

This checks that all agents, engines, flows, and dependencies are properly
configured.

Then run a flow:

```bash
miniautogen run main
```

## 7. What Happens Under the Hood

When you run a flow, MiniAutoGen orchestrates execution through a layered
architecture:

1. **PipelineRunner** -- the core execution engine. It manages the run lifecycle
   (PENDING -> RUNNING -> COMPLETED/FAILED), enforces timeouts, handles
   checkpoints, and emits execution events.

2. **AgentRuntime** -- wraps each agent with tool access, memory, delegation
   capabilities, and supervision. The runtime resolves the engine driver for
   each agent and manages turn-by-turn execution.

3. **Events** -- the system emits 72 typed events across 13 categories
   (run lifecycle, agent turns, tool calls, errors, etc.) for full
   observability via structlog.

4. **Policies** -- transversal concerns like retry, budget tracking, approval
   gates, and circuit breaking run as reactive policies that observe events
   without coupling to core logic.

5. **Results** -- each run produces a `RunResult` with the final state,
   collected outputs from all agents, and any errors encountered.

## 8. Next Steps

- **`miniautogen dash`** -- launch the TUI dashboard to monitor and manage
  agents, flows, and runs visually.
- **`miniautogen sessions`** -- list and inspect past run sessions.
- **`miniautogen check`** -- validate your project at any time.
- Browse the [architecture docs](pt/architecture/README.md) for deeper
  technical details.
- See the [examples/](../examples/) directory for complete project examples.
