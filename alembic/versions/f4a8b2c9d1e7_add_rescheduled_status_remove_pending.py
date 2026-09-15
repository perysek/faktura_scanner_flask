"""Add 'rescheduled' appointment status, remove stale 'pending'

Revision ID: f4a8b2c9d1e7
Revises: c90e539f3354
Create Date: 2026-09-15

Adds the 'rescheduled' status (a scheduled/confirmed visit whose date/time
changed — AppointmentBusinessService.reschedule_appointment freezes the
original row with this status and clones a new appointment carrying the
updated date/time forward). Bundles removal of 'pending', confirmed dead via
a full-repo audit: no route/service/repository ever sets an appointment's
status to 'pending' (create_appointment always defaults to 'scheduled'); the
only reachable path was an unguarded status <select> on the desktop edit
form, never exercised in practice.

New columns:
- clients.rescheduled_count — bumped by
  AppointmentBusinessService.apply_status_change_side_effects on every
  -> 'rescheduled' transition, same pattern as no_show_count/cancelled_count.
- appointments.rescheduled_to_appointment_id — nullable self-FK, set on the
  frozen original, pointing at its clone. Supports the reschedule-chain
  banner/link on the appointment detail page without parsing audit_log text.
"""
from alembic import op
import sqlalchemy as sa

revision = 'f4a8b2c9d1e7'
down_revision = 'c90e539f3354'
branch_labels = None
depends_on = None


def upgrade():
    # Defensive backfill before tightening the constraint — should be a
    # no-op (nothing sets 'pending'), but this is live production data and
    # nothing has ever verified there's no stray row from an older,
    # since-removed code path.
    op.execute("UPDATE appointments SET status = 'scheduled' WHERE status = 'pending'")

    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS chk_appointments_status_v2")
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT chk_appointments_status_v3 "
        "CHECK (status IN ("
        "'scheduled', 'confirmed', 'in_progress', "
        "'completed', 'cancelled', 'no_show', 'rescheduled'"
        "))"
    )

    op.add_column('clients', sa.Column('rescheduled_count', sa.Integer(),
                                        nullable=False, server_default='0'))

    op.add_column('appointments', sa.Column('rescheduled_to_appointment_id',
                                             sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_appointments_rescheduled_to', 'appointments', 'appointments',
        ['rescheduled_to_appointment_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_appointments_rescheduled_to', 'appointments',
                     ['rescheduled_to_appointment_id'])
    # No backfill needed for either new column — neither 'rescheduled' nor a
    # value in rescheduled_to_appointment_id could exist before this migration.


def downgrade():
    op.drop_index('ix_appointments_rescheduled_to', table_name='appointments')
    op.drop_constraint('fk_appointments_rescheduled_to', 'appointments', type_='foreignkey')
    op.drop_column('appointments', 'rescheduled_to_appointment_id')
    op.drop_column('clients', 'rescheduled_count')

    op.execute("ALTER TABLE appointments DROP CONSTRAINT IF EXISTS chk_appointments_status_v3")
    op.execute(
        "ALTER TABLE appointments ADD CONSTRAINT chk_appointments_status_v2 "
        "CHECK (status IN ("
        "'scheduled', 'pending', 'confirmed', 'in_progress', "
        "'completed', 'cancelled', 'no_show'"
        "))"
    )
