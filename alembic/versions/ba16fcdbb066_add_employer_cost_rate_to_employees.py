"""add employer cost rate to employees

Revision ID: ba16fcdbb066
Revises: 0c648f58079b
Create Date: 2026-02-09 23:36:53.253509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba16fcdbb066'
down_revision: Union[str, None] = '0c648f58079b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add employer_cost_rate column with default 0.22 (22% Polish ZUS/taxes/benefits)
    op.add_column('employees',
        sa.Column('employer_cost_rate', sa.Numeric(5, 4), nullable=False, server_default='0.22')
    )


def downgrade() -> None:
    op.drop_column('employees', 'employer_cost_rate')
