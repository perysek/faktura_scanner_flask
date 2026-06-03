"""Add can_send_sms flag to role_permissions

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-06-03

Adds an appointments-specific sub-permission to role_permissions:
  - can_send_sms : when TRUE (and the role has 'appointments' access),
    the role may use the manual "Wyślij SMS" button on the appointment
    details page and the bulk SMS send endpoints.

Defaults to FALSE so existing rows are unchanged. Seeds TRUE for superuser
and admin on the 'appointments' module so they keep SMS sending out of the
box; every other role loses the manual SMS button until an admin enables
the toggle in the role editor. Mirrors the can_edit_price_history flag.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'y0z1a2b3c4d5'
down_revision: Union[str, None] = 'x9y0z1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('role_permissions',
        sa.Column('can_send_sms', sa.Boolean(), nullable=False,
                  server_default='FALSE'))

    # Seed: built-in full-access roles keep manual SMS sending on appointments
    op.execute("""
        UPDATE role_permissions rp
        SET can_send_sms = TRUE
        FROM roles r
        WHERE r.id = rp.role_id
          AND rp.module_name = 'appointments'
          AND r.name IN ('superuser', 'admin');
    """)


def downgrade() -> None:
    op.drop_column('role_permissions', 'can_send_sms')
