"""SQLAlchemy-backed implementation of EffectJournal for durable persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from miniautogen.core.contracts.effect import (
    EffectDescriptor,
    EffectRecord,
    EffectStatus,
)
from miniautogen.stores._base import Base
from miniautogen.stores.effect_journal import EffectJournal


class DBEffectRecord(Base):
    """SQLAlchemy model for effect records with flattened descriptor fields."""

    __tablename__ = "effect_records"

    idempotency_key: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    error_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Flattened EffectDescriptor fields
    effect_type: Mapped[str] = mapped_column(String)
    tool_name: Mapped[str] = mapped_column(String)
    args_hash: Mapped[str] = mapped_column(String)
    run_id: Mapped[str] = mapped_column(String, index=True)
    step_id: Mapped[str] = mapped_column(String)



class SQLAlchemyEffectJournal(EffectJournal):
    """SQLAlchemy-backed effect journal for durable persistence."""

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

    async def register(self, record: EffectRecord) -> None:
        """Persist a new effect record. Overwrites existing by idempotency key."""
        async with self.async_session() as session:
            async with session.begin():
                existing = await session.get(DBEffectRecord, record.idempotency_key)
                if existing is None:
                    db_record = DBEffectRecord(
                        idempotency_key=record.idempotency_key,
                        status=record.status.value,
                        created_at=record.created_at,
                        completed_at=record.completed_at,
                        result_hash=record.result_hash,
                        error_info=record.error_info,
                        effect_type=record.descriptor.effect_type,
                        tool_name=record.descriptor.tool_name,
                        args_hash=record.descriptor.args_hash,
                        run_id=record.descriptor.run_id,
                        step_id=record.descriptor.step_id,
                    )
                    session.add(db_record)
                else:
                    existing.status = record.status.value
                    existing.created_at = record.created_at
                    existing.completed_at = record.completed_at
                    existing.result_hash = record.result_hash
                    existing.error_info = record.error_info
                    existing.effect_type = record.descriptor.effect_type
                    existing.tool_name = record.descriptor.tool_name
                    existing.args_hash = record.descriptor.args_hash
                    existing.run_id = record.descriptor.run_id
                    existing.step_id = record.descriptor.step_id

    async def get(self, idempotency_key: str) -> EffectRecord | None:
        """Fetch an effect record by its idempotency key."""
        async with self.async_session() as session:
            db_record = await session.get(DBEffectRecord, idempotency_key)
            if db_record is None:
                return None
            return self._to_domain(db_record)

    async def update_status(
        self,
        idempotency_key: str,
        status: EffectStatus,
        *,
        completed_at: datetime | None = None,
        result_hash: str | None = None,
        error_info: str | None = None,
    ) -> None:
        """Update the status of an existing effect record."""
        async with self.async_session() as session:
            async with session.begin():
                db_record = await session.get(DBEffectRecord, idempotency_key)
                if db_record is None:
                    return
                db_record.status = status.value
                if completed_at is not None:
                    db_record.completed_at = completed_at
                if result_hash is not None:
                    db_record.result_hash = result_hash
                if error_info is not None:
                    db_record.error_info = error_info

    async def list_by_run(
        self,
        run_id: str,
        *,
        status: EffectStatus | None = None,
    ) -> list[EffectRecord]:
        """List all effect records for a given run, optionally filtered by status."""
        async with self.async_session() as session:
            stmt = select(DBEffectRecord).where(DBEffectRecord.run_id == run_id)
            if status is not None:
                stmt = stmt.where(DBEffectRecord.status == status.value)
            result = await session.execute(stmt)
            return [self._to_domain(r) for r in result.scalars().all()]

    async def delete_by_run(self, run_id: str) -> int:
        """Delete all effect records for a given run. Returns count deleted."""
        async with self.async_session() as session:
            async with session.begin():
                # Count first
                count_stmt = (
                    select(func.count())
                    .select_from(DBEffectRecord)
                    .where(DBEffectRecord.run_id == run_id)
                )
                count_result = await session.execute(count_stmt)
                count = count_result.scalar_one()

                # Delete
                del_stmt = delete(DBEffectRecord).where(
                    DBEffectRecord.run_id == run_id,
                )
                await session.execute(del_stmt)
                return count

    @staticmethod
    def _to_domain(db: DBEffectRecord) -> EffectRecord:
        """Convert a DB row to a domain EffectRecord."""
        descriptor = EffectDescriptor(
            effect_type=db.effect_type,
            tool_name=db.tool_name,
            args_hash=db.args_hash,
            run_id=db.run_id,
            step_id=db.step_id,
        )
        return EffectRecord(
            idempotency_key=db.idempotency_key,
            descriptor=descriptor,
            status=EffectStatus(db.status),
            created_at=db.created_at.replace(tzinfo=timezone.utc)
            if db.created_at.tzinfo is None
            else db.created_at,
            completed_at=db.completed_at.replace(tzinfo=timezone.utc)
            if db.completed_at is not None and db.completed_at.tzinfo is None
            else db.completed_at,
            result_hash=db.result_hash,
            error_info=db.error_info,
        )
