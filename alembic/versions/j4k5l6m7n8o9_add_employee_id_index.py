"""Add single-column employee_id index on appointments for SCAL-01

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'j4k5l6m7n8o9'
down_revision: Union[str, None] = 'i3j4k5l6m7n8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add single-column index on appointments.employee_id.

    All indexes satisfying SCAL-01 requirement (including prior migrations):

    From migration 0c648f58079b:
      - idx_appointments_date_employee (appointment_date, employee_id)
      - idx_appointments_status        (status)
      - idx_appointments_date          (appointment_date)
      - idx_income_appointment         (appointment_id)  [on income_records]

    From migration d5e6f7a8b9c0:
      - idx_appointments_status_date   (status, appointment_date)
      - idx_appointments_employee_date (employee_id, appointment_date)

    Added here (SCAL-01 gap):
      - idx_appointments_employee_id   (employee_id)
        Covers standalone WHERE employee_id = %s queries that do not filter
        by date, for which the composite index requires a full index scan.
    """
    op.create_index(
        'idx_appointments_employee_id',
        'appointments',
        ['employee_id'],
    )


def downgrade() -> None:
    op.drop_index('idx_appointments_employee_id', table_name='appointments')
