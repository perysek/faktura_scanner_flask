"""Create service_price_history table + seed initial prices + service_prices module

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-06-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'w8x9y0z1a2b3'
down_revision: Union[str, None] = 'v7w8x9y0z1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── service_price_history ─────────────────────────────────────────────────
    op.create_table(
        'service_price_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('price', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='PLN'),
        sa.Column('effective_from', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('effective_to', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('change_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_sph_service_id', 'service_price_history', ['service_id'])
    op.create_index('idx_sph_effective_range', 'service_price_history',
                    ['service_id', sa.text('effective_from DESC')])
    # Partial UNIQUE index enforces the core invariant at the DB level:
    # at most one open (current) price row per service.
    op.create_index('idx_sph_open_entries', 'service_price_history', ['service_id'],
                    unique=True, postgresql_where=sa.text('effective_to IS NULL'))

    # ── seed: one open entry per existing service from its current price ──────
    op.execute("""
        INSERT INTO service_price_history
            (service_id, price, currency, effective_from, effective_to,
             changed_by, change_reason)
        SELECT s.id, s.price, COALESCE(s.currency, 'PLN'), NOW(), NULL,
               NULL, 'Migracja danych — wartość początkowa'
        FROM services s
    """)

    # ── seed: service_prices module permission for all roles ─────────────────
    # superuser/admin: full access; accountant: read-only (view history only).
    op.execute("""
        INSERT INTO role_permissions (role_id, module_name, has_access, read_only)
        SELECT r.id, 'service_prices',
               (r.name IN ('superuser', 'admin', 'accountant')),
               (r.name = 'accountant')
        FROM roles r
        ON CONFLICT (role_id, module_name) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE module_name = 'service_prices';")
    op.drop_index('idx_sph_open_entries', table_name='service_price_history')
    op.drop_index('idx_sph_effective_range', table_name='service_price_history')
    op.drop_index('idx_sph_service_id', table_name='service_price_history')
    op.drop_table('service_price_history')
