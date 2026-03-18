"""Comprehensive tests for SQLAlchemy-backed stores and InMemoryCheckpointStore edge cases.

Covers all uncovered lines identified by coverage analysis:
- SQLAlchemyMessageStore: init_db, add_message, get_messages, remove_message
- SQLAlchemyCheckpointStore: list_checkpoints, delete_checkpoint
- SQLAlchemyRunStore: list_runs (with status filter), delete_run
- InMemoryCheckpointStore: list_checkpoints for nonexistent run_id
"""

from datetime import datetime

import pytest

from miniautogen.schemas import Message
from miniautogen.stores.in_memory_checkpoint_store import InMemoryCheckpointStore
from miniautogen.stores.sqlalchemy import SQLAlchemyMessageStore
from miniautogen.stores.sqlalchemy_checkpoint_store import SQLAlchemyCheckpointStore
from miniautogen.stores.sqlalchemy_run_store import SQLAlchemyRunStore


# ---------------------------------------------------------------------------
# SQLAlchemyMessageStore (asyncio-only — aiosqlite does not support trio)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_store_init_and_add(tmp_path):
    """Covers __init__ (lines 31-32), init_db (39-40), add_message (43-51)."""
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages.db'}",
    )
    await store.init_db()

    msg = Message(
        sender_id="agent-1",
        content="hello world",
        timestamp=datetime(2025, 1, 1, 12, 0, 0),
        additional_info={"key": "value"},
    )
    await store.add_message(msg)

    messages = await store.get_messages()
    assert len(messages) == 1
    assert messages[0].sender_id == "agent-1"
    assert messages[0].content == "hello world"
    assert messages[0].additional_info == {"key": "value"}


@pytest.mark.asyncio
async def test_message_store_get_messages_pagination(tmp_path):
    """Covers get_messages with limit and offset (lines 54-59)."""
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages_page.db'}",
    )
    await store.init_db()

    for i in range(5):
        msg = Message(
            sender_id=f"agent-{i}",
            content=f"message {i}",
            timestamp=datetime(2025, 1, 1, 12, i, 0),
        )
        await store.add_message(msg)

    # Fetch with limit
    messages = await store.get_messages(limit=2)
    assert len(messages) == 2
    assert messages[0].sender_id == "agent-0"
    assert messages[1].sender_id == "agent-1"

    # Fetch with offset
    messages = await store.get_messages(limit=2, offset=3)
    assert len(messages) == 2
    assert messages[0].sender_id == "agent-3"
    assert messages[1].sender_id == "agent-4"


@pytest.mark.asyncio
async def test_message_store_get_empty(tmp_path):
    """get_messages on an empty store returns an empty list."""
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages_empty.db'}",
    )
    await store.init_db()

    messages = await store.get_messages()
    assert messages == []


@pytest.mark.asyncio
async def test_message_store_no_additional_info(tmp_path):
    """Message with no additional_info serializes/deserializes correctly."""
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages_no_info.db'}",
    )
    await store.init_db()

    msg = Message(
        sender_id="agent-x",
        content="bare message",
        timestamp=datetime(2025, 6, 15, 8, 0, 0),
    )
    await store.add_message(msg)

    messages = await store.get_messages()
    assert len(messages) == 1
    assert messages[0].additional_info == {}


@pytest.mark.asyncio
async def test_message_store_remove_message(tmp_path):
    """Covers remove_message (lines 73-76)."""
    store = SQLAlchemyMessageStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'messages_remove.db'}",
    )
    await store.init_db()

    msg = Message(
        sender_id="agent-1",
        content="to be removed",
        timestamp=datetime(2025, 1, 1, 12, 0, 0),
    )
    await store.add_message(msg)

    messages = await store.get_messages()
    assert len(messages) == 1
    msg_id = messages[0].id

    await store.remove_message(msg_id)

    messages = await store.get_messages()
    assert len(messages) == 0


# ---------------------------------------------------------------------------
# SQLAlchemyCheckpointStore -- list_checkpoints & delete_checkpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpoint_store_list_all(tmp_path):
    """Covers list_checkpoints with run_id=None (lines 72-73)."""
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'cp_list.db'}",
    )
    await store.init_db()

    await store.save_checkpoint("run-1", {"step": 1})
    await store.save_checkpoint("run-2", {"step": 2})
    await store.save_checkpoint("run-3", {"step": 3})

    checkpoints = await store.list_checkpoints()
    assert len(checkpoints) == 3
    assert {"step": 1} in checkpoints
    assert {"step": 2} in checkpoints
    assert {"step": 3} in checkpoints


@pytest.mark.asyncio
async def test_checkpoint_store_list_by_run_id(tmp_path):
    """Covers list_checkpoints with a specific run_id (lines 67-71)."""
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'cp_list_by_id.db'}",
    )
    await store.init_db()

    await store.save_checkpoint("run-1", {"step": "a"})
    await store.save_checkpoint("run-2", {"step": "b"})

    result = await store.list_checkpoints(run_id="run-1")
    assert result == [{"step": "a"}]

    result = await store.list_checkpoints(run_id="nonexistent")
    assert result == []


@pytest.mark.asyncio
async def test_checkpoint_store_delete(tmp_path):
    """Covers delete_checkpoint -- both found and not-found paths (lines 84-90)."""
    store = SQLAlchemyCheckpointStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'cp_delete.db'}",
    )
    await store.init_db()

    await store.save_checkpoint("run-1", {"data": "x"})

    assert await store.delete_checkpoint("run-1") is True
    assert await store.get_checkpoint("run-1") is None

    # Deleting a nonexistent checkpoint returns False
    assert await store.delete_checkpoint("run-1") is False
    assert await store.delete_checkpoint("never-existed") is False


# ---------------------------------------------------------------------------
# SQLAlchemyRunStore -- list_runs & delete_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_store_list_all(tmp_path):
    """Covers list_runs without status filter (lines 68-74)."""
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs_list.db'}",
    )
    await store.init_db()

    await store.save_run("run-1", {"status": "finished", "result": "ok"})
    await store.save_run("run-2", {"status": "started"})
    await store.save_run("run-3", {"status": "finished", "result": "err"})

    runs = await store.list_runs()
    assert len(runs) == 3


@pytest.mark.asyncio
async def test_run_store_list_with_status_filter(tmp_path):
    """Covers list_runs with status filter (lines 75-78)."""
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs_status.db'}",
    )
    await store.init_db()

    await store.save_run("run-1", {"status": "finished"})
    await store.save_run("run-2", {"status": "started"})
    await store.save_run("run-3", {"status": "finished"})

    finished = await store.list_runs(status="finished")
    assert len(finished) == 2
    assert all(r["status"] == "finished" for r in finished)

    started = await store.list_runs(status="started")
    assert len(started) == 1


@pytest.mark.asyncio
async def test_run_store_list_with_limit(tmp_path):
    """Covers list_runs limit slicing (line 79)."""
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs_limit.db'}",
    )
    await store.init_db()

    for i in range(5):
        await store.save_run(f"run-{i}", {"status": "finished", "i": i})

    runs = await store.list_runs(limit=3)
    assert len(runs) == 3


@pytest.mark.asyncio
async def test_run_store_delete(tmp_path):
    """Covers delete_run -- both found and not-found paths (lines 82-88)."""
    store = SQLAlchemyRunStore(
        db_url=f"sqlite+aiosqlite:///{tmp_path / 'runs_delete.db'}",
    )
    await store.init_db()

    await store.save_run("run-1", {"status": "finished"})

    assert await store.delete_run("run-1") is True
    assert await store.get_run("run-1") is None

    # Deleting a nonexistent run returns False
    assert await store.delete_run("run-1") is False
    assert await store.delete_run("never-existed") is False


# ---------------------------------------------------------------------------
# InMemoryCheckpointStore -- edge cases
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_in_memory_checkpoint_load_nonexistent():
    """get_checkpoint returns None for a key that was never stored."""
    store = InMemoryCheckpointStore()
    assert await store.get_checkpoint("does-not-exist") is None


@pytest.mark.anyio
async def test_in_memory_checkpoint_list_specific_missing():
    """Covers list_checkpoints with a run_id that does not exist (lines 23-24)."""
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("run-1", {"data": "present"})

    result = await store.list_checkpoints(run_id="nonexistent")
    assert result == []


@pytest.mark.anyio
async def test_in_memory_checkpoint_list_specific_existing():
    """list_checkpoints with an existing run_id returns its payload."""
    store = InMemoryCheckpointStore()
    await store.save_checkpoint("run-1", {"data": "x"})

    result = await store.list_checkpoints(run_id="run-1")
    assert result == [{"data": "x"}]


@pytest.mark.anyio
async def test_in_memory_checkpoint_delete_nonexistent():
    """delete_checkpoint returns False when the key is missing."""
    store = InMemoryCheckpointStore()
    assert await store.delete_checkpoint("nope") is False
