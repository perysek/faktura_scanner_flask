"""Remove hardcoded check_user_role constraint to support dynamic roles

The check_user_role constraint hardcoded 5 allowed role values in the users
table. Since the system supports dynamic role creation via the roles table,
this constraint prevented assigning newly created roles to users.
Validation is now done at the application layer (user_repository.py).

Revision ID: a9b8c7d6e5f4
Revises: f0a1b2c3d4e5
Create Date: 2026-03-23
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('check_user_role', 'users', type_='check')


def downgrade() -> None:
    op.create_check_constraint(
        'check_user_role',
        'users',
        "role IN ('superuser', 'admin', 'receptionist', 'stylist', 'accountant')"
    )
