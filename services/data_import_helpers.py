"""
Lookup builders, resolvers, and parsers for the caldis.pl import pipeline.

DB layer: PostgreSQL via psycopg2 + RealDictCursor (configured globally in
config.database). All queries use %s placeholders. Builders take a connection
and run a single SELECT each.

Resolvers and date/time parsers are pure functions — they accept the prebuilt
lookup maps and individual cell values, returning ids or normalised strings.
No DB access inside resolvers.

Mirrors the business rules of scripts/import_appointments_playwright.py,
ported to PostgreSQL.
"""
import re
import logging
from datetime import datetime, date
from typing import Any, Optional

import pandas as pd
import psycopg2.extensions

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────────────
DEFAULT_SERVICE_ID: int = 20
"""Fallback service id when category lookup fails. Verified against production."""

KALENDARZ_OVERRIDES: dict = {
    "zrecepcja asia": (3, 24),  # Joanna Asia → Masaż klasyczny
}
"""Hand-curated Kalendarz → (employee_id, service_id) overrides."""


# ── Utility ──────────────────────────────────────────────────────────────────
def _is_blank(v: Any) -> bool:
    """Return True if v is None, NaN, empty string, or 'nan' literal."""
    if v is None:
        return True
    try:
        if isinstance(v, float) and pd.isna(v):
            return True
    except Exception:
        pass
    s = str(v).strip()
    return not s or s.lower() == 'nan'


# ── DB Lookup Builders ───────────────────────────────────────────────────────

def build_employee_map(conn: psycopg2.extensions.connection) -> dict:
    """Return {first_name_lower: employee_id} for fast Kalendarz matching."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, first_name FROM employees")
    rows = cursor.fetchall()
    return {r['first_name'].strip().lower(): r['id'] for r in rows}


def build_client_map(conn: psycopg2.extensions.connection) -> dict:
    """Return {(first_name_lower, last_name_lower): client_id} with reversed-order fallback."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, first_name, last_name FROM clients")
    rows = cursor.fetchall()
    result: dict = {}
    for r in rows:
        fn = (r['first_name'] or '').strip().lower()
        ln = (r['last_name'] or '').strip().lower()
        result[(fn, ln)] = r['id']
        if ln:
            result.setdefault((ln, fn), r['id'])
    return result


def build_phone_map(conn: psycopg2.extensions.connection) -> dict:
    """Return {normalized_phone: client_id} for phone-fallback resolution."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, phone FROM clients WHERE phone IS NOT NULL AND phone != ''"
    )
    rows = cursor.fetchall()
    return {r['phone'].strip(): r['id'] for r in rows}


def build_service_map(conn: psycopg2.extensions.connection) -> list:
    """Return [(service_id, name_lower), ...] sorted ascending by id."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM services ORDER BY id")
    rows = cursor.fetchall()
    return [(r['id'], r['name'].strip().lower()) for r in rows]


# ── Resolvers (pure) ─────────────────────────────────────────────────────────

def resolve_employee_id(kalendarz: Any, employee_map: dict) -> Optional[int]:
    """Match the 'Kalendarz' xlsx cell to an employee.id.

    Strategy:
      1. Exact case-insensitive match
      2. Longest-first substring match (avoids false positives like 'a' in 'kasia')
    Returns None if nothing matches.
    """
    if _is_blank(kalendarz):
        return None
    val = str(kalendarz).strip().lower()
    if val in employee_map:
        return employee_map[val]
    for first_name_lower in sorted(employee_map, key=len, reverse=True):
        if first_name_lower in val:
            return employee_map[first_name_lower]
    return None


def normalize_phone(raw_phone: Any) -> Optional[str]:
    """Normalize to '48XXXXXXXXX'.

    Handles: '504020116', ' 504 020 116', '+48504020116', '0048504020116'.
    Returns None if not a valid Polish mobile.
    """
    if _is_blank(raw_phone):
        return None
    phone = str(raw_phone).strip().replace(' ', '').replace('-', '')
    if phone.startswith('+48'):
        phone = phone[3:]
    elif phone.startswith('0048'):
        phone = phone[4:]
    elif phone.startswith('+'):
        phone = phone[1:]
    phone = re.sub(r'\D', '', phone)
    if len(phone) == 9:
        return f'48{phone}'
    if len(phone) == 11 and phone.startswith('48'):
        return phone
    return None


def _strip_prefix(full_name: str) -> str:
    """Remove 'p.' prefix from full name."""
    cleaned = re.sub(r'^\s*p\.\s*', '', full_name.strip(), flags=re.IGNORECASE)
    return cleaned.strip()


def _resolve_by_phone(phone_raw: Any, phone_map: Optional[dict]) -> Optional[int]:
    if phone_map is None:
        return None
    normalized = normalize_phone(phone_raw)
    if normalized is None:
        return None
    return phone_map.get(normalized)


def parse_client_name(full_name_raw: Any) -> Optional[tuple]:
    """Split a raw 'Imie i nazwisko' cell into (first_name, last_name), 'p.' stripped.

    Returns None for a blank cell or the 'Wolne' placeholder (a blocked calendar
    slot, not a real client) — mirrors the same guard resolve_client_id uses, so
    callers deciding whether to auto-create a client stay consistent with what
    resolve_client_id would ever match against.
    """
    if _is_blank(full_name_raw):
        return None
    cleaned = _strip_prefix(str(full_name_raw))
    if not cleaned or cleaned.lower() == 'wolne':
        return None
    parts = cleaned.split(None, 1)
    if not parts:
        return None
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ''
    return (first_name, last_name)


def create_client(conn: psycopg2.extensions.connection,
                  first_name: str, last_name: str,
                  phone: Optional[str]) -> int:
    """Insert a new client discovered via caldis.pl import, return its id.

    A caldis.pl booking for a name that matches no existing client is a new
    customer, not a data error — the salon's calendar is the source of truth.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO clients (first_name, last_name, phone, is_active, created_at, updated_at)
        VALUES (%s, %s, %s, TRUE, NOW(), NOW())
        RETURNING id
        """,
        (first_name, last_name, phone),
    )
    return cursor.fetchone()['id']


def resolve_client_id(full_name_raw: Any, client_map: dict,
                      phone_raw: Any = None,
                      phone_map: Optional[dict] = None) -> Optional[int]:
    """Match 'Imie i nazwisko' xlsx cell to a client.id.

    Order: prefix-stripped exact → reversed order → first-name-only → phone.
    """
    if _is_blank(full_name_raw):
        return _resolve_by_phone(phone_raw, phone_map)
    cleaned = _strip_prefix(str(full_name_raw))
    if not cleaned or cleaned.lower() == 'wolne':
        return None
    parts = cleaned.split(None, 1)
    if not parts:
        return _resolve_by_phone(phone_raw, phone_map)
    fn = parts[0].lower()
    ln = parts[1].lower() if len(parts) > 1 else ''
    if (fn, ln) in client_map:
        return client_map[(fn, ln)]
    if ln and (ln, fn) in client_map:
        return client_map[(ln, fn)]
    if (fn, '') in client_map:
        return client_map[(fn, '')]
    if ln and (ln, '') in client_map:
        return client_map[(ln, '')]
    return _resolve_by_phone(phone_raw, phone_map)


def resolve_service_id(kategoria: Any, service_list: list) -> int:
    """Match the 'Kategoria' xlsx cell to a service.id.

    Order: exact → service name starts with kategoria → kategoria starts with
    service name → DEFAULT_SERVICE_ID.
    """
    if _is_blank(kategoria):
        return DEFAULT_SERVICE_ID
    kat = str(kategoria).strip().lower()
    for svc_id, svc_name in service_list:
        if svc_name == kat:
            return svc_id
    for svc_id, svc_name in service_list:
        if svc_name.startswith(kat):
            return svc_id
    for svc_id, svc_name in service_list:
        if kat.startswith(svc_name):
            return svc_id
    logger.warning("resolve_service_id: no match for kategoria=%r, "
                   "falling back to DEFAULT_SERVICE_ID=%d", kategoria, DEFAULT_SERVICE_ID)
    return DEFAULT_SERVICE_ID


# ── Date / Time Helpers ──────────────────────────────────────────────────────

def parse_appointment_date(cell_value: Any) -> Optional[str]:
    """Return 'YYYY-MM-DD' from a date/datetime/string cell, or None."""
    if _is_blank(cell_value):
        return None
    if isinstance(cell_value, (datetime, date)):
        return cell_value.strftime('%Y-%m-%d')
    try:
        dt = pd.to_datetime(str(cell_value))
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return None


def parse_time(cell_value: Any) -> Optional[str]:
    """Return 'HH:MM:SS' from a datetime/string cell, or None."""
    if _is_blank(cell_value):
        return None
    if isinstance(cell_value, datetime):
        return cell_value.strftime('%H:%M:%S')
    try:
        dt = pd.to_datetime(str(cell_value))
        return dt.strftime('%H:%M:%S')
    except Exception:
        return None


def parse_created_at(cell_value: Any) -> str:
    """Return 'YYYY-MM-DD HH:MM:SS'. Falls back to current time."""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if _is_blank(cell_value):
        return now_str
    try:
        dt = pd.to_datetime(str(cell_value))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return now_str


def calc_duration_minutes(od_cell: Any, do_cell: Any) -> int:
    """Calculate duration in minutes from Od/Do cells. Returns 0 on parse failure."""
    try:
        start = pd.to_datetime(str(od_cell))
        end = pd.to_datetime(str(do_cell))
        return max(int((end - start).total_seconds() / 60), 0)
    except Exception:
        return 0
