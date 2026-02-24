"""
Migrate data from existing faktury.db (SQLite) to PostgreSQL.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python scripts/migrate_sqlite_to_postgres.py

Or on Render (via Shell tab):
    DATABASE_URL=$DATABASE_URL python scripts/migrate_sqlite_to_postgres.py /data/faktury.db
"""
import os
import sys
import sqlite3

import psycopg2
import psycopg2.extras


def get_pg_url() -> str:
    url = os.environ.get('DATABASE_URL')
    if not url:
        print("ERROR: DATABASE_URL environment variable is not set")
        sys.exit(1)
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


def migrate(sqlite_path: str):
    print(f"Source SQLite: {sqlite_path}")
    if not os.path.exists(sqlite_path):
        print(f"ERROR: SQLite file not found: {sqlite_path}")
        sys.exit(1)

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    pg_conn = psycopg2.connect(get_pg_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    pg_conn.autocommit = False

    tables = ['sellers', 'invoices', 'audit_log', 'duplicate_detection', 'upload_staging']

    for table in tables:
        migrate_table(sqlite_conn, pg_conn, table)

    pg_conn.commit()
    sqlite_conn.close()
    pg_conn.close()
    print("\nMigration complete.")


def migrate_table(sqlite_conn, pg_conn, table: str):
    sc = sqlite_conn.cursor()
    sc.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    if not sc.fetchone():
        print(f"  Skipping {table} — not found in SQLite")
        return

    sc.execute(f"SELECT * FROM {table}")
    rows = sc.fetchall()
    if not rows:
        print(f"  {table}: 0 rows (empty)")
        return

    columns = [desc[0] for desc in sc.description]
    # Exclude 'id' — PostgreSQL SERIAL handles it; we reset sequences after
    non_id_cols = [c for c in columns if c != 'id']
    placeholders = ', '.join(['%s'] * len(non_id_cols))
    col_names = ', '.join(non_id_cols)

    pc = pg_conn.cursor()
    inserted = 0
    skipped = 0
    for row in rows:
        values = tuple(row[c] for c in non_id_cols)
        try:
            pc.execute(
                f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
                values
            )
            inserted += 1
        except psycopg2.errors.UniqueViolation:
            pg_conn.rollback()
            skipped += 1
        except Exception as e:
            pg_conn.rollback()
            print(f"  ERROR in {table}: {e} — row: {dict(zip(non_id_cols, values))}")
            skipped += 1

    # Reset PostgreSQL sequence to max id to avoid conflicts on new inserts
    pc.execute(f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', 'id'),
            COALESCE(MAX(id), 1)
        ) FROM {table}
    """)

    print(f"  {table}: {inserted} inserted, {skipped} skipped")


if __name__ == '__main__':
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else 'faktury.db'
    migrate(sqlite_path)
