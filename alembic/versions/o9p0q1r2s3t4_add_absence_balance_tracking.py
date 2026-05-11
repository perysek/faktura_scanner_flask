"""Add absence balance tracking tables and columns

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-05-12

Introduces:
  - New columns on absence_categories  : is_tracked, count_period, resets_at,
                                          rolling_days, warning_threshold_pct, default_max_value
  - employee_absence_limits             : per-employee override of category default limit
  - absence_balance_adjustments        : manual balance corrections (positive or negative)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'o9p0q1r2s3t4'
down_revision: Union[str, None] = 'n8o9p0q1r2s3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── extend absence_categories ─────────────────────────────────────────────
    op.add_column('absence_categories',
        sa.Column('is_tracked', sa.Boolean(), nullable=False, server_default='FALSE'))
    op.add_column('absence_categories',
        sa.Column('count_period', sa.String(20), nullable=False, server_default='yearly'))
    op.add_column('absence_categories',
        sa.Column('resets_at', sa.Integer(), nullable=True, server_default='1'))
    op.add_column('absence_categories',
        sa.Column('rolling_days', sa.Integer(), nullable=True))
    op.add_column('absence_categories',
        sa.Column('warning_threshold_pct', sa.Float(), nullable=False, server_default='0.80'))
    op.add_column('absence_categories',
        sa.Column('default_max_value', sa.Float(), nullable=False, server_default='0.0'))

    op.create_check_constraint(
        'chk_count_period', 'absence_categories',
        "count_period IN ('yearly', 'monthly', 'rolling')")
    op.create_check_constraint(
        'chk_resets_at', 'absence_categories',
        'resets_at IS NULL OR (resets_at >= 1 AND resets_at <= 365)')
    op.create_check_constraint(
        'chk_warning_threshold', 'absence_categories',
        'warning_threshold_pct >= 0.0 AND warning_threshold_pct <= 1.0')
    op.create_check_constraint(
        'chk_default_max_value', 'absence_categories',
        'default_max_value >= 0.0')
    op.create_check_constraint(
        'chk_rolling_days', 'absence_categories',
        'rolling_days IS NULL OR rolling_days > 0')

    # Seed: enable tracking for Annual leave — 26 days/year
    op.execute("""
        UPDATE absence_categories
        SET is_tracked = TRUE,
            count_period = 'yearly',
            resets_at = 1,
            default_max_value = 26.0,
            warning_threshold_pct = 0.80
        WHERE name = 'Urlop wypoczynkowy'
    """)

    # Seed: On-demand leave — 4 days/year
    op.execute("""
        UPDATE absence_categories
        SET is_tracked = TRUE,
            count_period = 'yearly',
            resets_at = 1,
            default_max_value = 4.0,
            warning_threshold_pct = 0.80
        WHERE name = 'Urlop na żądanie'
    """)

    # Seed: Private time-slot — 16 hours/month
    op.execute("""
        UPDATE absence_categories
        SET is_tracked = TRUE,
            count_period = 'monthly',
            resets_at = 1,
            default_max_value = 16.0,
            warning_threshold_pct = 0.75
        WHERE name = 'Wyjście prywatne'
    """)

    # ── employee_absence_limits ───────────────────────────────────────────────
    op.create_table(
        'employee_absence_limits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('max_value', sa.Float(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='FALSE'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['absence_categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint('max_value >= 0.0', name='chk_limit_max_value'),
    )
    op.create_index(
        'uq_absence_limits_active', 'employee_absence_limits',
        ['employee_id', 'category_id'],
        unique=True,
        postgresql_where=sa.text('is_deleted = FALSE'),
    )
    op.create_index('idx_absence_limits_employee', 'employee_absence_limits', ['employee_id'])
    op.create_index('idx_absence_limits_category', 'employee_absence_limits', ['category_id'])

    # ── absence_balance_adjustments ───────────────────────────────────────────
    op.create_table(
        'absence_balance_adjustments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('delta_value', sa.Float(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('period_label', sa.Text(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='FALSE'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['absence_categories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint("length(trim(reason)) > 0", name='chk_adj_reason_not_empty'),
    )
    op.create_index('idx_balance_adj_employee', 'absence_balance_adjustments', ['employee_id'])
    op.create_index('idx_balance_adj_category', 'absence_balance_adjustments', ['category_id'])
    op.create_index('idx_balance_adj_deleted', 'absence_balance_adjustments', ['is_deleted'])


def downgrade() -> None:
    op.drop_index('idx_balance_adj_deleted', table_name='absence_balance_adjustments')
    op.drop_index('idx_balance_adj_category', table_name='absence_balance_adjustments')
    op.drop_index('idx_balance_adj_employee', table_name='absence_balance_adjustments')
    op.drop_table('absence_balance_adjustments')

    op.drop_index('idx_absence_limits_category', table_name='employee_absence_limits')
    op.drop_index('idx_absence_limits_employee', table_name='employee_absence_limits')
    op.drop_index('uq_absence_limits_active', table_name='employee_absence_limits')
    op.drop_table('employee_absence_limits')

    op.drop_constraint('chk_rolling_days', 'absence_categories', type_='check')
    op.drop_constraint('chk_default_max_value', 'absence_categories', type_='check')
    op.drop_constraint('chk_warning_threshold', 'absence_categories', type_='check')
    op.drop_constraint('chk_resets_at', 'absence_categories', type_='check')
    op.drop_constraint('chk_count_period', 'absence_categories', type_='check')

    op.drop_column('absence_categories', 'default_max_value')
    op.drop_column('absence_categories', 'warning_threshold_pct')
    op.drop_column('absence_categories', 'rolling_days')
    op.drop_column('absence_categories', 'resets_at')
    op.drop_column('absence_categories', 'count_period')
    op.drop_column('absence_categories', 'is_tracked')
