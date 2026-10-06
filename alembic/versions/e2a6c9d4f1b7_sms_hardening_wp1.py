"""SMS hardening WP1: trigger_mode, sms_hold, booking_confirmed type, phone-digits index, employee-reminder re-time

Revision ID: e2a6c9d4f1b7
Revises: b7d3e9a1c4f2
Create Date: 2026-10-07

ADDITIVE ONLY — the legacy invoices-app (:8083) shares this database and must keep
working untouched: every new column has a server default, nothing is dropped or retyped.

1. sms_message_types.trigger_mode  ('before_visit' | 'on_status' | 'manual')
   The 15-minute reminder loop used to take EVERY enabled type and treat
   send_hours_before as "N hours before the visit". For the event-only types N = 0, so
   enabling `post_visit_message` texted clients "thanks, rate us" at the START of the
   visit and enabling `absence_cancellation` sent a false "your visit is cancelled" to
   everyone starting in the window. The loop now only takes `before_visit` types.
2. appointments.sms_hold
   Online bookings from a phone number we have never verified get ONE text (booking
   confirmation with confirm + cancel links); the reminder stream is held until the
   client confirms through that link. Stops a stranger's number being SMS-bombed.
3. sms_message_types: seed `booking_confirmed` — DISABLED (go-live switch, like every type).
4. Functional index on the digits of clients.phone — backs exact phone matching
   (`regexp_replace(phone,'[^0-9]','','g') = ANY(...)`) for rows written by EITHER app,
   replacing the old substring `ILIKE '%600%'` lookup.
5. Re-time still-`scheduled` employee_visit_reminder events. They were stored as a naive
   Warsaw time into a TIMESTAMPTZ column on a UTC session, i.e. 1-2 h too late.
   If the corrected moment has already passed the reminder is moot, so it is cancelled —
   re-timing it would make a stale "Za 20 min wizyta" text fire at the next tick.
"""
from alembic import op

revision = 'e2a6c9d4f1b7'
down_revision = 'b7d3e9a1c4f2'
branch_labels = None
depends_on = None

_WARSAW_REMINDER_AT = (
    "(((a.appointment_date + a.start_time) AT TIME ZONE 'Europe/Warsaw') - INTERVAL '20 minutes')"
)


def upgrade():
    # 1 ── trigger_mode ---------------------------------------------------------------
    op.execute("""
        ALTER TABLE sms_message_types
            ADD COLUMN IF NOT EXISTS trigger_mode VARCHAR(20) NOT NULL DEFAULT 'before_visit'
    """)
    op.execute("UPDATE sms_message_types SET trigger_mode = 'on_status' WHERE is_event_triggered")
    op.execute("""
        UPDATE sms_message_types SET trigger_mode = 'manual'
        WHERE NOT is_event_triggered AND send_hours_before = 0
    """)
    op.execute("""
        ALTER TABLE sms_message_types
            ADD CONSTRAINT ck_sms_message_types_trigger_mode
            CHECK (trigger_mode IN ('before_visit', 'on_status', 'manual'))
    """)

    # 2 ── sms_hold -------------------------------------------------------------------
    op.execute("""
        ALTER TABLE appointments
            ADD COLUMN IF NOT EXISTS sms_hold BOOLEAN NOT NULL DEFAULT FALSE
    """)

    # 3 ── booking_confirmed (disabled; no Polish diacritics → GSM-7, same as the newer seeds)
    op.execute("""
        INSERT INTO sms_message_types
            (type_key, name, description, is_enabled, send_hours_before, send_delay_minutes,
             template_text, include_confirm_link, include_cancel_link,
             is_event_triggered, is_custom, sort_order, trigger_mode)
        VALUES
            ('booking_confirmed',
             'Potwierdzenie rezerwacji online',
             'Jeden SMS zaraz po rezerwacji online, z linkiem do potwierdzenia i odwolania. Dla nowego numeru telefonu przypomnienia ruszaja dopiero po potwierdzeniu.',
             FALSE, 0, 0,
             '{salon_name}: rezerwacja przyjeta {date} o {time}. Potwierdz: {confirm_url} Odwolaj: {cancel_url}',
             TRUE, TRUE, FALSE, FALSE, 5, 'manual')
        ON CONFLICT (type_key) DO NOTHING
    """)

    # 4 ── exact phone matching index -------------------------------------------------
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_clients_phone_digits
            ON clients ((regexp_replace(phone, '[^0-9]', '', 'g')))
    """)

    # 5 ── repair employee reminders stored in the wrong timezone frame ---------------
    op.execute(f"""
        UPDATE sms_events e
        SET status = 'cancelled'
        FROM appointments a
        WHERE a.id = e.appointment_id
          AND e.event_type = 'employee_visit_reminder'
          AND e.status = 'scheduled'
          AND {_WARSAW_REMINDER_AT} <= NOW()
    """)
    op.execute(f"""
        UPDATE sms_events e
        SET scheduled_at = {_WARSAW_REMINDER_AT}
        FROM appointments a
        WHERE a.id = e.appointment_id
          AND e.event_type = 'employee_visit_reminder'
          AND e.status = 'scheduled'
    """)


def downgrade():
    # The re-timing in step 5 is a data repair and is intentionally not reversed.
    op.execute("DROP INDEX IF EXISTS ix_clients_phone_digits")
    op.execute("""
        UPDATE sms_reminders SET message_type_id = NULL
        WHERE message_type_id IN (SELECT id FROM sms_message_types WHERE type_key = 'booking_confirmed')
    """)
    op.execute("DELETE FROM sms_message_types WHERE type_key = 'booking_confirmed'")
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS sms_hold")
    op.execute("ALTER TABLE sms_message_types DROP CONSTRAINT IF EXISTS ck_sms_message_types_trigger_mode")
    op.execute("ALTER TABLE sms_message_types DROP COLUMN IF EXISTS trigger_mode")
