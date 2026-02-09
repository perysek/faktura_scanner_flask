"""
Bazowa klasa repository z CRUD operations
"""
import sqlite3
from typing import List, Optional

from config.database import DatabaseConnection


class BaseRepository:
	"""Bazowy repository z podstawowymi operacjami CRUD"""

	def __init__(self, table_name: str):
		self.table_name = table_name

	def _get_conn(self) -> sqlite3.Connection:
		"""Get database connection for current request context"""
		return DatabaseConnection.get_connection()

	def _execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
		"""Wykonaj query"""
		conn = self._get_conn()
		cursor = conn.cursor()
		cursor.execute(query, params)
		conn.commit()
		return cursor

	def _fetch_one(self, query: str, params: tuple = ()) -> Optional[
		sqlite3.Row]:
		"""Pobierz jeden rekord"""
		conn = self._get_conn()
		cursor = conn.cursor()
		cursor.execute(query, params)
		return cursor.fetchone()

	def _fetch_all(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
		"""Pobierz wszystkie rekordy"""
		conn = self._get_conn()
		cursor = conn.cursor()
		cursor.execute(query, params)
		return cursor.fetchall()
	
	def get_by_id(self, id: int) -> Optional[sqlite3.Row]:
		"""Pobierz rekord po ID"""
		query = f"SELECT * FROM {self.table_name} WHERE id = ?"
		return self._fetch_one(query, (id,))
	
	def get_all(self) -> List[sqlite3.Row]:
		"""Pobierz wszystkie rekordy"""
		query = f"SELECT * FROM {self.table_name} ORDER BY id DESC"
		return self._fetch_all(query)
	
	def delete(self, id: int) -> bool:
		"""Usuń rekord"""
		query = f"DELETE FROM {self.table_name} WHERE id = ?"
		cursor = self._execute(query, (id,))
		return cursor.rowcount > 0