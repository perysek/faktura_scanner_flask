"""Merge heads + replace global UNIQUE on invoice_number with partial unique index

Revision ID: g1h2i3j4k5l6
Revises: e9f0a1b2c3d4, c1d2e3f4a5b6
Create Date: 2026-03-31
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = ('e9f0a1b2c3d4', 'c1d2e3f4a5b6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Drop the global UNIQUE constraint on invoice_number.
    # PostgreSQL auto-names this 'invoices_invoice_number_key'.
    # Use IF EXISTS guard in case constraint name differs on some instances.
    op.execute("""
        DO $$
        BEGIN
            ALTER TABLE invoices DROP CONSTRAINT invoices_invoice_number_key;
        EXCEPTION
            WHEN undefined_object THEN NULL;
        END $$
    """)
    # Create partial unique index: only active invoices must be unique
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_invoice_number_active
        ON invoices (invoice_number)
        WHERE is_deleted = FALSE
    """)

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_invoices_invoice_number_active")
    op.create_unique_constraint(
        'invoices_invoice_number_key', 'invoices', ['invoice_number']
    )
