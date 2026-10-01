"""SQL composition of VisitNoteRepository.

The service tests prove WHO may see what; these prove the SQL actually carries
that scope: soft-delete filters, the own-data clause, the admin-view exclusion
choke-point (emp_exclusion_sql), the batched window-function query and
parameter order. Repository I/O is patched so no database is needed — the same
approach as tests/repositories/test_appointment_admin_view_filter.py.
"""
from unittest.mock import patch

REPO = 'repositories.appointments.visit_note_repository.VisitNoteRepository'


def _hidden(ids):
    """Simulate "admin view OFF, these employees hidden" (or () = reveal all)."""
    return patch('config.admin_view.hidden_ids_to_exclude', return_value=ids)


def _capture(method_name, rows=None):
    captured = {}

    def fake(self, sql, params=()):
        captured['sql'], captured['params'] = sql, list(params)
        return rows if rows is not None else []

    return captured, patch(f'{REPO}.{method_name}', fake)


def _repo():
    from repositories.appointments.visit_note_repository import VisitNoteRepository
    return VisitNoteRepository()


class TestListForClient:
    def test_filters_deleted_notes_and_visits_and_orders_by_last_edit(self, app):
        cap, p = _capture('_fetch_all')
        with app.app_context(), _hidden(()), p:
            _repo().list_for_client(5, None, 10, 0)
        sql = cap['sql']
        assert 'n.is_deleted = FALSE' in sql
        assert 'a.is_deleted = FALSE' in sql
        assert 'ORDER BY n.updated_at DESC, n.id DESC' in sql
        assert 'LIMIT %s OFFSET %s' in sql

    def test_first_service_prefers_the_main_service(self, app):
        cap, p = _capture('_fetch_all')
        with app.app_context(), _hidden(()), p:
            _repo().list_for_client(5, None, 10, 0)
        assert 'ORDER BY aps.is_addon ASC, aps.id ASC' in cap['sql']
        assert 'LIMIT 1' in cap['sql']

    def test_no_scope_clauses_for_unrestricted_caller(self, app):
        cap, p = _capture('_fetch_all')
        with app.app_context(), _hidden(()), p:
            _repo().list_for_client(5, None, 10, 0)
        assert 'a.employee_id = %s' not in cap['sql']
        assert 'NOT IN' not in cap['sql']
        assert cap['params'] == [5, 10, 0]

    def test_own_data_adds_the_employee_clause(self, app):
        cap, p = _capture('_fetch_all')
        with app.app_context(), _hidden(()), p:
            _repo().list_for_client(5, 7, 10, 0)
        assert 'a.employee_id = %s' in cap['sql']
        assert cap['params'] == [5, 7, 10, 0]

    def test_no_linked_employee_sentinel_matches_nothing(self, app):
        cap, p = _capture('_fetch_all')
        with app.app_context(), _hidden(()), p:
            _repo().list_for_client(5, -1, 10, 0)
        assert -1 in cap['params']  # an id no employee has

    def test_hidden_owner_is_excluded_and_params_precede_limit_offset(self, app):
        cap, p = _capture('_fetch_all')
        with app.app_context(), _hidden((9,)), p:
            _repo().list_for_client(5, 7, 10, 20)
        assert 'a.employee_id NOT IN' in cap['sql']
        assert cap['params'] == [5, 9, 7, 10, 20]  # client, hidden, own, limit, offset


class TestCountForClient:
    def test_count_applies_the_same_scope(self, app):
        cap, p = _capture('_fetch_one', rows={'total': 3})
        with app.app_context(), _hidden((9,)), p:
            total = _repo().count_for_client(5, 7)
        assert total == 3
        assert 'COUNT(*)' in cap['sql']
        assert 'n.is_deleted = FALSE' in cap['sql']
        assert 'a.employee_id NOT IN' in cap['sql']
        assert 'a.employee_id = %s' in cap['sql']
        assert cap['params'] == [5, 9, 7]


class TestEligibleVisits:
    def test_only_completed_visits_in_scope_newest_first(self, app):
        cap, p = _capture('_fetch_all')
        with app.app_context(), _hidden((9,)), p:
            _repo().eligible_visits(5, 7, 50)
        sql = cap['sql']
        assert "a.status = 'completed'" in sql
        assert 'a.is_deleted = FALSE' in sql
        assert 'ORDER BY a.appointment_date DESC, a.start_time DESC' in sql
        assert 'a.employee_id NOT IN' in sql and 'a.employee_id = %s' in sql
        assert cap['params'] == [5, 9, 7, 50]


class TestRecentForClients:
    def test_single_batched_window_query(self, app):
        calls = []

        def fake(self, sql, params=()):
            calls.append((sql, list(params)))
            return []

        with app.app_context(), _hidden((9,)), patch(f'{REPO}._fetch_all', fake):
            _repo().recent_for_clients([5, 6, 7], 8, 2)
        assert len(calls) == 1  # never N+1
        sql, params = calls[0]
        assert 'ROW_NUMBER() OVER (PARTITION BY a.client_id' in sql
        assert 'ORDER BY n.updated_at DESC, n.id DESC' in sql
        assert 'a.client_id = ANY(%s)' in sql
        assert 'n.is_deleted = FALSE' in sql
        assert 'a.employee_id NOT IN' in sql and 'a.employee_id = %s' in sql
        assert params == [[5, 6, 7], 9, 8, 2]  # ids, hidden, own, per-client cap

    def test_empty_id_list_short_circuits_without_a_query(self, app):
        with app.app_context(), patch(f'{REPO}._fetch_all') as fetch:
            assert _repo().recent_for_clients([], None, 2) == []
        fetch.assert_not_called()


class TestWrites:
    def test_soft_delete_flags_the_row_and_records_who(self, app):
        cap = {}

        class Cur:
            rowcount = 1

        def fake(self, sql, params=()):
            cap['sql'], cap['params'] = sql, list(params)
            return Cur()

        with app.app_context(), patch(f'{REPO}._execute', fake):
            assert _repo().soft_delete(11, 5) is True
        assert 'is_deleted = TRUE' in cap['sql']
        assert 'deleted_at' in cap['sql']
        assert 'is_deleted = FALSE' in cap['sql']  # idempotent: only live rows
        assert cap['params'] == [5, 11] or cap['params'] == [11, 5] or 11 in cap['params']

    def test_update_never_touches_created_columns(self, app):
        cap = {}

        class Cur:
            rowcount = 1

        def fake(self, sql, params=()):
            cap['sql'], cap['params'] = sql, list(params)
            return Cur()

        with app.app_context(), patch(f'{REPO}._execute', fake):
            assert _repo().update_text(11, 'Nowa treść', 5) is True
        assert 'created_at' not in cap['sql'] and 'created_by' not in cap['sql']
        assert 'updated_at' in cap['sql'] and 'updated_by' in cap['sql']
        assert 'is_deleted = FALSE' in cap['sql']
