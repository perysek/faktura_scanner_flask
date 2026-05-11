"""
Repository dla hierarchii przełożony↔pracownik (employee_supervisors).
"""
from typing import Any, List

from config.database import get_db_connection


class EmployeeSupervisorRepository:
    """Zarządza powiązaniami pracownik → przełożony (M:M)."""

    # ── reads ─────────────────────────────────────────────────────────────────

    def list_supervisors_for(self, employee_id: int) -> List[Any]:
        """Przełożeni przypisani do danego pracownika (do dropdownu wyboru approver)."""
        query = """
            SELECT e.id, e.first_name, e.last_name, e.position, e.user_id
            FROM employee_supervisors es
            JOIN employees e ON e.id = es.supervisor_employee_id
            WHERE es.employee_id = %s AND e.is_active = TRUE
            ORDER BY e.last_name, e.first_name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            return cursor.fetchall()

    def list_subordinates_for(self, supervisor_employee_id: int) -> List[Any]:
        """Podwładni danego przełożonego (do wyświetlania wniosków i tworzenia L4)."""
        query = """
            SELECT e.id, e.first_name, e.last_name, e.position, e.user_id
            FROM employee_supervisors es
            JOIN employees e ON e.id = es.employee_id
            WHERE es.supervisor_employee_id = %s AND e.is_active = TRUE
            ORDER BY e.last_name, e.first_name
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (supervisor_employee_id,))
            return cursor.fetchall()

    def is_supervisor(self, employee_id: int) -> bool:
        """True jeśli pracownik jest przełożonym co najmniej jednego innego pracownika."""
        query = """
            SELECT 1 FROM employee_supervisors
            WHERE supervisor_employee_id = %s
            LIMIT 1
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            return cursor.fetchone() is not None

    def link_exists(self, employee_id: int, supervisor_employee_id: int) -> bool:
        query = """
            SELECT 1 FROM employee_supervisors
            WHERE employee_id = %s AND supervisor_employee_id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, supervisor_employee_id))
            return cursor.fetchone() is not None

    # ── writes ────────────────────────────────────────────────────────────────

    def add_link(self, employee_id: int, supervisor_employee_id: int) -> bool:
        """Dodaj powiązanie (ignoruje jeśli już istnieje — INSERT OR IGNORE)."""
        query = """
            INSERT INTO employee_supervisors (employee_id, supervisor_employee_id)
            VALUES (%s, %s)
            ON CONFLICT (employee_id, supervisor_employee_id) DO NOTHING
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, supervisor_employee_id))
            conn.commit()
            return cursor.rowcount > 0

    def remove_link(self, employee_id: int, supervisor_employee_id: int) -> bool:
        query = """
            DELETE FROM employee_supervisors
            WHERE employee_id = %s AND supervisor_employee_id = %s
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, supervisor_employee_id))
            conn.commit()
            return cursor.rowcount > 0

    def remove_all_supervisors_for(self, employee_id: int) -> int:
        """Usuń wszystkich przełożonych pracownika (przy przebudowie hierarchii)."""
        query = "DELETE FROM employee_supervisors WHERE employee_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            conn.commit()
            return cursor.rowcount

    def remove_all_subordinates_for(self, supervisor_employee_id: int) -> int:
        """Usuń wszystkich podwładnych przełożonego (przy przebudowie hierarchii)."""
        query = "DELETE FROM employee_supervisors WHERE supervisor_employee_id = %s"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (supervisor_employee_id,))
            conn.commit()
            return cursor.rowcount
