# Terminal Harness — CLI Operator Commands

**Date:** 2026-03-17
**Status:** Approved
**Benchmark:** Claude Code CLI as primary UX/architecture reference

---

## 1. Vision

Transform MiniAutoGen from a framework with CLI scaffolding into an **operator-grade terminal harness**. Three new commands (`chat`, `gateway serve`, `backend ping/list`) provide the operational surface for interacting with backends, serving gateways, and diagnosing infrastructure — all following the patterns established by Claude Code.

## 2. Objectives

- Interactive and scriptable chat with any configured backend
- One-command gateway serving for the Gemini CLI bridge
- Backend health diagnostics with capability introspection
- Consistent UX across all commands (output formats, exit codes, events)

## 3. Non-Objectives

- Multi-backend generic gateway (future milestone)
- Rich TUI with Textual/Prompt Toolkit (future — abstracted behind `OperatorInput`)
- Session persistence, resume, fork (future M3.2 — interface reserved now)
- Tool permission enforcement (future M3.2 — flags reserved now)
- MCP prompt integration in slash commands (future)

## 4. Architecture

### Command topology

```
miniautogen
├── init          (existing)
├── check         (existing)
├── run           (existing)
├── sessions      (existing group)
│   ├── list
│   └── clean
├── chat          (NEW — top-level, most-used command)
├── gateway       (NEW — group)
│   └── serve
└── backend       (NEW — group)
    ├── ping
    └── list
```

`chat` is top-level because it is the primary operator command. `gateway` and `backend` are Click groups to allow natural extension.

### File structure (new files)

```
miniautogen/cli/
├── commands/
│   ├── chat.py              → Click command, TTY detection, flag parsing
│   ├── gateway.py           → Click group + serve subcommand
│   └── backend.py           → Click group + ping/list subcommands
├── services/
│   ├── chat_service.py      → run_interactive_chat(), run_single_turn()
│   ├── gateway_service.py   → start_gateway_server()
│   ├── backend_service.py   → ping_backend(), list_backends()
│   └── operator_input.py    → OperatorInput protocol + StdlibOperatorInput
```

### Backend configuration (new section in `miniautogen.yaml`)

The existing `ProjectConfig` has no `backends` field. This spec requires adding one:

```yaml
# miniautogen.yaml
backends:
  gemini:
    driver: agentapi
    endpoint: http://localhost:8000
  ollama:
    driver: agentapi
    endpoint: http://localhost:11434
  local-pty:
    driver: pty
    command: ["gemini", "--interactive"]
```

`ProjectConfig` extension:

```python
class ProjectConfig(BaseModel):
    # ... existing fields ...
    backends: dict[str, BackendConfig] = Field(default_factory=dict)
```

A helper function `build_resolver_from_config(config: ProjectConfig) -> BackendResolver` populates the resolver from the YAML-declared backends. This bridges `require_project_config()` output to `BackendResolver`.

### Integration with existing patterns

- All commands follow the established pattern: Click command → async service → `run_async()` bridge
- Output via `echo_success()`, `echo_error()`, `echo_json()`, `echo_table()`
- Config via `require_project_config()` where needed
- Backend resolution via `build_resolver_from_config()` → `BackendResolver` + factory pattern
- Events via `ExecutionEvent` + `InMemoryEventSink`
- Errors extend `CLIError` hierarchy from `cli/errors.py`

---

## 5. Command: `chat`

### Interface

```bash
# REPL interactive
miniautogen chat -b gemini
miniautogen chat -b gemini -s "You are a code reviewer"
miniautogen chat -b gemini --append-system-prompt-file context.md

# Print mode (single-shot)
miniautogen chat -p "explain asyncio" -b gemini
miniautogen chat -p "explain asyncio" -b gemini -o json

# Pipe mode (stdin non-interactive)
echo "explain asyncio" | miniautogen chat -b gemini --print
cat prompt.txt | miniautogen chat -b gemini --print

# Session continuity (M3.2)
miniautogen chat --continue
miniautogen chat --resume abc123
miniautogen chat --resume

# Permissions (M3.2)
miniautogen chat -b gemini --allowed-tools "file_*,search"
miniautogen chat -b gemini --disallowed-tools "shell_exec"
```

### Flags

| Flag | Type | Default | MVP? | Description |
|------|------|---------|------|-------------|
| `--backend` / `-b` | `str` | required | Yes | Backend ID from `miniautogen.yaml` |
| `--print` / `-p` | `str` | `None` | Yes | Single-shot message. Always requires a value. Pipe mode uses TTY detection (no flag needed) |
| `--system-prompt` / `-s` | `str` | `None` | Yes | System prompt inline (replaces base) |
| `--append-system-prompt` | `str` | `None` | Yes | Text appended to base system prompt |
| `--append-system-prompt-file` | `Path` | `None` | Yes | File content appended to base system prompt |
| `--timeout` | `float` | `None` | Yes | Turn timeout in seconds (entire turn) |
| `--output-format` / `-o` | `text\|json` | `text` | Yes | Output format |
| `--model` / `-m` | `str` | `None` | Yes | Model override |
| `--continue` / `-c` | flag | `False` | M3.2 | Resume most recent session |
| `--resume` / `-r` | `str?` | `None` | M3.2 | Resume session by ID or interactive picker |
| `--allowed-tools` | `str` | `None` | M3.2 | Glob patterns of allowed tools |
| `--disallowed-tools` | `str` | `None` | M3.2 | Glob patterns of blocked tools |
| `--fork-session` | `str` | reserved | Future | Fork from existing session |

### OperatorInput abstraction

The chat service never calls `input()` directly. It uses a protocol:

```python
class OperatorInput(Protocol):
    async def read_line(self, prompt: str = ">>> ") -> str | None: ...
```

MVP implementation: `StdlibOperatorInput`. Uses `anyio.to_thread.run_sync()` to avoid blocking the event loop:

```python
class StdlibOperatorInput:
    async def read_line(self, prompt: str = ">>> ") -> str | None:
        try:
            return await anyio.to_thread.run_sync(lambda: input(prompt))
        except EOFError:
            return None
```

Replaceable by `PromptToolkitInput`, `TextualInput`, or `PipeInput` without touching the service.

### System prompt composition

The final system prompt is built by ordered composition:

1. Base prompt from agent spec (`miniautogen.yaml`)
2. `--system-prompt` (full override, if present)
3. `--append-system-prompt` (appends inline text to base)
4. `--append-system-prompt-file` (appends file content to base)

`--system-prompt` and `--append-*` are mutually exclusive. The command MUST validate this at parse time:

```python
if system_prompt and (append_system_prompt or append_system_prompt_file):
    raise click.UsageError(
        "--system-prompt and --append-system-prompt/--append-system-prompt-file "
        "are mutually exclusive"
    )
```

If `--append-system-prompt-file` points to a non-existent or unreadable file, raise `ConfigurationError` (exit 3) with a descriptive message.

### REPL loop

1. Resolve backend via `build_resolver_from_config()` → `BackendResolver`
2. `start_session()` on driver
3. Loop: `operator_input.read_line()` → check slash commands → `send_turn()` → stream response → print
4. First Ctrl+C: cancel current turn (`cancel_turn()`)
5. Second Ctrl+C or Ctrl+D: `close_session()` + exit
6. Emits `ExecutionEvent`s throughout

**Error handling requirements:**
- `close_session()` MUST be called in a `finally` block to ensure cleanup
- `close_session()` failures: log warning, do not change exit code
- If `start_session()` succeeds but first `send_turn()` fails, session is still closed via `finally`

### Print mode

Same flow without loop: one message, one response, exit. If stdin is piped and no `-p` argument, reads stdin as the prompt automatically.

**`-p` flag and pipe mode:**
- `--print` / `-p` always requires a value (standard Click `type=str, default=None`). No bare-flag ambiguity.
- If `-p "msg"` is provided AND stdin is piped, `-p` value wins (stdin ignored).
- If stdin is piped and no `-p` flag, TTY detection triggers implicit print mode (reads stdin as message).
- If neither `-p` nor piped stdin, enters REPL mode.

```python
# Click definition (no optional-value ambiguity):
@click.option("--print", "-p", "print_msg", default=None, type=str,
              help="Single-shot message.")
```

### TTY detection

```python
if not sys.stdin.isatty() and print_msg is None:
    print_msg = sys.stdin.read()
```

### Domain events

| Event | When |
|-------|------|
| `chat_session_started` | Session opened |
| `chat_turn_started` | User sent message |
| `chat_response_delta` | Streaming fragment received |
| `chat_turn_completed` | Full response received |
| `chat_turn_cancelled` | Ctrl+C or timeout |
| `chat_turn_failed` | Error during turn |
| `chat_session_closed` | Session closed |

**Event layering:** `chat_*` events are CLI-layer operator events, distinct from `BACKEND_*` driver events (which already exist in `EventType`). During a chat session, BOTH layers emit: the driver emits `BACKEND_*` events, and the chat service wraps/translates them into `chat_*` events. The `scope` field on `ExecutionEvent` differentiates them: `scope="cli.chat"` vs `scope="backend"`.

`chat_response_delta` can be high-frequency (one per streaming fragment). Implementations should use a separate streaming sink or make delta events opt-in to avoid noise in `InMemoryEventSink`.

Observability events (`backend_resolved`, `stream_first_token_received`, etc.) are out of MVP scope.

### JSON envelope (print mode)

```json
{
  "status": "ok",
  "backend": "gemini",
  "model": "gemini-2.5-pro",
  "output_text": "...",
  "session_id": "ephemeral-abc123",
  "usage": null,
  "error": null
}
```

Stable envelope. Null fields are explicit to avoid breaking scripts.

### Slash commands — extensible namespace

Inputs starting with `/` are interpreted locally, never sent to the backend. The namespace is open and extensible with 3 sources:

| Source | Examples | MVP? |
|--------|----------|------|
| Built-in | `/exit`, `/clear`, `/help` | Yes |
| Skills | `/commit`, `/review` | M3.2 |
| MCP prompts | `/mcp:tool-name` | Future |

The slash command parser is a dispatcher that resolves source to handler:

```python
class SlashCommandHandler(Protocol):
    async def handle(self, args: str, context: ChatContext) -> str | None: ...

class SlashCommandRegistry:
    def register(self, name: str, handler: SlashCommandHandler) -> None: ...
    def resolve(self, input_line: str) -> tuple[SlashCommandHandler, str] | None: ...
```

Unknown slash commands produce an error message listing available commands, never sent to the backend.

### Session lifecycle

> MVP: session is ephemeral in-process memory. `session_id` is generated but not persisted. Transcript accumulated in an in-process list, capped at 200 turns. Beyond the cap, oldest turns are dropped (sliding window). This prevents unbounded memory growth in long sessions.

> M3.2: persistence via `SessionStore` protocol. Enables `--continue`, `--resume`, interactive picker. Explicit distinction between **conversation resume** (restores conversational context) and **file rewind** (restores disk state) — independent concepts, following the Claude Code model.

### Timeout semantics

- Applies to the entire turn (from `send_turn()` to complete response)
- Implemented via `anyio.fail_after(timeout)`
- On expiry: calls `cancel_turn()`, emits `chat_turn_cancelled`, returns error
- In print mode: exit code `11`

### Tool governance (M3.2)

- `--allowed-tools` and `--disallowed-tools` accept comma-separated glob patterns
- Resolved as filters over the agent's `ToolSpec`
- Default: all tools enabled (permissive mode)
- Future: strict-by-default mode, `--permission-mode ask|allow-safe|bypass`

---

## 6. Command: `gateway serve`

### Interface

```bash
miniautogen gateway serve
miniautogen gateway serve --host 0.0.0.0 --port 9000
miniautogen gateway serve --reload --log-level debug
```

### Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--host` | `str` | `127.0.0.1` | Bind address |
| `--port` / `-p` | `int` | `8000` | Port |
| `--reload` | flag | `False` | Hot reload (dev only, requires stable importable app path) |
| `--log-level` | `str` | `info` | `critical\|error\|warning\|info\|debug` — passed to uvicorn |

### Behavior

1. Imports `gemini_cli_gateway.app:app` (if import fails, raise `CLIError` with install instructions)
2. Prints boot banner:
   ```
   MiniAutoGen Gateway
     App:     gemini_cli_gateway
     Bind:    http://127.0.0.1:8000
     Reload:  off
     Config:  GEMINI_GATEWAY_BINARY=gemini
   ```
3. Uses `run_async()` to enter an async context, then:
   - Emits `gateway_server_starting`
   - Creates `uvicorn.Config` + `uvicorn.Server`
   - Calls `server.serve()` (async, blocks until shutdown)
   - On clean shutdown: emits `gateway_server_stopped`
   - On failure: emits `gateway_server_failed`, exit code `1`

This approach keeps events async-compatible and respects the AnyIO invariant. `uvicorn.Server.serve()` is natively async and works within `anyio.run()`.

**Note:** Gateway serve requires asyncio backend (uvicorn limitation). Trio backend is not supported for this command.

### Lifecycle events

| Event | When |
|-------|------|
| `gateway_server_starting` | Before launching uvicorn |
| `gateway_server_started` | Server ready to accept connections |
| `gateway_server_stopped` | Clean shutdown |
| `gateway_server_failed` | Startup error |

Emitted via local `InMemoryEventSink`. Not part of the pipeline — for tests and internal observability.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Clean shutdown |
| `1` | Startup error |

### Scope

> Direct wrap of the existing `gemini_cli_gateway`. Not a multi-backend generic gateway. Evolution to `gateway serve --backend <id>` is a future milestone.

---

## 7. Command: `backend ping` / `backend list`

### Interface

```bash
miniautogen backend ping my-backend
miniautogen backend ping my-backend --timeout 10 --deep
miniautogen backend ping my-backend -o json
miniautogen backend list
miniautogen backend list -o json
```

### Flags (`ping`)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `BACKEND_ID` | arg | required | Backend ID from config |
| `--timeout` / `-t` | `float` | `5.0` | Verification timeout |
| `--deep` | flag | `False` | Include session probe (`start_session` + `close_session`) |
| `--output-format` / `-o` | `text\|json` | `text` | Output format |

### Flags (`list`)

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--output-format` / `-o` | `text\|json` | `text` | Output format |

### Ping flow

1. `require_project_config()` — load config
2. Resolve backend via `BackendResolver`
3. **Basic ping**: executes the minimum verification supported by the driver (MVP: `driver.capabilities()`) with `anyio.fail_after(timeout)`
4. **Deep ping** (if `--deep`): additionally `start_session()` + `close_session()`
5. Measures total latency

### Text output

```
✓ Backend 'gemini' is reachable (234ms)

  Driver:    agent_api
  Target:    http://localhost:8000
  Status:    ok
  Probe:     basic

  Capabilities:
    sessions:    yes
    streaming:   no
    cancel:      no
    tools:       yes
    artifacts:   no
    multimodal:  no
```

`Target` adapts to the driver: URL for HTTP, command for PTY, `-` for stdio.

### JSON output

```json
{
  "backend_id": "gemini",
  "status": "ok",
  "reachable": true,
  "latency_ms": 234,
  "driver": "agent_api",
  "target": "http://localhost:8000",
  "probe": "basic",
  "capabilities": {
    "sessions": true,
    "streaming": false,
    "cancel": false,
    "tools": true,
    "artifacts": false,
    "multimodal": false
  },
  "error": null
}
```

### Status field

| Value | Meaning |
|-------|---------|
| `ok` | Backend responded within timeout |
| `timeout` | No response in time |
| `unreachable` | Connection refused or failed |
| `misconfigured` | Invalid config (missing endpoint, broken auth) |

`reachable` is derived: `true` when `status == "ok"`.

### `backend list`

Lists all configured backends without connecting:

```
Backends configured:
  gemini      agent_api   http://localhost:8000
  ollama      agent_api   http://localhost:11434
  local-pty   pty         gemini --interactive
```

### Latency measurement

- **Basic ping**: `latency_ms` measures time of `capabilities()` call only
- **Deep ping**: `latency_ms` measures `capabilities()` + `start_session()` + `close_session()` combined

### Deep ping cleanup on timeout

If timeout fires after `start_session()` but before `close_session()`, a best-effort cleanup is attempted:

```python
async with anyio.fail_after(timeout):
    caps = await driver.capabilities()
    if deep:
        resp = await driver.start_session(req)
        try:
            await driver.close_session(resp.session_id)
        except BaseException:
            with anyio.move_on_after(2.0):
                await driver.close_session(resp.session_id)
            raise
```

This prevents orphaned sessions (especially important for PTY backends with child processes).

### Exit codes (`ping`)

| Code | Meaning |
|------|---------|
| `0` | Backend reachable |
| `1` | Backend unreachable |
| `10` | Backend ID not found in config |
| `11` | Timeout |

### `backend list` — no events

`list` is a purely local config read with no backend interaction. No `ExecutionEvent` is emitted. This is an intentional exemption: events track operational actions, not declarative queries.

### Event (`ping`)

`backend_health_checked` with payload:

```json
{
  "backend_id": "gemini",
  "status": "ok",
  "latency_ms": 234,
  "driver": "agent_api",
  "target": "http://localhost:8000",
  "probe": "basic",
  "session_probe_performed": false,
  "timeout_s": 5.0
}
```

---

## 8. Consolidated event catalog (new)

All events are `ExecutionEvent` instances. The `scope` field differentiates CLI-layer events from existing `BACKEND_*` driver events.

| Scope | Event | Payload |
|-------|-------|---------|
| `cli.chat` | `chat_session_started` | `{backend_id, session_id, model}` |
| `cli.chat` | `chat_turn_started` | `{session_id, turn_index, message_preview}` |
| `cli.chat` | `chat_response_delta` | `{session_id, turn_index, delta}` (high-frequency, opt-in sink) |
| `cli.chat` | `chat_turn_completed` | `{session_id, turn_index, response_length}` |
| `cli.chat` | `chat_turn_cancelled` | `{session_id, turn_index, reason}` |
| `cli.chat` | `chat_turn_failed` | `{session_id, turn_index, error}` |
| `cli.chat` | `chat_session_closed` | `{session_id, turns_completed}` |
| `cli.gateway` | `gateway_server_starting` | `{host, port, reload}` |
| `cli.gateway` | `gateway_server_started` | `{host, port}` |
| `cli.gateway` | `gateway_server_stopped` | `{uptime_s}` |
| `cli.gateway` | `gateway_server_failed` | `{error}` |
| `cli.backend` | `backend_health_checked` | `{backend_id, status, latency_ms, driver, target, probe, session_probe_performed, timeout_s}` |

**Relationship with existing events:** During a `chat` session, the driver layer still emits its own `BACKEND_*` events (e.g., `BACKEND_SESSION_STARTED`, `BACKEND_TURN_COMPLETED`) with `scope="backend"`. The chat service emits `chat_*` events as a higher-level operator view. Both coexist in the event sink; filters can separate them by `scope`.

**Implementation note:** All new CLI-layer event types (`chat_*`, `gateway_*`, `backend_health_checked`) should be added to the `EventType` enum in `core/events/types.py` to maintain consistency with existing event types.

## 9. Consolidated exit codes

### Existing (do not change)

| Code | Meaning | Defined in |
|------|---------|------------|
| `0` | Success | — |
| `1` | General error | `CLIError` |
| `2` | Project not found | `ProjectNotFoundError` |
| `3` | Invalid configuration | `ConfigurationError` |
| `4` | Pipeline not found | `PipelineNotFoundError` |
| `5` | Validation error | `ValidationError` |

### New (starting from 10 to avoid collision)

| Code | Meaning | Used by | New error class |
|------|---------|---------|-----------------|
| `10` | Backend not found | chat, backend | `BackendNotFoundError` |
| `11` | Timeout | chat, backend | `TurnTimeoutError` |
| `12` | Cancelled by user | chat | `TurnCancelledError` |

All new error classes extend `CLIError` from `cli/errors.py`.

## 10. Roadmap — Claude Code alignment

| Capability | MVP | M3.2 | Future |
|------------|-----|------|--------|
| REPL interactive | Yes | | |
| Print mode | Yes | | |
| Pipe mode (TTY detection) | Yes | | |
| Slash commands (built-in) | Yes | | |
| System prompt composition | Yes | | |
| Ephemeral sessions | Yes | | |
| JSON output envelope | Yes | | |
| Backend diagnostics | Yes | | |
| Gateway serving | Yes | | |
| Session persistence + resume | | Yes | |
| Tool permission flags | | Yes | |
| Slash commands (skills) | | Yes | |
| Interactive session picker | | Yes | |
| Generic multi-backend gateway | | | Yes |
| Slash commands (MCP prompts) | | | Yes |
| File rewind (independent of conversation) | | | Yes |
| Session fork | | | Yes |
| Rich TUI (Textual/Prompt Toolkit) | | | Yes |
| Terminal context injection (`@terminal`) | | | Yes |
| IDE integration (diff viewing, diagnostics) | | | Yes |
