"""
Salon wall-clock time — every appointment_date/start_time/end_time is entered
and stored as naive Warsaw local time, but production runs with the OS clock
on UTC (`timedatectl`: Etc/UTC). A bare `datetime.now()` returns naive-UTC, so
comparing it directly against a naive-Warsaw appointment datetime is off by
the UTC offset (2h in summer CEST, 1h in winter CET) — exactly the appointment
status-transition bug (confirmed -> in progress -> completed) this fixes.
"""
import re
from datetime import datetime, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

WARSAW_TZ = ZoneInfo('Europe/Warsaw')


def now_local() -> datetime:
    """Current Warsaw wall-clock time, returned naive so it compares directly
    against the naive appointment_date/start_time/end_time values already in
    the database — no mixing of aware and naive datetimes at call sites."""
    return datetime.now(timezone.utc).astimezone(WARSAW_TZ).replace(tzinfo=None)


def to_local(dt: datetime) -> datetime:
    """Convert a naive server-clock timestamp (e.g. a `TIMESTAMP DEFAULT
    CURRENT_TIMESTAMP` column like audit_log.changed_at — naive-UTC, same
    origin as now_local()'s own UTC fetch) to naive Warsaw wall-clock time,
    for display. Diffing two such columns needs no conversion (same
    reference frame); only showing a clock time to a person does."""
    return dt.replace(tzinfo=timezone.utc).astimezone(WARSAW_TZ).replace(tzinfo=None)


def to_local_any(dt: datetime) -> datetime:
    """Naive Warsaw wall-clock for EITHER kind of database timestamp.

    `audit_log.changed_at` is a naive-UTC TIMESTAMP (`to_local`), but `sms_reminders.sent_at`,
    `sms_events.scheduled_at` and friends are TIMESTAMPTZ and arrive timezone-aware — feeding
    those to `to_local` would silently relabel their offset as UTC. This accepts both."""
    if dt.tzinfo is None:
        return to_local(dt)
    return dt.astimezone(WARSAW_TZ).replace(tzinfo=None)


def parse_year_month(value: Optional[str]) -> Optional[Tuple[int, int]]:
    """'2026-10' -> (2026, 10). Empty/None -> None. Anything else raises ValueError (callers answer 400)."""
    if not value:
        return None
    match = re.fullmatch(r'(\d{4})-(\d{2})', value.strip())
    if not match or not (2000 <= int(match[1]) <= 2100 and 1 <= int(match[2]) <= 12):
        raise ValueError(f'expected YYYY-MM, got {value!r}')
    return int(match[1]), int(match[2])


def first_of_next_month(year: int, month: int) -> datetime:
    """Naive Warsaw midnight that opens the month AFTER (year, month): the exclusive upper bound of
    "everything up to the end of that month"."""
    return datetime(year + (month == 12), month % 12 + 1, 1)
