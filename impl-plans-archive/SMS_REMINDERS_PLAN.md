# SMS Reminders Plan — MyWay Beauty Salon

**System**: Twilio outbound-only SMS reminders with mobile-first appointment confirmation page.
**Language**: Polish UI labels, code in English.
**Stack**: Flask · PostgreSQL · psycopg2 · Alembic · Twilio REST API · APScheduler.

---

## Architecture Overview

```
┌───────────────────────────────────────────────────────────────────┐
│                     Admin-side (authenticated)                    │
│                                                                   │
│  Settings page → configure N message types, each with own:       │
│    - timing (hours before appointment)                            │
│    - template text                                                │
│    - enabled flag                                                 │
│    Types: [confirmation_request] [reminder_1] [reminder_2]        │
│           [custom_1] [custom_2] ... (unlimited)                   │
│                                                                   │
│  Appointment view → "Wyślij SMS" button (manual per-type)         │
│  Appointment list → SMS column (types sent + confirmation status) │
│                                                                   │
│  POST /api/sms/send                                               │
│       ↓  {appointment_id, message_type_key}                       │
│  SmsService.send(appointment_id, type_key)                        │
│       ↓  generates uuid token if first time, inserts sms_reminders│
│  Twilio REST API → client phone                                   │
│       ↓  confirmation_request type appends confirm URL to text    │
│                                                                   │
│  Settings: GET/POST /settings/sms                                 │
│  SMS log:  GET /settings/sms/log                                  │
│  Stats:    GET /api/sms/stats  (JSON for stat cards)             │
└───────────────────────────────────────────────────────────────────┘
                              ↓
                 Client receives SMS on phone
                 Taps link: /confirm/<uuid-token>
                              ↓
┌───────────────────────────────────────────────────────────────────┐
│                Public side (no authentication)                    │
│                                                                   │
│  GET /confirm/<token> → mobile-first confirmation page            │
│  POST /confirm/<token> → updates appointments.confirmation_status │
│                        → inserts audit_log row                    │
│                        → renders success/already-done page        │
└───────────────────────────────────────────────────────────────────┘
```

---

## Phase 1 — Database Schema

**Milestone**: All new tables and columns exist in PostgreSQL, Alembic migration applied cleanly, seed rows for 3 built-in SMS types present.

### 1.1 New migration file

File: `alembic/versions/<next_id>_add_sms_reminder_system.py`

**Naming convention**: follow existing pattern (e.g. `q2r3s4t5u6v7_add_sms_reminder_system.py`).

```python
"""add sms reminder system

Revision ID: q2r3s4t5u6v7
Revises: p0q1r2s3t4u5
Create Date: 2026-05-18
"""
from alembic import op

revision = 'q2r3s4t5u6v7'
down_revision = 'p0q1r2s3t4u5'  # <-- replace with actual last migration ID
branch_labels = None
depends_on = None


def upgrade():
    # ----------------------------------------------------------------
    # sms_settings — Twilio credentials + global switches
    # Single row (id=1). No timing/template here; those live per-type.
    # ----------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS sms_settings (
            id              SERIAL PRIMARY KEY,
            account_sid     VARCHAR(64),
            auth_token      VARCHAR(64),
            from_number     VARCHAR(20),
            is_active       BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("""
        INSERT INTO sms_settings (id) VALUES (1)
        ON CONFLICT (id) DO NOTHING
    """)

    # ----------------------------------------------------------------
    # sms_message_types — one row per SMS type
    # Built-in types: confirmation_request, reminder_1, reminder_2
    # Admin can add custom types via UI (is_custom = TRUE).
    # ----------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS sms_message_types (
            id                   SERIAL PRIMARY KEY,
            type_key             VARCHAR(50) NOT NULL UNIQUE,
            name                 VARCHAR(120) NOT NULL,
            description          VARCHAR(255),
            is_enabled           BOOLEAN NOT NULL DEFAULT FALSE,
            send_hours_before    INTEGER NOT NULL DEFAULT 24,
                                 -- hours before appointment datetime to auto-send
            template_text        TEXT NOT NULL DEFAULT '',
            include_confirm_link BOOLEAN NOT NULL DEFAULT FALSE,
                                 -- appends {confirm_url} automatically when TRUE
            is_custom            BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order           INTEGER NOT NULL DEFAULT 99,
            created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Seed built-in types. Polish names, sensible defaults.
    op.execute("""
        INSERT INTO sms_message_types
            (type_key, name, description, is_enabled,
             send_hours_before, template_text, include_confirm_link, is_custom, sort_order)
        VALUES
            (
                'confirmation_request',
                'Prośba o potwierdzenie',
                'Wysyłana automatycznie X godzin przed wizytą. Zawiera link do potwierdzenia.',
                FALSE,
                48,
                'Hej {client_name}! Przypominamy o wizycie w {salon_name} dnia {date} o {time}. Czy możesz potwierdzić wizytę? {confirm_url}',
                TRUE,
                FALSE,
                1
            ),
            (
                'reminder_1',
                'Pierwsze przypomnienie',
                'Przypomnienie bez linku potwierdzenia — np. dzień przed wizytą.',
                FALSE,
                24,
                'Przypomnienie: jutro o {time} zapraszamy do {salon_name} na {services}. Do zobaczenia!',
                FALSE,
                FALSE,
                2
            ),
            (
                'reminder_2',
                'Drugie przypomnienie',
                'Krótkie przypomnienie tuż przed wizytą.',
                FALSE,
                2,
                'Hej {client_name}, za {hours_before}h wizyta w {salon_name}. Do zobaczenia o {time}!',
                FALSE,
                FALSE,
                3
            )
        ON CONFLICT (type_key) DO NOTHING
    """)

    # ----------------------------------------------------------------
    # sms_reminders — full log of every SMS send attempt
    # Linked to both the appointment and the message type.
    # ----------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS sms_reminders (
            id                   SERIAL PRIMARY KEY,
            appointment_id       INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
            client_id            INTEGER NOT NULL REFERENCES clients(id),
            message_type_id      INTEGER REFERENCES sms_message_types(id),
            message_type_key     VARCHAR(50) NOT NULL,
                                 -- denormalized — survives type deletion
            phone_number         VARCHAR(20) NOT NULL,
            message_body         TEXT NOT NULL,
            twilio_sid           VARCHAR(64),
            status               VARCHAR(20) NOT NULL DEFAULT 'pending',
                                 -- 'pending' | 'sent' | 'failed' | 'delivered'
            error_message        TEXT,
            sent_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_by_user_id   INTEGER REFERENCES users(id),
            created_by_name      VARCHAR(120)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sms_reminders_appointment_id
            ON sms_reminders(appointment_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sms_reminders_client_id
            ON sms_reminders(client_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sms_reminders_sent_at
            ON sms_reminders(sent_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sms_reminders_type_key
            ON sms_reminders(message_type_key)
    """)

    # ----------------------------------------------------------------
    # appointments — add confirmation columns
    # reminder_sent_at is NOT added; per-type sent state is derived
    # from sms_reminders by joining on appointment_id + message_type_key.
    # ----------------------------------------------------------------
    op.execute("""
        ALTER TABLE appointments
            ADD COLUMN IF NOT EXISTS confirmation_token       UUID UNIQUE,
            ADD COLUMN IF NOT EXISTS confirmation_status      VARCHAR(20) DEFAULT NULL,
                                                              -- NULL | 'confirmed' | 'declined'
            ADD COLUMN IF NOT EXISTS confirmation_updated_at  TIMESTAMP WITH TIME ZONE
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_appointments_confirmation_token
            ON appointments(confirmation_token)
    """)


def downgrade():
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS confirmation_token")
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS confirmation_status")
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS confirmation_updated_at")
    op.execute("DROP TABLE IF EXISTS sms_reminders")
    op.execute("DROP TABLE IF EXISTS sms_message_types")
    op.execute("DROP TABLE IF EXISTS sms_settings")
```

### 1.2 DB schema reference

| Table | Key columns | Notes |
|-------|-------------|-------|
| `sms_settings` | `account_sid`, `auth_token`, `from_number`, `is_active` | Single-row config (`id=1`). Credentials only — no timing here. |
| `sms_message_types` | `type_key`, `name`, `is_enabled`, `send_hours_before`, `template_text`, `include_confirm_link`, `is_custom` | One row per SMS type. 3 built-in + unlimited custom. |
| `sms_reminders` | `appointment_id`, `message_type_key`, `phone_number`, `status`, `twilio_sid` | Full send log. `message_type_key` denormalized for durability. |
| `appointments` | `confirmation_token UUID`, `confirmation_status`, `confirmation_updated_at` | Token = public URL key. Status = client reply. |

**Why `reminder_sent_at` was NOT added to `appointments`**: With multiple SMS types, one timestamp is insufficient. "What was sent" is derived from `sms_reminders` filtered by `appointment_id` — each row represents one sent type.

### 1.3 Template variables

Available in every `sms_message_types.template_text`:

| Variable | Resolves to |
|----------|-------------|
| `{salon_name}` | App name from config |
| `{client_name}` | Client's first name |
| `{date}` | Appointment date, formatted `DD.MM.YYYY` |
| `{time}` | Appointment start time, formatted `HH:MM` |
| `{employee_name}` | Stylist first name |
| `{services}` | Comma-separated service names |
| `{hours_before}` | Hours until appointment (computed at send time) |
| `{confirm_url}` | Full URL to `/confirm/<token>` — only meaningful when `include_confirm_link = TRUE` |

---

## Phase 2 — SMS Service and Repository

**Milestone**: `SmsService` can send any typed SMS to a real phone and log the result. The scheduler can iterate enabled types and send due reminders correctly.

### 2.1 SMS Repository

File: `repositories/sms/__init__.py` (empty)
File: `repositories/sms/sms_repository.py`

```python
"""
Repositories for sms_settings, sms_message_types, and sms_reminders.
"""
from typing import Optional, List
from repositories.base_repository import BaseRepository


class SmsSettingsRepository(BaseRepository):
    def __init__(self):
        super().__init__('sms_settings')

    def get_settings(self) -> Optional[dict]:
        """Return the single credentials row (id=1)."""
        row = self._fetch_one("SELECT * FROM sms_settings WHERE id = 1", ())
        return dict(row) if row else None

    def update_settings(self, **fields) -> bool:
        """Update sms_settings id=1 with provided keyword fields."""
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
        """Return all types ordered by sort_order."""
        rows = self._fetch_all(
            "SELECT * FROM sms_message_types ORDER BY sort_order, id", ()
        )
        return [dict(r) for r in rows]

    def get_enabled(self) -> List[dict]:
        """Return only enabled types — used by scheduler."""
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
        """Create a new user-defined SMS type. Generates unique type_key."""
        # Generate type_key from counter
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
        """Only custom types can be deleted; built-ins are protected."""
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
        """Return list of type_keys already sent (any status) for this appointment."""
        rows = self._fetch_all(
            "SELECT DISTINCT message_type_key FROM sms_reminders WHERE appointment_id = %s",
            (appointment_id,)
        )
        return [r['message_type_key'] for r in rows]

    def get_sent_types_batch(self, appointment_ids: List[int]) -> dict:
        """
        For a list of appointment IDs, return a map:
        {appointment_id: [{'type_key', 'status', 'sent_at'}, ...]}
        Used by the appointments list page to render the SMS column.
        """
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
        """Global paginated SMS log for the settings page."""
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
        """
        Return SMS usage stats for 1-MTD and 3-MTD periods.
        1-MTD  = current calendar month (1st to today)
        3-MTD  = last 3 calendar months (rolling)
        """
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
                -- 1-MTD
                COUNT(*) FILTER (
                    WHERE send_month = current_month
                ) AS mtd1_total,
                COUNT(*) FILTER (
                    WHERE send_month = current_month AND status IN ('sent', 'delivered')
                ) AS mtd1_sent,
                COUNT(*) FILTER (
                    WHERE send_month = current_month AND status = 'failed'
                ) AS mtd1_failed,
                COUNT(*) FILTER (
                    WHERE send_month = current_month
                      AND message_type_key = 'confirmation_request'
                ) AS mtd1_confirm_requests,
                COUNT(*) FILTER (
                    WHERE send_month = current_month
                      AND message_type_key = 'confirmation_request'
                      AND confirmation_status = 'confirmed'
                ) AS mtd1_confirmed,
                COUNT(*) FILTER (
                    WHERE send_month = current_month
                      AND message_type_key = 'confirmation_request'
                      AND confirmation_status = 'declined'
                ) AS mtd1_declined,
                -- 3-MTD
                COUNT(*) FILTER (
                    WHERE send_month >= three_months_ago
                ) AS mtd3_total,
                COUNT(*) FILTER (
                    WHERE send_month >= three_months_ago AND status IN ('sent', 'delivered')
                ) AS mtd3_sent,
                COUNT(*) FILTER (
                    WHERE send_month >= three_months_ago AND status = 'failed'
                ) AS mtd3_failed,
                COUNT(*) FILTER (
                    WHERE send_month >= three_months_ago
                      AND message_type_key = 'confirmation_request'
                ) AS mtd3_confirm_requests,
                COUNT(*) FILTER (
                    WHERE send_month >= three_months_ago
                      AND message_type_key = 'confirmation_request'
                      AND confirmation_status = 'confirmed'
                ) AS mtd3_confirmed,
                COUNT(*) FILTER (
                    WHERE send_month >= three_months_ago
                      AND message_type_key = 'confirmation_request'
                      AND confirmation_status = 'declined'
                ) AS mtd3_declined
            FROM periods
        """
        row = self._fetch_one(query, ())
        return dict(row) if row else {}
```

### 2.2 SMS Service

File: `services/sms_service.py`

```python
"""
Twilio SMS service — outbound only.
Requires: pip install twilio
"""
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple, List

from flask import current_app

from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.audit_repository import AuditRepository
from repositories.clients.client_repository import ClientRepository
from repositories.sms.sms_repository import (
    SmsSettingsRepository, SmsMessageTypeRepository, SmsReminderRepository
)


class SmsError(Exception):
    pass


class SmsService:
    """Wraps Twilio API and manages all SMS reminder workflows."""

    def __init__(self):
        self._settings_repo = SmsSettingsRepository()
        self._type_repo = SmsMessageTypeRepository()
        self._reminder_repo = SmsReminderRepository()
        self._appt_repo = AppointmentRepository()
        self._client_repo = ClientRepository()
        self._audit_repo = AuditRepository()

    # ------------------------------------------------------------------
    # Settings helpers
    # ------------------------------------------------------------------

    def get_settings(self) -> dict:
        return self._settings_repo.get_settings() or {}

    def save_settings(self, **kwargs) -> bool:
        return self._settings_repo.update_settings(**kwargs)

    def get_message_types(self) -> List[dict]:
        return self._type_repo.get_all()

    def save_message_type(self, type_id: int, **fields) -> bool:
        return self._type_repo.update(type_id, **fields)

    def create_custom_type(self, name: str, send_hours_before: int,
                           template_text: str, include_confirm_link: bool) -> int:
        return self._type_repo.create_custom(
            name=name, send_hours_before=send_hours_before,
            template_text=template_text, include_confirm_link=include_confirm_link
        )

    def delete_custom_type(self, type_id: int) -> bool:
        return self._type_repo.delete_custom(type_id)

    def test_connection(self, account_sid: str, auth_token: str,
                        from_number: str, to_number: str) -> Tuple[bool, str]:
        """Send a test SMS to verify Twilio credentials."""
        try:
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            msg = client.messages.create(
                body="Test wiadomości SMS z MyWay Beauty Salon.",
                from_=from_number,
                to=to_number,
            )
            return True, msg.sid
        except Exception as e:
            return False, str(e)

    # ------------------------------------------------------------------
    # Core: send one message type for one appointment
    # ------------------------------------------------------------------

    def send(
        self,
        appointment_id: int,
        message_type_key: str,
        sender_user_id: Optional[int] = None,
        sender_name: Optional[str] = None,
        base_url: str = None,
    ) -> dict:
        """
        Build and send a specific SMS type for appointment_id.

        Returns: {success, reminder_id, twilio_sid, message_body, error}
        Raises SmsError on config problems (no credentials, no phone, etc.).
        """
        settings = self.get_settings()
        if not settings.get('account_sid') or not settings.get('auth_token'):
            raise SmsError("Brak konfiguracji Twilio (account_sid / auth_token)")
        if not settings.get('from_number'):
            raise SmsError("Brak numeru nadawcy SMS")
        if not settings.get('is_active'):
            raise SmsError("Wysyłanie SMS jest wyłączone w ustawieniach")

        msg_type = self._type_repo.get_by_key(message_type_key)
        if not msg_type:
            raise SmsError(f"Nieznany typ SMS: {message_type_key}")

        appt = self._appt_repo.get_by_id(appointment_id)
        if not appt:
            raise SmsError(f"Wizyta {appointment_id} nie istnieje")

        client = self._client_repo.get_by_id(appt['client_id'])
        if not client:
            raise SmsError("Klient nie istnieje")

        phone_raw = (client['phone'] if hasattr(client, '__getitem__')
                     else getattr(client, 'phone', None))
        if not phone_raw:
            raise SmsError("Klient nie ma numeru telefonu")
        phone = self._normalize_phone(phone_raw)

        # Generate confirmation token if first time (shared across all types)
        token = appt.get('confirmation_token')
        if not token:
            token = str(uuid.uuid4())
            self._appt_repo.update_confirmation_token(appointment_id, token)

        if base_url is None:
            base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        confirm_url = f"{base_url}/confirm/{token}"

        # Build message body
        message_body = self._build_message(appt, client, msg_type, confirm_url)

        # Persist reminder row (status=pending)
        reminder_id = self._reminder_repo.create(
            appointment_id=appointment_id,
            client_id=appt['client_id'],
            message_type_id=msg_type['id'],
            message_type_key=message_type_key,
            phone_number=phone,
            message_body=message_body,
            created_by_user_id=sender_user_id,
            created_by_name=sender_name,
        )

        # Send via Twilio
        try:
            from twilio.rest import Client as TwilioClient
            twilio = TwilioClient(settings['account_sid'], settings['auth_token'])
            msg = twilio.messages.create(
                body=message_body,
                from_=settings['from_number'],
                to=phone,
            )
            twilio_sid = msg.sid
            self._reminder_repo.update_status(reminder_id, 'sent', twilio_sid=twilio_sid)

            appt_date_fmt = self._fmt_date(str(appt['appointment_date']))
            start_time = str(appt.get('start_time', ''))[:5]
            self._audit_repo.log_event(
                entity_type='appointment', action='SMS_SENT',
                entity_id=appointment_id,
                entity_label=f"{appt_date_fmt} {start_time}",
                field_name='sms_type',
                new_value=f"{msg_type['name']} → {phone} (SID: {twilio_sid})",
                user_id=sender_user_id, user_name=sender_name,
            )
            return {'success': True, 'reminder_id': reminder_id,
                    'twilio_sid': twilio_sid, 'message_body': message_body}

        except Exception as e:
            err = str(e)
            self._reminder_repo.update_status(reminder_id, 'failed', error_message=err)
            logging.error("SMS send failed appt=%s type=%s: %s",
                          appointment_id, message_type_key, err)
            return {'success': False, 'reminder_id': reminder_id, 'error': err}

    # ------------------------------------------------------------------
    # Auto-send: called by APScheduler every 15 minutes
    # ------------------------------------------------------------------

    def send_due_reminders(self, base_url: str) -> dict:
        """
        For each enabled SMS type, find appointments in its send window
        that have not yet received that type, and send them.
        Called by scheduler every 15 minutes.
        Returns {sent, skipped, failed}.
        """
        enabled_types = self._type_repo.get_enabled()
        sent = skipped = failed = 0

        for msg_type in enabled_types:
            hours_before = msg_type['send_hours_before']
            due_rows = self._appt_repo.get_appointments_due_for_type(
                hours_before=hours_before,
                message_type_key=msg_type['type_key'],
            )
            for row in due_rows:
                try:
                    result = self.send(
                        appointment_id=row['id'],
                        message_type_key=msg_type['type_key'],
                        sender_user_id=None,
                        sender_name='System (auto)',
                        base_url=base_url,
                    )
                    if result['success']:
                        sent += 1
                    else:
                        failed += 1
                except SmsError:
                    skipped += 1
                except Exception:
                    logging.exception("Auto-remind failed appt=%s type=%s",
                                      row['id'], msg_type['type_key'])
                    failed += 1

        return {'sent': sent, 'skipped': skipped, 'failed': failed}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_phone(self, phone: str) -> str:
        """Normalize Polish mobile number to E.164 (+48XXXXXXXXX)."""
        phone = re.sub(r'[\s\-\(\)]', '', phone.strip())
        if phone.startswith('+'):
            return phone
        if phone.startswith('48') and len(phone) == 11:
            return '+' + phone
        if phone.startswith('0') and len(phone) == 10:
            return '+48' + phone[1:]
        if len(phone) == 9:
            return '+48' + phone
        return phone

    def _fmt_date(self, date_str: str) -> str:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
        except ValueError:
            return date_str

    def _build_message(self, appt: dict, client, msg_type: dict, confirm_url: str) -> str:
        from repositories.appointments.appointment_service_repository import AppointmentServiceRepository
        services_rows = AppointmentServiceRepository().get_for_appointment(appt['id'])
        service_names = ', '.join(s['service_name'] for s in services_rows) if services_rows else ''

        appt_date_fmt = self._fmt_date(str(appt['appointment_date']))
        start_time = str(appt.get('start_time', ''))[:5]
        salon_name = current_app.config.get('APP_NAME', 'MyWay Beauty Salon')
        client_first = (client['first_name'] if hasattr(client, '__getitem__')
                        else getattr(client, 'first_name', ''))

        # Compute hours_before at send time
        try:
            appt_dt = datetime.strptime(
                f"{appt['appointment_date']} {start_time}", '%Y-%m-%d %H:%M'
            )
            delta = appt_dt - datetime.now()
            hours_before = max(0, int(delta.total_seconds() / 3600))
        except Exception:
            hours_before = msg_type['send_hours_before']

        template = msg_type['template_text']
        # Always replace all variables; if include_confirm_link is False,
        # the template simply won't contain {confirm_url}.
        body = (template
            .replace('{salon_name}', salon_name)
            .replace('{client_name}', client_first)
            .replace('{date}', appt_date_fmt)
            .replace('{time}', start_time)
            .replace('{services}', service_names)
            .replace('{hours_before}', str(hours_before))
            .replace('{confirm_url}', confirm_url if msg_type['include_confirm_link'] else '')
        )
        return body.strip()
```

### 2.3 AppointmentRepository additions

Add the following methods to `repositories/appointments/appointment_repository.py`:

```python
def update_confirmation_token(self, appointment_id: int, token: str) -> bool:
    cursor = self._execute(
        "UPDATE appointments SET confirmation_token = %s WHERE id = %s",
        (token, appointment_id)
    )
    return cursor.rowcount > 0

def get_by_confirmation_token(self, token: str) -> Optional[dict]:
    row = self._fetch_one(
        """SELECT a.*, e.first_name || ' ' || e.last_name AS employee_name
           FROM appointments a
           LEFT JOIN employees e ON e.id = a.employee_id
           WHERE a.confirmation_token = %s AND a.is_deleted IS NOT TRUE""",
        (token,)
    )
    return dict(row) if row else None

def update_confirmation_status(self, appointment_id: int, status: str) -> bool:
    """status: 'confirmed' | 'declined'"""
    cursor = self._execute(
        """UPDATE appointments
           SET confirmation_status = %s, confirmation_updated_at = NOW()
           WHERE id = %s""",
        (status, appointment_id)
    )
    return cursor.rowcount > 0

def get_appointments_due_for_type(self, hours_before: int,
                                   message_type_key: str) -> List[dict]:
    """
    Return appointments that need a specific SMS type sent now.
    Conditions:
    - status IN ('scheduled', 'pending', 'confirmed')  [active, future appointments]
    - not soft-deleted
    - client has a phone number
    - appointment datetime falls in the ±15-min window around hours_before from now
    - this message_type_key has NOT already been sent for this appointment
    """
    query = """
        SELECT a.*, c.phone, c.first_name AS client_first_name
        FROM appointments a
        JOIN clients c ON c.id = a.client_id
        WHERE a.status IN ('scheduled', 'pending', 'confirmed')
          AND a.is_deleted IS NOT TRUE
          AND c.phone IS NOT NULL AND c.phone != ''
          AND (a.appointment_date::timestamp + a.start_time::interval)
              BETWEEN NOW() + INTERVAL '1 minute' * (%s * 60 - 15)
                  AND NOW() + INTERVAL '1 minute' * (%s * 60 + 15)
          AND a.id NOT IN (
              SELECT DISTINCT appointment_id
              FROM sms_reminders
              WHERE message_type_key = %s
                AND status IN ('sent', 'delivered', 'pending')
          )
    """
    rows = self._fetch_all(query, (hours_before, hours_before, message_type_key))
    return [dict(r) for r in rows]
```

---

## Phase 3 — SMS Settings Page

**Milestone**: Admin can configure Twilio credentials, manage all SMS message types (edit, enable/disable, add custom, delete custom), test connection, and view the SMS send log.

### 3.1 Routes

File: `routes/sms_routes.py` (new Blueprint)

```python
"""
SMS settings and reminder routes — admin only.
"""
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from config.auth_config import module_permission_required
from services.sms_service import SmsService, SmsError
from repositories.sms.sms_repository import SmsReminderRepository, SmsMessageTypeRepository

sms_bp = Blueprint('sms', __name__)


@sms_bp.route('/settings/sms', methods=['GET'])
@login_required
@module_permission_required('settings')
def sms_settings():
    svc = SmsService()
    settings = svc.get_settings()
    message_types = svc.get_message_types()
    from repositories.sms.sms_repository import SmsReminderRepository
    stats = SmsReminderRepository().get_stats()
    return render_template('settings/sms.html',
                           settings=settings,
                           message_types=message_types,
                           stats=stats)


@sms_bp.route('/settings/sms/credentials', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_credentials_save():
    """Save Twilio credentials and global on/off switch."""
    svc = SmsService()
    data = request.form
    svc.save_settings(
        account_sid=data.get('account_sid', '').strip(),
        auth_token=data.get('auth_token', '').strip(),
        from_number=data.get('from_number', '').strip(),
        is_active=('is_active' in data),
    )
    flash('Dane dostępowe Twilio zapisane', 'success')
    return redirect(url_for('sms.sms_settings'))


@sms_bp.route('/settings/sms/message-type/<int:type_id>', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_message_type_save(type_id):
    """Save one message type's config (timing, template, enabled flag)."""
    svc = SmsService()
    data = request.form
    svc.save_message_type(
        type_id,
        is_enabled=('is_enabled' in data),
        send_hours_before=int(data.get('send_hours_before', 24)),
        template_text=data.get('template_text', '').strip(),
        include_confirm_link=('include_confirm_link' in data),
        name=data.get('name', '').strip(),
    )
    flash('Typ wiadomości SMS zaktualizowany', 'success')
    return redirect(url_for('sms.sms_settings'))


@sms_bp.route('/settings/sms/message-type/create', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_message_type_create():
    """Create a new custom SMS message type."""
    data = request.form
    name = data.get('name', '').strip()
    if not name:
        flash('Nazwa jest wymagana', 'error')
        return redirect(url_for('sms.sms_settings'))
    svc = SmsService()
    svc.create_custom_type(
        name=name,
        send_hours_before=int(data.get('send_hours_before', 24)),
        template_text=data.get('template_text', '').strip(),
        include_confirm_link=('include_confirm_link' in data),
    )
    flash('Nowy typ wiadomości SMS dodany', 'success')
    return redirect(url_for('sms.sms_settings'))


@sms_bp.route('/settings/sms/message-type/<int:type_id>/delete', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_message_type_delete(type_id):
    """Delete a custom SMS type (built-ins are protected)."""
    svc = SmsService()
    ok = svc.delete_custom_type(type_id)
    if ok:
        flash('Typ wiadomości usunięty', 'success')
    else:
        flash('Nie można usunąć wbudowanego typu wiadomości', 'error')
    return redirect(url_for('sms.sms_settings'))


@sms_bp.route('/settings/sms/test', methods=['POST'])
@login_required
@module_permission_required('settings')
def sms_test():
    """Send a test SMS using credentials from the form (not DB)."""
    data = request.get_json()
    svc = SmsService()
    ok, result = svc.test_connection(
        account_sid=data.get('account_sid', ''),
        auth_token=data.get('auth_token', ''),
        from_number=data.get('from_number', ''),
        to_number=data.get('to_number', ''),
    )
    return jsonify({'success': ok, 'result': result})


@sms_bp.route('/settings/sms/log', methods=['GET'])
@login_required
@module_permission_required('settings')
def sms_log():
    """Paginated SMS send history."""
    repo = SmsReminderRepository()
    offset = request.args.get('offset', 0, type=int)
    rows = repo.get_log(limit=100, offset=offset)
    return render_template('settings/sms_log.html', rows=rows, offset=offset)


@sms_bp.route('/api/sms/stats', methods=['GET'])
@login_required
@module_permission_required('settings')
def sms_stats():
    """Return 1-MTD and 3-MTD stats as JSON for the stat cards."""
    stats = SmsReminderRepository().get_stats()
    return jsonify({'success': True, 'stats': stats})


# -----------------------------------------------------------------------
# Appointment-level SMS endpoints (used from appointment views/list)
# -----------------------------------------------------------------------

@sms_bp.route('/api/sms/send', methods=['POST'])
@login_required
@module_permission_required('appointments')
def send_sms():
    """
    Manual trigger: send a specific SMS type for one appointment.
    Body: {"appointment_id": 123, "message_type_key": "confirmation_request"}
    Response: {"success": true/false, "message": "...", "reminder_id": 456}
    """
    data = request.get_json()
    appointment_id = data.get('appointment_id')
    message_type_key = data.get('message_type_key')
    if not appointment_id or not message_type_key:
        return jsonify({'success': False,
                        'message': 'Wymagane: appointment_id i message_type_key'}), 400

    base_url = request.host_url.rstrip('/')
    svc = SmsService()
    try:
        result = svc.send(
            appointment_id=int(appointment_id),
            message_type_key=message_type_key,
            sender_user_id=current_user.id,
            sender_name=current_user.full_name,
            base_url=base_url,
        )
        if result['success']:
            return jsonify({'success': True,
                            'message': 'SMS wysłany',
                            'reminder_id': result['reminder_id']})
        return jsonify({'success': False,
                        'message': result.get('error', 'Błąd wysyłki'),
                        'reminder_id': result.get('reminder_id')}), 500
    except SmsError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception:
        logging.exception("Unexpected error in send_sms")
        return jsonify({'success': False, 'message': 'Błąd serwera'}), 500


@sms_bp.route('/api/sms/bulk-send', methods=['POST'])
@login_required
@module_permission_required('appointments')
def bulk_send():
    """
    Send a specific SMS type to multiple appointments at once.
    Body: {"appointment_ids": [1, 2, 3], "message_type_key": "reminder_1"}
    Returns per-appointment status list.
    """
    data = request.get_json()
    ids = data.get('appointment_ids', [])
    message_type_key = data.get('message_type_key')
    if not ids or not message_type_key:
        return jsonify({'success': False,
                        'message': 'Wymagane: appointment_ids i message_type_key'}), 400

    base_url = request.host_url.rstrip('/')
    svc = SmsService()
    results = []
    for appt_id in ids:
        try:
            res = svc.send(
                appointment_id=int(appt_id),
                message_type_key=message_type_key,
                sender_user_id=current_user.id,
                sender_name=current_user.full_name,
                base_url=base_url,
            )
            results.append({'appointment_id': appt_id, **res})
        except SmsError as e:
            results.append({'appointment_id': appt_id, 'success': False, 'error': str(e)})

    sent = sum(1 for r in results if r.get('success'))
    return jsonify({'success': True, 'sent': sent, 'total': len(ids), 'details': results})


@sms_bp.route('/api/sms/appointment/<int:appointment_id>/log', methods=['GET'])
@login_required
@module_permission_required('appointments')
def appointment_sms_log(appointment_id):
    """Per-appointment SMS history (used in the appointment view panel)."""
    repo = SmsReminderRepository()
    rows = repo.get_for_appointment(appointment_id)
    for r in rows:
        if r.get('sent_at'):
            r['sent_at'] = str(r['sent_at'])
    return jsonify({'success': True, 'reminders': rows})
```

### 3.2 Register blueprint in app factory

In `app.py`:

```python
from routes.sms_routes import sms_bp
app.register_blueprint(sms_bp)
```

### 3.3 Settings template: `templates/settings/sms.html`

Extends `base.html`. Mirrors `templates/settings/email.html` CSS classes: `.refined-page`, `.page-header`, `.form-card`, `.form-field`, `.form-label`.

**Page structure (top to bottom):**

---

#### Section A — Statistics cards (rendered from `stats` context variable)

Two stat groups side by side (2-column grid on desktop, stacked on mobile).

**Group 1: Bieżący miesiąc (MTD)**

| Card | Value | Formula |
|------|-------|---------|
| Wysłane SMS | `stats.mtd1_sent` | status IN (sent, delivered) |
| Nieudane | `stats.mtd1_failed` | status = failed |
| Prośby o potwierdzenie | `stats.mtd1_confirm_requests` | type_key = confirmation_request |
| Potwierdzenia | `stats.mtd1_confirmed` + `(X%)` | confirmed / confirm_requests × 100 |
| Odmowy | `stats.mtd1_declined` + `(X%)` | declined / confirm_requests × 100 |

**Group 2: Ostatnie 3 miesiące (3-MTD)**

Same 5 cards using `mtd3_*` values.

Visual: small numbered cards with muted label above + bold number + optional trend arrow (no JS calculation needed — static display).

**Full stat card HTML pattern** (repeat per metric):
```html
<div class="stat-card">
    <p class="stat-label">Wysłane SMS</p>
    <p class="stat-value">{{ stats.mtd1_sent or 0 }}</p>
</div>
```

CSS for stat grid:
```css
.stats-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.75rem; margin-bottom: 1.5rem; }
.stat-card { background: white; border: 1px solid var(--color-border); border-radius: 2px; padding: 1rem; }
.stat-label { font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-ink-muted); margin-bottom: 0.375rem; }
.stat-value { font-size: 1.5rem; font-weight: 600; color: var(--color-ink); line-height: 1; }
.stat-sub { font-size: 0.75rem; color: var(--color-ink-muted); margin-top: 0.25rem; }
@media (max-width: 768px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
```

Period tabs above the cards:
```html
<div class="period-tabs">
    <button class="period-tab active" data-period="mtd1">Bieżący miesiąc</button>
    <button class="period-tab" data-period="mtd3">Ostatnie 3 miesiące</button>
</div>
```
JS toggles `data-period` visibility — just show/hide the relevant card group.

---

#### Section B — Dane dostępowe Twilio (form POSTs to `/settings/sms/credentials`)

Card with:
- `account_sid` text input, placeholder `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- `auth_token` password input with eye-toggle button
- `from_number` text input, placeholder `+48XXXXXXXXX`, hint: "Numer Twilio lub alfanumeryczny nadawca SMS"
- `is_active` toggle checkbox — "Włącz wysyłanie SMS"
- Save button

---

#### Section C — Test połączenia (collapsible details element)

```html
<details class="form-card">
    <summary>Test połączenia Twilio</summary>
    <!-- input: to_number -->
    <!-- button: Wyślij test (AJAX POST /settings/sms/test passing current form values) -->
    <!-- inline result badge -->
</details>
```

JS reads `account_sid`, `auth_token`, `from_number` from the form above (before saving), plus the test `to_number` field, sends them to `/settings/sms/test`, displays result inline.

---

#### Section D — Typy wiadomości SMS

One expandable card per message type, rendered via Jinja2 loop over `message_types`:

```html
{% for mt in message_types %}
<details class="form-card message-type-card {% if mt.is_enabled %}type-enabled{% endif %}"
         id="type-{{ mt.id }}">
    <summary class="type-summary">
        <span class="type-name">{{ mt.name }}</span>
        {% if mt.is_enabled %}
            <span class="badge-pill badge-green">Aktywny</span>
        {% else %}
            <span class="badge-pill badge-gray">Nieaktywny</span>
        {% endif %}
        <span class="type-timing">
            {% if mt.is_enabled %}
                {{ mt.send_hours_before }}h przed wizytą
            {% endif %}
        </span>
    </summary>

    <form method="POST" action="/settings/sms/message-type/{{ mt.id }}">
        <div class="form-field">
            <label class="form-label">Nazwa</label>
            <input type="text" name="name" value="{{ mt.name }}"
                   {% if not mt.is_custom %}readonly{% endif %}>
            {# Built-in names are read-only; only custom types allow renaming #}
        </div>

        <div class="form-field">
            <label class="form-label">Wyślij X godzin przed wizytą</label>
            <input type="number" name="send_hours_before"
                   value="{{ mt.send_hours_before }}" min="1" max="168">
            <p class="form-hint">Zakres: 1h – 168h (7 dni)</p>
        </div>

        <div class="form-field">
            <label class="form-label">Treść wiadomości</label>
            <textarea name="template_text" rows="4"
                      class="sms-template"
                      data-char-counter="true">{{ mt.template_text }}</textarea>
            <p class="form-hint char-counter">0 / 160 znaków</p>
        </div>

        <div class="form-field form-field--inline">
            <label class="form-label">
                <input type="checkbox" name="include_confirm_link"
                       {% if mt.include_confirm_link %}checked{% endif %}>
                Dołącz link potwierdzenia ({confirm_url})
            </label>
        </div>

        <div class="form-field form-field--inline">
            <label class="form-label">
                <input type="checkbox" name="is_enabled"
                       {% if mt.is_enabled %}checked{% endif %}>
                Włącz automatyczne wysyłanie
            </label>
        </div>

        <div class="type-actions">
            <button type="submit" class="btn-primary btn-sm">Zapisz</button>
            {% if mt.is_custom %}
            <form method="POST"
                  action="/settings/sms/message-type/{{ mt.id }}/delete"
                  style="display:inline"
                  onsubmit="return confirm('Usunąć ten typ wiadomości?')">
                <button type="submit" class="btn-danger btn-sm">Usuń</button>
            </form>
            {% endif %}
        </div>
    </form>
</details>
{% endfor %}
```

Below the loop — "Dodaj własny typ" collapsible form:

```html
<details class="form-card" id="add-custom-type">
    <summary>+ Dodaj własny typ wiadomości</summary>
    <form method="POST" action="/settings/sms/message-type/create">
        <!-- name, send_hours_before, template_text, include_confirm_link -->
        <button type="submit" class="btn-primary">Dodaj typ</button>
    </form>
</details>
```

**Variable reference panel** (shared, shown below all type cards):

```html
<div class="variable-reference">
    <p class="var-ref-title">Dostępne zmienne w treści wiadomości:</p>
    <code>{salon_name}</code> <code>{client_name}</code> <code>{date}</code>
    <code>{time}</code> <code>{employee_name}</code> <code>{services}</code>
    <code>{hours_before}</code> <code>{confirm_url}</code>
</div>
```

---

#### Section E — Footer links

- "Historia wysyłek SMS →" → `/settings/sms/log`

---

### 3.4 SMS Log template: `templates/settings/sms_log.html`

Table columns: Data wysyłki · Typ SMS · Klient · Telefon · Wizyta · Status · Sid Twilio · Wysłał · Potwierdzenie klienta.

Status badges:
- `pending` → gray pill "Oczekuje"
- `sent` → green pill "Wysłany"
- `delivered` → teal pill "Dostarczony"
- `failed` → red pill "Błąd" (show error_message in tooltip)

Confirmation column: shows the `appt_confirmation_status` from the joined appointment (`confirmed` → ✓ green, `declined` → ✗ red, NULL → dash).

Pagination: prev/next links using `?offset=` query param, 100 rows per page.

---

## Phase 4 — Appointment View Integration

**Milestone**: "Wyślij SMS" dropdown per-type visible on appointment view; confirmation status badge visible; per-appointment SMS log shown.

### 4.1 Appointment view page `templates/appointments/view.html`

Add to the appointment action bar (top-right button area):

```html
<!-- SMS Send Dropdown (only if SMS is active) -->
{% if settings_sms_active %}
<div class="dropdown" id="sms-dropdown">
    <button class="btn-secondary dropdown-toggle" type="button">
        📱 Wyślij SMS ▾
    </button>
    <ul class="dropdown-menu">
        {% for mt in sms_message_types %}
        <li>
            <button type="button"
                    class="dropdown-item"
                    onclick="sendSms({{ appointment.id }}, '{{ mt.type_key }}', '{{ mt.name }}')">
                {{ mt.name }}
                {% if mt.type_key in sms_sent_type_keys %}
                    <span class="badge-pill badge-gray" title="Wysłano już ten typ">Wysłano</span>
                {% endif %}
            </button>
        </li>
        {% endfor %}
    </ul>
</div>
{% endif %}

<!-- Confirmation status badge -->
{% if appointment.confirmation_status == 'confirmed' %}
    <span class="badge-pill badge-green">✓ Potwierdzona przez klienta</span>
{% elif appointment.confirmation_status == 'declined' %}
    <span class="badge-pill badge-red">✕ Odrzucona przez klienta</span>
{% elif sms_sent_type_keys %}
    <span class="badge-pill badge-gray">Oczekuje na odpowiedź klienta</span>
{% endif %}
```

**JS**:

```javascript
async function sendSms(appointmentId, typeKey, typeName) {
    if (!confirm(`Wysłać SMS "${typeName}" do klienta?`)) return;
    try {
        const resp = await fetch('/api/sms/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({appointment_id: appointmentId, message_type_key: typeKey})
        });
        const data = await resp.json();
        if (data.success) {
            showToast(`SMS "${typeName}" wysłany`, 'success');
        } else {
            showToast('Błąd: ' + data.message, 'error');
        }
    } catch (e) {
        showToast('Błąd połączenia', 'error');
    }
}
```

### 4.2 Pass SMS context to appointment view route

In `routes/main_routes.py`, on the appointment view route:

```python
@main_bp.route('/appointments/<int:appointment_id>')
@login_required
@module_permission_required('appointments')
def view_appointment(appointment_id):
    # ... existing logic to fetch appt ...
    from repositories.sms.sms_repository import (
        SmsSettingsRepository, SmsMessageTypeRepository, SmsReminderRepository
    )
    sms_settings = SmsSettingsRepository().get_settings() or {}
    sms_types = SmsMessageTypeRepository().get_all()
    sms_sent_keys = SmsReminderRepository().get_sent_type_keys_for_appointment(appointment_id)
    return render_template(
        'appointments/view.html',
        appointment=appt,
        settings_sms_active=sms_settings.get('is_active', False),
        sms_message_types=sms_types,
        sms_sent_type_keys=sms_sent_keys,
        ...
    )
```

### 4.3 Per-appointment SMS log section

Add collapsible section below audit trail in `templates/appointments/view.html`:

```html
<details id="sms-log-panel">
    <summary class="section-header">
        Historia SMS
        <span class="badge-count" id="sms-count"></span>
    </summary>
    <div id="sms-log-content">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Data</th><th>Typ</th><th>Status</th>
                    <th>Numer</th><th>Treść</th><th>Twilio SID</th><th>Wysłał</th>
                </tr>
            </thead>
            <tbody id="sms-log-tbody">
                <tr><td colspan="7" class="loading">Ładowanie...</td></tr>
            </tbody>
        </table>
    </div>
</details>
<script>
document.getElementById('sms-log-panel').addEventListener('toggle', async function() {
    if (!this.open) return;
    const resp = await fetch('/api/sms/appointment/{{ appointment.id }}/log');
    const data = await resp.json();
    const tbody = document.getElementById('sms-log-tbody');
    if (!data.reminders.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty">Brak wysyłek SMS</td></tr>';
        return;
    }
    document.getElementById('sms-count').textContent = data.reminders.length;
    tbody.innerHTML = data.reminders.map(r => `
        <tr>
            <td>${r.sent_at?.slice(0,16) ?? '—'}</td>
            <td>${r.type_name ?? r.message_type_key}</td>
            <td><span class="badge-pill badge-${statusColor(r.status)}">${r.status}</span></td>
            <td>${r.phone_number}</td>
            <td title="${r.message_body}">${r.message_body?.slice(0,60)}${r.message_body?.length > 60 ? '…' : ''}</td>
            <td class="mono">${r.twilio_sid ?? '—'}</td>
            <td>${r.sender_name ?? r.created_by_name ?? 'System'}</td>
        </tr>
    `).join('');
});
function statusColor(s) {
    return {sent:'green', delivered:'teal', failed:'red', pending:'gray'}[s] ?? 'gray';
}
</script>
```

---

## Phase 5 — Appointments List: SMS Status Column

**Milestone**: The appointments list table has a new "SMS" column (positioned after the "Status" column) displaying, for each appointment: which SMS types have been sent, which are still pending auto-send, and the client's confirmation reply.

### 5.1 Data loading for the list view

The list route (`/appointments` page or API feeding the table) must batch-load SMS state for all visible appointments. This avoids N+1 queries.

In `routes/main_routes.py` (or whatever route renders the appointments list template):

```python
@main_bp.route('/appointments')
@login_required
@module_permission_required('appointments')
def appointments_list():
    # Existing: fetch appointments list
    # ...

    # New: batch-load SMS status for visible appointments
    from repositories.sms.sms_repository import (
        SmsSettingsRepository, SmsMessageTypeRepository, SmsReminderRepository
    )
    sms_active = (SmsSettingsRepository().get_settings() or {}).get('is_active', False)
    all_types = SmsMessageTypeRepository().get_all() if sms_active else []
    enabled_types = [t for t in all_types if t['is_enabled']]

    appt_ids = [a['id'] for a in appointments]  # existing appointments list variable
    sms_sent_map = SmsReminderRepository().get_sent_types_batch(appt_ids) if appt_ids else {}

    return render_template(
        'appointments/list.html',
        appointments=appointments,
        sms_active=sms_active,
        sms_enabled_types=enabled_types,
        sms_sent_map=sms_sent_map,
        ...
    )
```

If the list is loaded via AJAX (JS fetching `/api/appointments`), add `sms_sent_map` to the API response JSON:

```python
# In appointment_routes.py get_appointments():
from repositories.sms.sms_repository import SmsReminderRepository, SmsSettingsRepository, SmsMessageTypeRepository
sms_active = (SmsSettingsRepository().get_settings() or {}).get('is_active', False)
if sms_active:
    appt_ids = [a['id'] for a in appointments]
    sms_sent_map = SmsReminderRepository().get_sent_types_batch(appt_ids)
    all_sms_types = SmsMessageTypeRepository().get_all()
    return jsonify({
        'success': True, 'appointments': appointments,
        'sms_sent_map': sms_sent_map,
        'sms_types': all_sms_types,
        'count': len(appointments)
    })
```

### 5.2 SMS column in the table: `templates/appointments/list.html`

Add one `<th>` after the Status column:

```html
<th class="col-sms">SMS</th>
```

In the table body row (`<tr>` per appointment), add the corresponding `<td>`:

```html
<td class="col-sms">
    {% if sms_active %}
        {% set sent_entries = sms_sent_map.get(appt.id, []) %}
        {% set sent_keys = sent_entries | map(attribute='type_key') | list %}

        {# --- Confirmation response status (most prominent) --- #}
        {% if appt.confirmation_status == 'confirmed' %}
            <span class="sms-tag sms-tag--confirmed" title="Klient potwierdził wizytę">
                ✓ Potw.
            </span>
        {% elif appt.confirmation_status == 'declined' %}
            <span class="sms-tag sms-tag--declined" title="Klient odmówił">
                ✕ Odmowa
            </span>
        {% endif %}

        {# --- SMS types already sent --- #}
        {% for entry in sent_entries %}
            {% if loop.first or entry.type_key != loop.previtem.type_key %}
                <span class="sms-tag sms-tag--{{ 'ok' if entry.status in ('sent','delivered') else 'fail' }}"
                      title="{{ entry.type_name }}: {{ entry.status }} ({{ entry.sent_at[:16] if entry.sent_at else '' }})">
                    {{ entry.type_name | truncate(8, True, '') }}
                </span>
            {% endif %}
        {% endfor %}

        {# --- Types still to be sent (enabled but not yet sent) --- #}
        {% for mt in sms_enabled_types %}
            {% if mt.type_key not in sent_keys %}
                <span class="sms-tag sms-tag--pending"
                      title="{{ mt.name }}: do wysyłki {{ mt.send_hours_before }}h przed wizytą">
                    {{ mt.name | truncate(8, True, '') }}…
                </span>
            {% endif %}
        {% endfor %}

        {# --- No SMS activity at all --- #}
        {% if not sent_entries and not sms_enabled_types %}
            <span class="sms-tag sms-tag--none" title="Brak konfiguracji SMS">—</span>
        {% endif %}
    {% endif %}
</td>
```

**CSS for the SMS column tags:**

```css
.col-sms { width: 140px; white-space: nowrap; }
.sms-tag {
    display: inline-block;
    padding: 0.125rem 0.375rem;
    border-radius: 2px;
    font-size: 0.625rem;
    font-weight: 500;
    letter-spacing: 0.02em;
    margin-right: 2px;
    margin-bottom: 2px;
    cursor: default;
}
.sms-tag--confirmed  { background: #dcfce7; color: #166534; }   /* green */
.sms-tag--declined   { background: #fee2e2; color: #991b1b; }   /* red */
.sms-tag--ok         { background: #dbeafe; color: #1e40af; }   /* blue: sent */
.sms-tag--fail       { background: #fee2e2; color: #991b1b; }   /* red: failed */
.sms-tag--pending    { background: #f3f4f6; color: #6b7280; border: 1px dashed #d1d5db; } /* gray dashed: not sent yet */
.sms-tag--none       { color: #9ca3af; }
```

**Visual guide for the column:**

| Scenario | What shows in the SMS cell |
|----------|---------------------------|
| No SMS sent, no enabled types | `—` |
| Confirmation request enabled, not sent yet | `Prośba…` (gray dashed) |
| Confirmation request sent, no client reply | `Prośba o po…` (blue) |
| Client confirmed | `✓ Potw.` (green) + sent type tags |
| Client declined | `✕ Odmowa` (red) + sent type tags |
| Reminder 1 sent, reminder 2 pending | `Pierwsze p…` (blue) + `Drugie prz…` (gray dashed) |
| SMS send failed | `Prośba o po…` (red) |

### 5.3 If the list loads via JS (AJAX)

If `templates/appointments/list.html` renders rows dynamically from JS (fetched JSON), move the SMS column rendering to JavaScript:

```javascript
function renderSmsCell(apptId, smsMap, smsTypes, confirmStatus) {
    const sent = smsMap[apptId] || [];
    const sentKeys = new Set(sent.map(s => s.type_key));
    const tags = [];

    if (confirmStatus === 'confirmed')
        tags.push(`<span class="sms-tag sms-tag--confirmed" title="Klient potwierdził">✓ Potw.</span>`);
    else if (confirmStatus === 'declined')
        tags.push(`<span class="sms-tag sms-tag--declined" title="Klient odmówił">✕ Odmowa</span>`);

    // Deduplicate by type_key (show last status per type)
    const seenKeys = new Set();
    for (const entry of sent) {
        if (seenKeys.has(entry.type_key)) continue;
        seenKeys.add(entry.type_key);
        const cls = ['sent','delivered'].includes(entry.status) ? 'ok' : 'fail';
        const shortName = (entry.type_name || entry.type_key).slice(0, 8);
        tags.push(`<span class="sms-tag sms-tag--${cls}" title="${entry.type_name}: ${entry.status}">${shortName}</span>`);
    }

    // Pending (enabled, not sent)
    for (const mt of smsTypes) {
        if (mt.is_enabled && !sentKeys.has(mt.type_key)) {
            const shortName = mt.name.slice(0, 8);
            tags.push(`<span class="sms-tag sms-tag--pending" title="${mt.name}: oczekuje">${shortName}…</span>`);
        }
    }

    return tags.length ? tags.join('') : '<span class="sms-tag sms-tag--none">—</span>';
}
```

---

## Phase 6 — Public Confirmation Page

**Milestone**: Client taps SMS link on phone → sees mobile-first page → taps Confirm or Decline → sees success screen. Audit log entry created. Toast shown on the confirmation page.

### 6.1 Route (no auth required)

File: `routes/public_routes.py` (new Blueprint — no `@login_required`)

```python
"""
Public routes — no authentication required.
Used for client-facing pages accessed via SMS links.
"""
import logging
from flask import Blueprint, render_template, request
from repositories.appointments.appointment_repository import AppointmentRepository
from repositories.clients.client_repository import ClientRepository
from repositories.audit_repository import AuditRepository

public_bp = Blueprint('public', __name__)


@public_bp.route('/confirm/<token>', methods=['GET'])
def appointment_confirm_view(token):
    repo = AppointmentRepository()
    appt = repo.get_by_confirmation_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    client = ClientRepository().get_by_id(appt['client_id'])
    return render_template(
        'public/appointment_confirm.html',
        appointment=appt,
        client=client,
        token=token,
        already_responded=(appt.get('confirmation_status') is not None),
        confirmation_status=appt.get('confirmation_status'),
        just_submitted=False,
    )


@public_bp.route('/confirm/<token>', methods=['POST'])
def appointment_confirm_submit(token):
    repo = AppointmentRepository()
    appt = repo.get_by_confirmation_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    # Idempotent — already responded
    if appt.get('confirmation_status'):
        return render_template(
            'public/appointment_confirm.html',
            appointment=appt, client=None, token=token,
            already_responded=True,
            confirmation_status=appt['confirmation_status'],
            just_submitted=False,
        )

    action = request.form.get('action')
    if action not in ('confirmed', 'declined'):
        return render_template(
            'public/appointment_confirm.html',
            appointment=appt, client=None, token=token,
            error='Nieprawidłowa akcja', already_responded=False,
            confirmation_status=None, just_submitted=False,
        )

    repo.update_confirmation_status(appt['id'], action)
    AuditRepository().log_event(
        entity_type='appointment', action='CLIENT_CONFIRMATION',
        entity_id=appt['id'],
        entity_label=f"{appt.get('appointment_date')} {str(appt.get('start_time',''))[:5]}",
        field_name='confirmation_status',
        old_value=None, new_value=action,
        user_id=None, user_name='Klient (SMS)',
    )

    return render_template(
        'public/appointment_confirm.html',
        appointment=appt, client=None, token=token,
        just_submitted=True, already_responded=True,
        confirmation_status=action,
    )
```

Register: `app.register_blueprint(public_bp)`

### 6.2 Public confirmation template

File: `templates/public/appointment_confirm.html`

**Standalone template (does NOT extend base.html)** — sidebar and auth nav must not appear.

```html
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Potwierdzenie wizyty — MyWay Beauty Salon</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', sans-serif;
            background: #f5f5f0;
            min-height: 100vh;
            display: flex; align-items: center; justify-content: center;
            padding: 1rem;
        }
        .card {
            background: white; border-radius: 8px;
            padding: 2rem 1.5rem; max-width: 420px; width: 100%;
            box-shadow: 0 4px 20px rgba(0,0,0,.08);
        }
        .salon-name { font-size: 0.75rem; font-weight: 500; letter-spacing: 0.1em;
                      text-transform: uppercase; color: #888; margin-bottom: 1.5rem; }
        .heading { font-size: 1.25rem; font-weight: 600; color: #1a1a1a; margin-bottom: 0.5rem; }
        .subheading { font-size: 0.875rem; color: #666; margin-bottom: 1.5rem; }
        .details-block { background: #f9f9f7; border-radius: 6px;
                         padding: 1rem; margin-bottom: 1.5rem; }
        .detail-row { display: flex; justify-content: space-between;
                      padding: 0.375rem 0; font-size: 0.875rem; }
        .detail-label { color: #888; }
        .detail-value { font-weight: 500; color: #1a1a1a; }
        .btn-confirm {
            display: block; width: 100%; padding: 0.875rem;
            background: #1a1a1a; color: white; border: none; border-radius: 6px;
            font-family: inherit; font-size: 0.9375rem; font-weight: 500;
            cursor: pointer; margin-bottom: 0.75rem;
        }
        .btn-confirm:active { background: #333; }
        .btn-decline {
            display: block; width: 100%; padding: 0.875rem;
            background: white; color: #666; border: 1px solid #ddd; border-radius: 6px;
            font-family: inherit; font-size: 0.875rem; cursor: pointer;
        }
        .status-icon { font-size: 2rem; margin-bottom: 0.75rem; }
        .status-message { font-size: 0.875rem; color: #666; margin-top: 0.5rem; }
        .toast {
            position: fixed; bottom: 1.5rem; left: 50%;
            transform: translateX(-50%);
            background: #1a1a1a; color: white;
            padding: 0.75rem 1.5rem; border-radius: 6px; font-size: 0.875rem;
            animation: slideup 0.3s ease;
        }
        @keyframes slideup {
            from { transform: translateX(-50%) translateY(16px); opacity: 0; }
            to   { transform: translateX(-50%) translateY(0);    opacity: 1; }
        }
    </style>
</head>
<body>
<div class="card">
    <p class="salon-name">MyWay Beauty Salon</p>

    {% if already_responded %}
        {% if confirmation_status == 'confirmed' %}
            <div class="status-icon">✅</div>
            <h1 class="heading">Wizyta potwierdzona</h1>
            <p class="status-message">Dziękujemy za potwierdzenie. Do zobaczenia!</p>
        {% elif confirmation_status == 'declined' %}
            <div class="status-icon">❌</div>
            <h1 class="heading">Wizyta odrzucona</h1>
            <p class="status-message">Otrzymaliśmy Twoją odpowiedź. Skontaktujemy się w razie potrzeby.</p>
        {% endif %}

        {% if just_submitted %}
        <script>
            window.addEventListener('load', () => {
                const t = document.createElement('div');
                t.className = 'toast';
                t.textContent = '{% if confirmation_status == "confirmed" %}Wizyta potwierdzona!{% else %}Odpowiedź zapisana.{% endif %}';
                document.body.appendChild(t);
                setTimeout(() => t.remove(), 3500);
            });
        </script>
        {% endif %}

    {% else %}
        <h1 class="heading">Potwierdzenie wizyty</h1>
        <p class="subheading">Prosimy o potwierdzenie lub anulowanie wizyty.</p>

        <div class="details-block">
            <div class="detail-row">
                <span class="detail-label">Data</span>
                <span class="detail-value">{{ appointment.appointment_date }}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Godzina</span>
                <span class="detail-value">{{ appointment.start_time|string|truncate(5, True, '') }}</span>
            </div>
            {% if appointment.employee_name %}
            <div class="detail-row">
                <span class="detail-label">Specjalista</span>
                <span class="detail-value">{{ appointment.employee_name }}</span>
            </div>
            {% endif %}
        </div>

        <form method="POST" action="/confirm/{{ token }}">
            <button type="submit" name="action" value="confirmed" class="btn-confirm">
                Potwierdzam wizytę
            </button>
            <button type="submit" name="action" value="declined" class="btn-decline">
                Odwołuję wizytę
            </button>
        </form>
    {% endif %}
</div>
</body>
</html>
```

File: `templates/public/confirm_invalid.html` — minimal standalone page: "Link wygasł lub jest nieprawidłowy. Skontaktuj się z salonem." Same CSS structure.

### 6.3 Global toast function (in `templates/base.html`)

Add before closing `</body>`:

```javascript
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-visible'));
    setTimeout(() => {
        toast.classList.remove('toast-visible');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}
```

CSS (in `base.html` `<style>` block):

```css
.toast-notification {
    position: fixed; bottom: 1.5rem; left: 50%;
    transform: translateX(-50%) translateY(16px);
    padding: 0.75rem 1.5rem; border-radius: 6px;
    font-size: 0.875rem; font-family: var(--font-body);
    opacity: 0; transition: opacity 0.25s ease, transform 0.25s ease;
    z-index: 9999; pointer-events: none;
}
.toast-notification.toast-visible { opacity: 1; transform: translateX(-50%) translateY(0); }
.toast-success { background: #1a1a1a; color: white; }
.toast-error   { background: #dc2626; color: white; }
.toast-info    { background: #2563eb; color: white; }
```

---

## Phase 7 — APScheduler Background Auto-Send

**Milestone**: When any `sms_message_types.is_enabled = TRUE`, the scheduler fires every 15 minutes and dispatches due reminders for each enabled type independently.

### 7.1 APScheduler setup

Install: `pip install APScheduler`

File: `scheduler.py` (new, top-level)

```python
"""
Background scheduler for periodic SMS auto-send.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_scheduler = None


def _run_auto_reminders(app):
    with app.app_context():
        from repositories.sms.sms_repository import SmsSettingsRepository
        settings = SmsSettingsRepository().get_settings() or {}
        if not settings.get('is_active'):
            return  # Global switch off — skip

        base_url = app.config.get('BASE_URL', 'http://localhost:5000')
        from services.sms_service import SmsService
        result = SmsService().send_due_reminders(base_url)
        if result['sent'] > 0 or result['failed'] > 0:
            logging.info("Auto SMS: sent=%s failed=%s skipped=%s",
                         result['sent'], result['failed'], result['skipped'])


def start_scheduler(app):
    global _scheduler
    _scheduler = BackgroundScheduler(timezone='Europe/Warsaw')
    _scheduler.add_job(
        func=_run_auto_reminders,
        args=[app],
        trigger=IntervalTrigger(minutes=15),
        id='sms_auto_send',
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logging.info("SMS auto-send scheduler started (interval=15min)")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
```

In `app.py`:

```python
from scheduler import start_scheduler
start_scheduler(app)

import atexit
from scheduler import stop_scheduler
atexit.register(stop_scheduler)

app.config['BASE_URL'] = os.environ.get('BASE_URL', 'http://localhost:5000')
```

---

## Phase 8 — Audit Trail UI

**Milestone**: All SMS events appear in appointment audit trail with correct action labels and source identification.

### 8.1 Action label mapping

In JS audit trail rendering (appointment view and audit log views):

```javascript
const ACTION_LABELS = {
    'CREATE':               'Utworzona',
    'UPDATE':               'Zmiana',
    'STATUS_CHANGE':        'Zmiana statusu',
    'COMPLETE':             'Zamknięta',
    'SMS_SENT':             'SMS wysłany',
    'CLIENT_CONFIRMATION':  'Potwierdzenie klienta',
};
```

For `CLIENT_CONFIRMATION` rows: `user_name = 'Klient (SMS)'` — render with a 📱 phone icon badge instead of user avatar. The `field_name` is `confirmation_status` and `new_value` is `'confirmed'` or `'declined'`.

For `SMS_SENT` rows: `field_name` is `sms_type`, `new_value` contains the type name + phone + Twilio SID.

### 8.2 Audit trail filter chip

Add filter chip "Tylko SMS" on the appointment detail audit panel — shows only entries where `action IN ('SMS_SENT', 'CLIENT_CONFIRMATION')`.

### 8.3 Appointment list phone indicator

In `templates/appointments/list.html`, the SMS column (Phase 5) already serves as the primary indicator. No additional icon in the client name column needed.

---

## Phase 9 — pip dependencies and environment variables

**Milestone**: All dependencies installed, environment documented, deployment scripts updated.

### 9.1 Install

```bash
pip install twilio APScheduler
pip freeze > requirements.txt
```

### 9.2 Environment variables

| Variable | Description | Example |
|----------|-------------|---------|
| `BASE_URL` | Public-facing URL for confirmation links | `https://salon.example.com` |
| `TWILIO_ACCOUNT_SID` | Optional env override (primary storage is DB) | `ACxxx` |
| `TWILIO_AUTH_TOKEN` | Optional env override | `abc123` |

### 9.3 Twilio phone number notes

- Must be a Twilio-purchased number or an approved Alphanumeric Sender ID.
- Polish numbers require E.164 format: `+48XXXXXXXXX`.
- Alphanumeric sender ID (e.g. `MyWaySalon`) is supported in Poland but cannot receive replies — correct for outbound-only use.
- Phone normalization is handled by `SmsService._normalize_phone()` — accepts 9-digit, 11-digit, or E.164 input.

---

## Implementation Order (for AI agent)

Execute phases strictly in order. Do not proceed to the next phase until the done-condition is verified.

| Phase | Files created / modified | Done when |
|-------|--------------------------|-----------|
| **1** | `alembic/versions/<id>_add_sms_reminder_system.py` | `alembic upgrade head` succeeds; all tables and columns present in DB; seed rows for 3 built-in types exist |
| **2** | `repositories/sms/__init__.py`, `repositories/sms/sms_repository.py`, `services/sms_service.py`, `repositories/appointments/appointment_repository.py` (+4 methods) | `SmsService().get_settings()` and `SmsService().get_message_types()` return correct data without exception |
| **3** | `routes/sms_routes.py`, `templates/settings/sms.html`, `templates/settings/sms_log.html`, `app.py` (blueprint registration) | `/settings/sms` renders with stat cards and message-type cards; credential save persists to DB; message type enable/disable persists |
| **4** | `templates/appointments/view.html`, `routes/main_routes.py` (SMS context vars) | SMS dropdown visible on appointment view; clicking a type calls `/api/sms/send` and shows toast |
| **5** | `templates/appointments/list.html`, `routes/main_routes.py` (batch SMS load), `routes/appointment_routes.py` (if AJAX) | SMS column visible in appointments table; sent types show blue tags; pending types show dashed gray tags; confirmation status shows correctly |
| **6** | `routes/public_routes.py`, `templates/public/appointment_confirm.html`, `templates/public/confirm_invalid.html`, `templates/base.html` (toast JS+CSS) | `/confirm/<valid-token>` shows appointment details; form POST sets `confirmation_status`; audit row created; toast shown on submission |
| **7** | `scheduler.py`, `app.py` (start/stop scheduler) | App starts without error; scheduler log line appears; auto-send fires for due appointments when enabled |
| **8** | `templates/appointments/view.html` (audit filter chip) | `SMS_SENT` and `CLIENT_CONFIRMATION` events render correctly in audit trail; "Tylko SMS" filter works |
| **9** | `requirements.txt` | `pip install -r requirements.txt` installs `twilio` and `APScheduler` cleanly |

---

## Acceptance Criteria (full system)

### Credentials & Settings
- [ ] Admin configures Twilio credentials on `/settings/sms`
- [ ] Test SMS arrives on real phone within 30 seconds
- [ ] Invalid credentials: test connection shows error message with Twilio error code

### Message Types
- [ ] 3 built-in types shown with correct Polish names
- [ ] Each type can be enabled/disabled independently
- [ ] Each type has its own `send_hours_before` (1–168) and `template_text`
- [ ] `include_confirm_link` toggle controls whether `{confirm_url}` is rendered
- [ ] Admin can add custom type — it appears in the list with a delete button
- [ ] Admin cannot delete built-in types (button absent, endpoint rejects)
- [ ] Built-in type names are read-only; custom names are editable

### Manual Send
- [ ] "Wyślij SMS" dropdown in appointment view shows all types
- [ ] Already-sent types show "Wysłano" badge in the dropdown
- [ ] Clicking a type sends that specific SMS and shows toast on success
- [ ] Client without phone number: toast shows error, no SMS attempted

### Auto-Send (Scheduler)
- [ ] When a type is enabled and `is_active = TRUE`, scheduler sends at the configured window
- [ ] Each type is sent at most once per appointment (idempotent)
- [ ] `is_active = FALSE` disables all auto-send regardless of per-type flags

### Appointments List SMS Column
- [ ] Column appears after Status column only when SMS is active
- [ ] Sent types appear as blue tags with correct truncated names
- [ ] Pending enabled types appear as dashed gray tags
- [ ] Client confirmation shows `✓ Potw.` (green) or `✕ Odmowa` (red)
- [ ] Failed sends appear as red tags
- [ ] No SMS activity: column shows `—`

### Public Confirmation Page
- [ ] `/confirm/<token>` loads without login and shows appointment date/time/stylist
- [ ] Submitting "Potwierdzam" sets `confirmation_status = 'confirmed'`, shows thank-you
- [ ] Submitting "Odwołuję" sets `confirmation_status = 'declined'`, shows appropriate message
- [ ] Second visit to same link shows "already responded" state (idempotent)
- [ ] `audit_log` row with `action='CLIENT_CONFIRMATION'` exists after submission
- [ ] Toast shown on the confirmation page after form submit
- [ ] Invalid/expired token: returns 404 with graceful error page

### Audit Trail
- [ ] `SMS_SENT` audit entries appear with type name + phone + Twilio SID in `new_value`
- [ ] `CLIENT_CONFIRMATION` entries appear with phone icon, `user_name='Klient (SMS)'`
- [ ] "Tylko SMS" filter chip shows only SMS-related audit events

### Statistics Cards
- [ ] `/settings/sms` page shows 5 stat cards for 1-MTD and 5 for 3-MTD
- [ ] Confirmation rate `%` computed as `confirmed / confirm_requests × 100`
- [ ] Zero-state: all cards show 0 before any SMS is sent
- [ ] Period tab toggle switches between MTD1 and MTD3 card groups

---

## Key Design Decisions

**Multi-type instead of single template** — One `sms_settings.reminder_hours_before` cannot express "send confirmation 48h before AND a reminder 2h before". The `sms_message_types` table gives each type its own schedule and content independently. Adding a new type is an INSERT, not a schema change.

**Denormalized `message_type_key` in `sms_reminders`** — If an admin renames or deletes a custom type, the send log must still show what type was used. Storing the key string directly makes the log durable across type renames/deletions.

**"To be sent" derived at render time, not stored** — We do not pre-schedule SMS sends into a queue table. Instead, the scheduler queries `get_appointments_due_for_type()` every 15 minutes, and the UI derives "to be sent" by comparing enabled types against `sms_sent_map`. This keeps the DB simple and avoids stale queue entries.

**Batch load for appointments list** — `get_sent_types_batch(ids)` makes ONE query for the entire page of appointments, not one per row. This keeps list performance O(1) DB queries regardless of list length.

**Token in DB not JWT** — UUIDs allow instant revocation (nullify `confirmation_token` to invalidate) and simpler queries. No crypto library needed. Token is never rotated on resend — the same token works for all SMS types sent to the same appointment.

**APScheduler not Celery** — No Redis/RabbitMQ in the existing stack. APScheduler runs in-process; adequate for a single-instance salon app sending ≤30 reminders/day. If the app ever scales to multiple workers, swap the BackgroundScheduler for a database-backed JobStore (SQLAlchemyJobStore) to avoid duplicate sends.
