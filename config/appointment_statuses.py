"""
Appointment status constants — single source of truth.

Usage:
    from config.appointment_statuses import AppointmentStatus

    if status in AppointmentStatus.FINAL:
        ...
    clause, params = BaseRepository._in_clause(list(AppointmentStatus.EXCLUDED_FROM_SCHEDULE))
    query = f"WHERE status NOT IN {clause}"
"""


class AppointmentStatus:
    SCHEDULED = 'scheduled'
    CONFIRMED = 'confirmed'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    NO_SHOW = 'no_show'
    RESCHEDULED = 'rescheduled'   # frozen original of a reschedule — see services.appointment_service.reschedule_appointment

    # Semantic groups
    #
    # RESCHEDULED is deliberately NOT in FINAL: the past-visit scanner
    # (routes/appointment_routes.py update_past_appointment_status) gates
    # allowed resolutions on `new_status in FINAL` — adding RESCHEDULED there
    # would let staff retroactively set a past appointment to 'rescheduled'
    # with no clone created. NEEDS_NO_RESOLUTION is the superset that route's
    # sibling past-pending queries should actually exclude instead.
    FINAL = {COMPLETED, CANCELLED, NO_SHOW}
    NEEDS_NO_RESOLUTION = FINAL | {RESCHEDULED}
    ACTIVE = {SCHEDULED, CONFIRMED, IN_PROGRESS}
    EXCLUDED_FROM_SCHEDULE = {CANCELLED, NO_SHOW, RESCHEDULED}

    # Valid status transitions (state machine)
    #
    # RESCHEDULED is deliberately absent as a VALUE here too (never a plain
    # status flip — always the compound freeze+clone operation in
    # AppointmentBusinessService.reschedule_appointment, gated by its own
    # scheduled/confirmed-only eligibility check). Adding it under
    # SCHEDULED/CONFIRMED would let PUT /appointments/<id>/status flip the
    # status with no clone, breaking "every rescheduled visit gets a clone".
    VALID_TRANSITIONS = {
        SCHEDULED: {CONFIRMED, IN_PROGRESS, CANCELLED},   # IN_PROGRESS: walk-in bypass (no confirmation needed)
        CONFIRMED: {IN_PROGRESS, CANCELLED, NO_SHOW},
        IN_PROGRESS: {COMPLETED, CANCELLED},
    }

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if a status transition is valid."""
        allowed = cls.VALID_TRANSITIONS.get(from_status)
        if allowed is None:
            return False
        return to_status in allowed
