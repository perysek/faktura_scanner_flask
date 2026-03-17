# Plan: Visit Satisfaction Score + Employee Skill Analytics

## Context

The salon management app currently has no mechanism for collecting client feedback on completed visits. Employee skill ratings (`employees.skills` JSON) are set manually. This plan adds:

1. A **`satisfaction_score` (1–5)** field on completed appointments — entered after the visit is finished.
2. A **skill-impact computation**: each satisfaction score updates a per-service-category satisfaction average, displayed as a complementary "data-driven rating" alongside the manual skill rating.
3. **Satisfaction analytics in the employee view** — a new "Satysfakcja" tab showing score distribution, trend, and per-service breakdown.
4. **Satisfaction column in the analytics dashboard** employee performance table (the `#nav-employees` "Wyniki pracowników" table) — average satisfaction per employee for the chosen period.

> **Design decision on skill mutation**: The satisfaction score does NOT overwrite the manual `employees.skills` JSON values. Instead, it feeds a computed average shown separately. This prevents data corruption from outlier visits while still surfacing actionable insights.

---

## Files to Modify / Create

| File | Change |
|------|--------|
| `database/schema.sql` | Add `satisfaction_score SMALLINT CHECK (1–5)` to appointments |
| `database/models.py` | Add `satisfaction_score: Optional[int] = None` to `Appointment` |
| `alembic/versions/<new>.py` | Migration: ALTER TABLE appointments ADD COLUMN satisfaction_score |
| `repositories/appointments/appointment_repository.py` | Add `update_satisfaction_score()` |
| `repositories/employees/employee_analytics_repository.py` | Add `get_satisfaction_stats()` |
| `repositories/analytics/analytics_repository.py` | Update `get_employee_performance()` to include `avg_satisfaction` |
| `routes/appointment_routes.py` | Add `PATCH /appointments/<id>/satisfaction` endpoint |
| `routes/analytics_routes.py` | Add `GET /employees/<id>/analytics/satisfaction` endpoint |
| `templates/appointments/view.html` | Add star-rating widget for completed visits |
| `templates/employees/view.html` | Add "Satysfakcja" tab to the existing analytics section |
| `templates/analytics/dashboard.html` | Add "Satysfakcja" column header to `#nav-employees` table |
| `static/js/analytics/dashboard.js` | Render satisfaction column in employee table rows |

---

## Phase 1 — Database Migration

### 1.1 Update `database/schema.sql`
Add to `appointments` table:
```sql
satisfaction_score SMALLINT CHECK (satisfaction_score BETWEEN 1 AND 5),
```

### 1.2 Create Alembic Migration
New file: `alembic/versions/<hash>_add_satisfaction_score_to_appointments.py`
```python
def upgrade():
    op.add_column('appointments',
        sa.Column('satisfaction_score', sa.SmallInteger(),
                  sa.CheckConstraint('satisfaction_score BETWEEN 1 AND 5'),
                  nullable=True))

def downgrade():
    op.drop_column('appointments', 'satisfaction_score')
```

### 1.3 Update `database/models.py`
In the `Appointment` dataclass, add after `cancellation_reason`:
```python
satisfaction_score: Optional[int] = None
```
Also update `row_to_appointment()` in `appointment_repository.py` to map this field.

---

## Phase 2 — Repository Layer

### 2.1 `repositories/appointments/appointment_repository.py`

Add method `update_satisfaction_score(appointment_id: int, score: int) -> bool`:
```python
def update_satisfaction_score(self, appointment_id: int, score: int) -> bool:
    """Set satisfaction_score only for completed appointments. Returns True on success."""
    conn = self._conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE appointments
        SET satisfaction_score = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s AND status = 'completed'
        RETURNING id
    """, (score, appointment_id))
    conn.commit()
    return cursor.fetchone() is not None
```

Also ensure `row_to_appointment()` maps `satisfaction_score` from the row dict.

### 2.2 `repositories/employees/employee_analytics_repository.py`

Add `get_satisfaction_stats(months: int = 12) -> Dict` — returns:
- `avg_score`: float (overall)
- `total_scored`: int (appointments with a score)
- `distribution`: `{1: n, 2: n, 3: n, 4: n, 5: n}` (star counts)
- `by_service_category`: `[{'category', 'avg_score', 'count'}]` — avg satisfaction per service category
- `monthly_trend`: `[{'month', 'month_label', 'avg_score', 'count'}]` — 12-month trend

```sql
-- avg_score + distribution
SELECT
    ROUND(AVG(a.satisfaction_score)::numeric, 2) AS avg_score,
    COUNT(a.satisfaction_score) AS total_scored,
    COUNT(*) FILTER (WHERE a.satisfaction_score = 1) AS score_1,
    COUNT(*) FILTER (WHERE a.satisfaction_score = 2) AS score_2,
    COUNT(*) FILTER (WHERE a.satisfaction_score = 3) AS score_3,
    COUNT(*) FILTER (WHERE a.satisfaction_score = 4) AS score_4,
    COUNT(*) FILTER (WHERE a.satisfaction_score = 5) AS score_5
FROM appointments a
WHERE a.employee_id = %(eid)s
  AND a.status = 'completed'
  AND a.satisfaction_score IS NOT NULL
  AND a.appointment_date >= CURRENT_DATE - (%(months)s || ' months')::interval

-- by_service_category
SELECT
    COALESCE(s.category, 'Inne') AS category,
    ROUND(AVG(a.satisfaction_score)::numeric, 2) AS avg_score,
    COUNT(a.id) AS count
FROM appointments a
JOIN appointment_services aps ON aps.appointment_id = a.id
JOIN services s ON s.id = aps.service_id
WHERE a.employee_id = %(eid)s
  AND a.status = 'completed'
  AND a.satisfaction_score IS NOT NULL
GROUP BY s.category
ORDER BY avg_score DESC

-- monthly_trend (reuse generate_series pattern from existing methods)
SELECT
    TO_CHAR(m.month_start, 'YYYY-MM') AS month,
    TO_CHAR(m.month_start, 'Mon YYYY') AS month_label,
    ROUND(AVG(a.satisfaction_score)::numeric, 2) AS avg_score,
    COUNT(a.satisfaction_score) AS count
FROM months m
LEFT JOIN appointments a
    ON a.employee_id = %(eid)s
    AND DATE_TRUNC('month', a.appointment_date) = m.month_start
    AND a.status = 'completed'
    AND a.satisfaction_score IS NOT NULL
GROUP BY m.month_start
ORDER BY m.month_start
```

### 2.3 `repositories/analytics/analytics_repository.py`

Update `get_employee_performance()` (line ~92) to LEFT JOIN avg satisfaction:
```sql
-- Add to the existing CTE/query:
LEFT JOIN (
    SELECT employee_id,
           ROUND(AVG(satisfaction_score)::numeric, 2) AS avg_satisfaction,
           COUNT(satisfaction_score) AS scored_count
    FROM appointments
    WHERE status = 'completed'
      AND satisfaction_score IS NOT NULL
      AND appointment_date BETWEEN %(start)s AND %(end)s
    GROUP BY employee_id
) sat ON sat.employee_id = e.id
```
Return dict includes: `avg_satisfaction` (float|None), `scored_count` (int).

---

## Phase 3 — API Endpoints

### 3.1 `routes/appointment_routes.py`

Add after `complete_appointment` (line ~381):
```python
@appointments_bp.route('/appointments/<int:appointment_id>/satisfaction', methods=['PATCH'])
@login_required
@module_permission_required('appointments')
def set_satisfaction_score(appointment_id: int):
    """Set satisfaction score (1–5) for a completed appointment."""
    data = request.get_json()
    score = data.get('score')
    if not isinstance(score, int) or score < 1 or score > 5:
        return jsonify({"success": False, "error": "Wynik musi być liczbą 1–5"}), 400
    repo = current_app.appointment_repo
    ok = repo.update_satisfaction_score(appointment_id, score)
    if not ok:
        return jsonify({"success": False, "error": "Nie można ocenić — wizyta nie jest zakończona lub nie istnieje"}), 404
    return jsonify({"success": True, "appointment_id": appointment_id, "score": score})
```

### 3.2 `routes/analytics_routes.py`

Add after `get_employee_commission_trend` (line ~514):
```python
@analytics_bp.route('/employees/<int:employee_id>/analytics/satisfaction', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_satisfaction(employee_id: int):
    """Satisfaction stats: avg, distribution, by_service_category, monthly_trend."""
    emp_repo, err = _get_employee_analytics_repo(employee_id)
    if err:
        return err
    months = int(request.args.get('months', 12))
    data = emp_repo.get_satisfaction_stats(months)
    return jsonify({"success": True, "employee_id": employee_id, "data": data})
```

---

## Phase 4 — UI: Appointment View Star Rating Widget

### `templates/appointments/view.html`

In the "completed" status section, add satisfaction input block (shown only when `status == 'completed'`):

```html
<!-- Satisfaction Rating — shown for completed visits only -->
<div id="satisfactionSection" class="refined-card mt-4" style="display:none">
    <h3 class="text-sm font-semibold mb-3">Ocena wizyty przez klienta</h3>
    <div id="satisfactionDisplay">
        <!-- Star rating 1–5 -->
        <div class="flex items-center gap-2 mb-3">
            {% for i in range(1,6) %}
            <button class="star-btn text-2xl" data-score="{{ i }}">☆</button>
            {% endfor %}
            <span id="scoreLabel" class="text-sm text-slate-500 ml-2">Brak oceny</span>
        </div>
        <button id="saveSatisfactionBtn" class="refined-btn-primary refined-btn-sm" disabled>
            Zapisz ocenę
        </button>
    </div>
</div>
```

JS in `{% block extra_scripts %}`:
- Show block when appointment status is `completed`
- Pre-fill stars if `satisfaction_score` already set
- On star click: update selected state, enable save button
- On save: `PATCH /api/appointments/<id>/satisfaction` with `{score: N}`
- Show success notification via `Notifications.success()`

---

## Phase 5 — Employee View: Satysfakcja Tab

### `templates/employees/view.html`

**5.1 Add tab button** (existing tabs at line ~592):
```html
<button id="tab-btn-satysfakcja" onclick="loadTab('satysfakcja')" class="analytics-tab-btn">Satysfakcja</button>
```

**5.2 Add tab content panel** (after existing tab panels):
```html
<div id="tab-satysfakcja" class="analytics-tab-panel" style="display:none">
    <!-- KPI row: avg score, total scored -->
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-bottom:1.5rem">
        <div class="kpi-box">
            <div class="kpi-label">Śr. ocena</div>
            <div id="sat-avg" class="kpi-value">—</div>
            <div class="kpi-sub">na 5 gwiazdek</div>
        </div>
        <div class="kpi-box">
            <div class="kpi-label">Ocenionych wizyt</div>
            <div id="sat-count" class="kpi-value">—</div>
        </div>
        <div class="kpi-box">
            <div class="kpi-label">Rozkład ocen</div>
            <div id="sat-dist" class="kpi-sub">— (gwiazdki)</div>
        </div>
    </div>

    <!-- Score by service category table -->
    <div style="margin-bottom:1.5rem">
        <div class="chart-label">Ocena wg kategorii usług</div>
        <table class="refined-table-mini" id="sat-by-category">
            <thead><tr><th>Kategoria</th><th class="text-right">Śr. ocena</th><th class="text-right">Liczba</th></tr></thead>
            <tbody><tr><td colspan="3" class="text-center text-slate-500">Ładowanie...</td></tr></tbody>
        </table>
    </div>

    <!-- Satisfaction trend chart -->
    <div>
        <div class="chart-label">Trend ocen (12 miesięcy)</div>
        <div style="height:220px"><canvas id="chart-satisfaction-trend"></canvas></div>
    </div>
</div>
```

**5.3 JS in `{% block extra_scripts %}`** — extend `loadTab()` switch to handle `'satysfakcja'`:
```javascript
case 'satysfakcja':
    if (!loaded.satysfakcja) {
        fetch(`/employees/${EMPLOYEE_ID}/analytics/satisfaction?months=12`)
            .then(r => r.json())
            .then(json => {
                if (!json.success) return;
                const d = json.data;
                document.getElementById('sat-avg').textContent =
                    d.avg_score ? `${d.avg_score} ★` : '—';
                document.getElementById('sat-count').textContent = d.total_scored ?? '—';
                // Render distribution text
                document.getElementById('sat-dist').textContent =
                    `★: ${d.distribution[5]||0} | ★★★★: ${d.distribution[4]||0} | ...`;
                // Render by-category table
                renderSatCategoryTable(d.by_service_category);
                // Render trend chart
                renderSatTrendChart(d.monthly_trend);
                loaded.satysfakcja = true;
            });
    }
    break;
```

---

## Phase 6 — Analytics Dashboard: Satisfaction Column

### `templates/analytics/dashboard.html`

In the `#nav-employees` table header (line ~196–204), add column:
```html
<th class="text-right">Satysfakcja</th>
```
Total columns becomes 8.

### `static/js/analytics/dashboard.js`

In the employee table row render function, add after net profit cell:
```javascript
const sat = emp.avg_satisfaction;
const satText = sat ? `${sat.toFixed(1)} ★` : '—';
const satColor = sat >= 4.5 ? 'text-green-600' : sat >= 3.5 ? 'text-amber-500' : sat ? 'text-red-500' : 'text-slate-400';
cells += `<td class="text-right ${satColor} text-sm">${satText}</td>`;
```

---

## Skill Impact Display (in Employee View)

The "Umiejętności" tab already shows `skills` JSON badges (`skill_name — rating/5`).

**Enhancement**: In the same tab, after the manual skills badges, add a computed section: "Ocena klientów wg kategorii" — pulling from satisfaction `by_service_category` data (fetched lazily when the Umiejętności tab loads).

This avoids mutating the manual `employees.skills` JSON while still surfacing the data-driven signal. The display shows:
```
Koloryzacja: ★★★★☆ (4.2 avg, 18 wizyt)
Strzyżenie:  ★★★★★ (4.8 avg, 31 wizyt)
```

In `loadTab('umiejetnosci')`, add a secondary fetch to `/employees/${EMPLOYEE_ID}/analytics/satisfaction?months=12` and render the `by_service_category` list below the existing skills badges.

---

## Verification Steps

1. **Run migration**: `alembic upgrade head` — confirm `satisfaction_score` column exists in `appointments`
2. **Test API (manual)**: `PATCH /api/appointments/<completed_id>/satisfaction` with `{"score": 4}` → 200 OK; with non-completed → 404; with `score: 6` → 400
3. **Test UI — appointment view**: Open a completed appointment, verify star widget appears; click stars, save; refresh and confirm stars are pre-filled
4. **Test employee view — Satysfakcja tab**: Navigate to employee view, click "Satysfakcja" tab; verify KPIs, category table, and trend chart render
5. **Test analytics dashboard**: Change period, confirm "Satysfakcja" column shows values for employees with scored visits; shows "—" for unscored
6. **Edge cases**: Appointments with `status != 'completed'` should NOT show star widget and PATCH should return 404

---

## Implementation Order

```
P1 → Migration (schema + alembic + model)
P2 → Repository (appointment_repo, employee_analytics_repo, analytics_repo)
P3 → API endpoints (appointment_routes, analytics_routes)
P4 → Appointment view star widget
P5 → Employee view Satysfakcja tab
P6 → Analytics dashboard satisfaction column + skill impact in Umiejętności tab
```
