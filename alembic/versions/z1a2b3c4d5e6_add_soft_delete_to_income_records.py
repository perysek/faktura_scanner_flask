"""Add soft delete columns (is_deleted, deleted_at) to income_records

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'z1a2b3c4d5e6'
down_revision: Union[str, None] = 'y0z1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('income_records', sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('income_records', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('idx_income_records_is_deleted', 'income_records', ['is_deleted'])


def downgrade() -> None:
    op.drop_index('idx_income_records_is_deleted', table_name='income_records')
    op.drop_column('income_records', 'deleted_at')
    op.drop_column('income_records', 'is_deleted')
