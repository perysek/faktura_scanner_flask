"""
Salon wall-clock time — every appointment_date/start_time/end_time is entered
and stored as naive Warsaw local time, but production runs with the OS clock
on UTC (`timedatectl`: Etc/UTC). A bare `datetime.now()` returns naive-UTC, so
comparing it directly against a naive-Warsaw appointment datetime is off by
the UTC offset (2h in summer CEST, 1h in winter CET) — exactly the appointment
status-transition bug (confirmed -> in progress -> completed) this fixes.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

WARSAW_TZ = ZoneInfo('Europe/Warsaw')


def now_local() -> datetime:
    """Current Warsaw wall-clock time, returned naive so it compares directly
    against the naive appointment_date/start_time/end_time values already in
    the database — no mixing of aware and naive datetimes at call sites."""
    return datetime.now(timezone.utc).astimezone(WARSAW_TZ).replace(tzinfo=None)
