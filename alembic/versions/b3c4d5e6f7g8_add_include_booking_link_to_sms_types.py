"""add include_booking_link to sms_message_types

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-12
"""
from alembic import op

revision = 'b3c4d5e6f7g8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE sms_message_types
            ADD COLUMN IF NOT EXISTS include_booking_link BOOLEAN NOT NULL DEFAULT FALSE
    """)


def downgrade():
    op.execute("ALTER TABLE sms_message_types DROP COLUMN IF EXISTS include_booking_link")
