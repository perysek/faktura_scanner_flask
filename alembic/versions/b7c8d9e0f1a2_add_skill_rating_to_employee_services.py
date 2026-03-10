"""add skill_rating to employee_services

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'b7c8d9e0f1a2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'employee_services',
        sa.Column(
            'skill_rating',
            sa.SmallInteger(),
            sa.CheckConstraint('skill_rating BETWEEN 1 AND 5',
                               name='chk_es_skill_rating_range'),
            nullable=True
        )
    )


def downgrade():
    op.drop_column('employee_services', 'skill_rating')
