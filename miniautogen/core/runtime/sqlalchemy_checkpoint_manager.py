"""SQLAlchemyCheckpointManager: ACID atomic transitions backed by SQLAlchemy.

Subclass of CheckpointManager that wraps atomic_transition() in a real
DB transaction. Checkpoint save + event appends happen in a single
commit -- if any part fails, the entire transaction rolls back.

Uses the shared Base from stores/_base.py and the existing SQLAlchemy
table models (DBCheckpoint, DBEvent) from the store implementations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from miniautogen._json import dumps, loads
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.core.events.event_sink import EventSink
from miniautogen.core.runtime.checkpoint_manager import CheckpointManager
from miniautogen.stores.sqlalchemy_checkpoint_store import DBCheckpoint
from miniautogen.stores.sqlalchemy_event_store import DBEvent


class SQLAlchemyCheckpointManager(CheckpointManager):
    """CheckpointManager with true DB-level ACID atomicity.

    Uses a single SQLAlchemy session/transaction for both checkpoint
    and event writes. On failure, everything rolls back -- no partial
    state is persisted.

    Accepts an engine + session_factory so the caller controls
    connection pooling and can share the engine across stores.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
        event_sink: EventSink | None = None,
    ) -> None:
        # We bypass super().__init__() because we don't use the composition
        # pattern with separate stores. Instead we access the DB directly
        # within a single transaction for true ACID guarantees.
        self._engine = engine
        self._session_factory = session_factory
        self._event_sink = event_sink

    async def atomic_transition(
        self,
        run_id: str,
        *,
        new_state: Any,
        events: list[ExecutionEvent],
        step_index: int,
    ) -> None:
        """Save checkpoint + append events in a single DB transaction.

        If any part fails, the entire transaction rolls back.
        Events are published to the live sink only AFTER successful commit.
        """
        async with self._session_factory() as session:
            async with session.begin():
                # 1. Save/update checkpoint
                db_checkpoint = await session.get(DBCheckpoint, run_id)
                payload = {"state": new_state, "step_index": step_index}
                if db_checkpoint is None:
                    db_checkpoint = DBCheckpoint(
                        run_id=run_id,
                        payload_json=dumps(payload),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(db_checkpoint)
                else:
                    db_checkpoint.payload_json = dumps(payload)
                    db_checkpoint.updated_at = datetime.now(timezone.utc)

                # 2. Determine next event index for this run
                count_stmt = (
                    select(func.count())
                    .select_from(DBEvent)
                    .where(DBEvent.run_id == run_id)
                )
                result = await session.execute(count_stmt)
                next_index = result.scalar_one()

                # 3. Append events within the same transaction
                for i, event in enumerate(events):
                    payload_dict = dict(event.payload)
                    db_event = DBEvent(
                        run_id=run_id,
                        index=next_index + i,
                        event_type=event.type,
                        timestamp=event.timestamp,
                        payload_json=dumps(payload_dict),
                        correlation_id=event.correlation_id,
                        scope=event.scope,
                    )
                    session.add(db_event)

        # 4. Publish to live sink AFTER successful commit
        if self._event_sink is not None:
            for event in events:
                await self._event_sink.publish(event)

    async def get_last_checkpoint(
        self,
        run_id: str,
    ) -> tuple[Any, int] | None:
        """Load last checkpoint, return (state, step_index) or None."""
        async with self._session_factory() as session:
            stmt = select(DBCheckpoint).where(DBCheckpoint.run_id == run_id)
            result = await session.execute(stmt)
            db_checkpoint = result.scalar_one_or_none()
            if db_checkpoint is None:
                return None
            cp = loads(db_checkpoint.payload_json)
            return cp["state"], cp["step_index"]  # type: ignore[index]

    async def get_events(
        self,
        run_id: str,
        after_index: int = 0,
    ) -> list[ExecutionEvent]:
        """Retrieve events for a run."""
        async with self._session_factory() as session:
            stmt = (
                select(DBEvent)
                .where(DBEvent.run_id == run_id, DBEvent.index >= after_index)
                .order_by(DBEvent.index)
            )
            result = await session.execute(stmt)
            return [self._to_event(row) for row in result.scalars().all()]

    @staticmethod
    def _to_event(db: DBEvent) -> ExecutionEvent:
        """Convert a DB row to a domain ExecutionEvent."""
        payload_data: dict[str, Any] = loads(db.payload_json)  # type: ignore[assignment]
        ts = db.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ExecutionEvent(
            type=db.event_type,
            timestamp=ts,
            run_id=db.run_id if db.run_id else None,
            correlation_id=db.correlation_id,
            scope=db.scope,
            payload=payload_data,
        )
