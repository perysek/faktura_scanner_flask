# Rolling 12-Month Trend Charts Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 7 rolling 12-month charts (new clients, cancellation rate, avg ticket, category mix, cost ratio, employee utilisation, visit frequency) in a dedicated "Trendy roczne" section at the bottom of the analytics dashboard.

**Architecture:** Each chart has its own parameterless repository method, API route under `/api/analytics/rolling/*`, and JS load function — all following the pattern established by `loadMonthlyTrend()` in Task 1. The template section appends after the existing service analysis table at the bottom of `{% block content %}`.

**Tech Stack:** Python/Flask, PostgreSQL (psycopg2 with DictCursor), Chart.js (already loaded), Jinja2, TailwindCSS

---

## Task 1: Repository — 7 new methods

**Files:**
- Modify: `repositories/analytics/analytics_repository.py` (append after `get_monthly_profit_trend()`)

**Step 1: Append all 7 methods to the repository class**

Add the following 7 methods at the end of the `AnalyticsRepository` class:

```python
def get_new_clients_monthly(self) -> List[Dict]:
    """Nowi klienci wg miesiąca (first_visit_date) — ostatnie 12 miesięcy."""
    query = """
        WITH months AS (
            SELECT generate_series(
                DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                DATE_TRUNC('month', CURRENT_DATE),
                '1 month'::interval
            )::date AS month_start
        ),
        new_per_month AS (
            SELECT
                DATE_TRUNC('month', first_visit_date)::date AS month_start,
                COUNT(*) AS new_clients
            FROM clients
            WHERE first_visit_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
              AND first_visit_date IS NOT NULL
            GROUP BY DATE_TRUNC('month', first_visit_date)::date
        )
        SELECT
            m.month_start,
            COALESCE(n.new_clients, 0) AS new_clients
        FROM months m
        LEFT JOIN new_per_month n ON n.month_start = m.month_start
        ORDER BY m.month_start
    """
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]

def get_cancellation_rate_monthly(self) -> List[Dict]:
    """Wskaźnik odwołań i nieobecności wg miesiąca — ostatnie 12 miesięcy."""
    query = """
        WITH months AS (
            SELECT generate_series(
                DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                DATE_TRUNC('month', CURRENT_DATE),
                '1 month'::interval
            )::date AS month_start
        ),
        rates_by_month AS (
            SELECT
                DATE_TRUNC('month', appointment_date)::date AS month_start,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled_count,
                COUNT(*) FILTER (WHERE status = 'no_show')   AS noshow_count,
                ROUND(
                    COUNT(*) FILTER (WHERE status = 'cancelled') * 100.0
                    / NULLIF(COUNT(*), 0), 1
                ) AS cancellation_pct,
                ROUND(
                    COUNT(*) FILTER (WHERE status = 'no_show') * 100.0
                    / NULLIF(COUNT(*), 0), 1
                ) AS noshow_pct
            FROM appointments
            WHERE appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
            GROUP BY DATE_TRUNC('month', appointment_date)::date
        )
        SELECT
            m.month_start,
            COALESCE(r.total, 0)             AS total,
            COALESCE(r.cancellation_pct, 0)  AS cancellation_pct,
            COALESCE(r.noshow_pct, 0)        AS noshow_pct
        FROM months m
        LEFT JOIN rates_by_month r ON r.month_start = m.month_start
        ORDER BY m.month_start
    """
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]

def get_avg_ticket_monthly(self) -> List[Dict]:
    """Średni rachunek za wizytę wg miesiąca — ostatnie 12 miesięcy."""
    query = """
        WITH months AS (
            SELECT generate_series(
                DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                DATE_TRUNC('month', CURRENT_DATE),
                '1 month'::interval
            )::date AS month_start
        ),
        avg_by_month AS (
            SELECT
                DATE_TRUNC('month', a.appointment_date)::date AS month_start,
                ROUND(AVG(i.net_amount)::numeric, 2)          AS avg_ticket
            FROM appointments a
            JOIN income_records i ON i.appointment_id = a.id
            WHERE a.status = 'completed'
              AND a.appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
            GROUP BY DATE_TRUNC('month', a.appointment_date)::date
        )
        SELECT
            m.month_start,
            COALESCE(ab.avg_ticket, 0) AS avg_ticket
        FROM months m
        LEFT JOIN avg_by_month ab ON ab.month_start = m.month_start
        ORDER BY m.month_start
    """
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]

def get_service_category_mix_monthly(self) -> List[Dict]:
    """
    Przychód wg kategorii usług i miesiąca — ostatnie 12 miesięcy.
    Zwraca wiersze (month_start, category, revenue) — pivot wykonuje JS.
    """
    query = """
        SELECT
            DATE_TRUNC('month', a.appointment_date)::date AS month_start,
            s.category,
            COALESCE(SUM(aps.price_charged), 0)           AS revenue
        FROM appointments a
        JOIN appointment_services aps ON aps.appointment_id = a.id
        JOIN services s               ON s.id = aps.service_id
        WHERE a.status = 'completed'
          AND a.appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
        GROUP BY DATE_TRUNC('month', a.appointment_date)::date, s.category
        ORDER BY month_start, s.category
    """
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]

def get_invoice_cost_ratio_monthly(self) -> List[Dict]:
    """
    Udział kosztów faktur w przychodach wg miesiąca — ostatnie 12 miesięcy.
    Zwraca: revenue, invoice_costs, ratio_pct.
    """
    query = """
        WITH months AS (
            SELECT generate_series(
                DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                DATE_TRUNC('month', CURRENT_DATE),
                '1 month'::interval
            )::date AS month_start
        ),
        revenue_by_month AS (
            SELECT
                DATE_TRUNC('month', a.appointment_date)::date AS month_start,
                COALESCE(SUM(i.net_amount), 0)                AS revenue
            FROM appointments a
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE a.status = 'completed'
              AND a.appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
            GROUP BY DATE_TRUNC('month', a.appointment_date)::date
        ),
        invoice_by_month AS (
            SELECT
                DATE_TRUNC('month', invoice_date)::date AS month_start,
                COALESCE(SUM(amount), 0)                AS invoice_costs
            FROM invoices
            WHERE invoice_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
            GROUP BY DATE_TRUNC('month', invoice_date)::date
        )
        SELECT
            m.month_start,
            COALESCE(r.revenue, 0)        AS revenue,
            COALESCE(ic.invoice_costs, 0) AS invoice_costs,
            ROUND(
                COALESCE(ic.invoice_costs, 0)
                / NULLIF(COALESCE(r.revenue, 0), 0) * 100,
                1
            ) AS ratio_pct
        FROM months m
        LEFT JOIN revenue_by_month r  ON r.month_start  = m.month_start
        LEFT JOIN invoice_by_month ic ON ic.month_start = m.month_start
        ORDER BY m.month_start
    """
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]

def get_employee_utilisation_monthly(self) -> List[Dict]:
    """
    Wykorzystanie pracowników wg miesiąca — ostatnie 12 miesięcy.
    Formuła: appointments / (22 dni rob. × max_appointments_per_day) × 100.
    Zwraca wiersze (month_start, employee_name, utilisation_pct).
    """
    query = """
        WITH months AS (
            SELECT generate_series(
                DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months'),
                DATE_TRUNC('month', CURRENT_DATE),
                '1 month'::interval
            )::date AS month_start
        ),
        appts_by_month AS (
            SELECT
                DATE_TRUNC('month', appointment_date)::date AS month_start,
                employee_id,
                COUNT(DISTINCT id) AS appointments_count
            FROM appointments
            WHERE status = 'completed'
              AND appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
            GROUP BY DATE_TRUNC('month', appointment_date)::date, employee_id
        )
        SELECT
            m.month_start,
            e.first_name || ' ' || e.last_name         AS employee_name,
            COALESCE(ab.appointments_count, 0)          AS appointments_count,
            COALESCE(e.max_appointments_per_day, 8)     AS max_per_day,
            ROUND(
                COALESCE(ab.appointments_count, 0) * 100.0
                / (22 * COALESCE(e.max_appointments_per_day, 8)),
                1
            ) AS utilisation_pct
        FROM months m
        CROSS JOIN employees e
        LEFT JOIN appts_by_month ab
            ON ab.month_start = m.month_start AND ab.employee_id = e.id
        WHERE e.is_active = TRUE
        ORDER BY m.month_start, employee_name
    """
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]

def get_visit_frequency_distribution(self) -> List[Dict]:
    """
    Histogram częstotliwości wizyt klientów w ostatnich 12 miesiącach.
    Zwraca: [{visit_count, client_count}] — JS grupuje 10+ do jednego kubełka.
    """
    query = """
        WITH client_visits AS (
            SELECT
                client_id,
                COUNT(*) AS visit_count
            FROM appointments
            WHERE status = 'completed'
              AND appointment_date >= CURRENT_DATE - INTERVAL '12 months'
            GROUP BY client_id
        )
        SELECT
            visit_count,
            COUNT(*) AS client_count
        FROM client_visits
        GROUP BY visit_count
        ORDER BY visit_count
    """
    conn = DatabaseConnection.get_connection()
    cursor = conn.cursor()
    cursor.execute(query)
    return [dict(row) for row in cursor.fetchall()]
```

**Step 2: Verify methods exist**

```bash
grep -n "def get_new_clients_monthly\|def get_cancellation_rate\|def get_avg_ticket\|def get_service_category_mix\|def get_invoice_cost_ratio\|def get_employee_utilisation\|def get_visit_frequency" repositories/analytics/analytics_repository.py
```

Expected: 7 lines, one per method.

**Step 3: Commit**

```bash
git add repositories/analytics/analytics_repository.py
git commit -m "feat(analytics): add 7 rolling 12-month repository methods"
```

---

## Task 2: API Routes — 7 new endpoints

**Files:**
- Modify: `routes/analytics_routes.py` (add before the final `get_insights` route)

**Step 1: Add all 7 routes**

Insert these routes **before** the existing `@analytics_bp.route('/analytics/insights')` line:

```python
@analytics_bp.route('/analytics/rolling/new-clients', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_rolling_new_clients():
    """Nowi klienci wg miesiąca — ruchome okno 12M"""
    months = repo.get_new_clients_monthly()
    return jsonify({"success": True, "months": months})


@analytics_bp.route('/analytics/rolling/cancellation-rate', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_rolling_cancellation_rate():
    """Wskaźnik odwołań/nieobecności — ruchome okno 12M"""
    months = repo.get_cancellation_rate_monthly()
    return jsonify({"success": True, "months": months})


@analytics_bp.route('/analytics/rolling/avg-ticket', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_rolling_avg_ticket():
    """Średni rachunek — ruchome okno 12M"""
    months = repo.get_avg_ticket_monthly()
    return jsonify({"success": True, "months": months})


@analytics_bp.route('/analytics/rolling/category-mix', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_rolling_category_mix():
    """Mix kategorii usług — ruchome okno 12M"""
    rows = repo.get_service_category_mix_monthly()
    return jsonify({"success": True, "rows": rows})


@analytics_bp.route('/analytics/rolling/cost-ratio', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_rolling_cost_ratio():
    """Udział kosztów faktur w przychodach — ruchome okno 12M"""
    months = repo.get_invoice_cost_ratio_monthly()
    return jsonify({"success": True, "months": months})


@analytics_bp.route('/analytics/rolling/employee-utilisation', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_rolling_employee_utilisation():
    """Wykorzystanie pracowników — ruchome okno 12M"""
    rows = repo.get_employee_utilisation_monthly()
    return jsonify({"success": True, "rows": rows})


@analytics_bp.route('/analytics/rolling/visit-frequency', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_rolling_visit_frequency():
    """Histogram częstotliwości wizyt klientów — ostatnie 12M"""
    distribution = repo.get_visit_frequency_distribution()
    return jsonify({"success": True, "distribution": distribution})
```

**Step 2: Smoke-test each endpoint**

Start the app (`python app.py`) and in a browser (logged in) visit:
- `http://localhost:5000/api/analytics/rolling/new-clients`
- `http://localhost:5000/api/analytics/rolling/cancellation-rate`
- `http://localhost:5000/api/analytics/rolling/avg-ticket`
- `http://localhost:5000/api/analytics/rolling/category-mix`
- `http://localhost:5000/api/analytics/rolling/cost-ratio`
- `http://localhost:5000/api/analytics/rolling/employee-utilisation`
- `http://localhost:5000/api/analytics/rolling/visit-frequency`

Each should return `{"success": true, ...}` with data or empty arrays. No 500 errors.

**Step 3: Commit**

```bash
git add routes/analytics_routes.py
git commit -m "feat(analytics): add 7 rolling trend API routes"
```

---

## Task 3: Template — "Trendy roczne" section

**Files:**
- Modify: `templates/analytics/dashboard.html` (append before closing `{% endblock %}`)

**Step 1: Find the end of the current content block**

```bash
grep -n "endblock\|{% endblock" templates/analytics/dashboard.html
```

Note the last line number of the template.

**Step 2: Append the new section**

Add the following HTML just **before** `{% endblock %}` at the end of the file:

```html
<!-- ═══════════════════════════════════════════════
     Trendy roczne (ruchome okno 12 miesięcy)
     ═══════════════════════════════════════════════ -->
<div class="mt-8 mb-4">
    <h2 class="text-xl font-semibold text-slate-800">Trendy roczne</h2>
    <p class="text-xs text-slate-400 mt-0.5">Wszystkie wykresy poniżej — ruchome okno 12 miesięcy, niezależne od wybranego okresu</p>
</div>

<!-- Row 1: New clients + Cancellation/no-show rate -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
    <div class="refined-card">
        <h3 class="text-lg font-medium mb-1">Nowi klienci / miesiąc</h3>
        <p class="text-xs text-slate-400 mb-4">Czy salon rośnie?</p>
        <div style="height: 280px;">
            <canvas id="newClientsChart"></canvas>
        </div>
    </div>
    <div class="refined-card">
        <h3 class="text-lg font-medium mb-1">Wskaźnik odwołań i nieobecności</h3>
        <p class="text-xs text-slate-400 mb-4">Czy niezawodność rezerwacji rośnie?</p>
        <div style="height: 280px;">
            <canvas id="cancellationRateChart"></canvas>
        </div>
    </div>
</div>

<!-- Row 2: Avg ticket + Invoice cost ratio -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
    <div class="refined-card">
        <h3 class="text-lg font-medium mb-1">Średni rachunek / miesiąc</h3>
        <p class="text-xs text-slate-400 mb-4">Czy wartość wizyty rośnie?</p>
        <div style="height: 280px;">
            <canvas id="avgTicketChart"></canvas>
        </div>
    </div>
    <div class="refined-card">
        <h3 class="text-lg font-medium mb-1">Udział kosztów faktur w przychodzie</h3>
        <p class="text-xs text-slate-400 mb-4">Czy koszty dostawców pochłaniają więcej przychodu?</p>
        <div style="height: 280px;">
            <canvas id="costRatioChart"></canvas>
        </div>
    </div>
</div>

<!-- Row 3: Service category mix (full width stacked bar) -->
<div class="refined-card mb-6">
    <h3 class="text-lg font-medium mb-1">Mix kategorii usług / miesiąc</h3>
    <p class="text-xs text-slate-400 mb-4">Które kategorie rosną, a które zanikają?</p>
    <div style="height: 320px;">
        <canvas id="categoryMixChart"></canvas>
    </div>
</div>

<!-- Row 4: Employee utilisation (full width multi-line) -->
<div class="refined-card mb-6">
    <h3 class="text-lg font-medium mb-1">Wykorzystanie pracowników / miesiąc</h3>
    <p class="text-xs text-slate-400 mb-4">Kto jest przeciążony, a kto niedociążony? (22 dni rob. × max wizyt/dzień)</p>
    <div style="height: 320px;">
        <canvas id="employeeUtilisationChart"></canvas>
    </div>
</div>

<!-- Row 5: Visit frequency histogram (full width) -->
<div class="refined-card mb-6">
    <h3 class="text-lg font-medium mb-1">Częstotliwość wizyt klientów</h3>
    <p class="text-xs text-slate-400 mb-4">Ilu klientów odwiedziło salon 1×, 2×, 3×… w ostatnich 12 miesiącach</p>
    <div style="height: 280px;">
        <canvas id="visitFrequencyChart"></canvas>
    </div>
</div>
```

**Step 3: Verify canvases exist**

```bash
grep -c "canvas id=" templates/analytics/dashboard.html
```

Expected: at least 12 (5 existing + 7 new).

**Step 4: Commit**

```bash
git add templates/analytics/dashboard.html
git commit -m "feat(analytics): add Trendy roczne template section with 7 canvases"
```

---

## Task 4: JS — Chart vars + Promise.all extension

**Files:**
- Modify: `static/js/analytics/dashboard.js`

**Step 1: Add 7 chart instance variables**

Find the existing block (around line 11):
```js
let revenueTrendChart = null;
let servicesChart = null;
let clientSplitChart = null;
let profitBreakdownChart = null;
let monthlyTrendChart = null;
```

Add after `monthlyTrendChart`:
```js
let newClientsChart = null;
let cancellationRateChart = null;
let avgTicketChart = null;
let categoryMixChart = null;
let costRatioChart = null;
let employeeUtilisationChart = null;
let visitFrequencyChart = null;
```

**Step 2: Extend the Promise.all in `loadDashboard()`**

Find (around line 132):
```js
        await Promise.all([
            loadSummary(),
            loadRevenueTrend(),
            loadEmployees(),
            loadServices(),
            loadClients(),
            loadProfit(),
            loadInsights(),
            loadOccupancy(),
            loadPeakHours(),
            loadServiceAnalysis(),
            loadMonthlyTrend()
        ]);
```

Replace with:
```js
        await Promise.all([
            loadSummary(),
            loadRevenueTrend(),
            loadEmployees(),
            loadServices(),
            loadClients(),
            loadProfit(),
            loadInsights(),
            loadOccupancy(),
            loadPeakHours(),
            loadServiceAnalysis(),
            loadMonthlyTrend(),
            loadNewClients(),
            loadCancellationRate(),
            loadAvgTicket(),
            loadCategoryMix(),
            loadCostRatio(),
            loadEmployeeUtilisation(),
            loadVisitFrequency()
        ]);
```

**Step 3: Commit**

```bash
git add static/js/analytics/dashboard.js
git commit -m "feat(analytics): add chart vars and extend Promise.all for 7 rolling charts"
```

---

## Task 5: JS — `loadNewClients()` + `loadCancellationRate()`

**Files:**
- Modify: `static/js/analytics/dashboard.js` (append before final `}` of the file)

**Step 1: Add `loadNewClients()`**

```js
async function loadNewClients() {
    const response = await fetch('/api/analytics/rolling/new-clients');
    const data = await response.json();
    const ctx = document.getElementById('newClientsChart');
    if (!ctx || !data.success) return;

    if (newClientsChart) newClientsChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];
    const labels = data.months.map(m => {
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    newClientsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Nowi klienci',
                data: data.months.map(m => m.new_clients),
                borderColor: 'rgba(22, 163, 74, 1)',
                backgroundColor: 'rgba(22, 163, 74, 0.1)',
                borderWidth: 2,
                pointRadius: 4,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Nowi klienci: ${ctx.parsed.y}`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true, ticks: { stepSize: 1 } }
            }
        }
    });
}
```

**Step 2: Add `loadCancellationRate()`**

```js
async function loadCancellationRate() {
    const response = await fetch('/api/analytics/rolling/cancellation-rate');
    const data = await response.json();
    const ctx = document.getElementById('cancellationRateChart');
    if (!ctx || !data.success) return;

    if (cancellationRateChart) cancellationRateChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];
    const labels = data.months.map(m => {
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    cancellationRateChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Odwołania',
                    data: data.months.map(m => m.cancellation_pct),
                    borderColor: 'rgba(234, 88, 12, 1)',
                    backgroundColor: 'rgba(234, 88, 12, 0.08)',
                    borderWidth: 2,
                    pointRadius: 4,
                    fill: false,
                    tension: 0.3
                },
                {
                    label: 'Nieobecności',
                    data: data.months.map(m => m.noshow_pct),
                    borderColor: 'rgba(239, 68, 68, 1)',
                    backgroundColor: 'rgba(239, 68, 68, 0.08)',
                    borderWidth: 2,
                    pointRadius: 4,
                    fill: false,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val}%` }
                }
            }
        }
    });
}
```

**Step 3: Commit**

```bash
git add static/js/analytics/dashboard.js
git commit -m "feat(analytics): add loadNewClients and loadCancellationRate charts"
```

---

## Task 6: JS — `loadAvgTicket()` + `loadCostRatio()`

**Files:**
- Modify: `static/js/analytics/dashboard.js` (append to end of file)

**Step 1: Add `loadAvgTicket()`**

```js
async function loadAvgTicket() {
    const response = await fetch('/api/analytics/rolling/avg-ticket');
    const data = await response.json();
    const ctx = document.getElementById('avgTicketChart');
    if (!ctx || !data.success) return;

    if (avgTicketChart) avgTicketChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];
    const labels = data.months.map(m => {
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    avgTicketChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Średni rachunek',
                data: data.months.map(m => m.avg_ticket),
                borderColor: 'rgba(37, 99, 235, 1)',
                backgroundColor: 'rgba(37, 99, 235, 0.08)',
                borderWidth: 2,
                pointRadius: 4,
                fill: false,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Średni rachunek: ${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val.toLocaleString('pl-PL')} zł` }
                }
            }
        }
    });
}
```

**Step 2: Add `loadCostRatio()` — dual-axis mixed chart**

```js
async function loadCostRatio() {
    const response = await fetch('/api/analytics/rolling/cost-ratio');
    const data = await response.json();
    const ctx = document.getElementById('costRatioChart');
    if (!ctx || !data.success) return;

    if (costRatioChart) costRatioChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];
    const labels = data.months.map(m => {
        const [y, mo] = m.month_start.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    costRatioChart = new Chart(ctx, {
        data: {
            labels,
            datasets: [
                {
                    type: 'bar',
                    label: 'Przychód',
                    data: data.months.map(m => m.revenue),
                    backgroundColor: 'rgba(37, 99, 235, 0.5)',
                    borderColor: 'rgba(37, 99, 235, 1)',
                    borderWidth: 1,
                    yAxisID: 'yPLN',
                    order: 2
                },
                {
                    type: 'line',
                    label: 'Udział faktur (%)',
                    data: data.months.map(m => m.ratio_pct),
                    borderColor: 'rgba(239, 68, 68, 1)',
                    backgroundColor: 'rgba(239, 68, 68, 0.08)',
                    borderWidth: 2,
                    pointRadius: 4,
                    fill: false,
                    tension: 0.3,
                    yAxisID: 'yPct',
                    order: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => ctx.dataset.yAxisID === 'yPct'
                            ? `${ctx.dataset.label}: ${ctx.parsed.y ?? 0}%`
                            : `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                yPLN: {
                    type: 'linear',
                    position: 'left',
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val.toLocaleString('pl-PL')} zł` }
                },
                yPct: {
                    type: 'linear',
                    position: 'right',
                    beginAtZero: true,
                    grid: { drawOnChartArea: false },
                    ticks: { callback: (val) => `${val}%` }
                }
            }
        }
    });
}
```

**Step 3: Commit**

```bash
git add static/js/analytics/dashboard.js
git commit -m "feat(analytics): add loadAvgTicket and loadCostRatio charts"
```

---

## Task 7: JS — `loadCategoryMix()`

**Files:**
- Modify: `static/js/analytics/dashboard.js` (append to end of file)

**Step 1: Add `loadCategoryMix()`**

The API returns unpivoted rows `[{month_start, category, revenue}]`. This function generates the 12-month label array from today (matching the other rolling charts) and pivots the data into per-category datasets.

```js
async function loadCategoryMix() {
    const response = await fetch('/api/analytics/rolling/category-mix');
    const data = await response.json();
    const ctx = document.getElementById('categoryMixChart');
    if (!ctx || !data.success) return;

    if (categoryMixChart) categoryMixChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];

    // Generate 12 month keys from today backwards (local time, no UTC shift)
    const today = new Date();
    const monthKeys = [];
    for (let i = 11; i >= 0; i--) {
        const d = new Date(today.getFullYear(), today.getMonth() - i, 1);
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        monthKeys.push(`${d.getFullYear()}-${mm}-01`);
    }
    const labels = monthKeys.map(k => {
        const [y, mo] = k.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    // Collect unique categories from response
    const categories = [...new Set(data.rows.map(r => r.category))].sort();

    // Build lookup: month_start_prefix → category → revenue
    // month_start from DB may be "2026-03-01", key format must match monthKeys
    const lookup = {};
    data.rows.forEach(r => {
        // Normalise key: take YYYY-MM from month_start and append -01
        const key = r.month_start.substring(0, 7) + '-01';
        if (!lookup[key]) lookup[key] = {};
        lookup[key][r.category] = parseFloat(r.revenue);
    });

    const CATEGORY_COLORS = [
        'rgba(37,99,235,0.8)',   'rgba(22,163,74,0.8)',  'rgba(234,88,12,0.8)',
        'rgba(168,85,247,0.8)', 'rgba(236,72,153,0.8)', 'rgba(20,184,166,0.8)',
        'rgba(245,158,11,0.8)', 'rgba(239,68,68,0.8)',  'rgba(100,116,139,0.8)',
        'rgba(14,165,233,0.8)'
    ];

    const datasets = categories.map((cat, i) => ({
        label: cat,
        data: monthKeys.map(k => (lookup[k] && lookup[k][cat]) || 0),
        backgroundColor: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
        borderWidth: 0
    }));

    categoryMixChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: { stacked: true, grid: { display: false } },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val.toLocaleString('pl-PL')} zł` }
                }
            }
        }
    });
}
```

**Step 2: Commit**

```bash
git add static/js/analytics/dashboard.js
git commit -m "feat(analytics): add loadCategoryMix stacked bar chart"
```

---

## Task 8: JS — `loadEmployeeUtilisation()`

**Files:**
- Modify: `static/js/analytics/dashboard.js` (append to end of file)

**Step 1: Add `loadEmployeeUtilisation()`**

The API returns rows `[{month_start, employee_name, utilisation_pct}]`. This function pivots into one dataset per employee.

```js
async function loadEmployeeUtilisation() {
    const response = await fetch('/api/analytics/rolling/employee-utilisation');
    const data = await response.json();
    const ctx = document.getElementById('employeeUtilisationChart');
    if (!ctx || !data.success) return;

    if (employeeUtilisationChart) employeeUtilisationChart.destroy();

    const PL_MONTHS = ['Sty','Lut','Mar','Kwi','Maj','Cze','Lip','Sie','Wrz','Paź','Lis','Gru'];

    // Collect unique sorted months from response
    const monthKeys = [...new Set(data.rows.map(r => r.month_start))].sort();
    const labels = monthKeys.map(k => {
        const [y, mo] = k.split('-').map(Number);
        return `${PL_MONTHS[mo - 1]} ${y}`;
    });

    const employees = [...new Set(data.rows.map(r => r.employee_name))].sort();

    // Build lookup: employee → month_start → utilisation_pct
    const lookup = {};
    data.rows.forEach(r => {
        if (!lookup[r.employee_name]) lookup[r.employee_name] = {};
        lookup[r.employee_name][r.month_start] = parseFloat(r.utilisation_pct);
    });

    const EMP_COLORS = [
        'rgba(37,99,235,1)',  'rgba(22,163,74,1)',  'rgba(234,88,12,1)',
        'rgba(168,85,247,1)', 'rgba(236,72,153,1)', 'rgba(20,184,166,1)',
        'rgba(245,158,11,1)', 'rgba(100,116,139,1)'
    ];

    const datasets = employees.map((emp, i) => ({
        label: emp,
        data: monthKeys.map(k => (lookup[emp] && lookup[emp][k]) || 0),
        borderColor: EMP_COLORS[i % EMP_COLORS.length],
        backgroundColor: EMP_COLORS[i % EMP_COLORS.length].replace(',1)', ',0.08)'),
        borderWidth: 2,
        pointRadius: 3,
        fill: false,
        tension: 0.3
    }));

    employeeUtilisationChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%`
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: (val) => `${val}%` }
                }
            }
        }
    });
}
```

**Step 2: Commit**

```bash
git add static/js/analytics/dashboard.js
git commit -m "feat(analytics): add loadEmployeeUtilisation multi-line chart"
```

---

## Task 9: JS — `loadVisitFrequency()`

**Files:**
- Modify: `static/js/analytics/dashboard.js` (append to end of file)

**Step 1: Add `loadVisitFrequency()`**

```js
async function loadVisitFrequency() {
    const response = await fetch('/api/analytics/rolling/visit-frequency');
    const data = await response.json();
    const ctx = document.getElementById('visitFrequencyChart');
    if (!ctx || !data.success) return;

    if (visitFrequencyChart) visitFrequencyChart.destroy();

    // Build buckets 1 through 10+ (anything >= 10 merged into one bucket)
    const MAX_BUCKET = 10;
    const buckets = {};
    data.distribution.forEach(d => {
        const key = parseInt(d.visit_count) >= MAX_BUCKET ? MAX_BUCKET : parseInt(d.visit_count);
        buckets[key] = (buckets[key] || 0) + parseInt(d.client_count);
    });

    const labels = [];
    const values = [];
    for (let i = 1; i <= MAX_BUCKET; i++) {
        labels.push(i === MAX_BUCKET ? `${MAX_BUCKET}+` : String(i));
        values.push(buckets[i] || 0);
    }

    visitFrequencyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Klienci',
                data: values,
                backgroundColor: 'rgba(37, 99, 235, 0.75)',
                borderColor: 'rgba(37, 99, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Klienci: ${ctx.parsed.y}`,
                        title: (items) => {
                            const v = items[0].label;
                            return v === '10+' ? '10 lub więcej wizyt' : `${v} ${v === '1' ? 'wizyta' : 'wizyty'}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    title: { display: true, text: 'Liczba wizyt w ostatnich 12 miesiącach' }
                },
                y: { beginAtZero: true, ticks: { stepSize: 1 } }
            }
        }
    });
}
```

**Step 2: Commit**

```bash
git add static/js/analytics/dashboard.js
git commit -m "feat(analytics): add loadVisitFrequency histogram chart"
```

---

## Task 10: CSS Rebuild + End-to-End Verification

**Step 1: Rebuild TailwindCSS**

```bash
npm run build:css
```

Expected output: `Done in NNNNms.`

**Step 2: Start the app**

```bash
python app.py
```

Navigate to `http://localhost:5000/analytics`.

**Step 3: Verify all 7 new charts render**

Check each one:
- [ ] "Nowi klienci / miesiąc" — green line chart, 12 month x-axis
- [ ] "Wskaźnik odwołań i nieobecności" — two lines (amber + red), % y-axis
- [ ] "Średni rachunek / miesiąc" — blue line, PLN y-axis
- [ ] "Udział kosztów faktur w przychodzie" — blue bars + red line, dual y-axis
- [ ] "Mix kategorii usług / miesiąc" — stacked bar, one color per category, legend at bottom
- [ ] "Wykorzystanie pracowników / miesiąc" — one line per employee
- [ ] "Częstotliwość wizyt klientów" — bar histogram, x-axis "1" through "10+"

**Step 4: Verify period switching does NOT affect the new section**

Change the period selector (e.g., "Ostatni miesiąc") — the 7 new charts must stay unchanged.

**Step 5: Check browser console for errors**

Open DevTools → Console. Should be no JS errors.

**Step 6: Commit CSS + final commit**

```bash
git add static/css/output.css
git commit -m "chore: rebuild TailwindCSS after rolling trends section"
```

---

## Summary of Changes

| File | Changes |
|------|---------|
| `repositories/analytics/analytics_repository.py` | +7 methods |
| `routes/analytics_routes.py` | +7 routes under `/api/analytics/rolling/*` |
| `templates/analytics/dashboard.html` | +1 section, 7 canvases |
| `static/js/analytics/dashboard.js` | +7 chart vars, extended Promise.all, +7 load functions |
| `static/css/output.css` | Rebuilt by TailwindCSS |
