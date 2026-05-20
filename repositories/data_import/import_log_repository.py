"""
Repository for import_logs — audit trail for the caldis.pl Playwright import feature.

Every import attempt (running, completed, failed, cancelled) has exactly one row.
The data_import_service writes here; the SSE / status / history endpoints read.

Background-thread safe: every method accepts an optional `conn` parameter so
the runner can pass a pool-acquired connection from outside the Flask request
context. When `conn=None`, falls back to DatabaseConnection.get_connection().
"""
import json
import logging
from datetime import date
from typing import Any, List, Optional

import psycopg2.extensions

from config.database import DatabaseConnection, safe_commit
from repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ImportLogRepository(BaseRepository):
    """CRUD + status transitions for import_logs."""

    _columns = (
        'id, started_at, finished_at, date_range_start, date_range_end, '
        'triggered_by_user_id, status, stats, error_message, session_status, '
        'dry_run, created_at'
    )

    def __init__(self):
        super().__init__('import_logs')

    # ── connection helper ────────────────────────────────────────────────────
    def _conn(self, conn: Optional[psycopg2.extensions.connection]):
        """Return the supplied connection, or fall back to the request-scoped one."""
        return conn if conn is not None else DatabaseConnection.get_connection()

    # ── create ───────────────────────────────────────────────────────────────
    def create(self, date_start: date, date_end: date,
               dry_run: bool, triggered_by_user_id: Optional[int],
               conn: Optional[psycopg2.extensions.connection] = None) -> int:
        """Insert a new running row, return its id."""
        query = """
            INSERT INTO import_logs
                (date_range_start, date_range_end, dry_run, triggered_by_user_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (
            date_start.isoformat(),
            date_end.isoformat(),
            dry_run,
            triggered_by_user_id,
        ))
        new_id = cursor.fetchone()['id']
        safe_commit(conn)
        return new_id

    # ── reads ────────────────────────────────────────────────────────────────
    def get_by_id(self, import_id: int,
                  conn: Optional[psycopg2.extensions.connection] = None) -> Optional[dict]:
        """Return a single import_logs row by id, or None."""
        query = f"SELECT {self._columns} FROM import_logs WHERE id = %s"
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (import_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def find_running(self,
                     conn: Optional[psycopg2.extensions.connection] = None) -> Optional[dict]:
        """Return the single currently-running import, or None."""
        query = f"""
            SELECT {self._columns}
            FROM import_logs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        return dict(row) if row else None

    def has_running_import(self,
                           conn: Optional[psycopg2.extensions.connection] = None) -> bool:
        """Return True if any import row currently has status='running'."""
        query = "SELECT 1 FROM import_logs WHERE status = 'running' LIMIT 1"
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query)
        return cursor.fetchone() is not None

    def get_recent(self, limit: int = 20,
                   conn: Optional[psycopg2.extensions.connection] = None) -> List[dict]:
        """Return the last N imports with triggered_by_user_name for the history table."""
        query = """
            SELECT
                il.id, il.started_at, il.finished_at,
                il.date_range_start, il.date_range_end,
                il.status, il.stats, il.error_message,
                il.session_status, il.dry_run,
                il.triggered_by_user_id,
                u.full_name AS triggered_by_user_name
            FROM import_logs il
            LEFT JOIN users u ON u.id = il.triggered_by_user_id
            ORDER BY il.started_at DESC
            LIMIT %s
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        return [dict(r) for r in cursor.fetchall()]

    def get_history(self, limit: int = 20,
                    conn: Optional[psycopg2.extensions.connection] = None) -> List[dict]:
        """Return last N imports with triggered_by_name (alias used by history endpoint)."""
        query = """
            SELECT
                il.id, il.started_at, il.finished_at,
                il.date_range_start, il.date_range_end,
                il.status, il.stats, il.error_message,
                il.session_status, il.dry_run,
                il.triggered_by_user_id,
                u.full_name AS triggered_by_name
            FROM import_logs il
            LEFT JOIN users u ON u.id = il.triggered_by_user_id
            ORDER BY il.started_at DESC
            LIMIT %s
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        return [dict(r) for r in cursor.fetchall()]

    # ── updates ──────────────────────────────────────────────────────────────
    def update_stats(self, import_id: int, stats: dict,
                     conn: Optional[psycopg2.extensions.connection] = None) -> None:
        """Replace the stats JSONB column entirely."""
        query = "UPDATE import_logs SET stats = %s::jsonb WHERE id = %s"
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (json.dumps(stats), import_id))
        safe_commit(conn)

    def update_session_status(self, import_id: int, session_status: str,
                              conn: Optional[psycopg2.extensions.connection] = None) -> None:
        if session_status not in ('active', 'expired', 'missing'):
            raise ValueError(f"Invalid session_status: {session_status}")
        query = "UPDATE import_logs SET session_status = %s WHERE id = %s"
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (session_status, import_id))
        safe_commit(conn)

    def mark_completed(self, import_id: int, stats: dict,
                       conn: Optional[psycopg2.extensions.connection] = None) -> None:
        query = """
            UPDATE import_logs
            SET status = 'completed', finished_at = NOW(), stats = %s::jsonb
            WHERE id = %s
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (json.dumps(stats), import_id))
        safe_commit(conn)

    def mark_failed(self, import_id: int, error_message: str,
                    stats: Optional[dict] = None,
                    conn: Optional[psycopg2.extensions.connection] = None) -> None:
        if stats is not None:
            query = """
                UPDATE import_logs
                SET status = 'failed', finished_at = NOW(),
                    error_message = %s, stats = %s::jsonb
                WHERE id = %s
            """
            params = (error_message, json.dumps(stats), import_id)
        else:
            query = """
                UPDATE import_logs
                SET status = 'failed', finished_at = NOW(),
                    error_message = %s
                WHERE id = %s
            """
            params = (error_message, import_id)
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, params)
        safe_commit(conn)

    def mark_cancelled(self, import_id: int,
                       conn: Optional[psycopg2.extensions.connection] = None) -> None:
        query = """
            UPDATE import_logs
            SET status = 'cancelled', finished_at = NOW()
            WHERE id = %s
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query, (import_id,))
        safe_commit(conn)

    # ── orphan cleanup ───────────────────────────────────────────────────────
    def cleanup_orphans(self,
                        conn: Optional[psycopg2.extensions.connection] = None) -> int:
        """Flip orphaned 'running' rows (from a previous crash) to 'failed'.

        Returns the number of rows updated.
        """
        query = """
            UPDATE import_logs
            SET status = 'failed', finished_at = NOW(),
                error_message = 'Server restarted mid-import'
            WHERE status = 'running'
        """
        conn = self._conn(conn)
        cursor = conn.cursor()
        cursor.execute(query)
        count = cursor.rowcount
        safe_commit(conn)
        if count > 0:
            logger.warning("cleanup_orphans: flipped %d stale 'running' rows to 'failed'",
                           count)
        return count
