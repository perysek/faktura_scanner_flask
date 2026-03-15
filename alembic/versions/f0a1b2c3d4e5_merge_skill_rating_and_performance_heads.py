"""Merge skill_rating and performance_indexes+soft_delete heads

Revision ID: f0a1b2c3d4e5
Revises: b7c8d9e0f1a2, e9f0a1b2c3d4
Create Date: 2026-03-15
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, None] = ('b7c8d9e0f1a2', 'e9f0a1b2c3d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
