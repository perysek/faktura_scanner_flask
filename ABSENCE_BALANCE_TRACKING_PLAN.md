# Absence Balance Tracking — Implementation Plan

**Date:** 2026-05-12  
**Status:** Ready for implementation  
**Feature branch:** invoices-app  
**Author:** Planning session (absence-balance-tracking)

---

## 1. Feature Summary

Add a balance-tracking layer on top of the existing absence management system. Each absence category can be marked as tracked (`is_tracked=TRUE`), with configurable reset periods and per-employee limits. Balance is computed dynamically from approved absences within the current period. The system warns when approaching limits and blocks (role-dependent) when limits would be exceeded.

---

## 2. Confirmed Design Decisions

| Decision | Choice |
|---|---|
| Limit breach for employee self-submission | **Hard block** (HTTP 400) |
| Limit breach for supervisor manual entry | **Soft warning** (returns `balance_warning` in JSON, does not block) |
| Limit scope | **Category default + per-employee override** |
| Time-slot unit | **Hours** (computed from `time_to - time_from`) |
| Full-day unit | **Days** (computed as `date_to - date_from + 1`) |

---

## 3. Project Context (for empty-context sessions)

### Tech stack
- Python Flask + Jinja2 templates, PostgreSQL via psycopg2, no ORM
- Repositories: raw SQL, `get_db_connection()` context manager returning dict-cursor rows
- Services: business logic, inject repositories via constructor
- Models: Python `@dataclass` in `database/models.py`
- Alembic for schema migrations in `alembic/versions/`
- Template design: "refined minimal" (2px radius, Inter 300/400/500, CSS custom properties, Material Icons + SVG heroicons)
- Toast system: `Notifications.success/error/warning(msg)` from `static/js/notifications.js`
- Confirmation modals: `Modals.confirm({ title, message, confirmText, onConfirm })` from `static/js/modals.js`
- Audit log: `AuditRepository.log_event(entity_type, action, entity_id, entity_label, field_name, old_value, new_value, user_id, user_name)`
- Soft delete pattern: `is_deleted BOOLEAN DEFAULT FALSE` + `deleted_at TIMESTAMP` columns
- Auth decorators: `@login_required`, `@module_permission_required('module_name')`, `@absence_management_required`
- Repositories registered in `app.py` as `app.<repo_name>`, accessed via `current_app.<repo_name>`

### Key existing tables
- `absence_categories(id, name, description, absence_full_day, is_deleted, deleted_at, created_at, updated_at)`
- `employee_absences(id, employee_id, category_id, date_from, date_to, time_from, time_to, approver_id, status, rejection_reason, notes, source, requested_at, responded_at, created_by, is_deleted, deleted_at, created_at, updated_at)`
- `employees(id, first_name, last_name, …)`
- `users(id, email, full_name, role, …)`
- `audit_log(id, entity_type, entity_id, entity_label, action, field_name, old_value, new_value, user_id, user_name, changed_at)`

### Existing absence category seeds
```
id=1 'Zwolnienie lekarskie (L4)' — full_day=TRUE
id=2 'Urlop wypoczynkowy'        — full_day=TRUE
id=3 'Urlop na żądanie'          — full_day=TRUE
id=4 'Wyjście prywatne'          — full_day=FALSE (time-slot)
```

---

## 4. Database Schema Changes

### Migration file
**Path:** `alembic/versions/o9p0q1r2s3t4_add_absence_balance_tracking.py`  
**Revision ID:** `o9p0q1r2s3t4`  
**Down-revision:** `n8o9p0q1r2s3`

### 4a. New columns on `absence_categories`

```sql
ALTER TABLE absence_categories
  ADD COLUMN IF NOT EXISTS is_tracked           BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS count_period         VARCHAR(20) NOT NULL DEFAULT 'yearly',
  ADD COLUMN IF NOT EXISTS resets_at            INTEGER DEFAULT 1,
  ADD COLUMN IF NOT EXISTS rolling_days         INTEGER,
  ADD COLUMN IF NOT EXISTS warning_threshold_pct FLOAT NOT NULL DEFAULT 0.80,
  ADD COLUMN IF NOT EXISTS default_max_value    FLOAT NOT NULL DEFAULT 0.0;

ALTER TABLE absence_categories
  ADD CONSTRAINT chk_count_period
    CHECK (count_period IN ('yearly', 'monthly', 'rolling')),
  ADD CONSTRAINT chk_resets_at
    CHECK (resets_at IS NULL OR (resets_at >= 1 AND resets_at <= 365)),
  ADD CONSTRAINT chk_warning_threshold
    CHECK (warning_threshold_pct >= 0.0 AND warning_threshold_pct <= 1.0),
  ADD CONSTRAINT chk_default_max_value
    CHECK (default_max_value >= 0.0),
  ADD CONSTRAINT chk_rolling_days
    CHECK (rolling_days IS NULL OR rolling_days > 0);

-- Seed: enable tracking for 'Urlop wypoczynkowy' with default 26 days
UPDATE absence_categories
SET is_tracked = TRUE,
    count_period = 'yearly',
    resets_at = 1,
    default_max_value = 26.0,
    warning_threshold_pct = 0.80
WHERE name = 'Urlop wypoczynkowy';

-- Seed: enable tracking for 'Urlop na żądanie' with default 4 days
UPDATE absence_categories
SET is_tracked = TRUE,
    count_period = 'yearly',
    resets_at = 1,
    default_max_value = 4.0,
    warning_threshold_pct = 0.80
WHERE name = 'Urlop na żądanie';

-- Seed: enable tracking for 'Wyjście prywatne' with default 16 hours/month
UPDATE absence_categories
SET is_tracked = TRUE,
    count_period = 'monthly',
    resets_at = 1,
    default_max_value = 16.0,
    warning_threshold_pct = 0.75
WHERE name = 'Wyjście prywatne';
```

**`resets_at` semantics:**
- `count_period='yearly'`: day-of-year (1 = Jan 1st, 32 = Feb 1st, …). Formula: `date(today.year, 1, 1) + timedelta(days=resets_at - 1)`
- `count_period='monthly'`: day-of-month (1–28). If today.day >= resets_at → period starts this month; else previous month
- `count_period='rolling'`: `resets_at` is ignored; use `rolling_days` instead

### 4b. New table `employee_absence_limits`

```sql
CREATE TABLE employee_absence_limits (
    id           SERIAL PRIMARY KEY,
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    category_id  INTEGER NOT NULL REFERENCES absence_categories(id) ON DELETE CASCADE,
    max_value    FLOAT NOT NULL,            -- days (full_day) or hours (time-slot)
    notes        TEXT,
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at   TIMESTAMP,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_max_value CHECK (max_value >= 0.0)
);

CREATE UNIQUE INDEX uq_absence_limits_active
    ON employee_absence_limits(employee_id, category_id)
    WHERE is_deleted = FALSE;

CREATE INDEX idx_absence_limits_employee ON employee_absence_limits(employee_id);
CREATE INDEX idx_absence_limits_category ON employee_absence_limits(category_id);
```

### 4c. New table `absence_balance_adjustments`

```sql
CREATE TABLE absence_balance_adjustments (
    id           SERIAL PRIMARY KEY,
    employee_id  INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    category_id  INTEGER NOT NULL REFERENCES absence_categories(id) ON DELETE CASCADE,
    delta_value  FLOAT NOT NULL,            -- positive = add, negative = deduct
    reason       TEXT NOT NULL,
    period_label TEXT,                      -- e.g. "2026", "2026-05", free text
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at   TIMESTAMP,
    created_by   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_reason_not_empty CHECK (length(trim(reason)) > 0)
);

CREATE INDEX idx_balance_adj_employee ON absence_balance_adjustments(employee_id);
CREATE INDEX idx_balance_adj_category ON absence_balance_adjustments(category_id);
CREATE INDEX idx_balance_adj_deleted  ON absence_balance_adjustments(is_deleted);
```

---

## 5. Python Models (`database/models.py`)

### Update `AbsenceCategory` dataclass

Add after the existing `updated_at` field:
```python
is_tracked: bool = False
count_period: str = 'yearly'          # 'yearly' | 'monthly' | 'rolling'
resets_at: Optional[int] = 1          # day-of-year (yearly) or day-of-month (monthly)
rolling_days: Optional[int] = None    # rolling window length in days
warning_threshold_pct: float = 0.80
default_max_value: float = 0.0
```

### New `EmployeeAbsenceLimit` dataclass

```python
@dataclass
class EmployeeAbsenceLimit:
    employee_id: int
    category_id: int
    max_value: float
    notes: Optional[str] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_by: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)
```

### New `AbsenceBalanceAdjustment` dataclass

```python
@dataclass
class AbsenceBalanceAdjustment:
    employee_id: int
    category_id: int
    delta_value: float
    reason: str
    period_label: Optional[str] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_by: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default_factory=datetime.now)
```

---

## 6. Repositories

### 6a. Update `AbsenceCategoryRepository` (`repositories/absences/absence_category_repository.py`)

- Extend `_COLUMNS` to include: `is_tracked, count_period, resets_at, rolling_days, warning_threshold_pct, default_max_value`
- Update `row_to_category()` to map new fields
- Add method: `list_tracked() -> List[Any]` — returns only `is_tracked=TRUE AND is_deleted=FALSE`
- Update `create()` and `update()` SQL to include new fields

### 6b. New `AbsenceLimitRepository` (`repositories/absences/absence_limit_repository.py`)

```python
class AbsenceLimitRepository:
    _COLUMNS = 'id, employee_id, category_id, max_value, notes, is_deleted, deleted_at, created_by, created_at, updated_at'

    def get_for_employee_category(self, employee_id: int, category_id: int) -> Optional[Any]:
        """Active limit for one employee+category pair."""

    def list_for_employee(self, employee_id: int) -> List[Any]:
        """All active limits for an employee."""

    def list_for_category(self, category_id: int) -> List[Any]:
        """All active limits for a category (admin overview)."""

    def upsert(self, limit: EmployeeAbsenceLimit) -> int:
        """Insert or update via ON CONFLICT DO UPDATE (active limits only)."""

    def soft_delete(self, limit_id: int) -> bool:

    def soft_delete_for_employee_category(self, employee_id: int, category_id: int) -> bool:
```

**Key SQL for `upsert`:**
```sql
INSERT INTO employee_absence_limits
    (employee_id, category_id, max_value, notes, created_by)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (employee_id, category_id) WHERE is_deleted = FALSE
DO UPDATE SET
    max_value  = EXCLUDED.max_value,
    notes      = EXCLUDED.notes,
    updated_at = CURRENT_TIMESTAMP
RETURNING id
```

### 6c. New `AbsenceAdjustmentRepository` (`repositories/absences/absence_adjustment_repository.py`)

```python
class AbsenceAdjustmentRepository:
    _COLUMNS = 'id, employee_id, category_id, delta_value, reason, period_label, is_deleted, deleted_at, created_by, created_at, updated_at'

    def list_for_employee(self, employee_id: int, include_deleted: bool = False) -> List[Any]:

    def list_for_employee_category(self, employee_id: int, category_id: int) -> List[Any]:

    def create(self, adj: AbsenceBalanceAdjustment) -> int:

    def soft_delete(self, adj_id: int) -> bool:
```

### 6d. New `AbsenceBalanceRepository` (`repositories/absences/absence_balance_repository.py`)

Read-only repository. Executes the balance computation SQL.

```python
class AbsenceBalanceRepository:

    def compute_used(self, employee_id: int, category_id: int,
                     period_start: date, full_day: bool) -> float:
        """
        Sum days (full_day=True) or hours (full_day=False) of approved
        non-deleted absences for employee+category since period_start.

        Full-day SQL:
            SUM(ea.date_to - ea.date_from + 1)
        Time-slot SQL:
            SUM(EXTRACT(EPOCH FROM (ea.time_to - ea.time_from)) / 3600.0)

        WHERE ea.employee_id=%s AND ea.category_id=%s
          AND ea.status='approved' AND ea.is_deleted=FALSE
          AND ea.date_from >= %s
        """

    def compute_adjustments(self, employee_id: int, category_id: int) -> float:
        """
        Sum delta_value from absence_balance_adjustments (not deleted).
        No period filter — adjustments are always cumulative.
        """

    def bulk_summary_for_list(self) -> List[dict]:
        """
        One-query summary: for each active employee, return their primary
        tracked category balance. Used to populate the employees list table column.

        Returns list of dicts: {employee_id, category_id, category_name,
                                 used, limit, pct, status}
        where status: 'ok' | 'warning' | 'exceeded' | 'unlimited'
        """
```

---

## 7. Service Layer

### 7a. New `AbsenceBalanceService` (`services/absence_balance_service.py`)

```python
from datetime import date, timedelta
from typing import Optional, List, Dict

class AbsenceBalanceService:

    def __init__(self):
        self.balance_repo      = AbsenceBalanceRepository()
        self.limit_repo        = AbsenceLimitRepository()
        self.adjustment_repo   = AbsenceAdjustmentRepository()
        self.category_repo     = AbsenceCategoryRepository()
        self.audit_repo        = AuditRepository()

    # ── Core balance computation ──────────────────────────────────────────

    def compute_period_start(self, count_period: str, resets_at: int,
                              rolling_days: int) -> date:
        """Return the start of the current tracking period."""
        today = date.today()
        if count_period == 'yearly':
            reset = date(today.year, 1, 1) + timedelta(days=(resets_at or 1) - 1)
            if today >= reset:
                return reset
            return date(today.year - 1, 1, 1) + timedelta(days=(resets_at or 1) - 1)
        elif count_period == 'monthly':
            day = min(resets_at or 1, 28)
            if today.day >= day:
                return date(today.year, today.month, day)
            if today.month == 1:
                return date(today.year - 1, 12, day)
            return date(today.year, today.month - 1, day)
        else:  # 'rolling'
            return today - timedelta(days=rolling_days or 365)

    def get_balance(self, employee_id: int, category_id: int) -> dict:
        """
        Compute full balance snapshot for one employee+category.

        Returns dict:
        {
          'category_id': int,
          'category_name': str,
          'absence_full_day': bool,
          'unit': 'days' | 'hours',
          'used': float,
          'adjustments': float,
          'net_used': float,         # used + adjustments
          'limit': float,            # effective limit (employee override or category default)
          'has_limit': bool,         # False if limit==0 (unlimited)
          'pct': float,              # net_used / limit * 100, or 0 if no limit
          'warning_threshold_pct': float,
          'status': 'ok' | 'warning' | 'exceeded' | 'unlimited',
          'period_start': date,
          'period_label': str,       # human-readable, e.g. "2026" or "2026-05"
        }
        Raises: ValueError if category not found or not tracked.
        """

    def get_all_balances_for_employee(self, employee_id: int) -> List[dict]:
        """All tracked category balances for one employee."""

    def get_balance_summary_for_list(self) -> Dict[int, dict]:
        """For employee list table: {employee_id → primary balance dict}."""

    # ── Limit management ─────────────────────────────────────────────────

    def set_limit(self, employee_id: int, category_id: int, max_value: float,
                  notes: Optional[str], created_by: int) -> int:
        """Create or update a per-employee limit. Logs to audit_log."""

    def remove_limit(self, limit_id: int, user_id: int, user_name: str) -> None:
        """Soft-delete a limit. Logs to audit_log."""

    # ── Adjustments ───────────────────────────────────────────────────────

    def create_adjustment(self, employee_id: int, category_id: int,
                           delta_value: float, reason: str,
                           period_label: Optional[str],
                           created_by: int) -> int:
        """Add manual balance adjustment. Logs to audit_log."""

    def delete_adjustment(self, adj_id: int, user_id: int, user_name: str) -> None:
        """Soft-delete adjustment. Logs to audit_log."""

    # ── Pre-submission check (called by AbsenceService) ──────────────────

    def check_before_submit(self, employee_id: int, category_id: int,
                             proposed_days_or_hours: float,
                             source: str) -> dict:
        """
        Check if proposed absence value would exceed the limit.

        Returns dict:
        {
          'ok': bool,
          'blocked': bool,      # True if source='request' AND limit exceeded
          'warning': bool,      # True if approaching or at limit
          'message': str,
          'balance': dict,      # full balance snapshot
        }

        Logic:
        - If not tracked OR limit==0: return {'ok': True, 'blocked': False, 'warning': False, ...}
        - Compute net_used_after = net_used + proposed_days_or_hours
        - If net_used_after > limit:
            - source='request' → blocked=True, ok=False
            - source='manual'  → blocked=False, ok=True, warning=True
        - Elif net_used_after >= limit * warning_threshold_pct:
            - warning=True, ok=True, blocked=False
        """
```

### 7b. Update `AbsenceService` (`services/absence_service.py`)

In `submit_request()` — after category validation and before conflict check:

```python
# Balance check (after getting cat_row, before conflicts check)
if bool(cat_row['is_tracked']):
    proposed = self._compute_proposed_value(
        cat_row['absence_full_day'], date_from, date_to, time_from, time_to
    )
    balance_check = AbsenceBalanceService().check_before_submit(
        employee_id, category_id, proposed, source='request'
    )
    if balance_check['blocked']:
        raise AbsenceError(
            f"Przekroczono limit nieobecności: {balance_check['message']}. "
            f"Skontaktuj się z przełożonym."
        )
```

In `create_manual()` — after category validation, before creating absence:

```python
if bool(cat_row['is_tracked']):
    proposed = self._compute_proposed_value(...)
    balance_check = AbsenceBalanceService().check_before_submit(
        employee_id, category_id, proposed, source='manual'
    )
    # Don't block, but return warning info
    # Include balance_check in the returned dict
result['balance_warning'] = balance_check if balance_check.get('warning') else None
```

Add helper `_compute_proposed_value()`:
```python
@staticmethod
def _compute_proposed_value(full_day: bool, date_from, date_to,
                             time_from, time_to) -> float:
    if full_day:
        return (date_to - date_from).days + 1  # number of days
    else:
        if time_from and time_to:
            secs = (datetime.combine(date_from, time_to) -
                    datetime.combine(date_from, time_from)).seconds
            return secs / 3600.0
        return 0.0
```

---

## 8. API Endpoints

### New file: `routes/absence_balance_routes.py`

Blueprint: `absence_balance_bp = Blueprint('absence_balance', __name__)`

Registered in `app.py` without prefix: `app.register_blueprint(absence_balance_bp)`

#### HTML page
```
GET /absence-balances
→ render_template('absences/balances.html', ...)
→ Auth: @absence_management_required
→ Context: employees (list), tracked_categories (list)
```

#### JSON API endpoints

```
GET  /api/absence-balances/summary
     Response: {success, balances: {employee_id: {category_name, used, limit, pct, status}}}
     Auth: @absence_management_required

GET  /api/employees/<int:employee_id>/absence-balances
     Response: {success, balances: [balance_dict...], employee_name: str}
     Auth: @login_required (own data) | @absence_management_required (others)

POST /api/employees/<int:employee_id>/absence-limits
     Body: {category_id, max_value, notes?}
     Response: {success, id}
     Auth: @absence_management_required
     Side effects: Modals.confirm on FE, audit log on BE

DELETE /api/employees/<int:employee_id>/absence-limits/<int:limit_id>
     Response: {success}
     Auth: @absence_management_required
     Side effects: audit log

GET  /api/employees/<int:employee_id>/absence-adjustments
     Response: {success, adjustments: [{id, category_name, delta_value, reason, period_label, created_at, created_by_name}...]}
     Auth: @absence_management_required

POST /api/employees/<int:employee_id>/absence-adjustments
     Body: {category_id, delta_value, reason, period_label?}
     Response: {success, id}
     Auth: @absence_management_required
     Side effects: audit log

DELETE /api/employees/<int:employee_id>/absence-adjustments/<int:adj_id>
     Response: {success}
     Auth: @absence_management_required
     Side effects: audit log

GET  /api/employees/<int:employee_id>/absence-balance-audit
     Response: {success, entries: [{action, field_name, old_value, new_value, user_name, changed_at}...]}
     Auth: @absence_management_required
     Query: entity_type='absence_limit' OR 'absence_adjustment' AND entity_id's for this employee
```

### Update existing `absence_routes.py`

Update `create_category()` and `update_category()` to accept and store new fields:
- `is_tracked`, `count_period`, `resets_at`, `rolling_days`, `warning_threshold_pct`, `default_max_value`

---

## 9. `app.py` Updates

Add new imports:
```python
from repositories.absences.absence_limit_repository import AbsenceLimitRepository
from repositories.absences.absence_adjustment_repository import AbsenceAdjustmentRepository
from repositories.absences.absence_balance_repository import AbsenceBalanceRepository
from services.absence_balance_service import AbsenceBalanceService
```

Add to `create_app()` after existing repos:
```python
app.absence_limit_repo      = AbsenceLimitRepository()
app.absence_adjustment_repo = AbsenceAdjustmentRepository()
app.absence_balance_repo    = AbsenceBalanceRepository()
app.absence_balance_service = AbsenceBalanceService()
```

Register blueprint:
```python
from routes.absence_balance_routes import absence_balance_bp
app.register_blueprint(absence_balance_bp)
```

---

## 10. GUI Templates

### 10a. `templates/employees/list.html` — add balance column

**Location:** After the "Pokrycie grafiku" column, before "Akcje".

Add new `<col>` with `width:8%` for "Bilans urlopu".

In `<thead>`:
```html
<th style="text-align:center;">Bilans urlopu</th>
```

In `loadEmployees()` JS function, after fetching employees, trigger a separate fetch to `/api/absence-balances/summary` and store result in a `balanceSummary` map keyed by `employee_id`.

When rendering each row, add:
```javascript
function renderBalanceBadge(summary) {
    if (!summary) return '<span style="color:var(--color-ink-subtle)">—</span>';
    const { used, limit, pct, status, unit } = summary;
    if (status === 'unlimited') return '<span style="color:var(--color-ink-subtle)">∞</span>';
    const color = status === 'exceeded' ? 'var(--color-error)'
                : status === 'warning'  ? 'var(--color-warning)'
                : 'var(--color-success)';
    const unitLabel = unit === 'hours' ? 'h' : 'd';
    return `<span style="color:${color};font-weight:600;">${used.toFixed(1)}/${limit}${unitLabel}</span>`;
}
```

### 10b. `templates/employees/view.html` — balance card

**Location:** Insert after the compensation card and before the services card.

```html
<!-- Absence Balances Card -->
<div class="refined-card" id="absence-balances-card">
    <div class="section-header">
        <h2 class="section-title">Bilanse nieobecności</h2>
        <button onclick="openAdjustmentModal()" class="refined-btn-secondary refined-btn-sm">
            <span class="material-icons">tune</span>
            Dostosuj
        </button>
    </div>
    <div id="balances-container">
        <!-- Populated by JS via GET /api/employees/<id>/absence-balances -->
        <!-- Each tracked category rendered as a progress bar row -->
    </div>
</div>
```

Each balance row HTML structure:
```html
<div class="balance-row" style="margin-bottom:1rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.375rem;">
        <span style="font-size:0.8125rem;font-weight:500;">{{ category_name }}</span>
        <span style="font-size:0.8125rem;color:var(--color-ink-subtle);">
            {{ net_used }}/{{ limit }} {{ 'dni' if unit=='days' else 'godz.' }}
        </span>
    </div>
    <div style="height:8px;background:var(--color-border);border-radius:2px;overflow:hidden;">
        <div style="height:100%;width:{{ pct }}%;background:{{ bar_color }};
                    transition:width 0.4s ease;border-radius:2px;"></div>
    </div>
    <div style="font-size:0.75rem;color:var(--color-ink-subtle);margin-top:0.25rem;">
        {{ pct|round(1) }}% — okres od {{ period_start }}
    </div>
</div>
```

Bar color logic (JS):
- `pct < warning_threshold_pct * 100` → `var(--color-success)`
- `pct < 100` → `#c2410c` (orange/warning)
- `pct >= 100` → `var(--color-error)`

**Toast on page load** (in `DOMContentLoaded`): if any balance status is `'warning'` or `'exceeded'`, call `Notifications.warning('Uwaga: limit nieobecności przekroczony lub bliski przekroczenia')` after 800ms delay.

**Adjustment history section** (below the bars):
```html
<div id="adj-history-section" style="display:none;margin-top:1rem;border-top:1px solid var(--color-border-subtle);padding-top:1rem;">
    <div style="font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;color:var(--color-ink-subtle);margin-bottom:0.5rem;">
        Historia korekt bilansu
    </div>
    <table id="adj-history-table" style="width:100%;border-collapse:collapse;font-size:0.8125rem;">...</table>
</div>
<button onclick="toggleAdjHistory()" class="refined-btn-secondary refined-btn-sm" style="margin-top:0.75rem;">
    <span class="material-icons">history</span>
    Historia korekt
</button>
```

**Adjustment modal** (Modals.show with form):
- Dropdown: select tracked category
- Input: `delta_value` (positive or negative float, with label "Korekta w dniach/godzinach (+/-)")
- Input: `reason` (text, required)
- Input: `period_label` (text, optional, e.g. "2026")
- Confirm: `Modals.confirm()` before saving

### 10c. `templates/employees/edit.html` — limits section

**Location:** Add new section card at the bottom of the edit form (before the save button area).

```html
<div class="refined-card">
    <h2 class="section-title">Limity nieobecności (indywidualne)</h2>
    <p style="font-size:0.8125rem;color:var(--color-ink-subtle);margin-bottom:1rem;">
        Zostaw puste, aby użyć domyślnego limitu kategorii.
    </p>
    <table id="limits-table" style="width:100%;border-collapse:collapse;">
        <thead>
            <tr>
                <th>Kategoria</th>
                <th>Limit domyślny</th>
                <th>Limit indywidualny</th>
                <th>Notatka</th>
                <th></th>
            </tr>
        </thead>
        <tbody id="limits-tbody">
            <!-- Populated via GET /api/employees/<id>/absence-balances -->
        </tbody>
    </table>
</div>
```

Each row renders inline inputs. Saving a row:
1. JS calls `Modals.confirm({ title: 'Zmień limit', message: 'Ustaw indywidualny limit...', ... })`
2. On confirm: `PATCH /api/employees/<id>/absence-limits` with `{category_id, max_value, notes}`
3. On success: `Notifications.success('Limit zaktualizowany')`

Clearing override (button "Usuń override"):
1. `Modals.confirm({ title: 'Usuń limit indywidualny', ... })`
2. `DELETE /api/employees/<id>/absence-limits/<limit_id>`
3. Row reverts to showing default_max_value

### 10d. `templates/absences/management.html` — balance hints

In the absence list rows (for pending/approved absences), add a compact balance indicator next to the employee name:

```html
<span class="balance-hint" data-employee-id="{{ absence.employee_id }}"
      data-category-id="{{ absence.category_id }}"
      style="font-size:0.75rem;color:var(--color-ink-subtle);margin-left:0.5rem;">
    <!-- JS populates: e.g. "(12/26 d)" -->
</span>
```

On page load JS: batch-fetch `/api/absence-balances/summary` and populate all `.balance-hint` spans.

If the category is tracked and `status == 'exceeded'`, change the employee name cell background subtly to `rgba(155,44,44,0.04)`.

### 10e. New page: `templates/absences/balances.html`

**Route:** `GET /absence-balances`

**Layout:** Extends `base.html`, class `refined-page` max-width 1400px.

**Page header:** "Bilanse urlopowe" / subtitle "Zarządzanie limitami i korektami"

**Stats cards row** (4 cards):
1. Pracownicy z aktywnym śledzeniem (count of employees with at least one tracked category with a balance)
2. Kategorie śledzone (count of `is_tracked=TRUE` categories)
3. Bliscy limitu (count of employees with `status='warning'`)
4. Przekroczony limit (count of employees with `status='exceeded'`)

**Filter row:** dropdown filter by tracked category, search by employee name.

**Main table columns:**
| Pracownik | Kategoria | Okres | Wykorzystano | Limit | % | Status | Akcje |
|---|---|---|---|---|---|---|---|

**Actions per row:**
- `Korekta` → opens adjustment modal
- `Ustaw limit` → opens limit edit modal  
- `Historia` → expands inline audit trail sub-row

**Inline audit trail** (expandable `<tr>` below the data row):
- Columns: Kiedy | Kto | Akcja | Szczegóły
- Fetched via `GET /api/employees/<id>/absence-balance-audit`

**"Nowa korekta" button** in page header opens a full modal:
- Select employee (searchable dropdown)
- Select tracked category  
- delta_value input
- reason (required)
- period_label (optional)
- `Modals.confirm()` before saving

**Toast on page load**: if any `status == 'exceeded'`, show `Notifications.warning(...)` listing those employees.

---

## 11. Sidebar Navigation

**File:** `templates/components/sidebar.html`

Under the "Zarządzanie" section, after the existing "Nieobecnosci" link:

```jinja
{% if user_permissions.absences or is_supervisor %}
{{ sidebar_link(
    url_for('absence_balance.balances_index'), 'Bilanse urlopow',
    'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
    request.endpoint == 'absence_balance.balances_index') }}
{% endif %}
```

Update the `zarzadzanie_active` set in sidebar to include `'absence_balance.balances_index'`.

---

## 12. Audit Trail Integration

All writes to `employee_absence_limits` and `absence_balance_adjustments` must call `AuditRepository.log_event()`.

```python
# On limit set/update:
audit_repo.log_event(
    entity_type='absence_limit',
    action='CREATE' or 'UPDATE',
    entity_id=limit_id,
    entity_label=f"{employee_name} — {category_name}",
    field_name='max_value',
    old_value=str(old_value) if old_value else None,
    new_value=str(new_value),
    user_id=current_user.id,
    user_name=current_user.full_name,
)

# On adjustment create:
audit_repo.log_event(
    entity_type='absence_adjustment',
    action='CREATE',
    entity_id=adj_id,
    entity_label=f"{employee_name} — {category_name}: {delta_value:+.1f}",
    field_name='delta_value',
    old_value=None,
    new_value=str(delta_value),
    user_id=current_user.id,
    user_name=current_user.full_name,
)

# On limit/adjustment soft-delete:
# action='DELETE', new_value='deleted'
```

The balance audit page queries `audit_log WHERE entity_type IN ('absence_limit', 'absence_adjustment')`. The `GET /api/employees/<id>/absence-balance-audit` endpoint fetches by entity_type + cross-referencing entity_ids that belong to the employee.

---

## 13. UX — Keyboard & Focus

### ESC keybinding on `templates/absences/balances.html`
```javascript
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (document.querySelector('.modal-overlay')) return;
        window.location.href = '/absences';
    }
});
```

### Focus trap in adjustment/limit modals
The modal system (`modals.js`) already implements focus trapping inside `.modal-content`. No additional work needed for the Modals API.

### Tab management
- Each limit edit row: Tab cycles through `max_value` input → `notes` input → save button → next row
- On form open in the balances page: `autofocus` on first interactive element

---

## 14. Complete File List

### New files to create
| File | Purpose |
|---|---|
| `alembic/versions/o9p0q1r2s3t4_add_absence_balance_tracking.py` | DB migration |
| `repositories/absences/absence_limit_repository.py` | CRUD for employee_absence_limits |
| `repositories/absences/absence_adjustment_repository.py` | CRUD for absence_balance_adjustments |
| `repositories/absences/absence_balance_repository.py` | Read-only balance computations |
| `services/absence_balance_service.py` | Balance business logic |
| `routes/absence_balance_routes.py` | Page + API endpoints for balance feature |
| `templates/absences/balances.html` | New admin balance management page |

### Files to modify
| File | Change |
|---|---|
| `database/models.py` | Update AbsenceCategory; add EmployeeAbsenceLimit, AbsenceBalanceAdjustment |
| `repositories/absences/absence_category_repository.py` | Extend _COLUMNS + row_to_category + create/update SQL + add list_tracked() |
| `services/absence_service.py` | Add balance check in submit_request() and create_manual() |
| `routes/absence_routes.py` | Update category create/update to accept new fields |
| `app.py` | Register new repos, service, blueprint |
| `templates/employees/list.html` | Add balance column + JS fetch |
| `templates/employees/view.html` | Add balance card with progress bars + adjustment modal |
| `templates/employees/edit.html` | Add limits section with inline edits |
| `templates/absences/management.html` | Add balance hints on absence rows |
| `templates/components/sidebar.html` | Add "Bilanse urlopow" nav link |

---

## 15. Implementation Order (recommended sequence)

1. **Migration** — add DB columns/tables (can be done and applied independently)
2. **Models** — update `database/models.py` dataclasses
3. **Category repository** — extend for new fields
4. **Limit + Adjustment + Balance repositories** — pure DB logic, no dependencies on services
5. **`AbsenceBalanceService`** — core computation + CRUD helpers
6. **Update `AbsenceService`** — add balance check in submit/create_manual
7. **`app.py`** — register repos, service, blueprint
8. **`absence_balance_routes.py`** — page + API endpoints
9. **`templates/absences/balances.html`** — new admin page
10. **`templates/employees/view.html`** — balance card
11. **`templates/employees/edit.html`** — limits section
12. **`templates/employees/list.html`** — balance column
13. **`templates/absences/management.html`** — balance hints
14. **Sidebar** — add nav link

Each step is independently testable. Steps 1–7 have no UI dependencies; steps 8–14 have no migration dependencies after step 1 is applied.

---

## 16. Validation Rules Summary

| Layer | Rule |
|---|---|
| DB | `count_period IN ('yearly', 'monthly', 'rolling')` |
| DB | `resets_at BETWEEN 1 AND 365` when not NULL |
| DB | `warning_threshold_pct BETWEEN 0.0 AND 1.0` |
| DB | `default_max_value >= 0.0` |
| DB | `max_value >= 0.0` in limits table |
| DB | `length(trim(reason)) > 0` in adjustments table |
| DB | Partial UNIQUE on `(employee_id, category_id) WHERE is_deleted=FALSE` in limits |
| Service | Hard block on submit if `source='request'` AND `net_used + proposed > limit > 0` |
| Service | Soft warning (in response dict) if `source='manual'` AND limit exceeded |
| Service | Warning flag if `net_used + proposed >= limit * warning_threshold_pct` |
| Service | `resets_at` must be 1–28 for `count_period='monthly'` |
| API | All mutation endpoints require `@absence_management_required` |
| API | `GET /api/employees/<id>/absence-balances` allows own employee OR supervisor |
| Frontend | `Modals.confirm()` before any limit set/change or adjustment create |
| Frontend | Toast `Notifications.warning()` on page load if any balance `status == 'exceeded'` |
