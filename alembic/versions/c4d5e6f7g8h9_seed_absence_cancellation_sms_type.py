"""seed absence_cancellation sms_message_types row

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-07-12

Manually-triggered (not event/status driven) SMS sent from the supervisor
conflict-resolution modal when a booked appointment is cancelled because the
assigned employee's absence was approved. Ships disabled — admin opts in from
the SMS settings page, same as every other custom type.
"""
from alembic import op

revision = 'c4d5e6f7g8h9'
down_revision = 'b3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO sms_message_types
            (type_key, name, description, is_enabled, send_hours_before, send_delay_minutes,
             template_text, include_booking_link, is_event_triggered, is_custom, sort_order)
        VALUES
            ('absence_cancellation',
             'Anulowanie wizyty (nieobecność pracownika)',
             'Wysylana recznie z modala rozwiazywania konfliktow, gdy wizyta zostaje anulowana z powodu zatwierdzonej nieobecnosci pracownika.',
             FALSE, 0, 0,
             'Twoja wizyta w dniu {date} o godz. {time} zostala odwolana z powodu nieobecnosci pracownika. Umow nowy termin online: {booking_url}',
             TRUE, FALSE, TRUE, 90)
        ON CONFLICT (type_key) DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM sms_message_types WHERE type_key = 'absence_cancellation'")
