fc# Implementation Plan — Employee Absence Management

**Source spec:** `C:\Projects\faktura_scanner_flask\new_feature_employees-absence-handling.txt`
**Target codebase:** `C:\Projects\faktura_scanner_flask` (Flask, raw psycopg2, dataclass models, Jinja2 + Refined Minimal CSS)
**Date:** 2026-05-09

---

## 1. Context

The salon app currently has:
- A simple `employee_time_off` table (migration `001_`) with only `start_date`, `end_date`, `reason` (VARCHAR), `status` pending/approved/denied. **It is unused by the application code** (no repository, no UI, no service references it — confirmed via grep).
- An `appointments` table with mature conflict-detection logic (`repositories/appointments/appointment_repository.py:296-382`) and a public client booking flow at `/booking`.
- No supervisor↔employee hierarchy.
- No multi-tab page convention in the templates.

We need a complete employee-absence subsystem that lets:
1. **Employees with active user accounts** submit day-off / time-slot absence requests, pick a category from an admin-managed list, and select an approver from THEIR linked supervisors.
2. **Supervisors** review their team's requests (accept / reject with reason), manually create absences (sick-leave / "L4"), and (admins only) manage categories — all from a single "Nieobecności" page with three tabs.
3. **Approved absences** behave exactly like appointment slots in the calendar: same conflict detection, same edit-form-with-yellow-glow conflict resolution flow, same exclusion from public client booking.

**Outcome:** every absence is a first-class scheduling entity that protects the employee's time from double-booking, and the salon has a clean audit trail (who requested, who approved/rejected, when, why).

---

## 2. Confirmed Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Drop `employee_time_off`** in the new migration; create richer `employee_absences` from scratch | Pre-production codebase per `CLAUDE.md` & memory; old table is unused |
| D2 | **Many-to-many supervisor model** via new `employee_supervisors` join table | Spec says "linked supervisors" (plural); join table is the only shape that fits |
| D3 | **JS-driven tabs in a single route** `/absences` (URL hash `#requests`, `#sick-leave`, `#categories`) | Matches spec's "multi-tab page view" wording; introduces a reusable `.refined-tabs` pattern to the codebase |
| D4 | **One responsive page** `/my-absences` (sidebar + standalone via mobile bookmark) | Single source of truth; design guide already mandates responsive layouts |
| D5 (auto) | **`date_to = date_from`** for time-slot absences (never NULL) | Simplifies range queries and conflict joins; one CHECK constraint covers both modes |
| D6 (auto) | **Sick-leave manually created by a supervisor is auto-approved** with `approver_id = creator's employee_id`, `responded_at = requested_at = now()` | Supervisor's intent is unambiguous; no second hop needed |
| D7 (auto) | **Conflict-highlight target fields** in appointment edit form: `appointment_date`, `start_time`, `employee_id` | Those are the three columns the absence overlap depends on |
| D8 (auto) | **Employee may edit/cancel their own request only while `status = 'pending'`** | Standard request-lifecycle UX; rejected/approved are immutable history |
| D9 (auto) | **New `absences` module** added to `MODULE_PERMISSIONS` for full management; supervisor access is a separate runtime check via `is_supervisor()` helper | Module decorator is too coarse — a stylist-supervisor must NOT see categories tab |
| D10 (auto) | **Conflict resolution modal** lists conflicting appointments with edit-icon → modal closes → `/appointments/<id>/edit?highlight=date,time` opens with yellow glow on those inputs | Mirrors spec line 21 verbatim |

---

## 3. Database Schema

**Migration file:** `C:\Projects\faktura_scanner_flask\alembic\versions\n8o9p0q1r2s3_create_absence_management_tables.py`
- `revision = 'n8o9p0q1r2s3'`
- `down_revision = 'm7n8o9p0q1r2'` (latest existing)

### 3.1 Drop legacy

```python
op.drop_index('idx_time_off_dates', table_name='employee_time_off')
op.drop_index('idx_time_off_employee', table_name='employee_time_off')
op.drop_table('employee_time_off')
```

### 3.2 `absence_categories` (lookup table for dropdown)

```python
op.create_table(
    'absence_categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('absence_full_day', sa.Boolean(), nullable=False, server_default='1'),
    sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', name='uq_absence_categories_name'),
)
op.create_index('idx_absence_categories_is_deleted', 'absence_categories', ['is_deleted'])
```

**Seed rows (in same migration):**
- `('Zwolnienie lekarskie (L4)', 'Sick leave / L4', true)` — required first row per spec
- `('Urlop wypoczynkowy', 'Annual leave', true)`
- `('Urlop na żądanie', 'On-demand leave', true)`
- `('Wyjście prywatne', 'Private time-slot', false)` — example time-slot category

### 3.3 `employee_supervisors` (many-to-many hierarchy)

```python
op.create_table(
    'employee_supervisors',
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('supervisor_employee_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    sa.PrimaryKeyConstraint('employee_id', 'supervisor_employee_id'),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['supervisor_employee_id'], ['employees.id'], ondelete='CASCADE'),
    sa.CheckConstraint('employee_id != supervisor_employee_id', name='check_no_self_supervision'),
)
op.create_index('idx_supervisors_employee', 'employee_supervisors', ['employee_id'])
op.create_index('idx_supervisors_supervisor', 'employee_supervisors', ['supervisor_employee_id'])
```

### 3.4 `employee_absences` (the main table)

```python
op.create_table(
    'employee_absences',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('date_from', sa.Date(), nullable=False),
    sa.Column('date_to', sa.Date(), nullable=False),  # = date_from for time slots (D5)
    sa.Column('time_from', sa.Time(), nullable=True),
    sa.Column('time_to', sa.Time(), nullable=True),
    sa.Column('approver_id', sa.Integer(), nullable=True),  # employees.id of approver
    sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
    sa.Column('rejection_reason', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('source', sa.String(20), nullable=False, server_default='request'),  # 'request' | 'manual'
    sa.Column('requested_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    sa.Column('responded_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),  # users.id
    sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
    sa.PrimaryKeyConstraint('id'),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['category_id'], ['absence_categories.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['approver_id'], ['employees.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')",
                       name='check_absence_status'),
    sa.CheckConstraint("source IN ('request', 'manual')", name='check_absence_source'),
    sa.CheckConstraint('date_to >= date_from', name='check_absence_date_order'),
    sa.CheckConstraint(
        '(time_from IS NULL AND time_to IS NULL) OR '
        '(time_from IS NOT NULL AND time_to IS NOT NULL AND time_to > time_from)',
        name='check_absence_time_order'),
    sa.CheckConstraint(
        "status != 'rejected' OR rejection_reason IS NOT NULL",
        name='check_rejection_reason_required'),
)
op.create_index('idx_absences_employee_dates', 'employee_absences', ['employee_id', 'date_from', 'date_to'])
op.create_index('idx_absences_status', 'employee_absences', ['status'])
op.create_index('idx_absences_approver', 'employee_absences', ['approver_id'])
op.create_index('idx_absences_is_deleted', 'employee_absences', ['is_deleted'])
```

`downgrade()` reverses in opposite order: drop indexes & `employee_absences` → drop `employee_supervisors` → drop `absence_categories` → recreate `employee_time_off` (paste original DDL from `001_`).

---

## 4. Models (`database/models.py` additions)

Add after the existing `EmployeeService` dataclass:

```python
@dataclass
class AbsenceCategory:
    """Słownikowa kategoria nieobecności (urlop, L4, wyjście prywatne, ...)."""
    name: str
    description: Optional[str] = None
    absence_full_day: bool = True
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)


@dataclass
class EmployeeSupervisor:
    """Powiązanie pracownik → przełożony (M:M)."""
    employee_id: int
    supervisor_employee_id: int
    created_at: Optional[datetime] = field(default_factory=datetime.now)


@dataclass
class EmployeeAbsence:
    """Wniosek / rejestracja nieobecności pracownika."""
    employee_id: int
    category_id: int
    date_from: date
    date_to: date
    time_from: Optional[time] = None
    time_to: Optional[time] = None
    approver_id: Optional[int] = None
    status: str = 'pending'  # pending | approved | rejected | cancelled
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None
    source: str = 'request'  # request | manual
    requested_at: Optional[datetime] = field(default_factory=datetime.now)
    responded_at: Optional[datetime] = None
    created_by: Optional[int] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)
```

---

## 5. Repositories

### 5.1 Create new directory `repositories/absences/`

| File | Class | Key methods |
|---|---|---|
| `repositories/absences/__init__.py` | — | empty |
| `repositories/absences/absence_category_repository.py` | `AbsenceCategoryRepository(BaseRepository)` | `list_active()`, `list_with_deleted()`, `get_by_id(id)`, `create(cat)`, `update(id, cat)`, `soft_delete(id)`, `restore(id)` |
| `repositories/absences/absence_repository.py` | `AbsenceRepository(BaseRepository)` | `create()`, `get_by_id()`, `update()`, `soft_delete()`, `list_for_employee(employee_id, status_in=None)`, `list_for_approver(approver_id, status_in=None)`, `list_all(filters)`, **`check_absence_conflicts(employee_id, date_from, date_to, time_from=None, time_to=None, exclude_id=None) -> list`**, **`get_overlapping_appointments(employee_id, date_from, date_to, time_from=None, time_to=None) -> list`**, `respond(id, status, approver_id, rejection_reason=None)` |
| `repositories/absences/employee_supervisor_repository.py` | `EmployeeSupervisorRepository` | `list_supervisors_for(employee_id) -> list[Employee]`, `list_subordinates_for(supervisor_employee_id) -> list[Employee]`, `is_supervisor(employee_id) -> bool`, `add_link(emp_id, sup_id)`, `remove_link(emp_id, sup_id)` |

`_COLUMNS` tuple convention from `EmployeeRepository._COLUMNS` is mirrored.

### 5.2 Conflict-check SQL (the heart of integration)

Inside `AbsenceRepository.check_absence_conflicts`, mirror the appointment overlap pattern from `repositories/appointments/appointment_repository.py:296-382`. Critically, this method must check overlap against BOTH approved/pending absences AND active appointments:

```python
def check_absence_conflicts(self, employee_id, date_from, date_to,
                             time_from=None, time_to=None, exclude_id=None):
    """Find existing absences for this employee that overlap the proposed range.

    Full-day absences (time_from IS NULL): conflict if date ranges overlap.
    Time-slot absences (time_from set): conflict only if date ranges overlap
    AND time ranges overlap (and proposed is also a time slot).
    """
    # Standard date-range overlap: existing.date_from <= proposed.date_to
    #                              AND existing.date_to   >= proposed.date_from
    # When BOTH sides are time-slots: also require time_from < proposed.time_to
    #                                                AND time_to   > proposed.time_from
```

`get_overlapping_appointments` runs the equivalent query against the `appointments` table (joined to `services` for display in the conflict modal). Returns rows with id, date, start, end, client name, service name.

### 5.3 Register in `app.py` (lines 137-139 area)

```python
from repositories.absences.absence_category_repository import AbsenceCategoryRepository
from repositories.absences.absence_repository import AbsenceRepository
from repositories.absences.employee_supervisor_repository import EmployeeSupervisorRepository
...
app.absence_category_repo = AbsenceCategoryRepository()
app.absence_repo = AbsenceRepository()
app.supervisor_repo = EmployeeSupervisorRepository()
```

---

## 6. Service Layer

**New file:** `services/absence_service.py` — class `AbsenceService` with:

| Method | Behavior |
|---|---|
| `submit_request(employee_id, category_id, date_from, date_to, time_from, time_to, approver_employee_id, notes)` | Validates: category exists, approver is in employee's linked supervisors list, time fields match category's `absence_full_day` flag, `time_to > time_from`. Creates row with `status='pending'`, `source='request'`. |
| `approve(absence_id, approver_user_id) -> dict` | Verifies approver matches `approver_id` OR is admin/superuser. Calls `get_overlapping_appointments`. If conflicts: returns `{status:'conflict', conflicts:[...]}` and does NOT change status. Otherwise sets status='approved', responded_at=now(). |
| `force_approve(absence_id, approver_user_id)` | Same as approve but skips conflict check (used after supervisor manually resolves conflicts via the modal flow). |
| `reject(absence_id, approver_user_id, rejection_reason)` | Sets status='rejected'. `rejection_reason` is required by DB constraint. |
| `cancel_own(absence_id, employee_user_id)` | Allowed only if `status='pending'` AND requester is the absence's employee. |
| `create_manual(employee_id, category_id, ...)` | Used by supervisors for L4. Auto-status='approved', source='manual', approver_id=creator's employee_id, responded_at=requested_at=now(). Same conflict-check flow as approve. |
| `update_manual(absence_id, ...)` | Edit a manually-created absence (admin/supervisor). Re-runs conflict check unless `force=True`. |
| `soft_delete(absence_id)` | Standard soft delete (admin/supervisor). |
| `list_for_employee(...)`, `list_for_approver(...)`, `list_all(...)` | Thin wrappers over repository with display-friendly joins (employee name, category name, approver name). |

The service depends on `AbsenceRepository`, `AbsenceCategoryRepository`, `EmployeeSupervisorRepository`, `EmployeeRepository`, `UserRepository`. Wire it in `app.py` alongside other services.

### 6.1 Extending the appointments side

Two integration points the service consumes (no schema change to `appointments`):

1. **Public booking** — `routes/booking_routes.py::get_public_slots()` and equivalent. After fetching booked appointments for the date, ALSO fetch approved absences for the employee+date range and add them to the `booked` list with the same shape (`start_time`/`end_time` keys). The existing in-memory overlap loop in `services/appointment_service.py:get_available_slots` (lines 428-489) then transparently excludes those slots.

2. **Admin appointment create/update** — `services/appointment_service.py::create_appointment` (lines 40-125) and `update_appointment` (lines 511-666). After the existing `appt_repo.check_conflicts(...)` call, add `absence_repo.check_absence_conflicts(...)`. If hit, raise `AppointmentError("Konflikt z nieobecnością pracownika ...")`. The existing `force_save=True` override on update should ALSO bypass absence conflicts.

---

## 7. Permissions

**`config/auth_config.py`** — add to `MODULE_PERMISSIONS` dict (line 19-28):

```python
'absences': ['superuser', 'admin'],          # full management view
```

**Add helper at module bottom:**

```python
def is_supervisor(user) -> bool:
    """Return True if the current user's linked employee record is on the
    supervisor side of any employee_supervisors row."""
    if not user or not user.is_authenticated:
        return False
    from repositories.employees.employee_repository import EmployeeRepository
    from repositories.absences.employee_supervisor_repository import EmployeeSupervisorRepository
    emp = EmployeeRepository().get_by_user_id(user.id)
    if not emp:
        return False
    return EmployeeSupervisorRepository().is_supervisor(emp['id'])
```

Routes use:
- `@module_permission_required('absences')` → admin/superuser only (categories CRUD + global list)
- A new lightweight decorator `@absence_management_required` that allows admin/superuser **OR** `is_supervisor(current_user)` → tab #1 + tab #2 actions
- `@login_required` only → `/my-absences` (any logged-in user with linked employee can submit; a runtime check bounces users without a linked employee)

**Inject `is_supervisor` into the context processor** in `app.py` (line 218 region) so sidebar Jinja can show/hide the "Nieobecności" link without a DB query in the template:

```python
return {
    ...
    'user_permissions': user_permissions,
    'is_supervisor': is_supervisor(current_user),
}
```

---

## 8. Routes

**New file:** `routes/absence_routes.py` — blueprint `absence_bp` registered in `app.py:176` after `booking_bp`:

```python
app.register_blueprint(absence_bp)
```

| Method | URL | Handler | Auth |
|---|---|---|---|
| GET | `/my-absences` | `my_absences()` — own list + submit form (responsive) | `@login_required` + has-linked-employee check |
| POST | `/my-absences/submit` | `submit_request()` — Zod-equivalent server-side validation, calls `AbsenceService.submit_request` | `@login_required` |
| POST | `/my-absences/<int:id>/cancel` | `cancel_own_request()` | `@login_required` |
| GET | `/absences` | `management_index()` — renders 3-tab layout, all data injected via Jinja | `@absence_management_required` |
| POST | `/absences/<int:id>/approve` | `approve_request()` — JSON; returns `{status:'approved'}` or `{status:'conflict', conflicts:[...]}` | `@absence_management_required` |
| POST | `/absences/<int:id>/approve/force` | `force_approve()` — used after conflict modal resolution | `@absence_management_required` |
| POST | `/absences/<int:id>/reject` | `reject_request()` — body `{rejection_reason}` | `@absence_management_required` |
| POST | `/absences/manual` | `create_manual()` — supervisor creates L4-style record | `@absence_management_required` |
| PUT | `/absences/<int:id>` | `update_absence()` — only manual-source records | `@absence_management_required` |
| DELETE | `/absences/<int:id>` | `delete_absence()` — soft delete | `@absence_management_required` |
| GET | `/absences/categories` | shares the `/absences` template (renders categories tab) | `@module_permission_required('absences')` |
| POST | `/absences/categories` | `create_category()` | `@module_permission_required('absences')` |
| PUT | `/absences/categories/<int:id>` | `update_category()` | `@module_permission_required('absences')` |
| DELETE | `/absences/categories/<int:id>` | `delete_category()` — soft delete | `@module_permission_required('absences')` |

JSON endpoints follow the existing `{success: bool, data?, error?}` shape used by `routes/appointment_routes.py`.

---

## 9. Templates

**New directory:** `templates/absences/`

| File | Purpose | Extends |
|---|---|---|
| `templates/absences/management.html` | Supervisor 3-tab page | `base.html` |
| `templates/absences/my.html` | Employee responsive submit + own list | `base.html` (responsive — sidebar collapses on mobile) |
| `templates/absences/_partials/requests_table.html` | Tab #1 partial — pending/responded requests with accept/reject icons | included |
| `templates/absences/_partials/manual_table.html` | Tab #2 partial — manually-created absences list + "Nowy wpis" button | included |
| `templates/absences/_partials/categories_table.html` | Tab #3 partial — categories CRUD (admin only — `{% if user_permissions.absences %}` gate inside the tab) | included |
| `templates/absences/_partials/submit_form.html` | The request submission form (used by `my.html` and admin "manual create") | included |
| `templates/absences/_partials/conflict_modal.html` | Modal showing conflicting appointments table with edit-icon → emits a JS event | included |

### 9.1 Tabs implementation (`management.html`)

Adds two reusable CSS components to the design system:

```html
<div class="refined-tabs" role="tablist">
  <button class="refined-tab active" data-tab="requests" role="tab">
    Wnioski <span class="tab-count">{{ pending_count }}</span>
  </button>
  <button class="refined-tab" data-tab="manual" role="tab">L4 (manualnie)</button>
  {% if user_permissions.absences %}
  <button class="refined-tab" data-tab="categories" role="tab">Kategorie</button>
  {% endif %}
</div>
<div id="tab-requests" class="tab-panel" role="tabpanel">{% include '...' %}</div>
<div id="tab-manual" class="tab-panel hidden" role="tabpanel">{% include '...' %}</div>
{% if user_permissions.absences %}
<div id="tab-categories" class="tab-panel hidden" role="tabpanel">{% include '...' %}</div>
{% endif %}
```

CSS: `.refined-tabs` flex row, 1px bottom border under inactive tabs; `.refined-tab.active` gets `--color-ink` underline (2px), `.tab-count` is a 1px-radius badge using `.status-badge` color tokens. Live in template `<style>` block (matching guide convention).

### 9.2 Yellow-glow conflict highlight (`templates/appointments/edit.html`)

Add CSS in the existing `<style>` block:

```css
.conflict-highlight {
  border-color: #fbbf24 !important;
  box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.25),
              0 0 12px rgba(251, 191, 36, 0.45);
  transition: box-shadow 0.3s ease;
}
```

Add JS at template bottom:

```javascript
const params = new URLSearchParams(location.search);
const fields = (params.get('highlight') || '').split(',').filter(Boolean);
const map = { date: 'appt-date', time: 'appt-time', employee: 'appt-employee' };
fields.forEach(f => document.getElementById(map[f])?.classList.add('conflict-highlight'));
```

### 9.3 Sidebar update (`templates/components/sidebar.html`)

**Line 21** — extend `zarzadzanie_active` list:

```jinja2
{% set zarzadzanie_active = request.endpoint in [
    'main.employees_list', 'main.services_list',
    'main.formy_zatrudnienia_list', 'main.service_categories_list',
    'absence.management_index', 'absence.my_absences'
] %}
```

**Lines 79-95** — add new `sidebar_link` calls. Two links may appear depending on user:

```jinja2
{% if is_supervisor or user_permissions.absences %}
{{ sidebar_link(
    url_for('absence.management_index'), 'Nieobecności',
    'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
    request.endpoint == 'absence.management_index') }}
{% endif %}
{# Self-service link — visible to any user whose user.id maps to an active employee. #}
{% if current_user.is_authenticated and has_linked_employee %}
{{ sidebar_link(
    url_for('absence.my_absences'), 'Moje nieobecności',
    'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2',
    request.endpoint == 'absence.my_absences') }}
{% endif %}
```

`has_linked_employee` is added to the context processor next to `is_supervisor`.

### 9.4 Submit form fields (`_partials/submit_form.html`)

Plain HTML using `.refined-input/select/label` classes. Behavior:

- `<select name="category_id">` — populated from `app.absence_category_repo.list_active()`.
- On category change, JS reads `data-full-day` attribute on the `<option>` and shows/hides:
  - if `full_day=true` → show `date_from` + `date_to`; hide `time_from`, `time_to`
  - if `full_day=false` → show `date_from` (label "Data nieobecności") + `time_from`, `time_to`; force `date_to = date_from` on submit
- `<select name="approver_id">` — populated from `supervisor_repo.list_supervisors_for(current_employee.id)`. If empty, render an inline warning ("Skontaktuj się z administratorem — brak przypisanego przełożonego.") and disable submit.
- CSRF: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` (Flask-WTF mounted globally).

---

## 10. Calendar Rendering of Absences

**File:** `templates/appointments/calendar.html`

1. Add a CSS class `.absence-block` next to existing `.appointment-block` styles:

   ```css
   .absence-block {
       border-left: 4px solid var(--color-ink-subtle);
       background: repeating-linear-gradient(
           45deg,
           rgba(138, 138, 138, 0.06),
           rgba(138, 138, 138, 0.06) 6px,
           rgba(138, 138, 138, 0.12) 6px,
           rgba(138, 138, 138, 0.12) 12px
       );
       opacity: 0.85;
       cursor: not-allowed;
   }
   ```

2. The calendar route (already in the project — fetches appointments for the visible window) must ALSO fetch approved absences for the same window via `absence_repo.list_all(status='approved', date_window=...)` and merge into the events array with `type='absence'`.

3. The Jinja loop that renders blocks branches: `{% if event.type == 'absence' %}<div class="absence-block" title="{{ event.category_name }}">...</div>{% endif %}`.

---

## 11. JavaScript

**New file:** `static/js/absences.js` — single module, no build step:

```javascript
const Absences = {
  initTabs() { /* hash-driven tab switching, syncs location.hash */ },
  initSubmitForm() { /* toggles full-day vs time-slot fields */ },
  approve(id) {
    fetch(`/absences/${id}/approve`, {method:'POST', ...}).then(r => r.json()).then(res => {
      if (res.status === 'conflict') {
        Absences.showConflictModal(id, res.conflicts);
      } else {
        Notifications.success('Wniosek zatwierdzony');
        location.reload();
      }
    });
  },
  reject(id) { /* opens modal with rejection_reason textarea */ },
  showConflictModal(absenceId, conflicts) {
    Modals.show({
      title: 'Konflikty z wizytami klientów',
      content: /* table with edit icons */,
      buttons: [
        { text: 'Anuluj', type: 'secondary', onClick: (e, ov) => Modals.close(ov) },
        { text: 'Zatwierdź mimo to', type: 'danger', onClick: () => fetch(`/absences/${absenceId}/approve/force`, ...) }
      ]
    });
    // Each edit icon: closes modal, navigates to /appointment/<id>/edit?highlight=date,time,employee
  }
};
document.addEventListener('DOMContentLoaded', () => {
  Absences.initTabs();
  Absences.initSubmitForm();
});
```

Reuses existing `Modals` (`static/js/modals.js`) and `Notifications` (`static/js/notifications.js`) — no changes to those files.

---

## 12. Implementation Phases

Sized so each phase is independently mergeable & testable.

### Phase 1 — Schema + Models + Repositories (no UI)
- Migration `n8o9p0q1r2s3_create_absence_management_tables.py` (DROP + 3 new tables + seed)
- Add 3 dataclasses to `database/models.py`
- Create `repositories/absences/` (3 files)
- Wire repos in `app.py`
- **Verify:** `alembic upgrade head` succeeds; `alembic downgrade -1` succeeds; quick Python REPL check of `app.absence_repo.check_absence_conflicts(...)` against seeded fixtures.

### Phase 2 — Service Layer + Conflict Integration
- Create `services/absence_service.py`
- Wire into `app.py`
- Modify `services/appointment_service.py` create/update flows to call `absence_repo.check_absence_conflicts(...)`
- Modify `routes/booking_routes.py` public slots endpoint to merge approved absences into `booked` list
- **Verify:** unit-test the service against an in-memory fixture set covering: full-day overlap, time-slot overlap, no-overlap, exclude_id case; a manual test in the browser that public booking hides times that fall inside an approved absence.

### Phase 3 — Routes + Permissions + Sidebar
- Create `routes/absence_routes.py` (all 14 endpoints)
- Update `config/auth_config.py` (MODULE_PERMISSIONS + `is_supervisor` helper + `absence_management_required` decorator)
- Update `app.py` context processor (`is_supervisor`, `has_linked_employee`)
- Update `templates/components/sidebar.html` (line 21 + nav links)
- Register `absence_bp` in `app.py:176`
- **Verify:** sidebar shows correct links for: superuser, admin, supervisor (stylist who is supervisor of someone), regular stylist (only "Moje nieobecności"), receptionist with no employee link (no link).

### Phase 4 — Templates: Submit + Management 3-tab
- `templates/absences/my.html` + submit form partial
- `templates/absences/management.html` + 3 tab partials
- `static/js/absences.js`
- Hook conflict modal up to existing `Modals` system
- **Verify:** end-to-end happy path — stylist submits → supervisor sees in tab 1 → approves → row gone from pending list → calendar shows the gray-striped block.

### Phase 5 — Calendar + Conflict Resolution Flow
- Update `templates/appointments/calendar.html` to render `.absence-block` events
- Update calendar data endpoint to merge absences
- Add `.conflict-highlight` CSS + URL-param JS to `templates/appointments/edit.html`
- Wire conflict modal "edit appointment" icons to navigate with `?highlight=...`
- **Verify:** create appointment that overlaps a future absence → server returns conflict error; supervisor approves an absence whose day has booked appointments → conflict modal lists them → click edit icon → appointment edit form opens with date/time inputs glowing yellow.

---

## 13. Verification Plan (final acceptance)

Run after Phase 5 completes. All flows manual unless otherwise noted.

| Flow | Steps | Expected |
|---|---|---|
| Migration | `alembic upgrade head` then `alembic downgrade base` then upgrade again | No errors |
| Stylist submits full-day | Login as stylist, /my-absences, pick "Urlop wypoczynkowy", date 2026-06-01..03, supervisor=Anna | Row in own list with status `pending` |
| Supervisor approves | Login as Anna, /absences#requests, click ✓ | Row moves to "responded"; calendar shows striped block on those 3 days |
| Stylist submits time-slot | Pick "Wyjście prywatne", date 2026-06-10, 13:30–15:00, supervisor=Anna | Row with `time_from/to` populated |
| Conflict on approval | Pre-create an appointment 14:00–15:00 on 2026-06-10; supervisor approves the time-slot above | Conflict modal lists the appointment; rejecting "Force" leaves status pending |
| Force approve flow | Same scenario, click "Zatwierdź mimo to" → modal closes → status approved | Calendar shows BOTH the absence and the conflicting appointment side-by-side |
| Edit conflicting appointment | From conflict modal, click pencil on a conflict row | Redirects to `/appointment/<id>/edit?highlight=date,time,employee`; date and time inputs glow yellow |
| Public booking exclusion | As anonymous browser, /booking, pick the same employee on 2026-06-01 | Time slots inside the approved absence are not offered |
| Reject without reason | Supervisor rejects without filling textarea | Form blocks submit (server returns 400 due to `check_rejection_reason_required`) |
| Cancel own pending | Stylist cancels their own pending request | Status `cancelled`, no longer in supervisor's list |
| Cannot edit responded | Stylist tries to edit an approved request | UI hides edit; direct POST returns 403 |
| Manual L4 (supervisor) | Supervisor /absences#manual, creates L4 for stylist, no approver dropdown | Status `approved`, source `manual`, immediately on calendar |
| Categories CRUD (admin) | Admin /absences#categories, create "Urlop bezpłatny" full_day=true | Appears in stylist's submit dropdown after page reload |
| Categories CRUD (supervisor non-admin) | Supervisor (stylist) opens /absences | Categories tab is NOT rendered |
| Soft delete | Admin deletes a manual absence | Row hidden from list but row still in DB with `is_deleted=true` |

Run `python -m pytest tests/` if a test suite exists for the project (status TBD — none seen during exploration).

Final smoke test: `pnpm verify`-equivalent for this Flask project = manual smoke + linter pass; if a CI script exists in the repo's existing conventions, run it.

---

## 14. Out of Scope (explicit non-goals)

- Email/SMS notifications when a request is submitted/approved/rejected (can be added later atop `services/email_service.py`).
- Calendar drag-and-drop creation of absences (admins use the form; the modal is read-only on calendar).
- Bulk approval / rejection.
- Absence balance tracking (e.g., "26 vacation days/year" counter) — categories are unmetered.
- Public-facing iCal feed of absences.
- Mobile push notifications.
- Role-graph migration to make "supervisor" a first-class role rather than a relational attribute.

---

## 15. Critical Files to Touch (quick scan)

**New:**
- `alembic/versions/n8o9p0q1r2s3_create_absence_management_tables.py`
- `repositories/absences/{__init__.py, absence_category_repository.py, absence_repository.py, employee_supervisor_repository.py}`
- `services/absence_service.py`
- `routes/absence_routes.py`
- `templates/absences/{management.html, my.html, _partials/*.html}`
- `static/js/absences.js`

**Modify:**
- `database/models.py` — append 3 dataclasses
- `app.py` — repository wiring (~line 139), service wiring (~line 147), blueprint register (~line 176), context processor (~line 218)
- `config/auth_config.py` — add `'absences'` to `MODULE_PERMISSIONS`, add `is_supervisor()` helper, add `absence_management_required` decorator
- `templates/components/sidebar.html` — line 21 endpoint list, lines 79-95 nav links
- `templates/appointments/calendar.html` — add `.absence-block` CSS + render branch
- `templates/appointments/edit.html` — add `.conflict-highlight` CSS + URL-param JS
- `services/appointment_service.py` — call `absence_repo.check_absence_conflicts` in `create_appointment` and `update_appointment`
- `routes/booking_routes.py` — merge approved absences into `booked` list in public slots endpoint

**No changes:**
- `static/js/modals.js`, `static/js/notifications.js` — reused as-is
- `repositories/base_repository.py` — soft-delete pattern reused unchanged
- `repositories/appointments/appointment_repository.py` — left untouched; absence integration lives in service layer
