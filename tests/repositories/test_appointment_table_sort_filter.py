"""Tests for server-side sort + column-filter in AppointmentRepository.get_latest.

The superadmin table editor used to sort/filter only the rows already loaded in the
browser. get_latest now applies sort + per-column filters in SQL across the whole
dataset (then paginates), so each page is a slice of the fully sorted+filtered set.

These tests assert the generated SQL and parameter ordering — including the
sort-column whitelist (no raw user input in ORDER BY), the label-aware status
filter, the service_name EXISTS subquery, and the COUNT(*) OVER() total.
"""
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_appt_db():
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    mock_conn.cursor.return_value = mock_cursor
    mock_cm = MagicMock()
    mock_cm.__enter__ = Mock(return_value=mock_conn)
    mock_cm.__exit__ = Mock(return_value=False)
    with patch('repositories.appointments.appointment_repository.get_db_connection',
               return_value=mock_cm):
        yield mock_cursor


def _call(cursor):
    return cursor.execute.call_args[0]


class TestSortWhitelist:
    def test_default_sort_unchanged(self, mock_appt_db):
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(100, 0)
        sql = _call(mock_appt_db)[0]
        assert 'ORDER BY a.appointment_date DESC, a.start_time DESC' in sql

    def test_whitelisted_sort_column_applied(self, mock_appt_db):
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(100, 0, sort_col='total_price', sort_dir='asc')
        sql = _call(mock_appt_db)[0]
        assert 'ORDER BY a.total_price ASC' in sql
        assert 'a.id DESC' in sql  # deterministic tiebreaker for stable pagination

    def test_unknown_sort_column_falls_back_to_default(self, mock_appt_db):
        # An attacker-supplied / unknown column must NOT reach the SQL.
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(100, 0, sort_col='id; DROP TABLE appointments')
        sql = _call(mock_appt_db)[0]
        assert 'DROP TABLE' not in sql
        assert 'ORDER BY a.appointment_date DESC, a.start_time DESC' in sql

    def test_client_name_sort_uses_concat_expr(self, mock_appt_db):
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(100, 0, sort_col='client_name', sort_dir='desc')
        sql = _call(mock_appt_db)[0]
        assert "ORDER BY (c.first_name || ' ' || c.last_name) DESC" in sql


class TestColumnFilters:
    def test_simple_filter_adds_ilike_and_param(self, mock_appt_db):
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(100, 0, filters={'client_name': 'kowal'})
        sql, params = _call(mock_appt_db)
        assert "(c.first_name || ' ' || c.last_name) ILIKE %s" in sql
        assert '%kowal%' in params
        # params end with limit, offset (execute receives a tuple)
        assert tuple(params[-2:]) == (100, 0)

    def test_status_filter_matches_label(self, mock_appt_db):
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(100, 0, filters={'status': 'zakon'})
        sql, params = _call(mock_appt_db)
        assert 'zakonczona' in sql        # Polish label mapping present
        assert "a.status ILIKE %s" in sql
        assert params.count('%zakon%') == 2  # raw + label comparison

    def test_service_name_filter_uses_exists_subquery(self, mock_appt_db):
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(100, 0, filters={'service_name': 'strzy'})
        sql, params = _call(mock_appt_db)
        assert 'EXISTS (SELECT 1 FROM appointment_services aps2' in sql
        assert 's2.name ILIKE %s' in sql
        assert '%strzy%' in params

    def test_filter_param_order_matches_sql(self, mock_appt_db):
        # employee/status come first, then column filters, then limit/offset.
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(
            50, 10, status='completed',
            filters={'id': '7', 'notes': 'vip'})
        sql, params = _call(mock_appt_db)
        # global status first, then id filter, then notes filter, then limit/offset
        assert params[0] == 'completed'
        assert '%7%' in params and '%vip%' in params
        assert tuple(params[-2:]) == (50, 10)


class TestTotalCount:
    def test_window_count_present(self, mock_appt_db):
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(100, 0)
        sql = _call(mock_appt_db)[0]
        assert 'COUNT(*) OVER() AS total_count' in sql

    def test_is_deleted_filter_retained(self, mock_appt_db):
        from repositories.appointments.appointment_repository import AppointmentRepository
        AppointmentRepository().get_latest(100, 0, sort_col='status',
                                           filters={'client_name': 'x'})
        sql = _call(mock_appt_db)[0]
        assert 'a.is_deleted = FALSE' in sql
