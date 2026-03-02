"""
Migrate ALL data from existing faktury.db (SQLite) to PostgreSQL.

Migrates all tables in foreign-key dependency order, preserving original
id values to maintain referential integrity across tables.

Usage:
    export $(grep -v '^#' .env | xargs)
    python scripts/migrate_sqlite_to_postgres.py /home/deploy/faktury_backup.db

Or with explicit DATABASE_URL:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python scripts/migrate_sqlite_to_postgres.py faktury.db
"""
import os
import sys
import sqlite3

import psycopg2
import psycopg2.extras


# SQLite stores booleans as 0/1 integers. These must be cast to Python bool
# before inserting into PostgreSQL BOOLEAN columns.
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

# Migrate in FK dependency order — parents before children.
# Tables not present in the SQLite source are silently skipped.
TABLES = [
    'users',                  # no FKs — authentication accounts
    'sellers',                # no FKs — invoice suppliers
    'clients',                # no FKs — salon clients
    'services',               # no FKs — service catalog
    'employees',              # FK → users
    'invoices',               # FK → sellers
    'service_addons',         # FK → services x2
    'employee_services',      # FK → employees, services
    'employee_availability',  # FK → employees
    'employee_time_off',      # FK → employees
    'client_preferences',     # FK → clients, services, employees
    'appointments',           # FK → clients, employees, users
    'appointment_services',   # FK → appointments, services
    'income_records',         # FK → appointments, clients, employees
    'audit_log',              # FK → invoices
    'duplicate_detection',    # FK → invoices
    'upload_staging',         # no FKs — temporary upload records
]


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

    for table in TABLES:
        migrate_table(sqlite_conn, pg_conn, table)
        # Commit after EACH table so that a later table's errors cannot
        # roll back rows already successfully migrated.
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

    # Include 'id' in the insert to preserve original IDs and maintain
    # referential integrity: if user id=5 becomes id=3 in PostgreSQL,
    # every employee.user_id=5 reference silently points to the wrong record.
    placeholders = ', '.join(['%s'] * len(columns))
    col_names = ', '.join(columns)

    pc = pg_conn.cursor()
    inserted = 0
    skipped = 0
    errors = 0

    for i, row in enumerate(rows):
        values = tuple(coerce_value(table, c, row[c]) for c in columns)
        row_id = row['id'] if 'id' in columns else f'row{i}'
        sp = f"sp_{i}"
        try:
            # SAVEPOINT scopes the rollback to this single row only.
            # Without it, any error would roll back the entire table's work.
            pc.execute(f"SAVEPOINT {sp}")
            pc.execute(
                f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
                values
            )
            pc.execute(f"RELEASE SAVEPOINT {sp}")
            inserted += 1

        except psycopg2.errors.UniqueViolation:
            # Row already exists — safe to skip (idempotent re-run support)
            pc.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            pc.execute(f"RELEASE SAVEPOINT {sp}")
            skipped += 1

        except psycopg2.errors.ForeignKeyViolation:
            # Orphaned row — parent was deleted in SQLite but SQLite doesn't
            # enforce FK constraints by default, leaving ghost references.
            # Example: audit_log entries for deleted invoices.
            pc.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            pc.execute(f"RELEASE SAVEPOINT {sp}")
            skipped += 1

        except psycopg2.errors.CheckViolation as e:
            # Data doesn't satisfy a PostgreSQL CHECK constraint that may not
            # have existed in SQLite (e.g. service category, user role values).
            pc.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            pc.execute(f"RELEASE SAVEPOINT {sp}")
            print(f"  WARN {table} id={row_id}: check constraint — {e.pgerror.strip()}")
            skipped += 1
            errors += 1

        except Exception as e:
            pc.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            pc.execute(f"RELEASE SAVEPOINT {sp}")
            print(f"  ERROR {table} id={row_id}: {e}")
            skipped += 1
            errors += 1

    # Reset the PostgreSQL SERIAL sequence to MAX(id) so future auto-incremented
    # inserts don't collide with the explicitly-inserted IDs.
    try:
        pc.execute(f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', 'id'),
                COALESCE(MAX(id), 1)
            ) FROM {table}
        """)
    except Exception:
        pass  # Some tables may not have a SERIAL sequence — safe to ignore

    status = f"{inserted} inserted, {skipped} skipped"
    if errors:
        status += f" ({errors} need review)"
    print(f"  {table}: {status}")


if __name__ == '__main__':
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else 'faktury.db'
    migrate(sqlite_path)
