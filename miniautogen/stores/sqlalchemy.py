from miniautogen._json import dumps, loads
from datetime import datetime
from typing import cast

from sqlalchemy import Column, DateTime, Integer, String, Text, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from miniautogen.schemas import Message
from miniautogen.stores.message_store import MessageStore


class Base(DeclarativeBase):
    pass


class DBMessage(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(String)
    message = Column(String)
    timestamp = Column(DateTime)
    additional_info = Column(Text)


class SQLAlchemyMessageStore(MessageStore):
    """SQLAlchemy-backed async message store."""

    def __init__(self, db_url: str = "sqlite+aiosqlite:///chat.db"):
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def add_message(self, message: Message) -> None:
        async with self.async_session() as session:
            async with session.begin():
                db_message = DBMessage(
                    sender_id=message.sender_id,
                    message=message.content,
                    timestamp=message.timestamp,
                    additional_info=dumps(message.additional_info),
                )
                session.add(db_message)

    async def get_messages(self, limit: int = 100, offset: int = 0) -> list[Message]:
        async with self.async_session() as session:
            stmt = select(DBMessage).order_by(DBMessage.timestamp).offset(offset).limit(limit)
            result = await session.execute(stmt)
            db_messages = result.scalars().all()

            return [
                Message(
                    id=cast(int | None, message.id),
                    sender_id=cast(str, message.sender_id),
                    content=cast(str, message.message),
                    timestamp=cast(datetime, message.timestamp),
                    additional_info=loads(cast(str, message.additional_info))
                    if message.additional_info
                    else {},
                )
                for message in db_messages
            ]

    async def remove_message(self, message_id: int) -> None:
        async with self.async_session() as session:
            async with session.begin():
                stmt = delete(DBMessage).where(DBMessage.id == message_id)
                await session.execute(stmt)
