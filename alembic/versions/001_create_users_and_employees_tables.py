"""Create users and employees tables for authentication and salon staff management

Revision ID: 001
Revises:
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
# Chained off the invoice-domain baseline (improvement #1). Was None (root);
# the baseline now creates invoices/sellers/audit_log/roles before the user/
# employee tables, so a fresh `alembic upgrade head` builds the whole schema.
down_revision: Union[str, None] = '000_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users and employees tables."""

    # Users table - Authentication accounts
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='receptionist'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.CheckConstraint("role IN ('superuser', 'admin', 'receptionist', 'stylist', 'accountant')", name='check_user_role')
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])

    # Employees table - Beauty salon staff
    op.create_table(
        'employees',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),  # Optional link to users table
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('position', sa.String(100), nullable=True),  # 'Stylist', 'Receptionist', 'Manager'
        sa.Column('employment_status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('hire_date', sa.Date(), nullable=True),
        sa.Column('termination_date', sa.Date(), nullable=True),

        # Compensation
        sa.Column('base_salary', sa.Numeric(10, 2), nullable=True),  # Monthly base salary
        sa.Column('commission_rate', sa.Numeric(5, 2), nullable=True),  # Percentage (e.g., 40.00 for 40%)

        # Skills & specializations (JSON stored as TEXT for SQLite compatibility)
        sa.Column('skills', sa.Text(), nullable=True),  # JSON: '{"Hair Color": 5, "Balayage": 4}' (skill: rating)
        sa.Column('specializations', sa.Text(), nullable=True),  # JSON: '["Bridal", "Extensions"]'

        # Schedule preferences (JSON stored as TEXT)
        sa.Column('work_schedule', sa.Text(), nullable=True),  # JSON: '{"mon": "9-17", "tue": "9-17", ...}'
        sa.Column('max_appointments_per_day', sa.Integer(), nullable=True, server_default='8'),

        # Metadata
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('photo_path', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('user_id'),  # One user can link to only one employee
        sa.CheckConstraint("employment_status IN ('active', 'on_leave', 'terminated')", name='check_employment_status')
    )
    op.create_index('idx_employees_user', 'employees', ['user_id'])
    op.create_index('idx_employees_status', 'employees', ['employment_status'])
    op.create_index('idx_employees_active', 'employees', ['is_active'])

    # Employee availability (recurring weekly schedule)
    op.create_table(
        'employee_availability',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),  # 0=Monday, 6=Sunday
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='1'),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.CheckConstraint('day_of_week BETWEEN 0 AND 6', name='check_day_of_week')
    )
    op.create_index('idx_availability_employee', 'employee_availability', ['employee_id'])

    # Employee time off / vacation
    op.create_table(
        'employee_time_off',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(100), nullable=True),  # 'Vacation', 'Sick Leave', 'Personal'
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),  # pending, approved, denied
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.CheckConstraint("status IN ('pending', 'approved', 'denied')", name='check_time_off_status')
    )
    op.create_index('idx_time_off_employee', 'employee_time_off', ['employee_id'])
    op.create_index('idx_time_off_dates', 'employee_time_off', ['start_date', 'end_date'])


def downgrade() -> None:
    """Drop users and employees tables."""
    op.drop_table('employee_time_off')
    op.drop_table('employee_availability')
    op.drop_table('employees')
    op.drop_table('users')
