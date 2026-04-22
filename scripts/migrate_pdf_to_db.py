"""
Backfill pdf_data BYTEA column for existing invoices.

Reads PDF/image files from the LOCAL uploads folder and pushes the bytes
directly into the Vultr PostgreSQL database over the network.

Usage:
    # Point DATABASE_URL at the VULTR database, then run locally:
    DATABASE_URL=postgresql://user:pass@<vultr-ip>:5432/dbname python scripts/migrate_pdf_to_db.py

    # Or load from .env.local (if it contains the Vultr DATABASE_URL):
    export $(grep -v '^#' .env.local | xargs) && python scripts/migrate_pdf_to_db.py

    # Dry-run — shows what would be updated without writing anything:
    python scripts/migrate_pdf_to_db.py --dry-run
"""
import os
import sys
import argparse
from pathlib import Path

import psycopg2
import psycopg2.extras

# Local uploads folder — adjust if your UPLOAD_FOLDER differs
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
LOCAL_UPLOADS = Path(os.environ.get('UPLOAD_FOLDER', PROJECT_ROOT / 'uploads'))


def get_pg_url() -> str:
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        print("ERROR: DATABASE_URL is not set.")
        print("  Set it to your Vultr PostgreSQL connection string, e.g.:")
        print("  DATABASE_URL=postgresql://user:pass@<vultr-ip>:5432/dbname")
        sys.exit(1)
    # Normalise render-style postgres:// → postgresql://
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    return url


def resolve_local_path(stored_path: str) -> Path | None:
    """Try to find the file locally given the path stored in the DB.

    The DB may store an absolute path from another machine, so we fall back
    to searching by filename in the local uploads tree.
    """
    if not stored_path:
        return None

    # 1. Exact path as stored (works if running on the same machine)
    p = Path(stored_path)
    if p.exists():
        return p

    # 2. Just the filename, in the local uploads root
    filename = Path(stored_path).name
    candidate = LOCAL_UPLOADS / filename
    if candidate.exists():
        return candidate

    # 3. Walk the full uploads tree (handles sub-folders like temp/session_id/)
    for found in LOCAL_UPLOADS.rglob(filename):
        return found  # return first match

    return None


def run(dry_run: bool = False) -> None:
    conn = psycopg2.connect(get_pg_url(), cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, pdf_path, pdf_filename
                FROM invoices
                WHERE pdf_data IS NULL
                  AND pdf_path IS NOT NULL
                  AND is_deleted = FALSE
                ORDER BY id
            """)
            rows = cur.fetchall()

        total = len(rows)
        print(f"Found {total} invoice(s) with pdf_path but no pdf_data.\n")

        if total == 0:
            print("Nothing to migrate.")
            return

        updated = 0
        skipped = 0

        for row in rows:
            invoice_id = row['id']
            stored_path = row['pdf_path']
            existing_filename = row['pdf_filename']

            local_file = resolve_local_path(stored_path)

            if not local_file:
                print(f"  [SKIP] id={invoice_id}  — file not found locally: {stored_path}")
                skipped += 1
                continue

            filename = existing_filename or local_file.name
            file_size = local_file.stat().st_size
            print(f"  [{'DRY ' if dry_run else 'PUSH'}] id={invoice_id}  {filename}  ({file_size / 1024:.1f} KB)")

            if dry_run:
                updated += 1
                continue

            with open(local_file, 'rb') as fh:
                pdf_bytes = fh.read()

            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE invoices
                    SET pdf_data = %s,
                        pdf_filename = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (psycopg2.Binary(pdf_bytes), filename, invoice_id)
                )
            conn.commit()
            updated += 1

        print(f"\nDone. Updated: {updated}  Skipped (file missing): {skipped}")
        if dry_run:
            print("(dry-run — no changes written)")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill pdf_data for existing invoices')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without writing')
    args = parser.parse_args()
    run(dry_run=args.dry_run)
