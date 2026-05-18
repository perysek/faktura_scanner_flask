"""add include_cancel_link to sms_message_types

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-05-19
"""
from alembic import op

revision = 't5u6v7w8x9y0'
down_revision = 's4t5u6v7w8x9'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE sms_message_types
            ADD COLUMN IF NOT EXISTS include_cancel_link BOOLEAN NOT NULL DEFAULT FALSE
    """)


def downgrade():
    op.execute("ALTER TABLE sms_message_types DROP COLUMN IF EXISTS include_cancel_link")
