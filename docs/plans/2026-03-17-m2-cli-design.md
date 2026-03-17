# Milestone 2 — CLI Developer Product: Design Document

**Status:** Approved
**Date:** 2026-03-17

## Goal

Transform the SDK's raw power into an ergonomic developer experience. The CLI is a *consumer* of `miniautogen.api` — it standardizes how teams create, validate, and run MiniAutoGen projects.

## Architecture Decisions

### D1: CLI inside main package
The CLI lives at `miniautogen/cli/` within the existing package. Single install (`pip install miniautogen`), shared versioning. Can be extracted later if needed.

### D2: Click as command framework
Click provides composable command groups, nested subcommands, and a mature plugin ecosystem. Async bridge via `anyio.run()` keeps commands sync on surface, async internally.

### D3: Dogfooding — import boundary
`services/` (and all CLI code) may import:
- stdlib
- external dependencies (click, jinja2, pyyaml)
- `miniautogen.api`

**Prohibited:** any import from `miniautogen.core`, `miniautogen.stores`, `miniautogen.backends`, `miniautogen.policies`, or any other internal module. All SDK integration goes through `miniautogen.api`.

### D4: YAML as CLI convention, not SDK constraint
`miniautogen.yaml` is the declarative project config for the CLI. The SDK remains Python-first. The YAML convention does not limit programmatic SDK usage.

### D5: Separation of adapter and application logic
`commands/` are CLI adapters (parse args, render output). `services/` contain testable application logic. Services never touch Click.

## Package Structure

```
miniautogen/
├── __main__.py                    # python -m miniautogen
├── cli/
│   ├── __init__.py
│   ├── main.py                    # Click group + run_async helper
│   ├── config.py                  # Project resolution + YAML loading + validation
│   ├── errors.py                  # CLI error hierarchy + exit codes
│   ├── output.py                  # Text/JSON output formatting
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── init.py                # miniautogen init <name>
│   │   ├── check.py               # miniautogen check
│   │   ├── run.py                 # miniautogen run <pipeline>
│   │   └── sessions.py            # miniautogen sessions [list|clean]
│   ├── services/
│   │   ├── __init__.py
│   │   ├── init_project.py        # Scaffold logic (Jinja2 rendering)
│   │   ├── check_project.py       # Static + environment validation
│   │   ├── run_pipeline.py        # Pipeline execution via public SDK surface
│   │   └── session_ops.py         # Store queries via public SDK surface
│   └── templates/
│       └── project/
│           ├── miniautogen.yaml.j2
│           ├── agents/__init__.py.j2
│           ├── pipelines/main.py.j2
│           └── .env.j2
```

## Layer Responsibilities

| Layer | Role | Allowed Imports |
|---|---|---|
| `commands/` | CLI adapters: parse arguments, invoke services, map errors, render output | `services/`, `config`, `output`, `errors`, `click` |
| `services/` | Application services for CLI use-cases: implement init, check, run, sessions on top of the public SDK surface | stdlib, `miniautogen.api` |
| `config.py` | Project resolution and configuration: locate root, parse YAML, validate schema, resolve paths | stdlib, `pydantic`, `yaml` |
| `output.py` | Presentation layer for terminal and structured output | stdlib, `click.echo` |
| `errors.py` | CLI-specific exception hierarchy and exit code mapping | stdlib |

## Commands

### `miniautogen init <name>`

Creates a new project with canonical structure.

- Generates `miniautogen.yaml` with sensible defaults
- Creates example agent, pipeline, `.env`
- Options: `--model`, `--provider`, `--no-examples`
- Service: `init_project.py` uses Jinja2 to render templates

### `miniautogen check`

Validates project configuration and environment.

**Static checks:**
- Config file valid and parseable
- Pipeline files/modules exist
- Agent references resolve
- Configuration shape correct

**Environment checks:**
- Required env vars present (API keys)
- Provider configured and accessible
- Database URL valid (if configured)

Reports pass/fail per check. Exit code 0 = all pass, 1 = failures.

### `miniautogen run <pipeline>`

Executes a pipeline headlessly.

- Resolves configured pipeline target
- Loads through public SDK surface
- Executes using public runtime API
- Streams events to stdout via LoggingEventSink
- Returns result as text or structured format
- Options: `--timeout`, `--format text|json`, `--verbose`

### `miniautogen sessions list|clean`

Manages local session/run data.

- `list`: queries store for recent runs (status, timestamps)
- `clean`: removes completed/failed/cancelled runs older than N days
  - **Never deletes active runs**
  - Requires `--older-than` or `--yes` for safety
- Options: `--status`, `--limit`, `--older-than`, `--yes`

## Project Config Schema (`miniautogen.yaml`)

```yaml
project:
  name: my-agent-team
  version: "0.1.0"

provider:
  default: litellm
  model: gpt-4o-mini

pipelines:
  main:
    target: pipelines.main:build_pipeline

database:
  url: sqlite+aiosqlite:///miniautogen.db
```

Pipeline targets use Python import path notation (`module.path:callable`) for explicitness and Python-first alignment.

Loaded into `ProjectConfig` Pydantic model by `config.py`.

## Entry Points

```toml
# pyproject.toml
[tool.poetry.scripts]
miniautogen = "miniautogen.cli.main:cli"
```

Plus `miniautogen/__main__.py` for `python -m miniautogen` support.

## Dependencies

New dependency required: `click>=8.0` and `pyyaml>=6.0`.

Already available: `jinja2>=3.1.0`, `pydantic>=2.5.0`, `anyio>=4.0.0`.

## Testing Strategy

- `tests/cli/` mirrors `miniautogen/cli/` structure
- `services/` tested independently (no Click dependency)
- `commands/` tested via Click's `CliRunner` (integration)
- Import boundary enforced by architectural test: scan `cli/` imports, fail if any internal module found
