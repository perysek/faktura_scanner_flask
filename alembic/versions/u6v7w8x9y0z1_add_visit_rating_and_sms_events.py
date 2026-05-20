"""add visit rating, employee token, sms_events, status_change_events

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-05-20
"""
from alembic import op

revision = 'u6v7w8x9y0z1'
down_revision = 't5u6v7w8x9y0'
branch_labels = None
depends_on = None


def upgrade():
    # --- appointments: rating and employee tokens ---
    op.execute("""
        ALTER TABLE appointments
            ADD COLUMN IF NOT EXISTS rating_token  UUID DEFAULT gen_random_uuid() UNIQUE,
            ADD COLUMN IF NOT EXISTS rating_status VARCHAR(30),
            ADD COLUMN IF NOT EXISTS rated_on      TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS rated_by      VARCHAR(20),
            ADD COLUMN IF NOT EXISTS employee_token UUID DEFAULT gen_random_uuid() UNIQUE
    """)

    # Backfill any NULLs (safety net for existing rows)
    op.execute("""
        UPDATE appointments SET rating_token = gen_random_uuid()
        WHERE rating_token IS NULL
    """)
    op.execute("""
        UPDATE appointments SET employee_token = gen_random_uuid()
        WHERE employee_token IS NULL
    """)

    op.execute("""
        ALTER TABLE appointments
            ALTER COLUMN rating_token  SET NOT NULL,
            ALTER COLUMN employee_token SET NOT NULL
    """)

    # --- sms_message_types: event-triggered support ---
    op.execute("""
        ALTER TABLE sms_message_types
            ADD COLUMN IF NOT EXISTS send_delay_minutes  INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS trigger_on_status   VARCHAR(30),
            ADD COLUMN IF NOT EXISTS is_event_triggered  BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS include_rate_link   BOOLEAN NOT NULL DEFAULT FALSE
    """)

    # --- sms_events table ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS sms_events (
            id               SERIAL PRIMARY KEY,
            appointment_id   INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
            event_type       VARCHAR(50) NOT NULL,
            scheduled_at     TIMESTAMPTZ NOT NULL,
            sent_at          TIMESTAMPTZ,
            status           VARCHAR(30) NOT NULL DEFAULT 'scheduled',
            sms_reminder_id  INTEGER REFERENCES sms_reminders(id),
            error_message    TEXT,
            retry_count      INTEGER NOT NULL DEFAULT 0,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sms_events_due
            ON sms_events(scheduled_at)
            WHERE status = 'scheduled'
    """)

    # --- status_change_events table ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS status_change_events (
            id             SERIAL PRIMARY KEY,
            appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
            old_status     VARCHAR(30),
            new_status     VARCHAR(30) NOT NULL,
            triggered_by   VARCHAR(30) NOT NULL DEFAULT 'employee_mobile',
            created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_status_change_events_created
            ON status_change_events(created_at)
    """)

    # --- seed post_visit_message type ---
    op.execute("""
        INSERT INTO sms_message_types
            (type_key, name, description, is_enabled, send_hours_before, send_delay_minutes,
             template_text, include_rate_link, is_event_triggered, trigger_on_status, sort_order)
        VALUES
            ('post_visit_message',
             'Ocena po wizycie',
             'Wysylana po zakonczeniu wizyty. Zawiera link do formularza oceny.',
             FALSE, 0, 30,
             'Hej {client_name}! Dziekujemy za wizyte w {salon_name}. Bedziemy wdzieczni za chwile i ocene naszej uslugi: {rate_url}',
             TRUE, TRUE, 'completed', 10)
        ON CONFLICT (type_key) DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM sms_message_types WHERE type_key = 'post_visit_message'")
    op.execute("DROP TABLE IF EXISTS status_change_events")
    op.execute("DROP TABLE IF EXISTS sms_events")
    op.execute("""
        ALTER TABLE sms_message_types
            DROP COLUMN IF EXISTS include_rate_link,
            DROP COLUMN IF EXISTS is_event_triggered,
            DROP COLUMN IF EXISTS trigger_on_status,
            DROP COLUMN IF EXISTS send_delay_minutes
    """)
    op.execute("""
        ALTER TABLE appointments
            DROP COLUMN IF EXISTS employee_token,
            DROP COLUMN IF EXISTS rated_by,
            DROP COLUMN IF EXISTS rated_on,
            DROP COLUMN IF EXISTS rating_status,
            DROP COLUMN IF EXISTS rating_token
    """)
