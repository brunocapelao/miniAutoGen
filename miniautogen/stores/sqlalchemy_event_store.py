"""SQLAlchemy-backed implementation of EventStore for durable persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from miniautogen._json import dumps, loads
from miniautogen.core.contracts.events import ExecutionEvent
from miniautogen.stores._base import Base
from miniautogen.stores.event_store import EventStore


class DBEvent(Base):
    """SQLAlchemy model for execution events."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    index: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    payload_json: Mapped[str] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)


class SQLAlchemyEventStore(EventStore):
    """SQLAlchemy-backed event store for durable persistence."""

    def __init__(self, db_url: str) -> None:
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def append(self, run_id: str, event: ExecutionEvent) -> None:
        """Append an event to the log for the given run."""
        async with self.async_session() as session:
            async with session.begin():
                # Determine next index for this run
                count_stmt = (
                    select(func.count())
                    .select_from(DBEvent)
                    .where(DBEvent.run_id == run_id)
                )
                result = await session.execute(count_stmt)
                next_index = result.scalar_one()

                # Serialize payload
                payload_dict = dict(event.payload)
                payload_json = dumps(payload_dict)

                db_event = DBEvent(
                    run_id=run_id,
                    index=next_index,
                    event_type=event.type,
                    timestamp=event.timestamp,
                    payload_json=payload_json,
                    correlation_id=event.correlation_id,
                    scope=event.scope,
                )
                session.add(db_event)

    async def list_events(
        self,
        run_id: str,
        after_index: int = 0,
    ) -> list[ExecutionEvent]:
        """List events for a run, optionally starting after a given index."""
        async with self.async_session() as session:
            stmt = (
                select(DBEvent)
                .where(DBEvent.run_id == run_id, DBEvent.index >= after_index)
                .order_by(DBEvent.index)
            )
            result = await session.execute(stmt)
            return [self._to_domain(row) for row in result.scalars().all()]

    async def count_events(self, run_id: str) -> int:
        """Return the number of events stored for a given run."""
        async with self.async_session() as session:
            stmt = (
                select(func.count())
                .select_from(DBEvent)
                .where(DBEvent.run_id == run_id)
            )
            result = await session.execute(stmt)
            return result.scalar_one()

    @staticmethod
    def _to_domain(db: DBEvent) -> ExecutionEvent:
        """Convert a DB row to a domain ExecutionEvent."""
        payload_data: dict[str, Any] = loads(db.payload_json)
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
