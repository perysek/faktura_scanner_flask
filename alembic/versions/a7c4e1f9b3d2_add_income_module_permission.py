"""Add 'income' module (Finanse → Przychody) to role_permissions

Seeds the new 'income' module for every existing role: access ON for
superuser and admin, OFF for everyone else (configurable afterwards on
Poziomy dostępu → Edytuj rolę → "Przychody").

ADDITIVE ONLY — the legacy invoices-app (:8083) shares this database and never
reads this module_name, and its role form upserts only its own modules.

Revision ID: a7c4e1f9b3d2
Revises: f3c7a1d9e2b4
Create Date: 2026-10-15
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a7c4e1f9b3d2'
down_revision: Union[str, None] = 'f3c7a1d9e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO role_permissions (role_id, module_name, has_access)
        SELECT r.id, 'income', (r.name IN ('superuser', 'admin'))
        FROM roles r
        ON CONFLICT (role_id, module_name) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE module_name = 'income';")
