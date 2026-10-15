"""Create support tickets ("Zgłoś problem lub podziel się pomysłem") + 'support_tickets' module

Three new tables carry the user ↔ administrator conversation started from the
sidebar's phone button:

  support_tickets              one conversation (kind, area, status, priority,
                               the auto-captured technical context as JSONB)
  support_ticket_messages      its messages: user / admin / system events,
                               admin internal notes (is_internal)
  support_ticket_attachments   screenshots (PNG/JPEG/WebP bytes, ≤ 4 MB each)

…and the 'support_tickets' RBAC module (Poziomy dostępu → "Zgłoszenia — panel
obsługi"), the gate of the issues.my-way-solutions.com admin app. Seeded ON for
superuser only, OFF for every other role.

ADDITIVE ONLY — the legacy invoices-app (:8083) shares this database; nothing
that already exists is altered. Timestamps are naive UTC, the house convention
(see b7d3e9a1c4f2_create_visit_notes).

Revision ID: c5e8a2d4f6b1
Revises: a7c4e1f9b3d2
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c5e8a2d4f6b1'
down_revision: Union[str, None] = 'a7c4e1f9b3d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UTC_NOW = sa.text("(NOW() AT TIME ZONE 'UTC')")


def upgrade() -> None:
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('area', sa.String(40), nullable=False),
        sa.Column('area_label', sa.String(80), nullable=False),
        sa.Column('title', sa.String(140), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='new'),
        sa.Column('priority', sa.String(8), nullable=False, server_default='normal'),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('close_reason', sa.String(16), nullable=True),
        sa.Column('context', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=_UTC_NOW),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=_UTC_NOW),
        # What the OTHER side has to catch up on: a public admin message or a status
        # change bumps last_admin_activity_at, a user message bumps last_user_activity_at.
        sa.Column('last_user_activity_at', sa.TIMESTAMP(), nullable=False, server_default=_UTC_NOW),
        sa.Column('last_admin_activity_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('user_last_read_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('admin_last_read_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('first_response_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('resolved_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('closed_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint("kind IN ('problem', 'idea')", name='ck_support_tickets_kind'),
        sa.CheckConstraint(
            "status IN ('new', 'seen', 'in_progress', 'waiting_user', 'resolved', 'closed')",
            name='ck_support_tickets_status'),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name='ck_support_tickets_priority'),
        sa.CheckConstraint(
            "close_reason IS NULL OR close_reason IN ('done', 'confirmed', 'declined', 'duplicate')",
            name='ck_support_tickets_close_reason'),
    )
    op.create_index('idx_support_tickets_creator', 'support_tickets',
                    ['created_by', sa.text('updated_at DESC')])
    op.create_index('idx_support_tickets_status', 'support_tickets',
                    ['status', sa.text('updated_at DESC')])

    op.create_table(
        'support_ticket_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('author_kind', sa.String(8), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_internal', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
        # System rows only: what happened ('status', 'assigned', 'priority') + its details.
        sa.Column('event', sa.String(16), nullable=True),
        sa.Column('meta', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=_UTC_NOW),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint("author_kind IN ('user', 'admin', 'system')", name='ck_support_messages_author_kind'),
        sa.CheckConstraint('char_length(body) <= 5000', name='ck_support_messages_body_len'),
    )
    op.create_index('idx_support_messages_ticket', 'support_ticket_messages', ['ticket_id', 'created_at'])

    op.create_table(
        'support_ticket_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(120), nullable=False),
        sa.Column('mime', sa.String(32), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=_UTC_NOW),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['support_ticket_messages.id'], ondelete='CASCADE'),
        sa.CheckConstraint("mime IN ('image/png', 'image/jpeg', 'image/webp')", name='ck_support_attachments_mime'),
        sa.CheckConstraint('size_bytes BETWEEN 1 AND 4194304', name='ck_support_attachments_size'),
    )
    op.create_index('idx_support_attachments_ticket', 'support_ticket_attachments', ['ticket_id'])

    op.execute("""
        INSERT INTO role_permissions (role_id, module_name, has_access)
        SELECT r.id, 'support_tickets', (r.name = 'superuser')
        FROM roles r
        ON CONFLICT (role_id, module_name) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE module_name = 'support_tickets';")
    op.drop_index('idx_support_attachments_ticket', table_name='support_ticket_attachments')
    op.drop_table('support_ticket_attachments')
    op.drop_index('idx_support_messages_ticket', table_name='support_ticket_messages')
    op.drop_table('support_ticket_messages')
    op.drop_index('idx_support_tickets_status', table_name='support_tickets')
    op.drop_index('idx_support_tickets_creator', table_name='support_tickets')
    op.drop_table('support_tickets')
