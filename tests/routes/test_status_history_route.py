"""GET /api/appointments/<id>/status-history — the "Historia zmian statusu" projection.

Regression for the principal's report (2026-10-07): a visit moved confirmed -> scheduled on the
EDIT page kept showing "Potwierdzona" with its old date, because the skeleton remembered the first
time each status was reached and had no notion of going backwards. The status endpoint cannot move
a visit backwards (VALID_TRANSITIONS), the edit page can — and writes an ordinary audit row, so the
audit list updated while the skeleton did not.

Repositories are patched at the route's import site; auth follows tests/routes/test_visit_notes_routes.py.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

XHR = {'X-Requested-With': 'XMLHttpRequest'}
FULL = {'appointments': {'has_access': True, 'read_only': False, 'own_data': False}}


def _user():
    from database.models import User
    return User(email='t@test.pl', password_hash='x', full_name='Test User',
                role='superuser', is_active=True, id=5)


def _logged_in():
    role_repo = MagicMock()
    role_repo.get_permission_flags.side_effect = lambda role, module: dict(
        FULL.get(module, {'has_access': False, 'read_only': False, 'own_data': False}))
    stack = ExitStack()
    stack.enter_context(patch('repositories.roles.role_repository.RoleRepository', return_value=role_repo))
    stack.enter_context(patch('flask_login.utils._get_user', return_value=_user()))
    stack.enter_context(patch('config.admin_view.get_hidden_employee_ids', return_value=()))
    return stack


def _row(status, **extra):
    row = {'id': 100, 'status': status, 'total_duration': 60,
           'created_at': datetime(2026, 10, 1, 8, 0),            # naive UTC -> 10:00 Warsaw
           'rescheduled_to_appointment_id': None,
           'confirmation_updated_at': None, 'cancelled_at': None}
    row.update(extra)
    return row


def _entry(old, new, hour, minute=0, who='Recepcja', day=2):
    return {'old_value': old, 'new_value': new, 'user_name': who,
            'timestamp': datetime(2026, 10, day, hour, minute)}      # naive UTC


def _get(client, row, entries, sms=None, sms_error=None):
    repo = MagicMock()
    repo.get_by_id.return_value = row
    audit = MagicMock()
    audit.get_by_entity.return_value = entries
    reminders = MagicMock()
    if sms_error is not None:
        reminders.return_value.get_for_appointment.side_effect = sms_error
    else:
        reminders.return_value.get_for_appointment.return_value = sms or []
    with _logged_in(), \
         patch('routes.appointment_routes.AppointmentRepository', return_value=repo), \
         patch('routes.appointment_routes.AuditRepository', return_value=audit), \
         patch('routes.appointment_routes.SmsReminderRepository', reminders):
        resp = client.get('/api/appointments/100/status-history', headers=XHR)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


def _sms(sms_id, hour, *, status='sent', auto=True, name='Prośba o potwierdzenie'):
    return {'id': sms_id, 'sent_at': datetime(2026, 10, 2, hour, 0, tzinfo=timezone.utc),
            'message_type_key': 'confirmation_request', 'type_name': name, 'status': status,
            'created_by_user_id': None if auto else 5, 'created_by_name': 'System (auto)' if auto else 'Ola',
            'sender_name': None if auto else 'Ola K.', 'error_message': None}


class TestRevertOnTheEditPage:
    def test_confirmed_back_to_scheduled_unreaches_potwierdzona(self, client):
        data = _get(client, _row('scheduled'), [
            _entry('scheduled', 'confirmed', 9),
            _entry('confirmed', 'scheduled', 11),          # the edit page's UPDATE row
        ])
        assert data['skeleton']['confirmed_at'] is None
        assert data['skeleton']['scheduled_at'] is not None
        # the audit list DID update before the fix — it must keep both rows, in order
        assert [(h['old_status'], h['new_status']) for h in data['history']] == [
            ('scheduled', 'confirmed'), ('confirmed', 'scheduled')]

    def test_reconfirming_dates_potwierdzona_with_the_latest_confirmation(self, client):
        data = _get(client, _row('confirmed'), [
            _entry('scheduled', 'confirmed', 9),
            _entry('confirmed', 'scheduled', 10),
            _entry('scheduled', 'confirmed', 13, 30),
        ])
        # 13:30 UTC on 2 Oct = 15:30 Warsaw (CEST)
        assert data['skeleton']['confirmed_at'].endswith('15:30:00')

    def test_completed_back_to_in_progress_drops_the_finish_and_the_duration(self, client):
        data = _get(client, _row('in_progress'), [
            _entry('scheduled', 'in_progress', 8),
            _entry('in_progress', 'completed', 9),
            _entry('completed', 'in_progress', 10),
        ])
        assert data['skeleton']['started_at'] is not None
        assert data['skeleton']['finished_at'] is None
        assert data['duration']['actual_minutes'] is None

    def test_cancelled_back_to_scheduled_clears_cancellation_and_confirmation(self, client):
        data = _get(client, _row('scheduled'), [
            _entry('scheduled', 'confirmed', 8),
            _entry('confirmed', 'cancelled', 9),
            _entry('cancelled', 'scheduled', 10),
        ])
        assert data['skeleton']['cancelled_at'] is None
        assert data['skeleton']['confirmed_at'] is None


class TestSuffixedAuditValues:
    """update_appointment_status audits `"<status> (<reason>)"` — it never equalled the bare status."""

    def test_cancelled_with_a_reason_still_marks_anulowana_and_keeps_the_reason(self, client):
        data = _get(client, _row('cancelled'), [
            _entry('confirmed', 'cancelled (klientka zachorowała)', 9),
        ])
        assert data['skeleton']['cancelled_at'] is not None
        entry = data['history'][0]
        assert entry['new_status'] == 'cancelled'
        assert entry['detail'] == 'klientka zachorowała'

    def test_salon_retiming_suffix_is_split_off_the_status(self, client):
        data = _get(client, _row('scheduled'), [
            _entry('confirmed', 'scheduled (zmiana terminu przez salon)', 9),
        ])
        assert data['history'][0]['new_status'] == 'scheduled'
        assert data['history'][0]['detail'] == 'zmiana terminu przez salon'


class TestNeverContradictsTheCurrentStatus:
    def test_empty_audit_with_a_scheduled_row_reaches_nothing_else(self, client):
        data = _get(client, _row('scheduled'), [])
        sk = data['skeleton']
        assert sk['confirmed_at'] is sk['cancelled_at'] is sk['started_at'] is sk['finished_at'] is None

    def test_an_audit_gap_is_filled_from_the_row_for_the_current_status(self, client):
        data = _get(client, _row('confirmed', confirmation_updated_at=datetime(2026, 10, 2, 7, 0)), [])
        assert data['skeleton']['confirmed_at'] is not None


class TestSmsSendsInTheTimeline:
    """Task 3: the visit's SMS sends ride along so the page can show them among the status changes."""

    def test_sends_come_oldest_first_in_warsaw_time_with_who_sent_them(self, client):
        data = _get(client, _row('scheduled'), [], sms=[_sms(2, 9, auto=False), _sms(1, 6)])
        assert [s['id'] for s in data['sms']] == [1, 2]                        # 06:00Z before 09:00Z
        assert data['sms'][0]['sent_at'] == '2026-10-02T08:00:00'               # CEST = UTC+2
        assert data['sms'][0]['automatic'] is True and data['sms'][0]['sent_by'] == 'System (auto)'
        assert data['sms'][1]['automatic'] is False and data['sms'][1]['sent_by'] == 'Ola K.'

    def test_two_sends_in_the_same_second_keep_creation_order(self, client):
        """Regression (found by the scratch-DB integration run): the repository returns newest first and
        sent_at is second-precision once formatted, so a stable sort alone left same-second rows reversed."""
        newest_first = [_sms(2, 9, status='failed', name='Przypomnienie 2h'), _sms(1, 9)]   # both 09:00:00Z
        data = _get(client, _row('scheduled'), [], sms=newest_first)
        assert [s['id'] for s in data['sms']] == [1, 2]

    def test_a_failed_send_keeps_its_status_so_the_ui_can_flag_it(self, client):
        data = _get(client, _row('scheduled'), [], sms=[_sms(1, 6, status='failed')])
        assert data['sms'][0]['status'] == 'failed'

    def test_no_sends_is_an_empty_list_not_a_missing_key(self, client):
        assert _get(client, _row('scheduled'), [])['sms'] == []

    def test_a_broken_sms_lookup_never_takes_the_status_history_down(self, client):
        entries = [_entry('scheduled', 'confirmed', 9)]
        data = _get(client, _row('confirmed'), entries, sms_error=RuntimeError('sms tables unavailable'))
        assert data['sms'] == []
        assert data['skeleton']['confirmed_at'] is not None and len(data['history']) == 1
