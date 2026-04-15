"""Create service_categories table and seed default categories

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-04-15

Introduces a proper lookup table for service categories replacing the
hardcoded list in templates. Existing services keep their text category
values; the categories table seeds the same 10 values so nothing breaks.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'k5l6m7n8o9p0'
down_revision: Union[str, None] = 'j4k5l6m7n8o9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Categories that match the previously hardcoded list in templates
DEFAULT_CATEGORIES = [
    'Strzyżenie',
    'Koloryzacja',
    'Stylizacja',
    'Trwała',
    'Pielęgnacja',
    'Masaż',
    'Manicure',
    'Pedicure',
    'Makijaż',
    'Inne',
]


def upgrade() -> None:
    op.create_table(
        'service_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('additional_description', sa.Text(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='FALSE'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_service_categories_name'),
    )
    op.create_index('ix_service_categories_name', 'service_categories', ['name'])
    op.create_index('ix_service_categories_is_deleted', 'service_categories', ['is_deleted'])

    # Seed default categories matching the previously hardcoded template values
    op.execute(
        sa.text(
            "INSERT INTO service_categories (name) VALUES "
            + ", ".join(f"('{cat}')" for cat in DEFAULT_CATEGORIES)
        )
    )


def downgrade() -> None:
    op.drop_index('ix_service_categories_is_deleted', table_name='service_categories')
    op.drop_index('ix_service_categories_name', table_name='service_categories')
    op.drop_table('service_categories')
