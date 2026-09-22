"""Permission-boundary fixes — bilanse urlopów write/own-data scoping and the
new formy_zatrudnienia_required decorator (RBAC hardening, 2026-09-22).

Repositories are mocked at their real import sites (`module_permission_required`/
`own_data_employee_id`/`get_linked_employee` all do `from repositories.X import Y`
INLINE, so patching the class in its home module is what actually takes effect —
the same pattern used by tests/routes/test_users_roles_profile_routes.py).
"""
import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

XHR = {'X-Requested-With': 'XMLHttpRequest'}


def _user(role='stylist', uid=5, name='Test User', email='t@test.pl'):
    from database.models import User
    return User(email=email, password_hash='x', full_name=name, role=role, is_active=True, id=uid)


@pytest.fixture
def api(app):
    app.config['WTF_CSRF_ENABLED'] = False
    app.employee_repo = MagicMock()
    app.absence_category_repo = MagicMock()
    app.audit_repo = MagicMock()
    app.absence_adjustment_repo = MagicMock()
    return app.test_client()


def _perm_stack(role_flags, *, own_employee_id=None):
    """Wires role_repo.get_permission_flags(role, module) -> role_flags[module]
    and the caller's linked-employee id (None = no linked employee)."""
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda role, module: dict(
        role_flags.get(module, {'has_access': False, 'read_only': False, 'own_data': False})
    )
    emp_repo = MagicMock()
    emp_repo.get_by_user_id.return_value = {'id': own_employee_id} if own_employee_id is not None else None

    stack = ExitStack()
    stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('repositories.employees.employee_repository.EmployeeRepository', return_value=emp_repo))
    return stack


def _as(user, role_flags, *, own_employee_id=None):
    stack = _perm_stack(role_flags, own_employee_id=own_employee_id)
    stack.enter_context(patch('flask_login.utils._get_user', return_value=user))
    return stack


FULL_ABSENCES = {'absences': {'has_access': True, 'read_only': False, 'own_data': False}}
READONLY_ABSENCES = {'absences': {'has_access': True, 'read_only': True, 'own_data': False}}
OWN_DATA_ABSENCES = {'absences': {'has_access': True, 'read_only': False, 'own_data': True}}
NO_ABSENCES = {'absences': {'has_access': False, 'read_only': False, 'own_data': False}}


# ─── ISC-4 · balance mutation endpoints: read_only + own_data enforcement ────

class TestBalanceLimitWrite:
    def _post(self, api, employee_id):
        return api.post(f'/api/employees/{employee_id}/absence-limits', headers=XHR, json={'category_id': 1, 'max_value': 10})

    def test_read_only_role_cannot_set_limit_for_anyone(self, api):
        with _as(_user(), READONLY_ABSENCES):
            resp = self._post(api, 999)
        assert resp.status_code == 403

    def test_own_data_role_cannot_set_limit_for_another_employee(self, api):
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7):
            resp = self._post(api, 999)
        assert resp.status_code == 403
        assert 'pracownika' in resp.get_json()['error']

    def test_own_data_role_can_set_limit_for_own_employee(self, api):
        svc = MagicMock()
        svc.set_limit.return_value = 1
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7), patch('routes.absence_balance_routes.AbsenceBalanceService', return_value=svc):
            resp = self._post(api, 7)
        assert resp.status_code == 201

    def test_own_data_role_with_no_linked_employee_is_denied_for_any_real_employee(self, api):
        # own_data_employee_id's -1 sentinel (no linked employee) never equals
        # a real positive employee_id, so every employee is out of scope —
        # Flask's <int:> converter doesn't route a literal -1 anyway, so this
        # proves the sentinel via an ordinary id rather than the URL itself.
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=None):
            resp = self._post(api, 5)
        assert resp.status_code == 403

    def test_full_access_role_can_set_limit_for_any_employee(self, api):
        svc = MagicMock()
        svc.set_limit.return_value = 1
        with _as(_user(role='admin'), FULL_ABSENCES), patch('routes.absence_balance_routes.AbsenceBalanceService', return_value=svc):
            resp = self._post(api, 999)
        assert resp.status_code == 201

    def test_no_absences_access_denied(self, api):
        with _as(_user(), NO_ABSENCES):
            resp = self._post(api, 5)
        assert resp.status_code == 403


class TestBalanceLimitDelete:
    def test_read_only_cannot_delete_limit(self, api):
        with _as(_user(), READONLY_ABSENCES):
            resp = api.delete('/api/employees/5/absence-limits/1', headers=XHR)
        assert resp.status_code == 403

    def test_own_data_cannot_delete_another_employees_limit(self, api):
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7):
            resp = api.delete('/api/employees/999/absence-limits/1', headers=XHR)
        assert resp.status_code == 403

    def test_own_data_can_delete_own_limit(self, api):
        svc = MagicMock()
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7), patch('routes.absence_balance_routes.AbsenceBalanceService', return_value=svc):
            resp = api.delete('/api/employees/7/absence-limits/1', headers=XHR)
        assert resp.status_code == 200


class TestBalanceAdjustmentWrite:
    def _post(self, api, employee_id):
        return api.post(f'/api/employees/{employee_id}/absence-adjustments', headers=XHR,
                        json={'category_id': 1, 'delta_value': 2, 'reason': 'test'})

    def test_read_only_cannot_create_adjustment(self, api):
        with _as(_user(), READONLY_ABSENCES):
            resp = self._post(api, 5)
        assert resp.status_code == 403

    def test_own_data_cannot_adjust_another_employee(self, api):
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7):
            resp = self._post(api, 999)
        assert resp.status_code == 403

    def test_own_data_can_adjust_own_balance(self, api):
        svc = MagicMock()
        svc.create_adjustment.return_value = 1
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7), patch('routes.absence_balance_routes.AbsenceBalanceService', return_value=svc):
            resp = self._post(api, 7)
        assert resp.status_code == 201

    def test_delete_adjustment_blocked_for_another_employee(self, api):
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7):
            resp = api.delete('/api/employees/999/absence-adjustments/1', headers=XHR)
        assert resp.status_code == 403


class TestBalanceAuditScope:
    def test_read_only_can_view_history_for_anyone(self, api):
        # read_only only blocks MUTATING methods — GET history stays reachable
        # for a full-visibility read-only role (own_data is what scopes reads).
        with _as(_user(), READONLY_ABSENCES):
            resp = api.get('/api/employees/999/absence-adjustments', headers=XHR)
        assert resp.status_code == 200

    def test_own_data_cannot_view_anothers_adjustment_history(self, api):
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7):
            resp = api.get('/api/employees/999/absence-adjustments', headers=XHR)
        assert resp.status_code == 403

    def test_own_data_cannot_clear_anothers_audit(self, api):
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7):
            resp = api.delete('/api/employees/999/absence-balance-audit', headers=XHR)
        assert resp.status_code == 403


# ─── ISC-5 · balances_summary scoped to own employee ─────────────────────────

class TestBalancesSummaryScope:
    def test_full_access_sees_every_employee(self, api):
        svc = MagicMock()
        svc.get_balance_summary_for_list.return_value = {1: {'a': 1}, 2: {'b': 2}}
        with _as(_user(role='admin'), FULL_ABSENCES), patch('routes.absence_balance_routes.AbsenceBalanceService', return_value=svc):
            data = api.get('/api/absence-balances/summary', headers=XHR).get_json()
        assert set(data['balances'].keys()) == {'1', '2'} or set(data['balances'].keys()) == {1, 2}

    def test_own_data_sees_only_self(self, api):
        svc = MagicMock()
        svc.get_balance_summary_for_list.return_value = {1: {'a': 1}, 7: {'b': 2}}
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7), patch('routes.absence_balance_routes.AbsenceBalanceService', return_value=svc):
            data = api.get('/api/absence-balances/summary', headers=XHR).get_json()
        assert list(data['balances'].keys()) in (['7'], [7])

    def test_own_data_with_no_row_yet_gets_empty_summary(self, api):
        svc = MagicMock()
        svc.get_balance_summary_for_list.return_value = {1: {'a': 1}}
        with _as(_user(), OWN_DATA_ABSENCES, own_employee_id=7), patch('routes.absence_balance_routes.AbsenceBalanceService', return_value=svc):
            data = api.get('/api/absence-balances/summary', headers=XHR).get_json()
        assert data['balances'] == {}


# ─── ISC-10 · formy_zatrudnienia_required ────────────────────────────────────

FULL_EMPLOYEES = {'employees': {'has_access': True, 'read_only': False, 'own_data': False}}
READONLY_EMPLOYEES = {'employees': {'has_access': True, 'read_only': True, 'own_data': False}}
OWN_DATA_EMPLOYEES = {'employees': {'has_access': True, 'read_only': False, 'own_data': True}}
NO_EMPLOYEES = {'employees': {'has_access': False, 'read_only': False, 'own_data': False}}


class TestFormyZatrudnieniaGate:
    def test_superuser_with_full_grant_can_list(self, api):
        app_ = api.application
        app_.forma_zatrudnienia_repo = MagicMock()
        app_.forma_zatrudnienia_repo.get_all.return_value = []
        with _as(_user(role='superuser'), FULL_EMPLOYEES):
            resp = api.get('/api/formy-zatrudnienia', headers=XHR)
        assert resp.status_code == 200

    def test_superuser_with_read_only_employees_denied(self, api):
        with _as(_user(role='superuser'), READONLY_EMPLOYEES):
            resp = api.get('/api/formy-zatrudnienia', headers=XHR)
        assert resp.status_code == 403

    def test_superuser_with_own_data_employees_denied(self, api):
        with _as(_user(role='superuser'), OWN_DATA_EMPLOYEES):
            resp = api.get('/api/formy-zatrudnienia', headers=XHR)
        assert resp.status_code == 403

    def test_superuser_with_no_employees_access_denied(self, api):
        with _as(_user(role='superuser'), NO_EMPLOYEES):
            resp = api.get('/api/formy-zatrudnienia', headers=XHR)
        assert resp.status_code == 403

    def test_admin_with_full_employees_grant_still_denied(self, api):
        """The literal ask: superuser-only, regardless of anyone else's employees grant."""
        with _as(_user(role='admin'), FULL_EMPLOYEES):
            resp = api.get('/api/formy-zatrudnienia', headers=XHR)
        assert resp.status_code == 403

    def test_get_is_not_exempted_unlike_module_permission_required(self, api):
        """Unlike module_permission_required, GET is not exempted here — this
        page has no legitimate read-only audience."""
        with _as(_user(role='superuser'), READONLY_EMPLOYEES):
            resp = api.get('/api/formy-zatrudnienia/1', headers=XHR)
        assert resp.status_code == 403

    def test_create_denied_for_read_only_superuser(self, api):
        with _as(_user(role='superuser'), READONLY_EMPLOYEES):
            resp = api.post('/api/formy-zatrudnienia', headers=XHR, json={'nazwa': 'B2B'})
        assert resp.status_code == 403

    def test_create_allowed_for_qualifying_superuser(self, api):
        app_ = api.application
        app_.forma_zatrudnienia_repo = MagicMock()
        app_.forma_zatrudnienia_repo.create.return_value = 1
        with _as(_user(role='superuser'), FULL_EMPLOYEES):
            resp = api.post('/api/formy-zatrudnienia', headers=XHR, json={'nazwa': 'B2B'})
        assert resp.status_code == 200

    def test_anonymous_redirected_not_500(self, api):
        resp = api.get('/api/formy-zatrudnienia', headers=XHR)
        assert resp.status_code in (302, 401)
