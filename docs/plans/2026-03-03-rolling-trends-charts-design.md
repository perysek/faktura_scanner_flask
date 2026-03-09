# Design: 7 Rolling 12-Month Trend Charts

**Date:** 2026-03-03
**Branch:** feat/2026-03-02-password-reset-and-db-fixes
**Status:** Approved

---

## Context

The analytics dashboard already has period-scoped KPI cards, a revenue trend chart, a profit breakdown chart, occupancy KPIs, a peak-hours heatmap, a service price analysis table, and the Task 1 rolling profit/cost/revenue bar+line chart.

Task 2 adds 7 more rolling 12-month charts, all independent of the period selector, grouped in a new "Trendy roczne" section at the bottom of the dashboard.

---

## Architecture

### Repository — 7 new parameterless methods in `repositories/analytics/analytics_repository.py`

All methods use PostgreSQL `generate_series` to guarantee 12 rows even for months with no data, except `get_service_category_mix_monthly()` and `get_visit_frequency_distribution()` which return unpivoted/histogram data (gap-filled in JS instead).

| Method | Data shape |
|--------|-----------|
| `get_new_clients_monthly()` | `[{month_start, new_clients}]` |
| `get_cancellation_rate_monthly()` | `[{month_start, cancellation_pct, noshow_pct, total}]` |
| `get_avg_ticket_monthly()` | `[{month_start, avg_ticket}]` |
| `get_service_category_mix_monthly()` | `[{month_start, category, revenue}]` unpivoted |
| `get_invoice_cost_ratio_monthly()` | `[{month_start, revenue, invoice_costs, ratio_pct}]` |
| `get_employee_utilisation_monthly()` | `[{month_start, employee_name, utilisation_pct}]` one row per employee×month |
| `get_visit_frequency_distribution()` | `[{visit_count, client_count}]` histogram |

### API — 7 new routes in `routes/analytics_routes.py`

All under `/api/analytics/rolling/*`, all `GET`, all `@login_required @module_permission_required('appointments')`, no period parameter.

| Endpoint | Repository method |
|----------|-------------------|
| `GET /api/analytics/rolling/new-clients` | `get_new_clients_monthly()` |
| `GET /api/analytics/rolling/cancellation-rate` | `get_cancellation_rate_monthly()` |
| `GET /api/analytics/rolling/avg-ticket` | `get_avg_ticket_monthly()` |
| `GET /api/analytics/rolling/category-mix` | `get_service_category_mix_monthly()` |
| `GET /api/analytics/rolling/cost-ratio` | `get_invoice_cost_ratio_monthly()` |
| `GET /api/analytics/rolling/employee-utilisation` | `get_employee_utilisation_monthly()` |
| `GET /api/analytics/rolling/visit-frequency` | `get_visit_frequency_distribution()` |

### JS — 7 new functions in `static/js/analytics/dashboard.js`

Chart instance variables declared at top alongside existing vars. All 7 functions added to the `Promise.all` in `loadDashboard()`. None call `buildParams()` — all are period-independent.

| Function | Chart instance var | Chart.js type |
|----------|-------------------|--------------|
| `loadNewClients()` | `newClientsChart` | `line` (single green dataset, fill tint) |
| `loadCancellationRate()` | `cancellationRateChart` | `line` (amber=cancellation, red=no-show, % y-axis) |
| `loadAvgTicket()` | `avgTicketChart` | `line` (single blue, PLN y-axis) |
| `loadCategoryMix()` | `categoryMixChart` | `bar` stacked (one dataset per category, JS pivots unpivoted rows) |
| `loadCostRatio()` | `costRatioChart` | mixed: `bar` (revenue, left y-axis PLN) + `line` (ratio %, right y-axis) |
| `loadEmployeeUtilisation()` | `employeeUtilisationChart` | `line` (one dataset per employee, cycling 8-color palette) |
| `loadVisitFrequency()` | `visitFrequencyChart` | `bar` (X = visit count labels "1"–"10+", Y = client count) |

### Template — new section in `templates/analytics/dashboard.html`

Appended at the very end of `{% block content %}`, after the existing service analysis table.

**Layout:**
```
<!-- Trendy roczne heading -->
Row 1 (lg:grid-cols-2): New clients | Cancellation/no-show
Row 2 (lg:grid-cols-2): Avg ticket  | Invoice cost ratio
Row 3 (full width):     Service category mix (stacked bar)
Row 4 (full width):     Employee utilisation (multi-line)
Row 5 (full width):     Visit frequency histogram
```

---

## SQL Details

### `get_new_clients_monthly()`
```sql
WITH months AS (generate_series 12M spine),
new_per_month AS (
    SELECT DATE_TRUNC('month', first_visit_date)::date AS month_start,
           COUNT(*) AS new_clients
    FROM clients
    WHERE first_visit_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
    GROUP BY 1
)
SELECT m.month_start, COALESCE(n.new_clients, 0) AS new_clients
FROM months m LEFT JOIN new_per_month n ON n.month_start = m.month_start
ORDER BY m.month_start
```

### `get_cancellation_rate_monthly()`
Uses `COUNT(*) FILTER (WHERE status = 'cancelled')` and `FILTER (WHERE status = 'no_show')` with `generate_series` spine. Returns 0% for months with no appointments.

### `get_avg_ticket_monthly()`
`AVG(income_records.net_amount)` joined to completed appointments, spine-guaranteed.

### `get_service_category_mix_monthly()`
No spine — returns only months+categories with revenue. JS pivots into per-category datasets:
```sql
SELECT DATE_TRUNC('month', a.appointment_date)::date AS month_start,
       s.category, COALESCE(SUM(aps.price_charged), 0) AS revenue
FROM appointments a
JOIN appointment_services aps ON aps.appointment_id = a.id
JOIN services s ON s.id = aps.service_id
WHERE a.status = 'completed'
  AND a.appointment_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months')
GROUP BY 1, 2
ORDER BY 1, 2
```

### `get_invoice_cost_ratio_monthly()`
```sql
ratio_pct = ROUND(invoice_costs / NULLIF(revenue, 0) * 100, 1)
```
Spine-guaranteed. Returns both raw values and the ratio.

### `get_employee_utilisation_monthly()`
```sql
utilisation_pct = ROUND(appointments_count * 100.0 / (22 * max_appointments_per_day), 1)
```
Uses 22 working days/month as a standard approximation. CROSS JOIN months × active employees, LEFT JOIN completed appointments.

### `get_visit_frequency_distribution()`
```sql
WITH client_visits AS (
    SELECT client_id, COUNT(*) AS visit_count
    FROM appointments
    WHERE status = 'completed'
      AND appointment_date >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY client_id
)
SELECT visit_count, COUNT(*) AS client_count
FROM client_visits
GROUP BY visit_count
ORDER BY visit_count
```
JS caps x-axis display at "10+" by bucketing anything > 10.

---

## Visual Design

- **Colors**: Reuse `CHART_COLORS` palette from dashboard.js; employee utilisation cycles through extended 8-color array
- **Tooltips**: All use `formatCurrency()` for PLN values, `toFixed(1) + '%'` for percentages
- **Axis labels**: PLN amounts use `toLocaleString('pl-PL') + ' zł'`; percentages use `val + '%'`
- **Date labels**: Same `PL_MONTHS` pattern as `loadMonthlyTrend()` — parsed as local time, no UTC shift
- **Section heading**: `<h2>Trendy roczne</h2>` with subtitle explaining period independence
- **Canvas heights**: 280px for 2-col charts, 320px for full-width multi-series charts

---

## Files Modified

| File | Change |
|------|--------|
| `repositories/analytics/analytics_repository.py` | +7 methods |
| `routes/analytics_routes.py` | +7 routes |
| `templates/analytics/dashboard.html` | +1 section (7 canvases) |
| `static/js/analytics/dashboard.js` | +7 chart vars, +7 functions, extended Promise.all |
