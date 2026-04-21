"""
test_seed_defaults_migration.py

Verifies the Alembic data migration seeds usr_default + wks_default
idempotently on a fresh SQLite file.
"""
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from backend.db.engine import create_engine_for_url


def _apply_all_migrations(db_path: Path) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")


def test_migration_seeds_default_user_and_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        _apply_all_migrations(db_path)

        engine = create_engine_for_url(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            users = conn.execute(text("SELECT id FROM users WHERE id='usr_default'")).fetchall()
            workspaces = conn.execute(text("SELECT id FROM workspaces WHERE id='wks_default'")).fetchall()
            members = conn.execute(
                text("SELECT workspace_id, user_id, role FROM workspace_members "
                     "WHERE workspace_id='wks_default' AND user_id='usr_default'")
            ).fetchall()

        assert len(users) == 1
        assert len(workspaces) == 1
        assert len(members) == 1
        assert members[0][2] == "owner"


def test_migration_is_idempotent():
    """Running upgrade twice should not fail or create duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        _apply_all_migrations(db_path)

        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
        command.downgrade(cfg, "-1")
        command.upgrade(cfg, "head")

        engine = create_engine_for_url(f"sqlite:///{db_path}")
        with engine.connect() as conn:
            users = conn.execute(text("SELECT COUNT(*) FROM users WHERE id='usr_default'")).scalar()
            workspaces = conn.execute(text("SELECT COUNT(*) FROM workspaces WHERE id='wks_default'")).scalar()

        assert users == 1, "Idempotency broken: duplicate user row"
        assert workspaces == 1, "Idempotency broken: duplicate workspace row"
