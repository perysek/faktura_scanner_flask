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
    # Execute each statement separately (psycopg2 does not support executescript)
    for statement in schema.split(';'):
        stmt = statement.strip()
        if stmt:
            cursor.execute(stmt)

    conn.commit()
    conn.close()
    print("Baza danych zainicjalizowana")
