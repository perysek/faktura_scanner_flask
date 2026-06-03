"""
Shared helpers for parsing an employee's ``work_schedule`` and validating
that an appointment falls within their working hours.

``work_schedule`` is stored on ``employees.work_schedule`` as a JSON string
(or already-decoded dict) keyed by 3-letter weekday, e.g.::

    {"mon": "9-17", "tue": "9:30-18:30", "wed": "0", "thu": "", "fri": "10-16"}

A value of ``"0"`` or ``""`` (or a missing key) means the employee is off
that day. This module is the single source of truth for that parsing — both
the public booking flow and the internal appointment service import it.
"""
import json
from datetime import datetime, time, date
from typing import Optional, Tuple

# Monday-first, matching Python's date.weekday() (Mon=0 … Sun=6)
WEEKDAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

DEFAULT_WORK_START = time(9, 0)
DEFAULT_WORK_END = time(18, 0)

# Full Polish weekday names for human-readable error messages
DAY_NAMES_PL = {
    'mon': 'poniedziałek', 'tue': 'wtorek', 'wed': 'środa', 'thu': 'czwartek',
    'fri': 'piątek', 'sat': 'sobota', 'sun': 'niedziela',
}


def parse_schedule_time_part(t_str: str) -> time:
    """Parse "H", "HH", or "HH:MM" into a ``time``."""
    t_str = t_str.strip()
    if ':' in t_str:
        return datetime.strptime(t_str, '%H:%M').time()
    return time(int(t_str), 0)


def parse_day_hours(schedule_dict: dict, day_key: str) -> Optional[Tuple[time, time]]:
    """Return (start, end) for a day, or ``None`` if the employee is off.

    Accepts values like "9-17", "9:30-18:30", "0", "".
    """
    val = (schedule_dict.get(day_key) or '').strip()
    if not val or val == '0':
        return None
    parts = val.split('-')
    if len(parts) != 2:
        return None
    try:
        return parse_schedule_time_part(parts[0]), parse_schedule_time_part(parts[1])
    except (ValueError, AttributeError):
        return None


def _decode_schedule(work_schedule_json) -> dict:
    """Decode the stored work_schedule value into a dict (tolerant of bad data)."""
    if not work_schedule_json:
        return {}
    if isinstance(work_schedule_json, dict):
        return work_schedule_json
    try:
        decoded = json.loads(work_schedule_json)
        return decoded if isinstance(decoded, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def work_hours_for_day(work_schedule_json, day_key: str) -> Optional[Tuple[time, time]]:
    """Return (start, end) for a specific weekday key.

    - No schedule defined at all → default Mon–Sun 09:00–18:00 window.
    - Schedule defined but the day is off → ``None``.
    """
    sched = _decode_schedule(work_schedule_json)
    if not sched:
        return DEFAULT_WORK_START, DEFAULT_WORK_END
    return parse_day_hours(sched, day_key)


def _coerce_time(value) -> Optional[time]:
    """Best-effort coerce a time/str/timedelta into a ``time``."""
    from datetime import timedelta
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, timedelta):
        return (datetime.min + value).time()
    if isinstance(value, str):
        for fmt in ('%H:%M:%S', '%H:%M'):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
    return None


def validate_within_working_hours(work_schedule_json, appt_date: date,
                                   start_time, end_time=None) -> Optional[str]:
    """Validate that an appointment falls within the employee's working hours.

    Returns ``None`` when the timing is valid, otherwise a Polish error message
    suitable for surfacing to the user. The message deliberately contains a
    stable marker phrase so the frontend can route it to the right field:

    - off day        → contains "nie pracuje"  (route to the date field)
    - outside hours  → contains "poza godzinami" (route to the start-time field)
    """
    day_key = WEEKDAY_KEYS[appt_date.weekday()]
    hours = work_hours_for_day(work_schedule_json, day_key)

    start_t = _coerce_time(start_time)
    if start_t is None:
        return None  # nothing sensible to validate against

    if hours is None:
        return (f"Pracownik nie pracuje w wybranym dniu "
                f"({DAY_NAMES_PL.get(day_key, day_key)}). Wybierz inny termin.")

    work_start, work_end = hours
    end_t = _coerce_time(end_time)

    # Start must fall inside the working window [work_start, work_end)
    if start_t < work_start or start_t >= work_end:
        return (f"Wizyta poza godzinami pracy pracownika "
                f"({work_start.strftime('%H:%M')}–{work_end.strftime('%H:%M')}). "
                f"Wybrana godzina rozpoczęcia: {start_t.strftime('%H:%M')}.")

    # Visit must also finish by closing time
    if end_t is not None and end_t > work_end:
        return (f"Wizyta poza godzinami pracy pracownika "
                f"({work_start.strftime('%H:%M')}–{work_end.strftime('%H:%M')}). "
                f"Wizyta kończy się o {end_t.strftime('%H:%M')}, po godzinach pracy.")

    return None
