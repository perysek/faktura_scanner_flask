"""
Konfiguracja bazy danych PostgreSQL
"""
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from flask import g

logger = logging.getLogger(__name__)

# Module-level connection pool
_pool: Optional[ThreadedConnectionPool] = None


def get_database_url() -> str:
    """Get the PostgreSQL database URL from environment"""
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    # Render uses postgres:// but psycopg2 requires postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


def initialize_pool() -> None:
    """Create the ThreadedConnectionPool from environment configuration.

    Reads:
        DB_POOL_MIN        — minimum connections (default 2)
        DB_POOL_MAX        — maximum connections (default 10)
        DB_CONNECT_TIMEOUT — connect timeout in seconds (default 5)
        DB_STATEMENT_TIMEOUT — statement timeout in milliseconds (default 30000)
    """
    global _pool

    minconn = int(os.environ.get('DB_POOL_MIN', '2'))
    maxconn = int(os.environ.get('DB_POOL_MAX', '10'))
    connect_timeout = int(os.environ.get('DB_CONNECT_TIMEOUT', '5'))
    statement_timeout = int(os.environ.get('DB_STATEMENT_TIMEOUT', '30000'))

    dsn = get_database_url()
    _pool = ThreadedConnectionPool(
        minconn,
        maxconn,
        dsn,
        connect_timeout=connect_timeout,
        options=f'-c statement_timeout={statement_timeout}',
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    logger.info(f"Connection pool initialized: min={minconn}, max={maxconn}")


def get_pool() -> ThreadedConnectionPool:
    """Return the module-level connection pool.

    Raises RuntimeError if initialize_pool() has not been called.
    """
    if _pool is None:
        raise RuntimeError(
            "Connection pool not initialized. Call initialize_pool() first."
        )
    return _pool


def close_pool() -> None:
    """Close all connections in the pool and reset the module reference."""
    global _pool
    if _pool is not None:
        try:
            _pool.closeall()
        except Exception:
            logger.exception("Error closing connection pool")
        _pool = None
        logger.info("Connection pool closed")


def get_db_connection() -> psycopg2.extensions.connection:
    """Helper function to get database connection (used by repositories)"""
    return DatabaseConnection.get_connection()


def is_in_transaction() -> bool:
    """Check whether the current request is inside a managed_transaction scope.

    Returns False when called from a background thread (no app context) —
    threads have no managed_transaction, so safe_commit always commits.
    """
    try:
        return getattr(g, '_in_transaction', False)
    except RuntimeError:
        return False  # No app context = no managed transaction


def safe_commit(conn):
    """Commit unless inside a managed_transaction scope.

    Repository methods call this instead of ``conn.commit()`` so that
    individual commits are suppressed when wrapped by managed_transaction.
    """
    if not is_in_transaction():
        conn.commit()


@contextmanager
def managed_transaction():
    """Wrap multiple repo calls in a single atomic transaction.

    Usage::

        with managed_transaction():
            repo_a.create(...)
            repo_b.create(...)
        # commits on success, rolls back on any exception

    Repo methods that normally call ``safe_commit(conn)`` will skip the
    commit when ``g._in_transaction`` is ``True``.
    """
    conn = DatabaseConnection.get_connection()
    g._in_transaction = True
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        g._in_transaction = False


class DatabaseConnection:
    """Per-request database connection using Flask's g object"""

    @classmethod
    def get_connection(cls) -> psycopg2.extensions.connection:
        """Get per-request database connection from Flask's g object.

        Obtains a connection from the pool, validates it with a health
        check (SELECT 1), and stores it in Flask ``g`` for the duration
        of the request.
        """
        if 'db' not in g:
            pool = get_pool()
            conn = pool.getconn()
            # Health check — replace dead/stale connections
            try:
                cur = conn.cursor()
                cur.execute('SELECT 1')
                cur.close()
            except Exception:
                # Connection is dead — discard and get a fresh one
                pool.putconn(conn, close=True)
                conn = pool.getconn()
            g.db = conn
        return g.db

    @classmethod
    def close_connection(cls):
        """Return the connection to the pool for current request context."""
        db = g.pop('db', None)
        if db is not None:
            try:
                pool = get_pool()
                pool.putconn(db)
            except Exception:
                # Pool already closed or connection already returned
                logger.debug("Could not return connection to pool", exc_info=True)

    @classmethod
    def close(cls):
        """Alias for close_connection for backward compatibility"""
        cls.close_connection()


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL into individual statements, respecting dollar-quoted blocks.

    A naive split(';') breaks PostgreSQL DO $$ BEGIN ... END $$ blocks because
    they contain internal semicolons that are NOT statement terminators.
    This parser tracks dollar-quote depth to split only at real boundaries.
    """
    statements = []
    current: list[str] = []
    in_dollar_quote = False
    dollar_tag = ''
    i = 0

    while i < len(sql):
        ch = sql[i]

        # Detect start/end of a dollar-quoted string (e.g. $$ or $body$)
        if ch == '$':
            j = sql.find('$', i + 1)
            if j != -1:
                tag = sql[i:j + 1]
                if in_dollar_quote and tag == dollar_tag:
                    # Closing tag — exit dollar-quote mode
                    in_dollar_quote = False
                    current.append(tag)
                    i = j + 1
                    continue
                elif not in_dollar_quote:
                    # Opening tag — enter dollar-quote mode
                    in_dollar_quote = True
                    dollar_tag = tag
                    current.append(tag)
                    i = j + 1
                    continue

        if ch == ';' and not in_dollar_quote:
            stmt = ''.join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(ch)

        i += 1

    # Capture any trailing statement without a final semicolon
    stmt = ''.join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements


def initialize_database():
    """Inicjalizuj bazę danych ze schema.

    Requires initialize_pool() to have been called first.
    """
    pool = get_pool()
    conn = pool.getconn()
    try:
        schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = f.read()

        cursor = conn.cursor()
        for stmt in _split_sql_statements(schema):
            cursor.execute(stmt)

        conn.commit()
        logger.info("Baza danych zainicjalizowana")
    finally:
        pool.putconn(conn)
