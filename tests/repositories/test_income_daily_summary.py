"""Tests for IncomeRepository.get_daily_summary() — backs the "Przychód: actual / expected"
footers on the calendar day/week/month views and the phone visit list.

SQL-shape tests against a mocked cursor (the suite has no live database): they pin the
status sets and the grouping key, which is where the business definition lives.
"""
from datetime import date
from unittest.mock import Mock, patch

REPO = 'repositories.appointments.income_repository'


def _conn(rows=()):
    cur = Mock()
    cur.fetchall.return_value = list(rows)
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


def _hidden(ids):
    return patch('config.admin_view.hidden_ids_to_exclude', return_value=ids)


def _run(app, employee_id=None, hidden=()):
    from repositories.appointments.income_repository import IncomeRepository
    conn, cur = _conn([{'day': date(2026, 10, 1), 'employee_id': 8, 'actual': 100, 'expected': 250}])
    with app.app_context(), _hidden(hidden), patch(f'{REPO}.get_db_connection', return_value=conn):
        rows = IncomeRepository().get_daily_summary(date(2026, 10, 1), date(2026, 10, 7), employee_id)
    return rows, cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])


class TestDailySummarySql:
    def test_returns_rows_from_cursor(self, app):
        rows, _, _ = _run(app)
        assert rows == [{'day': date(2026, 10, 1), 'employee_id': 8, 'actual': 100, 'expected': 250}]

    def test_groups_by_visit_date_not_payment_date(self, app):
        _, sql, _ = _run(app)
        assert 'GROUP BY a.appointment_date, a.employee_id' in sql
        assert 'payment_date' not in sql

    def test_actual_counts_only_completed_visits_net_amount(self, app):
        _, sql, _ = _run(app)
        actual = sql.split('AS actual')[0]
        assert "a.status = 'completed'" in actual
        assert 'ir.net_amount' in actual
        assert 'scheduled' not in actual

    def test_expected_is_completed_plus_active_and_nothing_else(self, app):
        _, sql, _ = _run(app)
        expected = sql.split('AS actual,')[1].split('AS expected')[0]
        assert "a.status IN ('confirmed', 'in_progress', 'scheduled')" in expected
        for excluded in ('cancelled', 'no_show', 'rescheduled'):
            assert excluded not in expected

    def test_soft_deleted_visits_and_income_are_ignored(self, app):
        _, sql, _ = _run(app)
        assert 'a.is_deleted = FALSE' in sql
        assert 'is_deleted = FALSE' in sql.split('LATERAL')[1].split(') ir')[0]

    def test_income_is_summed_per_visit_so_duplicates_cannot_double_count(self, app):
        _, sql, _ = _run(app)
        assert 'LEFT JOIN LATERAL' in sql
        assert 'SUM(net_amount)' in sql

    def test_params_are_dates_only_when_no_employee_and_admin_view(self, app):
        _, sql, params = _run(app)
        assert params == ['2026-10-01', '2026-10-07']
        assert 'a.employee_id = %s' not in sql

    def test_employee_filter_is_parameterised(self, app):
        _, sql, params = _run(app, employee_id=8)
        assert 'a.employee_id = %s' in sql
        assert params[:3] == ['2026-10-01', '2026-10-07', 8]

    def test_hidden_employee_exclusion_reaches_the_query(self, app):
        _, sql, params = _run(app, hidden=(9,))
        assert 'a.employee_id NOT IN' in sql
        assert params[-1] == 9
