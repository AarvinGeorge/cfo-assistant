"""seed default user and workspace

Revision ID: 16ece49d77a9
Revises: 2379796cca48
Create Date: 2026-04-21 07:02:19.317452

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '16ece49d77a9'
down_revision: Union[str, Sequence[str], None] = '2379796cca48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "INSERT OR IGNORE INTO users (id, email, display_name, created_at) "
        "VALUES ('usr_default', NULL, 'Local User', CURRENT_TIMESTAMP)"
    )
    op.execute(
        "INSERT OR IGNORE INTO workspaces "
        "(id, owner_id, name, description, status, created_at, updated_at) "
        "VALUES ('wks_default', 'usr_default', 'Default Workspace', "
        "'Auto-created on first install', 'active', "
        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )
    op.execute(
        "INSERT OR IGNORE INTO workspace_members "
        "(workspace_id, user_id, role, added_at) "
        "VALUES ('wks_default', 'usr_default', 'owner', CURRENT_TIMESTAMP)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM workspace_members WHERE workspace_id='wks_default' AND user_id='usr_default'")
    op.execute("DELETE FROM workspaces WHERE id='wks_default'")
    op.execute("DELETE FROM users WHERE id='usr_default'")
