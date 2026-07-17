"""Tests for VisitConflictScanService — detects past-visit duplicates created by
caldis.pl reschedules: (H1) same client/employee/service with overlapping time
slots, (H2) same client/service/day booked with a different employee. The
appointment with the highest id in a group is the "final" one; the rest are
superseded and (on apply()) soft-deleted along with their income record.
"""
from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import Mock, call

import pytest

TODAY = date.today()


def _svc_with_mocks():
    from services.visit_conflict_scan_service import VisitConflictScanService
    svc = VisitConflictScanService()
    svc.appt_repo = Mock()
    svc.income_repo = Mock()
    return svc


def _row(id, client_id=1, employee_id=1, service_id=1, appointment_date=None,
         start_time=time(10, 0), end_time=time(11, 0), status='completed',
         client_name='Anna Kowalska', employee_name='Kasia', service_name='Strzyżenie'):
    return {
        'id': id, 'client_id': client_id, 'employee_id': employee_id,
        'service_id': service_id,
        'appointment_date': appointment_date or (TODAY - timedelta(days=5)),
        'start_time': start_time, 'end_time': end_time, 'status': status,
        'total_price': Decimal('80.00'),
        'client_name': client_name, 'employee_name': employee_name,
        'service_name': service_name,
    }


class TestValidateRange:
    def test_rejects_start_after_end(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            with pytest.raises(Exception):
                svc.scan(TODAY, TODAY - timedelta(days=1))
            svc.appt_repo.get_candidates_for_conflict_scan.assert_not_called()

    def test_accepts_future_end_date(self, app):
        """Future ranges are allowed — the scanner also catches duplicate future
        bookings left behind by a reschedule that hasn't happened yet."""
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = []
            result = svc.scan(TODAY - timedelta(days=10), TODAY + timedelta(days=90))
            assert result['group_count'] == 0
            svc.appt_repo.get_candidates_for_conflict_scan.assert_called_once_with(
                TODAY - timedelta(days=10), TODAY + timedelta(days=90)
            )

    def test_accepts_today_as_end_date(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = []
            result = svc.scan(TODAY - timedelta(days=10), TODAY)
            assert result['group_count'] == 0


class TestScanNoConflicts:
    def test_empty_candidates(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = []
            result = svc.scan(TODAY - timedelta(days=30), TODAY)
            assert result == {
                'candidate_count': 0, 'group_count': 0,
                'superseded_count': 0, 'groups': [],
            }

    def test_single_visit_is_not_a_conflict(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = [_row(1)]
            result = svc.scan(TODAY - timedelta(days=30), TODAY)
            assert result['group_count'] == 0

    def test_same_employee_back_to_back_is_not_a_conflict(self, app):
        """Two real same-day visits with the same stylist that don't overlap
        (11:00 ends exactly when the next starts) must not be flagged."""
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY - timedelta(days=3)
            rows = [
                _row(1, appointment_date=d, start_time=time(10, 0), end_time=time(11, 0)),
                _row(2, appointment_date=d, start_time=time(11, 0), end_time=time(12, 0)),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            result = svc.scan(d, d)
            assert result['group_count'] == 0

    def test_different_service_is_not_a_conflict(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY - timedelta(days=3)
            rows = [
                _row(1, service_id=1, appointment_date=d, employee_id=2),
                _row(2, service_id=2, appointment_date=d, employee_id=3),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            result = svc.scan(d, d)
            assert result['group_count'] == 0

    def test_different_days_same_employee_is_not_a_conflict(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            rows = [
                _row(1, appointment_date=TODAY - timedelta(days=10)),
                _row(2, appointment_date=TODAY - timedelta(days=3)),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            result = svc.scan(TODAY - timedelta(days=30), TODAY)
            assert result['group_count'] == 0


class TestScanDetectsTimeOverlap:
    def test_overlapping_same_employee_flagged(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY - timedelta(days=3)
            rows = [
                _row(101, appointment_date=d, start_time=time(10, 0), end_time=time(11, 0)),
                _row(205, appointment_date=d, start_time=time(10, 30), end_time=time(11, 30)),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            result = svc.scan(d, d)

            assert result['group_count'] == 1
            assert result['superseded_count'] == 1
            group = result['groups'][0]
            assert group['reasons'] == ['time_overlap']
            assert group['keeper_id'] == 205  # highest id wins
            by_id = {a['id']: a for a in group['appointments']}
            assert by_id[205]['is_keeper'] is True
            assert by_id[101]['is_keeper'] is False


class TestScanDetectsSameDayDifferentStylist:
    def test_same_day_different_employee_flagged_even_without_overlap(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY - timedelta(days=3)
            rows = [
                _row(10, employee_id=1, appointment_date=d, start_time=time(9, 0), end_time=time(10, 0)),
                _row(20, employee_id=2, appointment_date=d, start_time=time(15, 0), end_time=time(16, 0)),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            result = svc.scan(d, d)

            assert result['group_count'] == 1
            group = result['groups'][0]
            assert group['reasons'] == ['same_day_different_stylist']
            assert group['keeper_id'] == 20

    def test_transitive_chain_merges_into_one_group_with_both_reasons(self, app):
        """A(overlaps B, same stylist) + B(same day, different stylist than C) →
        one connected group; the highest id anywhere in the chain is the keeper."""
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY - timedelta(days=3)
            rows = [
                _row(1, employee_id=1, appointment_date=d, start_time=time(9, 0), end_time=time(10, 0)),
                _row(2, employee_id=1, appointment_date=d, start_time=time(9, 30), end_time=time(10, 30)),
                _row(3, employee_id=2, appointment_date=d, start_time=time(15, 0), end_time=time(16, 0)),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            result = svc.scan(d, d)

            assert result['group_count'] == 1
            group = result['groups'][0]
            assert set(group['reasons']) == {'time_overlap', 'same_day_different_stylist'}
            assert group['keeper_id'] == 3
            assert len(group['appointments']) == 3


def _fake_txn(monkeypatch):
    import services.visit_conflict_scan_service as mod
    from contextlib import contextmanager

    @contextmanager
    def fake_txn():
        yield None
    monkeypatch.setattr(mod, 'managed_transaction', fake_txn)


class TestApply:
    def test_soft_deletes_only_superseded_completed_appointments(self, app, monkeypatch):
        """A 'completed' visit is terminal — VALID_TRANSITIONS has no path to
        'cancelled' for it, so apply() must fall back to soft-delete."""
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY - timedelta(days=3)
            rows = [
                _row(101, appointment_date=d, start_time=time(10, 0), end_time=time(11, 0), status='completed'),
                _row(205, appointment_date=d, start_time=time(10, 30), end_time=time(11, 30), status='completed'),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            svc.appt_repo.soft_delete_as_superseded.return_value = True
            svc.income_repo.soft_delete_by_appointment.return_value = True
            _fake_txn(monkeypatch)

            result = svc.apply(d, d)

            svc.appt_repo.soft_delete_as_superseded.assert_called_once()
            args = svc.appt_repo.soft_delete_as_superseded.call_args.args
            assert args[0] == 101
            assert '#205' in args[1]

            svc.income_repo.soft_delete_by_appointment.assert_called_once_with(101)
            svc.appt_repo.update_status.assert_not_called()
            assert result == {
                'group_count': 1, 'removed_count': 1, 'removed_ids': [101],
                'cancelled_count': 0, 'cancelled_ids': [],
                'soft_deleted_count': 1, 'soft_deleted_ids': [101],
            }

    def test_cancels_superseded_future_appointment_instead_of_soft_deleting(self, app, monkeypatch):
        """A 'scheduled' visit hasn't happened yet — cancel_appointment()'s
        underlying transition IS legal, so apply() should cancel it properly
        (visible on the calendar) rather than silently hiding it."""
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY + timedelta(days=5)
            rows = [
                _row(301, appointment_date=d, start_time=time(9, 0), end_time=time(10, 0), status='scheduled'),
                _row(302, appointment_date=d, start_time=time(9, 30), end_time=time(10, 30), status='confirmed'),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            svc.appt_repo.update_status.return_value = True
            _fake_txn(monkeypatch)

            result = svc.apply(d, d)

            svc.appt_repo.update_status.assert_called_once()
            args = svc.appt_repo.update_status.call_args.args
            assert args[0] == 301
            assert args[1] == 'cancelled'
            assert '#302' in args[2]

            svc.appt_repo.soft_delete_as_superseded.assert_not_called()
            svc.income_repo.soft_delete_by_appointment.assert_not_called()
            assert result == {
                'group_count': 1, 'removed_count': 1, 'removed_ids': [301],
                'cancelled_count': 1, 'cancelled_ids': [301],
                'soft_deleted_count': 0, 'soft_deleted_ids': [],
            }

    def test_mixed_batch_cancels_future_and_soft_deletes_past_in_one_apply(self, app, monkeypatch):
        with app.app_context():
            svc = _svc_with_mocks()
            past = TODAY - timedelta(days=3)
            future = TODAY + timedelta(days=5)
            rows = [
                _row(101, client_id=1, appointment_date=past, start_time=time(10, 0), end_time=time(11, 0), status='completed'),
                _row(205, client_id=1, appointment_date=past, start_time=time(10, 30), end_time=time(11, 30), status='completed'),
                _row(301, client_id=2, appointment_date=future, start_time=time(9, 0), end_time=time(10, 0), status='scheduled'),
                _row(302, client_id=2, appointment_date=future, start_time=time(9, 30), end_time=time(10, 30), status='confirmed'),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            svc.appt_repo.soft_delete_as_superseded.return_value = True
            svc.income_repo.soft_delete_by_appointment.return_value = True
            svc.appt_repo.update_status.return_value = True
            _fake_txn(monkeypatch)

            result = svc.apply(past, future)

            assert result['group_count'] == 2
            assert result['cancelled_ids'] == [301]
            assert result['soft_deleted_ids'] == [101]
            assert result['removed_ids'] == [301, 101]

    def test_no_groups_means_no_repo_calls(self, app, monkeypatch):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = []
            _fake_txn(monkeypatch)

            result = svc.apply(TODAY - timedelta(days=10), TODAY)

            svc.appt_repo.soft_delete_as_superseded.assert_not_called()
            svc.income_repo.soft_delete_by_appointment.assert_not_called()
            svc.appt_repo.update_status.assert_not_called()
            assert result == {
                'group_count': 0, 'removed_count': 0, 'removed_ids': [],
                'cancelled_count': 0, 'cancelled_ids': [],
                'soft_deleted_count': 0, 'soft_deleted_ids': [],
            }


class TestPlannedAction:
    def test_keeper_has_no_planned_action(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY - timedelta(days=3)
            rows = [
                _row(101, appointment_date=d, start_time=time(10, 0), end_time=time(11, 0), status='completed'),
                _row(205, appointment_date=d, start_time=time(10, 30), end_time=time(11, 30), status='completed'),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            result = svc.scan(d, d)
            by_id = {a['id']: a for a in result['groups'][0]['appointments']}
            assert by_id[205]['planned_action'] is None  # keeper
            assert by_id[101]['planned_action'] == 'soft_delete'

    def test_superseded_scheduled_appointment_planned_action_is_cancel(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY + timedelta(days=5)
            rows = [
                _row(301, appointment_date=d, start_time=time(9, 0), end_time=time(10, 0), status='scheduled'),
                _row(302, appointment_date=d, start_time=time(9, 30), end_time=time(10, 30), status='confirmed'),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            result = svc.scan(d, d)
            by_id = {a['id']: a for a in result['groups'][0]['appointments']}
            assert by_id[301]['planned_action'] == 'cancel'
            assert by_id[302]['planned_action'] is None  # keeper
