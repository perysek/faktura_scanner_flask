"""Add data_correction module to role_permissions

Seeds the new 'data_correction' module for all existing roles.
Only 'superuser' gets access enabled by default; all others get FALSE.

Revision ID: b0c1d2e3f4a5
Revises: a9b8c7d6e5f4
Create Date: 2026-03-23
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'b0c1d2e3f4a5'
down_revision: Union[str, None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO role_permissions (role_id, module_name, has_access)
        SELECT r.id, 'data_correction', (r.name = 'superuser')
        FROM roles r
        ON CONFLICT (role_id, module_name) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE module_name = 'data_correction';")
