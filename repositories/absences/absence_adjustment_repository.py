"""
Repository dla manualnych korekt bilansu nieobecności (absence_balance_adjustments).
"""
from typing import Any, List

from config.database import get_db_connection, safe_commit
from database.models import AbsenceBalanceAdjustment
from repositories.db_utils import parse_dt


class AbsenceAdjustmentRepository:
    """CRUD dla tabeli absence_balance_adjustments."""

    _COLUMNS = (
        'id, employee_id, category_id, delta_value, reason, period_label, '
        'is_deleted, deleted_at, created_by, created_at, updated_at'
    )

    def row_to_adjustment(self, row: Any) -> AbsenceBalanceAdjustment:
        if not row:
            return None
        return AbsenceBalanceAdjustment(
            id=row['id'],
            employee_id=row['employee_id'],
            category_id=row['category_id'],
            delta_value=float(row['delta_value']),
            reason=row['reason'],
            period_label=row['period_label'],
            is_deleted=bool(row['is_deleted']),
            deleted_at=parse_dt(row['deleted_at']),
            created_by=row['created_by'],
            created_at=parse_dt(row['created_at']),
            updated_at=parse_dt(row['updated_at']),
        )

    # ── reads ─────────────────────────────────────────────────────────────────

    def list_for_employee(self, employee_id: int,
                           include_deleted: bool = False) -> List[Any]:
        """Wszystkie korekty dla pracownika, opcjonalnie z usuniętymi."""
        query = f"""
            SELECT aba.{', aba.'.join(self._COLUMNS.replace(' ', '').split(','))},
                   ac.name AS category_name,
                   u.full_name AS created_by_name
            FROM absence_balance_adjustments aba
            JOIN absence_categories ac ON ac.id = aba.category_id
            LEFT JOIN users u ON u.id = aba.created_by
            WHERE aba.employee_id = %s
            {'AND aba.is_deleted = FALSE' if not include_deleted else ''}
            ORDER BY aba.created_at DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id,))
            return cursor.fetchall()

    def list_for_employee_category(self, employee_id: int,
                                    category_id: int) -> List[Any]:
        """Korekty dla konkretnej pary pracownik+kategoria (bez usuniętych)."""
        query = f"""
            SELECT {self._COLUMNS} FROM absence_balance_adjustments
            WHERE employee_id = %s AND category_id = %s AND is_deleted = FALSE
            ORDER BY created_at DESC
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (employee_id, category_id))
            return cursor.fetchall()

    # ── writes ────────────────────────────────────────────────────────────────

    def create(self, adj: AbsenceBalanceAdjustment) -> int:
        query = """
            INSERT INTO absence_balance_adjustments
                (employee_id, category_id, delta_value, reason, period_label, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        # safe_commit (not conn.commit) so this insert defers to an enclosing
        # managed_transaction — the balance service commits it atomically with the
        # audit_log row. Outside a transaction it commits immediately, as before.
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (
            adj.employee_id,
            adj.category_id,
            adj.delta_value,
            adj.reason,
            adj.period_label,
            adj.created_by,
        ))
        new_id = cursor.fetchone()['id']
        safe_commit(conn)
        return new_id

    def soft_delete(self, adj_id: int) -> bool:
        query = """
            UPDATE absence_balance_adjustments
            SET is_deleted = TRUE,
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND is_deleted = FALSE
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (adj_id,))
        safe_commit(conn)
        return cursor.rowcount > 0
