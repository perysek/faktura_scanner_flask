"""Add service_type column to services table for main/addon distinction

Revision ID: b6ac628ea1f1
Revises: 144e98f4eeec
Create Date: 2026-02-09 11:08:42.696624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6ac628ea1f1'
down_revision: Union[str, None] = '144e98f4eeec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add service_type column to services table.

    SQLite cannot add CHECK constraints via ALTER TABLE,
    so we use batch_alter_table to recreate the table.
    """
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('service_type', sa.String(10), nullable=False, server_default='main')
        )

    op.create_index('idx_services_type', 'services', ['service_type'])


def downgrade() -> None:
    """Remove service_type column from services table."""
    op.drop_index('idx_services_type', 'services')

    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.drop_column('service_type')
