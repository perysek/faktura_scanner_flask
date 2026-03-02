"""
Konfiguracja bazy danych PostgreSQL
"""
import os
from pathlib import Path
from typing import Optional

import psycopg2
import psycopg2.extras
from flask import g


def get_database_url() -> str:
    """Get the PostgreSQL database URL from environment"""
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    # Render uses postgres:// but psycopg2 requires postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


def get_db_connection() -> psycopg2.extensions.connection:
    """Helper function to get database connection (used by repositories)"""
    return DatabaseConnection.get_connection()


class DatabaseConnection:
    """Per-request database connection using Flask's g object"""

    @classmethod
    def get_connection(cls) -> psycopg2.extensions.connection:
        """Get per-request database connection from Flask's g object"""
        if 'db' not in g:
            g.db = psycopg2.connect(
                get_database_url(),
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        return g.db

    @classmethod
    def close_connection(cls):
        """Close the connection for current request context"""
        db = g.pop('db', None)
        if db is not None and not db.closed:
            db.close()

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
    """Inicjalizuj bazę danych ze schema"""
    conn = psycopg2.connect(
        get_database_url(),
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = f.read()

    cursor = conn.cursor()
    for stmt in _split_sql_statements(schema):
        cursor.execute(stmt)

    conn.commit()
    conn.close()
    print("Baza danych zainicjalizowana")
