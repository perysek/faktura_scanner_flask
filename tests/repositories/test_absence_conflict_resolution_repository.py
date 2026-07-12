"""Tests for AbsenceConflictResolutionRepository (Phase 0) — the audit trail
behind bulk-apply and the 'Historia rozwiązań' viewer in the supervisor
conflict-resolution modal (AD-9).
"""
from unittest.mock import Mock, patch

MODULE = 'repositories.absences.absence_conflict_resolution_repository'


def _write_conn(new_id=1):
    cursor = Mock()
    cursor.fetchone.return_value = {'id': new_id}
    conn = Mock()
    conn.cursor.return_value = cursor
    return conn, cursor


def _read_conn(rows):
    cur = Mock()
    cur.fetchall.return_value = rows
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


class TestCreate:
    def test_reassigned_round_trip(self, app):
        from repositories.absences.absence_conflict_resolution_repository import (
            AbsenceConflictResolutionRepository,
        )
        conn, cursor = _write_conn(new_id=5)
        with app.app_context(), patch(f'{MODULE}.get_db_connection', return_value=conn):
            new_id = AbsenceConflictResolutionRepository().create(
                absence_id=1, appointment_id=42, resolution_type='reassigned',
                resolved_by_user_id=9, previous_employee_id=2, new_employee_id=3,
            )
        assert new_id == 5
        sql, params = cursor.execute.call_args.args
        assert 'reassigned' in params
        assert 2 in params and 3 in params
        conn.commit.assert_called_once()

    def test_rescheduled_round_trip(self, app):
        from datetime import date, time
        from repositories.absences.absence_conflict_resolution_repository import (
            AbsenceConflictResolutionRepository,
        )
        conn, cursor = _write_conn(new_id=6)
        with app.app_context(), patch(f'{MODULE}.get_db_connection', return_value=conn):
            AbsenceConflictResolutionRepository().create(
                absence_id=1, appointment_id=42, resolution_type='rescheduled',
                resolved_by_user_id=9,
                previous_date=date(2026, 7, 20), previous_start_time=time(10, 0),
                previous_end_time=time(11, 0),
                new_date=date(2026, 7, 21), new_start_time=time(9, 0),
                new_end_time=time(10, 0),
            )
        params = cursor.execute.call_args.args[1]
        assert 'rescheduled' in params

    def test_cancelled_round_trip(self, app):
        from repositories.absences.absence_conflict_resolution_repository import (
            AbsenceConflictResolutionRepository,
        )
        conn, cursor = _write_conn(new_id=7)
        with app.app_context(), patch(f'{MODULE}.get_db_connection', return_value=conn):
            AbsenceConflictResolutionRepository().create(
                absence_id=1, appointment_id=42, resolution_type='cancelled',
                resolved_by_user_id=9, cancellation_reason='Brak zastępstwa',
            )
        params = cursor.execute.call_args.args[1]
        assert 'cancelled' in params
        assert 'Brak zastępstwa' in params


class TestListForAbsence:
    def test_returns_rows_ordered_by_resolved_at(self, app):
        from repositories.absences.absence_conflict_resolution_repository import (
            AbsenceConflictResolutionRepository,
        )
        rows = [{'id': 2, 'resolution_type': 'reassigned'}, {'id': 1, 'resolution_type': 'cancelled'}]
        conn, cur = _read_conn(rows)
        with app.app_context(), patch(f'{MODULE}.get_db_connection', return_value=conn):
            result = AbsenceConflictResolutionRepository().list_for_absence(1)
        assert result == rows
        sql = cur.execute.call_args.args[0]
        assert 'ORDER BY acr.resolved_at DESC' in sql
        assert 'WHERE acr.absence_id = %s' in sql

    def test_empty_when_no_history(self, app):
        from repositories.absences.absence_conflict_resolution_repository import (
            AbsenceConflictResolutionRepository,
        )
        conn, cur = _read_conn([])
        with app.app_context(), patch(f'{MODULE}.get_db_connection', return_value=conn):
            result = AbsenceConflictResolutionRepository().list_for_absence(999)
        assert result == []
