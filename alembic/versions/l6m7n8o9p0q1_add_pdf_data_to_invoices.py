"""Add pdf_data BYTEA and pdf_filename TEXT to invoices for DB-side file storage

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-04-22

Stores the raw PDF/image bytes directly in the invoices table so that
uploaded files survive server restarts, re-deployments, and disk wipes on
cloud VPS instances (Vultr, DO, etc.) where the local filesystem is ephemeral.

Existing rows keep pdf_path for backward-compat; the view_pdf endpoint
falls back to the filesystem path when pdf_data is NULL.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'l6m7n8o9p0q1'
down_revision: Union[str, None] = 'k5l6m7n8o9p0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('invoices', sa.Column('pdf_data', sa.LargeBinary(), nullable=True))
    op.add_column('invoices', sa.Column('pdf_filename', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('invoices', 'pdf_filename')
    op.drop_column('invoices', 'pdf_data')
