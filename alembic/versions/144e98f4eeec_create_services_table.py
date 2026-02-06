"""Create services table for salon service catalog

Revision ID: 144e98f4eeec
Revises: ee7039bc78b2
Create Date: 2026-02-06 00:55:18.167104

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '144e98f4eeec'
down_revision: Union[str, None] = 'ee7039bc78b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create services table."""

    # Services table - Salon service catalog
    op.create_table(
        'services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='PLN'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),

        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("category IN ('Strzyżenie', 'Koloryzacja', 'Stylizacja', 'Trwała', 'Pielęgnacja', 'Masaż', 'Manicure', 'Pedicure', 'Makijaż', 'Inne')", name='check_service_category')
    )

    # Indexes
    op.create_index('idx_services_name', 'services', ['name'])
    op.create_index('idx_services_category', 'services', ['category'])
    op.create_index('idx_services_active', 'services', ['is_active'])
    op.create_index('idx_services_price', 'services', ['price'])


def downgrade() -> None:
    """Drop services table."""
    op.drop_table('services')
