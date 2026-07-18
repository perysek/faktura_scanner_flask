"""add mobile_pin_hash to employees

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-07-18

Backs the employee-picker mobile app: each employee sets a short PIN on
first use (bcrypt-hashed, never stored in plaintext) instead of the app
relying on a per-appointment SMS token. NULL means "no PIN set yet".
"""
from alembic import op
import sqlalchemy as sa

revision = 'd5e6f7g8h9i0'
down_revision = 'c4d5e6f7g8h9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('employees', sa.Column('mobile_pin_hash', sa.String(length=60), nullable=True))


def downgrade():
    op.drop_column('employees', 'mobile_pin_hash')
