"""Drop hardcoded check_service_category constraint from services table

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-04-24

The check_service_category constraint was created with a hardcoded list of 10
category strings. A proper service_categories lookup table now owns category
management, so any value stored in service_categories.name must be accepted.
The constraint was blocking inserts for any user-created category not in the
original hardcoded list.

Validation responsibility moves to the application layer: the API checks that
the submitted category name exists in service_categories before writing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'm7n8o9p0q1r2'
down_revision: Union[str, None] = 'l6m7n8o9p0q1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VALID_CATEGORIES = (
    "Strzyżenie", "Koloryzacja", "Stylizacja", "Trwała",
    "Pielęgnacja", "Masaż", "Manicure", "Pedicure", "Makijaż", "Inne"
)


def upgrade() -> None:
    op.drop_constraint('check_service_category', 'services', type_='check')


def downgrade() -> None:
    cats = ", ".join(f"'{c}'" for c in VALID_CATEGORIES)
    check_expr = f"(service_type = 'addon' OR category IN ({cats}))"
    op.create_check_constraint('check_service_category', 'services', check_expr)
