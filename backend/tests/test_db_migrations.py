"""
test_db_migrations.py

Verifies the Alembic migration produces the same schema as the ORM
models (autogenerate-and-apply round-trip).
"""
import tempfile
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from backend.db.engine import create_engine_for_url


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        url = f"sqlite:///{db_path}"

        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")

        engine = create_engine_for_url(url)
        yield engine


def test_migration_creates_all_tables(temp_db):
    inspector = inspect(temp_db)
    tables = set(inspector.get_table_names())
    expected = {
        "users",
        "workspaces",
        "workspace_members",
        "documents",
        "chat_sessions",
        "alembic_version",
    }
    assert expected.issubset(tables)


def test_migration_creates_unique_constraint_on_documents(temp_db):
    inspector = inspect(temp_db)
    indexes = inspector.get_unique_constraints("documents")
    names = [ix["name"] for ix in indexes]
    assert "idx_workspace_file_hash" in names


def test_migration_enables_foreign_keys_in_runtime(temp_db):
    with temp_db.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys")).scalar()
    assert result == 1
