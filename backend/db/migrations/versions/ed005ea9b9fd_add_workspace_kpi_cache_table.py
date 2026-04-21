"""add workspace_kpi_cache table

Adds the workspace_kpi_cache table for 24-hour SQLite-backed caching of
the 6 KPI dashboard values, keyed by (workspace_id, kpi_key). Avoids
re-invoking the LangGraph orchestrator on every RightPanel mount.

Revision ID: ed005ea9b9fd
Revises: 16ece49d77a9
Create Date: 2026-04-21 08:04:39.167493

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ed005ea9b9fd'
down_revision: Union[str, Sequence[str], None] = '16ece49d77a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_kpi_cache",
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("kpi_key", sa.String(), nullable=False),
        sa.Column("response", sa.String(), nullable=False),
        sa.Column("citations", sa.String(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "kpi_key"),
    )


def downgrade() -> None:
    op.drop_table("workspace_kpi_cache")
