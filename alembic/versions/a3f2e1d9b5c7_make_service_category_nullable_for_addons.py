"""Make service category nullable for addon services

Revision ID: a3f2e1d9b5c7
Revises: ba16fcdbb066
Create Date: 2026-02-23

Business rule change: category is required only for service_type='main'.
Addon services (service_type='addon') do not belong to any category.

SQLite does not support ALTER COLUMN, so batch_alter_table recreates the
table transparently.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f2e1d9b5c7'
down_revision: Union[str, None] = 'ba16fcdbb066'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_CATEGORIES = (
    "Strzyżenie", "Koloryzacja", "Stylizacja", "Trwała",
    "Pielęgnacja", "Masaż", "Manicure", "Pedicure", "Makijaż", "Inne"
)


def upgrade() -> None:
    """Allow NULL category for addon services."""
    cats = ", ".join(f"'{c}'" for c in VALID_CATEGORIES)
    new_check = f"(service_type = 'addon' OR category IN ({cats}))"

    with op.batch_alter_table('services', recreate='always') as batch_op:
        # Drop old NOT NULL + category-only CHECK, replace with nullable column
        # and a cross-column CHECK that allows NULL when service_type='addon'
        batch_op.alter_column(
            'category',
            existing_type=sa.String(100),
            nullable=True,
        )
        batch_op.drop_constraint('check_service_category', type_='check')
        batch_op.create_check_constraint(
            'check_service_category',
            new_check,
        )


def downgrade() -> None:
    """Restore NOT NULL category required for all services."""
    cats = ", ".join(f"'{c}'" for c in VALID_CATEGORIES)
    old_check = f"category IN ({cats})"

    with op.batch_alter_table('services', recreate='always') as batch_op:
        batch_op.drop_constraint('check_service_category', type_='check')
        batch_op.create_check_constraint('check_service_category', old_check)
        batch_op.alter_column(
            'category',
            existing_type=sa.String(100),
            nullable=False,
        )
