"""Create absence management tables (drop legacy employee_time_off)

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-05-09

Introduces:
  - absence_categories  : lookup table for dropdown (includes seeded rows)
  - employee_supervisors: many-to-many supervisor/employee hierarchy
  - employee_absences   : main absence request / manual absence records

Drops:
  - employee_time_off (unused — no repo, no UI references)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'n8o9p0q1r2s3'
down_revision: Union[str, None] = 'm7n8o9p0q1r2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── drop legacy (unused) table ────────────────────────────────────────────
    op.drop_index('idx_time_off_dates', table_name='employee_time_off')
    op.drop_index('idx_time_off_employee', table_name='employee_time_off')
    op.drop_table('employee_time_off')

    # ── absence_categories ────────────────────────────────────────────────────
    op.create_table(
        'absence_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('absence_full_day', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_absence_categories_name'),
    )
    op.create_index('idx_absence_categories_is_deleted', 'absence_categories', ['is_deleted'])

    # Seed required categories — L4 must be first (spec §tab #2)
    op.execute("""
        INSERT INTO absence_categories (name, description, absence_full_day) VALUES
        ('Zwolnienie lekarskie (L4)', 'Sick leave / L4', TRUE),
        ('Urlop wypoczynkowy', 'Annual leave', TRUE),
        ('Urlop na żądanie', 'On-demand leave', TRUE),
        ('Wyjście prywatne', 'Private time-slot absence', FALSE)
    """)

    # ── employee_supervisors ──────────────────────────────────────────────────
    op.create_table(
        'employee_supervisors',
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('supervisor_employee_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('employee_id', 'supervisor_employee_id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supervisor_employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.CheckConstraint('employee_id != supervisor_employee_id',
                           name='check_no_self_supervision'),
    )
    op.create_index('idx_supervisors_employee', 'employee_supervisors', ['employee_id'])
    op.create_index('idx_supervisors_supervisor', 'employee_supervisors',
                    ['supervisor_employee_id'])

    # ── employee_absences ─────────────────────────────────────────────────────
    op.create_table(
        'employee_absences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('date_from', sa.Date(), nullable=False),
        sa.Column('date_to', sa.Date(), nullable=False),   # = date_from for time-slot absences
        sa.Column('time_from', sa.Time(), nullable=True),
        sa.Column('time_to', sa.Time(), nullable=True),
        sa.Column('approver_id', sa.Integer(), nullable=True),  # employees.id of approver
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source', sa.String(20), nullable=False, server_default='request'),
        sa.Column('requested_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),   # users.id
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['category_id'], ['absence_categories.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['approver_id'], ['employees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name='check_absence_status'),
        sa.CheckConstraint(
            "source IN ('request', 'manual')",
            name='check_absence_source'),
        sa.CheckConstraint('date_to >= date_from', name='check_absence_date_order'),
        sa.CheckConstraint(
            '(time_from IS NULL AND time_to IS NULL) OR '
            '(time_from IS NOT NULL AND time_to IS NOT NULL AND time_to > time_from)',
            name='check_absence_time_order'),
        sa.CheckConstraint(
            "status != 'rejected' OR rejection_reason IS NOT NULL",
            name='check_rejection_reason_required'),
    )
    op.create_index('idx_absences_employee_dates', 'employee_absences',
                    ['employee_id', 'date_from', 'date_to'])
    op.create_index('idx_absences_status', 'employee_absences', ['status'])
    op.create_index('idx_absences_approver', 'employee_absences', ['approver_id'])
    op.create_index('idx_absences_is_deleted', 'employee_absences', ['is_deleted'])


def downgrade() -> None:
    # ── drop new tables in reverse dependency order ───────────────────────────
    op.drop_index('idx_absences_is_deleted', table_name='employee_absences')
    op.drop_index('idx_absences_approver', table_name='employee_absences')
    op.drop_index('idx_absences_status', table_name='employee_absences')
    op.drop_index('idx_absences_employee_dates', table_name='employee_absences')
    op.drop_table('employee_absences')

    op.drop_index('idx_supervisors_supervisor', table_name='employee_supervisors')
    op.drop_index('idx_supervisors_employee', table_name='employee_supervisors')
    op.drop_table('employee_supervisors')

    op.drop_index('idx_absence_categories_is_deleted', table_name='absence_categories')
    op.drop_table('absence_categories')

    # ── recreate legacy table ─────────────────────────────────────────────────
    op.create_table(
        'employee_time_off',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.CheckConstraint("status IN ('pending', 'approved', 'denied')",
                           name='check_time_off_status'),
    )
    op.create_index('idx_time_off_employee', 'employee_time_off', ['employee_id'])
    op.create_index('idx_time_off_dates', 'employee_time_off', ['start_date', 'end_date'])
