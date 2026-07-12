"""
Repository dla trwałej historii rozwiązań konfliktów nieobecność/wizyta
(absence_conflict_resolutions) — audytowy ślad akcji podjętych w modalu
przełożonego (reassign / reschedule / cancel).
"""
from typing import Any, List, Optional

from config.database import get_db_connection, safe_commit


class AbsenceConflictResolutionRepository:
    """CRUD dla tabeli absence_conflict_resolutions."""

    def create(self, absence_id: int, appointment_id: int, resolution_type: str,
               resolved_by_user_id: int,
               previous_employee_id: Optional[int] = None,
               new_employee_id: Optional[int] = None,
               previous_date=None, previous_start_time=None, previous_end_time=None,
               new_date=None, new_start_time=None, new_end_time=None,
               cancellation_reason: Optional[str] = None) -> int:
        query = """
            INSERT INTO absence_conflict_resolutions (
                absence_id, appointment_id, resolution_type,
                previous_employee_id, new_employee_id,
                previous_date, previous_start_time, previous_end_time,
                new_date, new_start_time, new_end_time,
                cancellation_reason, resolved_by_user_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (
            absence_id, appointment_id, resolution_type,
            previous_employee_id, new_employee_id,
            previous_date, previous_start_time, previous_end_time,
            new_date, new_start_time, new_end_time,
            cancellation_reason, resolved_by_user_id,
        ))
        new_id = cursor.fetchone()['id']
        safe_commit(conn)
        return new_id

    def list_for_absence(self, absence_id: int) -> List[Any]:
        """Historia rozwiązań dla wniosku, z danymi wizyty/klienta/pracowników do
        wyświetlenia w widoku 'Historia rozwiązań' (Faza 3)."""
        query = """
            SELECT
                acr.*,
                c.first_name || ' ' || c.last_name AS client_name,
                (SELECT s.name FROM appointment_services aps
                 JOIN services s ON s.id = aps.service_id
                 WHERE aps.appointment_id = a.id AND aps.is_addon = FALSE
                 ORDER BY aps.id LIMIT 1) AS service_name,
                prev_e.first_name || ' ' || prev_e.last_name AS previous_employee_name,
                new_e.first_name || ' ' || new_e.last_name AS new_employee_name,
                u.full_name AS resolved_by_name
            FROM absence_conflict_resolutions acr
            JOIN appointments a ON a.id = acr.appointment_id
            JOIN clients c ON c.id = a.client_id
            LEFT JOIN employees prev_e ON prev_e.id = acr.previous_employee_id
            LEFT JOIN employees new_e ON new_e.id = acr.new_employee_id
            LEFT JOIN users u ON u.id = acr.resolved_by_user_id
            WHERE acr.absence_id = %s
            ORDER BY acr.resolved_at DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (absence_id,))
            return cursor.fetchall()
