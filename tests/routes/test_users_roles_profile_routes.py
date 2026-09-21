"""Users / Roles / Profil API — route gates, RBAC integrity guards, additive JSON, audit rows.

Repositories are mocked at the route-module seam (`_user_repo` / `_role_repo`), so
these tests exercise the real handlers, decorators and error mapping without a DB.
"""
import json
from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

XHR = {'X-Requested-With': 'XMLHttpRequest'}
FORBIDDEN_COMP_KEYS = ('base_salary', 'commission_rate', 'employer_cost_rate', 'salary', 'commission')


def _user(role='admin', uid=10, active=True, name='Admin Test', email='admin@test.pl'):
    from database.models import User
    return User(email=email, password_hash='x', full_name=name, role=role, is_active=active, id=uid,
                last_login=datetime(2026, 9, 1, 12, 30), created_at=datetime(2026, 1, 2, 8, 0))


@contextmanager
def as_user(user):
    with patch('flask_login.utils._get_user', return_value=user):
        yield


@pytest.fixture
def api(app):
    app.config['WTF_CSRF_ENABLED'] = False
    app.audit_repo = MagicMock()
    return app.test_client()


def _audit_kwargs(app):
    return [c.kwargs for c in app.audit_repo.safe_log_event.call_args_list]


def _flags(**on):
    base = {'has_access': False, 'read_only': False, 'own_data': False,
            'can_edit_price_history': False, 'can_send_sms': False}
    base.update(on)
    return base


def _perms(**modules):
    from repositories.roles.role_repository import ALL_MODULES
    return {m: (_flags(**modules[m]) if m in modules else _flags()) for m in ALL_MODULES}


def _user_repo_for(target, *, linked=None, superusers=2, link_state=None, roles=None):
    """A MagicMock UserRepository wired for a single target account."""
    repo = MagicMock()
    repo.get_by_id.return_value = {'id': target.id}
    repo.row_to_user.return_value = target
    repo.get_by_email.return_value = None
    repo.get_linked_employee.return_value = linked
    repo.count_active_superusers.return_value = superusers
    repo.get_employee_link_state.return_value = link_state
    repo.delete_user.return_value = True
    return repo


def _role_repo_for(*role_names):
    repo = MagicMock()
    rows = [{'id': i + 1, 'name': n, 'display_name': n.capitalize(), 'is_protected': n in ('superuser', 'admin'),
             'access_count': 2} for i, n in enumerate(role_names)]
    repo.get_all.return_value = rows
    repo.get_by_name.side_effect = lambda n: next((r for r in rows if r['name'] == n), None)
    repo.get_permissions.return_value = _perms(appointments={'has_access': True, 'own_data': True})
    repo.get_user_counts.return_value = {}
    return repo


# ─── ISC-2 · gates ────────────────────────────────────────────────────────────

class TestGates:
    def test_gates_anonymous_users_api_redirects_to_login(self, api):
        resp = api.get('/system/users/api', headers=XHR)
        assert resp.status_code == 302 and '/auth/login' in resp.headers['Location']

    def test_gates_stylist_cannot_reach_users_api(self, api):
        with as_user(_user('stylist', 5)):
            assert api.get('/system/users/api', headers=XHR).status_code == 302

    def test_gates_admin_cannot_reach_roles_api(self, api):
        with as_user(_user('admin')):
            assert api.get('/system/roles/api', headers=XHR).status_code == 302

    def test_gates_admin_can_reach_users_api(self, api):
        repo = MagicMock()
        repo.get_all_with_employee.return_value = []
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo):
            resp = api.get('/system/users/api', headers=XHR)
        assert resp.status_code == 200 and resp.get_json()['count'] == 0

    def test_gates_users_list_carries_role_display_name_with_key_fallback(self, api):
        base = {'id': 1, 'email': 'a@x.pl', 'full_name': 'A', 'is_active': True, 'last_login': None,
                'created_at': None, 'employee_id': None, 'employee_first_name': None, 'employee_last_name': None}
        repo = MagicMock()
        repo.get_all_with_employee.return_value = [
            {**base, 'role': 'stylist', 'role_display_name': 'Stylistka'},
            {**base, 'id': 2, 'role': 'ghost', 'role_display_name': None},
        ]
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo):
            users = api.get('/system/users/api', headers=XHR).get_json()['users']
        assert [u['role_display_name'] for u in users] == ['Stylistka', 'ghost']

    def test_gates_profile_json_open_to_any_authenticated_role(self, api):
        with as_user(_user('stylist', 5)), _profile_patches():
            resp = api.get('/auth/profile', headers=XHR)
        assert resp.status_code == 200 and resp.get_json()['success'] is True

    def test_gates_profile_anonymous_gets_no_data(self, api):
        resp = api.get('/auth/profile', headers=XHR)
        assert resp.status_code in (302, 401)
        assert b'"user"' not in resp.data


# ─── ISC-11/12 · profile JSON ────────────────────────────────────────────────

def _profile_patches(employee=None, role_row=None):
    role_repo = MagicMock()
    role_repo.get_by_name.return_value = role_row or {'id': 3, 'name': 'stylist', 'display_name': 'Stylistka'}
    user_repo = MagicMock()
    user_repo.get_profile_employee.return_value = employee
    from contextlib import ExitStack
    stack = ExitStack()
    stack.enter_context(patch('routes.auth.routes.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('routes.auth.routes.UserRepository', return_value=user_repo))
    stack.enter_context(patch('routes.auth.routes.get_all_permission_flags',
                              return_value={'appointments': {'has_access': True, 'read_only': False, 'own_data': True}}))
    return stack


class TestProfileJson:
    def test_profile_json_shape(self, api):
        emp = {'id': 8, 'first_name': 'Anna', 'last_name': 'Nowak', 'position': 'Stylistka',
               'employment_status': 'active', 'hire_date': date(2024, 3, 1)}
        with as_user(_user('stylist', 5, name='Anna Nowak', email='anna@test.pl')), _profile_patches(employee=emp):
            data = api.get('/auth/profile', headers=XHR).get_json()
        assert data['user'] == {
            'id': 5, 'email': 'anna@test.pl', 'full_name': 'Anna Nowak', 'role': 'stylist',
            'role_display_name': 'Stylistka', 'is_active': True,
            'last_login': '2026-09-01T12:30:00', 'created_at': '2026-01-02T08:00:00',
        }
        assert data['employee'] == {'id': 8, 'first_name': 'Anna', 'last_name': 'Nowak', 'position': 'Stylistka',
                                    'employment_status': 'active', 'hire_date': '2024-03-01'}
        assert data['permissions']['appointments']['own_data'] is True
        assert 'data_import' in data['module_display_names']

    def test_profile_json_employee_null_when_unlinked(self, api):
        with as_user(_user('accountant', 6)), _profile_patches(employee=None):
            assert api.get('/auth/profile', headers=XHR).get_json()['employee'] is None

    def test_profile_json_unknown_role_falls_back_to_key(self, api):
        role_repo = MagicMock()
        role_repo.get_by_name.return_value = None
        with as_user(_user('ghost', 7)), _profile_patches() as st:
            st.enter_context(patch('routes.auth.routes.RoleRepository', return_value=role_repo))
            data = api.get('/auth/profile', headers=XHR).get_json()
        assert data['user']['role_display_name'] == 'ghost'

    def test_profile_no_comp_keys_for_any_role(self, api):
        emp = {'id': 8, 'first_name': 'A', 'last_name': 'B', 'position': None, 'employment_status': 'active',
               'hire_date': None}
        for role in ('superuser', 'admin', 'receptionist', 'stylist', 'accountant'):
            with as_user(_user(role, 9)), _profile_patches(employee=emp):
                body = api.get('/auth/profile', headers=XHR).get_data(as_text=True)
            for key in FORBIDDEN_COMP_KEYS:
                assert key not in body, f'{key} leaked in profile JSON for {role}'

    def test_profile_no_comp_sql_uses_explicit_allowlist(self):
        from repositories.users.user_repository import UserRepository
        with patch.object(UserRepository, '_fetch_one', return_value=None) as fetch:
            UserRepository().get_profile_employee(5)
        query = fetch.call_args[0][0].lower()
        assert 'select *' not in query and 'e.*' not in query
        for banned in ('salary', 'commission', 'employer_cost'):
            assert banned not in query
        for wanted in ('first_name', 'last_name', 'position', 'employment_status', 'hire_date'):
            assert wanted in query


# ─── ISC-15 · self password change audit ─────────────────────────────────────

class TestSelfPasswordAudit:
    def test_self_password_audit_row_has_no_secret(self, api):
        audit = MagicMock()
        svc = MagicMock()
        svc.change_password.return_value = (True, None)
        with as_user(_user('stylist', 5)), \
                patch('routes.auth.routes.AuthService', return_value=svc), \
                patch('routes.auth.routes.AuditRepository', return_value=audit):
            resp = api.post('/auth/change-password', headers=XHR,
                            json={'old_password': 'OldSecret#1', 'new_password': 'NewSecret#2',
                                  'confirm_password': 'NewSecret#2'})
        assert resp.status_code == 200
        audit.safe_log_event.assert_called_once()
        kw = audit.safe_log_event.call_args.kwargs
        assert (kw['entity_type'], kw['action'], kw['field_name'], kw['new_value']) == ('user', 'UPDATE', 'hasło', '(zmieniono)')
        assert kw['entity_id'] == 5 and kw['user_id'] == 5
        blob = json.dumps(str(audit.mock_calls))
        assert 'OldSecret#1' not in blob and 'NewSecret#2' not in blob

    def test_self_password_failure_writes_no_audit_row(self, api):
        audit = MagicMock()
        svc = MagicMock()
        svc.change_password.return_value = (False, 'Nieprawidłowe stare hasło')
        with as_user(_user('stylist', 5)), \
                patch('routes.auth.routes.AuthService', return_value=svc), \
                patch('routes.auth.routes.AuditRepository', return_value=audit):
            resp = api.post('/auth/change-password', headers=XHR,
                            json={'old_password': 'x', 'new_password': 'NewSecret#2', 'confirm_password': 'NewSecret#2'})
        assert resp.status_code == 400
        audit.safe_log_event.assert_not_called()


# ─── ISC-17 · user ↔ employee link ───────────────────────────────────────────

def _put(api, uid, **payload):
    base = {'email': 'jan@test.pl', 'full_name': 'Jan Test', 'role': 'stylist', 'is_active': True}
    base.update(payload)
    return api.put(f'/system/users/api/{uid}', headers=XHR, json=base)


def _target(role='stylist', uid=20, active=True):
    return _user(role, uid, active, name='Jan Test', email='jan@test.pl')


class TestEmployeeLink:
    LINKED = {'id': 7, 'first_name': 'Jan', 'last_name': 'Kowalski'}

    def test_employee_link_null_unlinks_and_audits(self, api, app):
        repo = _user_repo_for(_target(), linked=self.LINKED)
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            resp = _put(api, 20, employee_id=None)
        assert resp.status_code == 200
        repo.unlink_employee.assert_called_once_with(20)
        repo.link_employee.assert_not_called()
        rows = [k for k in _audit_kwargs(app) if k.get('field_name') == 'pracownik']
        assert rows and rows[0]['old_value'] == 'Jan Kowalski' and rows[0]['new_value'] == '(brak)'

    def test_employee_link_relinks_to_free_employee(self, api, app):
        free = {'id': 9, 'first_name': 'Anna', 'last_name': 'Nowak', 'user_id': None}
        repo = _user_repo_for(_target(), linked=self.LINKED, link_state=free)
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            resp = _put(api, 20, employee_id=9)
        assert resp.status_code == 200
        repo.link_employee.assert_called_once_with(20, 9)
        rows = [k for k in _audit_kwargs(app) if k.get('field_name') == 'pracownik']
        assert rows[0]['new_value'] == 'Anna Nowak'

    def test_employee_link_absent_key_changes_nothing(self, api):
        repo = _user_repo_for(_target(), linked=self.LINKED)
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            resp = _put(api, 20)
        assert resp.status_code == 200
        repo.link_employee.assert_not_called()
        repo.unlink_employee.assert_not_called()

    def test_employee_link_same_employee_is_noop(self, api):
        same = {'id': 7, 'first_name': 'Jan', 'last_name': 'Kowalski', 'user_id': 20}
        repo = _user_repo_for(_target(), linked=self.LINKED, link_state=same)
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            assert _put(api, 20, employee_id=7).status_code == 200
        repo.link_employee.assert_not_called()

    def test_employee_link_rejects_employee_owned_by_another_account(self, api):
        taken = {'id': 9, 'first_name': 'Anna', 'last_name': 'Nowak', 'user_id': 99}
        repo = _user_repo_for(_target(), linked=self.LINKED, link_state=taken)
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            resp = _put(api, 20, employee_id=9)
        assert resp.status_code == 409
        repo.link_employee.assert_not_called()

    def test_employee_link_unknown_employee_is_404(self, api):
        repo = _user_repo_for(_target(), linked=None, link_state=None)
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            assert _put(api, 20, employee_id=12345).status_code == 404


class TestEmployeeLinkOnCreate:
    PAYLOAD = {'email': 'new@test.pl', 'full_name': 'Nowa Osoba', 'password': 'Passw0rd!x',
               'role': 'stylist', 'employee_id': 9}

    def _post(self, api, state):
        repo = MagicMock()
        repo.get_by_email.return_value = None
        repo.get_employee_link_state.return_value = state
        repo.create_user.return_value = 77
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo):
            return api.post('/system/users/api', headers=XHR, json=self.PAYLOAD), repo

    def test_employee_link_create_rejects_taken_employee(self, api):
        resp, repo = self._post(api, {'id': 9, 'first_name': 'Anna', 'last_name': 'Nowak', 'user_id': 5})
        assert resp.status_code == 409
        repo.create_user.assert_not_called()

    def test_employee_link_create_links_and_audits(self, api, app):
        resp, repo = self._post(api, {'id': 9, 'first_name': 'Anna', 'last_name': 'Nowak', 'user_id': None})
        assert resp.status_code == 201 and resp.get_json()['user_id'] == 77
        repo.link_employee.assert_called_once_with(77, 9)
        rows = [k for k in _audit_kwargs(app) if k.get('field_name') == 'pracownik']
        assert rows and rows[0]['action'] == 'CREATE' and rows[0]['new_value'] == 'Anna Nowak'
        assert 'Passw0rd!x' not in json.dumps(str(app.audit_repo.mock_calls))


# ─── ISC-18/19 · self protection + last superuser ────────────────────────────

class TestSelfProtection:
    def _run(self, api, actor, target, fn):
        repo = _user_repo_for(target)
        with as_user(actor), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('superuser', 'admin', 'stylist')):
            return fn(), repo

    def test_self_protection_cannot_change_own_role(self, api):
        su = _user('superuser', 1)
        resp, repo = self._run(api, su, su, lambda: _put(api, 1, role='admin'))
        assert resp.status_code == 400 and 'roli' in resp.get_json()['error'].lower()
        repo.update_user.assert_not_called()

    def test_self_protection_cannot_deactivate_self_via_update(self, api):
        su = _user('superuser', 1)
        resp, repo = self._run(api, su, su, lambda: _put(api, 1, role='superuser', is_active=False))
        assert resp.status_code == 400
        repo.update_user.assert_not_called()

    def test_self_protection_cannot_toggle_self(self, api):
        su = _user('superuser', 1)
        resp, repo = self._run(api, su, su, lambda: api.put('/system/users/api/1/toggle-active', headers=XHR))
        assert resp.status_code == 400
        repo.deactivate.assert_not_called()

    def test_self_protection_cannot_delete_self(self, api):
        su = _user('superuser', 1)
        resp, repo = self._run(api, su, su, lambda: api.delete('/system/users/api/1', headers=XHR))
        assert resp.status_code == 400
        repo.delete_user.assert_not_called()

    def test_self_protection_can_still_edit_own_name(self, api):
        su = _user('superuser', 1, name='Szef')
        resp, repo = self._run(api, su, su, lambda: _put(api, 1, role='superuser', full_name='Szefowa'))
        assert resp.status_code == 200
        repo.update_user.assert_called_once()


class TestLastSuperuser:
    def _go(self, api, count, fn):
        actor, target = _user('superuser', 1), _user('superuser', 2, name='Drugi', email='d@test.pl')
        repo = _user_repo_for(target, superusers=count)
        with as_user(actor), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('superuser', 'admin')):
            return fn(), repo

    def test_last_superuser_cannot_be_deactivated(self, api):
        resp, repo = self._go(api, 1, lambda: api.put('/system/users/api/2/toggle-active', headers=XHR))
        assert resp.status_code == 409
        repo.deactivate.assert_not_called()

    def test_last_superuser_cannot_be_deleted(self, api):
        resp, repo = self._go(api, 1, lambda: api.delete('/system/users/api/2', headers=XHR))
        assert resp.status_code == 409
        repo.delete_user.assert_not_called()

    def test_last_superuser_cannot_be_demoted(self, api):
        resp, repo = self._go(api, 1, lambda: _put(api, 2, role='admin', email='d@test.pl', full_name='Drugi'))
        assert resp.status_code == 409
        repo.update_user.assert_not_called()

    def test_last_superuser_guard_allows_when_another_remains(self, api):
        resp, repo = self._go(api, 2, lambda: api.put('/system/users/api/2/toggle-active', headers=XHR))
        assert resp.status_code == 200
        repo.deactivate.assert_called_once_with(2)


# ─── ISC-20/21/26 · user detail + form options ───────────────────────────────

class TestUserDetail:
    def test_user_detail_is_additive(self, api):
        target = _target()
        repo = _user_repo_for(target, linked={'id': 7, 'first_name': 'Jan', 'last_name': 'Kowalski'})
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            data = api.get('/system/users/api/20', headers=XHR).get_json()
        for key in ('id', 'email', 'full_name', 'role', 'is_active'):
            assert key in data['user']
        assert data['user']['role_display_name'] == 'Stylist'
        assert data['user']['last_login'] == '2026-09-01T12:30:00'
        assert data['user']['created_at'] == '2026-01-02T08:00:00'
        assert data['linked_employee'] == {'id': 7, 'first_name': 'Jan', 'last_name': 'Kowalski'}
        assert data['permissions']['appointments']['own_data'] is True
        assert 'module_display_names' in data

    def test_user_detail_orphan_role_falls_back_to_key(self, api):
        target = _user('ghost', 20, name='Duch', email='g@test.pl')
        repo = _user_repo_for(target)
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            data = api.get('/system/users/api/20', headers=XHR).get_json()
        assert data['user']['role_display_name'] == 'ghost' and data['permissions'] == {}

    def test_user_detail_admin_gets_403_for_superuser_target(self, api):
        repo = _user_repo_for(_user('superuser', 1))
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('superuser')):
            assert api.get('/system/users/api/1', headers=XHR).status_code == 403

    def test_user_detail_superuser_may_view_superuser(self, api):
        repo = _user_repo_for(_user('superuser', 2, name='Drugi', email='d@test.pl'))
        with as_user(_user('superuser', 1)), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('superuser')):
            assert api.get('/system/users/api/2', headers=XHR).status_code == 200


class TestFormOptions:
    def _opts(self, api, actor):
        urepo = MagicMock()
        urepo.get_available_employees.return_value = [{'id': 1, 'first_name': 'A', 'last_name': 'B'}]
        with as_user(actor), patch('routes.users.routes._user_repo', return_value=urepo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('superuser', 'admin', 'stylist')):
            return api.get('/system/users/api/form-options', headers=XHR).get_json()

    def test_form_options_admin_never_sees_superuser_role(self, api):
        names = [r['name'] for r in self._opts(api, _user('admin'))['roles']]
        assert 'superuser' not in names and 'stylist' in names

    def test_form_options_superuser_sees_all_roles(self, api):
        names = [r['name'] for r in self._opts(api, _user('superuser', 1))['roles']]
        assert 'superuser' in names

    def test_form_options_roles_carry_permission_summary(self, api):
        roles = self._opts(api, _user('admin'))['roles']
        assert all('permissions' in r and 'appointments' in r['permissions'] for r in roles)


# ─── ISC-22 · user audit rows ────────────────────────────────────────────────

class TestUserAudit:
    def test_user_audit_role_change_row(self, api, app):
        repo = _user_repo_for(_target('stylist'))
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist', 'receptionist')):
            assert _put(api, 20, role='receptionist').status_code == 200
        rows = [k for k in _audit_kwargs(app) if k.get('field_name') == 'rola']
        assert rows and (rows[0]['old_value'], rows[0]['new_value']) == ('stylist', 'receptionist')
        assert rows[0]['entity_type'] == 'user' and rows[0]['entity_id'] == 20

    def test_user_audit_status_change_through_update(self, api, app):
        repo = _user_repo_for(_target('stylist'))
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            assert _put(api, 20, is_active=False).status_code == 200
        assert any(k['action'] == 'STATUS_CHANGE' and k['new_value'] == 'nieaktywne' for k in _audit_kwargs(app))

    def test_user_audit_unchanged_update_writes_no_rows(self, api, app):
        repo = _user_repo_for(_target('stylist'))
        with as_user(_user('admin')), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            assert _put(api, 20).status_code == 200
        assert _audit_kwargs(app) == []

    def test_user_audit_admin_password_reset_has_no_secret(self, api, app):
        repo = _user_repo_for(_target('stylist'))
        with as_user(_user('superuser', 1)), patch('routes.users.routes._user_repo', return_value=repo), \
                patch('routes.users.routes._role_repo', return_value=_role_repo_for('stylist')):
            resp = api.put('/system/users/api/20', headers=XHR, json={'new_password': 'Sup3rSecret!'})
        assert resp.status_code == 200
        repo.update_password.assert_called_once_with(20, 'Sup3rSecret!')
        rows = [k for k in _audit_kwargs(app) if k['action'] == 'PASSWORD_RESET']
        assert rows and rows[0]['field_name'] == 'hasło'
        assert 'Sup3rSecret!' not in json.dumps(str(app.audit_repo.mock_calls))


# ─── ISC-27..30 · roles ──────────────────────────────────────────────────────

def _role_row(**kw):
    row = {'id': 5, 'name': 'manager', 'display_name': 'Kierownik', 'is_protected': False, 'access_count': 1}
    row.update(kw)
    return row


class TestRolesList:
    def test_roles_list_has_user_counts_and_display_names(self, api):
        from repositories.roles.role_repository import ALL_MODULES
        repo = MagicMock()
        repo.get_all.return_value = [_role_row(), _role_row(id=6, name='stylist', display_name='Stylistka')]
        repo.get_permissions.return_value = _perms(clients={'has_access': True})
        repo.get_user_counts.return_value = {'stylist': 3}
        with as_user(_user('superuser', 1)), patch('routes.roles.routes._role_repo', return_value=repo):
            data = api.get('/system/roles/api', headers=XHR).get_json()
        counts = {r['name']: r['user_count'] for r in data['roles']}
        assert counts == {'manager': 0, 'stylist': 3}
        assert set(ALL_MODULES) <= set(data['module_display_names'])
        assert data['module_display_names']['data_import']

    def test_roles_list_uses_one_grouped_count_query(self, api):
        repo = MagicMock()
        repo.get_all.return_value = [_role_row(id=i, name=f'r{i}') for i in range(4)]
        repo.get_permissions.return_value = _perms()
        repo.get_user_counts.return_value = {}
        with as_user(_user('superuser', 1)), patch('routes.roles.routes._role_repo', return_value=repo):
            api.get('/system/roles/api', headers=XHR)
        assert repo.get_user_counts.call_count == 1
        repo.count_users.assert_not_called()


class TestRoleDelete:
    def _delete(self, api, repo):
        with as_user(_user('superuser', 1)), patch('routes.roles.routes._role_repo', return_value=repo):
            return api.delete('/system/roles/api/5', headers=XHR)

    def test_role_delete_blocked_when_users_hold_it(self, api):
        repo = MagicMock()
        repo.get_by_id.return_value = _role_row()
        repo.count_users.return_value = 2
        resp = self._delete(api, repo)
        assert resp.status_code == 409 and 'użytkownik' in resp.get_json()['error']
        repo.delete.assert_not_called()

    def test_role_delete_protected_still_403(self, api):
        repo = MagicMock()
        repo.get_by_id.return_value = _role_row(is_protected=True)
        repo.count_users.return_value = 0
        assert self._delete(api, repo).status_code == 403
        repo.delete.assert_not_called()

    def test_role_delete_unused_role_succeeds(self, api, app):
        repo = MagicMock()
        repo.get_by_id.return_value = _role_row()
        repo.count_users.return_value = 0
        repo.delete.return_value = True
        assert self._delete(api, repo).status_code == 200
        repo.delete.assert_called_once_with(5)
        assert any(k['action'] == 'DELETE' and k['entity_type'] == 'role' for k in _audit_kwargs(app))


class TestRoleCreate:
    def _post(self, api, repo, **payload):
        body = {'name': 'head_stylist', 'display_name': 'Główna stylistka', 'permissions': {}}
        body.update(payload)
        with as_user(_user('superuser', 1)), patch('routes.roles.routes._role_repo', return_value=repo):
            return api.post('/system/roles/api', headers=XHR, json=body)

    def _repo(self):
        repo = MagicMock()
        repo.get_by_name.return_value = None
        repo.create.return_value = 42
        repo.get_permissions.return_value = _perms()
        return repo

    @pytest.mark.parametrize('bad', ['1abc', 'a', 'x' * 60, 'ma-ły', 'bad!name', '../etc', 'ÓŻ', '_lead'])
    def test_role_create_rejects_bad_names(self, api, bad):
        repo = self._repo()
        assert self._post(api, repo, name=bad).status_code == 400
        repo.create.assert_not_called()

    def test_role_create_normalises_spaces_and_case(self, api):
        repo = self._repo()
        assert self._post(api, repo, name='Head Stylist').status_code == 201
        repo.create.assert_called_once_with('head_stylist', 'Główna stylistka')

    def test_role_create_accepts_full_flag_dicts(self, api):
        repo = self._repo()
        perms = {'services': _flags(has_access=True, read_only=True, can_edit_price_history=True)}
        assert self._post(api, repo, permissions=perms).status_code == 201
        repo.set_permissions.assert_called_once_with(42, perms)


class TestRoleRoundtrip:
    def _conn(self):
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value = cur
        ctx = MagicMock()
        ctx.__enter__.return_value = conn
        ctx.__exit__.return_value = False
        return ctx, cur

    def test_role_roundtrip_set_permissions_persists_every_flag(self):
        from repositories.roles.role_repository import RoleRepository
        ctx, cur = self._conn()
        flags = _flags(has_access=True, read_only=True, own_data=False, can_edit_price_history=True, can_send_sms=False)
        with patch('repositories.roles.role_repository.get_db_connection', return_value=ctx):
            RoleRepository().set_permissions(3, {'services': flags})
        params = [c.args[1] for c in cur.execute.call_args_list if c.args[1][1] == 'services'][0]
        assert params == (3, 'services', True, True, False, True, False)

    def test_role_roundtrip_get_permissions_returns_stored_flags(self):
        from repositories.roles.role_repository import ALL_MODULES, RoleRepository
        ctx, cur = self._conn()
        cur.fetchall.return_value = [{'module_name': 'services', 'has_access': True, 'read_only': True,
                                      'own_data': False, 'can_edit_price_history': True, 'can_send_sms': False}]
        with patch('repositories.roles.role_repository.get_db_connection', return_value=ctx):
            perms = RoleRepository().get_permissions(3)
        assert perms['services'] == _flags(has_access=True, read_only=True, can_edit_price_history=True)
        assert set(perms) == set(ALL_MODULES)

    def test_role_roundtrip_user_count_queries(self):
        from repositories.roles.role_repository import RoleRepository
        ctx, cur = self._conn()
        cur.fetchone.return_value = {'n': 3}
        cur.fetchall.return_value = [{'role': 'stylist', 'n': 3}, {'role': 'admin', 'n': 1}]
        with patch('repositories.roles.role_repository.get_db_connection', return_value=ctx):
            repo = RoleRepository()
            assert repo.count_users('stylist') == 3
            assert repo.get_user_counts() == {'stylist': 3, 'admin': 1}


class TestUserRepositoryAdditions:
    def test_count_active_superusers_query(self):
        from repositories.users.user_repository import UserRepository
        with patch.object(UserRepository, '_fetch_one', return_value={'n': 2}) as fetch:
            assert UserRepository().count_active_superusers() == 2
        q = fetch.call_args[0][0].lower()
        assert 'superuser' in q and 'is_active' in q

    def test_get_employee_link_state_selects_owner(self):
        from repositories.users.user_repository import UserRepository
        row = {'id': 9, 'first_name': 'A', 'last_name': 'B', 'user_id': None}
        with patch.object(UserRepository, '_fetch_one', return_value=row):
            assert UserRepository().get_employee_link_state(9) == row
