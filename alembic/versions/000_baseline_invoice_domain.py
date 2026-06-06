"""Baseline: invoice-domain + roles tables (formerly database/schema.sql)

Revision ID: 000_baseline
Revises:
Create Date: 2026-06-06

Improvement area #1 — Schema dual-track.
=========================================

Before this migration the schema lived in **two** independently-evolving
places:

* ``database/schema.sql`` — created the *invoice domain* (invoices, sellers,
  audit_log, duplicate_detection, upload_staging) and the *roles* tables. It
  was executed on **every app boot** by ``initialize_database()``.
* the Alembic chain (starting at ``001``) — created users/employees/clients/
  services/appointments/absences/... and ``ALTER``-ed the invoice-domain tables
  added above (e.g. ``add_pdf_data_to_invoices``, ``add_soft_delete_columns``,
  ``add_performance_indexes``).

That split meant a fresh ``alembic upgrade head`` on an empty database would
**crash** the first time a migration tried to ``ALTER invoices`` — because the
``invoices`` table only ever existed in ``schema.sql``, never in a migration.

This migration closes the gap: it becomes the **new root of the chain** and
applies the same ``schema.sql`` DDL the bootstrap used to run, so a fresh DB
builds the invoice domain first, and the existing ALTER migrations downstream
find their target tables exactly as they always did on production.

Idempotency / safety
--------------------
* ``schema.sql`` is fully idempotent (``CREATE TABLE IF NOT EXISTS``,
  ``CREATE INDEX IF NOT EXISTS``, ``INSERT ... ON CONFLICT DO NOTHING``,
  guarded ``DO $$ ... $$`` blocks). Running it against a database that already
  has these objects is a no-op.
* **Existing production databases are already at head** — they never re-run this
  root (Alembic only applies revisions between the recorded version and head).
  So this is a pure fresh-install enabler with zero effect on live data.
"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '000_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Path to the canonical baseline DDL. From alembic/versions/<file>.py the
# project root is three parents up.
_SCHEMA_SQL = Path(__file__).resolve().parents[2] / "database" / "schema.sql"


def _is_blank_or_comment_only(stmt: str) -> bool:
    """True if a chunk has no executable SQL (only blank lines / -- comments).

    SQLAlchemy 2.0 raises ObjectNotExecutableError for a comment-only string,
    so these chunks must be skipped rather than executed.
    """
    for line in stmt.splitlines():
        s = line.strip()
        if s and not s.startswith('--'):
            return False
    return True


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL into individual statements, respecting dollar-quotes AND comments.

    A naive ``split(';')`` breaks two things:
      * PostgreSQL ``DO $$ BEGIN ... END $$`` blocks (internal semicolons that
        are NOT terminators) — handled by tracking dollar-quote depth.
      * a ``;`` that appears inside a ``-- line comment`` — handled by skipping
        to end-of-line when a ``--`` comment starts outside a dollar-quote.

    The second case is the bug that motivated this hardened copy: the previous
    parser was comment-blind, so any semicolon inside a ``--`` comment produced
    a bogus comment-only statement.
    """
    statements: list[str] = []
    current: list[str] = []
    in_dollar_quote = False
    dollar_tag = ''
    i = 0
    n = len(sql)

    while i < n:
        ch = sql[i]

        # Line comment outside a dollar-quote: copy verbatim to end-of-line so
        # any ';' inside it is NOT treated as a statement terminator.
        if not in_dollar_quote and ch == '-' and i + 1 < n and sql[i + 1] == '-':
            eol = sql.find('\n', i)
            if eol == -1:
                current.append(sql[i:])
                i = n
            else:
                current.append(sql[i:eol + 1])
                i = eol + 1
            continue

        # Dollar-quote open/close (e.g. $$ or $body$).
        if ch == '$':
            j = sql.find('$', i + 1)
            if j != -1:
                tag = sql[i:j + 1]
                if in_dollar_quote and tag == dollar_tag:
                    in_dollar_quote = False
                    current.append(tag)
                    i = j + 1
                    continue
                elif not in_dollar_quote:
                    in_dollar_quote = True
                    dollar_tag = tag
                    current.append(tag)
                    i = j + 1
                    continue

        if ch == ';' and not in_dollar_quote:
            stmt = ''.join(current).strip()
            if stmt and not _is_blank_or_comment_only(stmt):
                statements.append(stmt)
            current = []
        else:
            current.append(ch)
        i += 1

    stmt = ''.join(current).strip()
    if stmt and not _is_blank_or_comment_only(stmt):
        statements.append(stmt)
    return statements


def upgrade() -> None:
    """Create the invoice-domain + roles baseline from database/schema.sql.

    Executes each statement via ``exec_driver_sql`` (raw psycopg2, the same
    engine ``initialize_database`` always used) rather than ``op.execute`` —
    this tolerates leading comments and runs inside Alembic's transaction.
    """
    schema = _SCHEMA_SQL.read_text(encoding="utf-8")
    bind = op.get_bind()
    for statement in _split_sql_statements(schema):
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    """Drop the baseline objects.

    Never invoked in normal operation (production stays at head). Provided for
    correctness so ``downgrade base`` fully unwinds the chain. Order respects
    foreign keys: dependent tables first.
    """
    for table in (
        "role_permissions",
        "roles",
        "upload_staging",
        "duplicate_detection",
        "audit_log",
        "sellers",
        "invoices",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
