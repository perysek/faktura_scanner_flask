"""Create visit_notes table ("Uwagi i zalecenia z wizyt")

A note belongs to one visit (appointment) and is written after the visit is
completed. Additive only: one new table, one partial index and a text-length
guard. The database is shared with the production salon app, so nothing that
already exists is altered.

Timestamps are naive UTC (`NOW() AT TIME ZONE 'UTC'`) — the house convention
used by audit_log.changed_at — so they never depend on the server's session time
zone. utils.timezone.to_local() converts them to Warsaw time for display.

Revision ID: b7d3e9a1c4f2
Revises: f4a8b2c9d1e7
Create Date: 2026-10-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7d3e9a1c4f2'
down_revision: Union[str, None] = 'f4a8b2c9d1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UTC_NOW = sa.text("(NOW() AT TIME ZONE 'UTC')")


def upgrade() -> None:
    op.create_table(
        'visit_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=False),
        sa.Column('note_text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=_UTC_NOW),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=_UTC_NOW),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        sa.Column('deleted_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        # Same bounds the API enforces; the DB refuses a blank or oversized note
        # even if a future code path forgets to.
        sa.CheckConstraint('char_length(btrim(note_text)) BETWEEN 1 AND 2000',
                           name='ck_visit_notes_text_len'),
    )
    # Serves "this visit's live notes, newest edit first" and the per-client joins.
    op.create_index(
        'idx_visit_notes_appointment', 'visit_notes',
        ['appointment_id', sa.text('updated_at DESC')],
        postgresql_where=sa.text('is_deleted = FALSE'),
    )


def downgrade() -> None:
    op.drop_index('idx_visit_notes_appointment', table_name='visit_notes')
    op.drop_table('visit_notes')
