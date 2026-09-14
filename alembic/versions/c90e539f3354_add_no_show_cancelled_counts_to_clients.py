"""add no_show_count and cancelled_count to clients

Revision ID: c90e539f3354
Revises: ea828d25e3db
Create Date: 2026-09-14

Persisted counters bumped whenever a client's appointment transitions to
'no_show'/'cancelled' (AppointmentBusinessService.apply_status_change_side_effects,
called from every status-mutation entry point: admin transition_status/
resolve_past_status, mobile employee actions, client SMS cancellation).
Backfilled from existing appointments so historical visits aren't undercounted.
"""
from alembic import op
import sqlalchemy as sa

revision = 'c90e539f3354'
down_revision = 'ea828d25e3db'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clients', sa.Column('no_show_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('clients', sa.Column('cancelled_count', sa.Integer(), nullable=False, server_default='0'))

    op.execute("""
        UPDATE clients c SET no_show_count = sub.cnt
        FROM (
            SELECT client_id, COUNT(*) AS cnt FROM appointments
            WHERE status = 'no_show' GROUP BY client_id
        ) sub
        WHERE sub.client_id = c.id
    """)
    op.execute("""
        UPDATE clients c SET cancelled_count = sub.cnt
        FROM (
            SELECT client_id, COUNT(*) AS cnt FROM appointments
            WHERE status = 'cancelled' GROUP BY client_id
        ) sub
        WHERE sub.client_id = c.id
    """)


def downgrade():
    op.drop_column('clients', 'cancelled_count')
    op.drop_column('clients', 'no_show_count')
