"""Repository for event-triggered SMS scheduling (sms_events table)."""
from datetime import datetime
from typing import List, Optional

from repositories.base_repository import BaseRepository


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
        """Return all events where scheduled_at <= NOW() and status = 'scheduled'."""
        sql = """
            SELECT e.*, a.rating_token, a.client_id,
                   a.appointment_date, a.start_time
            FROM sms_events e
            JOIN appointments a ON a.id = e.appointment_id
            WHERE e.scheduled_at <= NOW()
              AND e.status = 'scheduled'
            ORDER BY e.scheduled_at
        """
        return [dict(r) for r in self._fetch_all(sql, ())]

    def mark_sent(self, event_id: int, sms_reminder_id: Optional[int]) -> bool:
        """Mark an event as successfully sent."""
        sql = """
            UPDATE sms_events
            SET status = 'sent', sent_at = NOW(), sms_reminder_id = %s
            WHERE id = %s
        """
        cursor = self._execute(sql, (sms_reminder_id, event_id))
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
