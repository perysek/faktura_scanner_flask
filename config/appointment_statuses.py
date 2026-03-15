"""
Appointment status constants — single source of truth.

Usage:
    from config.appointment_statuses import AppointmentStatus

    if status in AppointmentStatus.FINAL:
        ...
    query = f"WHERE status NOT IN ({AppointmentStatus.excluded_placeholders(AppointmentStatus.EXCLUDED_FROM_SCHEDULE)})"
"""


class AppointmentStatus:
    SCHEDULED = 'scheduled'
    PENDING = 'pending'
    CONFIRMED = 'confirmed'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    NO_SHOW = 'no_show'

    # Semantic groups
    FINAL = {COMPLETED, CANCELLED, NO_SHOW}
    ACTIVE = {SCHEDULED, PENDING, CONFIRMED, IN_PROGRESS}
    EXCLUDED_FROM_SCHEDULE = {CANCELLED, NO_SHOW}

    # Valid status transitions (state machine)
    VALID_TRANSITIONS = {
        SCHEDULED: {CONFIRMED, CANCELLED},
        PENDING: {CONFIRMED, CANCELLED},
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
