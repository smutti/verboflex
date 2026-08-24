"""Synchronous PostgreSQL session boundary for API and CLI transactions."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from verboflex.core.config import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    """Build a pooled SQLAlchemy engine without opening a connection eagerly."""
    url = database_url or str(get_settings().database_url)
    return create_engine(url, pool_pre_ping=True)


engine = build_engine()
SessionFactory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_db_session() -> Iterator[Session]:
    """Yield one request-scoped session and roll it back on any failure."""
    with SessionFactory() as session:
        try:
            yield session
        except BaseException:
            session.rollback()
            raise
