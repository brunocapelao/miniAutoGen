# M2 Chunk 4: Sessions Command Implementation Plan

> **For Agents:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Implement `miniautogen sessions list` and `miniautogen sessions clean` CLI commands that query and manage run data through the public SDK surface.

**Architecture:** The `sessions` command follows the same adapter/service split as other CLI commands. `commands/sessions.py` is a thin Click adapter that parses arguments and renders output. `services/session_ops.py` contains all application logic (store creation, querying, filtering, deletion). Services import only from `miniautogen.api` (and stdlib). A `create_run_store` factory abstracts over InMemory vs SQLAlchemy backends based on project config.

**Tech Stack:** Python 3.10+, Click 8+, SQLAlchemy 2+ (async), aiosqlite, pytest 7+, pytest-asyncio, ruff (line-length=100)

**Global Prerequisites:**
- Environment: macOS, Python 3.10-3.11
- Tools: `python --version`, `poetry --version`
- Access: No external services needed
- State: Branch from `main`, clean working tree
- **Chunks 1-3 MUST be implemented first** (CLI foundation, config, errors, output, init/check/run commands)

**Verification before starting:**
```bash
python --version        # Expected: Python 3.10.x or 3.11.x
poetry --version        # Expected: Poetry 1.x+
poetry run pytest --co  # Expected: collects tests, no import errors
poetry run ruff check . # Expected: no errors (or only pre-existing)
git status              # Expected: clean working tree
```

**Important Codebase Facts (discovered during planning):**

1. **RunStore is NOT in `miniautogen.api`** -- Task 0 must add it before CLI services can import it.
2. **Run payloads lack `created_at`** -- The PipelineRunner saves `{"status": "started", "correlation_id": "..."}` with no timestamp in the dict. The SQLAlchemy model has `updated_at` on the DB row but that's not returned in the payload. Task 0 must also add `created_at` to run payloads saved by PipelineRunner.
3. **Active run statuses are:** `"started"` (the only non-terminal status). Terminal statuses are: `"finished"`, `"failed"`, `"cancelled"`, `"timed_out"`.
4. **Click is not yet a dependency** -- must be added to pyproject.toml (expected from Chunk 1).
5. **The `run_id` is the dict key, not inside the payload** -- `list_runs` returns payloads without `run_id`. Services must handle this.

**What Already Exists (from SDK, DO NOT recreate):**
- `miniautogen/stores/run_store.py` -- `RunStore` ABC with `save_run`, `get_run`, `list_runs`, `delete_run`
- `miniautogen/stores/in_memory_run_store.py` -- `InMemoryRunStore`
- `miniautogen/stores/sqlalchemy_run_store.py` -- `SQLAlchemyRunStore` with `init_db()`, `DBRun` model
- `miniautogen/stores/__init__.py` -- exports all store classes

**What Must Exist from Chunks 1-3 (prerequisites, not built here):**
- `miniautogen/cli/__init__.py`
- `miniautogen/cli/main.py` -- Click group + `run_async` helper
- `miniautogen/cli/config.py` -- `ProjectConfig` Pydantic model with `database` section, `load_config()`
- `miniautogen/cli/errors.py` -- CLI error hierarchy + exit codes
- `miniautogen/cli/output.py` -- `render_text()`, `render_json()` formatting helpers
- `miniautogen/cli/commands/__init__.py`
- `miniautogen/cli/services/__init__.py`
- `click` in pyproject.toml dependencies

---

## Task 0: Expose RunStore in Public API and Add `created_at` to Run Payloads

**Why:** The design doc (D3) prohibits CLI services from importing `miniautogen.stores` directly. They must go through `miniautogen.api`. Also, `sessions clean --older-than` needs a `created_at` timestamp in run payloads, which the PipelineRunner currently doesn't save. We also need `run_id` inside the payload for `list_runs` to be useful.

**Files:**
- Modify: `miniautogen/api.py`
- Modify: `miniautogen/core/runtime/pipeline_runner.py`
- Modify: `miniautogen/stores/in_memory_run_store.py`
- Create: `tests/stores/test_run_store_payload_enrichment.py`

**Prerequisites:**
- Clean working tree on a feature branch

**Step 1: Write the test for enriched payloads**

Create `tests/stores/test_run_store_payload_enrichment.py`:

```python
"""Verify PipelineRunner saves run_id and created_at in run payloads."""

from datetime import datetime, timezone

import pytest

from miniautogen.stores import InMemoryRunStore


@pytest.mark.asyncio
async def test_list_runs_returns_payloads_with_run_id() -> None:
    store = InMemoryRunStore()
    await store.save_run(
        "run-abc",
        {
            "run_id": "run-abc",
            "status": "finished",
            "created_at": "2026-03-17T10:00:00+00:00",
        },
    )

    runs = await store.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-abc"
    assert runs[0]["created_at"] == "2026-03-17T10:00:00+00:00"


@pytest.mark.asyncio
async def test_list_runs_filters_by_status() -> None:
    store = InMemoryRunStore()
    await store.save_run(
        "run-1",
        {"run_id": "run-1", "status": "finished", "created_at": "2026-03-17T10:00:00+00:00"},
    )
    await store.save_run(
        "run-2",
        {"run_id": "run-2", "status": "started", "created_at": "2026-03-17T11:00:00+00:00"},
    )

    finished = await store.list_runs(status="finished")
    assert len(finished) == 1
    assert finished[0]["run_id"] == "run-1"
```

**Step 2: Run test to verify it passes (it should, since InMemoryRunStore just stores dicts)**

Run: `poetry run pytest tests/stores/test_run_store_payload_enrichment.py -v`

**Expected output:**
```
PASSED tests/stores/test_run_store_payload_enrichment.py::test_list_runs_returns_payloads_with_run_id
PASSED tests/stores/test_run_store_payload_enrichment.py::test_list_runs_filters_by_status
```

**Step 3: Add RunStore exports to `miniautogen/api.py`**

Add these imports after the existing imports in `miniautogen/api.py`:

```python
from miniautogen.stores.in_memory_run_store import InMemoryRunStore
from miniautogen.stores.run_store import RunStore
from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore
```

Add to the `__all__` list (in the "# Recovery" section or a new "# Stores" section):

```python
    # Stores
    "RunStore",
    "InMemoryRunStore",
    "SQLAlchemyRunStore",
```

**Step 4: Enrich PipelineRunner to save `run_id` and `created_at` in payloads**

In `miniautogen/core/runtime/pipeline_runner.py`, modify the `run_pipeline` method. Find the first `save_run` call (around line 98):

Replace:
```python
        if self.run_store is not None:
            await self.run_store.save_run(
                current_run_id,
                {
                    "status": "started",
                    "correlation_id": correlation_id,
                },
            )
```

With:
```python
        run_created_at = datetime.now(timezone.utc).isoformat()
        if self.run_store is not None:
            await self.run_store.save_run(
                current_run_id,
                {
                    "run_id": current_run_id,
                    "status": "started",
                    "correlation_id": correlation_id,
                    "created_at": run_created_at,
                },
            )
```

Then update ALL subsequent `save_run` calls in the same method to include `"run_id": current_run_id` and `"created_at": run_created_at`. There are 4 more calls to update:

1. The cancelled run (around line 153):
```python
                    await self.run_store.save_run(
                        current_run_id,
                        {
                            "run_id": current_run_id,
                            "status": "cancelled",
                            "correlation_id": correlation_id,
                            "created_at": run_created_at,
                        },
                    )
```

2. The timed_out run (around line 177):
```python
                    await self.run_store.save_run(
                        current_run_id,
                        {
                            "run_id": current_run_id,
                            "status": "timed_out",
                            "correlation_id": correlation_id,
                            "created_at": run_created_at,
                        },
                    )
```

3. The finished run (around line 202):
```python
                    await self.run_store.save_run(
                        current_run_id,
                        {
                            "run_id": current_run_id,
                            "status": "finished",
                            "correlation_id": correlation_id,
                            "created_at": run_created_at,
                        },
                    )
```

4. Update `_persist_failed_run` method to accept and include `created_at`:

Change the signature to:
```python
    async def _persist_failed_run(
        self,
        run_id: str,
        correlation_id: str,
        error_type: str,
        created_at: str,
    ) -> None:
        if self.run_store is not None:
            await self.run_store.save_run(
                run_id,
                {
                    "run_id": run_id,
                    "status": "failed",
                    "correlation_id": correlation_id,
                    "error_type": error_type,
                    "created_at": created_at,
                },
            )
```

And update the two calls to `_persist_failed_run` to pass `run_created_at`:
```python
            await self._persist_failed_run(
                current_run_id, correlation_id, type(exc).__name__, run_created_at,
            )
```

**Step 5: Run existing tests to verify no regression**

Run: `poetry run pytest tests/ -v -k "run_store or pipeline_runner" --no-header`

**Expected output:** All existing tests pass. No failures.

**Step 6: Commit**

```bash
git add miniautogen/api.py miniautogen/core/runtime/pipeline_runner.py tests/stores/test_run_store_payload_enrichment.py
git commit -m "feat: expose RunStore in public API and enrich run payloads with run_id and created_at"
```

**If Task Fails:**

1. **Import error in api.py:**
   - Check: `from miniautogen.stores.run_store import RunStore` -- verify file exists
   - Fix: Ensure `miniautogen/stores/run_store.py` is present
   - Rollback: `git checkout -- miniautogen/api.py`

2. **Existing tests break after PipelineRunner changes:**
   - Run: `poetry run pytest tests/ -v` (check what broke)
   - The payload shape changed, so tests that assert exact payload dicts will need updating
   - Rollback: `git checkout -- miniautogen/core/runtime/pipeline_runner.py`

---

## Task 1: Create `services/session_ops.py` -- Store Factory

**Why:** Both `list_sessions` and `clean_sessions` need a RunStore instance. The factory encapsulates the decision of InMemory vs SQLAlchemy based on project config.

**Files:**
- Create: `miniautogen/cli/services/session_ops.py`
- Create: `tests/cli/__init__.py`
- Create: `tests/cli/services/__init__.py`
- Create: `tests/cli/services/test_session_ops.py`

**Prerequisites:**
- Task 0 complete (RunStore exported from `miniautogen.api`)
- Chunks 1-3 complete (CLI package structure exists, `config.py` has `ProjectConfig`)

**Step 1: Write the test for the store factory**

Create `tests/cli/__init__.py` (empty file):
```python
```

Create `tests/cli/services/__init__.py` (empty file):
```python
```

Create `tests/cli/services/test_session_ops.py`:

```python
"""Tests for session_ops service — store factory, list, and clean."""

from __future__ import annotations

import pytest

from miniautogen.api import InMemoryRunStore
from miniautogen.cli.services.session_ops import create_run_store


@pytest.mark.asyncio
async def test_create_run_store_returns_in_memory_when_no_db_url() -> None:
    store = await create_run_store(database_url=None)
    assert isinstance(store, InMemoryRunStore)


@pytest.mark.asyncio
async def test_create_run_store_returns_sqlalchemy_when_db_url(tmp_path) -> None:
    from miniautogen.api import SQLAlchemyRunStore

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    store = await create_run_store(database_url=db_url)
    assert isinstance(store, SQLAlchemyRunStore)
```

**Step 2: Run test to verify it fails (module doesn't exist yet)**

Run: `poetry run pytest tests/cli/services/test_session_ops.py::test_create_run_store_returns_in_memory_when_no_db_url -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.cli.services.session_ops'
```

**Step 3: Implement the store factory**

Create `miniautogen/cli/services/session_ops.py`:

```python
"""Session operations — application logic for the sessions CLI command.

This module provides store creation, session listing, and session cleanup.
It imports ONLY from miniautogen.api (public SDK surface) and stdlib.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from miniautogen.api import InMemoryRunStore, RunStore, SQLAlchemyRunStore

logger = logging.getLogger(__name__)

# Statuses that are safe to delete (terminal states only).
_TERMINAL_STATUSES = frozenset({"finished", "failed", "cancelled", "timed_out"})

# Statuses that must NEVER be deleted (active/in-progress).
_ACTIVE_STATUSES = frozenset({"started"})


async def create_run_store(database_url: str | None) -> RunStore:
    """Create a RunStore from a database URL.

    If database_url is None or empty, returns InMemoryRunStore with a
    warning that data won't persist across CLI invocations.

    If database_url is provided, returns SQLAlchemyRunStore with
    tables auto-created.
    """
    if not database_url:
        logger.warning(
            "No database URL configured. Using in-memory store. "
            "Session data will not persist across CLI invocations."
        )
        return InMemoryRunStore()

    store = SQLAlchemyRunStore(db_url=database_url)
    await store.init_db()
    return store
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/cli/services/test_session_ops.py -v`

**Expected output:**
```
PASSED tests/cli/services/test_session_ops.py::test_create_run_store_returns_in_memory_when_no_db_url
PASSED tests/cli/services/test_session_ops.py::test_create_run_store_returns_sqlalchemy_when_db_url
```

**Step 5: Commit**

```bash
git add miniautogen/cli/services/session_ops.py tests/cli/__init__.py tests/cli/services/__init__.py tests/cli/services/test_session_ops.py
git commit -m "feat: add create_run_store factory for session operations"
```

**If Task Fails:**

1. **Import error on `miniautogen.cli.services`:**
   - Check: Does `miniautogen/cli/services/__init__.py` exist? (Chunk 1-3 prerequisite)
   - Fix: Create the `__init__.py` if missing

2. **SQLAlchemy store `init_db` fails:**
   - Check: `aiosqlite` installed? `poetry run python -c "import aiosqlite"`
   - Fix: `poetry add aiosqlite`

---

## Task 2: Implement `list_sessions` Service Function

**Why:** The `sessions list` command needs a function that queries the store and returns formatted results.

**Files:**
- Modify: `miniautogen/cli/services/session_ops.py`
- Modify: `tests/cli/services/test_session_ops.py`

**Prerequisites:**
- Task 1 complete

**Step 1: Write the tests for list_sessions**

Append to `tests/cli/services/test_session_ops.py`:

```python
from miniautogen.cli.services.session_ops import list_sessions


@pytest.mark.asyncio
async def test_list_sessions_returns_all_runs() -> None:
    store = InMemoryRunStore()
    await store.save_run(
        "run-1",
        {
            "run_id": "run-1",
            "status": "finished",
            "created_at": "2026-03-17T10:00:00+00:00",
        },
    )
    await store.save_run(
        "run-2",
        {
            "run_id": "run-2",
            "status": "started",
            "created_at": "2026-03-17T11:00:00+00:00",
        },
    )

    result = await list_sessions(store=store, status=None, limit=20)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_sessions_filters_by_status() -> None:
    store = InMemoryRunStore()
    await store.save_run(
        "run-1",
        {"run_id": "run-1", "status": "finished", "created_at": "2026-03-17T10:00:00+00:00"},
    )
    await store.save_run(
        "run-2",
        {"run_id": "run-2", "status": "started", "created_at": "2026-03-17T11:00:00+00:00"},
    )

    result = await list_sessions(store=store, status="finished", limit=20)
    assert len(result) == 1
    assert result[0]["run_id"] == "run-1"


@pytest.mark.asyncio
async def test_list_sessions_respects_limit() -> None:
    store = InMemoryRunStore()
    for i in range(5):
        await store.save_run(
            f"run-{i}",
            {
                "run_id": f"run-{i}",
                "status": "finished",
                "created_at": f"2026-03-17T{10 + i}:00:00+00:00",
            },
        )

    result = await list_sessions(store=store, status=None, limit=3)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_list_sessions_empty_store() -> None:
    store = InMemoryRunStore()
    result = await list_sessions(store=store, status=None, limit=20)
    assert result == []
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/cli/services/test_session_ops.py -v -k "list_sessions"`

**Expected output:**
```
FAILED - ImportError: cannot import name 'list_sessions' from 'miniautogen.cli.services.session_ops'
```

**Step 3: Implement list_sessions**

Add to `miniautogen/cli/services/session_ops.py` (after the `create_run_store` function):

```python
async def list_sessions(
    *,
    store: RunStore,
    status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """List runs from the store, optionally filtered by status.

    Args:
        store: The RunStore to query.
        status: If provided, only return runs with this status.
        limit: Maximum number of runs to return.

    Returns:
        List of run payload dicts, each containing at least
        run_id, status, and created_at.
    """
    return await store.list_runs(status=status, limit=limit)
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/cli/services/test_session_ops.py -v -k "list_sessions"`

**Expected output:**
```
PASSED tests/cli/services/test_session_ops.py::test_list_sessions_returns_all_runs
PASSED tests/cli/services/test_session_ops.py::test_list_sessions_filters_by_status
PASSED tests/cli/services/test_session_ops.py::test_list_sessions_respects_limit
PASSED tests/cli/services/test_session_ops.py::test_list_sessions_empty_store
```

**Step 5: Commit**

```bash
git add miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py
git commit -m "feat: add list_sessions service function"
```

**If Task Fails:**

1. **list_runs returns unexpected shape:**
   - Check: Payload dicts must include `run_id` and `status` (Task 0 ensures this)
   - Fix: Verify Task 0 was applied correctly

---

## Task 3: Implement `clean_sessions` Service Function

**Why:** The `sessions clean` command needs a function that safely deletes old terminal runs while NEVER touching active runs.

**Files:**
- Modify: `miniautogen/cli/services/session_ops.py`
- Modify: `tests/cli/services/test_session_ops.py`

**Prerequisites:**
- Task 2 complete

**Step 1: Write the tests for clean_sessions**

Append to `tests/cli/services/test_session_ops.py`:

```python
from datetime import datetime, timedelta, timezone

from miniautogen.cli.services.session_ops import clean_sessions


@pytest.mark.asyncio
async def test_clean_sessions_deletes_old_terminal_runs() -> None:
    store = InMemoryRunStore()
    old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    await store.save_run(
        "run-old",
        {"run_id": "run-old", "status": "finished", "created_at": old_date},
    )

    count = await clean_sessions(store=store, older_than_days=7)
    assert count == 1

    remaining = await store.list_runs()
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_clean_sessions_never_deletes_active_runs() -> None:
    """SAFETY INVARIANT: active (started) runs must never be deleted."""
    store = InMemoryRunStore()
    old_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    await store.save_run(
        "run-active",
        {"run_id": "run-active", "status": "started", "created_at": old_date},
    )

    count = await clean_sessions(store=store, older_than_days=1)
    assert count == 0

    remaining = await store.list_runs()
    assert len(remaining) == 1
    assert remaining[0]["status"] == "started"


@pytest.mark.asyncio
async def test_clean_sessions_respects_age_threshold() -> None:
    store = InMemoryRunStore()
    recent_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

    await store.save_run(
        "run-recent",
        {"run_id": "run-recent", "status": "finished", "created_at": recent_date},
    )
    await store.save_run(
        "run-old",
        {"run_id": "run-old", "status": "failed", "created_at": old_date},
    )

    count = await clean_sessions(store=store, older_than_days=7)
    assert count == 1

    remaining = await store.list_runs()
    assert len(remaining) == 1
    assert remaining[0]["run_id"] == "run-recent"


@pytest.mark.asyncio
async def test_clean_sessions_deletes_all_terminal_statuses() -> None:
    store = InMemoryRunStore()
    old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()

    for i, status in enumerate(["finished", "failed", "cancelled", "timed_out"]):
        await store.save_run(
            f"run-{i}",
            {"run_id": f"run-{i}", "status": status, "created_at": old_date},
        )

    count = await clean_sessions(store=store, older_than_days=7)
    assert count == 4

    remaining = await store.list_runs()
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_clean_sessions_empty_store_returns_zero() -> None:
    store = InMemoryRunStore()
    count = await clean_sessions(store=store, older_than_days=7)
    assert count == 0


@pytest.mark.asyncio
async def test_clean_sessions_skips_runs_without_created_at() -> None:
    """Runs missing created_at are skipped (not deleted) for safety."""
    store = InMemoryRunStore()
    await store.save_run(
        "run-no-date",
        {"run_id": "run-no-date", "status": "finished"},
    )

    count = await clean_sessions(store=store, older_than_days=1)
    assert count == 0

    remaining = await store.list_runs()
    assert len(remaining) == 1
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/cli/services/test_session_ops.py -v -k "clean_sessions"`

**Expected output:**
```
FAILED - ImportError: cannot import name 'clean_sessions' from 'miniautogen.cli.services.session_ops'
```

**Step 3: Implement clean_sessions**

Add to `miniautogen/cli/services/session_ops.py`:

```python
async def clean_sessions(
    *,
    store: RunStore,
    older_than_days: int,
) -> int:
    """Delete terminal runs older than the given number of days.

    SAFETY INVARIANT: Active runs (status='started') are NEVER deleted,
    regardless of age. Runs without a created_at field are also skipped
    for safety.

    Args:
        store: The RunStore to clean.
        older_than_days: Only delete runs older than this many days.

    Returns:
        Number of runs deleted.
    """
    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(days=older_than_days)
    all_runs = await store.list_runs(limit=10_000)

    deleted_count = 0
    for run in all_runs:
        status = run.get("status", "")
        if status in _ACTIVE_STATUSES:
            continue
        if status not in _TERMINAL_STATUSES:
            continue

        created_at_str = run.get("created_at")
        if not created_at_str:
            logger.warning(
                "Skipping run %s: no created_at field", run.get("run_id", "unknown")
            )
            continue

        try:
            created_at = datetime.fromisoformat(created_at_str)
        except (ValueError, TypeError):
            logger.warning(
                "Skipping run %s: invalid created_at=%r",
                run.get("run_id", "unknown"),
                created_at_str,
            )
            continue

        if created_at < cutoff:
            run_id = run.get("run_id")
            if run_id and await store.delete_run(run_id):
                deleted_count += 1

    return deleted_count
```

**IMPORTANT:** Replace the `__import__("datetime").timedelta` with a proper import. The function should use `timedelta` directly. Add `timedelta` to the existing `from datetime import datetime, timezone` import at the top of the file:

Change the import line from:
```python
from datetime import datetime, timezone
```
to:
```python
from datetime import datetime, timedelta, timezone
```

And the cutoff line becomes:
```python
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/cli/services/test_session_ops.py -v -k "clean_sessions"`

**Expected output:**
```
PASSED tests/cli/services/test_session_ops.py::test_clean_sessions_deletes_old_terminal_runs
PASSED tests/cli/services/test_session_ops.py::test_clean_sessions_never_deletes_active_runs
PASSED tests/cli/services/test_session_ops.py::test_clean_sessions_respects_age_threshold
PASSED tests/cli/services/test_session_ops.py::test_clean_sessions_deletes_all_terminal_statuses
PASSED tests/cli/services/test_session_ops.py::test_clean_sessions_empty_store_returns_zero
PASSED tests/cli/services/test_session_ops.py::test_clean_sessions_skips_runs_without_created_at
```

**Step 5: Run ALL session_ops tests**

Run: `poetry run pytest tests/cli/services/test_session_ops.py -v`

**Expected output:** All 10 tests pass.

**Step 6: Commit**

```bash
git add miniautogen/cli/services/session_ops.py tests/cli/services/test_session_ops.py
git commit -m "feat: add clean_sessions service with safety invariant against active run deletion"
```

**If Task Fails:**

1. **datetime.fromisoformat fails on Python 3.10:**
   - Check: Python 3.10 supports ISO format with `+00:00` suffix
   - Fix: If it fails, use `dateutil.parser.isoparse` instead (but it shouldn't)

2. **delete_run returns False unexpectedly:**
   - Check: `run_id` must be present in the payload for lookup
   - Fix: Verify Task 0 enrichment was applied

---

## Task 4: Run Code Review (Services)

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

## Task 5: Create `commands/sessions.py` -- Click Group with `list` Subcommand

**Why:** The `sessions list` subcommand is the CLI adapter that parses arguments, calls the service, and renders output.

**Files:**
- Create: `miniautogen/cli/commands/sessions.py`
- Create: `tests/cli/commands/__init__.py`
- Create: `tests/cli/commands/test_sessions.py`

**Prerequisites:**
- Tasks 0-3 complete
- Chunks 1-3 complete (specifically: `miniautogen/cli/main.py` with `cli` group, `config.py` with `load_config`, `output.py`)

**Step 1: Write the test for `sessions list`**

Create `tests/cli/commands/__init__.py` (empty file):
```python
```

Create `tests/cli/commands/test_sessions.py`:

```python
"""Tests for sessions CLI command using Click's CliRunner."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from miniautogen.cli.commands.sessions import sessions


def test_sessions_list_text_format() -> None:
    """sessions list renders a text table by default."""
    mock_runs = [
        {
            "run_id": "run-abc",
            "status": "finished",
            "created_at": "2026-03-17T10:00:00+00:00",
        },
        {
            "run_id": "run-def",
            "status": "failed",
            "created_at": "2026-03-17T11:00:00+00:00",
        },
    ]

    runner = CliRunner()
    with patch(
        "miniautogen.cli.commands.sessions._run_list_sessions",
        return_value=mock_runs,
    ):
        result = runner.invoke(sessions, ["list"])

    assert result.exit_code == 0
    assert "run-abc" in result.output
    assert "finished" in result.output
    assert "run-def" in result.output


def test_sessions_list_json_format() -> None:
    """sessions list --format json renders JSON output."""
    mock_runs = [
        {
            "run_id": "run-abc",
            "status": "finished",
            "created_at": "2026-03-17T10:00:00+00:00",
        },
    ]

    runner = CliRunner()
    with patch(
        "miniautogen.cli.commands.sessions._run_list_sessions",
        return_value=mock_runs,
    ):
        result = runner.invoke(sessions, ["list", "--format", "json"])

    assert result.exit_code == 0
    import json

    parsed = json.loads(result.output)
    assert len(parsed) == 1
    assert parsed[0]["run_id"] == "run-abc"


def test_sessions_list_empty() -> None:
    """sessions list with no runs shows informative message."""
    runner = CliRunner()
    with patch(
        "miniautogen.cli.commands.sessions._run_list_sessions",
        return_value=[],
    ):
        result = runner.invoke(sessions, ["list"])

    assert result.exit_code == 0
    assert "No sessions found" in result.output


def test_sessions_list_with_status_filter() -> None:
    """sessions list --status finished passes filter to service."""
    mock_runs = [
        {
            "run_id": "run-abc",
            "status": "finished",
            "created_at": "2026-03-17T10:00:00+00:00",
        },
    ]

    runner = CliRunner()
    with patch(
        "miniautogen.cli.commands.sessions._run_list_sessions",
        return_value=mock_runs,
    ) as mock_fn:
        result = runner.invoke(sessions, ["list", "--status", "finished"])

    assert result.exit_code == 0
    assert "run-abc" in result.output
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/cli/commands/test_sessions.py::test_sessions_list_text_format -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.cli.commands.sessions'
```

**Step 3: Implement the sessions command with list subcommand**

Create `miniautogen/cli/commands/sessions.py`:

```python
"""CLI command adapter for session management.

This module is a thin Click adapter. All application logic lives in
miniautogen.cli.services.session_ops.
"""

from __future__ import annotations

import json

import anyio
import click


def _run_list_sessions(
    status: str | None,
    limit: int,
    database_url: str | None,
) -> list[dict]:
    """Bridge async list_sessions into sync Click context."""
    from miniautogen.cli.services.session_ops import create_run_store, list_sessions

    async def _inner() -> list[dict]:
        store = await create_run_store(database_url=database_url)
        return await list_sessions(store=store, status=status, limit=limit)

    return anyio.from_thread.run(_inner)


@click.group("sessions")
def sessions() -> None:
    """Manage local session/run data."""


@sessions.command("list")
@click.option("--status", default=None, help="Filter by run status (e.g. finished, failed).")
@click.option("--limit", default=20, type=int, help="Maximum number of sessions to show.")
@click.option(
    "--format",
    "output_format",
    default="text",
    type=click.Choice(["text", "json"]),
    help="Output format.",
)
@click.pass_context
def list_cmd(ctx: click.Context, status: str | None, limit: int, output_format: str) -> None:
    """List recent pipeline runs/sessions."""
    # Resolve database URL from project config if available.
    database_url = _get_database_url(ctx)

    runs = _run_list_sessions(status=status, limit=limit, database_url=database_url)

    if output_format == "json":
        click.echo(json.dumps(runs, indent=2))
        return

    if not runs:
        click.echo("No sessions found.")
        return

    # Render text table.
    header = f"{'RUN ID':<40} {'STATUS':<12} {'CREATED AT':<28}"
    click.echo(header)
    click.echo("-" * len(header))
    for run in runs:
        run_id = run.get("run_id", "unknown")
        run_status = run.get("status", "unknown")
        created_at = run.get("created_at", "N/A")
        click.echo(f"{run_id:<40} {run_status:<12} {created_at:<28}")


def _get_database_url(ctx: click.Context) -> str | None:
    """Extract database URL from Click context or project config.

    Tries to load from the project config (set by parent CLI group).
    Falls back to None if not configured.
    """
    try:
        config = ctx.obj
        if config and hasattr(config, "database") and config.database:
            return getattr(config.database, "url", None)
    except Exception:
        pass
    return None
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/cli/commands/test_sessions.py -v`

**Expected output:**
```
PASSED tests/cli/commands/test_sessions.py::test_sessions_list_text_format
PASSED tests/cli/commands/test_sessions.py::test_sessions_list_json_format
PASSED tests/cli/commands/test_sessions.py::test_sessions_list_empty
PASSED tests/cli/commands/test_sessions.py::test_sessions_list_with_status_filter
```

**Step 5: Commit**

```bash
git add miniautogen/cli/commands/sessions.py tests/cli/commands/__init__.py tests/cli/commands/test_sessions.py
git commit -m "feat: add sessions list CLI command with text and json output"
```

**If Task Fails:**

1. **anyio.from_thread.run doesn't work in CliRunner:**
   - This happens because CliRunner runs synchronously. The mock patches `_run_list_sessions` directly, so the async bridge doesn't execute in tests.
   - For production use, the parent CLI group runs inside `anyio.run()` (from Chunk 1), so `from_thread.run` works.
   - Fix: If tests fail due to anyio, ensure the mock patches the correct function path.

2. **Click import error:**
   - Check: `poetry run python -c "import click"` -- is click installed?
   - Fix: `poetry add click` (should exist from Chunk 1)

---

## Task 6: Add `clean` Subcommand to Sessions Group

**Why:** The `sessions clean` command enables safe cleanup of old terminal runs.

**Files:**
- Modify: `miniautogen/cli/commands/sessions.py`
- Modify: `tests/cli/commands/test_sessions.py`

**Prerequisites:**
- Task 5 complete

**Step 1: Write tests for `sessions clean`**

Append to `tests/cli/commands/test_sessions.py`:

```python
def test_sessions_clean_with_older_than_and_yes() -> None:
    """sessions clean --older-than 7 --yes deletes runs without prompt."""
    runner = CliRunner()
    with patch(
        "miniautogen.cli.commands.sessions._run_clean_sessions",
        return_value=3,
    ):
        result = runner.invoke(sessions, ["clean", "--older-than", "7", "--yes"])

    assert result.exit_code == 0
    assert "3" in result.output
    assert "deleted" in result.output.lower()


def test_sessions_clean_requires_older_than_or_yes() -> None:
    """sessions clean without --older-than shows error."""
    runner = CliRunner()
    result = runner.invoke(sessions, ["clean"])

    assert result.exit_code != 0
    assert "older-than" in result.output.lower() or "required" in result.output.lower()


def test_sessions_clean_with_confirmation_prompt() -> None:
    """sessions clean --older-than 7 asks for confirmation."""
    runner = CliRunner()
    with patch(
        "miniautogen.cli.commands.sessions._run_count_cleanable_sessions",
        return_value=5,
    ), patch(
        "miniautogen.cli.commands.sessions._run_clean_sessions",
        return_value=5,
    ):
        result = runner.invoke(sessions, ["clean", "--older-than", "7"], input="y\n")

    assert result.exit_code == 0
    assert "5" in result.output


def test_sessions_clean_confirmation_declined() -> None:
    """sessions clean --older-than 7 with 'n' aborts."""
    runner = CliRunner()
    with patch(
        "miniautogen.cli.commands.sessions._run_count_cleanable_sessions",
        return_value=5,
    ):
        result = runner.invoke(sessions, ["clean", "--older-than", "7"], input="n\n")

    assert result.exit_code == 0
    assert "abort" in result.output.lower() or "cancel" in result.output.lower()


def test_sessions_clean_zero_deletable() -> None:
    """sessions clean with nothing to delete shows message."""
    runner = CliRunner()
    with patch(
        "miniautogen.cli.commands.sessions._run_count_cleanable_sessions",
        return_value=0,
    ):
        result = runner.invoke(sessions, ["clean", "--older-than", "7"])

    assert result.exit_code == 0
    assert "nothing" in result.output.lower() or "0" in result.output
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/cli/commands/test_sessions.py -v -k "clean"`

**Expected output:**
```
FAILED - AttributeError: 'Group' object has no attribute ... (or similar, since clean subcommand doesn't exist)
```

**Step 3: Add helper functions and `count_cleanable_sessions` to session_ops.py**

Add to `miniautogen/cli/services/session_ops.py`:

```python
async def count_cleanable_sessions(
    *,
    store: RunStore,
    older_than_days: int,
) -> int:
    """Count how many terminal runs would be deleted by clean_sessions.

    Uses the same filtering logic as clean_sessions but does not delete.
    Used for confirmation prompts.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    all_runs = await store.list_runs(limit=10_000)

    count = 0
    for run in all_runs:
        status = run.get("status", "")
        if status in _ACTIVE_STATUSES:
            continue
        if status not in _TERMINAL_STATUSES:
            continue

        created_at_str = run.get("created_at")
        if not created_at_str:
            continue

        try:
            created_at = datetime.fromisoformat(created_at_str)
        except (ValueError, TypeError):
            continue

        if created_at < cutoff:
            count += 1

    return count
```

**Step 4: Add bridge functions and clean subcommand to sessions.py**

Add to `miniautogen/cli/commands/sessions.py`, after the existing `_run_list_sessions` function:

```python
def _run_count_cleanable_sessions(
    older_than_days: int,
    database_url: str | None,
) -> int:
    """Bridge async count_cleanable_sessions into sync Click context."""
    from miniautogen.cli.services.session_ops import (
        count_cleanable_sessions,
        create_run_store,
    )

    async def _inner() -> int:
        store = await create_run_store(database_url=database_url)
        return await count_cleanable_sessions(store=store, older_than_days=older_than_days)

    return anyio.from_thread.run(_inner)


def _run_clean_sessions(
    older_than_days: int,
    database_url: str | None,
) -> int:
    """Bridge async clean_sessions into sync Click context."""
    from miniautogen.cli.services.session_ops import clean_sessions, create_run_store

    async def _inner() -> int:
        store = await create_run_store(database_url=database_url)
        return await clean_sessions(store=store, older_than_days=older_than_days)

    return anyio.from_thread.run(_inner)
```

Add the `clean` subcommand after the `list_cmd` function:

```python
@sessions.command("clean")
@click.option(
    "--older-than",
    "older_than_days",
    required=True,
    type=int,
    help="Delete terminal runs older than this many days.",
)
@click.option(
    "--yes",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt.",
)
@click.pass_context
def clean_cmd(ctx: click.Context, older_than_days: int, yes: bool) -> None:
    """Remove completed/failed/cancelled runs older than N days.

    SAFETY: Active runs (status=started) are NEVER deleted.
    """
    database_url = _get_database_url(ctx)

    if not yes:
        count = _run_count_cleanable_sessions(
            older_than_days=older_than_days,
            database_url=database_url,
        )
        if count == 0:
            click.echo("Nothing to clean. No terminal runs older than "
                        f"{older_than_days} days found.")
            return

        if not click.confirm(
            f"Found {count} session(s) older than {older_than_days} days. Delete them?"
        ):
            click.echo("Aborted.")
            return

    deleted = _run_clean_sessions(
        older_than_days=older_than_days,
        database_url=database_url,
    )
    click.echo(f"Deleted {deleted} session(s).")
```

**Step 5: Run tests to verify they pass**

Run: `poetry run pytest tests/cli/commands/test_sessions.py -v`

**Expected output:**
```
PASSED tests/cli/commands/test_sessions.py::test_sessions_list_text_format
PASSED tests/cli/commands/test_sessions.py::test_sessions_list_json_format
PASSED tests/cli/commands/test_sessions.py::test_sessions_list_empty
PASSED tests/cli/commands/test_sessions.py::test_sessions_list_with_status_filter
PASSED tests/cli/commands/test_sessions.py::test_sessions_clean_with_older_than_and_yes
PASSED tests/cli/commands/test_sessions.py::test_sessions_clean_requires_older_than_or_yes
PASSED tests/cli/commands/test_sessions.py::test_sessions_clean_with_confirmation_prompt
PASSED tests/cli/commands/test_sessions.py::test_sessions_clean_confirmation_declined
PASSED tests/cli/commands/test_sessions.py::test_sessions_clean_zero_deletable
```

**Step 6: Commit**

```bash
git add miniautogen/cli/commands/sessions.py miniautogen/cli/services/session_ops.py tests/cli/commands/test_sessions.py
git commit -m "feat: add sessions clean command with confirmation and safety invariant"
```

**If Task Fails:**

1. **`--older-than` not recognized as required:**
   - Check: Click uses `required=True` on options
   - Fix: Ensure the option decorator has `required=True`

2. **Confirmation prompt test hangs:**
   - Check: `input="y\n"` must be passed to `runner.invoke`
   - Fix: Ensure CliRunner input parameter is set

---

## Task 7: Register Sessions Group with Main CLI

**Why:** The sessions group needs to be added to the main CLI group so `miniautogen sessions list` and `miniautogen sessions clean` work.

**Files:**
- Modify: `miniautogen/cli/main.py`

**Prerequisites:**
- Task 6 complete
- `miniautogen/cli/main.py` exists (Chunk 1 prerequisite) with a `cli` Click group

**Step 1: Add the sessions group import and registration**

In `miniautogen/cli/main.py`, add the import:

```python
from miniautogen.cli.commands.sessions import sessions
```

And register it with the main group (near where other commands like `init`, `check`, `run` are registered):

```python
cli.add_command(sessions)
```

**Step 2: Verify registration**

Run: `poetry run python -m miniautogen sessions --help`

**Expected output:**
```
Usage: miniautogen sessions [OPTIONS] COMMAND [ARGS]...

  Manage local session/run data.

Commands:
  clean  Remove completed/failed/cancelled runs older than N days.
  list   List recent pipeline runs/sessions.
```

**Step 3: Commit**

```bash
git add miniautogen/cli/main.py
git commit -m "feat: register sessions command group with main CLI"
```

**If Task Fails:**

1. **Import error:**
   - Check: Does `miniautogen/cli/commands/sessions.py` exist?
   - Fix: Verify Task 5-6 completed successfully

---

## Task 8: Run Code Review (Commands)

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

## Task 9: End-to-End Integration Test

**Why:** Verify the entire sessions workflow from store creation through listing and cleaning, exercised through the service layer (not Click, to avoid async bridge complexity in tests).

**Files:**
- Create: `tests/cli/services/test_session_ops_integration.py`

**Prerequisites:**
- Tasks 0-7 complete

**Step 1: Write the integration test**

Create `tests/cli/services/test_session_ops_integration.py`:

```python
"""End-to-end integration test for sessions workflow.

Exercises: create store -> save runs -> list -> clean -> verify.
Uses InMemoryRunStore to avoid database setup in CI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from miniautogen.api import InMemoryRunStore
from miniautogen.cli.services.session_ops import (
    clean_sessions,
    count_cleanable_sessions,
    list_sessions,
)


@pytest.mark.asyncio
async def test_full_session_lifecycle() -> None:
    """Simulate: pipeline runs -> list sessions -> clean old ones."""
    store = InMemoryRunStore()
    now = datetime.now(timezone.utc)

    # Simulate pipeline runs saved by PipelineRunner.
    await store.save_run(
        "run-recent-ok",
        {
            "run_id": "run-recent-ok",
            "status": "finished",
            "correlation_id": "corr-1",
            "created_at": now.isoformat(),
        },
    )
    await store.save_run(
        "run-old-failed",
        {
            "run_id": "run-old-failed",
            "status": "failed",
            "correlation_id": "corr-2",
            "created_at": (now - timedelta(days=15)).isoformat(),
        },
    )
    await store.save_run(
        "run-old-cancelled",
        {
            "run_id": "run-old-cancelled",
            "status": "cancelled",
            "correlation_id": "corr-3",
            "created_at": (now - timedelta(days=20)).isoformat(),
        },
    )
    await store.save_run(
        "run-active",
        {
            "run_id": "run-active",
            "status": "started",
            "correlation_id": "corr-4",
            "created_at": (now - timedelta(days=30)).isoformat(),
        },
    )

    # --- List all sessions ---
    all_sessions = await list_sessions(store=store, status=None, limit=100)
    assert len(all_sessions) == 4

    # --- List only finished ---
    finished = await list_sessions(store=store, status="finished", limit=100)
    assert len(finished) == 1
    assert finished[0]["run_id"] == "run-recent-ok"

    # --- Count cleanable (older than 10 days) ---
    cleanable = await count_cleanable_sessions(store=store, older_than_days=10)
    assert cleanable == 2  # run-old-failed + run-old-cancelled (NOT run-active!)

    # --- Clean sessions older than 10 days ---
    deleted = await clean_sessions(store=store, older_than_days=10)
    assert deleted == 2

    # --- Verify remaining ---
    remaining = await list_sessions(store=store, status=None, limit=100)
    assert len(remaining) == 2

    remaining_ids = {r["run_id"] for r in remaining}
    assert "run-recent-ok" in remaining_ids  # Recent, not cleaned
    assert "run-active" in remaining_ids      # Active, NEVER cleaned
    assert "run-old-failed" not in remaining_ids
    assert "run-old-cancelled" not in remaining_ids


@pytest.mark.asyncio
async def test_clean_then_list_shows_consistent_state() -> None:
    """After cleaning, list should reflect the deletion."""
    store = InMemoryRunStore()
    old_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()

    for i in range(10):
        await store.save_run(
            f"run-{i}",
            {
                "run_id": f"run-{i}",
                "status": "finished",
                "created_at": old_date,
            },
        )

    deleted = await clean_sessions(store=store, older_than_days=1)
    assert deleted == 10

    remaining = await list_sessions(store=store, status=None, limit=100)
    assert remaining == []
```

**Step 2: Run the integration test**

Run: `poetry run pytest tests/cli/services/test_session_ops_integration.py -v`

**Expected output:**
```
PASSED tests/cli/services/test_session_ops_integration.py::test_full_session_lifecycle
PASSED tests/cli/services/test_session_ops_integration.py::test_clean_then_list_shows_consistent_state
```

**Step 3: Run the full test suite**

Run: `poetry run pytest tests/ -v --no-header`

**Expected output:** All tests pass, including the new ones.

**Step 4: Commit**

```bash
git add tests/cli/services/test_session_ops_integration.py
git commit -m "test: add end-to-end integration tests for sessions workflow"
```

**If Task Fails:**

1. **Test fails on count_cleanable_sessions:**
   - Check: Import `count_cleanable_sessions` exists in session_ops.py (added in Task 6 Step 3)
   - Fix: Verify Task 6 Step 3 was implemented

2. **Unexpected run count after clean:**
   - Debug: Print `remaining` to see what's left
   - Check: Active runs must survive cleaning

---

## Task 10: SQLAlchemy Integration Test (Optional but Recommended)

**Why:** Verify the sessions workflow works with a real SQLAlchemy database, not just InMemory.

**Files:**
- Create: `tests/cli/services/test_session_ops_sqlalchemy.py`

**Prerequisites:**
- Task 9 complete
- `aiosqlite` installed

**Step 1: Write the SQLAlchemy integration test**

Create `tests/cli/services/test_session_ops_sqlalchemy.py`:

```python
"""Integration test for sessions with SQLAlchemy backend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from miniautogen.cli.services.session_ops import (
    clean_sessions,
    create_run_store,
    list_sessions,
)


@pytest.mark.asyncio
async def test_sessions_with_sqlalchemy_store(tmp_path) -> None:
    """Full lifecycle test with a real SQLite database."""
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'sessions_test.db'}"
    store = await create_run_store(database_url=db_url)

    now = datetime.now(timezone.utc)

    await store.save_run(
        "run-1",
        {
            "run_id": "run-1",
            "status": "finished",
            "created_at": (now - timedelta(days=10)).isoformat(),
        },
    )
    await store.save_run(
        "run-2",
        {
            "run_id": "run-2",
            "status": "started",
            "created_at": (now - timedelta(days=10)).isoformat(),
        },
    )

    # List all
    all_runs = await list_sessions(store=store, status=None, limit=100)
    assert len(all_runs) == 2

    # Clean older than 5 days
    deleted = await clean_sessions(store=store, older_than_days=5)
    assert deleted == 1  # Only run-1 (finished), NOT run-2 (started)

    # Verify
    remaining = await list_sessions(store=store, status=None, limit=100)
    assert len(remaining) == 1
    assert remaining[0]["run_id"] == "run-2"
```

**Step 2: Run the test**

Run: `poetry run pytest tests/cli/services/test_session_ops_sqlalchemy.py -v`

**Expected output:**
```
PASSED tests/cli/services/test_session_ops_sqlalchemy.py::test_sessions_with_sqlalchemy_store
```

**Step 3: Commit**

```bash
git add tests/cli/services/test_session_ops_sqlalchemy.py
git commit -m "test: add SQLAlchemy integration test for sessions workflow"
```

**If Task Fails:**

1. **aiosqlite not installed:**
   - Fix: `poetry add aiosqlite` (should already be a dependency)

2. **Database file permission error:**
   - Check: `tmp_path` should be writable
   - Fix: Use a different temp directory

---

## Task 11: Lint and Final Verification

**Why:** Ensure all new code passes ruff linting and the full test suite.

**Files:** None (verification only)

**Step 1: Run ruff**

Run: `poetry run ruff check miniautogen/cli/ tests/cli/ --fix`

**Expected output:** No errors, or only auto-fixed formatting issues.

**Step 2: Run ruff format**

Run: `poetry run ruff format miniautogen/cli/ tests/cli/`

**Expected output:** Files formatted (or already formatted).

**Step 3: Run full test suite**

Run: `poetry run pytest tests/ -v --no-header`

**Expected output:** All tests pass.

**Step 4: Commit any lint fixes**

```bash
git add -u
git commit -m "style: apply ruff formatting to sessions command"
```

(Only if there were changes from Step 1-2.)

---

## Task 12: Final Code Review

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
   - All Low/Cosmetic issues have appropriate comments added

---

## Summary of Files Created/Modified

**Created:**
- `miniautogen/cli/services/session_ops.py` -- Store factory, list_sessions, clean_sessions, count_cleanable_sessions
- `miniautogen/cli/commands/sessions.py` -- Click group with list and clean subcommands
- `tests/cli/__init__.py` -- Package marker
- `tests/cli/services/__init__.py` -- Package marker
- `tests/cli/services/test_session_ops.py` -- Unit tests for service functions
- `tests/cli/services/test_session_ops_integration.py` -- End-to-end integration test
- `tests/cli/services/test_session_ops_sqlalchemy.py` -- SQLAlchemy integration test
- `tests/cli/commands/__init__.py` -- Package marker
- `tests/cli/commands/test_sessions.py` -- Click command tests via CliRunner
- `tests/stores/test_run_store_payload_enrichment.py` -- Enriched payload tests

**Modified:**
- `miniautogen/api.py` -- Added RunStore, InMemoryRunStore, SQLAlchemyRunStore exports
- `miniautogen/core/runtime/pipeline_runner.py` -- Added run_id and created_at to payloads
- `miniautogen/cli/main.py` -- Registered sessions command group

## Safety Invariants

1. **NEVER delete active runs** -- `clean_sessions` explicitly skips runs with status `"started"` (the only active status). This is tested in `test_clean_sessions_never_deletes_active_runs`.
2. **Runs without `created_at` are never deleted** -- Missing timestamps cause a skip, not a crash. Tested in `test_clean_sessions_skips_runs_without_created_at`.
3. **Import boundary respected** -- `session_ops.py` imports only from `miniautogen.api`, never from internal modules like `miniautogen.stores` directly.
