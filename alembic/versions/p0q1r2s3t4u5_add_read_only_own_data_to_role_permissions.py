"""Add read_only and own_data flags to role_permissions

Revision ID: p0q1r2s3t4u5
Revises: o9p0q1r2s3t4
Create Date: 2026-05-13

Adds two new boolean flags to role_permissions:
  - read_only : when TRUE, the role may only view data for this module (no create/edit/delete)
  - own_data  : when TRUE, the role may only see its own records (not other employees' data)

Both default to FALSE so existing rows are unchanged (full access behaviour preserved).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'p0q1r2s3t4u5'
down_revision: Union[str, None] = 'o9p0q1r2s3t4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('role_permissions',
        sa.Column('read_only', sa.Boolean(), nullable=False, server_default='FALSE'))
    op.add_column('role_permissions',
        sa.Column('own_data', sa.Boolean(), nullable=False, server_default='FALSE'))


def downgrade() -> None:
    op.drop_column('role_permissions', 'own_data')
    op.drop_column('role_permissions', 'read_only')
