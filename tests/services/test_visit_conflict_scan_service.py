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

    def test_rejects_future_end_date(self, app):
        with app.app_context():
            svc = _svc_with_mocks()
            with pytest.raises(Exception):
                svc.scan(TODAY - timedelta(days=10), TODAY + timedelta(days=1))
            svc.appt_repo.get_candidates_for_conflict_scan.assert_not_called()

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


class TestApply:
    def test_soft_deletes_only_superseded_appointments(self, app, monkeypatch):
        with app.app_context():
            svc = _svc_with_mocks()
            d = TODAY - timedelta(days=3)
            rows = [
                _row(101, appointment_date=d, start_time=time(10, 0), end_time=time(11, 0)),
                _row(205, appointment_date=d, start_time=time(10, 30), end_time=time(11, 30)),
            ]
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = rows
            svc.appt_repo.soft_delete_as_superseded.return_value = True
            svc.income_repo.soft_delete_by_appointment.return_value = True

            import services.visit_conflict_scan_service as mod
            from contextlib import contextmanager

            @contextmanager
            def fake_txn():
                yield None
            monkeypatch.setattr(mod, 'managed_transaction', fake_txn)

            result = svc.apply(d, d)

            svc.appt_repo.soft_delete_as_superseded.assert_called_once()
            args = svc.appt_repo.soft_delete_as_superseded.call_args.args
            assert args[0] == 101
            assert '#205' in args[1]

            svc.income_repo.soft_delete_by_appointment.assert_called_once_with(101)
            assert result == {'group_count': 1, 'removed_count': 1, 'removed_ids': [101]}

    def test_no_groups_means_no_repo_calls(self, app, monkeypatch):
        with app.app_context():
            svc = _svc_with_mocks()
            svc.appt_repo.get_candidates_for_conflict_scan.return_value = []

            import services.visit_conflict_scan_service as mod
            from contextlib import contextmanager

            @contextmanager
            def fake_txn():
                yield None
            monkeypatch.setattr(mod, 'managed_transaction', fake_txn)

            result = svc.apply(TODAY - timedelta(days=10), TODAY)

            svc.appt_repo.soft_delete_as_superseded.assert_not_called()
            svc.income_repo.soft_delete_by_appointment.assert_not_called()
            assert result == {'group_count': 0, 'removed_count': 0, 'removed_ids': []}
