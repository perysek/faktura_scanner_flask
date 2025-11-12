"""
Repository dla historii zmian (audit log)
"""
from typing import List
from repositories.base_repository import BaseRepository
from database.models import AuditEntry


class AuditRepository(BaseRepository):
	"""Repository dla audit log"""
	
	def __init__(self):
		super().__init__("audit_log")
	
	def log_change(
			self, invoice_id: int, field_name: str, old_value: str,
			new_value: str
			):
		"""Zapisz zmianę pola faktury"""
		query = """
            INSERT INTO audit_log (invoice_id, field_name, old_value, new_value)
            VALUES (?, ?, ?, ?)
        """
		self._execute(query, (invoice_id, field_name, old_value, new_value))
	
	def get_invoice_history(self, invoice_id: int) -> List[dict]:
		"""Pobierz historię zmian faktury"""
		query = """
            SELECT * FROM audit_log
            WHERE invoice_id = ?
            ORDER BY changed_at DESC
        """
		rows = self._fetch_all(query, (invoice_id,))
		
		return [
			{
				"id": row["id"],
				"field_name": row["field_name"],
				"old_value": row["old_value"],
				"new_value": row["new_value"],
				"changed_at": row["changed_at"]
				}
			for row in rows
			]