"""
Bazowa klasa repository z CRUD operations
"""
from typing import Any, List, Optional

import psycopg2.extensions

from config.database import DatabaseConnection


class BaseRepository:
	"""Bazowy repository z podstawowymi operacjami CRUD"""

	def __init__(self, table_name: str):
		self.table_name = table_name

	def _get_conn(self) -> psycopg2.extensions.connection:
		"""Get database connection for current request context"""
		return DatabaseConnection.get_connection()

	def _execute(self, query: str, params: tuple = ()) -> Any:
		"""Wykonaj query"""
		conn = self._get_conn()
		cursor = conn.cursor()
		cursor.execute(query, params)
		conn.commit()
		return cursor

	def _execute_insert(self, query: str, params: tuple = ()) -> Optional[int]:
		"""Execute INSERT and return the new row id via RETURNING id"""
		query = query.rstrip().rstrip(';') + ' RETURNING id'
		conn = self._get_conn()
		cursor = conn.cursor()
		cursor.execute(query, params)
		row = cursor.fetchone()
		conn.commit()
		return row['id'] if row else None

	def _fetch_one(self, query: str, params: tuple = ()) -> Optional[Any]:
		"""Pobierz jeden rekord"""
		conn = self._get_conn()
		cursor = conn.cursor()
		cursor.execute(query, params)
		return cursor.fetchone()

	def _fetch_all(self, query: str, params: tuple = ()) -> List[Any]:
		"""Pobierz wszystkie rekordy"""
		conn = self._get_conn()
		cursor = conn.cursor()
		cursor.execute(query, params)
		return cursor.fetchall()

	def get_by_id(self, id: int) -> Optional[Any]:
		"""Pobierz rekord po ID"""
		query = f"SELECT * FROM {self.table_name} WHERE id = %s"
		return self._fetch_one(query, (id,))

	def get_all(self) -> List[Any]:
		"""Pobierz wszystkie rekordy"""
		query = f"SELECT * FROM {self.table_name} ORDER BY id DESC"
		return self._fetch_all(query)

	def delete(self, id: int) -> bool:
		"""Usuń rekord"""
		query = f"DELETE FROM {self.table_name} WHERE id = %s"
		cursor = self._execute(query, (id,))
		return cursor.rowcount > 0
