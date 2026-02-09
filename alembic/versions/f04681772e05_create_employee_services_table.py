"""Create employee_services table for per-employee pricing and capabilities

Revision ID: f04681772e05
Revises: 66f80216b6b3
Create Date: 2026-02-09 11:09:48.855697

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f04681772e05'
down_revision: Union[str, None] = '66f80216b6b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create employee_services junction table.

    Links employees to services they can perform, with optional
    per-employee pricing and commission rate overrides.
    Works for both main and addon services.
    """
    op.create_table(
        'employee_services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('custom_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('commission_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('duration_override', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('employee_id', 'service_id',
                           name='uq_employee_service_pair')
    )

    op.create_index('idx_employee_services_employee', 'employee_services', ['employee_id'])
    op.create_index('idx_employee_services_service', 'employee_services', ['service_id'])
    op.create_index('idx_employee_services_active', 'employee_services', ['is_active'])


def downgrade() -> None:
    """Drop employee_services table."""
    op.drop_table('employee_services')
