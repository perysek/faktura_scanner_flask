"""Unit tests for the "Widok administratora" choke-point (config/admin_view.py).

These lock in the security-critical guarantees from the plan:
  1. the hidden set resolves from superuser-linked employees and is g-cached;
  2. emp_exclusion_sql emits a correctly-parameterised NOT IN clause (or nothing);
  3. admin_view_active() is False for a non-superuser even if they forge the
     session flag — and the toggle route enforces the same rule with a 403.
"""
from unittest.mock import Mock, patch


def _mock_conn(rows):
    """A get_db_connection() stand-in usable as a context manager."""
    cur = Mock()
    cur.fetchall.return_value = rows
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


class TestGetHiddenEmployeeIds:
    def test_resolves_superuser_linked_ids(self, app):
        from config import admin_view
        conn, cur = _mock_conn([{'id': 3}, {'id': 7}])
        with app.app_context():
            with patch('config.admin_view.get_db_connection', return_value=conn):
                ids = admin_view.get_hidden_employee_ids()
        assert ids == (3, 7)
        sql = cur.execute.call_args.args[0]
        assert "role = 'superuser'" in sql
        assert 'FROM employees' in sql

    def test_result_cached_on_g(self, app):
        from config import admin_view
        conn, cur = _mock_conn([{'id': 3}])
        with app.app_context():
            with patch('config.admin_view.get_db_connection', return_value=conn):
                admin_view.get_hidden_employee_ids()
                admin_view.get_hidden_employee_ids()
            # second call is served from the flask.g cache — DB queried once
            assert cur.execute.call_count == 1

    def test_empty_when_no_superuser_employee(self, app):
        from config import admin_view
        conn, _ = _mock_conn([])
        with app.app_context():
            with patch('config.admin_view.get_db_connection', return_value=conn):
                assert admin_view.get_hidden_employee_ids() == ()

    def test_db_error_fails_open_to_empty(self, app):
        from config import admin_view
        with app.app_context():
            with patch('config.admin_view.get_db_connection',
                       side_effect=RuntimeError('db down')):
                assert admin_view.get_hidden_employee_ids() == ()

    def test_no_app_context_returns_empty(self):
        from config import admin_view
        # No app context at all → nothing to hide, no crash.
        assert admin_view.get_hidden_employee_ids() == ()


class TestEmpExclusionSql:
    def test_emits_not_in_clause_when_hidden(self, app):
        from config import admin_view
        with app.app_context():
            with patch('config.admin_view.hidden_ids_to_exclude', return_value=(3, 7)):
                clause, params = admin_view.emp_exclusion_sql('a.employee_id')
        assert clause.strip().startswith('AND a.employee_id NOT IN (')
        assert clause.count('%s') == 2
        assert params == [3, 7]

    def test_empty_when_nothing_hidden(self, app):
        from config import admin_view
        with app.app_context():
            with patch('config.admin_view.hidden_ids_to_exclude', return_value=()):
                clause, params = admin_view.emp_exclusion_sql('a.employee_id')
        assert clause == ''
        assert params == []

    def test_column_expression_is_interpolated_verbatim(self, app):
        from config import admin_view
        with app.app_context():
            with patch('config.admin_view.hidden_ids_to_exclude', return_value=(1,)):
                clause, _ = admin_view.emp_exclusion_sql('cp.preferred_employee_id')
        assert 'cp.preferred_employee_id NOT IN' in clause


class TestAdminViewActive:
    def test_superuser_with_flag_on(self, app):
        from config import admin_view
        su = Mock(is_authenticated=True, role='superuser')
        with app.test_request_context():
            from flask import session
            session['admin_view'] = True
            with patch('config.admin_view.current_user', su):
                assert admin_view.admin_view_active() is True

    def test_superuser_without_flag_is_off(self, app):
        from config import admin_view
        su = Mock(is_authenticated=True, role='superuser')
        with app.test_request_context():
            with patch('config.admin_view.current_user', su):
                assert admin_view.admin_view_active() is False

    def test_non_superuser_forging_flag_is_ignored(self, app):
        from config import admin_view
        recep = Mock(is_authenticated=True, role='receptionist')
        with app.test_request_context():
            from flask import session
            session['admin_view'] = True   # forged by a non-superuser
            with patch('config.admin_view.current_user', recep):
                assert admin_view.admin_view_active() is False
                # hidden_ids_to_exclude still hides the owner for this viewer
                with patch('config.admin_view.get_hidden_employee_ids',
                           return_value=(9,)):
                    assert admin_view.hidden_ids_to_exclude() == (9,)

    def test_anonymous_is_off(self, app):
        from config import admin_view
        anon = Mock(is_authenticated=False, role=None)
        with app.test_request_context():
            with patch('config.admin_view.current_user', anon):
                assert admin_view.admin_view_active() is False
                assert admin_view.is_superuser() is False


class TestToggleRoute:
    def _client(self, app):
        app.config['WTF_CSRF_ENABLED'] = False
        return app.test_client()

    def test_requires_login(self, app):
        client = self._client(app)
        resp = client.post('/api/admin-view', json={'enabled': True})
        # login_required redirects anonymous users to the login view
        assert resp.status_code in (302, 401)

    def test_non_superuser_gets_403(self, app):
        client = self._client(app)
        recep = Mock(is_authenticated=True, role='receptionist',
                     get_id=Mock(return_value='2'))
        with patch('flask_login.utils._get_user', return_value=recep):
            resp = client.post('/api/admin-view', json={'enabled': True})
        assert resp.status_code == 403
        with client.session_transaction() as sess:
            assert sess.get('admin_view') is None

    def test_superuser_enables_flag(self, app):
        client = self._client(app)
        su = Mock(is_authenticated=True, role='superuser',
                  get_id=Mock(return_value='1'))
        with patch('flask_login.utils._get_user', return_value=su):
            resp = client.post('/api/admin-view', json={'enabled': True})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True and data['enabled'] is True
        with client.session_transaction() as sess:
            assert sess.get('admin_view') is True

    def test_superuser_disables_flag(self, app):
        client = self._client(app)
        su = Mock(is_authenticated=True, role='superuser',
                  get_id=Mock(return_value='1'))
        with patch('flask_login.utils._get_user', return_value=su):
            resp = client.post('/api/admin-view', json={'enabled': False})
        assert resp.status_code == 200
        assert resp.get_json()['enabled'] is False
        with client.session_transaction() as sess:
            assert sess.get('admin_view') is False
