"""
Bazowa klasa repository z CRUD operations
"""
from contextlib import contextmanager
from typing import Any, List, Optional

import psycopg2.extensions

from config.database import DatabaseConnection


class BaseRepository:
	"""Bazowy repository z podstawowymi operacjami CRUD"""

	# Override in child repositories to avoid SELECT *
	# e.g. _columns = 'id, name, email'
	_columns: str = '*'

	# Set True in child repositories that have is_deleted/deleted_at columns
	_soft_delete: bool = False

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

	@contextmanager
	def transaction(self):
		"""Context manager for explicit transaction control.

		Usage:
		    with self.transaction() as conn:
		        cursor = conn.cursor()
		        cursor.execute(...)
		        cursor.execute(...)
		    # auto-commits on success, rolls back on exception
		"""
		conn = self._get_conn()
		try:
			yield conn
			conn.commit()
		except Exception:
			conn.rollback()
			raise

	@staticmethod
	def _in_clause(items: list) -> tuple:
		"""Build safe IN clause placeholders.

		Returns (placeholders_str, params_tuple):
		    clause, params = self._in_clause([1, 2, 3])
		    query = f"SELECT * FROM t WHERE id IN {clause}"
		    cursor.execute(query, params)
		"""
		placeholders = ','.join(['%s'] * len(items))
		return f"({placeholders})", tuple(items)

	def get_by_id(self, id: int) -> Optional[Any]:
		"""Pobierz rekord po ID (pomija soft-deleted)"""
		soft = " AND is_deleted = FALSE" if self._soft_delete else ""
		query = f"SELECT {self._columns} FROM {self.table_name} WHERE id = %s{soft}"
		return self._fetch_one(query, (id,))

	def get_all(self) -> List[Any]:
		"""Pobierz wszystkie rekordy (pomija soft-deleted)"""
		soft = " WHERE is_deleted = FALSE" if self._soft_delete else ""
		query = f"SELECT {self._columns} FROM {self.table_name}{soft} ORDER BY id DESC"
		return self._fetch_all(query)

	def delete(self, id: int) -> bool:
		"""Usuń rekord (soft delete jeśli _soft_delete=True, hard delete otherwise)"""
		if self._soft_delete:
			query = f"UPDATE {self.table_name} SET is_deleted = TRUE, deleted_at = CURRENT_TIMESTAMP WHERE id = %s"
		else:
			query = f"DELETE FROM {self.table_name} WHERE id = %s"
		cursor = self._execute(query, (id,))
		return cursor.rowcount > 0

	def restore(self, id: int) -> bool:
		"""Przywróć soft-deleted rekord"""
		if not self._soft_delete:
			return False
		query = f"UPDATE {self.table_name} SET is_deleted = FALSE, deleted_at = NULL WHERE id = %s AND is_deleted = TRUE"
		cursor = self._execute(query, (id,))
		return cursor.rowcount > 0
