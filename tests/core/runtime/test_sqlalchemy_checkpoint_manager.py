"""Integration tests for SQLAlchemyCheckpointManager with ACID guarantees.

Tests verify that checkpoint + events are written atomically within
a single DB transaction, and that partial writes do not persist on failure.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import InMemoryEventSink
from miniautogen.stores._base import Base

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite async engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )


@pytest_asyncio.fixture
async def manager(db_engine, session_factory):
    """Create a SQLAlchemyCheckpointManager with shared engine."""
    from miniautogen.core.runtime.sqlalchemy_checkpoint_manager import (
        SQLAlchemyCheckpointManager,
    )

    return SQLAlchemyCheckpointManager(
        engine=db_engine,
        session_factory=session_factory,
    )


class TestSQLAlchemyCheckpointManagerImport:
    def test_import(self) -> None:
        from miniautogen.core.runtime.sqlalchemy_checkpoint_manager import (
            SQLAlchemyCheckpointManager,  # noqa: F401
        )

    def test_is_subclass_of_checkpoint_manager(self) -> None:
        from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
        from miniautogen.core.runtime.sqlalchemy_checkpoint_manager import (
            SQLAlchemyCheckpointManager,
        )

        assert issubclass(SQLAlchemyCheckpointManager, CheckpointManager)


class TestAtomicTransition:
    async def test_saves_checkpoint_and_events(self, manager) -> None:
        """atomic_transition persists both checkpoint and events in one transaction."""
        events = [
            ExecutionEvent(type="step_started", run_id="run-1"),
            ExecutionEvent(type="step_finished", run_id="run-1"),
        ]
        await manager.atomic_transition(
            "run-1",
            new_state={"result": 42},
            events=events,
            step_index=0,
        )

        result = await manager.get_last_checkpoint("run-1")
        assert result is not None
        state, step_index = result
        assert state == {"result": 42}
        assert step_index == 0

        stored_events = await manager.get_events("run-1")
        assert len(stored_events) == 2
        assert stored_events[0].type == "step_started"
        assert stored_events[1].type == "step_finished"

    async def test_get_last_checkpoint_returns_none_for_unknown(
        self, manager
    ) -> None:
        result = await manager.get_last_checkpoint("nonexistent")
        assert result is None

    async def test_get_events_returns_empty_for_unknown(self, manager) -> None:
        result = await manager.get_events("nonexistent")
        assert result == []

    async def test_multiple_transitions_update_checkpoint(self, manager) -> None:
        """Multiple transitions update the checkpoint and append events."""
        await manager.atomic_transition(
            "run-1",
            new_state={"s": 1},
            events=[],
            step_index=0,
        )
        await manager.atomic_transition(
            "run-1",
            new_state={"s": 2},
            events=[ExecutionEvent(type="ev1", run_id="run-1")],
            step_index=1,
        )

        result = await manager.get_last_checkpoint("run-1")
        assert result is not None
        state, step_index = result
        assert state == {"s": 2}
        assert step_index == 1

        stored_events = await manager.get_events("run-1")
        assert len(stored_events) == 1

    async def test_publishes_to_event_sink(self, db_engine, session_factory) -> None:
        """Events are published to the live event sink after DB commit."""
        from miniautogen.core.runtime.sqlalchemy_checkpoint_manager import (
            SQLAlchemyCheckpointManager,
        )

        sink = InMemoryEventSink()
        mgr = SQLAlchemyCheckpointManager(
            engine=db_engine,
            session_factory=session_factory,
            event_sink=sink,
        )
        events = [ExecutionEvent(type="test_ev", run_id="run-1")]
        await mgr.atomic_transition(
            "run-1",
            new_state={"x": 1},
            events=events,
            step_index=0,
        )

        assert len(sink.events) == 1
        assert sink.events[0].type == "test_ev"

    async def test_events_after_index(self, manager) -> None:
        """get_events with after_index filters correctly."""
        events_batch1 = [
            ExecutionEvent(type="ev0", run_id="run-1"),
            ExecutionEvent(type="ev1", run_id="run-1"),
        ]
        events_batch2 = [
            ExecutionEvent(type="ev2", run_id="run-1"),
        ]
        await manager.atomic_transition(
            "run-1",
            new_state={"s": 1},
            events=events_batch1,
            step_index=0,
        )
        await manager.atomic_transition(
            "run-1",
            new_state={"s": 2},
            events=events_batch2,
            step_index=1,
        )

        # Get events starting from index 2
        result = await manager.get_events("run-1", after_index=2)
        assert len(result) == 1
        assert result[0].type == "ev2"


class TestCrashSimulation:
    async def test_partial_write_does_not_persist(
        self, db_engine, session_factory
    ) -> None:
        """If the transaction fails mid-way, neither checkpoint nor events persist."""
        from miniautogen.core.runtime.sqlalchemy_checkpoint_manager import (
            SQLAlchemyCheckpointManager,
        )

        mgr = SQLAlchemyCheckpointManager(
            engine=db_engine,
            session_factory=session_factory,
        )

        # First, do a successful transition
        await mgr.atomic_transition(
            "run-crash",
            new_state={"s": 1},
            events=[],
            step_index=0,
        )

        # Simulate a crash by patching dumps to fail on the second call
        # (i.e., when serializing the event payload). The first call
        # serializes the checkpoint payload; the second serializes the event.
        import miniautogen.core.runtime.sqlalchemy_checkpoint_manager as mod

        original_dumps = mod.dumps
        call_count = 0

        def crashing_dumps(obj, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise RuntimeError("Simulated DB crash")
            return original_dumps(obj, **kwargs)

        with patch.object(mod, "dumps", crashing_dumps):
            with pytest.raises(RuntimeError, match="Simulated DB crash"):
                await mgr.atomic_transition(
                    "run-crash",
                    new_state={"s": 2},
                    events=[
                        ExecutionEvent(type="ev_crash", run_id="run-crash"),
                    ],
                    step_index=1,
                )

        # Verify: checkpoint should still show the OLD state (s=1, step_index=0)
        result = await mgr.get_last_checkpoint("run-crash")
        assert result is not None
        state, step_index = result
        assert state == {"s": 1}
        assert step_index == 0

        # Verify: no crash events persisted
        stored_events = await mgr.get_events("run-crash")
        assert len(stored_events) == 0

    async def test_sink_not_called_on_failure(
        self, db_engine, session_factory
    ) -> None:
        """Event sink should NOT be called if the DB transaction fails."""
        import miniautogen.core.runtime.sqlalchemy_checkpoint_manager as mod
        from miniautogen.core.runtime.sqlalchemy_checkpoint_manager import (
            SQLAlchemyCheckpointManager,
        )

        sink = InMemoryEventSink()
        mgr = SQLAlchemyCheckpointManager(
            engine=db_engine,
            session_factory=session_factory,
            event_sink=sink,
        )

        original_dumps = mod.dumps
        call_count = 0

        def crashing_dumps(obj, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise RuntimeError("Simulated DB crash")
            return original_dumps(obj, **kwargs)

        with patch.object(mod, "dumps", crashing_dumps):
            with pytest.raises(RuntimeError, match="Simulated DB crash"):
                await mgr.atomic_transition(
                    "run-crash",
                    new_state={"s": 1},
                    events=[
                        ExecutionEvent(type="ev_crash", run_id="run-crash"),
                    ],
                    step_index=0,
                )

        # Sink should have received zero events because the transaction failed
        assert len(sink.events) == 0
