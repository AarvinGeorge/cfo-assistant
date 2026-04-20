"""
test_db_engine.py

Verifies the SQLAlchemy engine and session factory produce a working
in-memory SQLite connection suitable for tests.
"""
from sqlalchemy import text
from backend.db.engine import create_engine_for_url, make_session_factory


def test_create_engine_for_url_returns_working_engine():
    engine = create_engine_for_url("sqlite:///:memory:")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 as x")).scalar()
    assert result == 1


def test_session_factory_yields_usable_session():
    engine = create_engine_for_url("sqlite:///:memory:")
    SessionLocal = make_session_factory(engine)
    with SessionLocal() as session:
        result = session.execute(text("SELECT 42 as x")).scalar()
    assert result == 42
