"""
Repository dla historii zmian (audit log)
"""
import logging
from typing import List, Optional

from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class AuditRepository(BaseRepository):
    """Repository dla audit log"""

    def __init__(self):
        super().__init__("audit_log")

    def log_event(
        self,
        entity_type: str,
        action: str,
        entity_id: Optional[int] = None,
        entity_label: Optional[str] = None,
        field_name: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
        invoice_id: Optional[int] = None,
    ):
        """Zapisz zdarzenie dla dowolnej encji aplikacji"""
        query = """
            INSERT INTO audit_log
                (entity_type, entity_id, entity_label, invoice_id,
                 action, field_name, old_value, new_value, user_id, user_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        self._execute(query, (
            entity_type, entity_id, entity_label, invoice_id,
            action, field_name, old_value, new_value, user_id, user_name,
        ))

    def safe_log_event(self, *, critical: bool = False, **kwargs) -> bool:
        """Log an audit event without ever silently losing it.

        The previous call sites used ``try: log_event(...) except Exception: pass``,
        which made a failed audit write indistinguishable from a successful one —
        fatal for a system whose audit trail is a financial/PII forensic artifact.

        On failure:
          - ``critical=False`` (default): log at ERROR so the dropped write surfaces
            in monitoring, but do NOT disrupt the business operation. Returns False.
          - ``critical=True``: re-raise, so the caller fails rather than proceeding
            un-audited (use for sensitive financial/RBAC mutations).

        Returns True on success, False on a swallowed (non-critical) failure.
        """
        try:
            self.log_event(**kwargs)
            return True
        except Exception:
            logger.error("AUDIT WRITE FAILED: %s", kwargs, exc_info=True)
            if critical:
                raise
            return False

    def log_change(
        self, invoice_id: int, field_name: str, old_value: str,
        new_value: str, action: str = 'UPDATE',
        user_id: Optional[int] = None, user_name: Optional[str] = None,
    ):
        """Zapisz zmianę pola faktury (backward-compatible wrapper)"""
        self.log_event(
            entity_type='invoice',
            action=action,
            entity_id=invoice_id,
            entity_label=None,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            user_id=user_id,
            user_name=user_name,
            invoice_id=invoice_id,
        )

    def get_by_invoice_id(self, invoice_id: int) -> List[dict]:
        """Pobierz historię zmian faktury"""
        return self.get_all(invoice_id=invoice_id)

    def get_all(
        self,
        invoice_id: Optional[int] = None,
        entity_type: Optional[str] = None,
    ) -> List[dict]:
        """
        Pobierz historię zmian z opcjonalnym filtrowaniem.
        Zwraca listę pasującą do oczekiwań API/Frontend.
        """
        params = []
        conditions = []

        if invoice_id:
            conditions.append("a.invoice_id = %s")
            params.append(invoice_id)

        if entity_type:
            conditions.append("a.entity_type = %s")
            params.append(entity_type)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        query = f"""
            SELECT
                a.id,
                a.entity_type,
                a.entity_id,
                a.entity_label,
                a.invoice_id,
                a.action,
                a.field_name,
                a.old_value,
                a.new_value,
                a.user_id,
                a.user_name,
                a.changed_at,
                i.invoice_number
            FROM audit_log a
            LEFT JOIN invoices i ON a.invoice_id = i.id
            {where_clause}
            ORDER BY a.changed_at DESC, a.id DESC
        """

        rows = self._fetch_all(query, tuple(params))

        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'entity_type': row['entity_type'] or 'invoice',
                'entity_id': row['entity_id'],
                'entity_label': row['entity_label'],
                'invoice_id': row['invoice_id'],
                'invoice_number': row['invoice_number'],
                'action': row['action'],
                'field_name': row['field_name'],
                'old_value': row['old_value'],
                'new_value': row['new_value'],
                'user_id': row['user_id'],
                'user_name': row['user_name'],
                'timestamp': row['changed_at'],
            })

        return results

    def get_for_employee_balance(self, employee_id: int) -> List[dict]:
        """Historia zmian limitów i korekt dla konkretnego pracownika."""
        query = """
            SELECT
                a.id, a.entity_type, a.entity_id, a.entity_label,
                a.action, a.field_name, a.old_value, a.new_value,
                a.user_id,
                COALESCE(a.user_name, u.full_name) AS user_name,
                a.changed_at
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.user_id
            WHERE (
                (a.entity_type = 'absence_limit' AND a.entity_id IN (
                    SELECT id FROM employee_absence_limits WHERE employee_id = %s
                ))
                OR
                (a.entity_type = 'absence_adjustment' AND a.entity_id IN (
                    SELECT id FROM absence_balance_adjustments WHERE employee_id = %s
                ))
            )
            ORDER BY a.changed_at DESC, a.id DESC
            LIMIT 200
        """
        rows = self._fetch_all(query, (employee_id, employee_id))
        return [
            {
                'id': r['id'],
                'entity_type': r['entity_type'],
                'entity_id': r['entity_id'],
                'entity_label': r['entity_label'],
                'action': r['action'],
                'field_name': r['field_name'],
                'old_value': r['old_value'],
                'new_value': r['new_value'],
                'user_id': r['user_id'],
                'user_name': r['user_name'],
                'timestamp': r['changed_at'],
            }
            for r in rows
        ]

    def delete_for_employee_balance(self, employee_id: int) -> int:
        """Usuń wpisy historii zmian dla bilansów konkretnego pracownika."""
        query = """
            DELETE FROM audit_log
            WHERE (
                (entity_type = 'absence_limit' AND entity_id IN (
                    SELECT id FROM employee_absence_limits WHERE employee_id = %s
                ))
                OR
                (entity_type = 'absence_adjustment' AND entity_id IN (
                    SELECT id FROM absence_balance_adjustments WHERE employee_id = %s
                ))
            )
        """
        cursor = self._execute(query, (employee_id, employee_id))
        return cursor.rowcount

    def get_employee_ids_with_balance_history(self) -> List[int]:
        """Zwróć listę ID pracowników mających wpisy w historii bilansów."""
        query = """
            SELECT DISTINCT emp_id FROM (
                SELECT eal.employee_id AS emp_id
                FROM audit_log a
                JOIN employee_absence_limits eal ON a.entity_id = eal.id
                WHERE a.entity_type = 'absence_limit'
                UNION
                SELECT aba.employee_id AS emp_id
                FROM audit_log a
                JOIN absence_balance_adjustments aba ON a.entity_id = aba.id
                WHERE a.entity_type = 'absence_adjustment'
            ) sub
            WHERE emp_id IS NOT NULL
        """
        rows = self._fetch_all(query, ())
        return [r['emp_id'] for r in rows]

    def get_details_by_ids(self, ids_list: List[int]) -> List[dict]:
        """Pobierz szczegóły zmian dla podanych ID"""
        if not ids_list:
            return []

        placeholders = ','.join(['%s'] * len(ids_list))
        query = f"""
            SELECT field_name, old_value, new_value
            FROM audit_log
            WHERE id IN ({placeholders})
        """
        rows = self._fetch_all(query, tuple(ids_list))
        return [dict(row) for row in rows]
