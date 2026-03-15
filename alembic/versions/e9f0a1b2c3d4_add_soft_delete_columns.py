"""Add soft delete columns (is_deleted, deleted_at) to invoices, appointments, clients

Revision ID: e9f0a1b2c3d4
Revises: d5e6f7a8b9c0
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e9f0a1b2c3d4'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ['invoices', 'appointments', 'clients']


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False))
        op.add_column(table, sa.Column('deleted_at', sa.DateTime(), nullable=True))
        op.create_index(f'idx_{table}_is_deleted', table, ['is_deleted'])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_index(f'idx_{table}_is_deleted', table_name=table)
        op.drop_column(table, 'deleted_at')
        op.drop_column(table, 'is_deleted')
