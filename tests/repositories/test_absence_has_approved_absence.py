"""Tests for AbsenceRepository.has_approved_absence() (Phase 0).

Narrower than check_absence_conflicts by design: only status='approved' counts —
a candidate for reassignment is excluded only by a *confirmed* absence, not a
still-pending one (spec: "not absence-approved").
"""
from unittest.mock import Mock, patch


def _ctx_conn(fetchone_result=None):
    cur = Mock()
    cur.fetchone.return_value = fetchone_result
    conn = Mock()
    conn.cursor.return_value = cur
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)
    return conn, cur


GDC = 'repositories.absences.absence_repository.get_db_connection'


class TestHasApprovedAbsence:
    def test_true_when_approved_row_found(self, app):
        from datetime import date
        from repositories.absences.absence_repository import AbsenceRepository
        conn, cur = _ctx_conn(fetchone_result={'?column?': 1})
        with app.app_context(), patch(GDC, return_value=conn):
            result = AbsenceRepository().has_approved_absence(5, date(2026, 7, 20))
        assert result is True
        sql = cur.execute.call_args.args[0]
        assert "status = 'approved'" in sql

    def test_false_when_nothing_found(self, app):
        from datetime import date
        from repositories.absences.absence_repository import AbsenceRepository
        conn, cur = _ctx_conn(fetchone_result=None)
        with app.app_context(), patch(GDC, return_value=conn):
            result = AbsenceRepository().has_approved_absence(5, date(2026, 7, 20))
        assert result is False

    def test_full_day_query_omits_time_clause(self, app):
        from datetime import date
        from repositories.absences.absence_repository import AbsenceRepository
        conn, cur = _ctx_conn(fetchone_result=None)
        with app.app_context(), patch(GDC, return_value=conn):
            AbsenceRepository().has_approved_absence(5, date(2026, 7, 20))
        sql, params = cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])
        assert 'time_from' not in sql or 'AND (' not in sql
        assert params == [5, '2026-07-20', '2026-07-20']

    def test_slot_query_includes_time_clause_and_params(self, app):
        from datetime import date, time
        from repositories.absences.absence_repository import AbsenceRepository
        conn, cur = _ctx_conn(fetchone_result=None)
        with app.app_context(), patch(GDC, return_value=conn):
            AbsenceRepository().has_approved_absence(
                5, date(2026, 7, 20), time(10, 0), time(11, 0)
            )
        sql, params = cur.execute.call_args.args[0], list(cur.execute.call_args.args[1])
        assert 'AND (' in sql
        assert params == [5, '2026-07-20', '2026-07-20', '11:00:00', '10:00:00']
