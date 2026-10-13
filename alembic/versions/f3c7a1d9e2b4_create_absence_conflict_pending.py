"""Create absence_conflict_pending table + seed absence_visit_update SMS type

Revision ID: f3c7a1d9e2b4
Revises: e2a6c9d4f1b7
Create Date: 2026-10-13

ADDITIVE ONLY — the legacy invoices-app (:8083) shares this database.

1. absence_conflict_pending — visits left WITHOUT a resolution when a supervisor
   clicks "Zatwierdź mimo to" in the absence conflict-resolution modal. Mirrors the
   conflict shape (absence / appointment / employee / original date+time, same as
   absence_conflict_resolutions) plus `valid_for`: the moment the visit is
   auto-cancelled if still unresolved (visit start − 48 h). Each row is paired with
   an `absence_cancellation` sms_events row scheduled at `valid_for`, so the client
   notice rides the ordinary 15-minute scheduler queue.
2. sms_message_types: seed `absence_visit_update` — the "Wyślij wiadomość" note for a
   visit whose stylist or time was changed in that modal. DISABLED (go-live switch,
   like every type); no Polish diacritics → GSM-7.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f3c7a1d9e2b4'
down_revision: Union[str, None] = 'e2a6c9d4f1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'absence_conflict_pending',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('absence_id', sa.Integer(), nullable=False),
        sa.Column('appointment_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=True),
        sa.Column('appointment_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('valid_for', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('sms_event_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['absence_id'], ['employee_absences.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sms_event_id'], ['sms_events.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('absence_id', 'appointment_id', name='uq_absence_conflict_pending'),
        sa.CheckConstraint(
            "status IN ('pending', 'auto_cancelled', 'resolved', 'failed')",
            name='check_absence_conflict_pending_status'),
    )
    op.create_index('idx_absence_conflict_pending_due', 'absence_conflict_pending',
                    ['status', 'valid_for'])

    op.execute("""
        INSERT INTO sms_message_types
            (type_key, name, description, is_enabled, send_hours_before, send_delay_minutes,
             template_text, include_cancel_link, is_event_triggered, is_custom, sort_order,
             trigger_mode)
        VALUES
            ('absence_visit_update',
             'Zmiana wizyty (nieobecnosc pracownika)',
             'Wysylana z modala rozwiazywania konfliktow (przycisk Wyslij wiadomosc), gdy wizycie zmieniono stylistke lub termin z powodu nieobecnosci pracownika.',
             FALSE, 0, 0,
             '{salon_name}: z powodu nieobecnosci pracownika zmienilismy Twoja wizyte. Aktualny termin: {date} godz. {time}. Jesli Ci nie pasuje, odwolaj: {cancel_url}',
             TRUE, FALSE, TRUE, 91, 'manual')
        ON CONFLICT (type_key) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE sms_reminders SET message_type_id = NULL
        WHERE message_type_id IN (SELECT id FROM sms_message_types WHERE type_key = 'absence_visit_update')
    """)
    op.execute("DELETE FROM sms_message_types WHERE type_key = 'absence_visit_update'")
    op.drop_index('idx_absence_conflict_pending_due', table_name='absence_conflict_pending')
    op.drop_table('absence_conflict_pending')
