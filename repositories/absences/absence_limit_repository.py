"""
Repository dla indywidualnych limitów nieobecności pracowników (employee_absence_limits).
"""
from typing import Any, List, Optional

from config.database import get_db_connection
from database.models import EmployeeAbsenceLimit
from repositories.db_utils import parse_dt


class AbsenceLimitRepository:
    """CRUD dla tabeli employee_absence_limits."""

    _COLUMNS = (
        'id, employee_id, category_id, max_value, notes, '
        'is_deleted, deleted_at, created_by, created_at, updated_at'
    )

    def row_to_limit(self, row: Any) -> EmployeeAbsenceLimit:
        if not row:
            return None
        return EmployeeAbsenceLimit(
            id=row['id'],
            employee_id=row['employee_id'],
            category_id=row['category_id'],
            max_value=float(row['max_value']),
            notes=row['notes'],
            is_deleted=bool(row['is_deleted']),
            deleted_at=parse_dt(row['deleted_at']),
            created_by=row['created_by'],
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at']),
        )

    # ── reads ─────────────────────────────────────────────────────────────────

    def get_for_employee_category(self, employee_id: int,
                                   category_id: int) -> Optional[Any]:
        """Aktywny limit dla pary pracownik+kategoria."""
        query = f"""
            SELECT {self._COLUMNS} FROM employee_absence_limits
            WHERE employee_id = %s AND category_id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, category_id))
            return cursor.fetchone()

    def list_for_employee(self, employee_id: int) -> List[Any]:
        """Wszystkie aktywne limity dla pracownika."""
        query = f"""
            SELECT {self._COLUMNS} FROM employee_absence_limits
            WHERE employee_id = %s AND is_deleted = FALSE
            ORDER BY category_id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            return cursor.fetchall()

    def list_for_category(self, category_id: int) -> List[Any]:
        """Wszystkie aktywne limity dla kategorii (widok admina)."""
        query = f"""
            SELECT {self._COLUMNS} FROM employee_absence_limits
            WHERE category_id = %s AND is_deleted = FALSE
            ORDER BY employee_id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (category_id,))
            return cursor.fetchall()

    # ── writes ────────────────────────────────────────────────────────────────

    def upsert(self, limit: EmployeeAbsenceLimit) -> int:
        """Wstaw lub zaktualizuj aktywny limit dla pary pracownik+kategoria."""
        query = """
            INSERT INTO employee_absence_limits
                (employee_id, category_id, max_value, notes, created_by)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (employee_id, category_id) WHERE is_deleted = FALSE
            DO UPDATE SET
                max_value  = EXCLUDED.max_value,
                notes      = EXCLUDED.notes,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                limit.employee_id,
                limit.category_id,
                limit.max_value,
                limit.notes,
                limit.created_by,
            ))
            row = cursor.fetchone()
            conn.commit()
            return row['id']

    def soft_delete(self, limit_id: int) -> bool:
        query = """
            UPDATE employee_absence_limits
            SET is_deleted = TRUE,
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit_id,))
            conn.commit()
            return cursor.rowcount > 0

    def soft_delete_for_employee_category(self, employee_id: int,
                                           category_id: int) -> bool:
        query = """
            UPDATE employee_absence_limits
            SET is_deleted = TRUE,
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE employee_id = %s AND category_id = %s AND is_deleted = FALSE
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, category_id))
            conn.commit()
            return cursor.rowcount > 0
