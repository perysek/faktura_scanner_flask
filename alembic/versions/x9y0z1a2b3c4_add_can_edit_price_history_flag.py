"""Add can_edit_price_history flag to role_permissions

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-06-03

Adds a services-specific sub-permission to role_permissions:
  - can_edit_price_history : when TRUE (and the role has 'services' access),
    the role may delete/edit entries in the service price-history table.

Defaults to FALSE so existing rows are unchanged. Seeds TRUE for superuser
and admin on the 'services' module so price-history editing works out of the box.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'x9y0z1a2b3c4'
down_revision: Union[str, None] = 'w8x9y0z1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('role_permissions',
        sa.Column('can_edit_price_history', sa.Boolean(), nullable=False,
                  server_default='FALSE'))

    # Seed: built-in full-access roles get price-history editing on the services module
    op.execute("""
        UPDATE role_permissions rp
        SET can_edit_price_history = TRUE
        FROM roles r
        WHERE r.id = rp.role_id
          AND rp.module_name = 'services'
          AND r.name IN ('superuser', 'admin');
    """)


def downgrade() -> None:
    op.drop_column('role_permissions', 'can_edit_price_history')
