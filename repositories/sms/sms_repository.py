"""
Repositories for sms_settings, sms_message_types, and sms_reminders.
"""
from typing import Optional, List
from repositories.base_repository import BaseRepository


class SmsSettingsRepository(BaseRepository):
    def __init__(self):
        super().__init__('sms_settings')

    def get_settings(self) -> Optional[dict]:
        row = self._fetch_one("SELECT * FROM sms_settings WHERE id = 1", ())
        return dict(row) if row else None

    def update_settings(self, **fields) -> bool:
        if not fields:
            return False
        set_clauses = ', '.join(f"{k} = %s" for k in fields)
        params = list(fields.values()) + [1]
        query = f"UPDATE sms_settings SET {set_clauses}, updated_at = NOW() WHERE id = %s"
        cursor = self._execute(query, tuple(params))
        return cursor.rowcount > 0


class SmsMessageTypeRepository(BaseRepository):
    def __init__(self):
        super().__init__('sms_message_types')

    def get_all(self) -> List[dict]:
        rows = self._fetch_all(
            "SELECT * FROM sms_message_types ORDER BY sort_order, id", ()
        )
        return [dict(r) for r in rows]

    def get_enabled(self) -> List[dict]:
        rows = self._fetch_all(
            "SELECT * FROM sms_message_types WHERE is_enabled = TRUE ORDER BY sort_order, id", ()
        )
        return [dict(r) for r in rows]

    def get_by_key(self, type_key: str) -> Optional[dict]:
        row = self._fetch_one(
            "SELECT * FROM sms_message_types WHERE type_key = %s", (type_key,)
        )
        return dict(row) if row else None

    def get_by_id(self, type_id: int) -> Optional[dict]:
        row = self._fetch_one(
            "SELECT * FROM sms_message_types WHERE id = %s", (type_id,)
        )
        return dict(row) if row else None

    def update(self, type_id: int, **fields) -> bool:
        if not fields:
            return False
        set_clauses = ', '.join(f"{k} = %s" for k in fields)
        params = list(fields.values()) + [type_id]
        query = f"UPDATE sms_message_types SET {set_clauses}, updated_at = NOW() WHERE id = %s"
        cursor = self._execute(query, tuple(params))
        return cursor.rowcount > 0

    def create_custom(self, name: str, send_hours_before: int,
                      template_text: str, include_confirm_link: bool) -> int:
        count_row = self._fetch_one(
            "SELECT COUNT(*) AS c FROM sms_message_types WHERE is_custom = TRUE", ()
        )
        n = (count_row['c'] if count_row else 0) + 1
        type_key = f"custom_{n:03d}"
        query = """
            INSERT INTO sms_message_types
                (type_key, name, is_enabled, send_hours_before, template_text,
                 include_confirm_link, is_custom, sort_order)
            VALUES (%s, %s, FALSE, %s, %s, %s, TRUE, 99)
        """
        return self._execute_insert(query, (
            type_key, name, send_hours_before,
            template_text, include_confirm_link
        ))

    def delete_custom(self, type_id: int) -> bool:
        cursor = self._execute(
            "DELETE FROM sms_message_types WHERE id = %s AND is_custom = TRUE",
            (type_id,)
        )
        return cursor.rowcount > 0


class SmsReminderRepository(BaseRepository):
    def __init__(self):
        super().__init__('sms_reminders')

    def create(self, appointment_id: int, client_id: int, message_type_id: int,
               message_type_key: str, phone_number: str, message_body: str,
               created_by_user_id: Optional[int], created_by_name: Optional[str]) -> int:
        query = """
            INSERT INTO sms_reminders
                (appointment_id, client_id, message_type_id, message_type_key,
                 phone_number, message_body, created_by_user_id, created_by_name, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
        """
        return self._execute_insert(query, (
            appointment_id, client_id, message_type_id, message_type_key,
            phone_number, message_body, created_by_user_id, created_by_name
        ))

    def update_status(self, reminder_id: int, status: str,
                      twilio_sid: str = None, error_message: str = None) -> bool:
        query = """
            UPDATE sms_reminders
            SET status = %s, twilio_sid = %s, error_message = %s
            WHERE id = %s
        """
        cursor = self._execute(query, (status, twilio_sid, error_message, reminder_id))
        return cursor.rowcount > 0

    def get_for_appointment(self, appointment_id: int) -> List[dict]:
        query = """
            SELECT sr.*, mt.name AS type_name,
                   u.full_name AS sender_name
            FROM sms_reminders sr
            LEFT JOIN sms_message_types mt ON mt.id = sr.message_type_id
            LEFT JOIN users u ON u.id = sr.created_by_user_id
            WHERE sr.appointment_id = %s
            ORDER BY sr.sent_at DESC
        """
        rows = self._fetch_all(query, (appointment_id,))
        return [dict(r) for r in rows]

    def get_sent_type_keys_for_appointment(self, appointment_id: int) -> List[str]:
        rows = self._fetch_all(
            "SELECT DISTINCT message_type_key FROM sms_reminders WHERE appointment_id = %s",
            (appointment_id,)
        )
        return [r['message_type_key'] for r in rows]

    def get_sent_types_batch(self, appointment_ids: List[int]) -> dict:
        if not appointment_ids:
            return {}
        placeholders = ','.join(['%s'] * len(appointment_ids))
        query = f"""
            SELECT
                sr.appointment_id,
                sr.message_type_key,
                sr.status,
                sr.sent_at,
                mt.name AS type_name
            FROM sms_reminders sr
            LEFT JOIN sms_message_types mt ON mt.id = sr.message_type_id
            WHERE sr.appointment_id IN ({placeholders})
            ORDER BY sr.appointment_id, sr.sent_at DESC
        """
        rows = self._fetch_all(query, tuple(appointment_ids))
        result: dict = {}
        for r in rows:
            appt_id = r['appointment_id']
            result.setdefault(appt_id, []).append({
                'type_key': r['message_type_key'],
                'type_name': r['type_name'],
                'status': r['status'],
                'sent_at': str(r['sent_at']) if r['sent_at'] else None,
            })
        return result

    def get_log(self, limit: int = 200, offset: int = 0) -> List[dict]:
        query = """
            SELECT
                sr.*,
                mt.name AS type_name,
                c.first_name || ' ' || c.last_name AS client_name,
                a.appointment_date,
                a.start_time,
                a.confirmation_status AS appt_confirmation_status
            FROM sms_reminders sr
            JOIN clients c ON c.id = sr.client_id
            JOIN appointments a ON a.id = sr.appointment_id
            LEFT JOIN sms_message_types mt ON mt.id = sr.message_type_id
            ORDER BY sr.sent_at DESC
            LIMIT %s OFFSET %s
        """
        rows = self._fetch_all(query, (limit, offset))
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        query = """
            WITH periods AS (
                SELECT
                    sr.id,
                    sr.status,
                    sr.message_type_key,
                    a.confirmation_status,
                    DATE_TRUNC('month', sr.sent_at) AS send_month,
                    DATE_TRUNC('month', CURRENT_DATE) AS current_month,
                    DATE_TRUNC('month', CURRENT_DATE - INTERVAL '2 months') AS three_months_ago
                FROM sms_reminders sr
                JOIN appointments a ON a.id = sr.appointment_id
            )
            SELECT
                COUNT(*) FILTER (WHERE send_month = current_month) AS mtd1_total,
                COUNT(*) FILTER (WHERE send_month = current_month AND status IN ('sent', 'delivered')) AS mtd1_sent,
                COUNT(*) FILTER (WHERE send_month = current_month AND status = 'failed') AS mtd1_failed,
                COUNT(*) FILTER (WHERE send_month = current_month AND message_type_key = 'confirmation_request') AS mtd1_confirm_requests,
                COUNT(*) FILTER (WHERE send_month = current_month AND message_type_key = 'confirmation_request' AND confirmation_status = 'confirmed') AS mtd1_confirmed,
                COUNT(*) FILTER (WHERE send_month = current_month AND message_type_key = 'confirmation_request' AND confirmation_status = 'declined') AS mtd1_declined,
                COUNT(*) FILTER (WHERE send_month >= three_months_ago) AS mtd3_total,
                COUNT(*) FILTER (WHERE send_month >= three_months_ago AND status IN ('sent', 'delivered')) AS mtd3_sent,
                COUNT(*) FILTER (WHERE send_month >= three_months_ago AND status = 'failed') AS mtd3_failed,
                COUNT(*) FILTER (WHERE send_month >= three_months_ago AND message_type_key = 'confirmation_request') AS mtd3_confirm_requests,
                COUNT(*) FILTER (WHERE send_month >= three_months_ago AND message_type_key = 'confirmation_request' AND confirmation_status = 'confirmed') AS mtd3_confirmed,
                COUNT(*) FILTER (WHERE send_month >= three_months_ago AND message_type_key = 'confirmation_request' AND confirmation_status = 'declined') AS mtd3_declined
            FROM periods
        """
        row = self._fetch_one(query, ())
        return dict(row) if row else {}
