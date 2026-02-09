"""Create appointments, appointment_services, client_preferences, income_records tables

Revision ID: 0c648f58079b
Revises: f04681772e05
Create Date: 2026-02-09 11:10:11.614192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c648f58079b'
down_revision: Union[str, None] = 'f04681772e05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create core appointment system tables."""

    # --- client_preferences ---
    op.create_table(
        'client_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=True),
        sa.Column('service_category', sa.String(100), nullable=True),
        sa.Column('preferred_employee_id', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['preferred_employee_id'], ['employees.id'], ondelete='CASCADE'),
    )

    op.create_index('idx_client_prefs_client', 'client_preferences', ['client_id'])
    op.create_index('idx_client_prefs_employee', 'client_preferences', ['preferred_employee_id'])

    # --- appointments ---
    op.create_table(
        'appointments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='scheduled'),
        sa.Column('appointment_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('total_price', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('total_duration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('discount_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show')",
            name='check_appointment_status'
        )
    )

    op.create_index('idx_appointments_date_employee', 'appointments',
                    ['appointment_date', 'employee_id'])
    op.create_index('idx_appointments_client', 'appointments', ['client_id'])
    op.create_index('idx_appointments_status', 'appointments', ['status'])
    op.create_index('idx_appointments_date', 'appointments', ['appointment_date'])

    # --- appointment_services ---
    op.create_table(
        'appointment_services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('price_charged', sa.Numeric(10, 2), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('commission_rate', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('commission_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('is_addon', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('added_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='RESTRICT'),
    )

    op.create_index('idx_appt_services_appointment', 'appointment_services', ['appointment_id'])
    op.create_index('idx_appt_services_service', 'appointment_services', ['service_id'])
    op.create_index('idx_appt_services_addon', 'appointment_services', ['is_addon'])

    # --- income_records ---
    op.create_table(
        'income_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('total_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('discount_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('net_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('commission_total', sa.Numeric(10, 2), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('appointment_id', name='uq_income_appointment')
    )

    op.create_index('idx_income_date', 'income_records', ['payment_date'])
    op.create_index('idx_income_employee', 'income_records', ['employee_id'])
    op.create_index('idx_income_client', 'income_records', ['client_id'])
    op.create_index('idx_income_appointment', 'income_records', ['appointment_id'])


def downgrade() -> None:
    """Drop all appointment system tables in reverse dependency order."""
    op.drop_table('income_records')
    op.drop_table('appointment_services')
    op.drop_table('appointments')
    op.drop_table('client_preferences')
