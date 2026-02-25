"""
Shared database utility helpers for repository row parsing.

PostgreSQL (via psycopg2) returns datetime/date/time columns as Python objects,
while SQLite returns them as strings. These helpers handle both transparently.
"""
from datetime import datetime, date, time


def parse_dt(val) -> datetime | None:
    """Parse a TIMESTAMP/DATETIME column value into a datetime object.

    Handles:
    - None → None
    - datetime object (PostgreSQL) → returned as-is
    - str (SQLite) → parsed with fromisoformat
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(str(val))


def parse_date(val) -> date | None:
    """Parse a DATE column value into a date object.

    Handles:
    - None → None
    - date object (PostgreSQL) → returned as-is
    - datetime object → .date() extracted
    - str (SQLite) → parsed with fromisoformat and .date() extracted
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return datetime.fromisoformat(str(val)).date()


def parse_time(val) -> time | None:
    """Parse a TIME column value into a time object.

    Handles:
    - None → None
    - time object (PostgreSQL) → returned as-is
    - str (SQLite) → parsed with strptime
    """
    if val is None:
        return None
    if isinstance(val, time):
        return val
    return datetime.strptime(str(val), '%H:%M:%S').time()
