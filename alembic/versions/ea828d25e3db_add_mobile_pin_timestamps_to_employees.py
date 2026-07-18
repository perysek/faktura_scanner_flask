"""add mobile_pin_set_at and mobile_last_login_at to employees

Revision ID: ea828d25e3db
Revises: d5e6f7g8h9i0
Create Date: 2026-07-18

Backs employee-edit-page PIN management: when the current PIN hash was set
(reset/change/first-use) and when the employee last authenticated with it in
the mobile app. NULL means "never".
"""
from alembic import op
import sqlalchemy as sa

revision = 'ea828d25e3db'
down_revision = 'd5e6f7g8h9i0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('employees', sa.Column('mobile_pin_set_at', sa.DateTime(), nullable=True))
    op.add_column('employees', sa.Column('mobile_last_login_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('employees', 'mobile_last_login_at')
    op.drop_column('employees', 'mobile_pin_set_at')
