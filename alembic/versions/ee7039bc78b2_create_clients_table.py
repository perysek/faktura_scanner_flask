"""create_clients_table

Revision ID: ee7039bc78b2
Revises: 001
Create Date: 2026-02-06 00:06:12.009890

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee7039bc78b2'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create clients table
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('preferences', sa.Text(), nullable=True),  # JSON stored as text
        sa.Column('first_visit_date', sa.Date(), nullable=True),
        sa.Column('last_visit_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for frequently searched fields
    op.create_index('ix_clients_phone', 'clients', ['phone'])
    op.create_index('ix_clients_email', 'clients', ['email'], unique=True)
    op.create_index('ix_clients_name', 'clients', ['last_name', 'first_name'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_clients_name', 'clients')
    op.drop_index('ix_clients_email', 'clients')
    op.drop_index('ix_clients_phone', 'clients')

    # Drop table
    op.drop_table('clients')
