"""GET /api/income/ledger — Finanse → Przychody (register + stats cards).

Gate: the 'income' module (Poziomy dostępu → "Przychody", one on/off switch).
A role without it must be refused AND must not reach the repository.
Same mocking pattern as tests/routes/test_income_summary_route.py.
"""
from contextlib import ExitStack
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

XHR = {'X-Requested-With': 'XMLHttpRequest'}
URL = '/api/income/ledger'
RANGE = {'start_date': '2026-10-01', 'end_date': '2026-10-31'}

ON = {'has_access': True, 'read_only': False, 'own_data': False}
OFF = {'has_access': False, 'read_only': False, 'own_data': False}


def _rec(rid, gross, share, new=False, method='gotówka'):
    return {
        'id': rid, 'appointment_id': 100 + rid, 'payment_date': date(2026, 10, rid), 'appointment_date': date(2026, 10, rid),
        'client_id': rid, 'client_name': f'Klient {rid}', 'employee_id': 8, 'employee_name': 'Anna Nowak',
        'gross_amount': gross, 'employee_share': share, 'net_amount': gross - share,
        'payment_method': method, 'is_new_client': new,
    }


RECORDS = [_rec(1, 200, 80, new=True), _rec(2, 100, 40, method='karta'), _rec(3, 300, 0)]
LOST = [
    {'kind': 'client_cancel', 'visits': 2, 'amount': 150},
    {'kind': 'no_show', 'visits': 1, 'amount': 90.5},
    {'kind': 'salon_cancel', 'visits': 1, 'amount': 120},
]


def _user(role='admin', uid=5):
    from database.models import User
    return User(email='t@test.pl', password_hash='x', full_name='Test User', role=role, is_active=True, id=uid)


@pytest.fixture
def api(app):
    app.config['WTF_CSRF_ENABLED'] = False
    return app.test_client()


def _as(income_flags, records=RECORDS, lost=LOST):
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda role, module: dict(income_flags if module == 'income' else ON)
    income_repo = MagicMock()
    income_repo.get_ledger.return_value = list(records)
    income_repo.get_lost_summary.return_value = list(lost)

    stack = ExitStack()
    stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('routes.income_routes.IncomeRepository', return_value=income_repo))
    stack.enter_context(patch('flask_login.utils._get_user', return_value=_user()))
    return stack, income_repo


def _get(api, **params):
    return api.get(URL, headers=XHR, query_string={**RANGE, **params})


class TestGate:
    def test_without_income_module_is_refused_before_the_repository(self, api):
        stack, repo = _as(OFF)
        with stack:
            resp = _get(api)
        assert resp.status_code == 403
        repo.get_ledger.assert_not_called()
        repo.get_lost_summary.assert_not_called()

    def test_with_income_module_gets_the_register(self, api):
        stack, repo = _as(ON)
        with stack:
            resp = _get(api)
        assert resp.status_code == 200
        repo.get_ledger.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 31))
        repo.get_lost_summary.assert_called_once_with(date(2026, 10, 1), date(2026, 10, 31))


class TestPayload:
    def test_records_are_serialised(self, api):
        stack, _ = _as(ON)
        with stack:
            body = _get(api).get_json()
        first = body['records'][0]
        assert first['payment_date'] == '2026-10-01'
        assert first['net_amount'] == 120
        assert first['is_new_client'] is True
        assert body['start_date'] == '2026-10-01' and body['end_date'] == '2026-10-31'

    def test_stats_cards(self, api):
        stack, _ = _as(ON)
        with stack:
            stats = _get(api).get_json()['stats']
        assert stats['count'] == 3
        assert stats['total_gross'] == 600
        assert stats['total_net'] == 480
        assert stats['avg_gross'] == 200
        assert stats['new_client_gross'] == 200
        assert stats['new_client_visits'] == 1
        assert stats['new_client_pct'] == pytest.approx(33.3)
        assert stats['lost']['client_cancel'] == {'visits': 2, 'amount': 150.0}
        assert stats['lost']['no_show'] == {'visits': 1, 'amount': 90.5}
        assert stats['lost']['salon_cancel'] == {'visits': 1, 'amount': 120.0}
        assert stats['lost']['visits'] == 4
        assert stats['lost']['amount'] == pytest.approx(360.5)

    def test_empty_period_has_zeroed_stats_not_division_errors(self, api):
        stack, _ = _as(ON, records=[], lost=[])
        with stack:
            stats = _get(api).get_json()['stats']
        assert stats['count'] == 0 and stats['avg_gross'] == 0 and stats['new_client_pct'] == 0
        assert stats['lost']['salon_cancel'] == {'visits': 0, 'amount': 0.0}


class TestValidation:
    @pytest.mark.parametrize('params', [
        {'start_date': 'nope'},
        {'end_date': ''},
        {'start_date': '2026-10-31', 'end_date': '2026-10-01'},
        {'start_date': '2020-01-01', 'end_date': '2026-10-01'},
    ])
    def test_bad_ranges_are_400(self, api, params):
        stack, repo = _as(ON)
        with stack:
            resp = _get(api, **params)
        assert resp.status_code == 400
        repo.get_ledger.assert_not_called()


def test_income_module_is_registered_for_the_role_editor():
    from repositories.roles.role_repository import ALL_MODULES, MODULE_DISPLAY_NAMES
    from config.auth_config import MODULE_PERMISSIONS
    assert ALL_MODULES[-1] == 'income'  # rendered last = below the existing sections
    assert MODULE_DISPLAY_NAMES['income'] == 'Przychody'
    assert MODULE_PERMISSIONS['income'] == ['superuser', 'admin']
