"""Create formy_zatrudnienia table and add FK column to employees

Revision ID: f1a2b3c4d5e6
Revises: c8d4e2f1a9b3
Create Date: 2026-03-09

Adds a lookup table for employment types (formy zatrudnienia) used in Polish
labour law (e.g. Umowa o pracę, B2B, Umowa zlecenie). Employees gain an
optional FK reference so a type can be assigned per employee.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'c8d4e2f1a9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create formy_zatrudnienia table and link it to employees."""
    op.create_table(
        'formy_zatrudnienia',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nazwa', sa.String(100), nullable=False),
        sa.Column('uwagi', sa.Text(), nullable=True),
        sa.Column('min_salary_required', sa.Boolean(), nullable=False, server_default='FALSE'),
        sa.Column('granted_salary', sa.Boolean(), nullable=False, server_default='FALSE'),
        sa.Column('commision_included', sa.Boolean(), nullable=False, server_default='FALSE'),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_formy_zatrudnienia_nazwa', 'formy_zatrudnienia', ['nazwa'])

    # Add optional FK on employees
    op.add_column('employees',
        sa.Column('forma_zatrudnienia_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_employees_forma_zatrudnienia',
        'employees', 'formy_zatrudnienia',
        ['forma_zatrudnienia_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    """Remove FK from employees and drop formy_zatrudnienia table."""
    op.drop_constraint('fk_employees_forma_zatrudnienia', 'employees', type_='foreignkey')
    op.drop_column('employees', 'forma_zatrudnienia_id')
    op.drop_index('ix_formy_zatrudnienia_nazwa', table_name='formy_zatrudnienia')
    op.drop_table('formy_zatrudnienia')
