"""add sms reminder system

Revision ID: q2r3s4t5u6v7
Revises: p0q1r2s3t4u5
Create Date: 2026-05-18
"""
from alembic import op

revision = 'q2r3s4t5u6v7'
down_revision = 'p0q1r2s3t4u5'
branch_labels = None
depends_on = None


def upgrade():
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

    op.execute("""
        CREATE TABLE IF NOT EXISTS sms_message_types (
            id                   SERIAL PRIMARY KEY,
            type_key             VARCHAR(50) NOT NULL UNIQUE,
            name                 VARCHAR(120) NOT NULL,
            description          VARCHAR(255),
            is_enabled           BOOLEAN NOT NULL DEFAULT FALSE,
            send_hours_before    INTEGER NOT NULL DEFAULT 24,
            template_text        TEXT NOT NULL DEFAULT '',
            include_confirm_link BOOLEAN NOT NULL DEFAULT FALSE,
            is_custom            BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order           INTEGER NOT NULL DEFAULT 99,
            created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("""
        INSERT INTO sms_message_types
            (type_key, name, description, is_enabled,
             send_hours_before, template_text, include_confirm_link, is_custom, sort_order)
        VALUES
            (
                'confirmation_request',
                'Prośba o potwierdzenie',
                'Wysyłana automatycznie X godzin przed wizytą. Zawiera link do potwierdzenia.',
                FALSE, 48,
                'Hej {client_name}! Przypominamy o wizycie w {salon_name} dnia {date} o {time}. Czy możesz potwierdzić wizytę? {confirm_url}',
                TRUE, FALSE, 1
            ),
            (
                'reminder_1',
                'Pierwsze przypomnienie',
                'Przypomnienie bez linku potwierdzenia — np. dzień przed wizytą.',
                FALSE, 24,
                'Przypomnienie: jutro o {time} zapraszamy do {salon_name} na {services}. Do zobaczenia!',
                FALSE, FALSE, 2
            ),
            (
                'reminder_2',
                'Drugie przypomnienie',
                'Krótkie przypomnienie tuż przed wizytą.',
                FALSE, 2,
                'Hej {client_name}, za {hours_before}h wizyta w {salon_name}. Do zobaczenia o {time}!',
                FALSE, FALSE, 3
            )
        ON CONFLICT (type_key) DO NOTHING
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS sms_reminders (
            id                   SERIAL PRIMARY KEY,
            appointment_id       INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
            client_id            INTEGER NOT NULL REFERENCES clients(id),
            message_type_id      INTEGER REFERENCES sms_message_types(id),
            message_type_key     VARCHAR(50) NOT NULL,
            phone_number         VARCHAR(20) NOT NULL,
            message_body         TEXT NOT NULL,
            twilio_sid           VARCHAR(64),
            status               VARCHAR(20) NOT NULL DEFAULT 'pending',
            error_message        TEXT,
            sent_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_by_user_id   INTEGER REFERENCES users(id),
            created_by_name      VARCHAR(120)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sms_reminders_appointment_id ON sms_reminders(appointment_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sms_reminders_client_id ON sms_reminders(client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sms_reminders_sent_at ON sms_reminders(sent_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sms_reminders_type_key ON sms_reminders(message_type_key)")

    op.execute("""
        ALTER TABLE appointments
            ADD COLUMN IF NOT EXISTS confirmation_token       UUID UNIQUE,
            ADD COLUMN IF NOT EXISTS confirmation_status      VARCHAR(20) DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS confirmation_updated_at  TIMESTAMP WITH TIME ZONE
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_confirmation_token ON appointments(confirmation_token)")


def downgrade():
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS confirmation_token")
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS confirmation_status")
    op.execute("ALTER TABLE appointments DROP COLUMN IF EXISTS confirmation_updated_at")
    op.execute("DROP TABLE IF EXISTS sms_reminders")
    op.execute("DROP TABLE IF EXISTS sms_message_types")
    op.execute("DROP TABLE IF EXISTS sms_settings")
