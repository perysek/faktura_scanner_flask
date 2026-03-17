"""Add composite performance indexes for appointments and income queries

Revision ID: d5e6f7a8b9c0
Revises: a1b2c3d4e5f6
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for common query patterns.

    Existing indexes from migration 0c648f58079b:
      - idx_appointments_date_employee (appointment_date, employee_id)
      - idx_appointments_client (client_id)
      - idx_appointments_status (status)
      - idx_appointments_date (appointment_date)
      - idx_income_employee (employee_id)
      - idx_income_appointment (appointment_id)

    New indexes cover:
      - Status + date filtering (analytics queries)
      - Employee-first lookup for schedule views (N+1 fix)
    """
    # Composite: analytics frequently filters WHERE status = 'completed' AND date >= ...
    op.create_index(
        'idx_appointments_status_date',
        'appointments',
        ['status', 'appointment_date'],
    )

    # Employee-first composite: schedule view queries filter by employee_id then date
    op.create_index(
        'idx_appointments_employee_date',
        'appointments',
        ['employee_id', 'appointment_date'],
    )


def downgrade() -> None:
    op.drop_index('idx_appointments_employee_date', table_name='appointments')
    op.drop_index('idx_appointments_status_date', table_name='appointments')
