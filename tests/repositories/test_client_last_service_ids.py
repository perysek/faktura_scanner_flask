"""ClientRepository.last_service_ids — the phone cards' "Umów wizytę" prefill.

Repository I/O is patched (no database): these prove the SQL carries what makes the
prefill trustworthy — completed visits only, never soft-deleted ones, the main
service before any add-on, the newest visit winning, the owner's hidden visits
excluded — and that it is one batched query, never one per client.
"""
from unittest.mock import patch

REPO = 'repositories.clients.client_repository.ClientRepository'


def _hidden(ids):
    """Simulate "admin view OFF, these employees hidden" (or () = reveal all)."""
    return patch('config.admin_view.hidden_ids_to_exclude', return_value=ids)


def _repo():
    from repositories.clients.client_repository import ClientRepository
    return ClientRepository()


def _capture(rows=None):
    calls = []

    def fake(self, sql, params=()):
        calls.append((sql, list(params)))
        return rows if rows is not None else []

    return calls, patch(f'{REPO}._fetch_all', fake)


class TestLastServiceIds:
    def test_one_batched_query_for_all_clients(self, app):
        calls, p = _capture()
        with app.app_context(), _hidden(()), p:
            _repo().last_service_ids([5, 6, 7])
        assert len(calls) == 1  # never N+1
        sql, params = calls[0]
        assert 'a.client_id = ANY(%s)' in sql
        assert params == [[5, 6, 7]]

    def test_only_live_completed_visits_count(self, app):
        calls, p = _capture()
        with app.app_context(), _hidden(()), p:
            _repo().last_service_ids([5])
        sql = calls[0][0]
        assert "a.status = 'completed'" in sql
        assert 'a.is_deleted = FALSE' in sql

    def test_picks_the_main_service_of_the_newest_visit(self, app):
        calls, p = _capture()
        with app.app_context(), _hidden(()), p:
            _repo().last_service_ids([5])
        sql = calls[0][0]
        assert 'DISTINCT ON (a.client_id)' in sql
        assert 'ORDER BY aps.is_addon ASC, aps.id ASC' in sql  # main before add-on
        assert 'ORDER BY a.client_id, a.appointment_date DESC, a.start_time DESC' in sql

    def test_a_visit_without_services_is_skipped_not_returned_as_null(self, app):
        calls, p = _capture()
        with app.app_context(), _hidden(()), p:
            _repo().last_service_ids([5])
        # inner JOIN LATERAL: a completed visit with no service rows drops out, so the
        # client's previous visit can win instead of the prefill coming back empty.
        assert 'JOIN LATERAL' in calls[0][0]
        assert 'LEFT JOIN LATERAL' not in calls[0][0]

    def test_owner_visits_are_excluded_while_admin_view_is_off(self, app):
        calls, p = _capture()
        with app.app_context(), _hidden((9,)), p:
            _repo().last_service_ids([5])
        assert 'a.employee_id NOT IN (9)' in calls[0][0]

    def test_no_exclusion_clause_when_nothing_is_hidden(self, app):
        calls, p = _capture()
        with app.app_context(), _hidden(()), p:
            _repo().last_service_ids([5])
        assert 'NOT IN' not in calls[0][0]

    def test_maps_rows_to_client_id_service_id(self, app):
        _, p = _capture(rows=[{'client_id': 5, 'service_id': 11}, {'client_id': 7, 'service_id': 3}])
        with app.app_context(), _hidden(()), p:
            assert _repo().last_service_ids([5, 6, 7]) == {5: 11, 7: 3}

    def test_empty_id_list_short_circuits_without_a_query(self, app):
        calls, p = _capture()
        with app.app_context(), p:
            assert _repo().last_service_ids([]) == {}
        assert calls == []
