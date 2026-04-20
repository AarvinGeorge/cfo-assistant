"""
engine.py

SQLAlchemy engine + session factory for the FinSight control plane.

Role in project:
    Infrastructure layer. Owns the single SQLAlchemy engine pointing at
    `data/finsight.db` (or an override URL for tests). Other modules
    consume `get_session_factory()` to interact with the database.

Main parts:
    - create_engine_for_url(url): builds a SQLAlchemy Engine for the
      given SQLite URL with appropriate pragmas for the local-first
      single-writer use case.
    - make_session_factory(engine): wraps the engine in a sessionmaker
      bound to the engine; returns a callable producing Session objects.
    - get_engine() / get_session_factory(): module-level singletons that
      resolve to the production database from settings.
"""
from __future__ import annotations

from functools import lru_cache
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings


def create_engine_for_url(url: str) -> Engine:
    """Build an Engine. Enables WAL mode and foreign keys for SQLite."""
    engine = create_engine(url, future=True)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.close()
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@lru_cache
def get_engine() -> Engine:
    """Singleton engine pointing at data/finsight.db (or settings.database_url)."""
    settings = get_settings()
    url = getattr(settings, "database_url", "sqlite:///data/finsight.db")
    return create_engine_for_url(url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return make_session_factory(get_engine())
