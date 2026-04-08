"""Add 'pending' to appointments.status CHECK constraint

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-04-08

The original migration 0c648f58079b created check_appointment_status with 6 values,
omitting 'pending'. AppointmentStatus enum has 7 values. This migration aligns the
database constraint with the Python enum.
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'i3j4k5l6m7n8'
down_revision: Union[str, None] = 'h2i3j4k5l6m7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace 6-value status constraint with 7-value constraint including 'pending'."""
    # Drop old constraint (6 values: scheduled, confirmed, in_progress, completed, cancelled, no_show)
    op.execute(
        "ALTER TABLE appointments DROP CONSTRAINT IF EXISTS check_appointment_status"
    )
    # Add new constraint (7 values: adds 'pending')
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT chk_appointments_status_v2 "
        "CHECK (status IN ("
        "'scheduled', 'pending', 'confirmed', 'in_progress', "
        "'completed', 'cancelled', 'no_show'"
        "))"
    )


def downgrade() -> None:
    """Restore original 6-value constraint (removes 'pending')."""
    op.execute(
        "ALTER TABLE appointments DROP CONSTRAINT IF EXISTS chk_appointments_status_v2"
    )
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT check_appointment_status "
        "CHECK (status IN ("
        "'scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show'"
        "))"
    )
