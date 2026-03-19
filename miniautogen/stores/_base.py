"""Shared SQLAlchemy declarative base for all SQL-backed stores."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
