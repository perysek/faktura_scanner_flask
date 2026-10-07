"""Projection of a visit's status audit trail onto the "Historia zmian statusu" checkpoints.

Why a replay, and not "the first time each status appeared":

  The edit page is the ONLY way to move a visit backwards — `AppointmentStatus.VALID_TRANSITIONS`
  forbids confirmed -> scheduled (and every other backward step) on the status endpoint — and it
  writes an ordinary audit row. A projection that only remembers the first time a status was reached
  therefore keeps "Potwierdzona" dated for ever after the visit has been put back to "Zaplanowana"
  (principal's report, 2026-10-07; reproduced on a scratch DB).

The rule: replay the audit rows oldest-first. Entering a status on the happy path
(scheduled -> confirmed -> in_progress -> completed) voids every checkpoint ranked above it and any
cancellation / no-show; cancelled and no_show are side branches that keep how far the visit got.
Finally the result is reconciled with the visit's CURRENT status, so a gap in the audit log can
never make the timeline contradict the status badge next to it.

Pure functions only (no DB, no Flask) so every case below is unit-tested without fixtures.
"""
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from config.appointment_statuses import AppointmentStatus as S

# How far along the normal life of a visit each status is. A move onto a LOWER rank is a regression.
HAPPY_PATH_RANK: Dict[str, int] = {S.SCHEDULED: 0, S.CONFIRMED: 1, S.IN_PROGRESS: 2, S.COMPLETED: 3}
# Terminal side branches: they do not void the progress the visit had made.
SIDE_BRANCHES = frozenset({S.CANCELLED, S.NO_SHOW})
_KNOWN = frozenset(HAPPY_PATH_RANK) | SIDE_BRANCHES


def parse_status_value(value: Optional[str]) -> Tuple[str, Optional[str]]:
    """Split an audit value into (bare status, human detail).

    The status endpoint audits `"cancelled (powód)"` and the edit route
    `"scheduled (zmiana terminu przez salon)"`; neither ever equalled the bare status, so a
    cancelled visit's timeline never showed "Anulowana". `"confirmed"` -> `("confirmed", None)`.
    """
    text = (value or '').strip()
    if not text:
        return '', None
    head, sep, tail = text.partition(' (')
    if not sep:
        return head.strip(), None
    detail = tail[:-1] if tail.endswith(')') else tail
    return head.strip(), (detail.strip() or None)


def standing_checkpoints(entries: Iterable[Mapping[str, Any]],
                         current_status: Optional[str],
                         fallbacks: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Return {status: timestamp} for the checkpoints that still STAND today.

    `entries` — audit rows ordered oldest-first, each with `new_value` and `timestamp`.
    `current_status` — the visit's status right now (the row, not the log).
    `fallbacks` — {status: timestamp} used ONLY when the log has no row for the current status
        (e.g. `confirmation_updated_at` for confirmed, `cancelled_at` for cancelled).
    """
    standing: Dict[str, Any] = {}
    for entry in entries:
        status, _ = parse_status_value(entry.get('new_value'))
        at = entry.get('timestamp')
        if status in HAPPY_PATH_RANK:
            rank = HAPPY_PATH_RANK[status]
            for key in [k for k in standing if k in SIDE_BRANCHES or HAPPY_PATH_RANK.get(k, -1) > rank]:
                del standing[key]
            standing[status] = at
        elif status in SIDE_BRANCHES:
            standing[status] = at

    current, _ = parse_status_value(current_status)
    if current in HAPPY_PATH_RANK:
        standing = {k: v for k, v in standing.items()
                    if k in HAPPY_PATH_RANK and HAPPY_PATH_RANK[k] <= HAPPY_PATH_RANK[current]}
    elif current in SIDE_BRANCHES:
        standing = {k: v for k, v in standing.items() if k not in SIDE_BRANCHES or k == current}

    if current in _KNOWN and current not in standing and fallbacks and fallbacks.get(current):
        standing[current] = fallbacks[current]
    return standing
