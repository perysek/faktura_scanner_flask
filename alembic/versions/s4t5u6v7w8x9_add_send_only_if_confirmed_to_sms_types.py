"""add send_only_if_confirmed to sms_message_types

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-05-19
"""
from alembic import op

revision = 's4t5u6v7w8x9'
down_revision = 'r3s4t5u6v7w8'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE sms_message_types
            ADD COLUMN IF NOT EXISTS send_only_if_confirmed BOOLEAN NOT NULL DEFAULT FALSE
    """)


def downgrade():
    op.execute("ALTER TABLE sms_message_types DROP COLUMN IF EXISTS send_only_if_confirmed")
