# Milestone 1 -- Chunk 4: Persistence & Stores

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan.

**Goal:** Complete store implementations and enable session recovery from checkpoints

**Architecture:** Store-agnostic persistence via ABC contracts; session recovery as first-class concept. All stores follow a consistent pattern: ABC defines the contract, InMemory implements with dicts/lists, SQLAlchemy implements with async sessions and aiosqlite. Recovery is a standalone class that composes stores, not a subclass.

**Tech Stack:** Python 3.10+, SQLAlchemy 2+ (async), aiosqlite, Pydantic v2, pytest-asyncio, ruff (line-length=100)

**Global Prerequisites:**
- Environment: macOS / Linux, Python 3.10-3.11
- Tools: `python --version`, `poetry --version`
- Access: No external services needed (aiosqlite runs in-process)
- State: Branch from `main`, clean working tree

**Verification before starting:**
```bash
python --version        # Expected: Python 3.10.x or 3.11.x
poetry --version        # Expected: Poetry 1.x+
poetry run pytest --co  # Expected: collects tests, no import errors
poetry run ruff check . # Expected: no errors (or only pre-existing)
git status              # Expected: clean working tree on main
```

**What Already Exists (DO NOT recreate):**
- `miniautogen/stores/in_memory.py` -- contains `InMemoryMessageStore` (already complete)
- `miniautogen/stores/sqlalchemy.py` -- contains `SQLAlchemyMessageStore` (already complete)
- `miniautogen/stores/__init__.py` -- already exports both message stores
- `tests/stores/test_in_memory_message_store.py` -- basic roundtrip + remove tests
- `miniautogen/core/events/types.py` -- `EventType.CHECKPOINT_RESTORED` already defined

---

## Task 1: Add SQLAlchemyMessageStore Tests

**Why:** `SQLAlchemyMessageStore` exists but has zero test coverage. Before extending any stores, we must verify the existing implementation works correctly.

**Files:**
- Create: `tests/stores/test_sqlalchemy_message_store.py`

**Prerequisites:**
- `miniautogen/stores/sqlalchemy.py` must exist (it does)
- `aiosqlite` must be installed

**Step 1: Write the test file**

Create `tests/stores/test_sqlalchemy_message_store.py`:

```python
import pytest

from miniautogen.core.contracts import Message
from miniautogen.stores import SQLAlchemyMessageStore


@pytest.mark.asyncio
async def test_sqlalchemy_message_store_roundtrip(tmp_path) -> None:
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages.db'}"
    )
    await store.init_db()

    msg = Message(sender_id="agent_1", content="hello world")
    await store.add_message(msg)

    messages = await store.get_messages()
    assert len(messages) == 1
    assert messages[0].sender_id == "agent_1"
    assert messages[0].content == "hello world"
    assert messages[0].id is not None


@pytest.mark.asyncio
async def test_sqlalchemy_message_store_returns_empty_when_no_messages(tmp_path) -> None:
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages-empty.db'}"
    )
    await store.init_db()

    messages = await store.get_messages()
    assert messages == []


@pytest.mark.asyncio
async def test_sqlalchemy_message_store_remove_message(tmp_path) -> None:
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages-remove.db'}"
    )
    await store.init_db()

    first = Message(sender_id="user", content="first")
    second = Message(sender_id="assistant", content="second")
    await store.add_message(first)
    await store.add_message(second)

    messages = await store.get_messages()
    assert len(messages) == 2

    await store.remove_message(messages[0].id or 0)

    remaining = await store.get_messages()
    assert len(remaining) == 1
    assert remaining[0].content == "second"


@pytest.mark.asyncio
async def test_sqlalchemy_message_store_limit_and_offset(tmp_path) -> None:
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages-paging.db'}"
    )
    await store.init_db()

    for i in range(5):
        await store.add_message(Message(sender_id="user", content=f"msg-{i}"))

    page = await store.get_messages(limit=2, offset=1)
    assert len(page) == 2
    assert page[0].content == "msg-1"
    assert page[1].content == "msg-2"


@pytest.mark.asyncio
async def test_sqlalchemy_message_store_preserves_additional_info(tmp_path) -> None:
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages-info.db'}"
    )
    await store.init_db()

    msg = Message(
        sender_id="agent_1",
        content="hello",
        additional_info={"model": "gpt-4", "tokens": 42},
    )
    await store.add_message(msg)

    messages = await store.get_messages()
    assert messages[0].additional_info == {"model": "gpt-4", "tokens": 42}
```

**Step 2: Run the tests**

Run: `poetry run pytest tests/stores/test_sqlalchemy_message_store.py -v`

**Expected output:**
```
tests/stores/test_sqlalchemy_message_store.py::test_sqlalchemy_message_store_roundtrip PASSED
tests/stores/test_sqlalchemy_message_store.py::test_sqlalchemy_message_store_returns_empty_when_no_messages PASSED
tests/stores/test_sqlalchemy_message_store.py::test_sqlalchemy_message_store_remove_message PASSED
tests/stores/test_sqlalchemy_message_store.py::test_sqlalchemy_message_store_limit_and_offset PASSED
tests/stores/test_sqlalchemy_message_store.py::test_sqlalchemy_message_store_preserves_additional_info PASSED
```

**If tests fail:** The existing `SQLAlchemyMessageStore` in `miniautogen/stores/sqlalchemy.py` may have bugs. Fix them there (do not create a new file).

**Step 3: Lint**

Run: `poetry run ruff check tests/stores/test_sqlalchemy_message_store.py`

**Expected output:** No errors.

**Step 4: Commit**

```bash
git add tests/stores/test_sqlalchemy_message_store.py
git commit -m "test: add SQLAlchemyMessageStore coverage"
```

**If Task Fails:**
1. **Import error for `SQLAlchemyMessageStore`:** Verify `miniautogen/stores/__init__.py` exports it from `miniautogen.stores.sqlalchemy`.
2. **aiosqlite not installed:** Run `poetry install`.
3. **Rollback:** `git checkout -- .`

---

## Task 2: Extend RunStore ABC with list_runs and delete_run

**Why:** The current `RunStore` ABC only has `save_run` and `get_run`. We need query and cleanup methods for session recovery and operational use.

**Files:**
- Modify: `miniautogen/stores/run_store.py` (lines 1-15)
- Modify: `miniautogen/stores/in_memory_run_store.py` (lines 1-17)
- Modify: `miniautogen/stores/sqlalchemy_run_store.py` (lines 1-62)
- Create: `tests/stores/test_run_store_extended.py`

**Step 1: Write the failing tests**

Create `tests/stores/test_run_store_extended.py`:

```python
import pytest

from miniautogen.stores import InMemoryRunStore


@pytest.mark.asyncio
async def test_list_runs_returns_all() -> None:
    store = InMemoryRunStore()
    await store.save_run("run-1", {"status": "started"})
    await store.save_run("run-2", {"status": "finished"})

    runs = await store.list_runs()
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_list_runs_filters_by_status() -> None:
    store = InMemoryRunStore()
    await store.save_run("run-1", {"status": "started"})
    await store.save_run("run-2", {"status": "finished"})
    await store.save_run("run-3", {"status": "finished"})

    runs = await store.list_runs(status="finished")
    assert len(runs) == 2
    assert all(r["status"] == "finished" for r in runs)


@pytest.mark.asyncio
async def test_list_runs_respects_limit() -> None:
    store = InMemoryRunStore()
    for i in range(5):
        await store.save_run(f"run-{i}", {"status": "finished"})

    runs = await store.list_runs(limit=3)
    assert len(runs) == 3


@pytest.mark.asyncio
async def test_delete_run_removes_entry() -> None:
    store = InMemoryRunStore()
    await store.save_run("run-1", {"status": "started"})

    deleted = await store.delete_run("run-1")
    assert deleted is True
    assert await store.get_run("run-1") is None


@pytest.mark.asyncio
async def test_delete_run_returns_false_for_missing() -> None:
    store = InMemoryRunStore()

    deleted = await store.delete_run("nonexistent")
    assert deleted is False
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/stores/test_run_store_extended.py -v`

**Expected output:**
```
FAILED - AttributeError: 'InMemoryRunStore' object has no attribute 'list_runs'
```

**Step 3: Extend the RunStore ABC**

Modify `miniautogen/stores/run_store.py` -- replace the entire file content:

```python
from abc import ABC, abstractmethod
from typing import Any


class RunStore(ABC):
    """Reserved contract for run persistence introduced in later waves."""

    @abstractmethod
    async def save_run(self, run_id: str, payload: dict[str, Any]) -> None:
        """Persist run metadata."""

    @abstractmethod
    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Fetch persisted run metadata."""

    @abstractmethod
    async def list_runs(
        self, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List runs, optionally filtered by status."""

    @abstractmethod
    async def delete_run(self, run_id: str) -> bool:
        """Delete a run by ID.  Returns True if it existed."""
```

**Step 4: Implement in InMemoryRunStore**

Modify `miniautogen/stores/in_memory_run_store.py` -- replace entire file:

```python
from typing import Any

from miniautogen.stores.run_store import RunStore


class InMemoryRunStore(RunStore):
    """Simple in-memory run persistence for the new runtime."""

    def __init__(self) -> None:
        self._runs: dict[str, dict[str, Any]] = {}

    async def save_run(self, run_id: str, payload: dict[str, Any]) -> None:
        self._runs[run_id] = payload

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self._runs.get(run_id)

    async def list_runs(
        self, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        runs = list(self._runs.values())
        if status is not None:
            runs = [r for r in runs if r.get("status") == status]
        return runs[:limit]

    async def delete_run(self, run_id: str) -> bool:
        if run_id in self._runs:
            del self._runs[run_id]
            return True
        return False
```

**Step 5: Implement in SQLAlchemyRunStore**

Modify `miniautogen/stores/sqlalchemy_run_store.py` -- replace entire file:

```python
import json
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import DateTime, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from miniautogen.stores.run_store import RunStore


class Base(DeclarativeBase):
    pass


class DBRun(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class SQLAlchemyRunStore(RunStore):
    """Minimal SQLAlchemy-backed run store for the new runtime."""

    def __init__(self, db_url: str):
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def save_run(self, run_id: str, payload: dict[str, Any]) -> None:
        async with self.async_session() as session:
            async with session.begin():
                db_run = await session.get(DBRun, run_id)
                if db_run is None:
                    db_run = DBRun(
                        run_id=run_id,
                        payload_json=json.dumps(payload),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(db_run)
                else:
                    db_run.payload_json = json.dumps(payload)
                    db_run.updated_at = datetime.now(timezone.utc)

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        async with self.async_session() as session:
            stmt = select(DBRun).where(DBRun.run_id == run_id)
            result = await session.execute(stmt)
            db_run = result.scalar_one_or_none()
            if db_run is None:
                return None
            return cast(dict[str, Any], json.loads(db_run.payload_json))

    async def list_runs(
        self, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        async with self.async_session() as session:
            stmt = select(DBRun).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            runs = [
                cast(dict[str, Any], json.loads(r.payload_json)) for r in rows
            ]
            if status is not None:
                runs = [r for r in runs if r.get("status") == status]
            return runs

    async def delete_run(self, run_id: str) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                db_run = await session.get(DBRun, run_id)
                if db_run is None:
                    return False
                await session.execute(
                    delete(DBRun).where(DBRun.run_id == run_id)
                )
                return True
```

**Step 6: Run all tests**

Run: `poetry run pytest tests/stores/test_run_store_extended.py tests/stores/test_in_memory_run_store.py tests/stores/test_sqlalchemy_run_store.py -v`

**Expected output:** All tests PASSED (existing roundtrip tests + new list/delete tests).

**Step 7: Lint**

Run: `poetry run ruff check miniautogen/stores/run_store.py miniautogen/stores/in_memory_run_store.py miniautogen/stores/sqlalchemy_run_store.py tests/stores/test_run_store_extended.py`

**Expected output:** No errors.

**Step 8: Commit**

```bash
git add miniautogen/stores/run_store.py miniautogen/stores/in_memory_run_store.py miniautogen/stores/sqlalchemy_run_store.py tests/stores/test_run_store_extended.py
git commit -m "feat: add list_runs and delete_run to RunStore ABC and implementations"
```

**If Task Fails:**
1. **Existing tests break:** The `list_runs` / `delete_run` additions to the ABC will break any mock/stub that implements `RunStore` without these methods. Search for `RunStore` usage across the codebase: `grep -r "RunStore" --include="*.py"`. Add the new methods to any stubs.
2. **SQLAlchemy filter issue:** The in-memory filter is applied after fetch. For large datasets this is inefficient but correct for MVP. Do not optimize.
3. **Rollback:** `git checkout -- miniautogen/stores/run_store.py miniautogen/stores/in_memory_run_store.py miniautogen/stores/sqlalchemy_run_store.py`

---

## Task 3: Extend CheckpointStore ABC with list_checkpoints and delete_checkpoint

**Why:** Mirror the RunStore extension for CheckpointStore. Needed for recovery listing and cleanup.

**Files:**
- Modify: `miniautogen/stores/checkpoint_store.py` (lines 1-15)
- Modify: `miniautogen/stores/in_memory_checkpoint_store.py` (lines 1-17)
- Modify: `miniautogen/stores/sqlalchemy_checkpoint_store.py` (lines 1-62)
- Create: `tests/stores/test_checkpoint_store_extended.py`

**Step 1: Write the failing tests**

Create `tests/stores/test_checkpoint_store_extended.py`:

```python
import pytest

from miniautogen.stores import InMemoryCheckpointStore


@pytest.mark.asyncio
async def test_list_checkpoints_returns_all() -> None:
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("run-1", {"step": 1})
    await store.save_checkpoint("run-2", {"step": 2})

    checkpoints = await store.list_checkpoints()
    assert len(checkpoints) == 2


@pytest.mark.asyncio
async def test_list_checkpoints_filters_by_run_id() -> None:
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("run-1", {"step": 1})
    await store.save_checkpoint("run-2", {"step": 2})

    checkpoints = await store.list_checkpoints(run_id="run-1")
    assert len(checkpoints) == 1
    assert checkpoints[0]["step"] == 1


@pytest.mark.asyncio
async def test_delete_checkpoint_removes_entry() -> None:
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("run-1", {"step": 1})

    deleted = await store.delete_checkpoint("run-1")
    assert deleted is True
    assert await store.get_checkpoint("run-1") is None


@pytest.mark.asyncio
async def test_delete_checkpoint_returns_false_for_missing() -> None:
    store = InMemoryCheckpointStore()

    deleted = await store.delete_checkpoint("nonexistent")
    assert deleted is False
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/stores/test_checkpoint_store_extended.py -v`

**Expected output:**
```
FAILED - AttributeError: 'InMemoryCheckpointStore' object has no attribute 'list_checkpoints'
```

**Step 3: Extend the CheckpointStore ABC**

Modify `miniautogen/stores/checkpoint_store.py` -- replace entire file:

```python
from abc import ABC, abstractmethod
from typing import Any


class CheckpointStore(ABC):
    """Reserved contract for checkpoint persistence introduced later."""

    @abstractmethod
    async def save_checkpoint(self, run_id: str, payload: dict[str, Any]) -> None:
        """Persist checkpoint data."""

    @abstractmethod
    async def get_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        """Fetch checkpoint data for a run."""

    @abstractmethod
    async def list_checkpoints(
        self, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        """List checkpoints, optionally filtered by run_id."""

    @abstractmethod
    async def delete_checkpoint(self, run_id: str) -> bool:
        """Delete a checkpoint by run_id.  Returns True if it existed."""
```

**Step 4: Implement in InMemoryCheckpointStore**

Modify `miniautogen/stores/in_memory_checkpoint_store.py` -- replace entire file:

```python
from typing import Any

from miniautogen.stores.checkpoint_store import CheckpointStore


class InMemoryCheckpointStore(CheckpointStore):
    """Simple in-memory checkpoint persistence for the new runtime."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, dict[str, Any]] = {}

    async def save_checkpoint(self, run_id: str, payload: dict[str, Any]) -> None:
        self._checkpoints[run_id] = payload

    async def get_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        return self._checkpoints.get(run_id)

    async def list_checkpoints(
        self, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        if run_id is not None:
            cp = self._checkpoints.get(run_id)
            return [cp] if cp is not None else []
        return list(self._checkpoints.values())

    async def delete_checkpoint(self, run_id: str) -> bool:
        if run_id in self._checkpoints:
            del self._checkpoints[run_id]
            return True
        return False
```

**Step 5: Implement in SQLAlchemyCheckpointStore**

Modify `miniautogen/stores/sqlalchemy_checkpoint_store.py` -- replace entire file:

```python
import json
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import DateTime, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from miniautogen.stores.checkpoint_store import CheckpointStore


class Base(DeclarativeBase):
    pass


class DBCheckpoint(Base):
    __tablename__ = "checkpoints"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class SQLAlchemyCheckpointStore(CheckpointStore):
    """Minimal SQLAlchemy-backed checkpoint store for the new runtime."""

    def __init__(self, db_url: str):
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def save_checkpoint(self, run_id: str, payload: dict[str, Any]) -> None:
        async with self.async_session() as session:
            async with session.begin():
                db_checkpoint = await session.get(DBCheckpoint, run_id)
                if db_checkpoint is None:
                    db_checkpoint = DBCheckpoint(
                        run_id=run_id,
                        payload_json=json.dumps(payload),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(db_checkpoint)
                else:
                    db_checkpoint.payload_json = json.dumps(payload)
                    db_checkpoint.updated_at = datetime.now(timezone.utc)

    async def get_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        async with self.async_session() as session:
            stmt = select(DBCheckpoint).where(DBCheckpoint.run_id == run_id)
            result = await session.execute(stmt)
            db_checkpoint = result.scalar_one_or_none()
            if db_checkpoint is None:
                return None
            return cast(dict[str, Any], json.loads(db_checkpoint.payload_json))

    async def list_checkpoints(
        self, run_id: str | None = None
    ) -> list[dict[str, Any]]:
        async with self.async_session() as session:
            stmt = select(DBCheckpoint)
            if run_id is not None:
                stmt = stmt.where(DBCheckpoint.run_id == run_id)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                cast(dict[str, Any], json.loads(r.payload_json)) for r in rows
            ]

    async def delete_checkpoint(self, run_id: str) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                db_checkpoint = await session.get(DBCheckpoint, run_id)
                if db_checkpoint is None:
                    return False
                await session.execute(
                    delete(DBCheckpoint).where(
                        DBCheckpoint.run_id == run_id
                    )
                )
                return True
```

**Step 6: Run all checkpoint tests**

Run: `poetry run pytest tests/stores/test_checkpoint_store_extended.py tests/stores/test_in_memory_checkpoint_store.py tests/stores/test_sqlalchemy_checkpoint_store.py -v`

**Expected output:** All tests PASSED.

**Step 7: Lint**

Run: `poetry run ruff check miniautogen/stores/checkpoint_store.py miniautogen/stores/in_memory_checkpoint_store.py miniautogen/stores/sqlalchemy_checkpoint_store.py tests/stores/test_checkpoint_store_extended.py`

**Expected output:** No errors.

**Step 8: Commit**

```bash
git add miniautogen/stores/checkpoint_store.py miniautogen/stores/in_memory_checkpoint_store.py miniautogen/stores/sqlalchemy_checkpoint_store.py tests/stores/test_checkpoint_store_extended.py
git commit -m "feat: add list_checkpoints and delete_checkpoint to CheckpointStore ABC and implementations"
```

**If Task Fails:**
1. **Existing tests break:** Same pattern as Task 2. Search for `CheckpointStore` implementations/mocks and add missing methods.
2. **Rollback:** `git checkout -- miniautogen/stores/checkpoint_store.py miniautogen/stores/in_memory_checkpoint_store.py miniautogen/stores/sqlalchemy_checkpoint_store.py`

---

## Task 4: Add SQLAlchemy Extended Store Tests

**Why:** Tasks 2 and 3 only tested InMemory. We need to verify list/delete work with SQLAlchemy too.

**Files:**
- Create: `tests/stores/test_sqlalchemy_store_extended.py`

**Step 1: Write the tests**

Create `tests/stores/test_sqlalchemy_store_extended.py`:

```python
import pytest

from miniautogen.stores import SQLAlchemyCheckpointStore, SQLAlchemyRunStore


# --- RunStore list/delete ---


@pytest.mark.asyncio
async def test_sqlalchemy_run_store_list_runs(tmp_path) -> None:
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs-list.db'}"
    )
    await store.init_db()
    await store.save_run("run-1", {"status": "started"})
    await store.save_run("run-2", {"status": "finished"})

    runs = await store.list_runs()
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_sqlalchemy_run_store_list_runs_by_status(tmp_path) -> None:
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs-filter.db'}"
    )
    await store.init_db()
    await store.save_run("run-1", {"status": "started"})
    await store.save_run("run-2", {"status": "finished"})
    await store.save_run("run-3", {"status": "finished"})

    runs = await store.list_runs(status="finished")
    assert len(runs) == 2


@pytest.mark.asyncio
async def test_sqlalchemy_run_store_delete_run(tmp_path) -> None:
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs-delete.db'}"
    )
    await store.init_db()
    await store.save_run("run-1", {"status": "started"})

    assert await store.delete_run("run-1") is True
    assert await store.get_run("run-1") is None


@pytest.mark.asyncio
async def test_sqlalchemy_run_store_delete_missing_returns_false(tmp_path) -> None:
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs-del-miss.db'}"
    )
    await store.init_db()

    assert await store.delete_run("nonexistent") is False


# --- CheckpointStore list/delete ---


@pytest.mark.asyncio
async def test_sqlalchemy_checkpoint_store_list_checkpoints(tmp_path) -> None:
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'cp-list.db'}"
    )
    await store.init_db()
    await store.save_checkpoint("run-1", {"step": 1})
    await store.save_checkpoint("run-2", {"step": 2})

    checkpoints = await store.list_checkpoints()
    assert len(checkpoints) == 2


@pytest.mark.asyncio
async def test_sqlalchemy_checkpoint_store_list_by_run_id(tmp_path) -> None:
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'cp-filter.db'}"
    )
    await store.init_db()
    await store.save_checkpoint("run-1", {"step": 1})
    await store.save_checkpoint("run-2", {"step": 2})

    checkpoints = await store.list_checkpoints(run_id="run-1")
    assert len(checkpoints) == 1
    assert checkpoints[0]["step"] == 1


@pytest.mark.asyncio
async def test_sqlalchemy_checkpoint_store_delete(tmp_path) -> None:
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'cp-delete.db'}"
    )
    await store.init_db()
    await store.save_checkpoint("run-1", {"step": 1})

    assert await store.delete_checkpoint("run-1") is True
    assert await store.get_checkpoint("run-1") is None


@pytest.mark.asyncio
async def test_sqlalchemy_checkpoint_store_delete_missing(tmp_path) -> None:
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'cp-del-miss.db'}"
    )
    await store.init_db()

    assert await store.delete_checkpoint("nonexistent") is False
```

**Step 2: Run the tests**

Run: `poetry run pytest tests/stores/test_sqlalchemy_store_extended.py -v`

**Expected output:** All 8 tests PASSED.

**Step 3: Lint**

Run: `poetry run ruff check tests/stores/test_sqlalchemy_store_extended.py`

**Expected output:** No errors.

**Step 4: Commit**

```bash
git add tests/stores/test_sqlalchemy_store_extended.py
git commit -m "test: add SQLAlchemy list/delete coverage for RunStore and CheckpointStore"
```

**If Task Fails:**
1. **Tests fail on list/delete:** The SQLAlchemy implementations from Tasks 2/3 have a bug. Read the traceback carefully and fix the specific method.
2. **Rollback:** `git checkout -- tests/stores/test_sqlalchemy_store_extended.py`

---

## Task 5: Implement SessionRecovery

**Why:** This is the core deliverable -- a standalone class that composes stores to enable crash recovery.

**Files:**
- Create: `miniautogen/core/runtime/recovery.py`
- Create: `tests/core/runtime/test_recovery.py`

**Prerequisites:**
- Tasks 2 and 3 completed (RunStore and CheckpointStore have list/delete methods)

**Step 1: Write the failing tests**

Create `tests/core/runtime/test_recovery.py`:

```python
import pytest

from miniautogen.core.runtime.recovery import SessionRecovery
from miniautogen.stores import InMemoryCheckpointStore, InMemoryRunStore


@pytest.mark.asyncio
async def test_can_resume_returns_false_when_no_checkpoint() -> None:
    checkpoint_store = InMemoryCheckpointStore()
    run_store = InMemoryRunStore()
    recovery = SessionRecovery(
        checkpoint_store=checkpoint_store, run_store=run_store
    )

    assert await recovery.can_resume("run-1") is False


@pytest.mark.asyncio
async def test_can_resume_returns_true_when_checkpoint_exists() -> None:
    checkpoint_store = InMemoryCheckpointStore()
    run_store = InMemoryRunStore()
    recovery = SessionRecovery(
        checkpoint_store=checkpoint_store, run_store=run_store
    )

    await checkpoint_store.save_checkpoint("run-1", {"step": 3, "data": "abc"})

    assert await recovery.can_resume("run-1") is True


@pytest.mark.asyncio
async def test_load_checkpoint_returns_none_when_missing() -> None:
    checkpoint_store = InMemoryCheckpointStore()
    run_store = InMemoryRunStore()
    recovery = SessionRecovery(
        checkpoint_store=checkpoint_store, run_store=run_store
    )

    result = await recovery.load_checkpoint("run-1")
    assert result is None


@pytest.mark.asyncio
async def test_load_checkpoint_returns_saved_data() -> None:
    checkpoint_store = InMemoryCheckpointStore()
    run_store = InMemoryRunStore()
    recovery = SessionRecovery(
        checkpoint_store=checkpoint_store, run_store=run_store
    )

    payload = {"step": 3, "partial_results": [1, 2, 3]}
    await checkpoint_store.save_checkpoint("run-1", payload)

    result = await recovery.load_checkpoint("run-1")
    assert result == payload


@pytest.mark.asyncio
async def test_mark_resumed_updates_run_status() -> None:
    checkpoint_store = InMemoryCheckpointStore()
    run_store = InMemoryRunStore()
    recovery = SessionRecovery(
        checkpoint_store=checkpoint_store, run_store=run_store
    )

    await run_store.save_run("run-1", {"status": "failed"})

    await recovery.mark_resumed("run-1")

    run = await run_store.get_run("run-1")
    assert run is not None
    assert run["status"] == "resumed"


@pytest.mark.asyncio
async def test_mark_resumed_creates_run_if_missing() -> None:
    checkpoint_store = InMemoryCheckpointStore()
    run_store = InMemoryRunStore()
    recovery = SessionRecovery(
        checkpoint_store=checkpoint_store, run_store=run_store
    )

    await recovery.mark_resumed("run-1")

    run = await run_store.get_run("run-1")
    assert run is not None
    assert run["status"] == "resumed"


@pytest.mark.asyncio
async def test_full_recovery_flow() -> None:
    """Simulate: run -> crash -> resume -> verify state."""
    checkpoint_store = InMemoryCheckpointStore()
    run_store = InMemoryRunStore()
    recovery = SessionRecovery(
        checkpoint_store=checkpoint_store, run_store=run_store
    )

    # Simulate a run that saved a checkpoint before crashing
    await run_store.save_run("run-1", {"status": "failed"})
    await checkpoint_store.save_checkpoint(
        "run-1", {"step": 2, "results_so_far": ["a", "b"]}
    )

    # Recovery flow
    assert await recovery.can_resume("run-1") is True
    restored = await recovery.load_checkpoint("run-1")
    assert restored == {"step": 2, "results_so_far": ["a", "b"]}

    await recovery.mark_resumed("run-1")
    run = await run_store.get_run("run-1")
    assert run is not None
    assert run["status"] == "resumed"
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/core/runtime/test_recovery.py -v`

**Expected output:**
```
FAILED - ModuleNotFoundError: No module named 'miniautogen.core.runtime.recovery'
```

**Step 3: Implement SessionRecovery**

Create `miniautogen/core/runtime/recovery.py`:

```python
from __future__ import annotations

from typing import Any

from miniautogen.stores.checkpoint_store import CheckpointStore
from miniautogen.stores.run_store import RunStore


class SessionRecovery:
    """Enables resuming a pipeline run from its last checkpoint.

    This class composes a CheckpointStore and RunStore to provide
    a clean API for crash recovery.  It does not own execution --
    it only manages the state lookup and status transitions.
    """

    def __init__(
        self,
        checkpoint_store: CheckpointStore,
        run_store: RunStore,
    ) -> None:
        self._checkpoint_store = checkpoint_store
        self._run_store = run_store

    async def can_resume(self, run_id: str) -> bool:
        """Return True if a checkpoint exists for the given run."""
        checkpoint = await self._checkpoint_store.get_checkpoint(run_id)
        return checkpoint is not None

    async def load_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        """Load the last checkpoint payload for a run."""
        return await self._checkpoint_store.get_checkpoint(run_id)

    async def mark_resumed(self, run_id: str) -> None:
        """Update (or create) the run record with status='resumed'."""
        await self._run_store.save_run(run_id, {"status": "resumed"})
```

**Step 4: Run the tests**

Run: `poetry run pytest tests/core/runtime/test_recovery.py -v`

**Expected output:**
```
tests/core/runtime/test_recovery.py::test_can_resume_returns_false_when_no_checkpoint PASSED
tests/core/runtime/test_recovery.py::test_can_resume_returns_true_when_checkpoint_exists PASSED
tests/core/runtime/test_recovery.py::test_load_checkpoint_returns_none_when_missing PASSED
tests/core/runtime/test_recovery.py::test_load_checkpoint_returns_saved_data PASSED
tests/core/runtime/test_recovery.py::test_mark_resumed_updates_run_status PASSED
tests/core/runtime/test_recovery.py::test_mark_resumed_creates_run_if_missing PASSED
tests/core/runtime/test_recovery.py::test_full_recovery_flow PASSED
```

**Step 5: Lint**

Run: `poetry run ruff check miniautogen/core/runtime/recovery.py tests/core/runtime/test_recovery.py`

**Expected output:** No errors.

**Step 6: Commit**

```bash
git add miniautogen/core/runtime/recovery.py tests/core/runtime/test_recovery.py
git commit -m "feat: add SessionRecovery for crash recovery from checkpoints"
```

**If Task Fails:**
1. **Import error for stores:** Verify Tasks 2/3 are complete and the ABCs have the new methods.
2. **Test fails on `mark_resumed`:** The `save_run` method does an upsert in InMemoryRunStore (overwrites existing). Verify this is the case.
3. **Rollback:** `git checkout -- miniautogen/core/runtime/recovery.py`

---

## Task 6: Wire Recovery into PipelineRunner

**Why:** The PipelineRunner must be able to accept a `SessionRecovery` instance and use it to restore state before running a pipeline.

**Files:**
- Modify: `miniautogen/core/runtime/pipeline_runner.py` (lines 17-32, 60-98)
- Create: `tests/core/runtime/test_runner_recovery.py`

**Prerequisites:**
- Task 5 completed (SessionRecovery exists)

**Step 1: Write the failing tests**

Create `tests/core/runtime/test_runner_recovery.py`:

```python
import pytest

from miniautogen.core.events import EventType, InMemoryEventSink
from miniautogen.core.runtime import PipelineRunner
from miniautogen.core.runtime.recovery import SessionRecovery
from miniautogen.stores import InMemoryCheckpointStore, InMemoryRunStore


class ResumablePipeline:
    """Pipeline that accepts restored state and continues from it."""

    async def run(self, state):
        # If state has "restored_step", continue from there
        step = state.get("restored_step", 0)
        results = list(state.get("results_so_far", []))
        for i in range(step, 3):
            results.append(f"step-{i}")
        return {"results": results, "completed": True}


class FailingPipeline:
    """Pipeline that fails partway through."""

    async def run(self, state):
        raise RuntimeError("simulated crash")


class StateWithRunId:
    """Minimal state object with a run_id attribute."""

    def __init__(self, run_id: str, data: dict | None = None):
        self.run_id = run_id
        self.data = data or {}

    def get(self, key, default=None):
        return self.data.get(key, default)


@pytest.mark.asyncio
async def test_runner_with_recovery_resumes_from_checkpoint() -> None:
    run_store = InMemoryRunStore()
    checkpoint_store = InMemoryCheckpointStore()
    event_sink = InMemoryEventSink()
    recovery = SessionRecovery(
        checkpoint_store=checkpoint_store, run_store=run_store
    )

    # Simulate a previous crashed run that saved a checkpoint
    await run_store.save_run("run-1", {"status": "failed"})
    await checkpoint_store.save_checkpoint(
        "run-1",
        {"restored_step": 1, "results_so_far": ["step-0"]},
    )

    runner = PipelineRunner(
        event_sink=event_sink,
        run_store=run_store,
        checkpoint_store=checkpoint_store,
        recovery=recovery,
    )

    # Use a state with the same run_id to trigger recovery
    state = StateWithRunId("run-1")
    result = await runner.run_pipeline(ResumablePipeline(), state)

    assert result == {"results": ["step-0", "step-1", "step-2"], "completed": True}

    # Verify CHECKPOINT_RESTORED event was emitted
    event_types = [e.type for e in event_sink.events]
    assert EventType.CHECKPOINT_RESTORED.value in event_types


@pytest.mark.asyncio
async def test_runner_without_recovery_runs_normally() -> None:
    run_store = InMemoryRunStore()
    checkpoint_store = InMemoryCheckpointStore()
    runner = PipelineRunner(
        run_store=run_store, checkpoint_store=checkpoint_store
    )

    result = await runner.run_pipeline(
        ResumablePipeline(), {"restored_step": 0}
    )
    assert result == {
        "results": ["step-0", "step-1", "step-2"],
        "completed": True,
    }


@pytest.mark.asyncio
async def test_runner_recovery_skipped_when_no_checkpoint() -> None:
    run_store = InMemoryRunStore()
    checkpoint_store = InMemoryCheckpointStore()
    event_sink = InMemoryEventSink()
    recovery = SessionRecovery(
        checkpoint_store=checkpoint_store, run_store=run_store
    )

    runner = PipelineRunner(
        event_sink=event_sink,
        run_store=run_store,
        checkpoint_store=checkpoint_store,
        recovery=recovery,
    )

    state = StateWithRunId("run-new")
    result = await runner.run_pipeline(ResumablePipeline(), state)

    assert result["completed"] is True
    event_types = [e.type for e in event_sink.events]
    assert EventType.CHECKPOINT_RESTORED.value not in event_types
```

**Step 2: Run tests to verify they fail**

Run: `poetry run pytest tests/core/runtime/test_runner_recovery.py -v`

**Expected output:**
```
FAILED - TypeError: PipelineRunner.__init__() got an unexpected keyword argument 'recovery'
```

**Step 3: Modify PipelineRunner to accept recovery**

In `miniautogen/core/runtime/pipeline_runner.py`, make two changes:

**Change 1 -- Add recovery parameter to `__init__`:**

Find this block (lines 20-32):
```python
    def __init__(
        self,
        event_sink: EventSink | None = None,
        run_store: RunStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        execution_policy: ExecutionPolicy | None = None,
    ):
        self.event_sink = event_sink or NullEventSink()
        self.run_store = run_store
        self.checkpoint_store = checkpoint_store
        self.execution_policy = execution_policy
        self.last_run_id: str | None = None
        self.logger = get_logger(__name__)
```

Replace with:
```python
    def __init__(
        self,
        event_sink: EventSink | None = None,
        run_store: RunStore | None = None,
        checkpoint_store: CheckpointStore | None = None,
        execution_policy: ExecutionPolicy | None = None,
        recovery: SessionRecovery | None = None,
    ):
        self.event_sink = event_sink or NullEventSink()
        self.run_store = run_store
        self.checkpoint_store = checkpoint_store
        self.execution_policy = execution_policy
        self.recovery = recovery
        self.last_run_id: str | None = None
        self.logger = get_logger(__name__)
```

**Change 2 -- Add import for SessionRecovery at top of file:**

Find (line 1):
```python
from __future__ import annotations
```

After all existing imports (after line 14), add:
```python
from miniautogen.core.runtime.recovery import SessionRecovery
```

**IMPORTANT: Circular import risk.** Since `recovery.py` imports from `stores` (not from `pipeline_runner`), there is no circular dependency. The import is safe.

**Change 3 -- Add recovery logic at the start of `run_pipeline`:**

Find this block (lines 80-87):
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

Insert this BEFORE it (between the logger.bind block and the run_store block):
```python
        # --- Session recovery ---
        recovered_state = None
        if self.recovery is not None:
            if await self.recovery.can_resume(current_run_id):
                recovered_state = await self.recovery.load_checkpoint(
                    current_run_id
                )
                await self.recovery.mark_resumed(current_run_id)
                await self.event_sink.publish(
                    ExecutionEvent(
                        type=EventType.CHECKPOINT_RESTORED.value,
                        timestamp=datetime.now(timezone.utc),
                        run_id=current_run_id,
                        correlation_id=correlation_id,
                        scope="pipeline_runner",
                        payload={"checkpoint": recovered_state},
                    )
                )
                logger.info(
                    "checkpoint_restored", run_id=current_run_id
                )

```

**Change 4 -- Use recovered state when running pipeline:**

Find (lines 101-105):
```python
            if effective_timeout is None:
                result = await pipeline.run(state)
            else:
                with anyio.fail_after(effective_timeout):
                    result = await pipeline.run(state)
```

Replace with:
```python
            run_state = recovered_state if recovered_state is not None else state
            if effective_timeout is None:
                result = await pipeline.run(run_state)
            else:
                with anyio.fail_after(effective_timeout):
                    result = await pipeline.run(run_state)
```

**Step 4: Run the new tests**

Run: `poetry run pytest tests/core/runtime/test_runner_recovery.py -v`

**Expected output:**
```
tests/core/runtime/test_runner_recovery.py::test_runner_with_recovery_resumes_from_checkpoint PASSED
tests/core/runtime/test_runner_recovery.py::test_runner_without_recovery_runs_normally PASSED
tests/core/runtime/test_runner_recovery.py::test_runner_recovery_skipped_when_no_checkpoint PASSED
```

**Step 5: Run ALL existing runner tests to check for regressions**

Run: `poetry run pytest tests/core/runtime/ -v`

**Expected output:** All existing tests pass (no regressions). The `recovery` parameter defaults to `None`, so existing code is unaffected.

**Step 6: Lint**

Run: `poetry run ruff check miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_runner_recovery.py`

**Expected output:** No errors.

**Step 7: Commit**

```bash
git add miniautogen/core/runtime/pipeline_runner.py tests/core/runtime/test_runner_recovery.py
git commit -m "feat: wire SessionRecovery into PipelineRunner for crash recovery"
```

**If Task Fails:**
1. **Circular import:** If `from miniautogen.core.runtime.recovery import SessionRecovery` causes a circular import, use `TYPE_CHECKING` guard instead:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from miniautogen.core.runtime.recovery import SessionRecovery
   ```
2. **Existing tests break on new parameter:** The `recovery` parameter defaults to `None`. If tests still break, check that the default works correctly.
3. **Recovery test fails with wrong state:** Verify the `recovered_state` variable is correctly passed to `pipeline.run()`.
4. **Rollback:** `git checkout -- miniautogen/core/runtime/pipeline_runner.py`

---

## Task 7: Store Contract Tests (Parametrized)

**Why:** A single parametrized test suite ensures ALL store implementations conform to the same contract, catching drift between InMemory and SQLAlchemy.

**Files:**
- Create: `tests/stores/test_store_contracts.py`

**Prerequisites:**
- Tasks 1-4 completed (all store methods exist)

**Step 1: Write the parametrized contract test suite**

Create `tests/stores/test_store_contracts.py`:

```python
"""Parametrized contract tests for all store implementations.

Every RunStore and CheckpointStore implementation must pass these tests.
This catches behavioral drift between InMemory and SQLAlchemy backends.
"""
from __future__ import annotations

from typing import Any

import pytest

from miniautogen.stores import (
    InMemoryCheckpointStore,
    InMemoryRunStore,
    SQLAlchemyCheckpointStore,
    SQLAlchemyRunStore,
)
from miniautogen.stores.checkpoint_store import CheckpointStore
from miniautogen.stores.run_store import RunStore


# --- Fixtures ---


@pytest.fixture
def in_memory_run_store() -> InMemoryRunStore:
    return InMemoryRunStore()


@pytest.fixture
async def sqlalchemy_run_store(tmp_path) -> SQLAlchemyRunStore:
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'contract-runs.db'}"
    )
    await store.init_db()
    return store


@pytest.fixture
def in_memory_checkpoint_store() -> InMemoryCheckpointStore:
    return InMemoryCheckpointStore()


@pytest.fixture
async def sqlalchemy_checkpoint_store(tmp_path) -> SQLAlchemyCheckpointStore:
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'contract-checkpoints.db'}"
    )
    await store.init_db()
    return store


# --- RunStore contract tests ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_run_store", "sqlalchemy_run_store"],
)
async def test_run_store_save_and_get(store_fixture: str, request) -> None:
    store: RunStore = request.getfixturevalue(store_fixture)
    await store.save_run("run-1", {"status": "started", "data": 42})

    result = await store.get_run("run-1")
    assert result is not None
    assert result["status"] == "started"
    assert result["data"] == 42


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_run_store", "sqlalchemy_run_store"],
)
async def test_run_store_get_nonexistent_returns_none(
    store_fixture: str, request
) -> None:
    store: RunStore = request.getfixturevalue(store_fixture)

    assert await store.get_run("nonexistent") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_run_store", "sqlalchemy_run_store"],
)
async def test_run_store_save_overwrites(
    store_fixture: str, request
) -> None:
    store: RunStore = request.getfixturevalue(store_fixture)
    await store.save_run("run-1", {"status": "started"})
    await store.save_run("run-1", {"status": "finished"})

    result = await store.get_run("run-1")
    assert result is not None
    assert result["status"] == "finished"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_run_store", "sqlalchemy_run_store"],
)
async def test_run_store_list_runs(store_fixture: str, request) -> None:
    store: RunStore = request.getfixturevalue(store_fixture)
    await store.save_run("run-1", {"status": "started"})
    await store.save_run("run-2", {"status": "finished"})

    runs = await store.list_runs()
    assert len(runs) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_run_store", "sqlalchemy_run_store"],
)
async def test_run_store_list_runs_with_filter(
    store_fixture: str, request
) -> None:
    store: RunStore = request.getfixturevalue(store_fixture)
    await store.save_run("run-1", {"status": "started"})
    await store.save_run("run-2", {"status": "finished"})

    runs = await store.list_runs(status="finished")
    assert len(runs) == 1
    assert runs[0]["status"] == "finished"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_run_store", "sqlalchemy_run_store"],
)
async def test_run_store_delete(store_fixture: str, request) -> None:
    store: RunStore = request.getfixturevalue(store_fixture)
    await store.save_run("run-1", {"status": "started"})

    assert await store.delete_run("run-1") is True
    assert await store.get_run("run-1") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_run_store", "sqlalchemy_run_store"],
)
async def test_run_store_delete_nonexistent(
    store_fixture: str, request
) -> None:
    store: RunStore = request.getfixturevalue(store_fixture)

    assert await store.delete_run("nonexistent") is False


# --- CheckpointStore contract tests ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_checkpoint_store", "sqlalchemy_checkpoint_store"],
)
async def test_checkpoint_store_save_and_get(
    store_fixture: str, request
) -> None:
    store: CheckpointStore = request.getfixturevalue(store_fixture)
    await store.save_checkpoint("run-1", {"step": 3, "data": [1, 2, 3]})

    result = await store.get_checkpoint("run-1")
    assert result is not None
    assert result["step"] == 3
    assert result["data"] == [1, 2, 3]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_checkpoint_store", "sqlalchemy_checkpoint_store"],
)
async def test_checkpoint_store_get_nonexistent_returns_none(
    store_fixture: str, request
) -> None:
    store: CheckpointStore = request.getfixturevalue(store_fixture)

    assert await store.get_checkpoint("nonexistent") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_checkpoint_store", "sqlalchemy_checkpoint_store"],
)
async def test_checkpoint_store_save_overwrites(
    store_fixture: str, request
) -> None:
    store: CheckpointStore = request.getfixturevalue(store_fixture)
    await store.save_checkpoint("run-1", {"step": 1})
    await store.save_checkpoint("run-1", {"step": 2})

    result = await store.get_checkpoint("run-1")
    assert result is not None
    assert result["step"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_checkpoint_store", "sqlalchemy_checkpoint_store"],
)
async def test_checkpoint_store_list(
    store_fixture: str, request
) -> None:
    store: CheckpointStore = request.getfixturevalue(store_fixture)
    await store.save_checkpoint("run-1", {"step": 1})
    await store.save_checkpoint("run-2", {"step": 2})

    checkpoints = await store.list_checkpoints()
    assert len(checkpoints) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_checkpoint_store", "sqlalchemy_checkpoint_store"],
)
async def test_checkpoint_store_list_with_filter(
    store_fixture: str, request
) -> None:
    store: CheckpointStore = request.getfixturevalue(store_fixture)
    await store.save_checkpoint("run-1", {"step": 1})
    await store.save_checkpoint("run-2", {"step": 2})

    checkpoints = await store.list_checkpoints(run_id="run-1")
    assert len(checkpoints) == 1
    assert checkpoints[0]["step"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_checkpoint_store", "sqlalchemy_checkpoint_store"],
)
async def test_checkpoint_store_delete(
    store_fixture: str, request
) -> None:
    store: CheckpointStore = request.getfixturevalue(store_fixture)
    await store.save_checkpoint("run-1", {"step": 1})

    assert await store.delete_checkpoint("run-1") is True
    assert await store.get_checkpoint("run-1") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "store_fixture",
    ["in_memory_checkpoint_store", "sqlalchemy_checkpoint_store"],
)
async def test_checkpoint_store_delete_nonexistent(
    store_fixture: str, request
) -> None:
    store: CheckpointStore = request.getfixturevalue(store_fixture)

    assert await store.delete_checkpoint("nonexistent") is False
```

**Step 2: Run the full contract suite**

Run: `poetry run pytest tests/stores/test_store_contracts.py -v`

**Expected output:**
```
tests/stores/test_store_contracts.py::test_run_store_save_and_get[in_memory_run_store] PASSED
tests/stores/test_store_contracts.py::test_run_store_save_and_get[sqlalchemy_run_store] PASSED
tests/stores/test_store_contracts.py::test_run_store_get_nonexistent_returns_none[in_memory_run_store] PASSED
tests/stores/test_store_contracts.py::test_run_store_get_nonexistent_returns_none[sqlalchemy_run_store] PASSED
... (all 32 parametrized tests PASSED)
```

**Step 3: Lint**

Run: `poetry run ruff check tests/stores/test_store_contracts.py`

**Expected output:** No errors.

**Step 4: Commit**

```bash
git add tests/stores/test_store_contracts.py
git commit -m "test: add parametrized contract tests for RunStore and CheckpointStore"
```

**If Task Fails:**
1. **Behavioral drift between InMemory and SQLAlchemy:** The contract test reveals a difference. Fix the implementation that deviates (usually the SQLAlchemy one).
2. **Async fixture issue:** If `sqlalchemy_run_store` fixture fails, ensure the fixture is marked with `@pytest.fixture` (not `@pytest_asyncio.fixture`). The `async def` + `@pytest.fixture` pattern works with pytest-asyncio 0.23+.
3. **Rollback:** `git checkout -- tests/stores/test_store_contracts.py`

---

## Task 8: Exports and api.py Update

**Why:** `SessionRecovery` must be importable from the public API. The runtime `__init__.py` and `api.py` need updating.

**Files:**
- Modify: `miniautogen/core/runtime/__init__.py` (lines 1-24)
- Modify: `miniautogen/api.py` (lines 1-105)
- Create: `tests/test_exports.py`

**Step 1: Write the verification test**

Create `tests/test_exports.py`:

```python
def test_session_recovery_importable_from_runtime() -> None:
    from miniautogen.core.runtime import SessionRecovery

    assert SessionRecovery is not None


def test_session_recovery_importable_from_api() -> None:
    from miniautogen.api import SessionRecovery

    assert SessionRecovery is not None
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/test_exports.py -v`

**Expected output:**
```
FAILED - ImportError: cannot import name 'SessionRecovery' from 'miniautogen.core.runtime'
```

**Step 3: Update runtime __init__.py**

In `miniautogen/core/runtime/__init__.py`, add the import and export.

Find:
```python
from .pipeline_runner import PipelineRunner
```

After it, add:
```python
from .recovery import SessionRecovery
```

Find in `__all__`:
```python
    "PipelineRunner",
```

After it, add:
```python
    "SessionRecovery",
```

**Step 4: Update api.py**

In `miniautogen/api.py`, add `SessionRecovery` to the runtime imports.

Find:
```python
from miniautogen.core.runtime import (
    AgenticLoopRuntime,
    CompositeRuntime,
    DeliberationRuntime,
    PipelineRunner,
    WorkflowRuntime,
)
```

Replace with:
```python
from miniautogen.core.runtime import (
    AgenticLoopRuntime,
    CompositeRuntime,
    DeliberationRuntime,
    PipelineRunner,
    SessionRecovery,
    WorkflowRuntime,
)
```

Find in `__all__`:
```python
    "PipelineRunner",
```

After it, add:
```python
    "SessionRecovery",
```

**Step 5: Run the verification test**

Run: `poetry run pytest tests/test_exports.py -v`

**Expected output:**
```
tests/test_exports.py::test_session_recovery_importable_from_runtime PASSED
tests/test_exports.py::test_session_recovery_importable_from_api PASSED
```

**Step 6: Run full test suite to check for regressions**

Run: `poetry run pytest tests/ -v --timeout=60`

**Expected output:** All tests pass. No import errors from the new exports.

**Step 7: Lint**

Run: `poetry run ruff check miniautogen/core/runtime/__init__.py miniautogen/api.py tests/test_exports.py`

**Expected output:** No errors.

**Step 8: Commit**

```bash
git add miniautogen/core/runtime/__init__.py miniautogen/api.py tests/test_exports.py
git commit -m "feat: export SessionRecovery from runtime and api modules"
```

**If Task Fails:**
1. **Circular import:** If importing `SessionRecovery` in `__init__.py` causes circular imports, check that `recovery.py` does not import from the runtime `__init__.py`. It should import directly from `stores/`.
2. **Rollback:** `git checkout -- miniautogen/core/runtime/__init__.py miniautogen/api.py`

---

## Task 9: Run Code Review

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

**Final verification after review:**

Run: `poetry run pytest tests/ -v --timeout=60`

**Expected output:** All tests pass.

Run: `poetry run ruff check miniautogen/ tests/`

**Expected output:** No lint errors.

---

## Summary of Files Changed

**New files:**
- `tests/stores/test_sqlalchemy_message_store.py` -- SQLAlchemy message store coverage
- `tests/stores/test_run_store_extended.py` -- RunStore list/delete tests
- `tests/stores/test_checkpoint_store_extended.py` -- CheckpointStore list/delete tests
- `tests/stores/test_sqlalchemy_store_extended.py` -- SQLAlchemy list/delete tests
- `miniautogen/core/runtime/recovery.py` -- SessionRecovery class
- `tests/core/runtime/test_recovery.py` -- SessionRecovery tests
- `tests/core/runtime/test_runner_recovery.py` -- PipelineRunner recovery integration tests
- `tests/stores/test_store_contracts.py` -- Parametrized contract tests
- `tests/test_exports.py` -- Export verification

**Modified files:**
- `miniautogen/stores/run_store.py` -- Added `list_runs`, `delete_run` abstract methods
- `miniautogen/stores/in_memory_run_store.py` -- Implemented `list_runs`, `delete_run`
- `miniautogen/stores/sqlalchemy_run_store.py` -- Implemented `list_runs`, `delete_run`
- `miniautogen/stores/checkpoint_store.py` -- Added `list_checkpoints`, `delete_checkpoint` abstract methods
- `miniautogen/stores/in_memory_checkpoint_store.py` -- Implemented `list_checkpoints`, `delete_checkpoint`
- `miniautogen/stores/sqlalchemy_checkpoint_store.py` -- Implemented `list_checkpoints`, `delete_checkpoint`
- `miniautogen/core/runtime/pipeline_runner.py` -- Added `recovery` parameter, checkpoint restore logic
- `miniautogen/core/runtime/__init__.py` -- Added `SessionRecovery` export
- `miniautogen/api.py` -- Added `SessionRecovery` export
