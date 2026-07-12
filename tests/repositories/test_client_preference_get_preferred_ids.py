"""Tests for ClientPreferenceRepository.get_preferred_employee_ids() (Phase 0).

Unlike get_suggested_employee (single best match), this returns the FULL set of
matching preferred_employee_ids across whichever of service_id/category was
passed — used by the reassignment-candidate flagger to mark ALL of a client's
preferred stylists, not just the top one.
"""
from unittest.mock import Mock, patch


def _ctx_conn(rows):
    cur = Mock()
    cur.fetchall.return_value = rows
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


GDC = 'repositories.clients.client_preference_repository.get_db_connection'


class TestGetPreferredEmployeeIds:
    def test_service_id_match_returns_set(self, app):
        from repositories.clients.client_preference_repository import ClientPreferenceRepository
        conn, cur = _ctx_conn([{'preferred_employee_id': 3}, {'preferred_employee_id': 7}])
        with app.app_context(), patch(GDC, return_value=conn):
            result = ClientPreferenceRepository().get_preferred_employee_ids(1, service_id=10)
        assert result == {3, 7}

    def test_category_match_returns_set(self, app):
        from repositories.clients.client_preference_repository import ClientPreferenceRepository
        conn, cur = _ctx_conn([{'preferred_employee_id': 4}])
        with app.app_context(), patch(GDC, return_value=conn):
            result = ClientPreferenceRepository().get_preferred_employee_ids(1, category='hair')
        assert result == {4}

    def test_no_filters_returns_all_preferences_for_client(self, app):
        from repositories.clients.client_preference_repository import ClientPreferenceRepository
        conn, cur = _ctx_conn([{'preferred_employee_id': 3}, {'preferred_employee_id': 4}])
        with app.app_context(), patch(GDC, return_value=conn):
            result = ClientPreferenceRepository().get_preferred_employee_ids(1)
        assert result == {3, 4}

    def test_no_matches_returns_empty_set(self, app):
        from repositories.clients.client_preference_repository import ClientPreferenceRepository
        conn, cur = _ctx_conn([])
        with app.app_context(), patch(GDC, return_value=conn):
            result = ClientPreferenceRepository().get_preferred_employee_ids(1, service_id=10)
        assert result == set()
