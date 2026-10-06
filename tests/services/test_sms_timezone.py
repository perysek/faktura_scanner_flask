"""P0-1 regression tests — SMS timing must use the *Warsaw* wall-clock frame.

Appointments are stored as naive Warsaw local time while production runs on a
UTC clock/session. Every comparison against "now" therefore has to use
`utils.timezone.now_local()` (or `NOW() AT TIME ZONE 'Europe/Warsaw'` in SQL),
otherwise reminders fire 1-2 h off — the employee "Za 20 min wizyta" text even
landed *after* the visit had started.

These tests patch `now_local` instead of the process clock, so they fail on the
old `datetime.now()` code regardless of the machine's own timezone.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from utils.timezone import WARSAW_TZ

SVC = 'services.sms_service'
REPO = 'repositories.appointments.appointment_repository'

# 2026-07-01 is CEST (UTC+2): 12:00 Warsaw == 10:00 UTC.
NOW_WARSAW = datetime(2026, 7, 1, 12, 0)


def _service_with_sms_active(active=True):
    from services.sms_service import SmsService
    svc = SmsService()
    svc.get_settings = Mock(return_value={'is_active': active})
    return svc


class TestEmployeeReminderScheduling:
    def _schedule(self, appointment_dt, *, active=True):
        svc = _service_with_sms_active(active)
        event_repo = Mock()
        event_repo.create.return_value = 77
        with patch(f'{SVC}.now_local', return_value=NOW_WARSAW), \
             patch('repositories.sms.sms_event_repository.SmsEventRepository', return_value=event_repo):
            result = svc.schedule_employee_reminder(5, appointment_dt)
        return result, event_repo

    def test_event_is_stored_as_the_correct_instant(self):
        # Visit 14:00 Warsaw -> reminder 13:40 Warsaw == 11:40 UTC.
        result, repo = self._schedule(datetime(2026, 7, 1, 14, 0))

        assert result == 77
        scheduled_at = repo.create.call_args.args[2]
        assert scheduled_at.tzinfo is not None, 'naive value would be read as UTC by the TIMESTAMPTZ column'
        assert scheduled_at.astimezone(timezone.utc) == datetime(2026, 7, 1, 11, 40, tzinfo=timezone.utc)

    def test_winter_time_uses_the_cet_offset(self):
        # 2026-01-15 is CET (UTC+1): visit 14:00 Warsaw -> reminder 13:40 Warsaw == 12:40 UTC.
        svc = _service_with_sms_active()
        repo = Mock()
        repo.create.return_value = 1
        with patch(f'{SVC}.now_local', return_value=datetime(2026, 1, 15, 8, 0)), \
             patch('repositories.sms.sms_event_repository.SmsEventRepository', return_value=repo):
            svc.schedule_employee_reminder(5, datetime(2026, 1, 15, 14, 0))
        scheduled_at = repo.create.call_args.args[2]
        assert scheduled_at.astimezone(timezone.utc) == datetime(2026, 1, 15, 12, 40, tzinfo=timezone.utc)

    def test_window_already_passed_in_warsaw_frame_is_not_scheduled(self):
        # Visit 12:10 -> reminder would be 11:50, but it is already 12:00 in Warsaw.
        result, repo = self._schedule(datetime(2026, 7, 1, 12, 10))
        assert result is None
        repo.create.assert_not_called()

    def test_cancels_previous_pending_reminder_before_creating_a_new_one(self):
        _, repo = self._schedule(datetime(2026, 7, 1, 15, 0))
        repo.cancel_type_for_appointment.assert_called_once_with(5, 'employee_visit_reminder')

    def test_nothing_scheduled_when_sms_is_off(self):
        result, repo = self._schedule(datetime(2026, 7, 1, 15, 0), active=False)
        assert result is None
        repo.create.assert_not_called()


class TestHoursBeforePlaceholder:
    def test_hours_before_is_measured_against_warsaw_now(self, app):
        from services.sms_service import SmsService
        appt = {'id': 1, 'appointment_date': '2026-07-01', 'start_time': '14:00:00',
                'rating_token': ''}
        client = {'first_name': 'Anna'}
        msg_type = {'template_text': 'Za {hours_before}h wizyta', 'send_hours_before': 24,
                    'include_confirm_link': False}
        with app.app_context(), \
             patch(f'{SVC}.now_local', return_value=NOW_WARSAW), \
             patch('repositories.appointments.appointment_service_repository.AppointmentServiceRepository') as asr:
            asr.return_value.get_all_for_appointment.return_value = []
            body = SmsService()._build_message(appt, client, msg_type, 'http://x/confirm/t')
        assert body == 'Za 2h wizyta'


class TestDueQueriesUseWarsawFrame:
    """SQL-shape guard (the suite mocks the DB). The semantic proof — a UTC
    session returning the right rows — was run against a real Postgres and is
    documented in the change notes."""

    @staticmethod
    def _run(method_name, *args):
        from repositories.appointments.appointment_repository import AppointmentRepository
        cur = Mock()
        cur.fetchall.return_value = []
        cur.fetchone.return_value = {'cnt': 0}
        conn = Mock()
        conn.cursor.return_value = cur
        conn.__enter__ = Mock(return_value=conn)
        conn.__exit__ = Mock(return_value=False)
        with patch(f'{REPO}.get_db_connection', return_value=conn), \
             patch('config.admin_view.hidden_ids_to_exclude', return_value=()):
            getattr(AppointmentRepository(), method_name)(*args)
        return cur.execute.call_args.args[0]

    @pytest.mark.parametrize('method, args', [
        ('get_appointments_due_for_type', (24, 'reminder_1')),
        ('get_past_pending_appointments', ()),
        ('count_past_pending_appointments', ()),
    ])
    def test_every_now_is_converted_to_warsaw(self, app, method, args):
        with app.app_context():
            sql = self._run(method, *args)
        bare = sql.replace("(NOW() AT TIME ZONE 'Europe/Warsaw')", '')
        assert "NOW() AT TIME ZONE 'Europe/Warsaw'" in sql
        assert 'NOW()' not in bare, 'a bare NOW() compares Warsaw wall-clock against a UTC instant'

    def test_due_query_skips_held_appointments(self, app):
        with app.app_context():
            sql = self._run('get_appointments_due_for_type', 24, 'reminder_1')
        assert 'a.sms_hold IS NOT TRUE' in sql


class TestVisitLinkGateAndPastStatusUseWarsawClock:
    """The employee visit-link gate and the past-visit validator had the same
    naive-UTC bug (link unlocked ~2 h late; 'past' recognised ~2 h late)."""

    def test_no_zero_arg_datetime_now_call_left_in_sms_adjacent_paths(self):
        """AST check (not a text grep, so explanatory comments can't trip it):
        `datetime.now()` with no tz argument is naive-UTC on the server."""
        import ast
        import inspect
        import routes.appointment_routes as ar
        import services.sms_service as ss
        for module in (ar, ss):
            tree = ast.parse(inspect.getsource(module))
            offenders = [
                n.lineno for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == 'now'
                and isinstance(n.func.value, ast.Name) and n.func.value.id == 'datetime'
                and not n.args and not n.keywords
            ]
            assert not offenders, f'{module.__name__}: naive-UTC datetime.now() at lines {offenders}'
