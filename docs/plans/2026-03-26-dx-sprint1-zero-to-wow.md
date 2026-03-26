# DX Sprint 1: Zero to Wow -- Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Enable a developer to go from `pip install miniautogen` to interacting with an agent in 3 minutes or less, by adding `send`, `chat`, console CRUD, init templates, and a hello-world example.

**Architecture:** Five additive features (G1-G5) that extend the existing CLI (Click commands), FastAPI server (CRUD endpoints), Next.js console (forms), and project templates. No breaking changes. Each feature follows the existing pattern: Click command -> service layer -> YAML/runtime operations. The `send` and `chat` commands create temporary AgentRuntime instances with a resolved backend driver, bypassing PipelineRunner for single-agent interactions.

**Tech Stack:** Python 3.10+ (AnyIO, Click, FastAPI, Pydantic, PyYAML), Next.js (React, TanStack Query, Tailwind CSS), pytest + pytest-anyio

**Global Prerequisites:**
- Environment: macOS/Linux, Python 3.10+, Node.js 18+
- Tools: `python --version`, `pip`, `pytest`, `npm`
- Access: No API keys required for tests (mocked drivers)
- State: Branch from `main` (commit `e68a847`), clean working tree

**Verification before starting:**
```bash
python --version        # Expected: Python 3.10+
pytest --version        # Expected: 7.0+
cd /Users/brunocapelao/Projects/miniAutoGen && git status  # Expected: clean working tree on main
```

---

## G5: Hello-World Example (Start here -- no code dependencies)

### Task 1: Create hello-world example project structure

**Files:**
- Create: `examples/hello-world/miniautogen.yaml`
- Create: `examples/hello-world/agents/assistant.yaml`
- Create: `examples/hello-world/.env.example`
- Create: `examples/hello-world/README.md`

**Prerequisites:**
- None (standalone files)

**Step 1: Create the example workspace config**

Create file `examples/hello-world/miniautogen.yaml`:
```yaml
project:
  name: hello-world
  version: "0.1.0"

defaults:
  engine: default_api
  memory_profile: default

engines:
  default_api:
    kind: api
    provider: openai
    model: gpt-4o-mini
    temperature: 0.7

memory_profiles:
  default:
    session: true
    retrieval:
      enabled: false
    compaction:
      enabled: false

flows:
  main:
    mode: workflow
    participants:
      - assistant

database:
  url: sqlite+aiosqlite:///miniautogen.db
```

**Step 2: Create the assistant agent config**

Create file `examples/hello-world/agents/assistant.yaml`:
```yaml
id: assistant
version: "1.0.0"
name: Helpful Assistant
description: >
  A friendly AI assistant that helps with questions and tasks.

role: Assistant
goal: >
  Help users by answering questions clearly and concisely.

engine_profile: default_api

memory:
  profile: default
  session_memory: true
  retrieval_memory: false
  max_context_tokens: 8000

runtime:
  max_turns: 5
  timeout_seconds: 120
```

**Step 3: Create the .env.example file**

Create file `examples/hello-world/.env.example`:
```
# Set your OpenAI API key here
OPENAI_API_KEY=sk-your-key-here

# Or use Anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Or use Google Gemini
# GOOGLE_API_KEY=your-key-here
```

**Step 4: Create the README**

Create file `examples/hello-world/README.md`:
```markdown
# Hello World -- MiniAutoGen

A minimal example to get started with MiniAutoGen in under 3 minutes.

## Quick Start

1. **Install MiniAutoGen** (if you haven't already):

   ```bash
   pip install miniautogen
   ```

2. **Set your API key:**

   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

3. **Send a message:**

   ```bash
   miniautogen send "Hello! What can you do?" --agent assistant
   ```

4. **Start a chat session:**

   ```bash
   miniautogen chat assistant
   ```

5. **Run a workflow:**

   ```bash
   miniautogen run main --input "Tell me about Python async programming"
   ```

## Project Structure

```
hello-world/
  miniautogen.yaml    # Workspace configuration
  agents/
    assistant.yaml    # Agent definition
  .env.example        # API key template
```

## What's Next?

- Add more agents: `miniautogen agent create reviewer --role "Code Reviewer" --goal "Review code" --engine default_api`
- Create flows: `miniautogen flow create review --mode deliberation`
- Open the web console: `miniautogen console`
- Check workspace health: `miniautogen check`
```

**Step 5: Verify the example validates**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.cli.config import load_config; from pathlib import Path; c = load_config(Path('examples/hello-world/miniautogen.yaml')); print(f'OK: {c.project.name}, agents dir exists: {(Path(\"examples/hello-world/agents\")).is_dir()}')" `

**Expected output:**
```
OK: hello-world, agents dir exists: True
```

**Step 6: Commit**

```bash
git add examples/hello-world/
git commit -m "docs(examples): add hello-world minimal example project"
```

**If Task Fails:**
1. YAML parse error: Check indentation (2-space YAML)
2. Validation error: Ensure `flows.main` has `mode` + `participants` (not `target`)
3. Rollback: `git checkout -- examples/hello-world/`

---

## G1: `miniautogen send` -- Direct Message to Agent

### Task 2: Write the send service (business logic)

**Files:**
- Create: `miniautogen/cli/services/send_service.py`

**Prerequisites:**
- Files must exist: `miniautogen/cli/services/agent_ops.py`, `miniautogen/backends/engine_resolver.py`

**Step 1: Create the send service**

Create file `miniautogen/cli/services/send_service.py`:
```python
"""Send service -- execute a single agent turn without a full pipeline run.

Creates a temporary AgentRuntime, sends one message, returns the response.
Emits ExecutionEvents for observability.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from miniautogen.cli.config import WorkspaceConfig, load_config, CONFIG_FILENAME
from miniautogen.cli.services.agent_ops import load_agent_specs
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import NullEventSink
from miniautogen.core.events.types import EventType


async def send_message(
    project_root: Path,
    message: str,
    *,
    agent_name: str | None = None,
    output_format: str = "text",
) -> dict[str, Any]:
    """Send a single message to an agent and return the response.

    Args:
        project_root: Path to the workspace root.
        message: The message to send.
        agent_name: Agent name (defaults to first agent in workspace).
        output_format: "text" or "json".

    Returns:
        Dict with keys: agent, message, response, run_id.

    Raises:
        ValueError: If no agents found or agent not found.
        RuntimeError: If agent execution fails.
    """
    from miniautogen.backends.engine_resolver import EngineResolver
    from miniautogen.core.runtime.agent_runtime import AgentRuntime

    config = load_config(project_root / CONFIG_FILENAME)

    # Resolve agent
    agent_specs = load_agent_specs(project_root)
    if not agent_specs:
        raise ValueError(
            "No agents found in workspace. "
            "Create one first: miniautogen agent create <name>"
        )

    if agent_name is None:
        agent_name = next(iter(agent_specs))
    elif agent_name not in agent_specs:
        available = ", ".join(agent_specs.keys())
        raise ValueError(
            f"Agent '{agent_name}' not found. Available: {available}"
        )

    spec = agent_specs[agent_name]
    run_id = f"send-{uuid.uuid4().hex[:8]}"

    # Resolve engine -> driver
    engine_resolver = EngineResolver()
    engine_name = getattr(spec, "engine_profile", None) or config.defaults.engine
    engine_config = config.engines.get(engine_name)
    if engine_config is None:
        raise ValueError(
            f"Engine '{engine_name}' not found in workspace config."
        )

    engine_resolver.register_profile(engine_name, engine_config)
    driver = engine_resolver.get_driver(engine_name)

    # Create temporary AgentRuntime
    run_context = RunContext(
        run_id=run_id,
        pipeline_name="send",
        workspace=project_root,
    )

    event_sink = NullEventSink()

    runtime = AgentRuntime(
        agent_id=agent_name,
        driver=driver,
        run_context=run_context,
        event_sink=event_sink,
        system_prompt=getattr(spec, "goal", None) or "",
    )

    try:
        await runtime.initialize()
        response = await runtime.process(message)
    finally:
        await runtime.close()

    return {
        "agent": agent_name,
        "message": message,
        "response": response,
        "run_id": run_id,
    }
```

**Step 2: Verify the module imports cleanly**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.cli.services.send_service import send_message; print('OK')"`

**Expected output:**
```
OK
```

**Step 3: Commit**

```bash
git add miniautogen/cli/services/send_service.py
git commit -m "feat(cli): add send_service for single-agent message execution"
```

**If Task Fails:**
1. Import error on `EngineResolver.register_profile`: Check the method name in `miniautogen/backends/engine_resolver.py` -- it may be named differently. Grep for `def register` in that file to find the actual method name.
2. Import error on `RunContext`: Check the constructor signature in `miniautogen/core/contracts/run_context.py` -- it may require different fields.
3. Rollback: `git checkout -- miniautogen/cli/services/send_service.py`

---

### Task 3: Write failing tests for the send service

**Files:**
- Create: `tests/cli/services/test_send_service.py`

**Prerequisites:**
- Task 2 complete

**Step 1: Write the tests**

Create file `tests/cli/services/test_send_service.py`:
```python
"""Tests for send_service -- single agent message execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from miniautogen.cli.services.send_service import send_message


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with one agent."""
    import yaml

    ws = tmp_path / "workspace"
    ws.mkdir()

    config = {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine": "test_engine"},
        "engines": {
            "test_engine": {
                "kind": "api",
                "provider": "openai",
                "model": "gpt-4o-mini",
            }
        },
        "flows": {
            "main": {
                "mode": "workflow",
                "participants": ["assistant"],
            }
        },
    }
    (ws / "miniautogen.yaml").write_text(yaml.dump(config))

    agents_dir = ws / "agents"
    agents_dir.mkdir()
    agent = {
        "id": "assistant",
        "version": "1.0.0",
        "name": "Assistant",
        "role": "Helper",
        "goal": "Help users",
        "engine_profile": "test_engine",
    }
    (agents_dir / "assistant.yaml").write_text(yaml.dump(agent))

    return ws


@pytest.mark.anyio
async def test_send_message_returns_response(workspace: Path) -> None:
    """send_message should return agent response."""
    mock_driver = AsyncMock()
    mock_driver.start_session.return_value = MagicMock(session_id="s1")

    # Mock _execute_turn to return a TurnResult-like object
    mock_turn_result = MagicMock()
    mock_turn_result.text = "Hello! I am your assistant."

    with (
        patch(
            "miniautogen.cli.services.send_service.EngineResolver"
        ) as MockResolver,
        patch(
            "miniautogen.cli.services.send_service.AgentRuntime"
        ) as MockRuntime,
    ):
        resolver_instance = MockResolver.return_value
        resolver_instance.get_driver.return_value = mock_driver

        runtime_instance = MockRuntime.return_value
        runtime_instance.initialize = AsyncMock()
        runtime_instance.process = AsyncMock(return_value="Hello! I am your assistant.")
        runtime_instance.close = AsyncMock()

        result = await send_message(
            workspace,
            "Hello!",
            agent_name="assistant",
        )

    assert result["agent"] == "assistant"
    assert result["message"] == "Hello!"
    assert result["response"] == "Hello! I am your assistant."
    assert result["run_id"].startswith("send-")


@pytest.mark.anyio
async def test_send_message_default_agent(workspace: Path) -> None:
    """send_message should use first agent when none specified."""
    with (
        patch(
            "miniautogen.cli.services.send_service.EngineResolver"
        ) as MockResolver,
        patch(
            "miniautogen.cli.services.send_service.AgentRuntime"
        ) as MockRuntime,
    ):
        resolver_instance = MockResolver.return_value
        resolver_instance.get_driver.return_value = AsyncMock()

        runtime_instance = MockRuntime.return_value
        runtime_instance.initialize = AsyncMock()
        runtime_instance.process = AsyncMock(return_value="response")
        runtime_instance.close = AsyncMock()

        result = await send_message(workspace, "test")

    assert result["agent"] == "assistant"


@pytest.mark.anyio
async def test_send_message_agent_not_found(workspace: Path) -> None:
    """send_message should raise ValueError for unknown agent."""
    with pytest.raises(ValueError, match="not found"):
        await send_message(workspace, "test", agent_name="nonexistent")


@pytest.mark.anyio
async def test_send_message_no_agents(tmp_path: Path) -> None:
    """send_message should raise ValueError when no agents exist."""
    import yaml

    ws = tmp_path / "empty"
    ws.mkdir()
    config = {
        "project": {"name": "empty", "version": "0.1.0"},
        "defaults": {"engine": "test"},
        "engines": {"test": {"kind": "api", "provider": "openai", "model": "gpt-4o-mini"}},
        "flows": {"main": {"mode": "workflow", "participants": ["x"]}},
    }
    (ws / "miniautogen.yaml").write_text(yaml.dump(config))

    with pytest.raises(ValueError, match="No agents found"):
        await send_message(ws, "hello")


@pytest.mark.anyio
async def test_send_message_closes_runtime_on_error(workspace: Path) -> None:
    """AgentRuntime.close() must be called even if process() raises."""
    with (
        patch(
            "miniautogen.cli.services.send_service.EngineResolver"
        ) as MockResolver,
        patch(
            "miniautogen.cli.services.send_service.AgentRuntime"
        ) as MockRuntime,
    ):
        resolver_instance = MockResolver.return_value
        resolver_instance.get_driver.return_value = AsyncMock()

        runtime_instance = MockRuntime.return_value
        runtime_instance.initialize = AsyncMock()
        runtime_instance.process = AsyncMock(side_effect=RuntimeError("boom"))
        runtime_instance.close = AsyncMock()

        with pytest.raises(RuntimeError, match="boom"):
            await send_message(workspace, "test", agent_name="assistant")

        runtime_instance.close.assert_called_once()
```

**Step 2: Run the tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_send_service.py -v`

**Expected output:** All 5 tests should pass (they use mocks, so no real LLM calls).

**Step 3: Commit**

```bash
git add tests/cli/services/test_send_service.py
git commit -m "test(cli): add tests for send_service"
```

**If Task Fails:**
1. `EngineResolver` method name mismatch: Read `miniautogen/backends/engine_resolver.py` to find the actual `register_profile` and `get_driver` method names. Update both the service and tests.
2. `RunContext` constructor mismatch: Read `miniautogen/core/contracts/run_context.py` for required fields.
3. Rollback: `git checkout -- tests/cli/services/test_send_service.py`

---

### Task 4: Create the send CLI command

**Files:**
- Create: `miniautogen/cli/commands/send.py`
- Modify: `miniautogen/cli/main.py` (add 3 lines at end)

**Prerequisites:**
- Task 2 complete

**Step 1: Create the send command**

Create file `miniautogen/cli/commands/send.py`:
```python
"""miniautogen send command -- direct message to an agent."""

from __future__ import annotations

import sys

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_json


@click.command("send")
@click.argument("message", required=False, default=None)
@click.option(
    "--agent",
    "agent_name",
    default=None,
    help="Agent to send message to (defaults to first agent).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def send_command(
    message: str | None,
    agent_name: str | None,
    output_format: str,
) -> None:
    """Send a message to an agent and get a response.

    The message can be passed as an argument, piped from stdin,
    or read from a file with @filepath syntax.

    \b
    Examples:
      miniautogen send "Hello, who are you?" --agent assistant
      echo "Review this code" | miniautogen send --agent reviewer
      miniautogen send "Analyze this" --format json
    """
    from miniautogen.cli.services.send_service import send_message

    root, _config = require_project_config()

    # Resolve message from argument or stdin
    if message is None:
        if not sys.stdin.isatty():
            message = sys.stdin.read().strip()
        else:
            echo_error("No message provided. Pass as argument or pipe from stdin.")
            raise SystemExit(1)

    if not message.strip():
        echo_error("Message cannot be empty.")
        raise SystemExit(1)

    try:
        result = run_async(
            send_message,
            root,
            message,
            agent_name=agent_name,
            output_format=output_format,
        )
    except ValueError as exc:
        echo_error(str(exc))
        raise SystemExit(1)
    except Exception as exc:
        echo_error(f"Send failed: {exc}")
        raise SystemExit(1)

    if output_format == "json":
        echo_json(result)
    else:
        click.echo(result["response"])
```

**Step 2: Register the command in main.py**

Add the following 3 lines at the end of `miniautogen/cli/main.py` (after the `console_command` registration):

```python
from miniautogen.cli.commands.send import send_command  # noqa: E402

cli.add_command(send_command)
```

**Step 3: Verify the command appears in help**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen --help`

**Expected output:** Should include `send` in the commands list:
```
  send         Send a message to an agent and get a response.
```

**Step 4: Commit**

```bash
git add miniautogen/cli/commands/send.py miniautogen/cli/main.py
git commit -m "feat(cli): add 'send' command for direct agent messaging"
```

**If Task Fails:**
1. Circular import: If importing `run_async` from `main.py` causes issues, move the `run_async` function to a separate utility module.
2. Rollback: `git checkout -- miniautogen/cli/commands/send.py miniautogen/cli/main.py`

---

### Task 5: Write CLI tests for the send command

**Files:**
- Create: `tests/cli/commands/test_send.py`

**Prerequisites:**
- Tasks 2, 4 complete

**Step 1: Write the CLI tests**

Create file `tests/cli/commands/test_send.py`:
```python
"""Tests for the send CLI command."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_send_no_message_no_stdin() -> None:
    """send without message or stdin should error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["send"])
    assert result.exit_code != 0
    assert "no message" in result.output.lower() or "error" in result.output.lower()


def test_send_with_message(init_project) -> None:
    """send with message argument should call send_service."""
    runner = init_project

    with patch(
        "miniautogen.cli.commands.send.send_message",
        new_callable=lambda: lambda: AsyncMock(
            return_value={
                "agent": "researcher",
                "message": "Hello",
                "response": "Hi there!",
                "run_id": "send-abc123",
            }
        ),
    ):
        result = runner.invoke(cli, ["send", "Hello", "--agent", "researcher"])

    assert result.exit_code == 0, result.output
    assert "Hi there!" in result.output


def test_send_json_format(init_project) -> None:
    """send --format json should output JSON."""
    runner = init_project

    with patch(
        "miniautogen.cli.commands.send.send_message",
        new_callable=lambda: lambda: AsyncMock(
            return_value={
                "agent": "researcher",
                "message": "Hello",
                "response": "Hi!",
                "run_id": "send-abc123",
            }
        ),
    ):
        result = runner.invoke(cli, [
            "send", "Hello", "--agent", "researcher", "--format", "json",
        ])

    assert result.exit_code == 0, result.output
    assert '"response"' in result.output


def test_send_empty_message(init_project) -> None:
    """send with empty message should error."""
    runner = init_project
    result = runner.invoke(cli, ["send", "   "])
    assert result.exit_code != 0
```

**Step 2: Run the tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_send.py -v`

**Expected output:** All tests pass.

**Step 3: Commit**

```bash
git add tests/cli/commands/test_send.py
git commit -m "test(cli): add CLI tests for send command"
```

**If Task Fails:**
1. The `init_project` fixture creates a project with `researcher` agent. Check that the fixture at `tests/cli/commands/conftest.py` still works by running an existing test first.
2. Mock path might be wrong if send_service is imported differently. Adjust the patch path.
3. Rollback: `git checkout -- tests/cli/commands/test_send.py`

---

### Task 6: Run Code Review (G1 + G5)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location
- Format: `TODO(review): [Issue description] (reported by [reviewer] on [date], severity: Low)`

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

---

## G2: `miniautogen chat` -- Interactive Chat Session

### Task 7: Write the chat service (business logic)

**Files:**
- Create: `miniautogen/cli/services/chat_service.py`

**Prerequisites:**
- Task 2 complete (send_service pattern)

**Step 1: Create the chat service**

Create file `miniautogen/cli/services/chat_service.py`:
```python
"""Chat service -- interactive conversation with an agent.

Manages a multi-turn conversation with an AgentRuntime,
maintaining conversation history across turns.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from miniautogen.cli.config import load_config, CONFIG_FILENAME
from miniautogen.cli.services.agent_ops import load_agent_specs
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import NullEventSink


class ChatSession:
    """Manages a multi-turn chat session with an agent.

    Usage:
        session = await ChatSession.create(project_root, agent_name="assistant")
        response = await session.send("Hello!")
        response = await session.send("Tell me more")
        await session.close()
    """

    def __init__(
        self,
        *,
        agent_name: str,
        runtime: Any,  # AgentRuntime
        run_id: str,
        history: list[dict[str, str]],
    ) -> None:
        self._agent_name = agent_name
        self._runtime = runtime
        self._run_id = run_id
        self._history = history
        self._closed = False

    @property
    def agent_name(self) -> str:
        return self._agent_name

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def history(self) -> list[dict[str, str]]:
        return list(self._history)

    @classmethod
    async def create(
        cls,
        project_root: Path,
        *,
        agent_name: str | None = None,
    ) -> "ChatSession":
        """Create and initialize a chat session.

        Args:
            project_root: Workspace root path.
            agent_name: Agent to chat with (defaults to first).

        Returns:
            An initialized ChatSession.
        """
        from miniautogen.backends.engine_resolver import EngineResolver
        from miniautogen.core.runtime.agent_runtime import AgentRuntime

        config = load_config(project_root / CONFIG_FILENAME)
        agent_specs = load_agent_specs(project_root)

        if not agent_specs:
            raise ValueError(
                "No agents found in workspace. "
                "Create one first: miniautogen agent create <name>"
            )

        if agent_name is None:
            agent_name = next(iter(agent_specs))
        elif agent_name not in agent_specs:
            available = ", ".join(agent_specs.keys())
            raise ValueError(
                f"Agent '{agent_name}' not found. Available: {available}"
            )

        spec = agent_specs[agent_name]
        run_id = f"chat-{uuid.uuid4().hex[:8]}"

        engine_name = getattr(spec, "engine_profile", None) or config.defaults.engine
        engine_config = config.engines.get(engine_name)
        if engine_config is None:
            raise ValueError(f"Engine '{engine_name}' not found in workspace config.")

        engine_resolver = EngineResolver()
        engine_resolver.register_profile(engine_name, engine_config)
        driver = engine_resolver.get_driver(engine_name)

        run_context = RunContext(
            run_id=run_id,
            pipeline_name="chat",
            workspace=project_root,
        )

        runtime = AgentRuntime(
            agent_id=agent_name,
            driver=driver,
            run_context=run_context,
            event_sink=NullEventSink(),
            system_prompt=getattr(spec, "goal", None) or "",
        )

        await runtime.initialize()

        return cls(
            agent_name=agent_name,
            runtime=runtime,
            run_id=run_id,
            history=[],
        )

    async def send(self, message: str) -> str:
        """Send a message and get the agent's response.

        Args:
            message: User message.

        Returns:
            Agent response text.

        Raises:
            RuntimeError: If session is closed.
        """
        if self._closed:
            raise RuntimeError("Chat session is closed.")

        self._history.append({"role": "user", "content": message})
        response = await self._runtime.process(message)
        self._history.append({"role": "assistant", "content": response})
        return response

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    async def close(self) -> None:
        """Close the chat session and release resources."""
        if not self._closed:
            await self._runtime.close()
            self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed


def list_available_agents(project_root: Path) -> list[str]:
    """List agent names available for chat.

    Args:
        project_root: Workspace root path.

    Returns:
        List of agent names.
    """
    agent_specs = load_agent_specs(project_root)
    return list(agent_specs.keys())
```

**Step 2: Verify the module imports cleanly**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.cli.services.chat_service import ChatSession; print('OK')"`

**Expected output:**
```
OK
```

**Step 3: Commit**

```bash
git add miniautogen/cli/services/chat_service.py
git commit -m "feat(cli): add chat_service for multi-turn agent conversations"
```

**If Task Fails:**
1. Same potential issues as Task 2 with EngineResolver/RunContext. Apply the same fixes.
2. Rollback: `git checkout -- miniautogen/cli/services/chat_service.py`

---

### Task 8: Write failing tests for the chat service

**Files:**
- Create: `tests/cli/services/test_chat_service.py`

**Prerequisites:**
- Task 7 complete

**Step 1: Write the tests**

Create file `tests/cli/services/test_chat_service.py`:
```python
"""Tests for chat_service -- multi-turn agent conversation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from miniautogen.cli.services.chat_service import ChatSession, list_available_agents


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Create a minimal workspace with two agents."""
    ws = tmp_path / "workspace"
    ws.mkdir()

    config = {
        "project": {"name": "test", "version": "0.1.0"},
        "defaults": {"engine": "test_engine"},
        "engines": {
            "test_engine": {
                "kind": "api",
                "provider": "openai",
                "model": "gpt-4o-mini",
            }
        },
        "flows": {
            "main": {
                "mode": "workflow",
                "participants": ["assistant", "reviewer"],
            }
        },
    }
    (ws / "miniautogen.yaml").write_text(yaml.dump(config))

    agents_dir = ws / "agents"
    agents_dir.mkdir()
    for name in ("assistant", "reviewer"):
        agent = {
            "id": name,
            "version": "1.0.0",
            "name": name.title(),
            "role": name.title(),
            "goal": f"Be a {name}",
            "engine_profile": "test_engine",
        }
        (agents_dir / f"{name}.yaml").write_text(yaml.dump(agent))

    return ws


@pytest.mark.anyio
async def test_chat_session_create_and_send(workspace: Path) -> None:
    """ChatSession should create, send messages, and return responses."""
    with (
        patch(
            "miniautogen.cli.services.chat_service.EngineResolver"
        ) as MockResolver,
        patch(
            "miniautogen.cli.services.chat_service.AgentRuntime"
        ) as MockRuntime,
    ):
        resolver_instance = MockResolver.return_value
        resolver_instance.get_driver.return_value = AsyncMock()

        runtime_instance = MockRuntime.return_value
        runtime_instance.initialize = AsyncMock()
        runtime_instance.process = AsyncMock(return_value="Hello!")
        runtime_instance.close = AsyncMock()

        session = await ChatSession.create(workspace, agent_name="assistant")
        assert session.agent_name == "assistant"
        assert session.run_id.startswith("chat-")

        response = await session.send("Hi")
        assert response == "Hello!"
        assert len(session.history) == 2
        assert session.history[0] == {"role": "user", "content": "Hi"}
        assert session.history[1] == {"role": "assistant", "content": "Hello!"}

        await session.close()
        assert session.is_closed
        runtime_instance.close.assert_called_once()


@pytest.mark.anyio
async def test_chat_session_default_agent(workspace: Path) -> None:
    """ChatSession should use first agent when none specified."""
    with (
        patch(
            "miniautogen.cli.services.chat_service.EngineResolver"
        ) as MockResolver,
        patch(
            "miniautogen.cli.services.chat_service.AgentRuntime"
        ) as MockRuntime,
    ):
        resolver_instance = MockResolver.return_value
        resolver_instance.get_driver.return_value = AsyncMock()

        runtime_instance = MockRuntime.return_value
        runtime_instance.initialize = AsyncMock()
        runtime_instance.close = AsyncMock()

        session = await ChatSession.create(workspace)
        assert session.agent_name == "assistant"
        await session.close()


@pytest.mark.anyio
async def test_chat_session_agent_not_found(workspace: Path) -> None:
    """ChatSession should raise ValueError for unknown agent."""
    with pytest.raises(ValueError, match="not found"):
        await ChatSession.create(workspace, agent_name="ghost")


@pytest.mark.anyio
async def test_chat_session_send_after_close(workspace: Path) -> None:
    """Sending after close should raise RuntimeError."""
    with (
        patch(
            "miniautogen.cli.services.chat_service.EngineResolver"
        ) as MockResolver,
        patch(
            "miniautogen.cli.services.chat_service.AgentRuntime"
        ) as MockRuntime,
    ):
        resolver_instance = MockResolver.return_value
        resolver_instance.get_driver.return_value = AsyncMock()

        runtime_instance = MockRuntime.return_value
        runtime_instance.initialize = AsyncMock()
        runtime_instance.close = AsyncMock()

        session = await ChatSession.create(workspace, agent_name="assistant")
        await session.close()

        with pytest.raises(RuntimeError, match="closed"):
            await session.send("Hello?")


@pytest.mark.anyio
async def test_chat_session_clear_history(workspace: Path) -> None:
    """clear_history should empty conversation history."""
    with (
        patch(
            "miniautogen.cli.services.chat_service.EngineResolver"
        ) as MockResolver,
        patch(
            "miniautogen.cli.services.chat_service.AgentRuntime"
        ) as MockRuntime,
    ):
        resolver_instance = MockResolver.return_value
        resolver_instance.get_driver.return_value = AsyncMock()

        runtime_instance = MockRuntime.return_value
        runtime_instance.initialize = AsyncMock()
        runtime_instance.process = AsyncMock(return_value="ok")
        runtime_instance.close = AsyncMock()

        session = await ChatSession.create(workspace, agent_name="assistant")
        await session.send("msg1")
        assert len(session.history) == 2

        session.clear_history()
        assert len(session.history) == 0

        await session.close()


def test_list_available_agents(workspace: Path) -> None:
    """list_available_agents should return agent names."""
    agents = list_available_agents(workspace)
    assert "assistant" in agents
    assert "reviewer" in agents
```

**Step 2: Run the tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_chat_service.py -v`

**Expected output:** All 6 tests pass.

**Step 3: Commit**

```bash
git add tests/cli/services/test_chat_service.py
git commit -m "test(cli): add tests for chat_service"
```

**If Task Fails:**
1. Same mock issues as Task 3. Apply same fixes.
2. Rollback: `git checkout -- tests/cli/services/test_chat_service.py`

---

### Task 9: Create the chat CLI command

**Files:**
- Create: `miniautogen/cli/commands/chat.py`
- Modify: `miniautogen/cli/main.py` (add 3 lines at end)

**Prerequisites:**
- Task 7 complete

**Step 1: Create the chat command**

Create file `miniautogen/cli/commands/chat.py`:
```python
"""miniautogen chat command -- interactive conversation with an agent.

Pure CLI chat loop using input() and click.echo(). No TUI/Textual.
"""

from __future__ import annotations

import click

from miniautogen.cli.config import require_project_config
from miniautogen.cli.main import run_async
from miniautogen.cli.output import echo_error, echo_info, echo_success, echo_warning


def _print_help() -> None:
    """Print available chat commands."""
    echo_info("Available commands:")
    echo_info("  /quit     Exit the chat session")
    echo_info("  /clear    Clear conversation history")
    echo_info("  /switch <agent>  Switch to a different agent")
    echo_info("  /help     Show this help message")
    echo_info("  /history  Show conversation history")


@click.command("chat")
@click.argument("agent_name", required=False, default=None)
def chat_command(agent_name: str | None) -> None:
    """Start an interactive chat session with an agent.

    \b
    Examples:
      miniautogen chat assistant
      miniautogen chat              # uses first agent
    """
    root, _config = require_project_config()
    run_async(_chat_loop, root, agent_name)


async def _chat_loop(root, agent_name: str | None) -> None:
    """Async chat loop -- creates session and handles user input."""
    from miniautogen.cli.services.chat_service import ChatSession, list_available_agents

    try:
        session = await ChatSession.create(root, agent_name=agent_name)
    except ValueError as exc:
        echo_error(str(exc))
        return

    echo_success(f"Chat session started with '{session.agent_name}'")
    echo_info(f"Session ID: {session.run_id}")
    echo_info("Type /help for commands, /quit to exit.\n")

    try:
        while True:
            try:
                user_input = input(click.style("You: ", fg="green"))
            except (EOFError, KeyboardInterrupt):
                click.echo("")
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                cmd_parts = user_input.split(maxsplit=1)
                cmd = cmd_parts[0].lower()

                if cmd == "/quit":
                    break
                elif cmd == "/clear":
                    session.clear_history()
                    echo_success("History cleared.")
                    continue
                elif cmd == "/help":
                    _print_help()
                    continue
                elif cmd == "/history":
                    if not session.history:
                        echo_info("No messages yet.")
                    else:
                        for msg in session.history:
                            role = msg["role"]
                            content = msg["content"]
                            if role == "user":
                                click.echo(click.style(f"You: ", fg="green") + content)
                            else:
                                click.echo(click.style(f"{session.agent_name}: ", fg="cyan") + content)
                    continue
                elif cmd == "/switch":
                    if len(cmd_parts) < 2:
                        agents = list_available_agents(root)
                        echo_info(f"Available agents: {', '.join(agents)}")
                        echo_info("Usage: /switch <agent_name>")
                        continue
                    new_agent = cmd_parts[1].strip()
                    try:
                        await session.close()
                        session = await ChatSession.create(root, agent_name=new_agent)
                        echo_success(f"Switched to '{session.agent_name}'")
                    except ValueError as exc:
                        echo_error(str(exc))
                    continue
                else:
                    echo_warning(f"Unknown command: {cmd}. Type /help for commands.")
                    continue

            # Send message to agent
            try:
                response = await session.send(user_input)
                click.echo(click.style(f"{session.agent_name}: ", fg="cyan") + response)
            except Exception as exc:
                echo_error(f"Error: {exc}")

    finally:
        await session.close()
        echo_info("Chat session ended.")
```

**Step 2: Register the command in main.py**

Add the following 3 lines at the end of `miniautogen/cli/main.py` (after the `send_command` registration):

```python
from miniautogen.cli.commands.chat import chat_command  # noqa: E402

cli.add_command(chat_command)
```

**Step 3: Verify the command appears in help**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen --help`

**Expected output:** Should include `chat` in the commands list:
```
  chat         Start an interactive chat session with an agent.
```

**Step 4: Commit**

```bash
git add miniautogen/cli/commands/chat.py miniautogen/cli/main.py
git commit -m "feat(cli): add 'chat' command for interactive agent conversations"
```

**If Task Fails:**
1. `input()` in async context: The `input()` call is synchronous inside an async function. This works because `anyio.run()` is already running the event loop. If it blocks, wrap with `await anyio.to_thread.run_sync(lambda: input(...))`.
2. Rollback: `git checkout -- miniautogen/cli/commands/chat.py miniautogen/cli/main.py`

---

### Task 10: Write CLI tests for the chat command

**Files:**
- Create: `tests/cli/commands/test_chat.py`

**Prerequisites:**
- Task 9 complete

**Step 1: Write the CLI tests**

Create file `tests/cli/commands/test_chat.py`:
```python
"""Tests for the chat CLI command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from miniautogen.cli.main import cli


def test_chat_help() -> None:
    """chat --help should show usage."""
    runner = CliRunner()
    result = runner.invoke(cli, ["chat", "--help"])
    assert result.exit_code == 0
    assert "interactive chat" in result.output.lower() or "chat session" in result.output.lower()


def test_chat_quit_immediately(init_project) -> None:
    """chat should exit cleanly on /quit."""
    runner = init_project

    mock_session = AsyncMock()
    mock_session.agent_name = "researcher"
    mock_session.run_id = "chat-abc123"
    mock_session.close = AsyncMock()

    with patch(
        "miniautogen.cli.commands.chat.ChatSession",
    ) as MockChatSession:
        MockChatSession.create = AsyncMock(return_value=mock_session)

        result = runner.invoke(cli, ["chat", "researcher"], input="/quit\n")

    assert result.exit_code == 0, result.output
    assert "session" in result.output.lower()


def test_chat_send_and_quit(init_project) -> None:
    """chat should send message, display response, then quit."""
    runner = init_project

    mock_session = AsyncMock()
    mock_session.agent_name = "researcher"
    mock_session.run_id = "chat-abc123"
    mock_session.send = AsyncMock(return_value="I can help with research!")
    mock_session.close = AsyncMock()

    with patch(
        "miniautogen.cli.commands.chat.ChatSession",
    ) as MockChatSession:
        MockChatSession.create = AsyncMock(return_value=mock_session)

        result = runner.invoke(
            cli, ["chat", "researcher"],
            input="Hello!\n/quit\n",
        )

    assert result.exit_code == 0, result.output
    mock_session.send.assert_called_once_with("Hello!")


def test_chat_clear_command(init_project) -> None:
    """chat /clear should clear history."""
    runner = init_project

    mock_session = AsyncMock()
    mock_session.agent_name = "researcher"
    mock_session.run_id = "chat-abc123"
    mock_session.clear_history = MagicMock()
    mock_session.close = AsyncMock()

    with patch(
        "miniautogen.cli.commands.chat.ChatSession",
    ) as MockChatSession:
        MockChatSession.create = AsyncMock(return_value=mock_session)

        result = runner.invoke(
            cli, ["chat", "researcher"],
            input="/clear\n/quit\n",
        )

    assert result.exit_code == 0, result.output
    mock_session.clear_history.assert_called_once()


def test_chat_agent_not_found(init_project) -> None:
    """chat with unknown agent should show error."""
    runner = init_project

    with patch(
        "miniautogen.cli.commands.chat.ChatSession",
    ) as MockChatSession:
        MockChatSession.create = AsyncMock(
            side_effect=ValueError("Agent 'ghost' not found.")
        )

        result = runner.invoke(cli, ["chat", "ghost"], input="/quit\n")

    assert "not found" in result.output.lower() or "error" in result.output.lower()
```

**Step 2: Run the tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_chat.py -v`

**Expected output:** All tests pass.

**Step 3: Commit**

```bash
git add tests/cli/commands/test_chat.py
git commit -m "test(cli): add CLI tests for chat command"
```

**If Task Fails:**
1. The `init_project` fixture may not create the researcher agent. Check conftest.py for what agents are scaffolded.
2. CliRunner may not handle `input()` well in async context. May need to test at a higher level or refactor `_chat_loop` to accept an input function.
3. Rollback: `git checkout -- tests/cli/commands/test_chat.py`

---

### Task 11: Run Code Review (G2)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately (do NOT add TODO comments for these severities)
- Re-run all 3 reviewers in parallel after fixes
- Repeat until zero Critical/High/Medium issues remain

**Low Issues:**
- Add `TODO(review):` comments in code at the relevant location

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain

---

## G3: Console CRUD -- Create/Edit/Delete Agents and Flows via Web

### Task 12: Expand ConsoleDataProvider protocol with write methods

**Files:**
- Modify: `miniautogen/server/provider_protocol.py`

**Prerequisites:**
- None

**Step 1: Add write methods to the protocol**

In `miniautogen/server/provider_protocol.py`, add these methods to the `ConsoleDataProvider` class (after the existing methods, before the closing of the class):

Add these methods after the `query_run_events` method:

```python
    # -- Write operations (CRUD) ---
    def create_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new agent. Returns the created agent dict."""
        ...

    def update_agent(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing agent. Returns the updated agent dict."""
        ...

    def delete_agent(self, name: str) -> dict[str, Any]:
        """Delete an agent. Returns deletion info."""
        ...

    def create_flow(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new flow. Returns the created flow dict."""
        ...

    def update_flow(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing flow. Returns the updated flow dict."""
        ...

    def delete_flow(self, name: str) -> dict[str, Any]:
        """Delete a flow. Returns deletion info."""
        ...
```

**Step 2: Verify the module imports**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.server.provider_protocol import ConsoleDataProvider; print('OK')"`

**Expected output:**
```
OK
```

**Step 3: Commit**

```bash
git add miniautogen/server/provider_protocol.py
git commit -m "feat(server): expand ConsoleDataProvider protocol with CRUD write methods"
```

**If Task Fails:**
1. Protocol syntax issue: Make sure methods use `...` as body (Ellipsis), not `pass`.
2. Rollback: `git checkout -- miniautogen/server/provider_protocol.py`

---

### Task 13: Implement write operations in DashDataProvider

**Files:**
- Modify: `miniautogen/tui/data_provider.py`

**Prerequisites:**
- Task 12 complete

**Step 1: Add CRUD methods to DashDataProvider**

Read `miniautogen/tui/data_provider.py` first to find where to add the methods. They should go after the existing read methods but before the run/pipeline execution methods. The class already imports `_create_agent`, `_delete_agent`, `_update_agent`, `_create_pipeline`, `_delete_pipeline`, `_update_pipeline` from the CLI services at the top of the file.

Add these methods to the `DashDataProvider` class:

```python
    # -- Write operations (CRUD) -------------------------------------------

    def create_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new agent from API payload."""
        name = data.get("name") or data.get("id")
        if not name:
            raise ValueError("Agent must have a 'name' or 'id' field.")
        return _create_agent(
            self._root,
            name,
            role=data.get("role", "Agent"),
            goal=data.get("goal", ""),
            engine_profile=data.get("engine_profile", "default_api"),
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
        )

    def update_agent(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing agent."""
        result = _update_agent(self._root, name, **data)
        return result.get("after", data)

    def delete_agent(self, name: str) -> dict[str, Any]:
        """Delete an agent."""
        return _delete_agent(self._root, name)

    def create_flow(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new flow from API payload."""
        name = data.get("name")
        if not name:
            raise ValueError("Flow must have a 'name' field.")
        flow_data = {k: v for k, v in data.items() if k != "name"}
        return _create_pipeline(self._root, name, **flow_data)

    def update_flow(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing flow."""
        result = _update_pipeline(self._root, name, **data)
        return result.get("after", data)

    def delete_flow(self, name: str) -> dict[str, Any]:
        """Delete a flow."""
        return _delete_pipeline(self._root, name)
```

**Step 2: Verify the methods work**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.tui.data_provider import DashDataProvider; print('OK: has create_agent:', hasattr(DashDataProvider, 'create_agent'))"`

**Expected output:**
```
OK: has create_agent: True
```

**Step 3: Commit**

```bash
git add miniautogen/tui/data_provider.py
git commit -m "feat(server): implement CRUD write operations in DashDataProvider"
```

**If Task Fails:**
1. `_create_pipeline` may have a different signature. Read `miniautogen/cli/services/pipeline_ops.py` for the actual function signature.
2. `_update_agent` returns `{"before": ..., "after": ...}` -- confirm this pattern by reading `miniautogen/cli/services/agent_ops.py:update_agent`.
3. Rollback: `git checkout -- miniautogen/tui/data_provider.py`

---

### Task 14: Implement write methods in StandaloneProvider

**Files:**
- Modify: `miniautogen/server/standalone_provider.py`

**Prerequisites:**
- Task 12 complete

**Step 1: Add CRUD delegation to StandaloneProvider**

Add these methods to `StandaloneProvider` class, after the existing `get_pipeline` method:

```python
    # -- Write operations (delegated to base provider) -------------------------

    def create_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._base.create_agent(data)

    def update_agent(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._base.update_agent(name, data)

    def delete_agent(self, name: str) -> dict[str, Any]:
        return self._base.delete_agent(name)

    def create_flow(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._base.create_flow(data)

    def update_flow(self, name: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._base.update_flow(name, data)

    def delete_flow(self, name: str) -> dict[str, Any]:
        return self._base.delete_flow(name)
```

**Step 2: Verify**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.server.standalone_provider import StandaloneProvider; print('OK')"`

**Expected output:**
```
OK
```

**Step 3: Commit**

```bash
git add miniautogen/server/standalone_provider.py
git commit -m "feat(server): delegate CRUD writes in StandaloneProvider to base"
```

**If Task Fails:**
1. Rollback: `git checkout -- miniautogen/server/standalone_provider.py`

---

### Task 15: Add Pydantic request models for CRUD

**Files:**
- Modify: `miniautogen/server/models.py`

**Prerequisites:**
- None

**Step 1: Add request models**

Add the following models to `miniautogen/server/models.py` (after the `ErrorResponse` class):

```python
class CreateAgentRequest(BaseModel):
    """Request payload for creating an agent."""
    name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    role: str = Field(..., min_length=1, max_length=256)
    goal: str = Field("", max_length=2000)
    engine_profile: str = Field("default_api", min_length=1, max_length=128)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=1_000_000)


class UpdateAgentRequest(BaseModel):
    """Request payload for updating an agent."""
    role: str | None = Field(None, min_length=1, max_length=256)
    goal: str | None = Field(None, max_length=2000)
    engine_profile: str | None = Field(None, min_length=1, max_length=128)
    temperature: float | None = Field(None, ge=0.0, le=2.0)


class CreateFlowRequest(BaseModel):
    """Request payload for creating a flow."""
    name: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    mode: str = Field(..., min_length=1, max_length=64)
    participants: list[str] = Field(default_factory=list)
    leader: str | None = Field(None, max_length=128)
    max_rounds: int | None = Field(None, ge=1, le=100)


class UpdateFlowRequest(BaseModel):
    """Request payload for updating a flow."""
    mode: str | None = Field(None, min_length=1, max_length=64)
    participants: list[str] | None = None
    leader: str | None = Field(None, max_length=128)
    max_rounds: int | None = Field(None, ge=1, le=100)
```

**Step 2: Verify**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.server.models import CreateAgentRequest, CreateFlowRequest; print('OK')"`

**Expected output:**
```
OK
```

**Step 3: Commit**

```bash
git add miniautogen/server/models.py
git commit -m "feat(server): add Pydantic request models for CRUD operations"
```

**If Task Fails:**
1. Rollback: `git checkout -- miniautogen/server/models.py`

---

### Task 16: Add CRUD endpoints to agents router

**Files:**
- Modify: `miniautogen/server/routes/agents.py`

**Prerequisites:**
- Tasks 12, 15 complete

**Step 1: Add POST/PUT/DELETE endpoints**

Replace the contents of `miniautogen/server/routes/agents.py` with:

```python
"""Agent endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from miniautogen.server.models import (
    CreateAgentRequest,
    ErrorResponse,
    UpdateAgentRequest,
)
from miniautogen.server.provider_protocol import ConsoleDataProvider


def agents_router(provider: ConsoleDataProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["agents"])

    @router.get("/agents")
    async def list_agents() -> list[dict[str, Any]]:
        agents = [dict(a) for a in provider.get_agents()]
        for a in agents:
            a.setdefault("engine_type", a.get("engine_profile", "unknown"))
        return agents

    @router.get("/agents/{name}", responses={404: {"model": ErrorResponse}})
    async def get_agent(name: str) -> dict[str, Any]:
        try:
            agent = dict(provider.get_agent(name))
            agent.setdefault("engine_type", agent.get("engine_profile", "unknown"))
            return agent
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Agent '{name}' not found",
                    code="agent_not_found",
                ).model_dump(),
            )

    @router.post("/agents", status_code=201, responses={409: {"model": ErrorResponse}})
    async def create_agent(request: CreateAgentRequest) -> dict[str, Any]:
        try:
            return provider.create_agent(request.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=str(exc),
                    code="agent_create_failed",
                ).model_dump(),
            )

    @router.put("/agents/{name}", responses={404: {"model": ErrorResponse}})
    async def update_agent(name: str, request: UpdateAgentRequest) -> dict[str, Any]:
        updates = request.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="No updates provided",
                    code="empty_update",
                ).model_dump(),
            )
        try:
            return provider.update_agent(name, updates)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Agent '{name}' not found",
                    code="agent_not_found",
                ).model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=str(exc),
                    code="agent_update_failed",
                ).model_dump(),
            )

    @router.delete("/agents/{name}", responses={404: {"model": ErrorResponse}})
    async def delete_agent(name: str) -> dict[str, Any]:
        try:
            return provider.delete_agent(name)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Agent '{name}' not found",
                    code="agent_not_found",
                ).model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=str(exc),
                    code="agent_delete_failed",
                ).model_dump(),
            )

    return router
```

**Step 2: Verify server imports**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.server.routes.agents import agents_router; print('OK')"`

**Expected output:**
```
OK
```

**Step 3: Commit**

```bash
git add miniautogen/server/routes/agents.py
git commit -m "feat(server): add POST/PUT/DELETE CRUD endpoints for agents"
```

**If Task Fails:**
1. Rollback: `git checkout -- miniautogen/server/routes/agents.py`

---

### Task 17: Add CRUD endpoints to flows router

**Files:**
- Modify: `miniautogen/server/routes/flows.py`

**Prerequisites:**
- Tasks 12, 15 complete

**Step 1: Add POST/PUT/DELETE endpoints**

Replace the contents of `miniautogen/server/routes/flows.py` with:

```python
"""Flow endpoints.

Note: "flow" is the user-facing term for what the codebase calls "pipeline".
The translation occurs in this router layer.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from miniautogen.server.models import (
    CreateFlowRequest,
    ErrorResponse,
    UpdateFlowRequest,
)
from miniautogen.server.provider_protocol import ConsoleDataProvider


def flows_router(provider: ConsoleDataProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["flows"])

    @router.get("/flows")
    async def list_flows() -> list[dict[str, Any]]:
        return provider.get_pipelines()

    @router.get("/flows/{name}", responses={404: {"model": ErrorResponse}})
    async def get_flow(name: str) -> dict[str, Any]:
        try:
            return provider.get_pipeline(name)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Flow '{name}' not found",
                    code="flow_not_found",
                ).model_dump(),
            )

    @router.post("/flows", status_code=201, responses={409: {"model": ErrorResponse}})
    async def create_flow(request: CreateFlowRequest) -> dict[str, Any]:
        try:
            return provider.create_flow(request.model_dump(exclude_none=True))
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=str(exc),
                    code="flow_create_failed",
                ).model_dump(),
            )

    @router.put("/flows/{name}", responses={404: {"model": ErrorResponse}})
    async def update_flow(name: str, request: UpdateFlowRequest) -> dict[str, Any]:
        updates = request.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="No updates provided",
                    code="empty_update",
                ).model_dump(),
            )
        try:
            return provider.update_flow(name, updates)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Flow '{name}' not found",
                    code="flow_not_found",
                ).model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error=str(exc),
                    code="flow_update_failed",
                ).model_dump(),
            )

    @router.delete("/flows/{name}", responses={404: {"model": ErrorResponse}})
    async def delete_flow(name: str) -> dict[str, Any]:
        try:
            return provider.delete_flow(name)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail=ErrorResponse(
                    error=f"Flow '{name}' not found",
                    code="flow_not_found",
                ).model_dump(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=str(exc),
                    code="flow_delete_failed",
                ).model_dump(),
            )

    return router
```

**Step 2: Verify**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -c "from miniautogen.server.routes.flows import flows_router; print('OK')"`

**Expected output:**
```
OK
```

**Step 3: Commit**

```bash
git add miniautogen/server/routes/flows.py
git commit -m "feat(server): add POST/PUT/DELETE CRUD endpoints for flows"
```

**If Task Fails:**
1. Rollback: `git checkout -- miniautogen/server/routes/flows.py`

---

### Task 18: Write API tests for agents CRUD

**Files:**
- Modify: `tests/server/test_agents.py`

**Prerequisites:**
- Tasks 12, 15, 16 complete

**Step 1: Update conftest mock provider**

In `tests/server/conftest.py`, add mock methods for CRUD operations to the `mock_provider` fixture. Add these lines after `provider.update_run = MagicMock(side_effect=_update_run)`:

```python
    # CRUD mocks
    provider.create_agent = MagicMock(return_value={
        "id": "new-agent", "name": "new-agent", "role": "Tester",
        "goal": "Test things", "engine_profile": "default_api",
    })
    provider.update_agent = MagicMock(return_value={
        "name": "researcher", "role": "Updated Role",
        "engine_profile": "default_api",
    })
    provider.delete_agent = MagicMock(return_value={"deleted": "researcher"})

    provider.create_flow = MagicMock(return_value={
        "name": "new-flow", "mode": "workflow", "participants": ["researcher"],
    })
    provider.update_flow = MagicMock(return_value={
        "name": "main", "mode": "deliberation",
    })
    provider.delete_flow = MagicMock(return_value={"deleted": "main"})
```

**Step 2: Add CRUD tests to test_agents.py**

Append these tests to `tests/server/test_agents.py`:

```python
def test_create_agent(client):
    resp = client.post("/api/v1/agents", json={
        "name": "new-agent",
        "role": "Tester",
        "goal": "Test things",
        "engine_profile": "default_api",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "new-agent"


def test_create_agent_invalid_name(client):
    resp = client.post("/api/v1/agents", json={
        "name": "123-invalid",
        "role": "Tester",
    })
    assert resp.status_code == 422  # Pydantic validation


def test_update_agent(client):
    resp = client.put("/api/v1/agents/researcher", json={
        "role": "Updated Role",
    })
    assert resp.status_code == 200


def test_update_agent_empty(client):
    resp = client.put("/api/v1/agents/researcher", json={})
    assert resp.status_code == 400
    assert resp.json()["code"] == "empty_update"


def test_update_agent_not_found(client, mock_provider):
    mock_provider.update_agent.side_effect = KeyError("nope")
    resp = client.put("/api/v1/agents/ghost", json={"role": "X"})
    assert resp.status_code == 404


def test_delete_agent(client):
    resp = client.delete("/api/v1/agents/researcher")
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] == "researcher"


def test_delete_agent_not_found(client, mock_provider):
    mock_provider.delete_agent.side_effect = KeyError("nope")
    resp = client.delete("/api/v1/agents/ghost")
    assert resp.status_code == 404


def test_delete_agent_referenced(client, mock_provider):
    mock_provider.delete_agent.side_effect = ValueError("referenced by pipeline")
    resp = client.delete("/api/v1/agents/researcher")
    assert resp.status_code == 409
```

**Step 3: Run the tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/server/test_agents.py -v`

**Expected output:** All tests pass (old + new).

**Step 4: Commit**

```bash
git add tests/server/conftest.py tests/server/test_agents.py
git commit -m "test(server): add CRUD tests for agents API endpoints"
```

**If Task Fails:**
1. 422 status code might differ if Pydantic validation errors are handled differently by FastAPI version.
2. Rollback: `git checkout -- tests/server/conftest.py tests/server/test_agents.py`

---

### Task 19: Write API tests for flows CRUD

**Files:**
- Modify: `tests/server/test_flows.py`

**Prerequisites:**
- Tasks 12, 15, 17, 18 (conftest update) complete

**Step 1: Add CRUD tests to test_flows.py**

Read `tests/server/test_flows.py` to see existing tests, then append:

```python
def test_create_flow(client):
    resp = client.post("/api/v1/flows", json={
        "name": "new-flow",
        "mode": "workflow",
        "participants": ["researcher"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "new-flow"


def test_create_flow_invalid_name(client):
    resp = client.post("/api/v1/flows", json={
        "name": "123bad",
        "mode": "workflow",
    })
    assert resp.status_code == 422


def test_update_flow(client):
    resp = client.put("/api/v1/flows/main", json={
        "mode": "deliberation",
    })
    assert resp.status_code == 200


def test_update_flow_empty(client):
    resp = client.put("/api/v1/flows/main", json={})
    assert resp.status_code == 400


def test_update_flow_not_found(client, mock_provider):
    mock_provider.update_flow.side_effect = KeyError("nope")
    resp = client.put("/api/v1/flows/ghost", json={"mode": "loop"})
    assert resp.status_code == 404


def test_delete_flow(client):
    resp = client.delete("/api/v1/flows/main")
    assert resp.status_code == 200


def test_delete_flow_not_found(client, mock_provider):
    mock_provider.delete_flow.side_effect = KeyError("nope")
    resp = client.delete("/api/v1/flows/ghost")
    assert resp.status_code == 404
```

**Step 2: Run the tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/server/test_flows.py -v`

**Expected output:** All tests pass.

**Step 3: Commit**

```bash
git add tests/server/test_flows.py
git commit -m "test(server): add CRUD tests for flows API endpoints"
```

**If Task Fails:**
1. Rollback: `git checkout -- tests/server/test_flows.py`

---

### Task 20: Add CRUD API methods to frontend api-client

**Files:**
- Modify: `console/src/lib/api-client.ts`
- Modify: `console/src/types/api.ts`

**Prerequisites:**
- Tasks 16, 17 complete (backend endpoints exist)

**Step 1: Add types for CRUD operations**

In `console/src/types/api.ts`, add after the existing `Agent` type:

```typescript
export type AgentDetail = Agent & {
  goal?: string;
  engine_profile?: string;
  description?: string;
  id?: string;
  version?: string;
  raw?: Record<string, unknown>;
};

export type CreateAgentPayload = {
  name: string;
  role: string;
  goal?: string;
  engine_profile?: string;
  temperature?: number;
  max_tokens?: number;
};

export type UpdateAgentPayload = {
  role?: string;
  goal?: string;
  engine_profile?: string;
  temperature?: number;
};

export type CreateFlowPayload = {
  name: string;
  mode: string;
  participants?: string[];
  leader?: string;
  max_rounds?: number;
};

export type UpdateFlowPayload = {
  mode?: string;
  participants?: string[];
  leader?: string;
  max_rounds?: number;
};
```

**Step 2: Add API methods**

In `console/src/lib/api-client.ts`, add these methods to the `api` object (before the closing `};`):

```typescript
  // Agent CRUD
  createAgent: (data: import('@/types/api').CreateAgentPayload) =>
    apiFetch<import('@/types/api').AgentDetail>('/agents', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateAgent: (name: string, data: import('@/types/api').UpdateAgentPayload) =>
    apiFetch<import('@/types/api').AgentDetail>(`/agents/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteAgent: (name: string) =>
    apiFetch<{ deleted: string }>(`/agents/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),
  // Flow CRUD
  createFlow: (data: import('@/types/api').CreateFlowPayload) =>
    apiFetch<import('@/types/api').Flow>('/flows', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateFlow: (name: string, data: import('@/types/api').UpdateFlowPayload) =>
    apiFetch<import('@/types/api').Flow>(`/flows/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  deleteFlow: (name: string) =>
    apiFetch<{ deleted: string }>(`/flows/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),
```

**Step 3: Verify TypeScript compiles**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen/console && npx tsc --noEmit 2>&1 | head -20`

**Expected output:** No errors (or only pre-existing errors).

**Step 4: Commit**

```bash
git add console/src/lib/api-client.ts console/src/types/api.ts
git commit -m "feat(console): add CRUD API methods and types for agents and flows"
```

**If Task Fails:**
1. TypeScript import path issues: Use `type` imports at the top of the file instead of inline `import()`.
2. Rollback: `git checkout -- console/src/lib/api-client.ts console/src/types/api.ts`

---

### Task 21: Add CRUD React hooks

**Files:**
- Modify: `console/src/hooks/useApi.ts`

**Prerequisites:**
- Task 20 complete

**Step 1: Add mutation hooks**

Add these hooks at the end of `console/src/hooks/useApi.ts` (before the closing of the file):

```typescript
export function useCreateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: import('@/types/api').CreateAgentPayload) =>
      api.createAgent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      queryClient.invalidateQueries({ queryKey: ['workspace'] });
    },
  });
}

export function useUpdateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: import('@/types/api').UpdateAgentPayload }) =>
      api.updateAgent(name, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      queryClient.invalidateQueries({ queryKey: ['agent', variables.name] });
    },
  });
}

export function useDeleteAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.deleteAgent(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] });
      queryClient.invalidateQueries({ queryKey: ['workspace'] });
    },
  });
}

export function useCreateFlow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: import('@/types/api').CreateFlowPayload) =>
      api.createFlow(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] });
      queryClient.invalidateQueries({ queryKey: ['workspace'] });
    },
  });
}

export function useUpdateFlow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: import('@/types/api').UpdateFlowPayload }) =>
      api.updateFlow(name, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['flows'] });
      queryClient.invalidateQueries({ queryKey: ['flow', variables.name] });
    },
  });
}

export function useDeleteFlow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.deleteFlow(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] });
      queryClient.invalidateQueries({ queryKey: ['workspace'] });
    },
  });
}
```

**Step 2: Verify**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen/console && npx tsc --noEmit 2>&1 | head -20`

**Expected output:** No new errors.

**Step 3: Commit**

```bash
git add console/src/hooks/useApi.ts
git commit -m "feat(console): add React mutation hooks for CRUD operations"
```

**If Task Fails:**
1. Rollback: `git checkout -- console/src/hooks/useApi.ts`

---

### Task 22: Create DeleteConfirmModal component

**Files:**
- Create: `console/src/components/DeleteConfirmModal.tsx`

**Prerequisites:**
- None (standalone component)

**Step 1: Create the modal component**

Create file `console/src/components/DeleteConfirmModal.tsx`:
```tsx
'use client';

import { useState } from 'react';

type DeleteConfirmModalProps = {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
  isDeleting?: boolean;
};

export function DeleteConfirmModal({
  isOpen,
  title,
  message,
  onConfirm,
  onCancel,
  isDeleting = false,
}: DeleteConfirmModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/60" onClick={onCancel} />
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl">
        <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
        <p className="text-sm text-gray-400 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add console/src/components/DeleteConfirmModal.tsx
git commit -m "feat(console): add DeleteConfirmModal reusable component"
```

---

### Task 23: Create AgentForm component

**Files:**
- Create: `console/src/components/AgentForm.tsx`

**Prerequisites:**
- Task 21 (hooks), Task 20 (types)

**Step 1: Create the agent form component**

Create file `console/src/components/AgentForm.tsx`:
```tsx
'use client';

import { useState } from 'react';
import type { CreateAgentPayload, UpdateAgentPayload, Agent } from '@/types/api';

type AgentFormProps = {
  mode: 'create' | 'edit';
  initialData?: Partial<Agent & { goal?: string; engine_profile?: string }>;
  onSubmit: (data: CreateAgentPayload | UpdateAgentPayload) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
  error?: string | null;
};

export function AgentForm({
  mode,
  initialData,
  onSubmit,
  onCancel,
  isSubmitting = false,
  error = null,
}: AgentFormProps) {
  const [name, setName] = useState(initialData?.name ?? '');
  const [role, setRole] = useState(initialData?.role ?? '');
  const [goal, setGoal] = useState(initialData?.goal ?? '');
  const [engineProfile, setEngineProfile] = useState(initialData?.engine_profile ?? 'default_api');
  const [temperature, setTemperature] = useState<string>(
    initialData?.temperature?.toString() ?? ''
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'create') {
      const payload: CreateAgentPayload = {
        name,
        role,
        goal: goal || undefined,
        engine_profile: engineProfile || undefined,
        temperature: temperature ? parseFloat(temperature) : undefined,
      };
      onSubmit(payload);
    } else {
      const payload: UpdateAgentPayload = {
        role: role || undefined,
        goal: goal || undefined,
        engine_profile: engineProfile || undefined,
        temperature: temperature ? parseFloat(temperature) : undefined,
      };
      onSubmit(payload);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {mode === 'create' && (
        <div>
          <label htmlFor="agent-name" className="block text-sm font-medium text-gray-400 mb-1">Name</label>
          <input
            id="agent-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            pattern="^[a-zA-Z][a-zA-Z0-9_-]*$"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="e.g., researcher"
          />
        </div>
      )}

      <div>
        <label htmlFor="agent-role" className="block text-sm font-medium text-gray-400 mb-1">Role</label>
        <input
          id="agent-role"
          type="text"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          required
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="e.g., Research Specialist"
        />
      </div>

      <div>
        <label htmlFor="agent-goal" className="block text-sm font-medium text-gray-400 mb-1">Goal</label>
        <textarea
          id="agent-goal"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          rows={3}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="What should this agent accomplish?"
        />
      </div>

      <div>
        <label htmlFor="agent-engine" className="block text-sm font-medium text-gray-400 mb-1">Engine Profile</label>
        <input
          id="agent-engine"
          type="text"
          value={engineProfile}
          onChange={(e) => setEngineProfile(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="default_api"
        />
      </div>

      <div>
        <label htmlFor="agent-temp" className="block text-sm font-medium text-gray-400 mb-1">Temperature (optional)</label>
        <input
          id="agent-temp"
          type="number"
          step="0.1"
          min="0"
          max="2"
          value={temperature}
          onChange={(e) => setTemperature(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="0.2"
        />
      </div>

      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
        >
          {isSubmitting ? (mode === 'create' ? 'Creating...' : 'Saving...') : (mode === 'create' ? 'Create Agent' : 'Save Changes')}
        </button>
      </div>
    </form>
  );
}
```

**Step 2: Commit**

```bash
git add console/src/components/AgentForm.tsx
git commit -m "feat(console): add AgentForm component for create/edit"
```

---

### Task 24: Create agent CRUD pages (new, edit) and update agents list page

**Files:**
- Create: `console/src/app/agents/new/page.tsx`
- Create: `console/src/app/agents/edit/page.tsx`
- Modify: `console/src/app/agents/page.tsx` (add create button + delete)

**Prerequisites:**
- Tasks 21, 22, 23 complete

**Step 1: Create the "new agent" page**

Create file `console/src/app/agents/new/page.tsx`:
```tsx
'use client';

import { useRouter } from 'next/navigation';
import { AgentForm } from '@/components/AgentForm';
import { useCreateAgent } from '@/hooks/useApi';
import type { CreateAgentPayload } from '@/types/api';

export default function NewAgentPage() {
  const router = useRouter();
  const createAgent = useCreateAgent();

  const handleSubmit = (data: CreateAgentPayload | Record<string, unknown>) => {
    createAgent.mutate(data as CreateAgentPayload, {
      onSuccess: () => router.push('/agents'),
    });
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Create Agent</h2>
      <AgentForm
        mode="create"
        onSubmit={handleSubmit}
        onCancel={() => router.push('/agents')}
        isSubmitting={createAgent.isPending}
        error={createAgent.isError ? (createAgent.error instanceof Error ? createAgent.error.message : 'Failed to create agent') : null}
      />
    </div>
  );
}
```

**Step 2: Create the "edit agent" page**

Create file `console/src/app/agents/edit/page.tsx`:
```tsx
'use client';

import { useSearchParams, useRouter } from 'next/navigation';
import { AgentForm } from '@/components/AgentForm';
import { useAgent, useUpdateAgent } from '@/hooks/useApi';
import { SkeletonCards } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';
import type { UpdateAgentPayload } from '@/types/api';

export default function EditAgentPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const name = searchParams.get('name') ?? '';
  const { data: agent, isLoading, error, refetch } = useAgent(name);
  const updateAgent = useUpdateAgent();

  if (isLoading) return <SkeletonCards count={1} />;
  if (error) return <QueryError error={error as Error} message="Failed to load agent" onRetry={refetch} />;
  if (!agent) return <p className="text-gray-500">Agent not found.</p>;

  const handleSubmit = (data: UpdateAgentPayload | Record<string, unknown>) => {
    updateAgent.mutate({ name, data: data as UpdateAgentPayload }, {
      onSuccess: () => router.push('/agents'),
    });
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Edit Agent: {name}</h2>
      <AgentForm
        mode="edit"
        initialData={agent}
        onSubmit={handleSubmit}
        onCancel={() => router.push('/agents')}
        isSubmitting={updateAgent.isPending}
        error={updateAgent.isError ? (updateAgent.error instanceof Error ? updateAgent.error.message : 'Failed to update agent') : null}
      />
    </div>
  );
}
```

**Step 3: Update agents list page with create button and delete**

Replace `console/src/app/agents/page.tsx` with:
```tsx
'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { useDeleteAgent } from '@/hooks/useApi';
import type { Agent } from '@/types/api';
import { SkeletonTable } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';

export default function AgentsPage() {
  const { data: agents, isLoading, error, refetch } = useQuery({ queryKey: ['agents'], queryFn: api.getAgents });
  const deleteAgent = useDeleteAgent();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  if (isLoading) return <SkeletonTable rows={5} cols={3} />;
  if (error) return <QueryError error={error as Error} message="Failed to load agents" onRetry={refetch} />;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Agents</h2>
        <Link
          href="/agents/new"
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          + New Agent
        </Link>
      </div>
      <div className="border border-gray-800 rounded-lg bg-gray-900">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-800">
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Agent</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
              <th className="text-left p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Engine</th>
              <th className="text-right p-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(agents ?? []).map((agent: Agent) => (
              <tr key={agent.name} className="border-b border-gray-800 last:border-0 hover:bg-gray-800/30 transition-colors">
                <td className="p-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-500/10 flex items-center justify-center text-blue-400 text-xs font-bold uppercase">
                      {agent.name.slice(0, 2)}
                    </div>
                    <span className="font-mono text-sm">{agent.name}</span>
                  </div>
                </td>
                <td className="p-3 text-sm text-gray-300">{agent.role}</td>
                <td className="p-3">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 border border-gray-700">
                    {agent.engine_type || agent.engine_profile}
                  </span>
                </td>
                <td className="p-3 text-right">
                  <div className="flex justify-end gap-2">
                    <Link
                      href={`/agents/edit?name=${encodeURIComponent(agent.name)}`}
                      className="text-xs px-2 py-1 text-gray-400 hover:text-white border border-gray-700 rounded transition-colors"
                    >
                      Edit
                    </Link>
                    <button
                      type="button"
                      onClick={() => setDeleteTarget(agent.name)}
                      className="text-xs px-2 py-1 text-red-400 hover:text-red-300 border border-gray-700 rounded transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <DeleteConfirmModal
        isOpen={deleteTarget !== null}
        title="Delete Agent"
        message={`Are you sure you want to delete agent "${deleteTarget}"? This action cannot be undone.`}
        onConfirm={() => {
          if (deleteTarget) {
            deleteAgent.mutate(deleteTarget, {
              onSuccess: () => setDeleteTarget(null),
            });
          }
        }}
        onCancel={() => setDeleteTarget(null)}
        isDeleting={deleteAgent.isPending}
      />
    </div>
  );
}
```

**Step 4: Commit**

```bash
git add console/src/app/agents/new/page.tsx console/src/app/agents/edit/page.tsx console/src/app/agents/page.tsx
git commit -m "feat(console): add agent create/edit/delete pages"
```

**If Task Fails:**
1. Next.js routing: Ensure `console/src/app/agents/new/` and `console/src/app/agents/edit/` directories exist before creating the files.
2. `useSearchParams` requires Suspense boundary in some Next.js versions. May need to wrap component.
3. Rollback: `git checkout -- console/src/app/agents/`

---

### Task 25: Create flow CRUD pages and update flows list page

**Files:**
- Create: `console/src/components/FlowForm.tsx`
- Create: `console/src/app/flows/new/page.tsx`
- Create: `console/src/app/flows/edit/page.tsx`
- Modify: `console/src/app/flows/page.tsx` (add create button + delete)

**Prerequisites:**
- Tasks 21, 22 complete

**Step 1: Create FlowForm component**

Create file `console/src/components/FlowForm.tsx`:
```tsx
'use client';

import { useState } from 'react';
import type { CreateFlowPayload, UpdateFlowPayload } from '@/types/api';

type FlowFormProps = {
  mode: 'create' | 'edit';
  initialData?: Partial<{ name: string; mode: string; participants: string[]; leader: string | null; max_rounds: number | null }>;
  onSubmit: (data: CreateFlowPayload | UpdateFlowPayload) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
  error?: string | null;
};

const MODES = ['workflow', 'deliberation', 'loop', 'group_chat', 'debate'];

export function FlowForm({
  mode: formMode,
  initialData,
  onSubmit,
  onCancel,
  isSubmitting = false,
  error = null,
}: FlowFormProps) {
  const [name, setName] = useState(initialData?.name ?? '');
  const [flowMode, setFlowMode] = useState(initialData?.mode ?? 'workflow');
  const [participants, setParticipants] = useState(initialData?.participants?.join(', ') ?? '');
  const [leader, setLeader] = useState(initialData?.leader ?? '');
  const [maxRounds, setMaxRounds] = useState<string>(initialData?.max_rounds?.toString() ?? '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const participantList = participants.split(',').map(p => p.trim()).filter(Boolean);

    if (formMode === 'create') {
      const payload: CreateFlowPayload = {
        name,
        mode: flowMode,
        participants: participantList.length > 0 ? participantList : undefined,
        leader: leader || undefined,
        max_rounds: maxRounds ? parseInt(maxRounds, 10) : undefined,
      };
      onSubmit(payload);
    } else {
      const payload: UpdateFlowPayload = {
        mode: flowMode || undefined,
        participants: participantList.length > 0 ? participantList : undefined,
        leader: leader || undefined,
        max_rounds: maxRounds ? parseInt(maxRounds, 10) : undefined,
      };
      onSubmit(payload);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {formMode === 'create' && (
        <div>
          <label htmlFor="flow-name" className="block text-sm font-medium text-gray-400 mb-1">Name</label>
          <input
            id="flow-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            pattern="^[a-zA-Z][a-zA-Z0-9_-]*$"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="e.g., dev-workflow"
          />
        </div>
      )}

      <div>
        <label htmlFor="flow-mode" className="block text-sm font-medium text-gray-400 mb-1">Mode</label>
        <select
          id="flow-mode"
          value={flowMode}
          onChange={(e) => setFlowMode(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          {MODES.map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="flow-participants" className="block text-sm font-medium text-gray-400 mb-1">Participants (comma-separated)</label>
        <input
          id="flow-participants"
          type="text"
          value={participants}
          onChange={(e) => setParticipants(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="e.g., researcher, writer, reviewer"
        />
      </div>

      {(flowMode === 'deliberation') && (
        <div>
          <label htmlFor="flow-leader" className="block text-sm font-medium text-gray-400 mb-1">Leader</label>
          <input
            id="flow-leader"
            type="text"
            value={leader}
            onChange={(e) => setLeader(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="Leader agent name"
          />
        </div>
      )}

      {(flowMode === 'deliberation') && (
        <div>
          <label htmlFor="flow-rounds" className="block text-sm font-medium text-gray-400 mb-1">Max Rounds</label>
          <input
            id="flow-rounds"
            type="number"
            min="1"
            max="100"
            value={maxRounds}
            onChange={(e) => setMaxRounds(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="3"
          />
        </div>
      )}

      <div className="flex justify-end gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
        >
          {isSubmitting ? (formMode === 'create' ? 'Creating...' : 'Saving...') : (formMode === 'create' ? 'Create Flow' : 'Save Changes')}
        </button>
      </div>
    </form>
  );
}
```

**Step 2: Create new flow page**

Create file `console/src/app/flows/new/page.tsx`:
```tsx
'use client';

import { useRouter } from 'next/navigation';
import { FlowForm } from '@/components/FlowForm';
import { useCreateFlow } from '@/hooks/useApi';
import type { CreateFlowPayload } from '@/types/api';

export default function NewFlowPage() {
  const router = useRouter();
  const createFlow = useCreateFlow();

  const handleSubmit = (data: CreateFlowPayload | Record<string, unknown>) => {
    createFlow.mutate(data as CreateFlowPayload, {
      onSuccess: () => router.push('/flows'),
    });
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Create Flow</h2>
      <FlowForm
        mode="create"
        onSubmit={handleSubmit}
        onCancel={() => router.push('/flows')}
        isSubmitting={createFlow.isPending}
        error={createFlow.isError ? (createFlow.error instanceof Error ? createFlow.error.message : 'Failed to create flow') : null}
      />
    </div>
  );
}
```

**Step 3: Create edit flow page**

Create file `console/src/app/flows/edit/page.tsx`:
```tsx
'use client';

import { useSearchParams, useRouter } from 'next/navigation';
import { FlowForm } from '@/components/FlowForm';
import { useFlow, useUpdateFlow } from '@/hooks/useApi';
import { SkeletonCards } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';
import type { UpdateFlowPayload } from '@/types/api';

export default function EditFlowPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const name = searchParams.get('name') ?? '';
  const { data: flow, isLoading, error, refetch } = useFlow(name);
  const updateFlow = useUpdateFlow();

  if (isLoading) return <SkeletonCards count={1} />;
  if (error) return <QueryError error={error as Error} message="Failed to load flow" onRetry={refetch} />;
  if (!flow) return <p className="text-gray-500">Flow not found.</p>;

  const handleSubmit = (data: UpdateFlowPayload | Record<string, unknown>) => {
    updateFlow.mutate({ name, data: data as UpdateFlowPayload }, {
      onSuccess: () => router.push('/flows'),
    });
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Edit Flow: {name}</h2>
      <FlowForm
        mode="edit"
        initialData={flow}
        onSubmit={handleSubmit}
        onCancel={() => router.push('/flows')}
        isSubmitting={updateFlow.isPending}
        error={updateFlow.isError ? (updateFlow.error instanceof Error ? updateFlow.error.message : 'Failed to update flow') : null}
      />
    </div>
  );
}
```

**Step 4: Update flows list page**

Replace `console/src/app/flows/page.tsx` with:
```tsx
'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api-client';
import { useDeleteFlow } from '@/hooks/useApi';
import type { Flow } from '@/types/api';
import { SkeletonCards } from '@/components/Skeleton';
import { QueryError } from '@/components/QueryError';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';

export default function FlowsPage() {
  const { data: flows, isLoading, error, refetch } = useQuery({ queryKey: ['flows'], queryFn: api.getFlows });
  const deleteFlow = useDeleteFlow();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  if (isLoading) return <SkeletonCards count={3} />;
  if (error) return <QueryError error={error as Error} message="Failed to load flows" onRetry={refetch} />;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Flows</h2>
        <Link
          href="/flows/new"
          className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          + New Flow
        </Link>
      </div>
      <div className="grid gap-4">
        {(flows ?? []).map((flow: Flow) => (
          <div
            key={flow.name}
            className="border border-gray-800 rounded-lg p-4 bg-gray-900/50 hover:bg-gray-800/50 hover:border-gray-700 transition-all"
          >
            <div className="flex items-center justify-between mb-2">
              <Link href={`/flows/detail?name=${flow.name}`} className="font-mono font-bold hover:text-blue-400 transition-colors">
                {flow.name}
              </Link>
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  flow.mode === 'workflow' ? 'bg-blue-500/10 text-blue-400' :
                  flow.mode === 'deliberation' ? 'bg-purple-500/10 text-purple-400' :
                  flow.mode === 'loop' ? 'bg-green-500/10 text-green-400' :
                  'bg-gray-500/10 text-gray-400'
                }`}>
                  {flow.mode}
                </span>
                <Link
                  href={`/flows/edit?name=${encodeURIComponent(flow.name)}`}
                  className="text-xs px-2 py-1 text-gray-400 hover:text-white border border-gray-700 rounded transition-colors"
                >
                  Edit
                </Link>
                <button
                  type="button"
                  onClick={() => setDeleteTarget(flow.name)}
                  className="text-xs px-2 py-1 text-red-400 hover:text-red-300 border border-gray-700 rounded transition-colors"
                >
                  Delete
                </button>
              </div>
            </div>
            <p className="text-sm text-gray-500">
              {flow.participants.length} agent{flow.participants.length !== 1 ? 's' : ''}: {flow.participants.join(', ')}
            </p>
            {flow.leader && (
              <p className="text-xs text-gray-600 mt-1">Leader: {flow.leader}</p>
            )}
          </div>
        ))}
      </div>

      <DeleteConfirmModal
        isOpen={deleteTarget !== null}
        title="Delete Flow"
        message={`Are you sure you want to delete flow "${deleteTarget}"? This action cannot be undone.`}
        onConfirm={() => {
          if (deleteTarget) {
            deleteFlow.mutate(deleteTarget, {
              onSuccess: () => setDeleteTarget(null),
            });
          }
        }}
        onCancel={() => setDeleteTarget(null)}
        isDeleting={deleteFlow.isPending}
      />
    </div>
  );
}
```

**Step 5: Commit**

```bash
git add console/src/components/FlowForm.tsx console/src/app/flows/new/page.tsx console/src/app/flows/edit/page.tsx console/src/app/flows/page.tsx
git commit -m "feat(console): add flow create/edit/delete pages and FlowForm component"
```

**If Task Fails:**
1. Next.js directory routing: Ensure `flows/new/` and `flows/edit/` directories are created.
2. Rollback: `git checkout -- console/src/components/FlowForm.tsx console/src/app/flows/`

---

### Task 26: Run Code Review (G3)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately

**Low Issues:**
- Add `TODO(review):` comments

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain

---

## G4: Init Templates -- quickstart, minimal, advanced

### Task 27: Create quickstart template files

**Files:**
- Create: `miniautogen/cli/templates/quickstart/miniautogen.yaml.j2`
- Create: `miniautogen/cli/templates/quickstart/agents/assistant.yaml.j2`
- Create: `miniautogen/cli/templates/quickstart/.env.j2`
- Create: `miniautogen/cli/templates/quickstart/.gitignore.j2`
- Create: `miniautogen/cli/templates/quickstart/README.md.j2`

**Prerequisites:**
- None

**Step 1: Create quickstart workspace config template**

Create file `miniautogen/cli/templates/quickstart/miniautogen.yaml.j2`:
```yaml
project:
  name: "{{ project_name }}"
  version: "0.1.0"

defaults:
  engine: default_api
  memory_profile: default

engines:
  default_api:
    kind: {{ "cli" if provider in ("gemini-cli", "claude-code", "codex-cli") else "api" }}
    provider: "{{ provider }}"
    model: "{{ model }}"
    temperature: 0.7

memory_profiles:
  default:
    session: true
    retrieval:
      enabled: false
    compaction:
      enabled: false

flows:
  main:
    mode: workflow
    participants:
      - assistant

database:
  url: sqlite+aiosqlite:///miniautogen.db
```

**Step 2: Create quickstart agent template**

Create file `miniautogen/cli/templates/quickstart/agents/assistant.yaml.j2`:
```yaml
id: assistant
version: "1.0.0"
name: Helpful Assistant
description: >
  A friendly AI assistant that helps with questions and tasks.

role: Assistant
goal: >
  Help users by answering questions clearly and concisely.

engine_profile: default_api

memory:
  profile: default
  session_memory: true
  retrieval_memory: false
  max_context_tokens: 8000

runtime:
  max_turns: 5
  timeout_seconds: 120
```

**Step 3: Create quickstart .env template**

Create file `miniautogen/cli/templates/quickstart/.env.j2`:
```
# MiniAutoGen environment configuration
# Set your API key for the configured provider

{% if provider == "openai" %}
OPENAI_API_KEY=sk-your-key-here
{% elif provider == "anthropic" %}
ANTHROPIC_API_KEY=sk-ant-your-key-here
{% elif provider == "google" %}
GOOGLE_API_KEY=your-key-here
{% else %}
# Set the API key for your provider
# OPENAI_API_KEY=sk-your-key-here
{% endif %}
```

**Step 4: Create quickstart .gitignore template**

Create file `miniautogen/cli/templates/quickstart/.gitignore.j2`:
```
.env
*.db
__pycache__/
.miniautogen/
```

**Step 5: Create quickstart README template**

Create file `miniautogen/cli/templates/quickstart/README.md.j2`:
```markdown
# {{ project_name }}

A MiniAutoGen workspace created with the quickstart template.

## Quick Start

1. Set your API key:
   ```bash
   cp .env.example .env  # or edit .env directly
   ```

2. Send a message:
   ```bash
   miniautogen send "Hello! What can you do?" --agent assistant
   ```

3. Start a chat:
   ```bash
   miniautogen chat assistant
   ```

4. Run the workflow:
   ```bash
   miniautogen run main --input "Tell me about this project"
   ```

5. Open the web console:
   ```bash
   miniautogen console
   ```

## Next Steps

- Add agents: `miniautogen agent create <name> --role "Role" --goal "Goal" --engine default_api`
- Create flows: `miniautogen flow create <name> --mode workflow`
- Check health: `miniautogen check`
- View docs: `miniautogen --help`
```

**Step 6: Commit**

```bash
git add miniautogen/cli/templates/quickstart/
git commit -m "feat(cli): add quickstart init template"
```

---

### Task 28: Create minimal and advanced templates

**Files:**
- Create: `miniautogen/cli/templates/minimal/miniautogen.yaml.j2`
- Create: `miniautogen/cli/templates/minimal/.env.j2`
- Create: `miniautogen/cli/templates/minimal/.gitignore.j2`
- Create: `miniautogen/cli/templates/advanced/miniautogen.yaml.j2`
- Create: `miniautogen/cli/templates/advanced/agents/architect.yaml.j2`
- Create: `miniautogen/cli/templates/advanced/agents/developer.yaml.j2`
- Create: `miniautogen/cli/templates/advanced/agents/reviewer.yaml.j2`
- Create: `miniautogen/cli/templates/advanced/.env.j2`
- Create: `miniautogen/cli/templates/advanced/.gitignore.j2`

**Prerequisites:**
- None

**Step 1: Create minimal template**

Create file `miniautogen/cli/templates/minimal/miniautogen.yaml.j2`:
```yaml
project:
  name: "{{ project_name }}"
  version: "0.1.0"

defaults:
  engine: default_api

engines:
  default_api:
    kind: {{ "cli" if provider in ("gemini-cli", "claude-code", "codex-cli") else "api" }}
    provider: "{{ provider }}"
    model: "{{ model }}"
```

Create file `miniautogen/cli/templates/minimal/.env.j2`:
```
# Set your API key
# OPENAI_API_KEY=sk-your-key-here
```

Create file `miniautogen/cli/templates/minimal/.gitignore.j2`:
```
.env
*.db
__pycache__/
.miniautogen/
```

**Step 2: Create advanced template agents**

Create file `miniautogen/cli/templates/advanced/miniautogen.yaml.j2`:
```yaml
project:
  name: "{{ project_name }}"
  version: "0.1.0"

defaults:
  engine: default_api
  memory_profile: default

engines:
  default_api:
    kind: {{ "cli" if provider in ("gemini-cli", "claude-code", "codex-cli") else "api" }}
    provider: "{{ provider }}"
    model: "{{ model }}"
    temperature: 0.2

memory_profiles:
  default:
    session: true
    retrieval:
      enabled: false
    compaction:
      enabled: false

flows:
  build:
    mode: workflow
    participants:
      - architect
      - developer
      - reviewer
  review:
    mode: deliberation
    participants:
      - architect
      - developer
      - reviewer
    leader: architect

database:
  url: sqlite+aiosqlite:///miniautogen.db
```

Create file `miniautogen/cli/templates/advanced/agents/architect.yaml.j2`:
```yaml
id: architect
version: "1.0.0"
name: Software Architect
role: Architect
goal: >
  Design software architecture, define interfaces, and make technical decisions.

engine_profile: default_api

runtime:
  max_turns: 10
  timeout_seconds: 300
```

Create file `miniautogen/cli/templates/advanced/agents/developer.yaml.j2`:
```yaml
id: developer
version: "1.0.0"
name: Software Developer
role: Developer
goal: >
  Implement features following the architect's design, write clean code.

engine_profile: default_api

runtime:
  max_turns: 10
  timeout_seconds: 300
```

Create file `miniautogen/cli/templates/advanced/agents/reviewer.yaml.j2`:
```yaml
id: reviewer
version: "1.0.0"
name: Code Reviewer
role: Reviewer
goal: >
  Review code for quality, security, and adherence to best practices.

engine_profile: default_api

runtime:
  max_turns: 10
  timeout_seconds: 300
```

Create file `miniautogen/cli/templates/advanced/.env.j2`:
```
# MiniAutoGen environment configuration
{% if provider == "openai" %}
OPENAI_API_KEY=sk-your-key-here
{% elif provider == "anthropic" %}
ANTHROPIC_API_KEY=sk-ant-your-key-here
{% elif provider == "google" %}
GOOGLE_API_KEY=your-key-here
{% else %}
# OPENAI_API_KEY=sk-your-key-here
{% endif %}
```

Create file `miniautogen/cli/templates/advanced/.gitignore.j2`:
```
.env
*.db
__pycache__/
.miniautogen/
```

**Step 3: Commit**

```bash
git add miniautogen/cli/templates/minimal/ miniautogen/cli/templates/advanced/
git commit -m "feat(cli): add minimal and advanced init templates"
```

---

### Task 29: Update init command and init_project service for templates

**Files:**
- Modify: `miniautogen/cli/commands/init.py`
- Modify: `miniautogen/cli/services/init_project.py`

**Prerequisites:**
- Tasks 27, 28 complete

**Step 1: Update init_project.py to support templates**

In `miniautogen/cli/services/init_project.py`, make these changes:

1. Add a `TEMPLATE_CONFIGS` dict mapping template names to their template maps.
2. Update `scaffold_project` to accept a `template` parameter.

The key changes are:

After `_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "project"`, add:

```python
_QUICKSTART_DIR = Path(__file__).parent.parent / "templates" / "quickstart"
_MINIMAL_DIR = Path(__file__).parent.parent / "templates" / "minimal"
_ADVANCED_DIR = Path(__file__).parent.parent / "templates" / "advanced"

_QUICKSTART_MAP: dict[str, str] = {
    "miniautogen.yaml.j2": "miniautogen.yaml",
    "agents/assistant.yaml.j2": "agents/assistant.yaml",
    ".env.j2": ".env",
    ".gitignore.j2": ".gitignore",
    "README.md.j2": "README.md",
}

_MINIMAL_MAP: dict[str, str] = {
    "miniautogen.yaml.j2": "miniautogen.yaml",
    ".env.j2": ".env",
    ".gitignore.j2": ".gitignore",
}

_ADVANCED_MAP: dict[str, str] = {
    "miniautogen.yaml.j2": "miniautogen.yaml",
    "agents/architect.yaml.j2": "agents/architect.yaml",
    "agents/developer.yaml.j2": "agents/developer.yaml",
    "agents/reviewer.yaml.j2": "agents/reviewer.yaml",
    ".env.j2": ".env",
    ".gitignore.j2": ".gitignore",
}

AVAILABLE_TEMPLATES = ("quickstart", "minimal", "advanced")
```

Update the `scaffold_project` function signature to add `template: str = "project"` parameter, and update the function body to select the correct template directory and map based on the template parameter. The logic should be:

```python
def scaffold_project(
    name: str,
    target_dir: Path,
    *,
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    include_examples: bool = True,
    force: bool = False,
    template: str = "project",
) -> Path:
```

Inside the function, after the name validation and directory creation, add template resolution:

```python
    # Resolve template directory and map
    if template == "quickstart":
        templates_dir = _QUICKSTART_DIR
        base_template_map = dict(_QUICKSTART_MAP)
    elif template == "minimal":
        templates_dir = _MINIMAL_DIR
        base_template_map = dict(_MINIMAL_MAP)
    elif template == "advanced":
        templates_dir = _ADVANCED_DIR
        base_template_map = dict(_ADVANCED_MAP)
    else:
        templates_dir = _TEMPLATES_DIR
        base_template_map = dict(_TEMPLATE_MAP)
```

Then use `templates_dir` for the Jinja2 `FileSystemLoader` and `base_template_map` instead of `_TEMPLATE_MAP`.

**Step 2: Update init command to accept --template**

In `miniautogen/cli/commands/init.py`, add the template option and from-example option:

```python
@click.command("init")
@click.argument("name")
@click.option(
    "--model",
    default="gpt-4o-mini",
    help="Default LLM model.",
)
@click.option(
    "--provider",
    default="openai",
    help="Default LLM provider.",
)
@click.option(
    "--template",
    type=click.Choice(["quickstart", "minimal", "advanced"]),
    default=None,
    help="Project template to use.",
)
@click.option(
    "--from-example",
    "from_example",
    default=None,
    help="Initialize from an example project (e.g., tamagotchi-dev-team).",
)
@click.option(
    "--no-examples",
    is_flag=True,
    default=False,
    help="Skip example agent, skill, and tool.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Add missing files to existing non-empty directory.",
)
def init_command(
    name: str,
    model: str,
    provider: str,
    template: str | None,
    from_example: str | None,
    no_examples: bool,
    force: bool,
) -> None:
    """Create a new MiniAutoGen project."""
    if from_example:
        _init_from_example(name, from_example, force)
        return

    effective_template = template or "project"

    try:
        project_dir = scaffold_project(
            name,
            Path.cwd(),
            model=model,
            provider=provider,
            include_examples=not no_examples,
            force=force,
            template=effective_template,
        )
        echo_success(f"Workspace created: {project_dir}\n")

        if effective_template == "quickstart":
            echo_info("Next steps:")
            echo_info(f"  cd {name}")
            echo_info(f"  # Edit .env with your API key")
            echo_info(f"  miniautogen send 'Hello!' --agent assistant")
            echo_info(f"  miniautogen chat assistant")
        else:
            echo_info("Next steps:")
            echo_info(f"  cd {name}")
            echo_info(f"  miniautogen engine create default --provider openai --model gpt-4o")
            echo_info(f"  miniautogen agent create researcher --engine default --role \"Researcher\"")
            echo_info(f"  miniautogen check")
            echo_info(f"  miniautogen run main")
    except FileExistsError:
        echo_error(
            f"Directory '{name}' already exists and is not empty. "
            f"Use --force to add missing files without overwriting."
        )
        raise SystemExit(1)
    except ValueError as exc:
        echo_error(str(exc))
        raise SystemExit(1)


def _init_from_example(name: str, example: str, force: bool) -> None:
    """Initialize a project by copying an example."""
    import shutil

    examples_dir = Path(__file__).parent.parent.parent.parent / "examples"
    example_dir = examples_dir / example

    if not example_dir.is_dir():
        available = [d.name for d in examples_dir.iterdir() if d.is_dir()]
        echo_error(
            f"Example '{example}' not found. "
            f"Available: {', '.join(available) or '(none)'}"
        )
        raise SystemExit(1)

    target = Path.cwd() / name
    if target.exists() and not force:
        echo_error(f"Directory '{name}' already exists. Use --force to overwrite.")
        raise SystemExit(1)

    if target.exists():
        shutil.rmtree(target)

    shutil.copytree(example_dir, target)
    echo_success(f"Workspace created from example '{example}': {target}")
    echo_info("Next steps:")
    echo_info(f"  cd {name}")
    echo_info(f"  # Edit .env with your API key")
    echo_info(f"  miniautogen check")
```

**Step 3: Verify the command works**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen init --help`

**Expected output:** Should show `--template` with choices `quickstart`, `minimal`, `advanced`.

**Step 4: Commit**

```bash
git add miniautogen/cli/commands/init.py miniautogen/cli/services/init_project.py
git commit -m "feat(cli): add --template and --from-example to init command"
```

**If Task Fails:**
1. Template directory not found: Verify the paths resolve correctly by checking `Path(__file__).parent.parent / "templates"`.
2. Existing tests may break if `scaffold_project` signature changed. Run `pytest tests/cli/services/test_init_project.py -v` to check.
3. Rollback: `git checkout -- miniautogen/cli/commands/init.py miniautogen/cli/services/init_project.py`

---

### Task 30: Write tests for init templates

**Files:**
- Create: `tests/cli/services/test_init_templates.py`

**Prerequisites:**
- Task 29 complete

**Step 1: Write the tests**

Create file `tests/cli/services/test_init_templates.py`:
```python
"""Tests for init template selection."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from miniautogen.cli.services.init_project import scaffold_project, AVAILABLE_TEMPLATES


def test_quickstart_template(tmp_path: Path) -> None:
    """Quickstart template should create workspace + assistant agent."""
    project = scaffold_project(
        "myapp", tmp_path,
        template="quickstart",
    )
    assert (project / "miniautogen.yaml").is_file()
    assert (project / "agents" / "assistant.yaml").is_file()
    assert (project / ".env").is_file()
    assert (project / "README.md").is_file()

    config = yaml.safe_load((project / "miniautogen.yaml").read_text())
    assert config["project"]["name"] == "myapp"
    assert "assistant" in config["flows"]["main"]["participants"]


def test_minimal_template(tmp_path: Path) -> None:
    """Minimal template should create only config + env."""
    project = scaffold_project(
        "myapp", tmp_path,
        template="minimal",
    )
    assert (project / "miniautogen.yaml").is_file()
    assert (project / ".env").is_file()
    # No agents directory
    assert not (project / "agents").is_dir()
    assert not (project / "README.md").is_file()


def test_advanced_template(tmp_path: Path) -> None:
    """Advanced template should create 3 agents + 2 flows."""
    project = scaffold_project(
        "myapp", tmp_path,
        template="advanced",
    )
    assert (project / "miniautogen.yaml").is_file()
    assert (project / "agents" / "architect.yaml").is_file()
    assert (project / "agents" / "developer.yaml").is_file()
    assert (project / "agents" / "reviewer.yaml").is_file()

    config = yaml.safe_load((project / "miniautogen.yaml").read_text())
    assert "build" in config["flows"]
    assert "review" in config["flows"]
    assert config["flows"]["review"]["mode"] == "deliberation"


def test_default_template_unchanged(tmp_path: Path) -> None:
    """Default template (project) should still work as before."""
    project = scaffold_project(
        "myapp", tmp_path,
        template="project",
    )
    assert (project / "miniautogen.yaml").is_file()


def test_available_templates_list() -> None:
    """AVAILABLE_TEMPLATES should contain the 3 named templates."""
    assert "quickstart" in AVAILABLE_TEMPLATES
    assert "minimal" in AVAILABLE_TEMPLATES
    assert "advanced" in AVAILABLE_TEMPLATES
```

**Step 2: Run the tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_init_templates.py -v`

**Expected output:** All 5 tests pass.

**Step 3: Commit**

```bash
git add tests/cli/services/test_init_templates.py
git commit -m "test(cli): add tests for init template selection"
```

**If Task Fails:**
1. Template file not found: Verify template directories exist with correct file names.
2. `AVAILABLE_TEMPLATES` import error: Check if the variable was exported from `init_project.py`.
3. Rollback: `git checkout -- tests/cli/services/test_init_templates.py`

---

### Task 31: Write CLI tests for --template and --from-example flags

**Files:**
- Modify: `tests/cli/commands/test_init.py` (append tests)

**Prerequisites:**
- Task 29 complete

**Step 1: Append template tests**

Read `tests/cli/commands/test_init.py` first, then append these tests:

```python
def test_init_quickstart_template(tmp_path, monkeypatch) -> None:
    """init --template quickstart should create quickstart project."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myapp", "--template", "quickstart"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "myapp" / "agents" / "assistant.yaml").is_file()


def test_init_minimal_template(tmp_path, monkeypatch) -> None:
    """init --template minimal should create minimal project."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myapp", "--template", "minimal"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "myapp" / "miniautogen.yaml").is_file()


def test_init_advanced_template(tmp_path, monkeypatch) -> None:
    """init --template advanced should create advanced project."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myapp", "--template", "advanced"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "myapp" / "agents" / "architect.yaml").is_file()


def test_init_from_example_hello_world(tmp_path, monkeypatch) -> None:
    """init --from-example hello-world should copy example."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myapp", "--from-example", "hello-world"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "myapp" / "miniautogen.yaml").is_file()


def test_init_from_example_not_found(tmp_path, monkeypatch) -> None:
    """init --from-example nonexistent should error."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "myapp", "--from-example", "nonexistent"])
    assert result.exit_code != 0
```

Note: You need to add the required imports at the top of the file if not already present:
```python
from click.testing import CliRunner
from miniautogen.cli.main import cli
```

**Step 2: Run the tests**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/commands/test_init.py -v`

**Expected output:** All tests pass (old + new).

**Step 3: Commit**

```bash
git add tests/cli/commands/test_init.py
git commit -m "test(cli): add tests for --template and --from-example init flags"
```

**If Task Fails:**
1. hello-world example may not exist yet (Task 1). If so, skip that test or ensure Task 1 is complete first.
2. Rollback: `git checkout -- tests/cli/commands/test_init.py`

---

### Task 32: Run Code Review (G4 + G5)

1. **Dispatch all 3 reviewers in parallel:**
   - REQUIRED SUB-SKILL: Use requesting-code-review
   - All reviewers run simultaneously (code-reviewer, business-logic-reviewer, security-reviewer)
   - Wait for all to complete

2. **Handle findings by severity (MANDATORY):**

**Critical/High/Medium Issues:**
- Fix immediately

**Low Issues:**
- Add `TODO(review):` comments

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain

---

### Task 33: Run full test suite to verify zero regression

**Files:**
- None (verification only)

**Prerequisites:**
- All previous tasks complete

**Step 1: Run the complete test suite**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest --tb=short -q 2>&1 | tail -20`

**Expected output:** 3,045+ tests passing with 0 failures. Some tests may be skipped (xfail) but no new failures.

**Step 2: Run the new tests specifically**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m pytest tests/cli/services/test_send_service.py tests/cli/services/test_chat_service.py tests/cli/services/test_init_templates.py tests/cli/commands/test_send.py tests/cli/commands/test_chat.py tests/server/test_agents.py tests/server/test_flows.py -v`

**Expected output:** All new tests pass.

**Step 3: Verify CLI commands exist**

Run: `cd /Users/brunocapelao/Projects/miniAutoGen && python -m miniautogen --help`

**Expected output:** Should show `send`, `chat`, and the updated `init` command with `--template` in the help.

**If Task Fails:**
1. If existing tests break, check if changes to `init_project.py` signature broke backward compatibility. The `template` parameter defaults to `"project"` which should maintain backward compat.
2. If server tests break, check if the conftest.py mock provider changes are additive.
3. Document any failures and their cause before proceeding.

---

## Summary of Files Created/Modified

### New Files (19)
- `examples/hello-world/miniautogen.yaml`
- `examples/hello-world/agents/assistant.yaml`
- `examples/hello-world/.env.example`
- `examples/hello-world/README.md`
- `miniautogen/cli/commands/send.py`
- `miniautogen/cli/commands/chat.py`
- `miniautogen/cli/services/send_service.py`
- `miniautogen/cli/services/chat_service.py`
- `miniautogen/cli/templates/quickstart/*` (5 files)
- `miniautogen/cli/templates/minimal/*` (3 files)
- `miniautogen/cli/templates/advanced/*` (5 files)
- `console/src/components/AgentForm.tsx`
- `console/src/components/FlowForm.tsx`
- `console/src/components/DeleteConfirmModal.tsx`
- `console/src/app/agents/new/page.tsx`
- `console/src/app/agents/edit/page.tsx`
- `console/src/app/flows/new/page.tsx`
- `console/src/app/flows/edit/page.tsx`
- `tests/cli/services/test_send_service.py`
- `tests/cli/services/test_chat_service.py`
- `tests/cli/services/test_init_templates.py`
- `tests/cli/commands/test_send.py`
- `tests/cli/commands/test_chat.py`

### Modified Files (13)
- `miniautogen/cli/main.py` (register send + chat commands)
- `miniautogen/cli/commands/init.py` (add --template, --from-example)
- `miniautogen/cli/services/init_project.py` (template support)
- `miniautogen/server/provider_protocol.py` (CRUD methods)
- `miniautogen/server/standalone_provider.py` (CRUD delegation)
- `miniautogen/server/models.py` (request schemas)
- `miniautogen/server/routes/agents.py` (POST/PUT/DELETE)
- `miniautogen/server/routes/flows.py` (POST/PUT/DELETE)
- `miniautogen/tui/data_provider.py` (CRUD implementations)
- `console/src/lib/api-client.ts` (CRUD methods)
- `console/src/types/api.ts` (CRUD types)
- `console/src/hooks/useApi.ts` (mutation hooks)
- `console/src/app/agents/page.tsx` (create button + delete)
- `console/src/app/flows/page.tsx` (create button + delete)
- `tests/server/conftest.py` (CRUD mocks)
- `tests/server/test_agents.py` (CRUD tests)
- `tests/server/test_flows.py` (CRUD tests)
- `tests/cli/commands/test_init.py` (template tests)
