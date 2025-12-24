from typing import List, Optional
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Text, select, delete
from sqlalchemy.ext.declarative import declarative_base
from miniautogen.schemas import Message
from miniautogen.storage.repository import ChatRepository

Base = declarative_base()

class DBMessage(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(String)
    message = Column(String)
    timestamp = Column(DateTime)
    additional_info = Column(Text)

class SQLAlchemyAsyncRepository(ChatRepository):
    def __init__(self, db_url: str = "sqlite+aiosqlite:///chat.db"):
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self):
        """Creates tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def add_message(self, message: Message) -> None:
        async with self.async_session() as session:
            async with session.begin():
                db_msg = DBMessage(
                    sender_id=message.sender_id,
                    message=message.content,
                    timestamp=message.timestamp,
                    additional_info=json.dumps(message.additional_info)
                )
                session.add(db_msg)
                # After commit, db_msg.id is populated

            # Update the original Pydantic model ID if needed,
            # though usually we query back.

    async def get_messages(self, limit: int = 100, offset: int = 0) -> List[Message]:
        async with self.async_session() as session:
            stmt = select(DBMessage).order_by(DBMessage.timestamp).offset(offset).limit(limit)
            result = await session.execute(stmt)
            db_messages = result.scalars().all()

            return [
                Message(
                    id=m.id,
                    sender_id=m.sender_id,
                    content=m.message,
                    timestamp=m.timestamp,
                    additional_info=json.loads(m.additional_info) if m.additional_info else {}
                )
                for m in db_messages
            ]

    async def remove_message(self, message_id: int) -> None:
        async with self.async_session() as session:
            async with session.begin():
                stmt = delete(DBMessage).where(DBMessage.id == message_id)
                await session.execute(stmt)
