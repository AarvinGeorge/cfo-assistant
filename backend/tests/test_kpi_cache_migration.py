"""
test_kpi_cache_migration.py

Verifies the workspace_kpi_cache table is created correctly by the
Alembic migration.

Role in project:
    Test suite — schema migration guard. Runs the full Alembic migration
    chain against a fresh temp SQLite file and inspects the resulting
    schema.

Main parts:
    - test_migration_creates_workspace_kpi_cache_table: confirms the table
      exists with the expected columns and composite primary key.
"""
import tempfile
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from backend.db.engine import create_engine_for_url


def test_migration_creates_workspace_kpi_cache_table():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        command.upgrade(cfg, "head")

        engine = create_engine_for_url(f"sqlite:///{db_path}")
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "workspace_kpi_cache" in tables

        cols = {c["name"] for c in inspector.get_columns("workspace_kpi_cache")}
        assert {"workspace_id", "kpi_key", "response", "citations", "computed_at"}.issubset(cols)

        # Primary key is composite
        pk = inspector.get_pk_constraint("workspace_kpi_cache")
        assert set(pk["constrained_columns"]) == {"workspace_id", "kpi_key"}
