"""GET /api/appointments/income-summary — the "Przychód: actual / expected" footers.

The privacy rule lives server-side: a viewer gets figures only for (a) the employee
linked to their own user, or (b) anyone, when they are a superuser with an
unrestricted 'employees' grant. Everything else must come back empty AND must not
even reach the repository.

Same mocking pattern as tests/routes/test_permission_boundary_fixes.py.
"""
from contextlib import ExitStack
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

XHR = {'X-Requested-With': 'XMLHttpRequest'}
URL = '/api/appointments/income-summary'
RANGE = {'start_date': '2026-10-01', 'end_date': '2026-10-07'}

ROW = {'day': date(2026, 10, 1), 'employee_id': 8, 'actual': 120, 'expected': 300.5}


def _user(role='stylist', uid=5):
    from database.models import User
    return User(email='t@test.pl', password_hash='x', full_name='Test User', role=role, is_active=True, id=uid)


@pytest.fixture
def api(app):
    app.config['WTF_CSRF_ENABLED'] = False
    return app.test_client()


def _flags(employees=None, appointments=None):
    default = {'has_access': True, 'read_only': False, 'own_data': False}
    return {'appointments': appointments or default, 'employees': employees or default}


def _as(user, role_flags, *, own_employee_id=None, rows=(ROW,)):
    """Returns (ExitStack, repo_mock). Caller enters the stack."""
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda role, module: dict(
        role_flags.get(module, {'has_access': False, 'read_only': False, 'own_data': False})
    )
    emp_repo = MagicMock()
    emp_repo.get_by_user_id.return_value = {'id': own_employee_id} if own_employee_id is not None else None
    income_repo = MagicMock()
    income_repo.get_daily_summary.return_value = list(rows)

    stack = ExitStack()
    stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('repositories.employees.employee_repository.EmployeeRepository', return_value=emp_repo))
    stack.enter_context(patch('routes.appointment_routes.IncomeRepository', return_value=income_repo))
    stack.enter_context(patch('flask_login.utils._get_user', return_value=user))
    return stack, income_repo


def _get(api, **params):
    return api.get(URL, headers=XHR, query_string={**RANGE, **params})


class TestSuperuserFullGrant:
    def test_sees_everyone_and_rows_are_serialised(self, api):
        stack, repo = _as(_user('superuser'), _flags(), own_employee_id=3)
        with stack:
            body = _get(api).get_json()
        assert body['scope'] == 'all'
        assert body['rows'] == [{'date': '2026-10-01', 'employee_id': 8, 'actual': 120.0, 'expected': 300.5}]
        repo.get_daily_summary.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 7), None)

    def test_employee_filter_is_passed_through(self, api):
        stack, repo = _as(_user('superuser'), _flags(), own_employee_id=3)
        with stack:
            _get(api, employee_id=8)
        repo.get_daily_summary.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 7), 8)


class TestSuperuserWithoutFullGrant:
    @pytest.mark.parametrize('employees', [
        {'has_access': True, 'read_only': True, 'own_data': False},
        {'has_access': True, 'read_only': False, 'own_data': True},
        {'has_access': False, 'read_only': False, 'own_data': False},
    ])
    def test_falls_back_to_own_employee_only(self, api, employees):
        stack, repo = _as(_user('superuser'), _flags(employees=employees), own_employee_id=3)
        with stack:
            body = _get(api).get_json()
        assert body['scope'] == 'own' and body['own_employee_id'] == 3
        repo.get_daily_summary.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 7), 3)

    def test_someone_elses_income_is_not_even_queried(self, api):
        stack, repo = _as(_user('superuser'), _flags(employees={'has_access': True, 'read_only': True, 'own_data': False}), own_employee_id=3)
        with stack:
            body = _get(api, employee_id=8).get_json()
        assert body['rows'] == []
        repo.get_daily_summary.assert_not_called()


class TestOrdinaryUser:
    def test_a_full_employees_grant_is_not_enough_without_superuser(self, api):
        stack, repo = _as(_user('admin'), _flags(), own_employee_id=3)
        with stack:
            body = _get(api).get_json()
        assert body['scope'] == 'own'
        repo.get_daily_summary.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 7), 3)

    def test_own_employee_is_visible(self, api):
        stack, repo = _as(_user(), _flags(), own_employee_id=8)
        with stack:
            body = _get(api, employee_id=8).get_json()
        assert len(body['rows']) == 1
        repo.get_daily_summary.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 7), 8)

    def test_another_employee_is_empty_and_never_queried(self, api):
        stack, repo = _as(_user(), _flags(), own_employee_id=8)
        with stack:
            body = _get(api, employee_id=9).get_json()
        assert body['rows'] == [] and body['scope'] == 'own'
        repo.get_daily_summary.assert_not_called()

    def test_no_linked_employee_sees_nothing(self, api):
        stack, repo = _as(_user(), _flags(), own_employee_id=None)
        with stack:
            body = _get(api).get_json()
        assert body['scope'] == 'none' and body['rows'] == []
        repo.get_daily_summary.assert_not_called()

    def test_appointments_own_data_role_is_pinned_to_own_employee(self, api):
        own_data = {'has_access': True, 'read_only': False, 'own_data': True}
        stack, repo = _as(_user(), _flags(appointments=own_data), own_employee_id=8)
        with stack:
            _get(api, employee_id=9)
        # Asked for 9, but the role is pinned to its own employee first (as in get_appointments),
        # so the only thing ever queried is employee 8.
        repo.get_daily_summary.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 7), 8)

    def test_no_appointments_access_is_forbidden(self, api):
        stack, repo = _as(_user(), _flags(appointments={'has_access': False, 'read_only': False, 'own_data': False}), own_employee_id=8)
        with stack:
            resp = _get(api)
        assert resp.status_code in (302, 403)
        repo.get_daily_summary.assert_not_called()


class TestValidation:
    @pytest.mark.parametrize('params', [
        {'start_date': None, 'end_date': None},
        {'start_date': '2026-10-07', 'end_date': '2026-10-01'},
        {'start_date': 'nope', 'end_date': '2026-10-01'},
        {'start_date': '2026-01-01', 'end_date': '2027-12-31'},
    ])
    def test_bad_range_is_400(self, api, params):
        stack, repo = _as(_user('superuser'), _flags(), own_employee_id=3)
        with stack:
            resp = api.get(URL, headers=XHR, query_string={k: v for k, v in params.items() if v})
        assert resp.status_code == 400
        repo.get_daily_summary.assert_not_called()
