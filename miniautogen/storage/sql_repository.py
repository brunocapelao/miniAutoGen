from miniautogen.stores.sqlalchemy import Base, DBMessage, SQLAlchemyMessageStore

__all__ = ["Base", "DBMessage", "SQLAlchemyAsyncRepository"]


class SQLAlchemyAsyncRepository(SQLAlchemyMessageStore):
    """Legacy SQL repository kept as a compatibility facade."""
