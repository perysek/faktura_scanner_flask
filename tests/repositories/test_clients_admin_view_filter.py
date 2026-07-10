"""Widok administratora filtering across the client-facing repositories.

Client *records* stay listed, but their derived numbers (visit counts, last/next
visit, monthly trends), their preference rows, and their visit history must all
exclude the owner's appointments while admin view is OFF.
"""
from unittest.mock import Mock, patch


def _ctx_conn():
    """get_db_connection()-style context-manager mock (client_preference / appointment)."""
    cur = Mock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


def _plain_conn():
    """DatabaseConnection.get_connection()-style mock (BaseRepository)."""
    cur = Mock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    conn = Mock()
    conn.cursor.return_value = cur
    return conn, cur


def _hidden(ids):
    return patch('config.admin_view.hidden_ids_to_exclude', return_value=ids)


class TestClientStats:
    def test_get_clients_with_stats_excludes_owner_appointments(self, app):
        from repositories.clients.client_repository import ClientRepository
        conn, cur = _plain_conn()
        with app.app_context(), _hidden((9,)), \
                patch('config.database.DatabaseConnection.get_connection', return_value=conn):
            ClientRepository().get_clients_with_stats()
        sql = cur.execute.call_args.args[0]
        # both the aggregate join and the next-visit LATERAL carry the exclusion
        assert 'a.employee_id NOT IN (9)' in sql
        assert 'na.employee_id NOT IN (9)' in sql
        # client identity itself is not employee-filtered — the row still lists
        assert 'FROM clients c' in sql

    def test_monthly_visit_trends_excludes_owner(self, app):
        from repositories.clients.client_repository import ClientRepository
        conn, cur = _plain_conn()
        with app.app_context(), _hidden((9,)), \
                patch('config.database.DatabaseConnection.get_connection', return_value=conn):
            ClientRepository().get_all_monthly_visit_trends()
        assert 'a.employee_id NOT IN (9)' in cur.execute.call_args.args[0]

    def test_no_filter_when_admin_view_on(self, app):
        from repositories.clients.client_repository import ClientRepository
        conn, cur = _plain_conn()
        with app.app_context(), _hidden(()), \
                patch('config.database.DatabaseConnection.get_connection', return_value=conn):
            ClientRepository().get_clients_with_stats()
        # the query legitimately contains a status NOT IN (...) — assert only the
        # employee exclusion is absent under admin view ON.
        assert 'employee_id NOT IN' not in cur.execute.call_args.args[0]


class TestClientPreferences:
    def test_preferences_for_client_hides_owner_rows(self, app):
        from repositories.clients.client_preference_repository import ClientPreferenceRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), \
                patch('repositories.clients.client_preference_repository.get_db_connection',
                      return_value=conn):
            ClientPreferenceRepository().get_preferences_for_client(5)
        sql, params = cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])
        assert 'cp.preferred_employee_id NOT IN' in sql
        assert params == [5, 9]

    def test_clients_preferring_employee_filtered(self, app):
        from repositories.clients.client_preference_repository import ClientPreferenceRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), \
                patch('repositories.clients.client_preference_repository.get_db_connection',
                      return_value=conn):
            ClientPreferenceRepository().get_clients_preferring_employee(3)
        assert 'cp.preferred_employee_id NOT IN' in cur.execute.call_args.args[0]


class TestClientVisitHistory:
    def test_get_client_appointments_excludes_owner_before_limit(self, app):
        from repositories.appointments.appointment_repository import AppointmentRepository
        conn, cur = _ctx_conn()
        with app.app_context(), _hidden((9,)), \
                patch('repositories.appointments.appointment_repository.get_db_connection',
                      return_value=conn):
            AppointmentRepository().get_client_appointments(5, limit=20)
        sql, params = cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])
        assert 'a.employee_id NOT IN' in sql
        # param order: client_id, hidden id(s)..., limit
        assert params == [5, 9, 20]
