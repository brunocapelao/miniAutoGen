import json
from datetime import datetime, timezone
from typing import Any, cast

from sqlalchemy import DateTime, String, Text, select
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
