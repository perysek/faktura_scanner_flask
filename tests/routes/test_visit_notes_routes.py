"""Visit notes ("Uwagi i zalecenia z wizyt") — permission matrix, validation,
paging and the two list integrations (clients table, visits list).

The rule under test (principal, 2026-10-01), identical for every role including
superuser:

  * `appointments` access OFF  -> nothing, 403
  * read_only ON               -> view only, every write 403
  * own_data ON                -> only visits of the caller's linked employee
                                  (view AND write); no linked employee -> nothing
  * own_data OFF               -> all visits

Repositories are patched at the service's import site (the service builds them
itself) and role/employee lookups at their home modules, the same pattern as
tests/routes/test_permission_boundary_fixes.py.
"""
from contextlib import ExitStack
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

XHR = {'X-Requested-With': 'XMLHttpRequest'}

FULL = {'appointments': {'has_access': True, 'read_only': False, 'own_data': False},
        'clients': {'has_access': True, 'read_only': False, 'own_data': False}}
READ_ONLY = {'appointments': {'has_access': True, 'read_only': True, 'own_data': False},
             'clients': {'has_access': True, 'read_only': False, 'own_data': False}}
OWN_DATA = {'appointments': {'has_access': True, 'read_only': False, 'own_data': True},
            'clients': {'has_access': True, 'read_only': False, 'own_data': False}}
NO_ACCESS = {'appointments': {'has_access': False, 'read_only': False, 'own_data': False},
             'clients': {'has_access': True, 'read_only': False, 'own_data': False}}

NOTE_TEXT = 'Farba 6.1 + utleniacz 6%'


def _user(role='stylist', uid=5):
    from database.models import User
    return User(email='t@test.pl', password_hash='x', full_name='Test User',
                role=role, is_active=True, id=uid)


def _as(user, flags, *, own_employee_id=None, hidden=()):
    """Log `user` in with `flags`; `own_employee_id` is their linked employee."""
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda role, module: dict(
        flags.get(module, {'has_access': False, 'read_only': False, 'own_data': False}))
    emp_repo = MagicMock()
    emp_repo.get_by_user_id.return_value = (
        {'id': own_employee_id} if own_employee_id is not None else None)
    stack = ExitStack()
    stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('repositories.employees.employee_repository.EmployeeRepository', return_value=emp_repo))
    stack.enter_context(patch('flask_login.utils._get_user', return_value=user))
    stack.enter_context(patch('config.admin_view.get_hidden_employee_ids', return_value=tuple(hidden)))
    return stack


def _appt(employee_id=7, status='completed', client_id=5):
    return {'id': 100, 'employee_id': employee_id, 'status': status, 'client_id': client_id}


def _note_row(employee_id=7, note_id=11):
    return {
        'id': note_id, 'appointment_id': 100, 'client_id': 5, 'employee_id': employee_id,
        'client_name': 'Anna Nowak', 'service_name': 'Koloryzacja',
        'note_text': NOTE_TEXT, 'appointment_date': date(2026, 9, 30),
        # naive UTC, as the column stores it -> 08:15 in Warsaw (CEST)
        'updated_at': datetime(2026, 10, 1, 6, 15), 'created_at': datetime(2026, 9, 30, 12, 0),
        'updated_by_name': 'Ewa Kowalska',
    }


@pytest.fixture
def env(app):
    app.config['WTF_CSRF_ENABLED'] = False
    app.client_repo = MagicMock()
    app.client_repo.get_by_id.return_value = {'id': 5, 'first_name': 'Anna', 'last_name': 'Nowak'}
    notes, appts = MagicMock(), MagicMock()
    notes.create.return_value = 11
    notes.update_text.return_value = True
    notes.soft_delete.return_value = True
    notes.list_for_client.return_value = []
    notes.count_for_client.return_value = 0
    notes.eligible_visits.return_value = []
    notes.recent_for_clients.return_value = []
    notes.get_with_visit.return_value = _note_row()
    appts.get_by_id.return_value = _appt()
    with patch('services.visit_note_service.VisitNoteRepository', return_value=notes), \
         patch('services.visit_note_service.AppointmentRepository', return_value=appts), \
         patch('routes.visit_note_routes.audit_event') as audit:
        yield SimpleNamespace(c=app.test_client(), notes=notes, appts=appts, audit=audit, app=app)


def _create(env, text=NOTE_TEXT, appointment_id=100):
    return env.c.post('/api/visit-notes', headers=XHR, json={'appointment_id': appointment_id, 'note_text': text})


def _update(env, text='Nowa treść', note_id=11):
    return env.c.put(f'/api/visit-notes/{note_id}', headers=XHR, json={'note_text': text})


def _delete(env, note_id=11):
    return env.c.delete(f'/api/visit-notes/{note_id}', headers=XHR)


def _list(env, query=''):
    return env.c.get(f'/api/clients/5/visit-notes{query}', headers=XHR)


def _eligible(env):
    return env.c.get('/api/clients/5/visit-notes/visits', headers=XHR)


def _audit_values(env):
    """Every value handed to audit_event, positional and keyword, flattened to strings."""
    out = []
    for call in env.audit.call_args_list:
        out += [str(v) for v in call.args] + [str(v) for v in call.kwargs.values()]
    return out


def _assert_no_text_in_audit(env, *texts):
    """GET /api/history is open to every logged-in user (no module check, no own-data or
    hidden-owner scope) and returns old_value/new_value verbatim — so note text must
    never be written to audit_log (independent review finding, 2026-10-01)."""
    leaked = [v for v in _audit_values(env) for t in texts if t in v]
    assert not leaked, f'note text reached the audit trail: {leaked}'


# ─── ISC-2 · access OFF ──────────────────────────────────────────────────────

class TestNoAccess:
    @pytest.mark.parametrize('call', [_list, _eligible, _create, _update, _delete],
                             ids=['list', 'eligible', 'create', 'update', 'delete'])
    def test_every_endpoint_is_403_without_appointments_access(self, env, call):
        with _as(_user(), NO_ACCESS):
            assert call(env).status_code == 403
        env.notes.create.assert_not_called()
        env.notes.update_text.assert_not_called()
        env.notes.soft_delete.assert_not_called()
        env.notes.list_for_client.assert_not_called()


# ─── ISC-3 · read_only: view yes, write no ───────────────────────────────────

class TestReadOnly:
    def test_can_view_list_and_eligible(self, env):
        with _as(_user(), READ_ONLY):
            assert _list(env).status_code == 200
            assert _eligible(env).status_code == 200

    @pytest.mark.parametrize('call', [_create, _update, _delete], ids=['create', 'update', 'delete'])
    def test_cannot_write(self, env, call):
        with _as(_user(), READ_ONLY):
            assert call(env).status_code == 403
        env.notes.create.assert_not_called()
        env.notes.update_text.assert_not_called()
        env.notes.soft_delete.assert_not_called()

    def test_superuser_is_an_ordinary_role_read_only_still_blocks(self, env):
        with _as(_user(role='superuser'), READ_ONLY):
            assert _create(env).status_code == 403


# ─── ISC-4 · own_data: only the linked employee's visits ─────────────────────

class TestOwnData:
    def test_list_is_scoped_to_the_linked_employee(self, env):
        with _as(_user(), OWN_DATA, own_employee_id=7):
            assert _list(env).status_code == 200
        # (client_id, own_employee_id, limit, offset)
        assert env.notes.list_for_client.call_args.args == (5, 7, 10, 0)
        assert env.notes.count_for_client.call_args.args == (5, 7)

    def test_no_linked_employee_matches_nothing(self, env):
        with _as(_user(), OWN_DATA, own_employee_id=None):
            assert _list(env).status_code == 200
        assert env.notes.list_for_client.call_args.args[1] == -1  # sentinel: matches no employee

    def test_create_on_own_visit_is_allowed(self, env):
        env.appts.get_by_id.return_value = _appt(employee_id=7)
        with _as(_user(), OWN_DATA, own_employee_id=7):
            assert _create(env).status_code == 201

    def test_create_on_another_employees_visit_is_403(self, env):
        env.appts.get_by_id.return_value = _appt(employee_id=8)
        with _as(_user(), OWN_DATA, own_employee_id=7):
            assert _create(env).status_code == 403
        env.notes.create.assert_not_called()

    def test_update_and_delete_on_another_employees_note_are_403(self, env):
        env.notes.get_with_visit.return_value = _note_row(employee_id=8)
        with _as(_user(), OWN_DATA, own_employee_id=7):
            assert _update(env).status_code == 403
            assert _delete(env).status_code == 403
        env.notes.update_text.assert_not_called()
        env.notes.soft_delete.assert_not_called()

    def test_no_linked_employee_cannot_write_anything(self, env):
        with _as(_user(), OWN_DATA, own_employee_id=None):
            assert _create(env).status_code == 403
            assert _update(env).status_code == 403
            assert _delete(env).status_code == 403


# ─── ISC-5 · full access, superuser not special ──────────────────────────────

class TestFullAccess:
    @pytest.mark.parametrize('role', ['stylist', 'receptionist', 'superuser'])
    def test_any_role_with_full_flags_writes_on_any_visit(self, env, role):
        env.appts.get_by_id.return_value = _appt(employee_id=8)
        env.notes.get_with_visit.return_value = _note_row(employee_id=8)
        with _as(_user(role=role), FULL, own_employee_id=7):
            assert _create(env).status_code == 201
            assert _update(env).status_code == 200
            assert _delete(env).status_code == 200

    def test_list_is_unscoped(self, env):
        with _as(_user(role='superuser'), FULL, own_employee_id=7):
            _list(env)
        assert env.notes.list_for_client.call_args.args[1] is None


# ─── ISC-6 · the owner-employee stays hidden from non-superusers ─────────────

class TestHiddenOwner:
    def test_non_superuser_gets_404_for_the_owners_visit(self, env):
        env.appts.get_by_id.return_value = _appt(employee_id=9)
        env.notes.get_with_visit.return_value = _note_row(employee_id=9)
        with _as(_user(role='receptionist'), FULL, hidden=(9,)):
            assert _create(env).status_code == 404
            assert _update(env).status_code == 404
            assert _delete(env).status_code == 404
        env.notes.create.assert_not_called()

    def test_superuser_still_reaches_the_owners_visit(self, env):
        env.appts.get_by_id.return_value = _appt(employee_id=9)
        with _as(_user(role='superuser'), FULL, hidden=(9,)):
            assert _create(env).status_code == 201


# ─── ISC-11 / ISC-11.1 · create ──────────────────────────────────────────────

class TestCreate:
    def test_creates_on_completed_visit_with_trimmed_text(self, env):
        with _as(_user(uid=5), FULL):
            resp = _create(env, text=f'  {NOTE_TEXT}  ')
        assert resp.status_code == 201
        assert resp.get_json() == {'success': True, 'id': 11}
        env.notes.create.assert_called_once_with(100, NOTE_TEXT, 5)

    @pytest.mark.parametrize('status', ['scheduled', 'confirmed', 'in_progress', 'cancelled', 'no_show', 'rescheduled'])
    def test_only_completed_visits_take_notes(self, env, status):
        env.appts.get_by_id.return_value = _appt(status=status)
        with _as(_user(), FULL):
            assert _create(env).status_code == 409
        env.notes.create.assert_not_called()

    def test_unknown_visit_is_404(self, env):
        env.appts.get_by_id.return_value = None
        with _as(_user(), FULL):
            assert _create(env).status_code == 404

    @pytest.mark.parametrize('text', ['', '   ', '\n\t ', None, 'x' * 2001])
    def test_bad_text_is_400(self, env, text):
        with _as(_user(), FULL):
            assert _create(env, text=text).status_code == 400
        env.notes.create.assert_not_called()

    def test_text_at_the_limit_is_accepted(self, env):
        with _as(_user(), FULL):
            assert _create(env, text='x' * 2000).status_code == 201

    def test_missing_visit_id_is_400(self, env):
        with _as(_user(), FULL):
            resp = env.c.post('/api/visit-notes', headers=XHR, json={'note_text': NOTE_TEXT})
        assert resp.status_code == 400

    def test_writes_an_audit_event(self, env):
        with _as(_user(), FULL):
            _create(env)
        kwargs = env.audit.call_args.kwargs
        assert env.audit.call_args.args[:2] == ('visit_note', 'CREATE')
        assert kwargs['entity_id'] == 11
        assert kwargs['field_name'] == 'note_length'
        assert kwargs['new_value'] == str(len(NOTE_TEXT))
        _assert_no_text_in_audit(env, NOTE_TEXT)


# ─── hardening: malformed input is a 400, never a 500 or a silent mis-target ──

class TestMalformedInput:
    @pytest.mark.parametrize('body', [[1, 2], 'text', 5, None], ids=['list', 'string', 'number', 'null'])
    def test_non_object_body_is_400_on_create_and_update(self, env, body):
        with _as(_user(), FULL):
            assert env.c.post('/api/visit-notes', headers=XHR, json=body).status_code == 400
            assert env.c.put('/api/visit-notes/11', headers=XHR, json=body).status_code == 400
        env.notes.create.assert_not_called()
        env.notes.update_text.assert_not_called()

    @pytest.mark.parametrize('bad_id', [True, 5.9, float('inf'), 'abc', '', -3, 0, None, [1]],
                             ids=['bool', 'float', 'infinity', 'word', 'empty', 'negative', 'zero', 'null', 'list'])
    def test_appointment_id_must_be_a_real_positive_integer(self, env, bad_id):
        """int(True) is 1 and int(5.9) is 5 — a bool/float must never silently address a visit."""
        with _as(_user(), FULL):
            assert _create(env, appointment_id=bad_id).status_code == 400
        env.appts.get_by_id.assert_not_called()
        env.notes.create.assert_not_called()

    def test_digit_string_id_is_accepted(self, env):
        with _as(_user(), FULL):
            assert _create(env, appointment_id='100').status_code == 201
        assert env.notes.create.call_args.args[0] == 100

    def test_nul_character_in_text_is_400(self, env):
        with _as(_user(), FULL):
            assert _create(env, text='a\x00b').status_code == 400
            assert _update(env, text='a\x00b').status_code == 400
        env.notes.create.assert_not_called()
        env.notes.update_text.assert_not_called()

    def test_huge_offset_is_clamped_not_a_500(self, env):
        with _as(_user(), FULL):
            assert _list(env, '?offset=99999999999999999999999').status_code == 200
        assert env.notes.list_for_client.call_args.args[3] == 100_000


# ─── ISC-12 / ISC-11.1 · update ──────────────────────────────────────────────

class TestUpdate:
    def test_updates_text_and_editor_only(self, env):
        with _as(_user(uid=5), FULL):
            resp = _update(env, text='  Nowa treść  ')
        assert resp.status_code == 200
        # the repository signature carries no created_* at all: it cannot touch them
        env.notes.update_text.assert_called_once_with(11, 'Nowa treść', 5)

    @pytest.mark.parametrize('text', ['', '   ', None, 'x' * 2001])
    def test_bad_text_is_400(self, env, text):
        with _as(_user(), FULL):
            assert _update(env, text=text).status_code == 400
        env.notes.update_text.assert_not_called()

    def test_unknown_note_is_404(self, env):
        env.notes.get_with_visit.return_value = None
        with _as(_user(), FULL):
            assert _update(env).status_code == 404

    def test_writes_an_audit_event_with_old_and_new_lengths_only(self, env):
        with _as(_user(), FULL):
            _update(env, text='Nowa treść')
        kwargs = env.audit.call_args.kwargs
        assert env.audit.call_args.args[:2] == ('visit_note', 'UPDATE')
        assert kwargs['old_value'] == str(len(NOTE_TEXT))
        assert kwargs['new_value'] == str(len('Nowa treść'))
        _assert_no_text_in_audit(env, NOTE_TEXT, 'Nowa treść')


# ─── ISC-13 · delete ─────────────────────────────────────────────────────────

class TestDelete:
    def test_soft_deletes(self, env):
        with _as(_user(uid=5), FULL):
            resp = _delete(env)
        assert resp.status_code == 200
        env.notes.soft_delete.assert_called_once_with(11, 5)

    def test_unknown_note_is_404(self, env):
        env.notes.get_with_visit.return_value = None
        with _as(_user(), FULL):
            assert _delete(env).status_code == 404
        env.notes.soft_delete.assert_not_called()

    def test_writes_an_audit_event(self, env):
        with _as(_user(), FULL):
            _delete(env)
        assert env.audit.call_args.args[:2] == ('visit_note', 'DELETE')
        assert env.audit.call_args.kwargs['old_value'] == str(len(NOTE_TEXT))
        _assert_no_text_in_audit(env, NOTE_TEXT)


# ─── ISC-14 / ISC-14.1 · list ────────────────────────────────────────────────

class TestList:
    def test_row_shape_and_formatting(self, env):
        env.notes.list_for_client.return_value = [_note_row()]
        env.notes.count_for_client.return_value = 1
        with _as(_user(), FULL):
            body = _list(env).get_json()
        row = body['notes'][0]
        assert row['id'] == 11
        assert row['appointment_date'] == '2026-09-30'
        assert row['client_name'] == 'Anna Nowak'
        assert row['service_name'] == 'Koloryzacja'
        assert row['note_text'] == NOTE_TEXT
        assert row['updated_at'] == '2026-10-01T08:15:00'  # Warsaw-local, no designator
        assert row['updated_by_name'] == 'Ewa Kowalska'
        assert row['can_edit'] is True
        assert 'created_at' not in row and 'created_by' not in row  # never sent to the UI
        assert body['total'] == 1 and body['has_more'] is False

    def test_paging_flags(self, env):
        env.notes.list_for_client.return_value = [_note_row(note_id=i) for i in range(10)]
        env.notes.count_for_client.return_value = 23
        with _as(_user(), FULL):
            first = _list(env).get_json()
            third = _list(env, '?offset=20').get_json()
        assert first['has_more'] is True
        assert env.notes.list_for_client.call_args_list[0].args == (5, None, 10, 0)
        assert env.notes.list_for_client.call_args_list[1].args == (5, None, 10, 20)
        env.notes.list_for_client.return_value = [_note_row(note_id=i) for i in range(3)]
        with _as(_user(), FULL):
            last = _list(env, '?offset=20').get_json()
        assert last['has_more'] is False

    @pytest.mark.parametrize('query,expected', [('?limit=500', 50), ('?limit=0', 10), ('?limit=abc', 10), ('?offset=-5', 10)])
    def test_limit_is_clamped(self, env, query, expected):
        with _as(_user(), FULL):
            _list(env, query)
        assert env.notes.list_for_client.call_args.args[2] == expected
        assert env.notes.list_for_client.call_args.args[3] == 0

    def test_can_edit_false_for_read_only(self, env):
        env.notes.list_for_client.return_value = [_note_row()]
        with _as(_user(), READ_ONLY):
            row = _list(env).get_json()['notes'][0]
        assert row['can_edit'] is False

    def test_can_edit_false_when_the_visit_is_outside_own_scope(self, env):
        # a defensive case: even if a foreign row reached the serializer, no edit rights
        env.notes.list_for_client.return_value = [_note_row(employee_id=8)]
        with _as(_user(), OWN_DATA, own_employee_id=7):
            row = _list(env).get_json()['notes'][0]
        assert row['can_edit'] is False

    def test_unknown_client_is_404(self, env):
        env.app.client_repo.get_by_id.return_value = None
        with _as(_user(), FULL):
            assert _list(env).status_code == 404

    def test_can_add_follows_eligible_visits_on_the_client_page(self, env):
        env.notes.eligible_visits.return_value = [{'appointment_id': 100}]
        with _as(_user(), FULL):
            assert _list(env).get_json()['can_add'] is True
        env.notes.eligible_visits.return_value = []
        with _as(_user(), FULL):
            assert _list(env).get_json()['can_add'] is False

    def test_can_add_false_for_read_only(self, env):
        env.notes.eligible_visits.return_value = [{'appointment_id': 100}]
        with _as(_user(), READ_ONLY):
            assert _list(env).get_json()['can_add'] is False

    def test_can_add_for_a_specific_visit_needs_it_completed_and_in_scope(self, env):
        env.appts.get_by_id.return_value = _appt(status='completed', employee_id=7)
        with _as(_user(), OWN_DATA, own_employee_id=7):
            assert _list(env, '?appointment_id=100').get_json()['can_add'] is True
        env.appts.get_by_id.return_value = _appt(status='scheduled', employee_id=7)
        with _as(_user(), OWN_DATA, own_employee_id=7):
            assert _list(env, '?appointment_id=100').get_json()['can_add'] is False
        env.appts.get_by_id.return_value = _appt(status='completed', employee_id=8)
        with _as(_user(), OWN_DATA, own_employee_id=7):
            assert _list(env, '?appointment_id=100').get_json()['can_add'] is False


# ─── ISC-15 · eligible visits for the client-page picker ─────────────────────

class TestEligibleVisits:
    def test_returns_scoped_completed_visits(self, env):
        env.notes.eligible_visits.return_value = [{
            'appointment_id': 100, 'appointment_date': date(2026, 9, 30),
            'service_name': 'Koloryzacja', 'employee_name': 'Ewa Kowalska'}]
        with _as(_user(), OWN_DATA, own_employee_id=7):
            body = _eligible(env).get_json()
        assert body['visits'] == [{'appointment_id': 100, 'appointment_date': '2026-09-30',
                                   'service_name': 'Koloryzacja', 'employee_name': 'Ewa Kowalska'}]
        assert env.notes.eligible_visits.call_args.args[:2] == (5, 7)


# ─── ISC-17 · clients list: recent_notes (max 2, one batched query) ──────────

def _client_row(cid):
    now = datetime(2026, 1, 1)
    return {'id': cid, 'first_name': 'Anna', 'last_name': f'K{cid}', 'phone': None, 'email': None,
            'date_of_birth': None, 'notes': None, 'preferences': None, 'first_visit_date': None,
            'last_visit_date': None, 'is_active': True, 'no_show_count': 0, 'cancelled_count': 0,
            'rescheduled_count': 0, 'created_at': now, 'updated_at': now, 'completed_visits': 0,
            'visits_last_8w': 0, 'next_visit_date': None, 'next_visit_time': None,
            'next_visit_employee': None}


class TestClientsListIntegration:
    @pytest.fixture(autouse=True)
    def _clients(self, env):
        from repositories.clients.client_repository import ClientRepository
        env.app.client_repo.get_clients_with_stats.return_value = [_client_row(5), _client_row(6)]
        env.app.client_repo.row_to_client = ClientRepository().row_to_client
        env.notes.recent_for_clients.return_value = [
            {'client_id': 5, 'note_text': 'Nowsza', 'updated_at': datetime(2026, 10, 1, 6, 15)},
            {'client_id': 5, 'note_text': 'Starsza', 'updated_at': datetime(2026, 9, 1, 8, 0)},
        ]

    def test_attaches_two_newest_per_client_in_one_query(self, env):
        with _as(_user(), FULL):
            body = env.c.get('/api/clients?include_notes=1', headers=XHR).get_json()
        by_id = {c['id']: c for c in body['clients']}
        assert by_id[5]['recent_notes'] == [
            {'text': 'Nowsza', 'at': '2026-10-01T08:15:00'},
            {'text': 'Starsza', 'at': '2026-09-01T10:00:00'},
        ]
        assert by_id[6]['recent_notes'] == []
        assert env.notes.recent_for_clients.call_count == 1
        assert env.notes.recent_for_clients.call_args.args == ([5, 6], None, 2)

    def test_absent_without_the_flag(self, env):
        with _as(_user(), FULL):
            body = env.c.get('/api/clients', headers=XHR).get_json()
        assert all('recent_notes' not in c for c in body['clients'])
        env.notes.recent_for_clients.assert_not_called()

    def test_absent_and_unqueried_without_appointments_access(self, env):
        with _as(_user(), NO_ACCESS):
            resp = env.c.get('/api/clients?include_notes=1', headers=XHR)
        assert resp.status_code == 200
        assert all('recent_notes' not in c for c in resp.get_json()['clients'])
        env.notes.recent_for_clients.assert_not_called()

    def test_own_data_scope_reaches_the_query(self, env):
        with _as(_user(), OWN_DATA, own_employee_id=7):
            env.c.get('/api/clients?include_notes=1', headers=XHR)
        assert env.notes.recent_for_clients.call_args.args[1] == 7


# ─── ISC-18 · visits list: latest_note (1) ───────────────────────────────────

class TestAppointmentsListIntegration:
    @pytest.fixture(autouse=True)
    def _appointments(self, env):
        env.appt_repo = MagicMock()
        env.appt_repo.get_by_date_range.return_value = [
            {'id': 1, 'client_id': 5, 'employee_id': 7, 'status': 'completed'},
            {'id': 2, 'client_id': 6, 'employee_id': 7, 'status': 'scheduled'},
            {'id': 3, 'client_id': 5, 'employee_id': 7, 'status': 'scheduled'},
        ]
        env.notes.recent_for_clients.return_value = [
            {'client_id': 5, 'note_text': 'Najnowsza', 'updated_at': datetime(2026, 10, 1, 6, 15)}]
        with patch('routes.appointment_routes.AppointmentRepository', return_value=env.appt_repo):
            yield

    def _get(self, env, query=''):
        return env.c.get(f'/api/appointments?start_date=2026-10-01&end_date=2026-10-07{query}', headers=XHR)

    def test_attaches_the_clients_single_latest_note(self, env):
        with _as(_user(), FULL):
            appts = {a['id']: a for a in self._get(env, '&include_notes=1').get_json()['appointments']}
        assert appts[1]['latest_note'] == {'text': 'Najnowsza', 'at': '2026-10-01T08:15:00'}
        assert appts[3]['latest_note'] == {'text': 'Najnowsza', 'at': '2026-10-01T08:15:00'}  # same client
        assert appts[2]['latest_note'] is None
        assert env.notes.recent_for_clients.call_args.args == ([5, 6], None, 1)
        assert env.notes.recent_for_clients.call_count == 1

    def test_payload_unchanged_without_the_flag(self, env):
        with _as(_user(), FULL):
            appts = self._get(env).get_json()['appointments']
        assert all('latest_note' not in a for a in appts)
        env.notes.recent_for_clients.assert_not_called()

    def test_own_data_scope_reaches_the_query(self, env):
        with _as(_user(), OWN_DATA, own_employee_id=7):
            self._get(env, '&include_notes=1')
        assert env.notes.recent_for_clients.call_args.args[1] == 7
