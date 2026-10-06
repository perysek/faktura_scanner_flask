"""GET /api/appointments/<id>/visit-link — the employee's in-app way to open the
`/visit/<token>` start/end form. It unlocks 20 minutes before the visit starts.

Regression (SMS review P0-1, found while fixing it): the gate compared the
naive-Warsaw appointment time with `datetime.now()` — naive UTC on the server —
so it unlocked ~2 h LATE (1 h in winter). It must use the Warsaw clock.
`now_local` is patched, so the old code (which read the real clock) fails the
"too early" case no matter when or where the suite runs.
"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

ROUTES = 'routes.appointment_routes'
VISIT_DAY = date(2026, 7, 1)          # CEST (UTC+2): 14:00 Warsaw == 12:00 UTC


def _user():
    from database.models import User
    return User(email='t@test.pl', password_hash='x', full_name='Test User',
                role='stylist', is_active=True, id=5)


def _get(app, warsaw_now, *, status='scheduled', employee_id=7, own_employee_id=7):
    appt = {'id': 100, 'employee_id': employee_id, 'status': status, 'client_id': 1,
            'appointment_date': VISIT_DAY, 'start_time': '14:00:00', 'employee_token': 'tok-123'}
    repo = MagicMock()
    repo.get_by_id.return_value = appt
    emp_repo = MagicMock()
    emp_repo.get_by_user_id.return_value = {'id': own_employee_id}
    app.config['BASE_URL'] = 'https://salon.example'
    with patch('flask_login.utils._get_user', return_value=_user()), \
         patch(f'{ROUTES}.AppointmentRepository', return_value=repo), \
         patch('repositories.employees.employee_repository.EmployeeRepository', return_value=emp_repo), \
         patch(f'{ROUTES}.now_local', return_value=warsaw_now):
        return app.test_client().get('/api/appointments/100/visit-link')


@pytest.mark.parametrize('now, expect_open', [
    (datetime(2026, 7, 1, 13, 30), False),    # 30 min before: still locked
    (datetime(2026, 7, 1, 13, 39), False),    # 21 min before: still locked
    (datetime(2026, 7, 1, 13, 40), True),     # exactly 20 min before: opens
    (datetime(2026, 7, 1, 13, 45), True),
    (datetime(2026, 7, 1, 14, 5), True),      # already started: stays open
])
def test_gate_opens_at_twenty_minutes_before_warsaw_start(app, now, expect_open):
    resp = _get(app, now)
    body = resp.get_json()
    if expect_open:
        assert resp.status_code == 200, body
        assert body['url'] == 'https://salon.example/visit/tok-123'
    else:
        assert resp.status_code == 425, body
        assert body['too_early'] is True


def test_remaining_minutes_are_reported_against_the_warsaw_clock(app):
    resp = _get(app, datetime(2026, 7, 1, 13, 20))        # 40 min before -> 20 min until it opens
    assert resp.status_code == 425
    assert resp.get_json()['minutes_remaining'] == 20


def test_in_progress_visit_bypasses_the_time_gate(app):
    resp = _get(app, datetime(2026, 7, 1, 9, 0), status='in_progress')
    assert resp.status_code == 200


def test_other_employees_visit_is_forbidden(app):
    resp = _get(app, datetime(2026, 7, 1, 13, 45), employee_id=7, own_employee_id=8)
    assert resp.status_code == 403
