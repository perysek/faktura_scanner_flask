"""
Repository dla historii zmian (audit log)
"""
from typing import Any, List, Optional

from repositories.base_repository import BaseRepository


class AuditRepository(BaseRepository):
    """Repository dla audit log"""

    def __init__(self):
        super().__init__("audit_log")

    def log_change(
            self, invoice_id: int, field_name: str, old_value: str,
            new_value: str, action: str = 'UPDATE'
    ):
        """Zapisz zmianę pola faktury"""
        query = """
            INSERT INTO audit_log (invoice_id, field_name, old_value, new_value, action)
            VALUES (%s, %s, %s, %s, %s)
        """
        self._execute(query, (invoice_id, field_name, old_value, new_value, action))

    def get_by_invoice_id(self, invoice_id: int) -> List[dict]:
        """Pobierz historię zmian faktury (wrapper for get_all)"""
        return self.get_all(invoice_id)

    def get_all(self, invoice_id: Optional[int] = None) -> List[dict]:
        """
        Pobierz historię zmian (płaska lista)
        Zwraca listę obiektów pasujących do oczekiwań API/Frontend
        """
        params = []
        query = """
            SELECT 
                a.id,
                a.invoice_id,
                a.action,
                a.field_name,
                a.old_value,
                a.new_value,
                a.changed_at,
                i.invoice_number
            FROM audit_log a
            LEFT JOIN invoices i ON a.invoice_id = i.id
        """
        
        if invoice_id:
            query += " WHERE a.invoice_id = %s"
            params.append(invoice_id)
            
        query += " ORDER BY a.changed_at DESC, a.id DESC"
        
        rows = self._fetch_all(query, tuple(params))
        
        results = []
        for row in rows:
            results.append({
                'id': row['id'],
                'invoice_id': row['invoice_id'],
                'invoice_number': row['invoice_number'],
                'action': row['action'],
                'field_name': row['field_name'],
                'old_value': row['old_value'],
                'new_value': row['new_value'],
                'timestamp': row['changed_at']
            })
            
        return results

    def get_details_by_ids(self, ids_list: List[int]) -> List[dict]:
        """Pobierz szczegóły zmian dla podanych ID"""
        if not ids_list:
            return []
        
        placeholders = ','.join(['%s'] * len(ids_list))
        query = f"""
            SELECT 
                field_name,
                old_value,
                new_value
            FROM audit_log
            WHERE id IN ({placeholders})
        """
        
        rows = self._fetch_all(query, tuple(ids_list))
        
        return [dict(row) for row in rows]