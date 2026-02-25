"""
Migrate data from existing faktury.db (SQLite) to PostgreSQL.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python scripts/migrate_sqlite_to_postgres.py

Or on Vultr server:
    export $(grep -v '^#' .env | xargs)
    python scripts/migrate_sqlite_to_postgres.py /home/deploy/faktury_backup.db
"""
import os
import sys
import sqlite3

import psycopg2
import psycopg2.extras


# SQLite stores booleans as 0/1 integers. These columns must be cast to
# Python bool before inserting into PostgreSQL BOOLEAN columns.
BOOLEAN_COLUMNS = {
    'invoices': ['is_duplicate'],
    'employees': ['is_active'],
    'clients': ['is_active'],
    'services': ['is_active'],
    'employee_services': ['is_active'],
    'appointment_services': ['is_addon'],
    'employee_availability': ['is_available'],
    'users': ['is_active'],
}


def get_pg_url() -> str:
    url = os.environ.get('DATABASE_URL')
    if not url:
        print("ERROR: DATABASE_URL environment variable is not set")
        sys.exit(1)
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


def coerce_value(table: str, col: str, value):
    """Cast SQLite integer booleans to Python bool for PostgreSQL."""
    bool_cols = BOOLEAN_COLUMNS.get(table, [])
    if col in bool_cols and value is not None:
        return bool(value)
    return value


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
        # Commit after EACH table so that an error in a later table
        # cannot roll back rows already successfully migrated.
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
    # Exclude 'id' — PostgreSQL SERIAL auto-assigns it; sequences are reset after
    non_id_cols = [c for c in columns if c != 'id']
    placeholders = ', '.join(['%s'] * len(non_id_cols))
    col_names = ', '.join(non_id_cols)

    pc = pg_conn.cursor()
    inserted = 0
    skipped = 0
    for i, row in enumerate(rows):
        values = tuple(coerce_value(table, c, row[c]) for c in non_id_cols)
        sp = f"sp_{table}_{i}"
        try:
            # SAVEPOINT rolls back only this single row on error,
            # leaving all previously inserted rows in the transaction intact.
            pc.execute(f"SAVEPOINT {sp}")
            pc.execute(
                f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
                values
            )
            pc.execute(f"RELEASE SAVEPOINT {sp}")
            inserted += 1
        except psycopg2.errors.UniqueViolation as e:
            pc.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            pc.execute(f"RELEASE SAVEPOINT {sp}")
            skipped += 1
        except psycopg2.errors.ForeignKeyViolation as e:
            # Audit log entries for invoices that were deleted in SQLite are
            # silently dropped — the invoice no longer exists, so neither
            # should its history.
            pc.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            pc.execute(f"RELEASE SAVEPOINT {sp}")
            skipped += 1
        except Exception as e:
            pc.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            pc.execute(f"RELEASE SAVEPOINT {sp}")
            print(f"  ERROR in {table}: {e} — row: {dict(zip(non_id_cols, values))}")
            skipped += 1

    # Reset PostgreSQL sequence to max id so new inserts don't conflict
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
