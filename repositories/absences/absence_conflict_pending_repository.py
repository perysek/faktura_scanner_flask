"""
Repository dla absence_conflict_pending — wizyty zostawione BEZ rozwiązania przy
"Zatwierdź mimo to" w modalu konfliktów nieobecności. Każdy wiersz czeka do
`valid_for` (start wizyty − 48 h); potem scheduler anuluje wizytę, o ile nadal
koliduje z nieobecnością (services/absence_conflict_deferral_service.py).
"""
from datetime import datetime
from typing import List, Optional

from repositories.base_repository import BaseRepository


class AbsenceConflictPendingRepository(BaseRepository):

    def __init__(self):
        super().__init__('absence_conflict_pending')

    def create(self, absence_id: int, appointment_id: int, employee_id: Optional[int],
               appointment_date, start_time, end_time, valid_for: datetime,
               created_by_user_id: int, sms_event_id: Optional[int] = None) -> Optional[int]:
        """Insert one pending row. A re-insert for the same (absence, visit) is a no-op
        (returns None) — "Zatwierdź mimo to" cannot double-schedule a visit."""
        sql = """
            INSERT INTO absence_conflict_pending (
                absence_id, appointment_id, employee_id,
                appointment_date, start_time, end_time,
                valid_for, sms_event_id, created_by_user_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (absence_id, appointment_id) DO NOTHING
        """
        return self._execute_insert(sql, (
            absence_id, appointment_id, employee_id,
            appointment_date, start_time, end_time,
            valid_for, sms_event_id, created_by_user_id,
        ))

    def get_due(self) -> List[dict]:
        """Pending rows whose auto-cancel moment has come."""
        sql = """
            SELECT p.*
            FROM absence_conflict_pending p
            WHERE p.status = 'pending' AND p.valid_for <= NOW()
            ORDER BY p.valid_for, p.id
        """
        return [dict(r) for r in self._fetch_all(sql, ())]

    def mark(self, row_id: int, status: str, error_message: Optional[str] = None) -> bool:
        sql = """
            UPDATE absence_conflict_pending
            SET status = %s, processed_at = NOW(), error_message = %s
            WHERE id = %s
        """
        return self._execute(sql, (status, error_message, row_id)).rowcount > 0

    def list_for_absence(self, absence_id: int) -> List[dict]:
        sql = """
            SELECT p.* FROM absence_conflict_pending p
            WHERE p.absence_id = %s
            ORDER BY p.valid_for, p.id
        """
        return [dict(r) for r in self._fetch_all(sql, (absence_id,))]
