"""add messaging_service_sid to sms_settings

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-05-19
"""
from alembic import op

revision = 'r3s4t5u6v7w8'
down_revision = 'q2r3s4t5u6v7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE sms_settings
            ADD COLUMN IF NOT EXISTS messaging_service_sid VARCHAR(64)
    """)


def downgrade():
    op.execute("ALTER TABLE sms_settings DROP COLUMN IF EXISTS messaging_service_sid")
