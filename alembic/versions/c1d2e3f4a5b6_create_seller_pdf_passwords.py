"""Create seller_pdf_passwords table for encrypted PDF auto-unlock

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-03-28

Stores PDF passwords per seller, matched via seller_id or email_sender_pattern.
When an encrypted PDF arrives from a known email sender, the system looks up
the password and automatically unlocks the PDF for OCR processing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b0c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create seller_pdf_passwords table."""
    op.create_table(
        'seller_pdf_passwords',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('seller_id', sa.Integer(), nullable=True),
        sa.Column('email_sender_pattern', sa.String(255), nullable=True),
        sa.Column('pdf_password', sa.String(255), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['seller_id'], ['sellers.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_seller_pdf_passwords_seller_id', 'seller_pdf_passwords', ['seller_id'])
    op.create_index('ix_seller_pdf_passwords_email_pattern', 'seller_pdf_passwords', ['email_sender_pattern'])


def downgrade() -> None:
    """Drop seller_pdf_passwords table."""
    op.drop_index('ix_seller_pdf_passwords_email_pattern', table_name='seller_pdf_passwords')
    op.drop_index('ix_seller_pdf_passwords_seller_id', table_name='seller_pdf_passwords')
    op.drop_table('seller_pdf_passwords')
