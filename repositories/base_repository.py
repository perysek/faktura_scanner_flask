"""
Bazowa klasa repository z CRUD operations

Repository access pattern (improvement #2)
==========================================
Repositories are **stateless connection-borrowers**: every method pulls its
connection from Flask ``g`` (via ``DatabaseConnection.get_connection()``), so an
instance carries no per-request data. Two ways to obtain one coexist and are
BOTH safe:

  * ``current_app.<x>_repo`` — the shared singletons attached in ``create_app()``.
    Convenient inside a request. These are **frozen at attachment** (see
    ``freeze_repository_singleton`` below) so they can never acquire mutable
    instance state that would leak across ``gthread`` worker threads.
  * ``XRepository()`` — direct instantiation. The ONLY option outside a request
    context (background threads, the AuditableMixin, boot code) and for repos
    that have no singleton. Always safe because a fresh instance is private to
    the caller.

The one rule: **a repository must never hold mutable instance state** (caches,
per-user filters, memoized lookups). The singleton freeze enforces this for the
shared instances; new repos should follow it too. A genuinely per-call,
stateful helper (e.g. EmployeeAnalyticsRepository, scoped to one employee_id)
is fine — just never attach it as an ``app.*`` singleton.
"""
from contextlib import contextmanager
from typing import Any, List, Optional

import psycopg2
import psycopg2.extensions

from config.database import DatabaseConnection, safe_commit
from exceptions import DatabaseConnectionError


def freeze_repository_singleton(repo: Any) -> Any:
    """Make a repository instance reject all post-construction attribute writes.

    A repository attached to the Flask app (``app.invoice_repo`` …) is a SINGLE
    object shared by every ``gthread`` worker thread. It is safe today only
    because it is stateless. The latent trap (improvement #2): the day a method
    or a well-meaning "optimization" runs ``self._cache = {}`` on that shared
    instance, the state leaks across requests and threads — and a plain ``dict``
    is not thread-safe, so concurrent writes can corrupt it or raise
    ``RuntimeError: dictionary changed size during iteration``. The bug is
    intermittent and nearly impossible to reproduce with one user.

    Freezing the instance at attachment time makes that structurally impossible:
    any later ``self.x = ...`` raises immediately (caught in dev/test the first
    time it runs) instead of silently corrupting production data.

    Mechanism: swap the instance to a frozen subclass whose ``__setattr__``
    raises. ``isinstance`` and method resolution are unaffected (the frozen
    class IS-A the original, and keeps its name). The instance is already fully
    constructed, so legitimate construction-time state (e.g. ``table_name``) is
    preserved. Works for every repo regardless of base class. Idempotent.
    """
    cls = type(repo)
    if getattr(cls, '_is_frozen_singleton', False):
        return repo  # already frozen — idempotent

    def _frozen_setattr(self, name, value):  # noqa: ANN001
        raise AttributeError(
            f"{cls.__name__} is a frozen shared singleton (improvement #2): "
            f"cannot set instance attribute {name!r}. A repository attached to "
            f"the Flask app is shared across worker threads and MUST stay "
            f"stateless. Use a local variable or per-request state, never "
            f"instance state. (If you truly need per-instance state, build the "
            f"repo locally with XRepository() and do not attach it as a singleton.)"
        )

    frozen_cls = type(cls.__name__, (cls,), {
        '__setattr__': _frozen_setattr,
        '_is_frozen_singleton': True,
    })
    repo.__class__ = frozen_cls  # original __setattr__ is plain object's — allowed
    return repo


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
		try:
			conn = self._get_conn()
			cursor = conn.cursor()
			cursor.execute(query, params)
			safe_commit(conn)
			return cursor
		except psycopg2.OperationalError as e:
			raise DatabaseConnectionError(f'Database unreachable: {type(e).__name__}') from e
		except psycopg2.InterfaceError as e:
			raise DatabaseConnectionError(f'Database connection lost: {type(e).__name__}') from e

	def _execute_insert(self, query: str, params: tuple = ()) -> Optional[int]:
		"""Execute INSERT and return the new row id via RETURNING id"""
		try:
			query = query.rstrip().rstrip(';') + ' RETURNING id'
			conn = self._get_conn()
			cursor = conn.cursor()
			cursor.execute(query, params)
			row = cursor.fetchone()
			safe_commit(conn)
			return row['id'] if row else None
		except psycopg2.OperationalError as e:
			raise DatabaseConnectionError(f'Database unreachable: {type(e).__name__}') from e
		except psycopg2.InterfaceError as e:
			raise DatabaseConnectionError(f'Database connection lost: {type(e).__name__}') from e

	def _fetch_one(self, query: str, params: tuple = ()) -> Optional[Any]:
		"""Pobierz jeden rekord"""
		try:
			conn = self._get_conn()
			cursor = conn.cursor()
			cursor.execute(query, params)
			return cursor.fetchone()
		except psycopg2.OperationalError as e:
			raise DatabaseConnectionError(f'Database unreachable: {type(e).__name__}') from e
		except psycopg2.InterfaceError as e:
			raise DatabaseConnectionError(f'Database connection lost: {type(e).__name__}') from e

	def _fetch_all(self, query: str, params: tuple = ()) -> List[Any]:
		"""Pobierz wszystkie rekordy"""
		try:
			conn = self._get_conn()
			cursor = conn.cursor()
			cursor.execute(query, params)
			return cursor.fetchall()
		except psycopg2.OperationalError as e:
			raise DatabaseConnectionError(f'Database unreachable: {type(e).__name__}') from e
		except psycopg2.InterfaceError as e:
			raise DatabaseConnectionError(f'Database connection lost: {type(e).__name__}') from e

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
