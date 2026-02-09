"""Create service_addons table for addon-to-main service compatibility

Revision ID: 66f80216b6b3
Revises: b6ac628ea1f1
Create Date: 2026-02-09 11:09:17.187950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66f80216b6b3'
down_revision: Union[str, None] = 'b6ac628ea1f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create service_addons table.

    Defines which addon services are compatible with which main services.
    If an addon has NO rows here, it is compatible with ALL main services.
    """
    op.create_table(
        'service_addons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('addon_service_id', sa.Integer(), nullable=False),
        sa.Column('main_service_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['addon_service_id'], ['services.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['main_service_id'], ['services.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('addon_service_id', 'main_service_id',
                           name='uq_service_addons_pair')
    )

    op.create_index('idx_service_addons_addon', 'service_addons', ['addon_service_id'])
    op.create_index('idx_service_addons_main', 'service_addons', ['main_service_id'])


def downgrade() -> None:
    """Drop service_addons table."""
    op.drop_table('service_addons')
