"""Add soft delete columns to services table

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-03-31

The e9f0a1b2c3d4 migration added is_deleted/deleted_at to invoices, appointments,
and clients. This migration extends the same pattern to the services table.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'h2i3j4k5l6m7'
down_revision: Union[str, None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('services', sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('services', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('idx_services_is_deleted', 'services', ['is_deleted'])

def downgrade() -> None:
    op.drop_index('idx_services_is_deleted', table_name='services')
    op.drop_column('services', 'deleted_at')
    op.drop_column('services', 'is_deleted')
