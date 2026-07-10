# VISIT RATING & STATUS TRANSITION SMS — Implementation Plan

**Features**:
1. Post-visit client rating form delivered via SMS 30 min after visit completion.
2. Employee (stylist) mobile-first form for real-time status transitions (`confirmed→in_progress`, `in_progress→completed`) with time-gated access token.
3. Real-time web app toast notifications when employee mobile form triggers a status change.

---

## Architecture Overview

### Key Design Decision: Event-Driven SMS via `sms_events` Table

The existing scheduler fires **time-before-appointment** queries (`send_hours_before`).
The new feature needs **event-triggered** scheduling: "send X minutes after status changes to Y".

**Solution**: New `sms_events` table stores scheduled jobs with explicit `scheduled_at`
timestamps. When a status change fires, a row is inserted with `scheduled_at = NOW() + delay`.
The existing 15-min APScheduler job checks this table on each tick — no new scheduler jobs,
no APScheduler date-triggers, no race conditions.

### Status Change Hook Location

All status mutations flow through `repo.update_status()` in:
- **`routes/appointment_routes.py`** — primary (line ~966, `update_past_appointment_status`)
- **`routes/public_routes.py`** — client SMS confirmation → `confirmed` status

Hook lives in the **route layer** (not repository) to keep DB code free of business
logic and to have access to `current_app.config['BASE_URL']`.

### Rating Token

A `rating_token UUID` column (auto-generated via `gen_random_uuid()`) gives every
appointment a stable unique URL for the mobile form: `/rate/<token>`.
Reuses the same pattern as the existing `confirmation_token`.

---

## Dependency Graph

```
P01 (migration)
  └─ P02 (models update)
       ├─ P03 (repositories)
       │    ├─ P04 (SMS service extension)
       │    │    ├─ P05 (status change hook in routes)
       │    │    └─ P06 (scheduler extension)
       │    └─ P08 (public rating routes)
       │         └─ P07 (mobile rating template)
       └─ P09 (app UI rating status)

P10 (employee mobile status form + realtime web toasts) — parallel to P07-P09
P11 (SMS settings UI for send_delay_minutes) — last, independent
```

---

## Phase P01: Database Migration

**New file**: `alembic/versions/u6v7w8x9y0z1_add_visit_rating_and_sms_events.py`

`down_revision = 't5u6v7w8x9y0'` (last SMS migration)

### New columns on `appointments`

```sql
ALTER TABLE appointments
    ADD COLUMN rating_token  UUID DEFAULT gen_random_uuid() UNIQUE,
    ADD COLUMN rating_status VARCHAR(30),   -- 'scheduled'|'sent'|'awaiting_feedback'|'received'
    ADD COLUMN rated_on      TIMESTAMPTZ,
    ADD COLUMN rated_by      VARCHAR(20);   -- 'client'

-- Backfill token for any rows created before migration (safety net)
UPDATE appointments SET rating_token = gen_random_uuid() WHERE rating_token IS NULL;
ALTER TABLE appointments ALTER COLUMN rating_token SET NOT NULL;
```

### Extend `sms_message_types`

```sql
ALTER TABLE sms_message_types
    ADD COLUMN send_delay_minutes  INTEGER DEFAULT 0,
    ADD COLUMN trigger_on_status   VARCHAR(30),   -- 'completed' | 'in_progress'
    ADD COLUMN is_event_triggered  BOOLEAN DEFAULT FALSE,
    ADD COLUMN include_rate_link   BOOLEAN DEFAULT FALSE;
```

### New table `sms_events`

```sql
CREATE TABLE sms_events (
    id               SERIAL PRIMARY KEY,
    appointment_id   INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    event_type       VARCHAR(50) NOT NULL,
    scheduled_at     TIMESTAMPTZ NOT NULL,
    sent_at          TIMESTAMPTZ,
    status           VARCHAR(30) NOT NULL DEFAULT 'scheduled',
    sms_reminder_id  INTEGER REFERENCES sms_reminders(id),
    error_message    TEXT,
    retry_count      INTEGER DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sms_events_due
    ON sms_events(scheduled_at)
    WHERE status = 'scheduled';
```

### New column on `appointments` — employee access token

```sql
ALTER TABLE appointments ADD COLUMN employee_token UUID DEFAULT gen_random_uuid() UNIQUE;
UPDATE appointments SET employee_token = gen_random_uuid() WHERE employee_token IS NULL;
ALTER TABLE appointments ALTER COLUMN employee_token SET NOT NULL;
```

Token is time-gated in application logic (accessible ≤30 min before scheduled start).
Separate from `confirmation_token` (client use) and `rating_token` (post-visit rating).

### New table `status_change_events`

Lightweight log of status changes triggered by employee mobile form.
Consumed by the web app polling endpoint to deliver real-time toast notifications.

```sql
CREATE TABLE status_change_events (
    id             SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    old_status     VARCHAR(30),
    new_status     VARCHAR(30) NOT NULL,
    triggered_by   VARCHAR(30) NOT NULL DEFAULT 'employee_mobile',
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_status_change_events_created ON status_change_events(created_at);
```

### Seed new message types

```sql
INSERT INTO sms_message_types
    (type_key, name, description, is_enabled, send_hours_before, send_delay_minutes,
     template_text, include_rate_link, is_event_triggered, trigger_on_status, sort_order)
VALUES
    ('post_visit_message',
     'Ocena po wizycie',
     'Wysyłana po zakończeniu wizyty. Zawiera link do formularza oceny.',
     FALSE, 0, 30,
     'Hej {client_name}! Dziękujemy za wizytę w {salon_name}. '
     'Będziemy wdzięczni za chwilę i ocenę naszej usługi: {rate_url}',
     TRUE, TRUE, 'completed', 10);
```

### Down migration

```python
def downgrade():
    op.execute("DELETE FROM sms_message_types WHERE type_key = 'post_visit_message'")
    op.drop_table('status_change_events')
    op.drop_table('sms_events')
    op.drop_column('sms_message_types', 'include_rate_link')
    op.drop_column('sms_message_types', 'is_event_triggered')
    op.drop_column('sms_message_types', 'trigger_on_status')
    op.drop_column('sms_message_types', 'send_delay_minutes')
    op.drop_column('appointments', 'employee_token')
    op.drop_column('appointments', 'rated_by')
    op.drop_column('appointments', 'rated_on')
    op.drop_column('appointments', 'rating_status')
    op.drop_column('appointments', 'rating_token')
```

**Acceptance**: `alembic upgrade head` and `alembic downgrade -1` run cleanly with no data loss.

---

## Phase P02: Data Models Update

**File**: `database/models.py`

### Update `Appointment` dataclass (add after `satisfaction_score`)

```python
rating_token:   Optional[str]      = None   # UUID — client rating form URL
rating_status:  Optional[str]      = None   # 'scheduled'|'sent'|'awaiting_feedback'|'received'
rated_on:       Optional[datetime] = None
rated_by:       Optional[str]      = None   # 'client'
employee_token: Optional[str]      = None   # UUID — employee mobile form URL (time-gated)
```

### New `SmsEvent` dataclass

```python
@dataclass
class SmsEvent:
    appointment_id:  int
    event_type:      str
    scheduled_at:    datetime
    status:          str                = 'scheduled'
    sent_at:         Optional[datetime] = None
    sms_reminder_id: Optional[int]     = None
    error_message:   Optional[str]     = None
    retry_count:     int               = 0
    created_at:      Optional[datetime] = None
    id:              Optional[int]     = None
```

### New `StatusChangeEvent` dataclass

```python
@dataclass
class StatusChangeEvent:
    appointment_id: int
    new_status:     str
    old_status:     Optional[str] = None
    triggered_by:   str           = 'employee_mobile'
    created_at:     Optional[datetime] = None
    id:             Optional[int] = None
```

### Update `SmsMessageType` dataclass (if it exists in models.py)

```python
send_delay_minutes: int          = 0
trigger_on_status:  Optional[str] = None
is_event_triggered: bool         = False
include_rate_link:  bool         = False
```

---

## Phase P03: Repository Updates

### 3a. AppointmentRepository additions

**File**: `repositories/appointments/appointment_repository.py`

```python
def get_by_rating_token(self, token: str) -> Optional[dict]:
    """Public lookup by rating_token (no auth required)."""
    sql = """
        SELECT a.*, c.first_name, c.last_name, c.phone
        FROM appointments a
        JOIN clients c ON c.id = a.client_id
        WHERE a.rating_token = %s
    """
    row = self._db.fetchone(sql, (token,))
    return dict(row) if row else None

def update_rating(self, appointment_id: int, score: int,
                  rated_on, rated_by: str = 'client') -> bool:
    """Set satisfaction_score + rating metadata atomically."""
    sql = """
        UPDATE appointments
        SET satisfaction_score = %s,
            rated_on           = %s,
            rated_by           = %s,
            rating_status      = 'received'
        WHERE id = %s
    """
    return self._db.execute(sql, (score, rated_on, rated_by, appointment_id))

def update_rating_status(self, appointment_id: int, status: str) -> bool:
    sql = "UPDATE appointments SET rating_status = %s WHERE id = %s"
    return self._db.execute(sql, (status, appointment_id))
```

### 3b. New SmsEventRepository

**New file**: `repositories/sms/sms_event_repository.py`

```python
"""Repository for event-triggered SMS scheduling."""
from datetime import datetime
from typing import List, Optional


class SmsEventRepository:

    def create(self, appointment_id: int, event_type: str,
               scheduled_at: datetime) -> int:
        """Insert sms_events row. Returns new id."""
        sql = """
            INSERT INTO sms_events (appointment_id, event_type, scheduled_at)
            VALUES (%s, %s, %s)
            RETURNING id
        """
        row = self._db.fetchone(sql, (appointment_id, event_type, scheduled_at))
        return row['id']

    def get_due(self) -> List[dict]:
        """All events where scheduled_at <= NOW() and status = 'scheduled'."""
        sql = """
            SELECT e.*, a.rating_token, a.client_id,
                   a.appointment_date, a.start_time
            FROM sms_events e
            JOIN appointments a ON a.id = e.appointment_id
            WHERE e.scheduled_at <= NOW()
              AND e.status = 'scheduled'
            ORDER BY e.scheduled_at
        """
        return [dict(r) for r in self._db.fetchall(sql)]

    def mark_sent(self, event_id: int, sms_reminder_id: int) -> bool:
        sql = """
            UPDATE sms_events
            SET status = 'sent', sent_at = NOW(), sms_reminder_id = %s
            WHERE id = %s
        """
        return self._db.execute(sql, (sms_reminder_id, event_id))

    def mark_failed(self, event_id: int, error_message: str) -> bool:
        sql = """
            UPDATE sms_events
            SET status = 'failed', error_message = %s,
                retry_count = retry_count + 1
            WHERE id = %s
        """
        return self._db.execute(sql, (error_message, event_id))

    def cancel_pending_for_appointment(self, appointment_id: int) -> int:
        """Cancel all 'scheduled' events for this appointment. Returns count."""
        sql = """
            UPDATE sms_events SET status = 'cancelled'
            WHERE appointment_id = %s AND status = 'scheduled'
        """
        return self._db.execute(sql, (appointment_id,))
```

### 3c. New StatusChangeEventRepository

**New file**: `repositories/appointments/status_change_event_repository.py`

```python
"""Repository for real-time status-change notification events."""
from datetime import datetime
from typing import List


class StatusChangeEventRepository:

    def create(self, appointment_id: int, old_status: str, new_status: str,
               triggered_by: str = 'employee_mobile') -> int:
        sql = """
            INSERT INTO status_change_events
                (appointment_id, old_status, new_status, triggered_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        row = self._db.fetchone(sql, (appointment_id, old_status, new_status, triggered_by))
        return row['id']

    def get_since(self, since: datetime) -> List[dict]:
        """Fetch all events created after 'since'. Consumed by the polling endpoint."""
        sql = """
            SELECT e.*,
                   c.first_name || ' ' || c.last_name AS client_name
            FROM status_change_events e
            JOIN appointments a ON a.id = e.appointment_id
            JOIN clients c      ON c.id = a.client_id
            WHERE e.created_at > %s
            ORDER BY e.created_at
        """
        return [dict(r) for r in self._db.fetchall(sql, (since,))]
```

### 3d. AppointmentRepository — additional method

Add to the existing additions in 3a:

```python
def get_by_employee_token(self, token: str) -> Optional[dict]:
    """Public lookup by employee_token. Used by employee mobile form route."""
    sql = """
        SELECT a.*,
               c.first_name, c.last_name, c.phone,
               e.full_name AS employee_name
        FROM appointments a
        JOIN clients c ON c.id = a.client_id
        LEFT JOIN employees e ON e.id = a.employee_id
        WHERE a.employee_token = %s
    """
    row = self._db.fetchone(sql, (token,))
    return dict(row) if row else None
```

### 3e. SmsMessageTypeRepository — new method

**File**: `repositories/sms/sms_repository.py`

```python
def get_event_triggered_by_status(self, trigger_on_status: str) -> List[dict]:
    """Return all enabled event-triggered types for a status transition."""
    sql = """
        SELECT * FROM sms_message_types
        WHERE is_event_triggered = TRUE
          AND trigger_on_status  = %s
          AND is_enabled         = TRUE
    """
    return [dict(r) for r in self._db.fetchall(sql, (trigger_on_status,))]
```

---

## Phase P04: SMS Service Extension

**File**: `services/sms_service.py`

### New method: `schedule_event_sms()`

```python
def schedule_event_sms(self, appointment_id: int, event_type: str,
                        delay_minutes: int, base_url: str) -> Optional[int]:
    """
    Create an sms_events row to fire 'event_type' SMS after delay_minutes.
    Updates appointment.rating_status = 'scheduled' for post_visit_message.
    Returns sms_events.id, or None if SMS globally disabled.
    """
    from datetime import datetime, timedelta, timezone
    from repositories.sms.sms_event_repository import SmsEventRepository

    settings = self.get_settings()
    if not settings.get('is_active'):
        return None

    scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    event_id = SmsEventRepository().create(appointment_id, event_type, scheduled_at)

    if event_type == 'post_visit_message':
        self._appt_repo.update_rating_status(appointment_id, 'scheduled')

    return event_id
```

### New method: `send_due_event_sms()`

```python
def send_due_event_sms(self, base_url: str) -> dict:
    """
    Called by scheduler every 15 min. Sends all due sms_events rows.
    Returns {sent, failed, skipped}.
    """
    from repositories.sms.sms_event_repository import SmsEventRepository
    event_repo = SmsEventRepository()

    sent = failed = skipped = 0
    for event in event_repo.get_due():
        try:
            result = self.send(
                appointment_id=event['appointment_id'],
                message_type_key=event['event_type'],
                base_url=base_url,
            )
            if result.get('success'):
                event_repo.mark_sent(event['id'], result.get('reminder_id'))
                if event['event_type'] == 'post_visit_message':
                    self._appt_repo.update_rating_status(
                        event['appointment_id'], 'sent'
                    )
                sent += 1
            else:
                event_repo.mark_failed(event['id'], result.get('error', ''))
                failed += 1
        except Exception as e:
            event_repo.mark_failed(event['id'], str(e))
            failed += 1

    return {'sent': sent, 'failed': failed, 'skipped': skipped}
```

### New high-level method: `schedule_status_triggered_sms()`

Shared entry point called from **both** `appointment_routes.py` (admin status change)
and `public_routes.py` (employee mobile form). Avoids duplicating the lookup logic.

```python
def schedule_status_triggered_sms(self, appointment_id: int,
                                   trigger_status: str, base_url: str) -> int:
    """
    Look up all enabled event-triggered types for trigger_status,
    schedule each, and return count scheduled.
    """
    settings = self.get_settings()
    if not settings.get('is_active'):
        return 0

    types = self._type_repo.get_event_triggered_by_status(trigger_status)
    count = 0
    for mt in types:
        if mt.get('is_enabled'):
            self.schedule_event_sms(
                appointment_id, mt['type_key'],
                mt.get('send_delay_minutes', 0), base_url,
            )
            count += 1
    return count
```

### Extend `_render_template()` (or wherever placeholders are substituted)

Add `{rate_url}` support alongside existing `{confirm_url}`, `{cancel_url}`:

```python
if '{rate_url}' in template_text:
    rating_token = appt.get('rating_token', '')
    rate_url = f"{base_url.rstrip('/')}/rate/{rating_token}"
    template_text = template_text.replace('{rate_url}', rate_url)
```

Locate the exact method name (`_render_template`, `_build_message`, or similar) in
`services/sms_service.py` before implementing — the placeholder substitution block
is the insertion point.

---

## Phase P05: Status Change Hook

**File**: `routes/appointment_routes.py`

### Add two private helper functions (top of file or near `_audit`):

```python
def _schedule_post_visit_sms(appointment_id: int) -> None:
    """Schedule post-visit rating SMS when visit status → completed. Swallows errors.
    Called from admin status-change route AND employee mobile form route."""
    try:
        from services.sms_service import SmsService
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5000')
        SmsService().schedule_status_triggered_sms(appointment_id, 'completed', base_url)
    except Exception as exc:
        logging.error('_schedule_post_visit_sms failed appt_id=%s: %s', appointment_id, exc)


def _cancel_event_sms(appointment_id: int) -> None:
    """Cancel all pending sms_events when appointment is cancelled."""
    try:
        from repositories.sms.sms_event_repository import SmsEventRepository
        SmsEventRepository().cancel_pending_for_appointment(appointment_id)
    except Exception as exc:
        logging.error('_cancel_event_sms failed appt_id=%s: %s', appointment_id, exc)
```

### Hook into status update (around line 966, after `success = repo.update_status(...)`):

```python
if success:
    # ... existing audit log (unchanged) ...

    # Post-visit rating SMS: only fires when admin sets status to completed.
    # The employee mobile form (P10) calls _schedule_post_visit_sms() independently.
    if new_status == AppointmentStatus.COMPLETED:
        _schedule_post_visit_sms(appointment_id)
    elif new_status == AppointmentStatus.CANCELLED:
        _cancel_event_sms(appointment_id)
    # IN_PROGRESS transitions from admin: no SMS — employee mobile form handles this.

    return jsonify({'success': True, 'message': f'Status zaktualizowany na: {new_status}'})
```

**Note**: `AppointmentStatus.COMPLETED` = `'completed'`.
Verify exact constant names in `config/appointment_statuses.py`.

---

## Phase P06: Scheduler Extension

**File**: `scheduler.py`

Extend `_run_auto_reminders()` to also drain the `sms_events` queue:

```python
def _run_auto_reminders(app):
    with app.app_context():
        from repositories.sms.sms_repository import SmsSettingsRepository
        settings = SmsSettingsRepository().get_settings() or {}
        if not settings.get('is_active'):
            return

        base_url = app.config.get('BASE_URL', 'http://localhost:5000')
        from services.sms_service import SmsService
        svc = SmsService()

        # Existing: time-based pre-appointment reminders
        result = svc.send_due_reminders(base_url)
        if result['sent'] > 0 or result['failed'] > 0:
            logging.info("SMS reminders: sent=%s failed=%s skipped=%s",
                         result['sent'], result['failed'], result['skipped'])

        # New: event-triggered SMS (post_visit_message, visit_started, …)
        event_result = svc.send_due_event_sms(base_url)
        if event_result['sent'] > 0 or event_result['failed'] > 0:
            logging.info("SMS events: sent=%s failed=%s skipped=%s",
                         event_result['sent'], event_result['failed'],
                         event_result['skipped'])
```

No new APScheduler job needed — same 15-min interval handles both.

---

## Phase P07: Mobile Rating Form Template

**New file**: `templates/public/appointment_rate.html`

Design matches `appointment_confirm.html`: standalone HTML, inline CSS, Inter font,
420px card, `#f5f5f0` background.

### States

| State | Condition | Content |
|-------|-----------|---------|
| Default | `not already_rated` | 5 grey stars, no submit button |
| Star tapped | JS: user taps star | Stars update colour, two buttons appear |
| Submitted | `already_rated and just_submitted` | Thank-you message + star display |
| Already rated | `already_rated and not just_submitted` | "Już oceniłeś/aś tę wizytę" + star display |
| Invalid | No appointment for token | `templates/public/rate_invalid.html` (new) |

### Star Component HTML

```html
<div class="stars-row" id="stars">
    {% for i in range(1, 6) %}
    <button class="star" data-score="{{ i }}" type="button"
            aria-label="Ocena {{ i }}/5">★</button>
    {% endfor %}
</div>
<div id="submit-area" style="display:none;">
    <form id="rating-form" method="POST">
        <input type="hidden" name="score" id="score-input">
        <button class="btn-submit" id="btn-submit" type="submit">
            Prześlij ocenę
        </button>
        <button class="btn-skip" id="btn-skip" type="button">
            Nie teraz
        </button>
    </form>
</div>
<div id="skip-message" style="display:none;">
    <p class="status-message">Może następnym razem. Dziękujemy za wizytę!</p>
</div>
```

### CSS (key rules to add alongside existing styles)

```css
.stars-row {
    display: flex; gap: 0.5rem; justify-content: center; margin: 1.5rem 0;
}
.star {
    font-size: 2.75rem; background: none; border: none;
    cursor: pointer; color: #d0cfc9; padding: 0.25rem; line-height: 1;
    transition: color 0.12s, transform 0.1s;
    -webkit-tap-highlight-color: transparent;
}
.star.active { color: #f59e0b; }
.star:active  { transform: scale(1.15); }
.btn-submit {
    display: block; width: 100%; padding: 0.875rem;
    background: #1a1a1a; color: white; border: none; border-radius: 6px;
    font-family: inherit; font-size: 0.9375rem; font-weight: 500;
    cursor: pointer; margin-bottom: 0.75rem;
}
.btn-skip {
    display: block; width: 100%; padding: 0.875rem;
    background: white; color: #666; border: 1px solid #ddd; border-radius: 6px;
    font-family: inherit; font-size: 0.875rem; cursor: pointer;
}
```

### JavaScript (vanilla, no dependencies)

```javascript
let selectedScore = 0;
const stars       = document.querySelectorAll('.star');
const submitArea  = document.getElementById('submit-area');
const skipMsg     = document.getElementById('skip-message');

stars.forEach(star => {
    star.addEventListener('click', () => {
        selectedScore = parseInt(star.dataset.score, 10);
        stars.forEach((s, idx) => s.classList.toggle('active', idx < selectedScore));
        submitArea.style.display = 'block';
        skipMsg.style.display    = 'none';
    });
});

document.getElementById('btn-skip').addEventListener('click', () => {
    submitArea.style.display = 'none';
    skipMsg.style.display    = 'block';
});
```

### Read-only star display (for already-rated state)

```html
{% if already_rated and current_score %}
<div class="stars-row stars-readonly">
    {% for i in range(1, 6) %}
    <span class="star {% if i <= current_score %}active{% endif %}">★</span>
    {% endfor %}
</div>
{% endif %}
```

---

## Phase P08: Public Rating Routes

**File**: `routes/public_routes.py`

```python
@public_bp.route('/rate/<token>', methods=['GET'])
def appointment_rate_view(token):
    appt = AppointmentRepository().get_by_rating_token(token)
    if not appt:
        return render_template('public/rate_invalid.html'), 404

    appt = dict(appt)
    already_rated = appt.get('satisfaction_score') is not None
    client = ClientRepository().get_by_id(appt['client_id'])
    return render_template(
        'public/appointment_rate.html',
        appointment=appt, client=client, token=token,
        already_rated=already_rated,
        current_score=appt.get('satisfaction_score'),
        just_submitted=False,
    )


@public_bp.route('/rate/<token>', methods=['POST'])
def appointment_rate_submit(token):
    repo = AppointmentRepository()
    appt = repo.get_by_rating_token(token)
    if not appt:
        return render_template('public/rate_invalid.html'), 404

    appt = dict(appt)

    # Idempotent guard: already rated → show confirmation, no DB write
    if appt.get('satisfaction_score') is not None:
        return render_template(
            'public/appointment_rate.html',
            appointment=appt, client=None, token=token,
            already_rated=True,
            current_score=appt['satisfaction_score'],
            just_submitted=False,
        )

    try:
        score = int(request.form.get('score', 0))
        if not 1 <= score <= 5:
            raise ValueError('score out of range')
    except (ValueError, TypeError):
        return render_template(
            'public/appointment_rate.html',
            appointment=appt, client=None, token=token,
            already_rated=False, current_score=None,
            error='Nieprawidłowa ocena — wybierz od 1 do 5 gwiazdek.',
            just_submitted=False,
        )

    from datetime import datetime, timezone
    repo.update_rating(
        appointment_id=appt['id'],
        score=score,
        rated_on=datetime.now(timezone.utc),
        rated_by='client',
    )

    AuditRepository().log_event(
        entity_type='appointment', action='CLIENT_RATING',
        entity_id=appt['id'],
        entity_label=f"{appt.get('appointment_date')} — ocena: {score}/5",
        field_name='satisfaction_score',
        old_value=None, new_value=str(score),
        user_id=None, user_name='Klient (SMS)',
    )

    return render_template(
        'public/appointment_rate.html',
        appointment=appt, client=None, token=token,
        already_rated=True, current_score=score, just_submitted=True,
    )
```

No blueprint registration change needed — both routes go into the existing `public_bp`.

---

## Phase P09: App UI — Rating Status Display

**File**: `templates/appointments/view.html`

Add a rating status section below the existing star widget, visible only for completed appointments.

```html
{% if appointment.status == 'completed' %}
<div class="rating-status-block">
    {% if appointment.rating_status == 'scheduled' %}
        <span class="badge badge-info">SMS z prośbą o ocenę — zaplanowany</span>
    {% elif appointment.rating_status == 'sent' %}
        <span class="badge badge-warning">Oczekiwanie na ocenę klienta</span>
    {% elif appointment.rating_status == 'received' %}
        <span class="badge badge-success">Ocena otrzymana</span>
        {% if appointment.rated_on %}
            <small class="text-muted ms-2">
                {{ appointment.rated_on | format_datetime('%d.%m.%Y %H:%M') }}
            </small>
        {% endif %}
    {% endif %}
</div>
{% endif %}
```

**Route that renders `view.html`** (locate the view route in `routes/appointment_routes.py`
or `routes/main_routes.py`): ensure `rating_status`, `rated_on`, `rated_by` are included
in the appointment dict passed to the template. Typically this means adding them to the
`SELECT` in `AppointmentRepository.get_by_id()` or the view route query.

---

## Phase P10: Employee Mobile Status Form + Real-Time Web Notifications

### Overview

The assigned stylist opens `/visit/<employee_token>` on their phone before the visit.
The page is **time-gated**: accessible only when `NOW() >= appointment_start - 30 min`.
Two status transitions are handled by this single route:

| Action button | Pre-condition | New status |
|---------------|--------------|------------|
| "Wizyta rozpoczęta" | status in ('scheduled', 'confirmed') AND within time window | `in_progress` |
| "Wizyta zakończona" | status == 'in_progress' | `completed` |

On submission, the backend writes a `status_change_events` row. The web app polls
this table every 5 s and pops a toast for each new event.

---

### 10a. Employee Mobile Form Template

**New file**: `templates/public/appointment_employee_status.html`

Design matches `appointment_confirm.html` (standalone HTML, inline CSS, Inter font,
420px card, `#f5f5f0` background).

#### States

| `state` | Condition | Content |
|---------|-----------|---------|
| `too_early` | `minutes_until_start > 30` | "Formularz dostępny za X minut" |
| `wrong_status` | status not actionable | "Wizyta ma nieprawidłowy status" |
| `start_visit` | status in ('scheduled','confirmed'), within window | Visit details + "Wizyta rozpoczęta" |
| `end_visit` | status == 'in_progress' | Visit details + "Wizyta zakończona" |
| `already_done` | status in ('completed','cancelled','no_show') | "Wizyta już zakończona" |
| `success` | POST succeeded | "Status zaktualizowany" + new status label |

#### Key HTML sections

```html
<!-- start_visit state -->
{% if state == 'start_visit' %}
<div class="details-block">
    <div class="detail-row">
        <span class="detail-label">Klient</span>
        <span class="detail-value">{{ appointment.first_name }} {{ appointment.last_name }}</span>
    </div>
    <div class="detail-row">
        <span class="detail-label">Godzina</span>
        <span class="detail-value">{{ appointment.start_time | string | truncate(5, True, '') }}</span>
    </div>
</div>
<form method="POST">
    <input type="hidden" name="action" value="start">
    <button class="btn-confirm" type="submit">Wizyta rozpoczęta</button>
</form>
{% endif %}

<!-- end_visit state -->
{% if state == 'end_visit' %}
<div class="details-block"><!-- same detail rows --></div>
<form method="POST">
    <input type="hidden" name="action" value="end">
    <button class="btn-confirm" type="submit">Wizyta zakończona</button>
</form>
{% endif %}

<!-- success state -->
{% if state == 'success' %}
<div class="status-icon">✅</div>
<h1 class="heading">Status zaktualizowany</h1>
<p class="status-message">
    Wizyta oznaczona jako
    <strong>{{ 'W trakcie' if new_status == 'in_progress' else 'Zakończona' }}</strong>.
</p>
<script>
    // Auto-close hint — page has no further action
    setTimeout(() => {
        document.querySelector('.status-message').textContent += ' Możesz zamknąć tę stronę.';
    }, 1500);
</script>
{% endif %}

<!-- too_early state -->
{% if state == 'too_early' %}
<div class="status-icon">⏳</div>
<h1 class="heading">Za wcześnie</h1>
<p class="status-message">
    Formularz będzie dostępny
    {% if minutes_remaining %}za {{ minutes_remaining }} min{% endif %}
    (30 minut przed wizytą).
</p>
{% endif %}
```

---

### 10b. Employee Status Routes

**File**: `routes/public_routes.py`

```python
@public_bp.route('/visit/<token>', methods=['GET'])
def employee_visit_status_view(token):
    appt = AppointmentRepository().get_by_employee_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    appt = dict(appt)
    state, ctx = _employee_visit_state(appt)
    return render_template(
        'public/appointment_employee_status.html',
        appointment=appt, state=state, **ctx,
    )


@public_bp.route('/visit/<token>', methods=['POST'])
def employee_visit_status_submit(token):
    repo = AppointmentRepository()
    appt = repo.get_by_employee_token(token)
    if not appt:
        return render_template('public/confirm_invalid.html'), 404

    appt = dict(appt)
    action = request.form.get('action')  # 'start' | 'end'
    state, ctx = _employee_visit_state(appt)

    # Server-side re-validation (never trust client-only guards)
    if action == 'start' and state != 'start_visit':
        return render_template('public/appointment_employee_status.html',
                               appointment=appt, state=state,
                               error='Akcja niedostępna w bieżącym stanie wizyty.', **ctx)
    if action == 'end' and state != 'end_visit':
        return render_template('public/appointment_employee_status.html',
                               appointment=appt, state=state,
                               error='Akcja niedostępna w bieżącym stanie wizyty.', **ctx)

    old_status = appt['status']
    new_status  = 'in_progress' if action == 'start' else 'completed'

    repo.update_status(appt['id'], new_status)

    # Real-time notification event
    from repositories.appointments.status_change_event_repository import StatusChangeEventRepository
    StatusChangeEventRepository().create(appt['id'], old_status, new_status, 'employee_mobile')

    # Audit log
    AuditRepository().log_event(
        entity_type='appointment', action='STATUS_CHANGED',
        entity_id=appt['id'],
        entity_label=f"{appt.get('appointment_date')} {str(appt.get('start_time',''))[:5]}",
        field_name='status', old_value=old_status, new_value=new_status,
        user_id=None, user_name='Pracownik (mobile)',
    )

    # Trigger post-visit rating SMS when completing
    if new_status == 'completed':
        from routes.appointment_routes import _schedule_post_visit_sms
        _schedule_post_visit_sms(appt['id'])

    appt['status'] = new_status
    return render_template(
        'public/appointment_employee_status.html',
        appointment=appt, state='success', new_status=new_status,
    )


def _employee_visit_state(appt: dict) -> tuple:
    """Return (state_str, context_dict) for the employee visit form."""
    from datetime import datetime
    now        = datetime.now()
    start_time = appt['start_time']
    if hasattr(start_time, 'hour'):
        appt_dt = datetime.combine(appt['appointment_date'], start_time)
    else:
        from datetime import time as _time
        h, m = str(start_time)[:5].split(':')
        appt_dt = datetime.combine(appt['appointment_date'], _time(int(h), int(m)))

    minutes_until = (appt_dt - now).total_seconds() / 60
    status = appt['status']

    if status in ('completed', 'cancelled', 'no_show'):
        return 'already_done', {}
    if status == 'in_progress':
        return 'end_visit', {}
    if status in ('scheduled', 'confirmed', 'pending'):
        if minutes_until > 30:
            return 'too_early', {'minutes_remaining': int(minutes_until - 30)}
        return 'start_visit', {}
    return 'wrong_status', {}
```

**Note**: `_schedule_post_visit_sms` is defined in `appointment_routes.py` (P05).
If circular-import issues arise, move it to `services/sms_service.py` as
`SmsService.schedule_status_triggered_sms('completed', ...)`.

---

### 10c. Real-Time Web Notification Polling

#### Backend polling endpoint

**File**: `routes/appointment_routes.py`

```python
@appointment_bp.route('/appointments/status-events', methods=['GET'])
@login_required
def get_status_change_events():
    """5-second polling endpoint for real-time visit status toast notifications."""
    since_str = request.args.get('since', '')
    try:
        from datetime import datetime, timedelta, timezone
        since = datetime.fromisoformat(since_str) if since_str else \
                datetime.now(timezone.utc) - timedelta(seconds=10)
    except ValueError:
        from datetime import datetime, timedelta, timezone
        since = datetime.now(timezone.utc) - timedelta(seconds=10)

    from repositories.appointments.status_change_event_repository import StatusChangeEventRepository
    from datetime import datetime, timezone
    events = StatusChangeEventRepository().get_since(since)
    return jsonify({
        'events': [dict(e) for e in events],
        'server_time': datetime.now(timezone.utc).isoformat(),
    })
```

URL registered at `/api/appointments/status-events` (verify `appointment_bp` URL prefix
in `app.py` to confirm the full path).

#### Frontend polling JS

**File**: `templates/base.html` (inside `{% block scripts %}` or equivalent footer block)

Only inject when user is authenticated (template context already has `current_user`):

```html
{% if current_user.is_authenticated %}
<style>
.status-toast {
    position: fixed; bottom: 1.5rem; right: 1.5rem;
    background: #1a1a1a; color: white;
    padding: 0.75rem 1.25rem; border-radius: 6px;
    font-size: 0.875rem; z-index: 9999;
    animation: slide-in-right 0.25s ease;
    max-width: 320px; pointer-events: none;
}
@keyframes slide-in-right {
    from { transform: translateX(16px); opacity: 0; }
    to   { transform: translateX(0);    opacity: 1; }
}
</style>
<script>
(function () {
    const STATUS_LABELS = {
        in_progress: 'W trakcie',
        completed:   'Zakończona',
        cancelled:   'Anulowana',
    };
    let lastPoll = new Date().toISOString();

    function pollStatusEvents() {
        fetch('/api/appointments/status-events?since=' + encodeURIComponent(lastPoll))
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (!data) return;
                lastPoll = data.server_time;
                (data.events || []).forEach(evt => {
                    const label = STATUS_LABELS[evt.new_status] || evt.new_status;
                    showStatusToast(`Wizyta — ${evt.client_name}: status → "${label}"`);
                });
            })
            .catch(() => {});  // Non-critical; silence network errors
    }

    function showStatusToast(msg) {
        // Reuse app's existing showToast() if available; fall back to DOM injection
        if (typeof window.showToast === 'function') {
            window.showToast(msg, 'info', 6000);
            return;
        }
        const el = document.createElement('div');
        el.className = 'status-toast';
        el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.3s';
            setTimeout(() => el.remove(), 350);
        }, 5000);
    }

    setInterval(pollStatusEvents, 5000);
})();
</script>
{% endif %}
```

**Why polling over WebSockets**: single-server Flask + APScheduler already running;
polling at 5 s adds ~12 tiny requests/minute per logged-in tab — negligible load.
WebSockets (flask-socketio + gevent) would require changing the WSGI worker model.

---

## Phase P11: SMS Settings UI Extension

**File**: `templates/sms/settings.html` (or equivalent message-type settings template)

For `is_event_triggered = TRUE` types, display `send_delay_minutes` as an editable field
instead of (or alongside) `send_hours_before`:

```html
{% if message_type.is_event_triggered %}
<div class="form-group">
    <label>Opóźnienie wysyłki (minuty)</label>
    <input type="number" name="send_delay_minutes"
           value="{{ message_type.send_delay_minutes }}" min="0" max="1440">
    <small class="hint">0 = natychmiast po zmianie statusu</small>
</div>
{% else %}
<!-- existing send_hours_before field -->
{% endif %}
```

**Route**: `routes/sms_routes.py` — `save_message_type()` already passes `**fields`
through to `SmsMessageTypeRepository.update()`. Verify that `update()` accepts
`send_delay_minutes` — add it to the allowed fields list if there is one.

---

## Risk Notes

| Risk | Mitigation |
|------|-----------|
| Scheduler fires before `sms_events` row committed | Hook runs synchronously in the route handler; row is committed before scheduler next wakes |
| Duplicate SMS if scheduler crashes mid-send | Mark event `sent` atomically; `get_due()` skips already-sent rows on retry |
| `BASE_URL` not set in production | `rate_url` will be broken; add config validation or startup warning |
| Rating form accessed before appointment is `completed` | Token is permanent but SMS only fires post-completion; token alone reveals nothing sensitive |
| SMS sent to wrong phone after client phone number change | `send()` always fetches current phone from `clients` table at send time (existing behaviour) |
| Employee taps "Zakończona" after admin already set it via web UI | Server-side re-validation in `_employee_visit_state()` returns `already_done`; no double-write |
| Employee token shared or leaked | Token is UUID (128-bit entropy); only controls status updates for one appointment; no PII exposed |
| `status_change_events` grows unbounded | Add a periodic cleanup job (e.g. DELETE WHERE created_at < NOW() - INTERVAL '7 days') — implement alongside the scheduler |

---

## Full Acceptance Criteria

- [ ] `alembic upgrade head` succeeds; `alembic downgrade -1` reverts cleanly
- [ ] Changing appointment status to `completed` inserts an `sms_events` row with
      `scheduled_at = NOW() + 30min` and `event_type = 'post_visit_message'`
- [ ] `appointment.rating_status` becomes `'scheduled'` immediately on status change
- [ ] Scheduler (15-min tick) picks up due `sms_events`, sends SMS, marks `status='sent'`
- [ ] `appointment.rating_status` becomes `'sent'` after SMS dispatch
- [ ] Client opens `/rate/<token>` — sees 5 grey stars, no submit button
- [ ] Tapping star N turns stars 1–N yellow; "Prześlij ocenę" + "Nie teraz" appear
- [ ] "Nie teraz" hides buttons and shows soft decline message (no DB write)
- [ ] "Prześlij ocenę" POSTs → updates `satisfaction_score`, `rated_on`, `rated_by='client'`,
      `rating_status='received'`
- [ ] Re-opening already-rated link shows confirmation state, no double-rating possible
- [ ] Appointment view shows correct chip: `scheduled` / `oczekiwanie` / `ocena otrzymana`
- [ ] Cancelling an appointment sets pending `sms_events` status to `'cancelled'`
- [ ] `send_delay_minutes` for `post_visit_message` is editable in SMS settings and
      respected (changing to 60 min delays SMS by 60 min)
- [ ] All existing SMS reminder tests still pass
- [ ] `{rate_url}` in template text renders correctly with `BASE_URL` prefix
- [ ] Employee opens `/visit/<employee_token>` more than 30 min before start → sees "Za wcześnie" state
- [ ] Employee opens link within 30 min of start, status = 'confirmed' → sees "Wizyta rozpoczęta" button
- [ ] Tapping "Wizyta rozpoczęta" → status updates to `in_progress` in DB
- [ ] After `in_progress`, same link shows "Wizyta zakończona" button
- [ ] Tapping "Wizyta zakończona" → status updates to `completed`, triggers `post_visit_message` SMS scheduling
- [ ] Both actions write a row to `status_change_events` with `triggered_by='employee_mobile'`
- [ ] Web app (admin, logged-in) polls `/api/appointments/status-events` and shows toast within 5–10 s of employee tap
- [ ] Server-side re-validation blocks replayed POST if state has changed between GET and POST
- [ ] Already-completed appointment shows "Wizyta już zakończona" (no action buttons)

---

## Files Created / Modified Summary

| Action | File |
|--------|------|
| **Create** | `alembic/versions/u6v7w8x9y0z1_add_visit_rating_and_sms_events.py` |
| **Modify** | `database/models.py` |
| **Modify** | `repositories/appointments/appointment_repository.py` |
| **Create** | `repositories/sms/sms_event_repository.py` |
| **Modify** | `repositories/sms/sms_repository.py` |
| **Modify** | `services/sms_service.py` |
| **Modify** | `routes/appointment_routes.py` |
| **Modify** | `routes/public_routes.py` |
| **Modify** | `scheduler.py` |
| **Create** | `templates/public/appointment_rate.html` |
| **Create** | `templates/public/rate_invalid.html` |
| **Create** | `templates/public/appointment_employee_status.html` |
| **Create** | `repositories/appointments/status_change_event_repository.py` |
| **Modify** | `templates/appointments/view.html` |
| **Modify** | `templates/base.html` (polling JS + toast CSS) |
| **Modify** | `templates/sms/settings.html` (or equivalent) |
