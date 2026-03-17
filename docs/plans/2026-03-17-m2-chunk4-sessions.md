# Milestone 2 — Chunk 4: `sessions` Command Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Implement `miniautogen sessions list` and `miniautogen sessions clean` CLI commands that query and manage run data through the public SDK surface.

**Architecture:** The `sessions` command follows the same adapter/service split as other CLI commands (D5). `commands/sessions.py` is a thin Click adapter that parses arguments and renders output. `services/session_ops.py` contains all application logic (store creation, querying, filtering, deletion). Services import only from `miniautogen.api` (D3 import boundary). A `create_run_store` factory abstracts over `InMemoryRunStore` vs `SQLAlchemyRunStore` backends based on the project config's `database.url` field. The `clean` operation enforces a safety invariant: it NEVER deletes runs with `status="started"` (active runs).

**Tech Stack:** Python 3.10+, Click 8+, SQLAlchemy 2+ (async), aiosqlite, Pydantic v2, pytest 7+, pytest-asyncio 0.23+, ruff (line-length=100)

**Global Prerequisites:**
- Environment: macOS, Python 3.10-3.11
- Tools: `python --version`, `poetry --version`
- Access: No external services needed
- State: Branch from `main`, clean working tree
- **Chunks 1-3 MUST be implemented first** (CLI foundation, config, errors, output, init/check/run commands)

**Verification before starting:**
```bash
cd /Users/brunocapelao/Projects/miniAutoGen
python --version        # Expected: Python 3.10.x or 3.11.x
poetry --version        # Expected: Poetry 1.x+
poetry run python -c "from miniautogen.cli.main import cli; print('OK')"       # Expected: OK
poetry run python -c "from miniautogen.cli.config import ProjectConfig, load_config; print('OK')"  # Expected: OK
poetry run python -c "from miniautogen.cli.errors import CLIError; print('OK')"  # Expected: OK
poetry run pytest --co -q  # Expected: collects tests, no import errors
git status              # Expected: clean working tree
```

**What Already Exists (DO NOT recreate):**
- `miniautogen/stores/run_store.py` -- `RunStore` ABC with `save_run`, `get_run`, `list_runs`, `delete_run`
- `miniautogen/stores/in_memory_run_store.py` -- `InMemoryRunStore` (dict-backed)
- `miniautogen/stores/sqlalchemy_run_store.py` -- `SQLAlchemyRunStore` with `DBRun` ORM model, `init_db()`, full CRUD
- `miniautogen/stores/__init__.py` -- re-exports all store classes
- `miniautogen/cli/main.py` -- Click group + `run_async` helper (from Chunks 1-2)
- `miniautogen/cli/config.py` -- `ProjectConfig` (fields: `project: dict`, `provider: dict`, `pipelines: dict`, `database: dict | None`), `load_config()`, `find_project_root()`
- `miniautogen/cli/errors.py` -- `CLIError`, `ConfigurationError`
- `miniautogen/cli/output.py` -- output formatting functions
- `miniautogen/cli/commands/run.py` -- `run_command` registered via `cli.add_command()`

**Important Design Facts:**
1. `ProjectConfig.database` is `dict[str, Any] | None`. When present, it has a `"url"` key with a SQLAlchemy async DSN like `"sqlite+aiosqlite:///miniautogen.db"`. When `None`, the in-memory store is used.
2. `RunStore.list_runs(status, limit)` returns `list[dict[str, Any]]`. Each dict is the payload saved via `save_run`. The payload typically contains `"run_id"`, `"status"`, `"started_at"`, `"finished_at"` keys, but this is convention (the store treats payloads as opaque dicts).
3. `SQLAlchemyRunStore` has an `updated_at` column on `DBRun`, but `list_runs` does NOT filter by date. Date filtering must happen in our service layer by inspecting payload fields.
4. `RunStore` and `SQLAlchemyRunStore` are NOT currently in `miniautogen.api`. Task 1 adds them.

**Important Design Constraint (D3):** `services/session_ops.py` may ONLY import from `miniautogen.api`, stdlib, and external deps. It must NOT import from `miniautogen.stores`, `miniautogen.core`, or any other internal module.

---

## Task 1: Extend `miniautogen.api` to Export RunStore, InMemoryRunStore, SQLAlchemyRunStore

**Why:** The sessions service needs `RunStore`, `InMemoryRunStore`, and `SQLAlchemyRunStore`, but `miniautogen/api.py` does not export them yet. D3 compliance requires all store access to go through the public API facade.

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/api.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/test_api_exports.py`

**Prerequisites:**
- `miniautogen/api.py` must exist (it does)
- `miniautogen/stores/run_store.py` must exist (it does)
- `miniautogen/stores/in_memory_run_store.py` must exist (it does)
- `miniautogen/stores/sqlalchemy_run_store.py` must exist (it does)

**Step 1: Write the failing test**

Append these tests to the **end** of `/Users/brunocapelao/Projects/miniAutoGen/tests/test_api_exports.py`:

```python
def test_api_exports_run_store():
    from miniautogen.api import RunStore
    assert RunStore is not None


def test_api_exports_in_memory_run_store():
    from miniautogen.api import InMemoryRunStore
    assert InMemoryRunStore is not None


def test_api_exports_sqlalchemy_run_store():
    from miniautogen.api import SQLAlchemyRunStore
    assert SQLAlchemyRunStore is not None
```

**Note:** `InMemoryRunStore` may already be exported if Chunk 3 Task 1 was executed. If the test already passes for `InMemoryRunStore`, that is fine -- the test is still valid. The new exports are `RunStore` and `SQLAlchemyRunStore`.

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_api_exports.py::test_api_exports_run_store tests/test_api_exports.py::test_api_exports_sqlalchemy_run_store -v`

**Expected output:**
```
FAILED tests/test_api_exports.py::test_api_exports_run_store - ImportError: cannot import name 'RunStore'
FAILED tests/test_api_exports.py::test_api_exports_sqlalchemy_run_store - ImportError: cannot import name 'SQLAlchemyRunStore'
```

**Step 3: Add imports and exports to `miniautogen/api.py`**

Add these import lines. Place them after the existing `from miniautogen.core.runtime.recovery import SessionRecovery` line (or after the `InMemoryRunStore` import if Chunk 3 already added it):

```python
from miniautogen.stores.run_store import RunStore
from miniautogen.stores.in_memory_run_store import InMemoryRunStore
from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore
```

**Note:** If `InMemoryRunStore` was already imported by Chunk 3, do NOT duplicate it. Only add the missing imports.

Then add these strings to the `__all__` list. Add a `# Stores` section (or extend the existing one if Chunk 3 created it):

```python
    # Stores
    "RunStore",
    "InMemoryRunStore",
    "SQLAlchemyRunStore",
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/test_api_exports.py::test_api_exports_run_store tests/test_api_exports.py::test_api_exports_in_memory_run_store tests/test_api_exports.py::test_api_exports_sqlalchemy_run_store -v`

**Expected output:**
```
PASSED tests/test_api_exports.py::test_api_exports_run_store
PASSED tests/test_api_exports.py::test_api_exports_in_memory_run_store
PASSED tests/test_api_exports.py::test_api_exports_sqlalchemy_run_store
```

**Step 5: Run full API export tests**

Run: `poetry run pytest tests/test_api_exports.py -v`

**Expected output:** All tests PASSED.

**Step 6: Run linter**

Run: `poetry run ruff check miniautogen/api.py tests/test_api_exports.py`

**Expected output:** No errors.

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/api.py tests/test_api_exports.py
git commit -m "feat(api): export RunStore, InMemoryRunStore, SQLAlchemyRunStore from public API"
```

**If Task Fails:**

1. **Import error on stores:**
   - Check: `poetry run python -c "from miniautogen.stores.run_store import RunStore; print('OK')"`
   - Check: `poetry run python -c "from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore; print('OK')"`
   - Both should print `OK`. If not, the source files have import issues.

2. **Duplicate InMemoryRunStore import:**
   - If Chunk 3 already added `InMemoryRunStore`, you will get a ruff error for duplicate import.
   - Fix: Remove the duplicate import line, keep only one.

3. **Can't recover:**
   - Rollback: `git checkout -- miniautogen/api.py tests/test_api_exports.py`

---

## Task 2: Create `create_run_store` Factory in `services/session_ops.py`

**Why:** The factory function creates the appropriate `RunStore` backend based on whether the project config has a database URL configured. This is the foundation for all session operations.

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/session_ops.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_session_ops.py`

**Prerequisites:**
- Task 1 completed (API exports RunStore, InMemoryRunStore, SQLAlchemyRunStore)
- `miniautogen/cli/services/__init__.py` must exist (from Chunks 1-2)
- `tests/cli/services/__init__.py` must exist (from Chunk 2 or 3)

**Step 1: Verify directory structure**

Run:
```bash
ls /Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/__init__.py
ls /Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/__init__.py
```

**Expected output:** Both files listed. If missing, create them:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/cli/services
touch /Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/__init__.py
```

**Step 2: Write the failing tests**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_session_ops.py`:

```python
"""Tests for session operations service."""
from __future__ import annotations

import pytest

from miniautogen.cli.services.session_ops import create_run_store


class TestCreateRunStore:
    """Tests for the create_run_store factory."""

    def test_returns_in_memory_store_when_no_database(self) -> None:
        from miniautogen.api import InMemoryRunStore

        config_database = None
        store = create_run_store(config_database)
        assert isinstance(store, InMemoryRunStore)

    def test_returns_sqlalchemy_store_when_database_url_present(self) -> None:
        from miniautogen.api import SQLAlchemyRunStore

        config_database = {"url": "sqlite+aiosqlite:///test.db"}
        store = create_run_store(config_database)
        assert isinstance(store, SQLAlchemyRunStore)

    def test_returns_in_memory_store_when_database_dict_has_no_url(
        self,
    ) -> None:
        from miniautogen.api import InMemoryRunStore

        config_database = {"other_key": "value"}
        store = create_run_store(config_database)
        assert isinstance(store, InMemoryRunStore)
```

**Step 3: Run test to verify it fails**

Run: `poetry run pytest tests/cli/services/test_session_ops.py::TestCreateRunStore -v`

**Expected output:**
```
ERROR tests/cli/services/test_session_ops.py - ModuleNotFoundError: No module named 'miniautogen.cli.services.session_ops'
```

**Step 4: Write minimal implementation**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/session_ops.py`:

```python
"""Session/run management service for the CLI.

Provides operations to list, inspect, and clean session/run data
via the public SDK surface (miniautogen.api).
"""
from __future__ import annotations

from typing import Any

from miniautogen.api import InMemoryRunStore, RunStore, SQLAlchemyRunStore


def create_run_store(
    config_database: dict[str, Any] | None,
) -> RunStore:
    """Create a RunStore based on project database configuration.

    Parameters
    ----------
    config_database:
        The ``database`` section from ``ProjectConfig``.
        If ``None`` or missing ``url`` key, returns ``InMemoryRunStore``.
        Otherwise returns ``SQLAlchemyRunStore`` connected to the URL.

    Returns
    -------
    RunStore
        The appropriate store implementation.
    """
    if config_database and "url" in config_database:
        return SQLAlchemyRunStore(config_database["url"])
    return InMemoryRunStore()
```

**Step 5: Run test to verify it passes**

Run: `poetry run pytest tests/cli/services/test_session_ops.py::TestCreateRunStore -v`

**Expected output:**
```
PASSED tests/cli/services/test_session_ops.py::TestCreateRunStore::test_returns_in_memory_store_when_no_database
PASSED tests/cli/services/test_session_ops.py::TestCreateRunStore::test_returns_sqlalchemy_store_when_database_url_present
PASSED tests/cli/services/test_session_ops.py::TestCreateRunStore::test_returns_in_memory_store_when_database_dict_has_no_url
```

**Step 6: Run linter**

Run: `poetry run ruff check miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py`

**Expected output:** No errors.

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py
git commit -m "feat(cli): add create_run_store factory for session operations"
```

**If Task Fails:**

1. **Import error on miniautogen.api stores:**
   - Check: `poetry run python -c "from miniautogen.api import RunStore, InMemoryRunStore, SQLAlchemyRunStore; print('OK')"`
   - If fails, Task 1 was not completed. Go back.

2. **Can't recover:**
   - Rollback: `git checkout -- miniautogen/cli/services/session_ops.py`

---

## Task 3: Add `list_sessions` Async Service Function

**Why:** The core query logic for listing sessions. It creates a store, queries it with optional status filter and limit, and returns a list of session dicts. This function handles the `SQLAlchemyRunStore.init_db()` call when using a database backend.

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/session_ops.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_session_ops.py`

**Prerequisites:**
- Task 2 completed

**Step 1: Write the failing test**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_session_ops.py`:

```python
class TestListSessions:
    """Tests for the list_sessions async function."""

    @pytest.mark.anyio
    async def test_list_sessions_empty_store(self) -> None:
        from miniautogen.cli.services.session_ops import list_sessions

        result = await list_sessions(
            config_database=None,
            status=None,
            limit=100,
        )
        assert result == []

    @pytest.mark.anyio
    async def test_list_sessions_returns_saved_runs(self) -> None:
        from miniautogen.api import InMemoryRunStore
        from miniautogen.cli.services.session_ops import (
            list_sessions_from_store,
        )

        store = InMemoryRunStore()
        await store.save_run("run-1", {
            "run_id": "run-1",
            "status": "finished",
            "started_at": "2026-03-17T10:00:00Z",
        })
        await store.save_run("run-2", {
            "run_id": "run-2",
            "status": "failed",
            "started_at": "2026-03-17T11:00:00Z",
        })

        result = await list_sessions_from_store(
            store=store, status=None, limit=100
        )
        assert len(result) == 2

    @pytest.mark.anyio
    async def test_list_sessions_filter_by_status(self) -> None:
        from miniautogen.api import InMemoryRunStore
        from miniautogen.cli.services.session_ops import (
            list_sessions_from_store,
        )

        store = InMemoryRunStore()
        await store.save_run("run-1", {
            "run_id": "run-1",
            "status": "finished",
        })
        await store.save_run("run-2", {
            "run_id": "run-2",
            "status": "failed",
        })
        await store.save_run("run-3", {
            "run_id": "run-3",
            "status": "finished",
        })

        result = await list_sessions_from_store(
            store=store, status="finished", limit=100
        )
        assert len(result) == 2
        assert all(r["status"] == "finished" for r in result)

    @pytest.mark.anyio
    async def test_list_sessions_respects_limit(self) -> None:
        from miniautogen.api import InMemoryRunStore
        from miniautogen.cli.services.session_ops import (
            list_sessions_from_store,
        )

        store = InMemoryRunStore()
        for i in range(10):
            await store.save_run(f"run-{i}", {
                "run_id": f"run-{i}",
                "status": "finished",
            })

        result = await list_sessions_from_store(
            store=store, status=None, limit=3
        )
        assert len(result) == 3
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/cli/services/test_session_ops.py::TestListSessions -v`

**Expected output:**
```
FAILED ... - ImportError: cannot import name 'list_sessions' from 'miniautogen.cli.services.session_ops'
```

**Step 3: Implement `list_sessions` and `list_sessions_from_store`**

Add to the **end** of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/session_ops.py`:

```python


async def list_sessions_from_store(
    store: RunStore,
    status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Query sessions from an already-instantiated store.

    Parameters
    ----------
    store:
        An initialized ``RunStore`` instance.
    status:
        If provided, filter runs by this status value.
    limit:
        Maximum number of runs to return.

    Returns
    -------
    list[dict]
        List of run payload dicts.
    """
    return await store.list_runs(status=status, limit=limit)


async def list_sessions(
    config_database: dict[str, Any] | None,
    status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """List sessions/runs from the project's configured store.

    Creates the appropriate store backend based on config, initializes
    it if needed (SQLAlchemy), and queries for runs.

    Parameters
    ----------
    config_database:
        The ``database`` section from ``ProjectConfig``.
    status:
        If provided, filter by run status.
    limit:
        Maximum number of runs to return.

    Returns
    -------
    list[dict]
        List of run payload dicts.
    """
    store = create_run_store(config_database)
    if hasattr(store, "init_db"):
        await store.init_db()
    return await list_sessions_from_store(
        store=store, status=status, limit=limit
    )
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/cli/services/test_session_ops.py::TestListSessions -v`

**Expected output:**
```
PASSED tests/cli/services/test_session_ops.py::TestListSessions::test_list_sessions_empty_store
PASSED tests/cli/services/test_session_ops.py::TestListSessions::test_list_sessions_returns_saved_runs
PASSED tests/cli/services/test_session_ops.py::TestListSessions::test_list_sessions_filter_by_status
PASSED tests/cli/services/test_session_ops.py::TestListSessions::test_list_sessions_respects_limit
```

**Step 5: Run linter**

Run: `poetry run ruff check miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py`

**Expected output:** No errors.

**Step 6: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py
git commit -m "feat(cli): add list_sessions service for querying run data"
```

**If Task Fails:**

1. **pytest-anyio not installed or `@pytest.mark.anyio` not recognized:**
   - Try: `@pytest.mark.asyncio` instead (if using pytest-asyncio).
   - Check: `poetry run python -c "import anyio; print('OK')"` -- if anyio is installed, the `anyio` marker should work with `pytest-anyio` or `anyio` pytest plugin.
   - Alternative: If the project uses `pytest-asyncio`, change all `@pytest.mark.anyio` to `@pytest.mark.asyncio`.

2. **Can't recover:**
   - Rollback: `git checkout -- miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py`

---

## Task 4: Add `clean_sessions` Async Service Function

**Why:** The deletion logic with safety invariant: NEVER delete active (status="started") runs. Only removes completed, failed, or cancelled runs, optionally filtered by age.

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/session_ops.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_session_ops.py`

**Prerequisites:**
- Task 3 completed

**Step 1: Write the failing tests**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/services/test_session_ops.py`:

```python
from datetime import datetime, timedelta, timezone


class TestCleanSessions:
    """Tests for the clean_sessions async function."""

    @pytest.mark.anyio
    async def test_clean_removes_finished_runs(self) -> None:
        from miniautogen.api import InMemoryRunStore
        from miniautogen.cli.services.session_ops import (
            clean_sessions_from_store,
        )

        store = InMemoryRunStore()
        await store.save_run("run-1", {
            "run_id": "run-1",
            "status": "finished",
            "started_at": "2026-03-01T10:00:00Z",
        })

        deleted = await clean_sessions_from_store(
            store=store,
            older_than_days=None,
        )
        assert deleted == 1

        remaining = await store.list_runs()
        assert len(remaining) == 0

    @pytest.mark.anyio
    async def test_clean_removes_failed_runs(self) -> None:
        from miniautogen.api import InMemoryRunStore
        from miniautogen.cli.services.session_ops import (
            clean_sessions_from_store,
        )

        store = InMemoryRunStore()
        await store.save_run("run-1", {
            "run_id": "run-1",
            "status": "failed",
            "started_at": "2026-03-01T10:00:00Z",
        })

        deleted = await clean_sessions_from_store(
            store=store,
            older_than_days=None,
        )
        assert deleted == 1

    @pytest.mark.anyio
    async def test_clean_removes_cancelled_runs(self) -> None:
        from miniautogen.api import InMemoryRunStore
        from miniautogen.cli.services.session_ops import (
            clean_sessions_from_store,
        )

        store = InMemoryRunStore()
        await store.save_run("run-1", {
            "run_id": "run-1",
            "status": "cancelled",
            "started_at": "2026-03-01T10:00:00Z",
        })

        deleted = await clean_sessions_from_store(
            store=store,
            older_than_days=None,
        )
        assert deleted == 1

    @pytest.mark.anyio
    async def test_clean_never_deletes_active_runs(self) -> None:
        from miniautogen.api import InMemoryRunStore
        from miniautogen.cli.services.session_ops import (
            clean_sessions_from_store,
        )

        store = InMemoryRunStore()
        await store.save_run("active-1", {
            "run_id": "active-1",
            "status": "started",
            "started_at": "2026-01-01T10:00:00Z",
        })
        await store.save_run("done-1", {
            "run_id": "done-1",
            "status": "finished",
            "started_at": "2026-01-01T10:00:00Z",
        })

        deleted = await clean_sessions_from_store(
            store=store,
            older_than_days=None,
        )
        assert deleted == 1

        remaining = await store.list_runs()
        assert len(remaining) == 1
        assert remaining[0]["run_id"] == "active-1"

    @pytest.mark.anyio
    async def test_clean_respects_older_than_days(self) -> None:
        from miniautogen.api import InMemoryRunStore
        from miniautogen.cli.services.session_ops import (
            clean_sessions_from_store,
        )

        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(days=10)).isoformat()
        recent_time = (now - timedelta(hours=1)).isoformat()

        store = InMemoryRunStore()
        await store.save_run("old-run", {
            "run_id": "old-run",
            "status": "finished",
            "started_at": old_time,
        })
        await store.save_run("recent-run", {
            "run_id": "recent-run",
            "status": "finished",
            "started_at": recent_time,
        })

        deleted = await clean_sessions_from_store(
            store=store,
            older_than_days=7,
        )
        assert deleted == 1

        remaining = await store.list_runs()
        assert len(remaining) == 1
        assert remaining[0]["run_id"] == "recent-run"

    @pytest.mark.anyio
    async def test_clean_returns_zero_when_nothing_to_delete(self) -> None:
        from miniautogen.api import InMemoryRunStore
        from miniautogen.cli.services.session_ops import (
            clean_sessions_from_store,
        )

        store = InMemoryRunStore()
        deleted = await clean_sessions_from_store(
            store=store,
            older_than_days=None,
        )
        assert deleted == 0
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/cli/services/test_session_ops.py::TestCleanSessions -v`

**Expected output:**
```
FAILED ... - ImportError: cannot import name 'clean_sessions_from_store' from 'miniautogen.cli.services.session_ops'
```

**Step 3: Implement `clean_sessions_from_store` and `clean_sessions`**

Add these imports at the top of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/services/session_ops.py`, after the existing `from typing import Any` line:

```python
from datetime import datetime, timedelta, timezone
```

Then add to the **end** of the file:

```python

# Statuses that are safe to delete. "started" is explicitly excluded.
_CLEANABLE_STATUSES = frozenset({"finished", "failed", "cancelled"})


def _is_older_than(
    run: dict[str, Any], older_than_days: int | None
) -> bool:
    """Check if a run's started_at is older than the threshold.

    If ``older_than_days`` is None, all runs match (no age filter).
    If the run has no ``started_at`` field or it cannot be parsed,
    the run is considered old (safe to delete).
    """
    if older_than_days is None:
        return True

    started_at_raw = run.get("started_at")
    if not started_at_raw:
        return True

    try:
        started_at = datetime.fromisoformat(str(started_at_raw))
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return True

    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    return started_at < cutoff


async def clean_sessions_from_store(
    store: RunStore,
    older_than_days: int | None,
) -> int:
    """Delete non-active sessions from an already-instantiated store.

    SAFETY: Runs with status="started" are NEVER deleted.

    Parameters
    ----------
    store:
        An initialized ``RunStore`` instance.
    older_than_days:
        If provided, only delete runs older than this many days.
        If ``None``, all non-active runs are eligible for deletion.

    Returns
    -------
    int
        Number of runs deleted.
    """
    all_runs = await store.list_runs(status=None, limit=10_000)
    deleted = 0

    for run in all_runs:
        status = run.get("status", "")
        if status not in _CLEANABLE_STATUSES:
            continue
        if not _is_older_than(run, older_than_days):
            continue

        run_id = run.get("run_id")
        if run_id and await store.delete_run(run_id):
            deleted += 1

    return deleted


async def clean_sessions(
    config_database: dict[str, Any] | None,
    older_than_days: int | None,
) -> int:
    """Clean sessions/runs from the project's configured store.

    Creates the appropriate store backend, initializes it, and
    deletes non-active runs matching the age criteria.

    Parameters
    ----------
    config_database:
        The ``database`` section from ``ProjectConfig``.
    older_than_days:
        If provided, only delete runs older than this many days.

    Returns
    -------
    int
        Number of runs deleted.
    """
    store = create_run_store(config_database)
    if hasattr(store, "init_db"):
        await store.init_db()
    return await clean_sessions_from_store(
        store=store, older_than_days=older_than_days
    )
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/cli/services/test_session_ops.py::TestCleanSessions -v`

**Expected output:**
```
PASSED tests/cli/services/test_session_ops.py::TestCleanSessions::test_clean_removes_finished_runs
PASSED tests/cli/services/test_session_ops.py::TestCleanSessions::test_clean_removes_failed_runs
PASSED tests/cli/services/test_session_ops.py::TestCleanSessions::test_clean_removes_cancelled_runs
PASSED tests/cli/services/test_session_ops.py::TestCleanSessions::test_clean_never_deletes_active_runs
PASSED tests/cli/services/test_session_ops.py::TestCleanSessions::test_clean_respects_older_than_days
PASSED tests/cli/services/test_session_ops.py::TestCleanSessions::test_clean_returns_zero_when_nothing_to_delete
```

**Step 5: Run all session_ops tests together**

Run: `poetry run pytest tests/cli/services/test_session_ops.py -v`

**Expected output:** All tests PASSED (3 from Task 2 + 4 from Task 3 + 6 from Task 4 = 13 tests).

**Step 6: Run linter**

Run: `poetry run ruff check miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py`

**Expected output:** No errors.

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py
git commit -m "feat(cli): add clean_sessions service with active-run safety guard"
```

**If Task Fails:**

1. **datetime.fromisoformat fails on trailing 'Z':**
   - Python 3.10 `fromisoformat` does not handle `Z` suffix.
   - Fix: Replace `Z` with `+00:00` before parsing:
     ```python
     raw = str(started_at_raw).replace("Z", "+00:00")
     started_at = datetime.fromisoformat(raw)
     ```
   - Update the implementation accordingly.

2. **Can't recover:**
   - Rollback: `git checkout -- miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py`

---

## Task 5: Create `commands/sessions.py` Click Group with `list` Subcommand

**Why:** The user-facing CLI command. `sessions` is a Click group with `list` as its first subcommand. `list` loads project config, creates the store, queries sessions, and renders output.

**Files:**
- Create: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/sessions.py`
- Create: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_sessions.py`

**Prerequisites:**
- Tasks 1-4 completed
- `miniautogen/cli/main.py` exists with `cli` group and `run_async` helper
- `miniautogen/cli/config.py` exists with `load_project_config()` or `load_config()`
- `miniautogen/cli/output.py` exists with output formatting
- `miniautogen/cli/errors.py` exists with `CLIError`
- `tests/cli/commands/__init__.py` exists (from Chunk 3)

**Step 1: Verify test directory exists**

Run:
```bash
ls /Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/__init__.py
```

**Expected:** File listed. If missing:
```bash
mkdir -p /Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands
touch /Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/__init__.py
```

**Step 2: Write the failing tests**

Create `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_sessions.py`:

```python
"""Integration tests for the 'sessions' CLI command group."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from miniautogen.cli.main import cli


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal project with database config."""
    db_path = tmp_path / "miniautogen.db"
    config_content = textwrap.dedent(f"""\
        project:
          name: test-project
          version: "0.1.0"

        provider:
          default: litellm
          model: gpt-4o-mini

        pipelines:
          main:
            target: pipelines.main:build_pipeline

        database:
          url: "sqlite+aiosqlite:///{db_path}"
    """)
    (tmp_path / "miniautogen.yaml").write_text(config_content)
    return tmp_path


@pytest.fixture()
def project_dir_no_db(tmp_path: Path) -> Path:
    """Create a minimal project without database config."""
    config_content = textwrap.dedent("""\
        project:
          name: test-project
          version: "0.1.0"

        provider:
          default: litellm
          model: gpt-4o-mini

        pipelines:
          main:
            target: pipelines.main:build_pipeline
    """)
    (tmp_path / "miniautogen.yaml").write_text(config_content)
    return tmp_path


class TestSessionsListCommand:
    """Tests for 'miniautogen sessions list'."""

    def test_list_empty(self, project_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sessions", "list"],
            catch_exceptions=False,
            env={"MINIAUTOGEN_PROJECT_DIR": str(project_dir)},
        )
        assert result.exit_code == 0, f"Output: {result.output}"
        assert "no sessions" in result.output.lower() or result.output.strip() == ""

    def test_list_json_format_empty(self, project_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sessions", "list", "--format", "json"],
            catch_exceptions=False,
            env={"MINIAUTOGEN_PROJECT_DIR": str(project_dir)},
        )
        assert result.exit_code == 0, f"Output: {result.output}"
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_without_database_uses_in_memory(
        self, project_dir_no_db: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sessions", "list"],
            catch_exceptions=False,
            env={"MINIAUTOGEN_PROJECT_DIR": str(project_dir_no_db)},
        )
        assert result.exit_code == 0, f"Output: {result.output}"
```

**Step 3: Run test to verify it fails**

Run: `poetry run pytest tests/cli/commands/test_sessions.py::TestSessionsListCommand -v`

**Expected output:**
```
FAILED ... - (sessions command not registered or doesn't exist)
```

**Step 4: Implement the sessions command group and list subcommand**

Create `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/sessions.py`:

```python
"""CLI command group: miniautogen sessions [list|clean].

Manages session/run data stored by the project.
"""
from __future__ import annotations

import json

import click

from miniautogen.cli.config import load_project_config
from miniautogen.cli.errors import CLIError
from miniautogen.cli.main import run_async


@click.group("sessions")
def sessions_group() -> None:
    """Manage session/run data."""


@sessions_group.command("list")
@click.option(
    "--status",
    type=str,
    default=None,
    help="Filter by run status (e.g. finished, failed, started).",
)
@click.option(
    "--limit",
    type=int,
    default=50,
    help="Maximum number of sessions to show.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: text (default) or json.",
)
def list_command(
    status: str | None,
    limit: int,
    output_format: str,
) -> None:
    """List sessions/runs from the project store."""
    from miniautogen.cli.services.session_ops import list_sessions

    try:
        config = load_project_config()
    except CLIError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    config_database = config.database

    try:
        sessions = run_async(
            list_sessions(
                config_database=config_database,
                status=status,
                limit=limit,
            )
        )
    except Exception as exc:
        click.echo(f"Error listing sessions: {exc}", err=True)
        raise SystemExit(1) from exc

    if output_format == "json":
        click.echo(json.dumps(sessions, indent=2, default=str))
    elif not sessions:
        click.echo("No sessions found.")
    else:
        for session in sessions:
            run_id = session.get("run_id", "unknown")
            run_status = session.get("status", "unknown")
            started = session.get("started_at", "N/A")
            click.echo(f"  {run_id}  {run_status:12s}  {started}")
```

**Step 5: Register the sessions group with the CLI**

In `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/main.py`, add the import and registration following the same pattern as the `run` command. After the existing `cli.add_command(run_command)` line (or wherever commands are registered), add:

```python
from miniautogen.cli.commands.sessions import sessions_group

cli.add_command(sessions_group)
```

**Note:** Look at how `run_command` and `check_command` are registered and follow the exact same pattern.

**Step 6: Run test to verify it passes**

Run: `poetry run pytest tests/cli/commands/test_sessions.py::TestSessionsListCommand -v`

**Expected output:**
```
PASSED tests/cli/commands/test_sessions.py::TestSessionsListCommand::test_list_empty
PASSED tests/cli/commands/test_sessions.py::TestSessionsListCommand::test_list_json_format_empty
PASSED tests/cli/commands/test_sessions.py::TestSessionsListCommand::test_list_without_database_uses_in_memory
```

**Step 7: Run linter**

Run: `poetry run ruff check miniautogen/cli/commands/sessions.py tests/cli/commands/test_sessions.py miniautogen/cli/main.py`

**Expected output:** No errors.

**Step 8: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/commands/sessions.py tests/cli/commands/test_sessions.py miniautogen/cli/main.py
git commit -m "feat(cli): add 'sessions list' command with status/limit/format options"
```

**If Task Fails:**

1. **`load_project_config` is actually named `load_config` or has different signature:**
   - Check Chunk 1 plan: it defines `load_config(path: Path)` not `load_project_config()`.
   - If `load_project_config()` does not exist, you need a convenience wrapper. Check what the `run` command from Chunk 3 uses and follow the same pattern.
   - The `run` command imports `load_project_config` from `miniautogen.cli.config`. If Chunk 1 only created `load_config(path)`, then a `load_project_config()` wrapper must have been added that finds the project root and calls `load_config`.

2. **`run_async` has different signature:**
   - Check: `poetry run python -c "from miniautogen.cli.main import run_async; print('OK')"`
   - If it does not exist or has a different name, check `main.py` for the async bridge function.

3. **Can't recover:**
   - Rollback: `git checkout -- miniautogen/cli/commands/sessions.py miniautogen/cli/main.py`

---

## Task 6: Add `clean` Subcommand to Sessions Group

**Why:** The `clean` subcommand deletes non-active runs with safety confirmation. It requires `--older-than` (in days) or `--yes` for explicit confirmation.

**Files:**
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/sessions.py`
- Modify: `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_sessions.py`

**Prerequisites:**
- Task 5 completed

**Step 1: Write the failing tests**

Append to `/Users/brunocapelao/Projects/miniAutoGen/tests/cli/commands/test_sessions.py`:

```python
class TestSessionsCleanCommand:
    """Tests for 'miniautogen sessions clean'."""

    def test_clean_requires_confirmation(self, project_dir: Path) -> None:
        """Without --yes, clean prompts for confirmation."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sessions", "clean"],
            input="n\n",
            env={"MINIAUTOGEN_PROJECT_DIR": str(project_dir)},
        )
        assert result.exit_code == 0 or result.exit_code == 1
        assert "confirm" in result.output.lower() or "abort" in result.output.lower()

    def test_clean_with_yes_flag(self, project_dir: Path) -> None:
        """With --yes, clean runs without prompting."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sessions", "clean", "--yes"],
            catch_exceptions=False,
            env={"MINIAUTOGEN_PROJECT_DIR": str(project_dir)},
        )
        assert result.exit_code == 0, f"Output: {result.output}"
        assert "deleted" in result.output.lower() or "0" in result.output

    def test_clean_with_older_than(self, project_dir: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sessions", "clean", "--older-than", "7", "--yes"],
            catch_exceptions=False,
            env={"MINIAUTOGEN_PROJECT_DIR": str(project_dir)},
        )
        assert result.exit_code == 0, f"Output: {result.output}"

    def test_clean_aborted_on_no_confirmation(
        self, project_dir: Path
    ) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sessions", "clean"],
            input="n\n",
            env={"MINIAUTOGEN_PROJECT_DIR": str(project_dir)},
        )
        assert "abort" in result.output.lower() or result.exit_code == 1
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/cli/commands/test_sessions.py::TestSessionsCleanCommand -v`

**Expected output:**
```
FAILED ... - (clean subcommand not found)
```

**Step 3: Implement the clean subcommand**

Add to the **end** of `/Users/brunocapelao/Projects/miniAutoGen/miniautogen/cli/commands/sessions.py`:

```python


@sessions_group.command("clean")
@click.option(
    "--older-than",
    "older_than_days",
    type=int,
    default=None,
    help="Only delete runs older than this many days.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
def clean_command(
    older_than_days: int | None,
    yes: bool,
) -> None:
    """Remove completed/failed/cancelled sessions.

    Active runs (status=started) are NEVER deleted.
    """
    from miniautogen.cli.services.session_ops import clean_sessions

    try:
        config = load_project_config()
    except CLIError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    config_database = config.database

    if not yes:
        msg = "Delete all non-active sessions"
        if older_than_days is not None:
            msg += f" older than {older_than_days} days"
        msg += "?"
        if not click.confirm(msg):
            click.echo("Aborted.")
            return

    try:
        deleted = run_async(
            clean_sessions(
                config_database=config_database,
                older_than_days=older_than_days,
            )
        )
    except Exception as exc:
        click.echo(f"Error cleaning sessions: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo(f"Deleted {deleted} session(s).")
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/cli/commands/test_sessions.py::TestSessionsCleanCommand -v`

**Expected output:**
```
PASSED tests/cli/commands/test_sessions.py::TestSessionsCleanCommand::test_clean_requires_confirmation
PASSED tests/cli/commands/test_sessions.py::TestSessionsCleanCommand::test_clean_with_yes_flag
PASSED tests/cli/commands/test_sessions.py::TestSessionsCleanCommand::test_clean_with_older_than
PASSED tests/cli/commands/test_sessions.py::TestSessionsCleanCommand::test_clean_aborted_on_no_confirmation
```

**Step 5: Run all sessions tests**

Run: `poetry run pytest tests/cli/commands/test_sessions.py -v`

**Expected output:** All 7 tests PASSED (3 list + 4 clean).

**Step 6: Run linter**

Run: `poetry run ruff check miniautogen/cli/commands/sessions.py tests/cli/commands/test_sessions.py`

**Expected output:** No errors.

**Step 7: Commit**

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add miniautogen/cli/commands/sessions.py tests/cli/commands/test_sessions.py
git commit -m "feat(cli): add 'sessions clean' command with safety guard and confirmation"
```

**If Task Fails:**

1. **click.confirm does not work in CliRunner:**
   - CliRunner handles `input=` for confirmation. Make sure `input="n\n"` is passed.
   - If `click.confirm` still fails, check that the CliRunner `input` stream is being read.

2. **Can't recover:**
   - Rollback: `git checkout -- miniautogen/cli/commands/sessions.py tests/cli/commands/test_sessions.py`

---

## Task 7: Run Code Review

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
- This tracks tech debt for future resolution

**Cosmetic/Nitpick Issues:**
- Add `FIXME(nitpick):` comments in code at the relevant location
- Format: `FIXME(nitpick): [Issue description] (reported by [reviewer] on [date], severity: Cosmetic)`
- Low-priority improvements tracked inline

3. **Proceed only when:**
   - Zero Critical/High/Medium issues remain
   - All Low issues have TODO(review): comments added
   - All Cosmetic issues have FIXME(nitpick): comments added

**Files to review:**
- `miniautogen/api.py` (changes from Task 1)
- `miniautogen/cli/services/session_ops.py` (Tasks 2-4)
- `miniautogen/cli/commands/sessions.py` (Tasks 5-6)
- `miniautogen/cli/main.py` (registration change from Task 5)
- `tests/cli/services/test_session_ops.py` (Tasks 2-4)
- `tests/cli/commands/test_sessions.py` (Tasks 5-6)

---

## Task 8: D3 Import Boundary Verification and Full Regression

**Why:** Verify that all new code respects the D3 import boundary and integrates cleanly with the existing codebase.

**Files:** No files to create or modify.

**Prerequisites:** Tasks 1-7 completed.

**Step 1: Verify D3 import boundary on session_ops.py**

Run:
```bash
poetry run python -c "
import ast, sys
with open('miniautogen/cli/services/session_ops.py') as f:
    tree = ast.parse(f.read())
forbidden = [
    'miniautogen.core', 'miniautogen.stores', 'miniautogen.policies',
    'miniautogen.backends', 'miniautogen.observability',
]
violations = []
for node in ast.walk(tree):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        if isinstance(node, ast.ImportFrom) and node.module:
            for prefix in forbidden:
                if node.module.startswith(prefix):
                    violations.append(node.module)
if violations:
    print(f'FAIL: D3 import boundary violations: {violations}')
    sys.exit(1)
else:
    print('PASS: No import boundary violations in session_ops.py')
"
```

**Expected output:** `PASS: No import boundary violations in session_ops.py`

**Step 2: Verify D3 import boundary on commands/sessions.py**

Run:
```bash
poetry run python -c "
import ast, sys
with open('miniautogen/cli/commands/sessions.py') as f:
    tree = ast.parse(f.read())
forbidden = [
    'miniautogen.core', 'miniautogen.stores', 'miniautogen.policies',
    'miniautogen.backends', 'miniautogen.observability',
]
violations = []
for node in ast.walk(tree):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        if isinstance(node, ast.ImportFrom) and node.module:
            for prefix in forbidden:
                if node.module.startswith(prefix):
                    violations.append(node.module)
if violations:
    print(f'FAIL: D3 import boundary violations: {violations}')
    sys.exit(1)
else:
    print('PASS: No import boundary violations in commands/sessions.py')
"
```

**Expected output:** `PASS: No import boundary violations in commands/sessions.py`

**Step 3: Run full test suite**

Run: `poetry run pytest -v --tb=short`

**Expected output:** All tests pass. Zero failures, zero errors.

**Step 4: Run linter on all changed files**

Run: `poetry run ruff check miniautogen/api.py miniautogen/cli/services/session_ops.py miniautogen/cli/commands/sessions.py miniautogen/cli/main.py tests/cli/services/test_session_ops.py tests/cli/commands/test_sessions.py`

**Expected output:** No errors.

**Step 5: Final commit if any review/lint fixes were made**

If Task 7 or this task produced fixes not yet committed:

```bash
cd /Users/brunocapelao/Projects/miniAutoGen
git add -u
git commit -m "fix(cli): address review and lint findings in sessions command"
```

**If Task Fails:**

1. **D3 import boundary violation:**
   - The service or command imports from internal modules.
   - Fix: Change to import from `miniautogen.api` instead. Task 1 ensured the stores are exported there.

2. **Regression test failure:**
   - Run: `poetry run pytest --tb=long -x` to see the first failure.
   - If pre-existing, document and proceed.
   - If introduced by this chunk, fix the issue.

3. **Can't recover:**
   - Document what failed and why.
   - Return to human partner.

---

## Appendix A: Complete `session_ops.py` Reference

The final file after Tasks 2-4 should look like this:

```python
"""Session/run management service for the CLI.

Provides operations to list, inspect, and clean session/run data
via the public SDK surface (miniautogen.api).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from miniautogen.api import InMemoryRunStore, RunStore, SQLAlchemyRunStore


def create_run_store(
    config_database: dict[str, Any] | None,
) -> RunStore:
    """Create a RunStore based on project database configuration.

    Parameters
    ----------
    config_database:
        The ``database`` section from ``ProjectConfig``.
        If ``None`` or missing ``url`` key, returns ``InMemoryRunStore``.
        Otherwise returns ``SQLAlchemyRunStore`` connected to the URL.

    Returns
    -------
    RunStore
        The appropriate store implementation.
    """
    if config_database and "url" in config_database:
        return SQLAlchemyRunStore(config_database["url"])
    return InMemoryRunStore()


async def list_sessions_from_store(
    store: RunStore,
    status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Query sessions from an already-instantiated store.

    Parameters
    ----------
    store:
        An initialized ``RunStore`` instance.
    status:
        If provided, filter runs by this status value.
    limit:
        Maximum number of runs to return.

    Returns
    -------
    list[dict]
        List of run payload dicts.
    """
    return await store.list_runs(status=status, limit=limit)


async def list_sessions(
    config_database: dict[str, Any] | None,
    status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """List sessions/runs from the project's configured store.

    Creates the appropriate store backend based on config, initializes
    it if needed (SQLAlchemy), and queries for runs.

    Parameters
    ----------
    config_database:
        The ``database`` section from ``ProjectConfig``.
    status:
        If provided, filter by run status.
    limit:
        Maximum number of runs to return.

    Returns
    -------
    list[dict]
        List of run payload dicts.
    """
    store = create_run_store(config_database)
    if hasattr(store, "init_db"):
        await store.init_db()
    return await list_sessions_from_store(
        store=store, status=status, limit=limit
    )


# Statuses that are safe to delete. "started" is explicitly excluded.
_CLEANABLE_STATUSES = frozenset({"finished", "failed", "cancelled"})


def _is_older_than(
    run: dict[str, Any], older_than_days: int | None
) -> bool:
    """Check if a run's started_at is older than the threshold.

    If ``older_than_days`` is None, all runs match (no age filter).
    If the run has no ``started_at`` field or it cannot be parsed,
    the run is considered old (safe to delete).
    """
    if older_than_days is None:
        return True

    started_at_raw = run.get("started_at")
    if not started_at_raw:
        return True

    try:
        raw = str(started_at_raw).replace("Z", "+00:00")
        started_at = datetime.fromisoformat(raw)
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return True

    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    return started_at < cutoff


async def clean_sessions_from_store(
    store: RunStore,
    older_than_days: int | None,
) -> int:
    """Delete non-active sessions from an already-instantiated store.

    SAFETY: Runs with status="started" are NEVER deleted.

    Parameters
    ----------
    store:
        An initialized ``RunStore`` instance.
    older_than_days:
        If provided, only delete runs older than this many days.
        If ``None``, all non-active runs are eligible for deletion.

    Returns
    -------
    int
        Number of runs deleted.
    """
    all_runs = await store.list_runs(status=None, limit=10_000)
    deleted = 0

    for run in all_runs:
        status = run.get("status", "")
        if status not in _CLEANABLE_STATUSES:
            continue
        if not _is_older_than(run, older_than_days):
            continue

        run_id = run.get("run_id")
        if run_id and await store.delete_run(run_id):
            deleted += 1

    return deleted


async def clean_sessions(
    config_database: dict[str, Any] | None,
    older_than_days: int | None,
) -> int:
    """Clean sessions/runs from the project's configured store.

    Creates the appropriate store backend, initializes it, and
    deletes non-active runs matching the age criteria.

    Parameters
    ----------
    config_database:
        The ``database`` section from ``ProjectConfig``.
    older_than_days:
        If provided, only delete runs older than this many days.

    Returns
    -------
    int
        Number of runs deleted.
    """
    store = create_run_store(config_database)
    if hasattr(store, "init_db"):
        await store.init_db()
    return await clean_sessions_from_store(
        store=store, older_than_days=older_than_days
    )
```

## Appendix B: Complete `commands/sessions.py` Reference

```python
"""CLI command group: miniautogen sessions [list|clean].

Manages session/run data stored by the project.
"""
from __future__ import annotations

import json

import click

from miniautogen.cli.config import load_project_config
from miniautogen.cli.errors import CLIError
from miniautogen.cli.main import run_async


@click.group("sessions")
def sessions_group() -> None:
    """Manage session/run data."""


@sessions_group.command("list")
@click.option(
    "--status",
    type=str,
    default=None,
    help="Filter by run status (e.g. finished, failed, started).",
)
@click.option(
    "--limit",
    type=int,
    default=50,
    help="Maximum number of sessions to show.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format: text (default) or json.",
)
def list_command(
    status: str | None,
    limit: int,
    output_format: str,
) -> None:
    """List sessions/runs from the project store."""
    from miniautogen.cli.services.session_ops import list_sessions

    try:
        config = load_project_config()
    except CLIError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    config_database = config.database

    try:
        sessions = run_async(
            list_sessions(
                config_database=config_database,
                status=status,
                limit=limit,
            )
        )
    except Exception as exc:
        click.echo(f"Error listing sessions: {exc}", err=True)
        raise SystemExit(1) from exc

    if output_format == "json":
        click.echo(json.dumps(sessions, indent=2, default=str))
    elif not sessions:
        click.echo("No sessions found.")
    else:
        for session in sessions:
            run_id = session.get("run_id", "unknown")
            run_status = session.get("status", "unknown")
            started = session.get("started_at", "N/A")
            click.echo(f"  {run_id}  {run_status:12s}  {started}")


@sessions_group.command("clean")
@click.option(
    "--older-than",
    "older_than_days",
    type=int,
    default=None,
    help="Only delete runs older than this many days.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
def clean_command(
    older_than_days: int | None,
    yes: bool,
) -> None:
    """Remove completed/failed/cancelled sessions.

    Active runs (status=started) are NEVER deleted.
    """
    from miniautogen.cli.services.session_ops import clean_sessions

    try:
        config = load_project_config()
    except CLIError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    config_database = config.database

    if not yes:
        msg = "Delete all non-active sessions"
        if older_than_days is not None:
            msg += f" older than {older_than_days} days"
        msg += "?"
        if not click.confirm(msg):
            click.echo("Aborted.")
            return

    try:
        deleted = run_async(
            clean_sessions(
                config_database=config_database,
                older_than_days=older_than_days,
            )
        )
    except Exception as exc:
        click.echo(f"Error cleaning sessions: {exc}", err=True)
        raise SystemExit(1) from exc

    click.echo(f"Deleted {deleted} session(s).")
```

## Appendix C: Assumptions About Chunks 1-3 Functions

This plan depends on these functions from previous chunks:

| Function | Module | Expected Signature |
|---|---|---|
| `load_project_config()` | `miniautogen.cli.config` | `() -> ProjectConfig` (finds project root via env var or cwd) |
| `run_async(coro)` | `miniautogen.cli.main` | `(coro) -> Any` (bridges async into Click sync) |
| `cli` | `miniautogen.cli.main` | Click group (root command) |
| `CLIError` | `miniautogen.cli.errors` | Base exception for CLI errors |

If `load_project_config` does not exist and only `load_config(path: Path)` exists, follow the pattern from `commands/run.py` (Chunk 3) which uses `load_project_config`. If Chunk 3 had to create a `load_project_config` wrapper, it should already exist.
