"""add satisfaction_score to appointments

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'appointments',
        sa.Column(
            'satisfaction_score',
            sa.SmallInteger(),
            sa.CheckConstraint('satisfaction_score BETWEEN 1 AND 5',
                               name='chk_satisfaction_score_range'),
            nullable=True
        )
    )


def downgrade():
    op.drop_column('appointments', 'satisfaction_score')
