# Implementation Plan: Employee Management Features

## Context

Extending the salon management app's employee module with four related features:
- **Task #1** — Add a `formy_zatrudnienia` (employment type) lookup table, CRUD UI, and link it to employees
- **Task #2** — Add 10 per-employee analytics metrics in a tabbed section on the employee view page
- **Task #3** — Bring employee create/edit forms to full field coverage (skills, schedule, specializations, employer cost rate, etc.)
- **Task #4** — Bring the employee view page to full field display + the analytics section from Task #2

**Key gap found:** `employer_cost_rate` exists in the DB (migration `ba16fcdbb066`) but is **missing from the `Employee` dataclass** and all repository methods. Must be fixed in Phase 1.

---

## Phase 1 — Forma Zatrudnienia: Database + Backend

**Goal:** Create `formy_zatrudnienia` table, FK on `employees`, dataclass, repository, API/route endpoints.
**Blocks:** Phases 2 and 3.

### New files
- `alembic/versions/<hash>_create_formy_zatrudnienia.py`
  - `down_revision = 'c8d4e2f1a9b3'` (current HEAD)
  - `upgrade()`: Create `formy_zatrudnienia` table (`id` SERIAL PK, `nazwa` VARCHAR(100) NOT NULL, `uwagi` TEXT, `min_salary_required` BOOL DEFAULT FALSE, `granted_salary` BOOL DEFAULT FALSE, `commision_included` BOOL DEFAULT FALSE, `created_at`, `updated_at`); add `forma_zatrudnienia_id INTEGER` FK to `employees` with `ON DELETE SET NULL`
  - `downgrade()`: drop FK, drop column, drop table (reverse order)
- `repositories/employees/forma_zatrudnienia_repository.py` — `FormaZatrudnieniaRepository` class
  - Pattern: identical to `employee_repository.py` (uses `get_db_connection()` context manager, `row_to_forma()` converter)
  - Methods: `get_all() -> List`, `get_by_id(id) -> Optional`, `create(forma) -> int`, `update(id, forma) -> bool`, `delete(id) -> bool`
  - `delete()` must guard against employees referencing this ID (raise descriptive exception)

### Modified files
- `database/models.py`
  - Add `FormaZatrudnienia` dataclass (after `Employee`): fields `nazwa: str`, `uwagi: Optional[str] = None`, `min_salary_required: bool = False`, `granted_salary: bool = False`, `commision_included: bool = False`, `id: Optional[int] = None`, `created_at`, `updated_at`
  - Add to `Employee` dataclass: `forma_zatrudnienia_id: Optional[int] = None` (after `user_id`) and `employer_cost_rate: float = 0.22` (after `commission_rate`) — **both missing**
- `repositories/employees/employee_repository.py`
  - `row_to_employee()`: add `forma_zatrudnienia_id` and `employer_cost_rate` field reads
  - `create()` INSERT: include `forma_zatrudnienia_id`, `employer_cost_rate`
  - `update()` SET: include `forma_zatrudnienia_id = %s`, `employer_cost_rate = %s`
- `app.py` — add `app.forma_zatrudnienia_repo = FormaZatrudnieniaRepository()`
- `routes/api_routes.py`
  - Add `GET/POST /api/formy-zatrudnienia` and `GET/PUT/DELETE /api/formy-zatrudnienia/<int:id>`
  - Update `create_employee_endpoint()` and `update_employee()` to pass `forma_zatrudnienia_id` and `employer_cost_rate`
  - Update `get_employee()` serialization to include both new fields
- `routes/main_routes.py` — add `GET /formy-zatrudnienia` route (`formy_zatrudnienia_list`)

### Verification
- `alembic upgrade head` → confirm table and column created
- `GET /api/formy-zatrudnienia` → returns `[]`
- POST/PUT/DELETE roundtrip on a test entry
- `GET /api/employees/<id>` → response includes `forma_zatrudnienia_id` and `employer_cost_rate`

---

## Phase 2 — Forma Zatrudnienia: UI + Sidebar

**Goal:** Build the list/CRUD template and add the sidebar nav item.
**Depends on:** Phase 1.

### New files
- `templates/employees/formy_zatrudnienia/list.html`
  - Extends `base.html`, uses existing refined design system variables
  - Top `refined-card`: create form with fields `nazwa` (required), `uwagi` (textarea), three checkboxes
  - Bottom `refined-card`: table (`refined-table`) with columns: Nazwa, Uwagi, Min. wynagrodzenie, Gwarantowane, Prowizja, Akcje
  - Each row: Edit button (inline text inputs toggle via JS) + Delete button with confirmation
  - JS in `{% block extra_scripts %}`: fetch `GET /api/formy-zatrudnienia` on load, POST to create, PUT to update, DELETE with `Notifications` toasts

### Modified files
- `templates/components/sidebar.html` (lines 102–110)
  - Insert new `<a>` tag for "Rodzaje zatrudnienia" → `url_for('main.formy_zatrudnienia_list')` **before** the closing `{% endif %}` (line 110)
  - Active state: `{% if request.endpoint == 'main.formy_zatrudnienia_list' %}...{% endif %}`
  - Icon: SVG path for a document/list icon (e.g., `M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2`)

### Verification
- Navigate to `/formy-zatrudnienia` → page loads with empty table
- Create "Umowa o pracę" → appears in table
- Edit inline → PUT fires, row updates without reload
- Delete → removed with success toast
- Sidebar link highlights when on the page

---

## Phase 3 — Employee Forms + View: Full Field Coverage

**Goal:** Update create/edit forms and view page to cover all Employee dataclass fields (excluding analytics section).
**Depends on:** Phase 1 (so `forma_zatrudnienia_id` API and repo exist).

### Modified files
- `routes/main_routes.py` — `create_employee()` and `edit_employee()` routes
  - Pass `forma_options = current_app.forma_zatrudnienia_repo.get_all()` to template context
  - For `edit_employee()`, also instantiate `UserRepository()` inline and pass `user_options` for the user dropdown

- `templates/employees/create.html`
  - New section **"Szczegóły stanowiska"**: `forma_zatrudnienia_id` dropdown (populated from `forma_options`), `user_id` dropdown (populated from `user_options`, optional, label "Konto użytkownika")
  - New section **"Koszty i harmonogram"**: `employer_cost_rate` number input (default `0.22`, step `0.01`, range `0–1`, hint: "np. 0.22 = 22% ZUS/podatki"), `max_appointments_per_day` number input (default `8`)
  - New section **"Umiejętności"**: dynamic rows container `<div id="skills-container">` — each row: text input (nazwa umiejętności) + `<select>` 1–5 (ocena); "Dodaj umiejętność" button appends a row; JS serializes to `{"skill": rating}` object before POST
  - New section **"Specjalizacje"**: tag/chip input — text input + "Dodaj" button; chips as `<span>Nazwa <button>×</button></span>`; JS maintains array, serializes to JSON array
  - New section **"Harmonogram pracy"**: 7-row grid (Mon–Sun); each row: day label, checkbox "Pracuje", "Od" time input, "Do" time input (enabled only when checked); JS serializes checked days only to `{"mon": "09:00-17:00", ...}`
  - `photo_path`: text input for file path

- `templates/employees/edit.html`
  - Mirror all new sections from `create.html`
  - Pre-populate from `employee` Jinja object: `employer_cost_rate`, `max_appointments_per_day`, `photo_path`, `forma_zatrudnienia_id`, `user_id`
  - Pre-populate JSON fields via inline `<script>`: call `populateSkills({{ employee.get_skills_dict()|tojson }})`, `populateSpecializations({{ employee.get_specializations_list()|tojson }})`, `populateSchedule({{ employee.get_work_schedule_dict()|tojson }})`

- `templates/employees/view.html` (non-analytics additions)
  - Header: if `employee.photo_path`, show `<img>` instead of initials avatar
  - "Wynagrodzenie" card: add `employer_cost_rate` as badge (e.g. "22% ZUS"), add `max_appointments_per_day`
  - "Dane osobowe" card: add `forma_zatrudnienia` resolved name (pass from route: `forma_nazwa`)
  - New **"Umiejętności i specjalizacje"** card: skills as colored rating pills, specializations as chip tags
  - New **"Harmonogram pracy"** card: 7-column weekly grid, grayed for non-working days

- `routes/main_routes.py` — `view_employee()` route
  - Fetch `forma_nazwa` from DB if `employee.forma_zatrudnienia_id` is set; pass to template

- `routes/api_routes.py`
  - Accept and pass `employer_cost_rate`, `skills`, `specializations`, `work_schedule`, `max_appointments_per_day`, `photo_path` in create/update employee endpoints
  - Add `employer_cost_rate` to `_audit_changes` tracking

- `repositories/employees/employee_repository.py`
  - Ensure `employer_cost_rate` is in `create()` INSERT and `update()` SET (currently missing despite DB column existing)

### Verification
- Create employee with skills JSON, work schedule, specializations, and forma dropdown → verify all saved via `GET /api/employees/<id>`
- Edit existing employee → confirm all fields pre-populate and update correctly
- View page shows: photo (if set), work schedule grid, skills rating pills, specialization chips, forma zatrudnienia name, employer_cost_rate badge

---

## Phase 4 — Employee Analytics: Backend

**Goal:** Build `EmployeeAnalyticsRepository` and 7 API endpoints for per-employee metrics.
**Depends on:** Nothing (fully independent, can run in parallel with Phase 3).

### New files
- `repositories/employees/employee_analytics_repository.py`
  - Class `EmployeeAnalyticsRepository(employee_id: int)`
  - Uses `DatabaseConnection.get_connection()` — **not** `get_db_connection()` (matches `analytics_repository.py` pattern, not the CRUD repo pattern)
  - Reference: `repositories/analytics/analytics_repository.py` — copy cost formula from `get_employee_performance()`, copy CTE logic from `get_client_metrics()`, copy heatmap query from `get_peak_hours()`

  Methods:
  - `get_summary(months=12) -> Dict` — total revenue, employer cost (`GREATEST(base_salary, commission) * (1 + employer_cost_rate)`), net profit, avg ticket, total appointments
  - `get_revenue_trend(months=12) -> List[Dict]` — monthly `{'month', 'revenue', 'commission', 'appointments'}`, use `generate_series` to fill zero months
  - `get_services_mix() -> List[Dict]` — top 10 services by appointment count: `{'service_name', 'appointment_count', 'revenue'}`
  - `get_peak_hours() -> List[Dict]` — `{'day_of_week', 'hour_of_day', 'appointment_count'}`
  - `get_client_split(months=12) -> List[Dict]` — monthly `{'month', 'new_clients', 'returning_clients'}` using CTE
  - `get_skills_radar() -> List[Dict]` — parse `skills` JSON in Python: `[{'skill', 'rating'}]` sorted DESC
  - `get_commission_trend(months=12) -> List[Dict]` — monthly `{'month', 'base_salary', 'commission_earned', 'gross_salary'}`

### Modified files
- `routes/analytics_routes.py` — add 7 endpoints:
  ```
  GET /api/employees/<id>/analytics/summary
  GET /api/employees/<id>/analytics/revenue-trend
  GET /api/employees/<id>/analytics/services-mix
  GET /api/employees/<id>/analytics/peak-hours
  GET /api/employees/<id>/analytics/client-split
  GET /api/employees/<id>/analytics/skills-radar
  GET /api/employees/<id>/analytics/commission-trend
  ```
  - All: `@login_required`, `@module_permission_required('appointments')`
  - Return `{'success': True, 'employee_id': id, 'data': ...}`
  - Return 404 if employee not found

### Verification
- Each endpoint with a valid `employee_id` returns correct JSON shape
- Endpoint with invalid `employee_id` returns 404
- Zero-data employee returns empty lists (not errors)

---

## Phase 5 — Employee Analytics: UI

**Goal:** Add tabbed analytics section to `view.html` with Chart.js charts.
**Depends on:** Phase 4 (endpoints must exist), Phase 3 (view.html in updated state).

### New files
- `static/js/employees/analytics.js`
  - Copy `CHART_COLORS`, `formatCurrency()`, `escapeHtml()` from `dashboard.js`
  - Chart instances: `revenueChart`, `appointmentsChart`, `serviceMixChart`, `clientSplitChart`, `skillsChart`, `commissionChart` (all `= null` initially)
  - `initAnalytics(employeeId)` — stores `EMPLOYEE_ID`, calls `loadTab('overview')` on DOMContentLoaded
  - `loadTab(tabName)` — shows/hides panels, updates active button class, calls load functions for that tab

  Per-tab functions:
  - **overview**: `loadSummaryKPIs()` — fetch `/summary`, populate 4 KPI cards (revenue, cost, net profit, avg ticket); net profit card red if negative
  - **przychody**: `loadRevenueTrend()` (line chart: revenue + commission datasets), `loadCommissionTrend()` (stacked bar: base_salary vs commission_earned)
  - **wizyty**: `loadAppointmentVolume()` (line chart from revenue-trend `appointments` field), `loadClientSplit()` (bar chart per month), `loadServiceMix()` (doughnut, top 8), `loadPeakHours()` (HTML heatmap table — **not a canvas**)
  - **umiejetnosci**: `loadSkillsRadar()` — radar chart with `scales.r.min: 0, max: 5`; show "Brak danych o umiejętnościach" if empty

  All chart functions: destroy existing instance before creating new (`if (chart) chart.destroy()`); `responsive: true, maintainAspectRatio: false`

  Heatmap pattern:
  ```javascript
  // Build 7×24 matrix, render as <table> with cell opacity = count / maxCount
  // style="background: rgba(37,99,235,${opacity})"
  ```

### Modified files
- `templates/employees/view.html`
  - Add analytics section after notes card, before action bar:
    ```html
    <div class="refined-card" id="analytics-section">
      <h2>Analizy i wyniki</h2>
      <!-- Tab nav: Przegląd | Przychody | Wizyty | Umiejętności -->
      <div class="analytics-tabs">...</div>
      <!-- 4 tab panels, only "tab-overview" visible by default -->
      <div id="tab-overview"><!-- 4 KPI cards grid --></div>
      <div id="tab-przychody" style="display:none"><!-- 2 canvases --></div>
      <div id="tab-wizyty" style="display:none"><!-- 3 canvases + heatmap table --></div>
      <div id="tab-umiejetnosci" style="display:none"><!-- radar canvas --></div>
    </div>
    ```
  - Each `<canvas>`: `style="height: 250px"` (required for `maintainAspectRatio: false`)
  - KPI grid: `display:grid; grid-template-columns: repeat(4, 1fr); gap: 1rem`
  - In `{% block extra_scripts %}`: add Chart.js CDN (`chart.umd.min.js@4.4.0`), `analytics.js` script tag, inline `<script>initAnalytics({{ employee.id }});</script>`

### Verification
- Navigate to `/employee/<id>` with appointment history
- All 4 tabs render without console errors
- Charts destroy/recreate cleanly when switching tabs
- Heatmap renders as HTML table with opacity scaling
- Employee with no data shows empty states (no JS errors)

---

## Critical File Paths

| File | Phase | Purpose |
|------|-------|---------|
| `database/models.py` | 1 | Add `FormaZatrudnienia` dataclass; add `forma_zatrudnienia_id` + `employer_cost_rate` to `Employee` |
| `repositories/employees/employee_repository.py` | 1 | Update `row_to_employee()`, `create()`, `update()` |
| `repositories/employees/forma_zatrudnienia_repository.py` | 1 | **New** — CRUD for employment types |
| `repositories/employees/employee_analytics_repository.py` | 4 | **New** — 7 analytics query methods |
| `repositories/analytics/analytics_repository.py` | 4 | **Reference** — cost formula, CTE patterns, heatmap SQL |
| `routes/analytics_routes.py` | 4 | Add 7 per-employee analytics endpoints |
| `routes/api_routes.py` | 1, 3 | Add forma CRUD endpoints; update employee endpoints |
| `routes/main_routes.py` | 1, 2, 3 | Add routes; pass `forma_options` context |
| `app.py` | 1 | Register `FormaZatrudnieniaRepository` |
| `templates/components/sidebar.html` | 2 | Add "Rodzaje zatrudnienia" nav item (insert before line 110 `{% endif %}`) |
| `templates/employees/formy_zatrudnienia/list.html` | 2 | **New** — employment type CRUD page |
| `templates/employees/create.html` | 3 | Add 5 new field sections |
| `templates/employees/edit.html` | 3 | Mirror create.html + pre-population JS |
| `templates/employees/view.html` | 3, 5 | Add new field display cards + analytics section |
| `static/js/employees/analytics.js` | 5 | **New** — Chart.js analytics tab logic |
| `static/js/analytics/dashboard.js` | 5 | **Reference** — Chart.js patterns to copy |

## Phase Dependency Order

```
Phase 1 (DB + backend) ──► Phase 2 (forma UI)
                       ──► Phase 3 (forms + view)

Phase 4 (analytics backend)  ──► Phase 5 (analytics UI)
                              (Phase 3 should also precede 5 so view.html is stable)
```

Phases 1 and 4 can be built in parallel. Phases 2, 3, 5 follow sequentially from their dependencies.
