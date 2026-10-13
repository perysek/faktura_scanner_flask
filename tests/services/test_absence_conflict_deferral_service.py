"""Absence conflict modal — "Zatwierdź mimo to" deferral + "Wyślij wiadomość" SMS queue.

Contract:
  * an unresolved visit is parked with valid_for = visit start − 48 h (Warsaw wall-clock,
    stored timezone-aware) and an `absence_cancellation` SMS event for that same moment;
  * at valid_for the scheduler cancels the visit only if it STILL collides with the approved
    absence — otherwise the queued "your visit is cancelled" text is withdrawn;
  * a failed auto-cancel never leaves its cancellation text queued;
  * "Wyślij wiadomość" queues the SMS matching each visit's latest resolution, for the next tick,
    and ignores visits with no resolution on this absence.
"""
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from services.absence_conflict_deferral_service import (
    AUTO_CANCEL_OFFSET_HOURS,
    AUTO_CANCEL_REASON,
    AbsenceConflictDeferralService,
    compute_valid_for,
)
from utils.timezone import WARSAW_TZ


def _svc(**overrides):
    deps = dict(pending_repo=MagicMock(), event_repo=MagicMock(), absence_repo=MagicMock(),
                resolution_repo=MagicMock(), appointment_service=MagicMock())
    deps.update(overrides)
    return AbsenceConflictDeferralService(**deps), deps


def _conflict(appt_id=11, d='2026-11-20', start='10:00:00', end='11:00:00'):
    return {'appointment_id': appt_id, 'date': d, 'start_time': start, 'end_time': end,
            'client_name': 'Anna X', 'service_name': 'Strzyżenie', 'status': 'scheduled'}


class TestValidFor:
    def test_is_visit_start_minus_48h_in_warsaw(self):
        vf = compute_valid_for('2026-11-20', '10:00:00')
        assert AUTO_CANCEL_OFFSET_HOURS == 48
        assert vf == datetime(2026, 11, 18, 10, 0, tzinfo=WARSAW_TZ)
        assert vf.tzinfo is not None   # TIMESTAMPTZ needs an aware value (UTC DB session)

    def test_accepts_date_and_time_objects(self):
        assert compute_valid_for(date(2026, 7, 1), time(9, 30)) == datetime(2026, 6, 29, 9, 30, tzinfo=WARSAW_TZ)

    def test_summer_offset_is_respected(self):
        # 10:00 CEST = 08:00 UTC
        assert compute_valid_for('2026-07-03', '10:00').astimezone(timezone.utc).hour == 8


class TestDeferUnresolved:
    def test_parks_each_visit_with_a_cancellation_sms_at_valid_for(self):
        svc, d = _svc()
        d['event_repo'].create.return_value = 501
        d['pending_repo'].create.return_value = 7

        out = svc.defer_unresolved(3, 42, [_conflict()], created_by_user_id=9)

        vf = datetime(2026, 11, 18, 10, 0, tzinfo=WARSAW_TZ)
        # held: no scheduler (incl. the legacy app's) may send it before the visit is cancelled
        d['event_repo'].create.assert_called_once_with(11, 'absence_cancellation', vf, status='held')
        kwargs = d['pending_repo'].create.call_args.kwargs
        assert kwargs['absence_id'] == 3 and kwargs['appointment_id'] == 11 and kwargs['employee_id'] == 42
        assert kwargs['valid_for'] == vf and kwargs['sms_event_id'] == 501 and kwargs['created_by_user_id'] == 9
        assert out == [{'appointment_id': 11, 'valid_for': vf.isoformat()}]

    def test_multi_service_visit_repeated_by_the_overlap_query_is_parked_once(self):
        svc, d = _svc()
        d['pending_repo'].create.return_value = 1
        svc.defer_unresolved(3, 42, [_conflict(), _conflict()], created_by_user_id=9)
        assert d['pending_repo'].create.call_count == 1
        assert d['event_repo'].create.call_count == 1

    def test_already_parked_visit_drops_the_duplicate_sms(self):
        svc, d = _svc()
        d['event_repo'].create.return_value = 502
        d['pending_repo'].create.return_value = None   # ON CONFLICT DO NOTHING
        assert svc.defer_unresolved(3, 42, [_conflict()], created_by_user_id=9) == []
        d['event_repo'].mark_skipped.assert_called_once()
        assert d['event_repo'].mark_skipped.call_args.args[0] == 502


class TestQueueResolutionSms:
    def test_type_follows_latest_resolution_and_fires_next_tick(self):
        svc, d = _svc()
        d['resolution_repo'].list_for_absence.return_value = [   # newest first
            {'appointment_id': 1, 'resolution_type': 'cancelled'},
            {'appointment_id': 2, 'resolution_type': 'reassigned'},
            {'appointment_id': 3, 'resolution_type': 'rescheduled'},
            {'appointment_id': 1, 'resolution_type': 'reassigned'},   # older — ignored
        ]
        d['event_repo'].create.side_effect = [10, 20, 30]

        before = datetime.now(timezone.utc)
        out = svc.queue_resolution_sms(5, [3, 1, 2])

        types = {c.args[0]: c.args[1] for c in d['event_repo'].create.call_args_list}
        assert types == {1: 'absence_cancellation', 2: 'absence_visit_update', 3: 'absence_visit_update'}
        for c in d['event_repo'].create.call_args_list:
            assert before - timedelta(seconds=1) <= c.args[2] <= datetime.now(timezone.utc)
        assert [q['appointment_id'] for q in out] == [1, 2, 3]

    def test_visit_without_resolution_on_this_absence_is_ignored(self):
        svc, d = _svc()
        d['resolution_repo'].list_for_absence.return_value = [{'appointment_id': 1, 'resolution_type': 'cancelled'}]
        assert [q['appointment_id'] for q in svc.queue_resolution_sms(5, [1, 999])] == [1]
        assert d['event_repo'].create.call_count == 1

    def test_nothing_marked_touches_nothing(self):
        svc, d = _svc()
        assert svc.queue_resolution_sms(5, []) == []
        d['resolution_repo'].list_for_absence.assert_not_called()


def _due_row(**kw):
    row = {'id': 70, 'absence_id': 3, 'appointment_id': 11, 'sms_event_id': 501, 'created_by_user_id': 9}
    row.update(kw)
    return row


def _approved_absence():
    return {'id': 3, 'employee_id': 42, 'status': 'approved', 'is_deleted': False,
            'date_from': date(2026, 11, 20), 'date_to': date(2026, 11, 20), 'time_from': None, 'time_to': None}


class TestProcessDue:
    def test_still_colliding_visit_is_cancelled_and_logged(self):
        svc, d = _svc()
        d['pending_repo'].get_due.return_value = [_due_row()]
        d['absence_repo'].get_by_id.return_value = _approved_absence()
        d['absence_repo'].get_overlapping_appointments.return_value = [{'id': 11}]

        assert svc.process_due() == {'cancelled': 1, 'resolved': 0, 'failed': 0}
        d['appointment_service'].cancel_appointment.assert_called_once_with(11, AUTO_CANCEL_REASON)
        res = d['resolution_repo'].create.call_args.kwargs
        assert res['resolution_type'] == 'cancelled' and res['resolved_by_user_id'] == 9
        d['pending_repo'].mark.assert_called_once_with(70, 'auto_cancelled')
        d['event_repo'].release.assert_called_once_with(501)   # only now may the text go out
        d['event_repo'].mark_skipped.assert_not_called()

    def test_visit_resolved_meanwhile_is_left_alone_and_its_sms_withdrawn(self):
        svc, d = _svc()
        d['pending_repo'].get_due.return_value = [_due_row()]
        d['absence_repo'].get_by_id.return_value = _approved_absence()
        d['absence_repo'].get_overlapping_appointments.return_value = []   # reassigned elsewhere

        assert svc.process_due() == {'cancelled': 0, 'resolved': 1, 'failed': 0}
        d['appointment_service'].cancel_appointment.assert_not_called()
        d['event_repo'].release.assert_not_called()
        d['event_repo'].mark_skipped.assert_called_once()
        assert d['event_repo'].mark_skipped.call_args.args[0] == 501
        d['pending_repo'].mark.assert_called_once_with(70, 'resolved')

    @pytest.mark.parametrize('absence', [None, {**_approved_absence(), 'status': 'cancelled'},
                                         {**_approved_absence(), 'is_deleted': True}],
                             ids=['gone', 'absence-cancelled', 'absence-deleted'])
    def test_no_longer_approved_absence_cancels_nothing(self, absence):
        svc, d = _svc()
        d['pending_repo'].get_due.return_value = [_due_row()]
        d['absence_repo'].get_by_id.return_value = absence
        assert svc.process_due()['resolved'] == 1
        d['appointment_service'].cancel_appointment.assert_not_called()

    def test_failed_cancel_withdraws_the_sms_and_marks_failed(self):
        svc, d = _svc()
        d['pending_repo'].get_due.return_value = [_due_row()]
        d['absence_repo'].get_by_id.return_value = _approved_absence()
        d['absence_repo'].get_overlapping_appointments.return_value = [{'id': 11}]
        d['appointment_service'].cancel_appointment.side_effect = Exception('in_progress → cancelled')

        assert svc.process_due() == {'cancelled': 0, 'resolved': 0, 'failed': 1}
        d['event_repo'].mark_skipped.assert_called_once()
        assert d['pending_repo'].mark.call_args.args[:2] == (70, 'failed')
        d['event_repo'].release.assert_not_called()
