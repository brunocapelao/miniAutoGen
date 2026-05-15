# API Facade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `miniautogen.api` public facade and refactor 4 CLI files that import internal modules directly (D3 violation), making `test_import_boundary.py` pass.

**Architecture:** Single `miniautogen/api/__init__.py` module re-exports the classes/functions needed by CLI (`create_app`, `StandaloneProvider`, `AgentRuntime`, stores, etc.) plus a `create_runtime()` helper that abstracts the AgentRuntime creation pattern duplicated across chat/send services.

**Tech Stack:** Python 3.11, pytest (boundary test), ruff, mypy

---

### Task 1: Create `miniautogen/api/__init__.py`

**Files:**
- Create: `miniautogen/api/__init__.py`

- [ ] **Step 1: Create the file**

```python
"""Public API facade for CLI and external consumers.

All SDK interaction from CLI must go through this module.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from miniautogen.backends.engine_resolver import EngineResolver
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import NullEventSink
from miniautogen.core.runtime.agent_runtime import AgentRuntime
from miniautogen.server.app import create_app
from miniautogen.server.standalone_provider import StandaloneProvider
from miniautogen.stores.in_memory_event_store import InMemoryEventStore
from miniautogen.stores.in_memory_run_store import InMemoryRunStore
from miniautogen.stores.sqlalchemy_event_store import SQLAlchemyEventStore
from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore
from miniautogen.tui.data_provider import DashDataProvider


async def create_runtime(
    project_root: Path,
    agent_name: str,
    run_id_prefix: str = "run",
    system_prompt: str = "",
) -> tuple[AgentRuntime, str]:
    """Load agent config, create driver, build and initialize AgentRuntime.

    Args:
        project_root: Path to the workspace root.
        agent_name: Name of the agent to use.
        run_id_prefix: Prefix for the auto-generated run ID.
        system_prompt: Optional override. Falls back to agent spec goal.

    Returns:
        Tuple of (initialized AgentRuntime, run_id).

    Raises:
        ValueError: If agent not found.
    """
    from miniautogen.cli.config import load_config, CONFIG_FILENAME
    from miniautogen.cli.services.agent_ops import load_agent_specs

    config = load_config(project_root / CONFIG_FILENAME)
    agent_specs = load_agent_specs(project_root)
    spec = agent_specs[agent_name]
    run_id = f"{run_id_prefix}-{uuid.uuid4().hex[:8]}"

    engine_resolver = EngineResolver()
    engine_name = getattr(spec, "engine_profile", None) or config.defaults.engine
    driver = engine_resolver.create_fresh_driver(engine_name, config)

    run_context = RunContext(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )

    runtime = AgentRuntime(
        agent_id=agent_name,
        driver=driver,
        run_context=run_context,
        event_sink=NullEventSink(),
        system_prompt=system_prompt or getattr(spec, "goal", None) or "",
    )
    await runtime.initialize()
    return runtime, run_id
```

- [ ] **Step 2: Verify it can be imported**

```bash
uv run python -c "from miniautogen.api import create_runtime, create_app, StandaloneProvider; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Run ruff on the new module**

```bash
uv run ruff check miniautogen/api/
```
Expected: no errors.

- [ ] **Step 4: Run mypy on the new module**

```bash
uv run mypy miniautogen/api/
```
Expected: Success.

- [ ] **Step 5: Commit**

```bash
git add miniautogen/api/__init__.py
git commit -m "feat(api): create miniautogen.api public facade"
```

---

### Task 2: Refactor `cli/services/chat_service.py`

**Files:**
- Modify: `miniautogen/cli/services/chat_service.py:15-16,71-72,54-121`

- [ ] **Step 1: Replace imports**

Remove:
```python
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import NullEventSink
```

Add:
```python
from miniautogen.api import create_runtime
```

- [ ] **Step 2: Replace ChatSession.create() body**

Remove the lazy imports inside `create()`:
```python
        from miniautogen.backends.engine_resolver import EngineResolver
        from miniautogen.core.runtime.agent_runtime import AgentRuntime
```

Replace the body of `create()` from line 76 (`config = load_config(...)`) to line 115 (`await runtime.initialize()`) with:

```python
        from miniautogen.cli.services.agent_ops import load_agent_specs

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
        runtime, run_id = await create_runtime(
            project_root, agent_name, "chat",
            system_prompt=getattr(spec, "goal", None) or "",
        )
```

- [ ] **Step 3: Run ruff**

```bash
uv run ruff check miniautogen/cli/services/chat_service.py
```
Expected: no errors.

- [ ] **Step 4: Run mypy**

```bash
uv run mypy miniautogen/cli/services/chat_service.py
```
Expected: Success (note: pre-existing errors unrelated to these changes may appear).

- [ ] **Step 5: Commit**

```bash
git add miniautogen/cli/services/chat_service.py
git commit -m "refactor(cli): use miniautogen.api in chat_service"
```

---

### Task 3: Refactor `cli/services/send_service.py`

**Files:**
- Modify: `miniautogen/cli/services/send_service.py:15-17,42-43`

- [ ] **Step 1: Replace imports**

Remove:
```python
from miniautogen.core.contracts.run_context import RunContext
from miniautogen.core.events.event_sink import NullEventSink
```

Add:
```python
from miniautogen.api import create_runtime
```

- [ ] **Step 2: Replace send_message() lazy imports and body**

Remove the lazy imports:
```python
    from miniautogen.backends.engine_resolver import EngineResolver
    from miniautogen.core.runtime.agent_runtime import AgentRuntime
```

Replace the body from line 45 (`config = load_config(...)`) to the end with:

```python
    from miniautogen.cli.services.agent_ops import load_agent_specs

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

    runtime, run_id = await create_runtime(
        project_root, agent_name, "send",
        system_prompt="",
    )
    try:
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

- [ ] **Step 3: Run ruff**

```bash
uv run ruff check miniautogen/cli/services/send_service.py
```
Expected: no errors.

- [ ] **Step 4: Run mypy**

```bash
uv run mypy miniautogen/cli/services/send_service.py
```
Expected: Success (pre-existing errors unrelated).

- [ ] **Step 5: Commit**

```bash
git add miniautogen/cli/services/send_service.py
git commit -m "refactor(cli): use miniautogen.api in send_service"
```

---

### Task 4: Refactor `cli/commands/console.py`

**Files:**
- Modify: `miniautogen/cli/commands/console.py:166-167,211-212,290-305`

- [ ] **Step 1: Replace lazy imports (3 locations)**

Location 1 (console function, around lines 166-167):
```python
    from miniautogen.server.app import create_app
    from miniautogen.server.standalone_provider import StandaloneProvider
```
Replace with:
```python
    from miniautogen.api import create_app, StandaloneProvider
```

Location 2 (dev function, around lines 211-212):
```python
    from miniautogen.server.app import create_app
    from miniautogen.server.standalone_provider import StandaloneProvider
```
Replace with:
```python
    from miniautogen.api import create_app, StandaloneProvider
```

Location 3 (run_console function, around lines 290-305):
```python
        from miniautogen.stores.sqlalchemy_event_store import SQLAlchemyEventStore
        from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore
```
and:
```python
        from miniautogen.stores.in_memory_event_store import InMemoryEventStore
        from miniautogen.stores.in_memory_run_store import InMemoryRunStore
```
Replace both with a single import at the top of the block:
```python
        from miniautogen.api import (
            SQLAlchemyEventStore,
            SQLAlchemyRunStore,
            InMemoryEventStore,
            InMemoryRunStore,
        )
```

- [ ] **Step 2: Run ruff**

```bash
uv run ruff check miniautogen/cli/commands/console.py
```
Expected: no errors.

- [ ] **Step 3: Run mypy**

```bash
uv run mypy miniautogen/cli/commands/console.py
```
Expected: Success.

- [ ] **Step 4: Commit**

```bash
git add miniautogen/cli/commands/console.py
git commit -m "refactor(cli): use miniautogen.api in console command"
```

---

### Task 5: Refactor `cli/commands/run.py`

**Files:**
- Modify: `miniautogen/cli/commands/run.py:166`

- [ ] **Step 1: Replace lazy import**

Change line 166:
```python
        from miniautogen.server.app import create_app
```
to:
```python
        from miniautogen.api import create_app
```

- [ ] **Step 2: Run ruff**

```bash
uv run ruff check miniautogen/cli/commands/run.py
```
Expected: no errors.

- [ ] **Step 3: Run mypy**

```bash
uv run mypy miniautogen/cli/commands/run.py
```
Expected: Success.

- [ ] **Step 4: Commit**

```bash
git add miniautogen/cli/commands/run.py
git commit -m "refactor(cli): use miniautogen.api in run command"
```

---

### Task 6: Full validation

- [ ] **Step 1: Verify the boundary test passes**

```bash
uv run pytest tests/cli/test_import_boundary.py -v
```
Expected: PASS (D3 violations resolved).

- [ ] **Step 2: Run ruff on all changed files**

```bash
uv run ruff check miniautogen/api/ miniautogen/cli/
```
Expected: no errors.

- [ ] **Step 3: Run mypy**

```bash
uv run mypy miniautogen/api/ miniautogen/cli/
```
Expected: Success (pre-existing errors acceptable).

- [ ] **Step 4: Run CLI tests**

```bash
uv run pytest tests/cli/ --ignore=tests/tui -k "not test_spinner_used_on_tty" -q
```
Expected: all passing (except pre-existing spinner test failure).

- [ ] **Step 5: Confirm the architecture test from Sprint 1.1 still passes**

```bash
uv run pytest tests/architecture/ -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: final validation pass for API facade"
```
