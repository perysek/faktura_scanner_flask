"""Create absence_conflict_resolutions table

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-07-12

Audit trail for supervisor conflict-resolution actions (reassign / reschedule /
cancel) taken against appointments that conflict with a pending absence request.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'z1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'absence_conflict_resolutions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('absence_id', sa.Integer(), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=False),
        sa.Column('resolution_type', sa.String(20), nullable=False),
        sa.Column('previous_employee_id', sa.Integer(), nullable=True),
        sa.Column('new_employee_id', sa.Integer(), nullable=True),
        sa.Column('previous_date', sa.Date(), nullable=True),
        sa.Column('previous_start_time', sa.Time(), nullable=True),
        sa.Column('previous_end_time', sa.Time(), nullable=True),
        sa.Column('new_date', sa.Date(), nullable=True),
        sa.Column('new_start_time', sa.Time(), nullable=True),
        sa.Column('new_end_time', sa.Time(), nullable=True),
        sa.Column('cancellation_reason', sa.String(255), nullable=True),
        sa.Column('resolved_by_user_id', sa.Integer(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['absence_id'], ['employee_absences.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['previous_employee_id'], ['employees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['new_employee_id'], ['employees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.CheckConstraint(
            "resolution_type IN ('reassigned', 'rescheduled', 'cancelled')",
            name='check_resolution_type'),
    )
    op.create_index('idx_conflict_resolutions_absence', 'absence_conflict_resolutions',
                    ['absence_id'])
    op.create_index('idx_conflict_resolutions_appointment', 'absence_conflict_resolutions',
                    ['appointment_id'])


def downgrade() -> None:
    op.drop_index('idx_conflict_resolutions_appointment', table_name='absence_conflict_resolutions')
    op.drop_index('idx_conflict_resolutions_absence', table_name='absence_conflict_resolutions')
    op.drop_table('absence_conflict_resolutions')
