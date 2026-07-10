"""Widok administratora coverage across AnalyticsRepository aggregates.

Every dashboard aggregate must exclude the superuser-linked employee's
appointments/income/rows when admin view is OFF, so salon-wide revenue, profit,
coverage and per-employee cards omit the owner. This test drives each aggregate
against a mocked DB with one hidden employee and asserts the emitted SQL carries a
NOT IN clause — a single missed method (or an f-string that didn't render the
inline clause) fails here. The admin-view-ON case asserts the clause disappears.
"""
from unittest.mock import Mock, patch
from datetime import date


class _Row(dict):
    """dict that yields 0 for any unset key, so aggregate post-processing that
    indexes result columns runs without a real DB."""
    def __missing__(self, key):
        return 0


def _conn():
    cur = Mock()
    cur.fetchone.return_value = _Row()
    cur.fetchall.return_value = []
    conn = Mock()
    conn.cursor.return_value = cur
    return conn, cur


# (method_name, args) — every cash-flow / appointment / employee aggregate.
_START, _END = date(2026, 1, 1), date(2026, 1, 31)
AGGREGATES = [
    ('get_revenue_summary', (_START, _END)),
    ('get_employee_performance', (_START, _END)),
    ('get_service_breakdown', (_START, _END)),
    ('get_client_metrics', (_START, _END)),
    ('get_occupancy_stats', (_START, _END)),
    ('get_peak_hours', (_START, _END)),
    ('get_service_price_analysis', (_START, _END)),
    ('get_revenue_trend', (_START, _END)),
    ('get_monthly_profit_trend', ()),
    ('get_top_clients', (_START, _END)),
    ('get_new_clients_monthly', ()),
    ('get_cancellation_rate_monthly', ()),
    ('get_avg_ticket_monthly', ()),
    ('get_service_category_mix_monthly', ()),
    ('get_invoice_cost_ratio_monthly', ()),
    ('get_employee_utilisation_monthly', ()),
    ('get_visit_frequency_distribution', ()),
    ('get_satisfaction_rating_monthly', ()),
]


def _run(app, method, args, hidden):
    from repositories.analytics.analytics_repository import AnalyticsRepository
    conn, cur = _conn()
    with app.app_context(), \
            patch('config.admin_view.hidden_ids_to_exclude', return_value=hidden), \
            patch('config.database.DatabaseConnection.get_connection', return_value=conn):
        getattr(AnalyticsRepository(), method)(*args)
    return [c.args[0] for c in cur.execute.call_args_list]


import pytest


class TestAdminViewCoverage:
    @pytest.mark.parametrize('method,args', AGGREGATES)
    def test_aggregate_excludes_hidden_when_off(self, app, method, args):
        sqls = _run(app, method, args, hidden=(9,))
        joined = '\n'.join(sqls)
        assert 'NOT IN (9)' in joined, f"{method} did not emit the exclusion clause"

    @pytest.mark.parametrize('method,args', AGGREGATES)
    def test_aggregate_unfiltered_when_admin_view_on(self, app, method, args):
        sqls = _run(app, method, args, hidden=())
        assert 'NOT IN' not in '\n'.join(sqls), \
            f"{method} emitted an exclusion clause under admin view ON"
