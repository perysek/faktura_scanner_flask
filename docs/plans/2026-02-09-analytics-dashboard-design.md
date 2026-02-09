# Analytics Dashboard Design
**Date**: 2026-02-09
**Status**: Design Complete - Ready for Implementation
**Phase**: Phase 5 - Business Intelligence & Analytics

---

## 1. Overview

### Purpose
Provide salon owners and managers with comprehensive business intelligence through visual dashboards. Enable data-driven decisions by surfacing key metrics across revenue, employee performance, service popularity, and client behavior.

### Scope
- **Revenue Analytics**: Trends, period comparisons, KPIs
- **Employee Performance**: Revenue generated, employment costs (Polish ZUS/tax model), profitability analysis
- **Service Insights**: Revenue by service type, popularity metrics
- **Client Metrics**: New vs. returning, retention rates, at-risk client alerts

### Out of Scope (Future Phases)
- Forecasting / predictive analytics
- Custom report builder
- Automated email reports
- Drill-down capabilities (click chart to see details)

---

## 2. Architecture

### High-Level Flow
```
Browser Request
    ↓
GET /analytics (main_routes.py)
    ↓
Renders analytics/dashboard.html
    ↓
JavaScript fetches data from API endpoints:
    - GET /api/analytics/summary
    - GET /api/analytics/revenue-trend
    - GET /api/analytics/employees
    - GET /api/analytics/services
    - GET /api/analytics/clients
    ↓
AnalyticsRepository executes SQL queries
    ↓
Returns JSON with metrics
    ↓
Chart.js renders visualizations
```

### Technology Stack
- **Backend**: Flask + SQLite (SQL-first approach)
- **Frontend**: Vanilla JavaScript + Chart.js 4.x
- **Styling**: Tailwind CSS (Refined Minimal design system)
- **Icons**: Material Icons

### Design Approach: SQL-First Analytics
**Rationale**: Direct SQL queries rather than ORM or database views
- Dynamic date ranges (this month, last month, custom)
- Parameterized queries more flexible than static views
- SQLite is fast enough for modest data volumes (thousands of appointments)
- Can add caching layer later if needed

**Trade-offs**:
- ✅ Fast queries (database-optimized aggregations)
- ✅ Easy to cache results
- ✅ Clean separation of concerns
- ❌ SQLite date function limitations (work around with Python datetime)
- ❌ Complex SQL for advanced metrics (retention rate)

---

## 3. Database Layer

### New Migration Required
Add employer cost tracking to employees table:

```sql
ALTER TABLE employees
ADD COLUMN employer_cost_rate NUMERIC(5,4) DEFAULT 0.22;
```

**Purpose**: Configurable employer cost rate per employee (default 22% for Polish ZUS/taxes/benefits)

### Key SQL Queries

#### 3.1 Revenue Summary
```sql
SELECT
    COUNT(DISTINCT a.id) as total_appointments,
    COUNT(DISTINCT a.client_id) as unique_clients,
    COALESCE(SUM(i.net_amount), 0) as total_revenue,
    COALESCE(AVG(i.net_amount), 0) as avg_ticket,
    COALESCE(SUM(i.commission_total), 0) as total_commissions
FROM appointments a
LEFT JOIN income_records i ON i.appointment_id = a.id
WHERE a.status = 'completed'
    AND a.appointment_date BETWEEN ? AND ?
```

#### 3.2 Revenue Trend (Daily Aggregation)
```sql
SELECT
    a.appointment_date as date,
    COUNT(a.id) as appointments,
    COALESCE(SUM(i.net_amount), 0) as revenue
FROM appointments a
LEFT JOIN income_records i ON i.appointment_id = a.id
WHERE a.status = 'completed'
    AND a.appointment_date BETWEEN ? AND ?
GROUP BY a.appointment_date
ORDER BY a.appointment_date
```

#### 3.3 Employee Performance (with Polish Cost Model)
```sql
SELECT
    e.id,
    e.first_name || ' ' || e.last_name as employee_name,
    e.base_salary,
    COALESCE(e.employer_cost_rate, 0.22) as cost_rate,
    COUNT(a.id) as appointments_count,
    COALESCE(SUM(i.net_amount), 0) as revenue_generated,
    COALESCE(SUM(i.commission_total), 0) as commission_earned,

    -- Cost calculation
    (e.base_salary + COALESCE(SUM(i.commission_total), 0)) as gross_salary,
    (e.base_salary + COALESCE(SUM(i.commission_total), 0)) * (1 + COALESCE(e.employer_cost_rate, 0.22)) as total_employer_cost,

    -- Profitability
    COALESCE(SUM(i.net_amount), 0) - ((e.base_salary + COALESCE(SUM(i.commission_total), 0)) * (1 + COALESCE(e.employer_cost_rate, 0.22))) as net_profit
FROM employees e
LEFT JOIN appointments a ON a.employee_id = e.id AND a.status = 'completed'
LEFT JOIN income_records i ON i.appointment_id = a.id
WHERE e.is_active = 1
    AND (a.appointment_date BETWEEN ? AND ? OR a.appointment_date IS NULL)
GROUP BY e.id, e.first_name, e.last_name, e.base_salary, e.employer_cost_rate
ORDER BY revenue_generated DESC
```

**Polish Employment Cost Breakdown** (22% employer rate):
- Employer ZUS: ~19.48% (pension 9.76% + disability 6.5% + other 3.22%)
- Work accident insurance: ~1.67%
- Labor Fund (Fundusz Pracy): 2.45%
- FGŚP (Fundusz Gwarantowanych Świadczeń Pracowniczych): 0.10%
- **Total**: ~22% on top of gross salary

**Total Employer Cost** = (Base Salary + Commission) × 1.22

#### 3.4 Service Breakdown
```sql
SELECT
    s.name as service_name,
    s.category,
    COUNT(aps.id) as times_booked,
    COALESCE(SUM(aps.price_charged), 0) as revenue_generated
FROM services s
LEFT JOIN appointment_services aps ON aps.service_id = s.id
LEFT JOIN appointments a ON a.id = aps.appointment_id
WHERE a.status = 'completed'
    AND a.appointment_date BETWEEN ? AND ?
GROUP BY s.id, s.name, s.category
ORDER BY revenue_generated DESC
```

#### 3.5 Client Metrics

**New vs. Returning Clients**:
```sql
SELECT
    COUNT(DISTINCT CASE
        WHEN c.first_visit_date >= ? THEN c.id
    END) as new_clients,
    COUNT(DISTINCT CASE
        WHEN c.first_visit_date < ? THEN c.id
    END) as returning_clients
FROM clients c
INNER JOIN appointments a ON a.client_id = c.id
WHERE a.status = 'completed'
    AND a.appointment_date BETWEEN ? AND ?
```

**Client Retention Rate** (90-day window):
```sql
WITH client_visits AS (
    SELECT
        client_id,
        appointment_date,
        LAG(appointment_date) OVER (PARTITION BY client_id ORDER BY appointment_date) as prev_visit
    FROM appointments
    WHERE status = 'completed'
)
SELECT
    COUNT(CASE WHEN julianday(appointment_date) - julianday(prev_visit) <= 90 THEN 1 END) * 100.0 / COUNT(*) as retention_rate
FROM client_visits
WHERE prev_visit IS NOT NULL
    AND appointment_date BETWEEN ? AND ?
```

**At-Risk Clients** (90+ days since last visit):
```sql
SELECT
    c.id,
    c.first_name || ' ' || c.last_name as client_name,
    c.last_visit_date,
    julianday('now') - julianday(c.last_visit_date) as days_since_visit
FROM clients c
WHERE c.is_active = 1
    AND c.last_visit_date < date('now', '-90 days')
ORDER BY c.last_visit_date ASC
LIMIT 20
```

---

## 4. Time Period Handling

### Date Range Helper (AnalyticsRepository)

```python
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

def get_date_ranges(self, period: str, reference_date: date = None):
    """
    Returns (current_start, current_end, previous_start, previous_end)

    Supported periods:
    - 'current_month': This month vs. last month
    - 'last_month': Last month vs. month before that
    - 'current_year': Year-to-date vs. same period last year
    - 'custom': Requires explicit start/end dates
    """
    ref = reference_date or date.today()

    if period == 'current_month':
        current_start = ref.replace(day=1)
        current_end = (current_start + relativedelta(months=1)) - timedelta(days=1)
        previous_start = current_start - relativedelta(months=1)
        previous_end = current_start - timedelta(days=1)

    elif period == 'last_month':
        current_start = (ref.replace(day=1) - relativedelta(months=1))
        current_end = ref.replace(day=1) - timedelta(days=1)
        previous_start = current_start - relativedelta(months=1)
        previous_end = current_start - timedelta(days=1)

    elif period == 'current_year':
        current_start = ref.replace(month=1, day=1)
        current_end = ref
        previous_start = current_start - relativedelta(years=1)
        previous_end = ref - relativedelta(years=1)

    return (current_start, current_end, previous_start, previous_end)
```

### Frontend Period Selector
```html
<div class="period-selector">
    <button data-period="current_month" class="active">Ten miesiąc</button>
    <button data-period="last_month">Ostatni miesiąc</button>
    <button data-period="current_year">Rok do daty</button>
    <button data-period="custom">Własny zakres</button>
</div>
```

**Display Format**:
- Absolute values: "15,450 zł revenue this month"
- Comparison: "+12.5% vs. last month" (green) or "-8.2% vs. last month" (red)

---

## 5. API Endpoints

### Analytics Blueprint (`routes/analytics_routes.py`)

#### 5.1 GET /api/analytics/summary
**Purpose**: High-level KPIs for selected period

**Query Parameters**:
- `period`: 'current_month' | 'last_month' | 'current_year' | 'custom'
- `start_date`: YYYY-MM-DD (required if period=custom)
- `end_date`: YYYY-MM-DD (required if period=custom)

**Response**:
```json
{
    "success": true,
    "period": "current_month",
    "current": {
        "start_date": "2026-02-01",
        "end_date": "2026-02-28",
        "total_revenue": 45600.00,
        "total_appointments": 124,
        "unique_clients": 87,
        "avg_ticket": 367.74,
        "total_commissions": 18240.00
    },
    "previous": {
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "total_revenue": 40500.00,
        "total_appointments": 115,
        "unique_clients": 76,
        "avg_ticket": 352.17,
        "total_commissions": 16200.00
    },
    "change": {
        "revenue_pct": 12.5,
        "appointments_pct": 7.8,
        "clients_pct": 14.5,
        "avg_ticket_pct": 4.4,
        "commissions_pct": 12.6
    }
}
```

#### 5.2 GET /api/analytics/revenue-trend
**Purpose**: Daily/weekly revenue data for line charts

**Response**:
```json
{
    "success": true,
    "period": "current_month",
    "data": [
        {"date": "2026-02-01", "revenue": 1200.00, "appointments": 5},
        {"date": "2026-02-02", "revenue": 1450.00, "appointments": 6},
        ...
    ],
    "summary": {
        "total": 45600.00,
        "avg_daily": 1628.57
    }
}
```

#### 5.3 GET /api/analytics/employees
**Purpose**: Employee performance with cost analysis

**Response**:
```json
{
    "success": true,
    "period": "current_month",
    "employees": [
        {
            "id": 1,
            "name": "Anna Kowalska",
            "appointments_count": 45,
            "revenue_generated": 18500.00,
            "commission_earned": 8325.00,
            "base_salary": 4000.00,
            "gross_salary": 12325.00,
            "employer_cost_rate": 0.22,
            "total_employer_cost": 15036.50,
            "net_profit": 3463.50
        },
        ...
    ]
}
```

#### 5.4 GET /api/analytics/services
**Purpose**: Service breakdown for charts

**Response**:
```json
{
    "success": true,
    "period": "current_month",
    "services": [
        {
            "name": "Koloryzacja",
            "category": "Włosy",
            "times_booked": 42,
            "revenue": 12500.00
        },
        ...
    ]
}
```

#### 5.5 GET /api/analytics/clients
**Purpose**: Client metrics and retention

**Response**:
```json
{
    "success": true,
    "period": "current_month",
    "metrics": {
        "new_clients": 25,
        "returning_clients": 62,
        "retention_rate": 78.5,
        "avg_visits_per_client": 1.42
    },
    "at_risk": [
        {
            "id": 15,
            "name": "Jan Nowak",
            "last_visit": "2025-11-10",
            "days_since": 91
        },
        ...
    ]
}
```

**Authorization**: All endpoints require `@login_required` and `@module_permission_required('appointments')`

---

## 6. Frontend Implementation

### 6.1 Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│ ANALYTICS DASHBOARD                           [Period ▼]    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│ │ Revenue  │  │Appoint.  │  │ Clients  │  │Avg Ticket│    │
│ │ 45,600zł │  │   124    │  │    87    │  │  367zł   │    │
│ │ +12.5% ↑ │  │ +7.8% ↑  │  │+14.5% ↑  │  │ +4.4% ↑  │    │
│ └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ ┌─────────────────────────────────┐ ┌────────────────────┐ │
│ │  Revenue Trend (Line Chart)     │ │ Services           │ │
│ │                                  │ │ (Horizontal Bar)   │ │
│ │  [Daily revenue over period]    │ │                    │ │
│ │                                  │ │ Koloryzacja  ████ │ │
│ │                                  │ │ Strzyżenie   ███  │ │
│ └─────────────────────────────────┘ │ Balayage     ██   │ │
│                                      └────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  Employee Performance (Table)                           │ │
│ │  ───────────────────────────────────────────────────    │ │
│ │  Name      Appt  Revenue   Comm.   Cost    Profit      │ │
│ │  Anna K.   45    18,500zł  8,325zł 15,037zł +3,463zł   │ │
│ │  Marta W.  38    14,200zł  5,680zł 11,208zł +2,992zł   │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                               │
│ ┌─────────────────────────┐ ┌───────────────────────────┐  │
│ │ Client Split (Doughnut) │ │ At-Risk Clients           │  │
│ │                         │ │                           │  │
│ │  New: 35%               │ │ 12 clients haven't        │  │
│ │  Returning: 65%         │ │ visited in 90+ days       │  │
│ │                         │ │ [View List →]             │  │
│ └─────────────────────────┘ └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Chart.js Configuration

**Color Palette** (Refined Minimal):
```javascript
const CHART_COLORS = {
    primary: '#2563eb',    // Blue
    purple: '#7c3aed',
    pink: '#db2777',
    orange: '#ea580c',
    green: '#65a30d',
    gray: '#e2e8f0'
};
```

**Revenue Trend Line Chart**:
```javascript
new Chart(ctx, {
    type: 'line',
    data: {
        labels: dailyDates,
        datasets: [{
            label: 'Przychód',
            data: dailyRevenue,
            borderColor: CHART_COLORS.primary,
            backgroundColor: 'rgba(37, 99, 235, 0.1)',
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
                    label: (ctx) => `${ctx.parsed.y.toFixed(2)} zł`
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: { callback: (val) => `${val} zł` }
            }
        }
    }
});
```

**Service Breakdown Bar Chart**:
```javascript
new Chart(ctx, {
    type: 'bar',
    data: {
        labels: serviceNames,
        datasets: [{
            data: serviceRevenues,
            backgroundColor: [
                CHART_COLORS.primary,
                CHART_COLORS.purple,
                CHART_COLORS.pink,
                CHART_COLORS.orange,
                CHART_COLORS.green
            ]
        }]
    },
    options: {
        indexAxis: 'y',  // Horizontal
        responsive: true,
        plugins: { legend: { display: false } }
    }
});
```

**Client Split Doughnut Chart**:
```javascript
new Chart(ctx, {
    type: 'doughnut',
    data: {
        labels: ['Nowi klienci', 'Powracający'],
        datasets: [{
            data: [newClients, returningClients],
            backgroundColor: [CHART_COLORS.primary, CHART_COLORS.gray]
        }]
    }
});
```

### 6.3 JavaScript Data Fetching

**Main Dashboard Script** (`static/js/analytics/dashboard.js`):
```javascript
class AnalyticsDashboard {
    constructor() {
        this.currentPeriod = 'current_month';
        this.charts = {};
    }

    async init() {
        await this.loadAllMetrics();
        this.setupEventListeners();
    }

    async loadAllMetrics() {
        try {
            const [summary, trend, employees, services, clients] = await Promise.all([
                this.fetchSummary(),
                this.fetchRevenueTrend(),
                this.fetchEmployees(),
                this.fetchServices(),
                this.fetchClients()
            ]);

            this.renderKPICards(summary);
            this.renderRevenueTrendChart(trend);
            this.renderEmployeeTable(employees);
            this.renderServicesChart(services);
            this.renderClientsChart(clients);
        } catch (error) {
            this.handleError(error);
        }
    }

    async fetchSummary() {
        const response = await fetch(`/api/analytics/summary?period=${this.currentPeriod}`);
        const data = await response.json();
        if (!data.success) throw new Error(data.error);
        return data;
    }

    renderKPICards(data) {
        // Update revenue, appointments, clients, avg_ticket cards
        document.getElementById('kpi-revenue').textContent = formatCurrency(data.current.total_revenue);
        document.getElementById('kpi-revenue-change').textContent = formatChange(data.change.revenue_pct);
        // ... similar for other KPIs
    }

    setupEventListeners() {
        document.querySelectorAll('.period-selector button').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                this.currentPeriod = e.target.dataset.period;
                await this.loadAllMetrics();
            });
        });
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new AnalyticsDashboard();
    dashboard.init();
});
```

---

## 7. Error Handling & Edge Cases

### 7.1 No Data Scenarios

**New Salon (No Appointments)**:
```javascript
if (data.current.total_appointments === 0) {
    showEmptyState('Brak wizyt. Rozpocznij rezerwacje klientów!');
    hideAllCharts();
}
```

**No Comparison Data**:
```javascript
if (data.previous.total_appointments === 0) {
    displayMetricsWithoutComparison(data.current);
    // Show current values without arrows/percentages
}
```

**Employee with Zero Revenue**:
- Still display in table with 0 revenue
- Show base salary cost even if no commission
- Highlight in red if cost > 0 but revenue = 0 (unprofitable)

### 7.2 API Error Handling

```javascript
try {
    const response = await fetch('/api/analytics/summary?period=current_month');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    if (!data.success) {
        throw new Error(data.error);
    }
    return data;

} catch (error) {
    console.error('Analytics error:', error);
    Notifications.error('Nie udało się załadować danych analitycznych');

    // Try to show cached/stale data if available
    const cached = localStorage.getItem('analytics_cache');
    if (cached) {
        displayCachedData(JSON.parse(cached));
    }
}
```

### 7.3 Backend Validation

```python
@analytics_bp.route('/analytics/summary')
@login_required
@module_permission_required('appointments')
def get_analytics_summary():
    period = request.args.get('period', 'current_month')

    # Custom period validation
    if period == 'custom':
        start = request.args.get('start_date')
        end = request.args.get('end_date')

        if not start or not end:
            return jsonify({
                'success': False,
                'error': 'Brak zakresu dat dla własnego okresu'
            }), 400

        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Nieprawidłowy format daty (użyj YYYY-MM-DD)'
            }), 400

        if end_date < start_date:
            return jsonify({
                'success': False,
                'error': 'Data końcowa nie może być przed datą początkową'
            }), 400

        # Limit to max 1 year range
        if (end_date - start_date).days > 365:
            return jsonify({
                'success': False,
                'error': 'Zakres dat nie może przekraczać 1 roku'
            }), 400
```

### 7.4 Performance Safeguards

- **Limit trend data**: Max 90 days of daily data (prevents slow queries)
- **Query timeout**: Set 30-second timeout on analytics queries
- **Loading states**: Show skeleton UI while data loads
- **Progressive loading**: Load KPI cards first (fast), then charts (slower)

---

## 8. Files to Create/Modify

### New Files (5)

1. **`repositories/analytics/analytics_repository.py`** (~300 lines)
   - `get_date_ranges(period, reference_date)`
   - `get_revenue_summary(start_date, end_date)`
   - `get_revenue_trend(start_date, end_date)`
   - `get_employee_performance(start_date, end_date)`
   - `get_service_breakdown(start_date, end_date)`
   - `get_client_metrics(start_date, end_date)`
   - `get_at_risk_clients(days_threshold=90)`

2. **`routes/analytics_routes.py`** (~200 lines)
   - Analytics blueprint registration
   - 5 API endpoints (summary, trend, employees, services, clients)
   - Input validation, error handling

3. **`templates/analytics/dashboard.html`** (~400 lines)
   - Page layout with Refined Minimal styling
   - KPI card grid (4 cards)
   - Chart containers (canvas elements)
   - Period selector UI
   - Empty states, loading skeletons

4. **`static/js/analytics/dashboard.js`** (~500 lines)
   - AnalyticsDashboard class
   - API fetch methods
   - Chart.js initialization
   - KPI card rendering
   - Period selector event handlers
   - Error handling, caching

5. **`alembic/versions/XXXXXX_add_employer_cost_rate.py`** (~30 lines)
   - Migration to add `employer_cost_rate` column to employees table

### Modified Files (3)

1. **`app.py`** (+3 lines)
   - Register analytics blueprint

2. **`routes/main_routes.py`** (+10 lines)
   - Add analytics dashboard page route
   - `@main_bp.route('/analytics')`

3. **`templates/components/sidebar.html`** (+8 lines)
   - Add "Analityka" navigation link under "Zarządzanie" section

### Total Estimate
- **New files**: 5 (~1,430 lines)
- **Modified files**: 3 (~21 lines)
- **Total new code**: ~1,450 lines

---

## 9. Implementation Sequence

### Phase 1: Backend Foundation
1. Create Alembic migration for `employer_cost_rate`
2. Run migration: `alembic upgrade head`
3. Create `repositories/analytics/analytics_repository.py`
   - Implement all SQL queries
   - Test with sample data
4. Create `routes/analytics_routes.py`
   - Implement all 5 endpoints
   - Test with curl/Postman

### Phase 2: Frontend Shell
5. Create `templates/analytics/dashboard.html`
   - HTML structure without charts
   - Static KPI cards
   - Period selector buttons
6. Update sidebar navigation
7. Test page rendering

### Phase 3: Chart Integration
8. Create `static/js/analytics/dashboard.js`
   - API fetch methods
   - Chart.js initialization
9. Test each chart individually
10. Wire up period selector

### Phase 4: Polish & Testing
11. Add error handling
12. Add loading states
13. Mobile responsive testing
14. End-to-end testing (all periods, edge cases)

**Estimated Time**: 8-12 hours (1.5-2 days)

---

## 10. Testing Strategy

### Unit Tests (Backend)
```python
# Test analytics repository
def test_get_revenue_summary():
    repo = AnalyticsRepository()
    summary = repo.get_revenue_summary(
        date(2026, 2, 1),
        date(2026, 2, 28)
    )
    assert summary['total_revenue'] > 0
    assert summary['total_appointments'] > 0

def test_employee_performance_cost_calculation():
    # Employee with base 4000, commission 8325
    # Expected cost: (4000 + 8325) * 1.22 = 15,036.50
    performance = repo.get_employee_performance(...)
    employee = performance[0]
    assert employee['total_employer_cost'] == 15036.50
```

### Integration Tests (API)
```python
def test_analytics_summary_endpoint(client):
    response = client.get('/api/analytics/summary?period=current_month')
    assert response.status_code == 200
    data = response.json
    assert data['success'] == True
    assert 'current' in data
    assert 'previous' in data
    assert 'change' in data

def test_invalid_period_returns_400(client):
    response = client.get('/api/analytics/summary?period=invalid')
    assert response.status_code == 400
```

### Manual Testing Checklist
- [ ] KPI cards display correct values
- [ ] Period selector switches data correctly
- [ ] Charts render without errors
- [ ] Comparison arrows show correct direction (up/down)
- [ ] Employee table sorts by revenue (highest first)
- [ ] At-risk clients list shows correct data
- [ ] Empty state displays when no data
- [ ] Mobile responsive (all charts visible)
- [ ] No console errors in browser

---

## 11. Future Enhancements (Out of Scope)

### Phase 6+ Features
- **Forecasting**: ML-based revenue predictions
- **Custom Reports**: User-defined report builder
- **Automated Insights**: "Revenue down 15% this week - investigate?"
- **Email Reports**: Weekly/monthly summary emails
- **Drill-down**: Click chart to see details (e.g., click employee → see their appointments)
- **Export**: Export charts as PDF/PNG
- **Benchmarking**: Compare to industry averages
- **Goal Tracking**: Set revenue/client targets, track progress

### Performance Optimizations
- Redis caching for expensive queries (retention rate)
- Pre-compute daily aggregates (materialized views)
- Migrate to PostgreSQL for better analytics performance
- Add database indexes on common query patterns

---

## 12. Success Metrics

### Implementation Success
- ✅ All 5 API endpoints return correct data
- ✅ Charts render without errors
- ✅ Period comparisons show accurate percentages
- ✅ Employee cost calculations match Polish tax law
- ✅ Page loads in <2 seconds with 1000 appointments

### Business Value
- ✅ Salon owner can identify top-performing employees
- ✅ Salon owner can see which services are most profitable
- ✅ Salon owner can track month-over-month revenue trends
- ✅ Salon owner can identify at-risk clients for retention efforts
- ✅ Employee profitability analysis helps with hiring decisions

---

## Appendix A: Polish Employment Cost Reference

### Employer Costs (Pracodawca)
- **Pension Insurance** (ubezpieczenie emerytalne): 9.76% of gross
- **Disability Insurance** (ubezpieczenie rentowe): 6.50% of gross
- **Accident Insurance** (ubezpieczenie wypadkowe): 0.67-3.33% (avg 1.67%)
- **Labor Fund** (Fundusz Pracy): 2.45% of gross
- **FGŚP** (Fundusz Gwarantowanych Świadczeń): 0.10% of gross
- **Total**: ~20-22% on top of gross salary

### Employee Costs (Pracownik) - For Reference Only
These are deducted from gross salary, NOT employer costs:
- Social security (ZUS): ~13.71% of gross
- Health insurance: ~9% of gross
- Income tax (PIT): 12% or 32% (progressive)

### Example Calculation
```
Base Salary: 4,000 zł
Commission: 8,325 zł
─────────────────────
Gross Salary: 12,325 zł

Employer ZUS (20.5%): 2,526.63 zł
Accident Insurance (1.67%): 205.83 zł
Labor Fund (2.45%): 301.96 zł
FGŚP (0.10%): 12.33 zł
─────────────────────
Total Employer Cost: 15,371.75 zł

(Simplified in design: 12,325 × 1.22 = 15,036.50 zł)
```

**Note**: The 22% rate is a simplification. Actual costs vary by:
- Accident insurance category (depends on business activity)
- Employee age (over 55 = no Labor Fund contribution)
- Special exemptions (disabled employees, etc.)

For accuracy, the `employer_cost_rate` field allows per-employee customization.

---

**End of Design Document**
