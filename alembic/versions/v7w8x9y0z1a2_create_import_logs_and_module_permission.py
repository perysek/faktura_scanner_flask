"""Create import_logs table + seed data_import module permission

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'v7w8x9y0z1a2'
down_revision: Union[str, None] = 'u6v7w8x9y0z1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── import_logs ───────────────────────────────────────────────────────────
    op.create_table(
        'import_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('finished_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('date_range_start', sa.Date(), nullable=False),
        sa.Column('date_range_end', sa.Date(), nullable=False),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('stats', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('session_status', sa.String(20), nullable=True),
        sa.Column('dry_run', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'],
                                ondelete='SET NULL'),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled')",
            name='check_import_logs_status'),
        sa.CheckConstraint(
            "session_status IS NULL OR session_status IN ('active', 'expired', 'missing')",
            name='check_import_logs_session_status'),
        sa.CheckConstraint(
            'date_range_end >= date_range_start',
            name='check_import_logs_date_order'),
    )
    op.create_index('idx_import_logs_started_at', 'import_logs',
                    [sa.text('started_at DESC')])
    op.create_index('idx_import_logs_status', 'import_logs', ['status'])

    # ── seed data_import module permission for all roles ──────────────────────
    op.execute("""
        INSERT INTO role_permissions (role_id, module_name, has_access)
        SELECT r.id, 'data_import', (r.name IN ('superuser', 'admin'))
        FROM roles r
        ON CONFLICT (role_id, module_name) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE module_name = 'data_import';")
    op.drop_index('idx_import_logs_status', table_name='import_logs')
    op.drop_index('idx_import_logs_started_at', table_name='import_logs')
    op.drop_table('import_logs')
