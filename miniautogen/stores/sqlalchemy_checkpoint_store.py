import json
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import DateTime, String, Text, select
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
        self,
        run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        async with self.async_session() as session:
            if run_id is not None:
                stmt = select(DBCheckpoint).where(
                    DBCheckpoint.run_id == run_id,
                )
            else:
                stmt = select(DBCheckpoint)
            result = await session.execute(stmt)
            return [
                cast(
                    dict[str, Any],
                    json.loads(cp.payload_json),
                )
                for cp in result.scalars().all()
            ]

    async def delete_checkpoint(self, run_id: str) -> bool:
        async with self.async_session() as session:
            async with session.begin():
                db_cp = await session.get(DBCheckpoint, run_id)
                if db_cp is None:
                    return False
                await session.delete(db_cp)
                return True
