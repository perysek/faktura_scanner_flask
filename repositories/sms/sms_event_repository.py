"""Repository for event-triggered SMS scheduling (sms_events table)."""
from datetime import datetime
from typing import List, Optional

from repositories.base_repository import BaseRepository

# What counts as a PENDING event: still scheduled, and its visit still exists. ONE definition shared by
# get_due() (what the scheduler sends) and get_scheduled_for_queue() (what the "Oczekujące" page lists), so
# the page can never list something the scheduler will not send, nor hide something it will.
#
# The visit clause matters: deleting a visit used to leave its queued events behind, and an
# `employee_visit_reminder` carries no check of its own, so the employee would still have been texted about a
# visit that no longer exists (found on the live site, 2026-10-07: the principal's own deleted test visit had
# one queued for his own phone). delete_appointment now cancels them too; this filter is the safety net for
# every other way a visit can be soft-deleted, and for orphans created before that.
PENDING_EVENT_FILTER = "e.status = 'scheduled' AND a.is_deleted IS NOT TRUE"


class SmsEventRepository(BaseRepository):
    """Manages the sms_events queue for event-triggered outbound SMS."""

    def __init__(self):
        super().__init__('sms_events')

    def create(self, appointment_id: int, event_type: str,
               scheduled_at: datetime) -> int:
        """Insert an sms_events row. Returns the new id."""
        sql = """
            INSERT INTO sms_events (appointment_id, event_type, scheduled_at)
            VALUES (%s, %s, %s)
        """
        return self._execute_insert(sql, (appointment_id, event_type, scheduled_at))

    def get_due(self) -> List[dict]:
        """Return the pending events (see PENDING_EVENT_FILTER) whose scheduled_at has come."""
        sql = f"""
            SELECT e.*, a.rating_token, a.client_id,
                   a.appointment_date, a.start_time, a.employee_token,
                   emp.phone      AS employee_phone,
                   emp.first_name AS employee_first_name,
                   emp.last_name  AS employee_last_name,
                   c.first_name || ' ' || c.last_name AS employee_client_name
            FROM sms_events e
            JOIN appointments a ON a.id = e.appointment_id
            LEFT JOIN employees emp ON emp.id = a.employee_id
            LEFT JOIN clients   c   ON c.id  = a.client_id
            WHERE e.scheduled_at <= NOW()
              AND {PENDING_EVENT_FILTER}
            ORDER BY e.scheduled_at
        """
        return [dict(r) for r in self._fetch_all(sql, ())]

    def get_scheduled_for_queue(self, appointment_id: Optional[int] = None) -> List[dict]:
        """Queued events the scheduler will still send, with who receives them.

        Same population as get_due() (PENDING_EVENT_FILTER, shared on purpose) but WITHOUT the
        `scheduled_at <= NOW()` cut, so it lists what is still to come — read-only, backs the "Oczekujące"
        views. `employee_visit_reminder` goes to the employee, every other event type to the client.
        """
        # visit_status / type_* / already_sent are what SmsService.send() weighs before texting a client for
        # an event (an employee reminder skips all of them), so the queue can say which rows would be refused.
        sql = f"""
            SELECT e.id, e.appointment_id, e.event_type, e.scheduled_at,
                   a.appointment_date, a.start_time,
                   a.status                             AS visit_status,
                   c.first_name || ' ' || c.last_name   AS client_name,
                   c.phone                              AS client_phone,
                   emp.first_name || ' ' || emp.last_name AS employee_name,
                   emp.phone                            AS employee_phone,
                   mt.name                              AS type_name,
                   mt.is_enabled                        AS type_enabled,
                   mt.send_only_if_confirmed            AS type_only_confirmed,
                   EXISTS (SELECT 1 FROM sms_reminders r
                           WHERE r.appointment_id = e.appointment_id AND r.message_type_key = e.event_type
                             AND r.status IN ('pending', 'sent', 'delivered')) AS already_sent
            FROM sms_events e
            JOIN appointments a ON a.id = e.appointment_id
            LEFT JOIN clients   c   ON c.id  = a.client_id
            LEFT JOIN employees emp ON emp.id = a.employee_id
            LEFT JOIN sms_message_types mt ON mt.type_key = e.event_type
            WHERE {PENDING_EVENT_FILTER}
        """
        params: tuple = ()
        if appointment_id is not None:
            sql += " AND e.appointment_id = %s"
            params = (appointment_id,)
        sql += " ORDER BY e.scheduled_at, e.id"
        return [dict(r) for r in self._fetch_all(sql, params)]

    def cancel_type_for_appointment(self, appointment_id: int, event_type: str) -> int:
        """Cancel pending events of a specific type for this appointment."""
        sql = """
            UPDATE sms_events SET status = 'cancelled'
            WHERE appointment_id = %s AND event_type = %s AND status = 'scheduled'
        """
        cursor = self._execute(sql, (appointment_id, event_type))
        return cursor.rowcount

    def mark_sent(self, event_id: int, sms_reminder_id: Optional[int]) -> bool:
        """Mark an event as successfully sent."""
        sql = """
            UPDATE sms_events
            SET status = 'sent', sent_at = NOW(), sms_reminder_id = %s
            WHERE id = %s
        """
        cursor = self._execute(sql, (sms_reminder_id, event_id))
        return cursor.rowcount > 0

    def mark_skipped(self, event_id: int, reason: str) -> bool:
        """Close an event that must not send (e.g. the text already went out).
        Stored as 'cancelled' so it leaves the due-queue without counting as a failure."""
        sql = """
            UPDATE sms_events SET status = 'cancelled', error_message = %s
            WHERE id = %s
        """
        cursor = self._execute(sql, (reason, event_id))
        return cursor.rowcount > 0

    def mark_failed(self, event_id: int, error_message: str) -> bool:
        """Mark an event as failed and increment retry_count."""
        sql = """
            UPDATE sms_events
            SET status = 'failed', error_message = %s,
                retry_count = retry_count + 1
            WHERE id = %s
        """
        cursor = self._execute(sql, (error_message, event_id))
        return cursor.rowcount > 0

    def cancel_pending_for_appointment(self, appointment_id: int) -> int:
        """Cancel all 'scheduled' events for this appointment. Returns affected row count."""
        sql = """
            UPDATE sms_events SET status = 'cancelled'
            WHERE appointment_id = %s AND status = 'scheduled'
        """
        cursor = self._execute(sql, (appointment_id,))
        return cursor.rowcount
