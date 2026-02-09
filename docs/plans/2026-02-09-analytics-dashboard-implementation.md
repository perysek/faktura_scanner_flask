# Analytics Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build comprehensive analytics dashboard with revenue metrics, employee cost tracking (Polish ZUS model), service insights, and client retention analysis.

**Architecture:** SQL-first analytics using Flask + SQLite with Chart.js 4.x visualizations. Direct parameterized queries for flexibility with time periods (month-over-month, year-over-year, custom ranges). Vanilla JavaScript frontend with Refined Minimal design system.

**Tech Stack:** Flask, SQLite, Chart.js 4.x, TailwindCSS, Material Icons, python-dateutil

---

## Task 1: Database Migration - Add Employer Cost Rate

**Files:**
- Create: `alembic/versions/xxx_add_employer_cost_rate_to_employees.py`

**Step 1: Create migration file**

```bash
cd /c/Projects/faktura_scanner_flask/.worktrees/analytics-dashboard
alembic revision -m "add employer cost rate to employees"
```

**Step 2: Write migration script**

Edit the generated file in `alembic/versions/`:

```python
"""add employer cost rate to employees

Revision ID: <generated>
Revises: <previous>
Create Date: <generated>
"""
from alembic import op
import sqlalchemy as sa

revision = '<generated>'
down_revision = '<previous>'
branch_labels = None
depends_on = None

def upgrade():
    # Add employer_cost_rate column with default 0.22 (22% Polish ZUS/taxes/benefits)
    op.add_column('employees',
        sa.Column('employer_cost_rate', sa.Numeric(5, 4), nullable=False, server_default='0.22')
    )

def downgrade():
    op.drop_column('employees', 'employer_cost_rate')
```

**Step 3: Run migration**

```bash
alembic upgrade head
```

Expected: "Running upgrade xxx -> yyy, add employer cost rate to employees"

**Step 4: Verify schema**

```bash
sqlite3 faktury.db "PRAGMA table_info(employees);" | grep employer_cost_rate
```

Expected: employer_cost_rate column present

**Step 5: Commit**

```bash
git add alembic/versions/*.py
git commit -m "feat(db): add employer_cost_rate to employees for Polish cost tracking

Adds configurable employer cost rate (default 22%) to support:
- ZUS contributions (~19.48%)
- Work accident insurance (~1.67%)
- Labor Fund (2.45%)
- FGŚP (0.10%)

Total employer cost = (base_salary + commission) × (1 + rate)"
```

---

## Task 2: Analytics Repository - Date Range Helper

**Files:**
- Create: `repositories/analytics/analytics_repository.py`

**Step 1: Write failing test**

Create: `tests/repositories/analytics/test_analytics_repository.py`

```python
"""Tests for AnalyticsRepository date range calculations"""
import pytest
from datetime import date
from dateutil.relativedelta import relativedelta
from repositories.analytics.analytics_repository import AnalyticsRepository


class TestDateRanges:
    """Test date range calculation for different periods"""

    def setup_method(self):
        self.repo = AnalyticsRepository()

    def test_current_month_ranges(self):
        """Current month should return this month vs. last month"""
        ref = date(2026, 2, 15)  # Feb 15, 2026
        current_start, current_end, prev_start, prev_end = self.repo.get_date_ranges('current_month', ref)

        assert current_start == date(2026, 2, 1)
        assert current_end == date(2026, 2, 28)
        assert prev_start == date(2026, 1, 1)
        assert prev_end == date(2026, 1, 31)

    def test_last_month_ranges(self):
        """Last month should return previous month vs. month before that"""
        ref = date(2026, 2, 15)
        current_start, current_end, prev_start, prev_end = self.repo.get_date_ranges('last_month', ref)

        assert current_start == date(2026, 1, 1)
        assert current_end == date(2026, 1, 31)
        assert prev_start == date(2025, 12, 1)
        assert prev_end == date(2025, 12, 31)

    def test_current_year_ranges(self):
        """Current year should return YTD vs. same period last year"""
        ref = date(2026, 2, 15)
        current_start, current_end, prev_start, prev_end = self.repo.get_date_ranges('current_year', ref)

        assert current_start == date(2026, 1, 1)
        assert current_end == date(2026, 2, 15)
        assert prev_start == date(2025, 1, 1)
        assert prev_end == date(2025, 2, 15)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/repositories/analytics/test_analytics_repository.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'repositories.analytics'"

**Step 3: Write minimal implementation**

Create: `repositories/analytics/__init__.py` (empty file)

Create: `repositories/analytics/analytics_repository.py`

```python
"""
Analytics repository for dashboard metrics
"""
from datetime import date, timedelta
from typing import Tuple
from dateutil.relativedelta import relativedelta


class AnalyticsRepository:
    """Repository for analytics queries with time period support"""

    def get_date_ranges(
        self,
        period: str,
        reference_date: date = None
    ) -> Tuple[date, date, date, date]:
        """
        Calculate date ranges for current and comparison periods.

        Args:
            period: 'current_month' | 'last_month' | 'current_year' | 'custom'
            reference_date: Reference date for calculations (defaults to today)

        Returns:
            (current_start, current_end, previous_start, previous_end)
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

        else:
            raise ValueError(f"Unsupported period: {period}")

        return (current_start, current_end, previous_start, previous_end)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/repositories/analytics/test_analytics_repository.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add repositories/analytics/ tests/repositories/analytics/
git commit -m "feat(analytics): add date range calculation for time periods

Supports current_month, last_month, current_year periods.
Returns current and comparison date ranges for analytics queries.

Uses python-dateutil for robust date arithmetic."
```

---

## Task 3: Analytics Repository - Revenue Summary Query

**Files:**
- Modify: `repositories/analytics/analytics_repository.py`
- Modify: `tests/repositories/analytics/test_analytics_repository.py`

**Step 1: Write failing test**

Add to `tests/repositories/analytics/test_analytics_repository.py`:

```python
from unittest.mock import Mock, patch


class TestRevenueSummary:
    """Test revenue summary query"""

    def setup_method(self):
        self.repo = AnalyticsRepository()

    @patch('repositories.analytics.analytics_repository.DatabaseConnection')
    def test_get_revenue_summary_executes_correct_query(self, mock_db):
        """Revenue summary should query appointments and income_records"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {
            'total_appointments': 124,
            'unique_clients': 87,
            'total_revenue': 45600.00,
            'avg_ticket': 367.74,
            'total_commissions': 18240.00
        }
        mock_db.get_connection.return_value = mock_conn

        start = date(2026, 2, 1)
        end = date(2026, 2, 28)
        result = self.repo.get_revenue_summary(start, end)

        # Verify query was executed
        assert mock_cursor.execute.called
        query = mock_cursor.execute.call_args[0][0]
        assert 'appointments' in query.lower()
        assert 'income_records' in query.lower()
        assert 'completed' in query.lower()

        # Verify result structure
        assert result['total_appointments'] == 124
        assert result['unique_clients'] == 87
        assert result['total_revenue'] == 45600.00
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/repositories/analytics/test_analytics_repository.py::TestRevenueSummary -v
```

Expected: FAIL with "AttributeError: 'AnalyticsRepository' object has no attribute 'get_revenue_summary'"

**Step 3: Write minimal implementation**

Add to `repositories/analytics/analytics_repository.py`:

```python
from config.database import DatabaseConnection
from typing import Dict


class AnalyticsRepository:
    # ... existing code ...

    def get_revenue_summary(self, start_date: date, end_date: date) -> Dict:
        """
        Get revenue summary for date range.

        Returns:
            {
                'total_appointments': int,
                'unique_clients': int,
                'total_revenue': float,
                'avg_ticket': float,
                'total_commissions': float
            }
        """
        query = """
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
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        row = cursor.fetchone()

        return dict(row) if row else {
            'total_appointments': 0,
            'unique_clients': 0,
            'total_revenue': 0.0,
            'avg_ticket': 0.0,
            'total_commissions': 0.0
        }
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/repositories/analytics/test_analytics_repository.py::TestRevenueSummary -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add repositories/analytics/analytics_repository.py tests/repositories/analytics/test_analytics_repository.py
git commit -m "feat(analytics): add revenue summary query

Aggregates appointments and income data:
- Total appointments
- Unique clients
- Total revenue
- Average ticket size
- Total commissions"
```

---

## Task 4: Analytics Repository - Employee Performance Query

**Files:**
- Modify: `repositories/analytics/analytics_repository.py`
- Modify: `tests/repositories/analytics/test_analytics_repository.py`

**Step 1: Write failing test**

Add to `tests/repositories/analytics/test_analytics_repository.py`:

```python
class TestEmployeePerformance:
    """Test employee performance query with Polish cost model"""

    def setup_method(self):
        self.repo = AnalyticsRepository()

    @patch('repositories.analytics.analytics_repository.DatabaseConnection')
    def test_get_employee_performance_includes_cost_calculations(self, mock_db):
        """Employee performance should calculate Polish employer costs"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'employee_name': 'Anna Kowalska',
                'base_salary': 4000.00,
                'cost_rate': 0.22,
                'appointments_count': 45,
                'revenue_generated': 18500.00,
                'commission_earned': 8325.00,
                'gross_salary': 12325.00,
                'total_employer_cost': 15036.50,
                'net_profit': 3463.50
            }
        ]
        mock_db.get_connection.return_value = mock_conn

        start = date(2026, 2, 1)
        end = date(2026, 2, 28)
        results = self.repo.get_employee_performance(start, end)

        # Verify query was executed
        assert mock_cursor.execute.called
        query = mock_cursor.execute.call_args[0][0]
        assert 'employees' in query.lower()
        assert 'employer_cost_rate' in query.lower()

        # Verify cost calculations in results
        emp = results[0]
        assert emp['gross_salary'] == 12325.00
        assert emp['total_employer_cost'] == 15036.50
        assert emp['net_profit'] == 3463.50
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/repositories/analytics/test_analytics_repository.py::TestEmployeePerformance -v
```

Expected: FAIL with "AttributeError: 'AnalyticsRepository' object has no attribute 'get_employee_performance'"

**Step 3: Write minimal implementation**

Add to `repositories/analytics/analytics_repository.py`:

```python
from typing import List


class AnalyticsRepository:
    # ... existing code ...

    def get_employee_performance(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Get employee performance metrics with Polish employment cost model.

        Total Employer Cost = (base_salary + commission) × (1 + employer_cost_rate)
        Net Profit = revenue_generated - total_employer_cost

        Returns list of:
            {
                'id': int,
                'employee_name': str,
                'base_salary': float,
                'cost_rate': float (default 0.22 = 22%),
                'appointments_count': int,
                'revenue_generated': float,
                'commission_earned': float,
                'gross_salary': float (base + commission),
                'total_employer_cost': float (gross × 1.22),
                'net_profit': float (revenue - cost)
            }
        """
        query = """
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
                (e.base_salary + COALESCE(SUM(i.commission_total), 0)) *
                    (1 + COALESCE(e.employer_cost_rate, 0.22)) as total_employer_cost,

                -- Profitability
                COALESCE(SUM(i.net_amount), 0) -
                    ((e.base_salary + COALESCE(SUM(i.commission_total), 0)) *
                     (1 + COALESCE(e.employer_cost_rate, 0.22))) as net_profit
            FROM employees e
            LEFT JOIN appointments a ON a.employee_id = e.id AND a.status = 'completed'
            LEFT JOIN income_records i ON i.appointment_id = a.id
            WHERE e.is_active = 1
                AND (a.appointment_date BETWEEN ? AND ? OR a.appointment_date IS NULL)
            GROUP BY e.id, e.first_name, e.last_name, e.base_salary, e.employer_cost_rate
            ORDER BY revenue_generated DESC
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/repositories/analytics/test_analytics_repository.py::TestEmployeePerformance -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add repositories/analytics/analytics_repository.py tests/repositories/analytics/test_analytics_repository.py
git commit -m "feat(analytics): add employee performance query with Polish cost model

Calculates Polish employment costs:
- Employer ZUS: ~19.48%
- Accident insurance: ~1.67%
- Labor Fund: 2.45%
- FGŚP: 0.10%
Total: 22% on top of gross salary

Includes net profit: revenue - total employer cost"
```

---

## Task 5: Analytics Repository - Service and Client Queries

**Files:**
- Modify: `repositories/analytics/analytics_repository.py`

**Step 1: Add service breakdown query**

Add to `repositories/analytics/analytics_repository.py`:

```python
class AnalyticsRepository:
    # ... existing code ...

    def get_service_breakdown(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Get service revenue breakdown.

        Returns list of:
            {
                'service_name': str,
                'category': str,
                'times_booked': int,
                'revenue_generated': float
            }
        """
        query = """
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
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_client_metrics(self, start_date: date, end_date: date) -> Dict:
        """
        Get client acquisition and retention metrics.

        Returns:
            {
                'new_clients': int,
                'returning_clients': int,
                'retention_rate': float (percentage),
                'at_risk_clients': List[Dict]
            }
        """
        # New vs. returning clients
        new_returning_query = """
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
        """

        # Retention rate (90-day window)
        retention_query = """
            WITH client_visits AS (
                SELECT
                    client_id,
                    appointment_date,
                    LAG(appointment_date) OVER (PARTITION BY client_id ORDER BY appointment_date) as prev_visit
                FROM appointments
                WHERE status = 'completed'
            )
            SELECT
                COUNT(CASE WHEN julianday(appointment_date) - julianday(prev_visit) <= 90 THEN 1 END) * 100.0 /
                NULLIF(COUNT(*), 0) as retention_rate
            FROM client_visits
            WHERE prev_visit IS NOT NULL
                AND appointment_date BETWEEN ? AND ?
        """

        # At-risk clients (90+ days since last visit)
        at_risk_query = """
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
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()

        # New/returning
        cursor.execute(new_returning_query, (start_date, start_date, start_date, end_date))
        nr_row = cursor.fetchone()

        # Retention
        cursor.execute(retention_query, (start_date, end_date))
        ret_row = cursor.fetchone()

        # At-risk
        cursor.execute(at_risk_query)
        at_risk_rows = cursor.fetchall()

        return {
            'new_clients': nr_row['new_clients'] if nr_row else 0,
            'returning_clients': nr_row['returning_clients'] if nr_row else 0,
            'retention_rate': ret_row['retention_rate'] if ret_row else 0.0,
            'at_risk_clients': [dict(row) for row in at_risk_rows]
        }
```

**Step 2: Run quick manual verification**

```bash
python -c "from repositories.analytics.analytics_repository import AnalyticsRepository; print('Import OK')"
```

Expected: "Import OK"

**Step 3: Commit**

```bash
git add repositories/analytics/analytics_repository.py
git commit -m "feat(analytics): add service breakdown and client metrics queries

Service breakdown: revenue by service type and category
Client metrics: new/returning split, 90-day retention rate, at-risk list"
```

---

## Task 6: Analytics Repository - Revenue Trend Query

**Files:**
- Modify: `repositories/analytics/analytics_repository.py`

**Step 1: Add revenue trend query**

Add to `repositories/analytics/analytics_repository.py`:

```python
class AnalyticsRepository:
    # ... existing code ...

    def get_revenue_trend(self, start_date: date, end_date: date) -> List[Dict]:
        """
        Get daily revenue trend for line chart.

        Returns list of:
            {
                'date': str (YYYY-MM-DD),
                'revenue': float,
                'appointments': int
            }
        """
        query = """
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
        """

        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()

        return [dict(row) for row in rows]
```

**Step 2: Commit**

```bash
git add repositories/analytics/analytics_repository.py
git commit -m "feat(analytics): add revenue trend query for line charts

Returns daily revenue and appointment counts for time series visualization"
```

---

## Task 7: Analytics Routes - Blueprint Setup

**Files:**
- Create: `routes/analytics_routes.py`
- Modify: `app.py`

**Step 1: Create analytics blueprint**

Create: `routes/analytics_routes.py`

```python
"""
Analytics API routes
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required
from datetime import date

from config.auth_config import module_permission_required
from repositories.analytics.analytics_repository import AnalyticsRepository


analytics_bp = Blueprint('analytics', __name__)
repo = AnalyticsRepository()


def parse_period_params():
    """Parse period and date parameters from request"""
    period = request.args.get('period', 'current_month')

    if period == 'custom':
        start_str = request.args.get('start_date')
        end_str = request.args.get('end_date')

        if not start_str or not end_str:
            return None, {"error": "Custom period requires start_date and end_date"}

        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
            return (start_date, end_date, None, None), None
        except ValueError:
            return None, {"error": "Invalid date format. Use YYYY-MM-DD"}

    else:
        try:
            ranges = repo.get_date_ranges(period)
            return ranges, None
        except ValueError as e:
            return None, {"error": str(e)}


@analytics_bp.route('/analytics/summary', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_summary():
    """Get summary KPIs with period comparison"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, prev_start, prev_end = ranges

    # Get current period metrics
    current = repo.get_revenue_summary(current_start, current_end)

    # Get previous period metrics (if not custom)
    if prev_start and prev_end:
        previous = repo.get_revenue_summary(prev_start, prev_end)

        # Calculate percentage changes
        def pct_change(curr, prev):
            if prev == 0:
                return 0.0
            return ((curr - prev) / prev) * 100

        change = {
            'revenue_pct': pct_change(current['total_revenue'], previous['total_revenue']),
            'appointments_pct': pct_change(current['total_appointments'], previous['total_appointments']),
            'clients_pct': pct_change(current['unique_clients'], previous['unique_clients']),
            'avg_ticket_pct': pct_change(current['avg_ticket'], previous['avg_ticket']),
            'commissions_pct': pct_change(current['total_commissions'], previous['total_commissions'])
        }
    else:
        previous = None
        change = None

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        "current": {
            "start_date": current_start.isoformat(),
            "end_date": current_end.isoformat(),
            **current
        },
        "previous": {
            "start_date": prev_start.isoformat() if prev_start else None,
            "end_date": prev_end.isoformat() if prev_end else None,
            **previous
        } if previous else None,
        "change": change
    })
```

**Step 2: Register blueprint in app.py**

Add to `app.py` after existing blueprint imports:

```python
from routes.analytics_routes import analytics_bp
```

Add to blueprint registration section:

```python
app.register_blueprint(analytics_bp, url_prefix='/api')
```

**Step 3: Test endpoint manually**

```bash
# Start app in another terminal
python app.py

# Test endpoint
curl http://localhost:8083/api/analytics/summary?period=current_month
```

Expected: JSON response with current/previous/change fields

**Step 4: Commit**

```bash
git add routes/analytics_routes.py app.py
git commit -m "feat(analytics): add summary API endpoint with period comparison

GET /api/analytics/summary?period=current_month
Returns KPIs with percentage changes vs. previous period"
```

---

## Task 8: Analytics Routes - Remaining Endpoints

**Files:**
- Modify: `routes/analytics_routes.py`

**Step 1: Add revenue trend endpoint**

Add to `routes/analytics_routes.py`:

```python
@analytics_bp.route('/analytics/revenue-trend', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_revenue_trend():
    """Get revenue trend for line chart"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, _, _ = ranges

    data = repo.get_revenue_trend(current_start, current_end)

    # Calculate summary
    total = sum(d['revenue'] for d in data)
    days_count = len(data) if data else 1
    avg_daily = total / days_count

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        "data": data,
        "summary": {
            "total": total,
            "avg_daily": avg_daily
        }
    })


@analytics_bp.route('/analytics/employees', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employees():
    """Get employee performance metrics"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, _, _ = ranges

    employees = repo.get_employee_performance(current_start, current_end)

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        "employees": employees
    })


@analytics_bp.route('/analytics/services', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_services():
    """Get service breakdown"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, _, _ = ranges

    services = repo.get_service_breakdown(current_start, current_end)

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        "services": services
    })


@analytics_bp.route('/analytics/clients', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_clients():
    """Get client metrics and retention"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, _, _ = ranges

    metrics = repo.get_client_metrics(current_start, current_end)

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        "metrics": metrics
    })
```

**Step 2: Commit**

```bash
git add routes/analytics_routes.py
git commit -m "feat(analytics): add revenue-trend, employees, services, clients endpoints

All endpoints support period parameter and return JSON data for charts"
```

---

## Task 9: Main Route - Analytics Dashboard Page

**Files:**
- Modify: `routes/main_routes.py`

**Step 1: Add analytics dashboard route**

Add to `routes/main_routes.py`:

```python
@main_bp.route('/analytics')
@login_required
@module_permission_required('appointments')
def analytics_dashboard():
    """Analytics dashboard view"""
    return render_template('analytics/dashboard.html')
```

**Step 2: Commit**

```bash
git add routes/main_routes.py
git commit -m "feat(analytics): add dashboard route

GET /analytics renders analytics/dashboard.html"
```

---

## Task 10: Analytics Dashboard Template - Structure

**Files:**
- Create: `templates/analytics/dashboard.html`

**Step 1: Create dashboard template**

Create: `templates/analytics/dashboard.html`

```html
{% extends "base.html" %}
{% block title %}Analityka - {{ super() }}{% endblock %}

{% block page_title %}
<div class="flex justify-between items-center">
    <h1 class="text-2xl font-medium text-ink">Analityka biznesowa</h1>

    <!-- Period Selector -->
    <div class="period-selector flex gap-2">
        <button data-period="current_month" class="refined-btn-secondary refined-btn-sm active">
            Ten miesiąc
        </button>
        <button data-period="last_month" class="refined-btn-secondary refined-btn-sm">
            Ostatni miesiąc
        </button>
        <button data-period="current_year" class="refined-btn-secondary refined-btn-sm">
            Rok do daty
        </button>
        <button data-period="custom" class="refined-btn-secondary refined-btn-sm">
            Własny zakres
        </button>
    </div>
</div>
{% endblock %}

{% block content %}
<!-- Custom Date Range Modal (hidden by default) -->
<div id="customRangeModal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="refined-card max-w-md w-full">
        <h3 class="text-lg font-medium mb-4">Wybierz zakres dat</h3>
        <div class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-1">Data początkowa</label>
                <input type="date" id="customStartDate" class="w-full px-3 py-2 border rounded">
            </div>
            <div>
                <label class="block text-sm font-medium mb-1">Data końcowa</label>
                <input type="date" id="customEndDate" class="w-full px-3 py-2 border rounded">
            </div>
            <div class="flex justify-end gap-2">
                <button onclick="closeCustomRange()" class="refined-btn-secondary refined-btn-sm">
                    Anuluj
                </button>
                <button onclick="applyCustomRange()" class="refined-btn-primary refined-btn-sm">
                    Zastosuj
                </button>
            </div>
        </div>
    </div>
</div>

<!-- KPI Cards -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
    <!-- Revenue Card -->
    <div class="refined-card">
        <div class="text-sm text-ink-light mb-1">Przychód</div>
        <div id="kpi-revenue" class="text-2xl font-semibold text-ink mb-2">-</div>
        <div id="kpi-revenue-change" class="text-sm"></div>
    </div>

    <!-- Appointments Card -->
    <div class="refined-card">
        <div class="text-sm text-ink-light mb-1">Wizyty</div>
        <div id="kpi-appointments" class="text-2xl font-semibold text-ink mb-2">-</div>
        <div id="kpi-appointments-change" class="text-sm"></div>
    </div>

    <!-- Clients Card -->
    <div class="refined-card">
        <div class="text-sm text-ink-light mb-1">Klienci</div>
        <div id="kpi-clients" class="text-2xl font-semibold text-ink mb-2">-</div>
        <div id="kpi-clients-change" class="text-sm"></div>
    </div>

    <!-- Avg Ticket Card -->
    <div class="refined-card">
        <div class="text-sm text-ink-light mb-1">Średni rachunek</div>
        <div id="kpi-avg-ticket" class="text-2xl font-semibold text-ink mb-2">-</div>
        <div id="kpi-avg-ticket-change" class="text-sm"></div>
    </div>
</div>

<!-- Charts Row 1: Revenue Trend + Services -->
<div class="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
    <!-- Revenue Trend Chart -->
    <div class="refined-card lg:col-span-2">
        <h3 class="text-lg font-medium mb-4">Trend przychodów</h3>
        <div style="height: 300px;">
            <canvas id="revenueTrendChart"></canvas>
        </div>
    </div>

    <!-- Services Chart -->
    <div class="refined-card">
        <h3 class="text-lg font-medium mb-4">Usługi</h3>
        <div style="height: 300px;">
            <canvas id="servicesChart"></canvas>
        </div>
    </div>
</div>

<!-- Employee Performance Table -->
<div class="refined-card mb-6">
    <h3 class="text-lg font-medium mb-4">Wyniki pracowników</h3>
    <div class="overflow-x-auto">
        <table class="table">
            <thead>
                <tr>
                    <th>Pracownik</th>
                    <th class="text-right">Wizyty</th>
                    <th class="text-right">Przychód</th>
                    <th class="text-right">Prowizja</th>
                    <th class="text-right">Wynagrodzenie brutto</th>
                    <th class="text-right">Koszt pracodawcy</th>
                    <th class="text-right">Zysk netto</th>
                </tr>
            </thead>
            <tbody id="employeeTableBody">
                <tr>
                    <td colspan="7" class="text-center text-ink-light">Ładowanie...</td>
                </tr>
            </tbody>
        </table>
    </div>
</div>

<!-- Charts Row 2: Client Split + At-Risk -->
<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <!-- Client Split Chart -->
    <div class="refined-card">
        <h3 class="text-lg font-medium mb-4">Nowi vs. powracający klienci</h3>
        <div style="height: 300px;">
            <canvas id="clientSplitChart"></canvas>
        </div>
        <div id="retentionRate" class="text-center mt-4 text-sm text-ink-light"></div>
    </div>

    <!-- At-Risk Clients -->
    <div class="refined-card">
        <h3 class="text-lg font-medium mb-4">Klienci zagrożeni utratą</h3>
        <div id="atRiskList" class="space-y-2 max-h-[300px] overflow-y-auto">
            <p class="text-center text-ink-light">Ładowanie...</p>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_scripts %}
<!-- Chart.js from CDN -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="{{ url_for('static', filename='js/analytics/dashboard.js') }}"></script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add templates/analytics/dashboard.html
git commit -m "feat(analytics): create dashboard template structure

Includes KPI cards, charts placeholders, employee table, at-risk list"
```

---

## Task 11: Dashboard JavaScript - Data Fetching & KPIs

**Files:**
- Create: `static/js/analytics/dashboard.js`

**Step 1: Create dashboard JavaScript**

Create: `static/js/analytics/dashboard.js`

```javascript
/**
 * Analytics Dashboard - Data Fetching and Visualization
 */

// Current period state
let currentPeriod = 'current_month';
let customStartDate = null;
let customEndDate = null;

// Chart instances
let revenueTrendChart = null;
let servicesChart = null;
let clientSplitChart = null;

// Chart.js color palette (Refined Minimal)
const CHART_COLORS = {
    primary: '#2563eb',    // Blue
    purple: '#7c3aed',
    pink: '#db2777',
    orange: '#ea580c',
    green: '#65a30d',
    gray: '#e2e8f0'
};

/**
 * Initialize dashboard on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    // Period selector buttons
    document.querySelectorAll('.period-selector button').forEach(btn => {
        btn.addEventListener('click', () => {
            const period = btn.dataset.period;

            if (period === 'custom') {
                openCustomRangeModal();
            } else {
                selectPeriod(period);
            }
        });
    });

    // Load initial data
    loadDashboard();
});

/**
 * Select period and reload dashboard
 */
function selectPeriod(period) {
    currentPeriod = period;
    customStartDate = null;
    customEndDate = null;

    // Update active button
    document.querySelectorAll('.period-selector button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === period);
    });

    loadDashboard();
}

/**
 * Load all dashboard data
 */
async function loadDashboard() {
    try {
        await Promise.all([
            loadSummary(),
            loadRevenueTrend(),
            loadEmployees(),
            loadServices(),
            loadClients()
        ]);
    } catch (error) {
        console.error('Error loading dashboard:', error);
        Notifications.error('Błąd ładowania danych analitycznych');
    }
}

/**
 * Load summary KPIs
 */
async function loadSummary() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/summary?${params}`);
    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || 'Failed to load summary');
    }

    // Update KPI cards
    updateKPI('revenue', data.current.total_revenue, data.change?.revenue_pct);
    updateKPI('appointments', data.current.total_appointments, data.change?.appointments_pct);
    updateKPI('clients', data.current.unique_clients, data.change?.clients_pct);
    updateKPI('avg-ticket', data.current.avg_ticket, data.change?.avg_ticket_pct);
}

/**
 * Update KPI card with value and change percentage
 */
function updateKPI(key, value, changePct) {
    const valueEl = document.getElementById(`kpi-${key}`);
    const changeEl = document.getElementById(`kpi-${key}-change`);

    // Format value
    if (key === 'revenue' || key === 'avg-ticket') {
        valueEl.textContent = formatCurrency(value, 'PLN');
    } else {
        valueEl.textContent = value.toLocaleString('pl-PL');
    }

    // Format change percentage
    if (changePct !== null && changePct !== undefined) {
        const sign = changePct >= 0 ? '+' : '';
        const color = changePct >= 0 ? 'text-green-600' : 'text-red-600';
        const arrow = changePct >= 0 ? '↑' : '↓';

        changeEl.textContent = `${sign}${changePct.toFixed(1)}% ${arrow}`;
        changeEl.className = `text-sm font-medium ${color}`;
    } else {
        changeEl.textContent = '';
    }
}

/**
 * Build URL parameters for API requests
 */
function buildParams() {
    const params = new URLSearchParams();
    params.set('period', currentPeriod);

    if (currentPeriod === 'custom' && customStartDate && customEndDate) {
        params.set('start_date', customStartDate);
        params.set('end_date', customEndDate);
    }

    return params.toString();
}

/**
 * Format currency in Polish locale
 */
function formatCurrency(amount, currency = 'PLN') {
    return new Intl.NumberFormat('pl-PL', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2
    }).format(amount);
}

/**
 * Custom date range modal functions
 */
function openCustomRangeModal() {
    document.getElementById('customRangeModal').classList.remove('hidden');
}

function closeCustomRange() {
    document.getElementById('customRangeModal').classList.add('hidden');
}

function applyCustomRange() {
    const startDate = document.getElementById('customStartDate').value;
    const endDate = document.getElementById('customEndDate').value;

    if (!startDate || !endDate) {
        Notifications.warning('Wybierz obie daty');
        return;
    }

    if (new Date(startDate) > new Date(endDate)) {
        Notifications.error('Data początkowa musi być wcześniejsza niż końcowa');
        return;
    }

    currentPeriod = 'custom';
    customStartDate = startDate;
    customEndDate = endDate;

    // Update active button
    document.querySelectorAll('.period-selector button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.period === 'custom');
    });

    closeCustomRange();
    loadDashboard();
}
```

**Step 2: Commit**

```bash
git add static/js/analytics/dashboard.js
git commit -m "feat(analytics): add dashboard JS with KPI loading

Implements period selection, data fetching, KPI updates with change indicators"
```

---

## Task 12: Dashboard JavaScript - Charts Implementation

**Files:**
- Modify: `static/js/analytics/dashboard.js`

**Step 1: Add revenue trend chart**

Add to `static/js/analytics/dashboard.js`:

```javascript
/**
 * Load and render revenue trend chart
 */
async function loadRevenueTrend() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/revenue-trend?${params}`);
    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || 'Failed to load revenue trend');
    }

    const ctx = document.getElementById('revenueTrendChart');

    // Destroy existing chart
    if (revenueTrendChart) {
        revenueTrendChart.destroy();
    }

    // Create new chart
    revenueTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.data.map(d => formatDateLabel(d.date)),
            datasets: [{
                label: 'Przychód',
                data: data.data.map(d => d.revenue),
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
                        label: (ctx) => `${formatCurrency(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (val) => `${val.toLocaleString('pl-PL')} zł`
                    }
                }
            }
        }
    });
}

/**
 * Format date for chart labels
 */
function formatDateLabel(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
}
```

**Step 2: Add services chart**

Add to `static/js/analytics/dashboard.js`:

```javascript
/**
 * Load and render services chart
 */
async function loadServices() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/services?${params}`);
    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || 'Failed to load services');
    }

    // Take top 5 services
    const topServices = data.services.slice(0, 5);

    const ctx = document.getElementById('servicesChart');

    // Destroy existing chart
    if (servicesChart) {
        servicesChart.destroy();
    }

    // Create new chart
    servicesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: topServices.map(s => s.service_name),
            datasets: [{
                data: topServices.map(s => s.revenue_generated),
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
            indexAxis: 'y',  // Horizontal bars
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${formatCurrency(ctx.parsed.x)}`
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        callback: (val) => `${val.toLocaleString('pl-PL')} zł`
                    }
                }
            }
        }
    });
}
```

**Step 3: Add client split chart**

Add to `static/js/analytics/dashboard.js`:

```javascript
/**
 * Load and render client metrics
 */
async function loadClients() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/clients?${params}`);
    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || 'Failed to load client metrics');
    }

    // Render client split doughnut chart
    const ctx = document.getElementById('clientSplitChart');

    // Destroy existing chart
    if (clientSplitChart) {
        clientSplitChart.destroy();
    }

    // Create new chart
    clientSplitChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Nowi klienci', 'Powracający'],
            datasets: [{
                data: [
                    data.metrics.new_clients,
                    data.metrics.returning_clients
                ],
                backgroundColor: [CHART_COLORS.primary, CHART_COLORS.gray]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });

    // Update retention rate
    const retentionEl = document.getElementById('retentionRate');
    retentionEl.textContent = `Wskaźnik retencji (90 dni): ${data.metrics.retention_rate.toFixed(1)}%`;

    // Render at-risk clients list
    renderAtRiskList(data.metrics.at_risk_clients);
}

/**
 * Render at-risk clients list
 */
function renderAtRiskList(clients) {
    const listEl = document.getElementById('atRiskList');

    if (clients.length === 0) {
        listEl.innerHTML = '<p class="text-center text-ink-light">Brak klientów zagrożonych utratą</p>';
        return;
    }

    listEl.innerHTML = clients.map(client => `
        <div class="flex justify-between items-center p-2 border-b">
            <div>
                <div class="font-medium">${escapeHtml(client.client_name)}</div>
                <div class="text-sm text-ink-light">
                    Ostatnia wizyta: ${formatDateLabel(client.last_visit_date)}
                </div>
            </div>
            <div class="text-sm text-red-600">
                ${Math.floor(client.days_since_visit)} dni
            </div>
        </div>
    `).join('');
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
```

**Step 4: Commit**

```bash
git add static/js/analytics/dashboard.js
git commit -m "feat(analytics): add Chart.js visualizations

Revenue trend line chart, services bar chart, client split doughnut chart"
```

---

## Task 13: Dashboard JavaScript - Employee Table

**Files:**
- Modify: `static/js/analytics/dashboard.js`

**Step 1: Add employee table rendering**

Add to `static/js/analytics/dashboard.js`:

```javascript
/**
 * Load and render employee performance table
 */
async function loadEmployees() {
    const params = buildParams();
    const response = await fetch(`/api/analytics/employees?${params}`);
    const data = await response.json();

    if (!data.success) {
        throw new Error(data.error || 'Failed to load employees');
    }

    const tbody = document.getElementById('employeeTableBody');

    if (data.employees.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-ink-light">Brak danych</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = data.employees.map(emp => `
        <tr>
            <td class="font-medium">${escapeHtml(emp.employee_name)}</td>
            <td class="text-right">${emp.appointments_count}</td>
            <td class="text-right">${formatCurrency(emp.revenue_generated)}</td>
            <td class="text-right">${formatCurrency(emp.commission_earned)}</td>
            <td class="text-right">${formatCurrency(emp.gross_salary)}</td>
            <td class="text-right" title="Stawka pracodawcy: ${(emp.cost_rate * 100).toFixed(1)}%">
                ${formatCurrency(emp.total_employer_cost)}
            </td>
            <td class="text-right ${emp.net_profit >= 0 ? 'text-green-600' : 'text-red-600'} font-medium">
                ${formatCurrency(emp.net_profit)}
            </td>
        </tr>
    `).join('');
}
```

**Step 2: Commit**

```bash
git add static/js/analytics/dashboard.js
git commit -m "feat(analytics): add employee performance table rendering

Shows revenue, costs, commissions, and net profit with Polish cost model"
```

---

## Task 14: Update Sidebar Navigation

**Files:**
- Modify: `templates/base.html`

**Step 1: Add analytics link to sidebar**

Find the sidebar navigation section in `templates/base.html` and add analytics link after appointments:

```html
<a href="{{ url_for('main.appointments_list') }}"
   class="nav-link {% if request.endpoint == 'main.appointments_list' or request.endpoint.startswith('main.appointments') %}active{% endif %}">
    <span class="material-icons">event</span>
    <span>Wizyty</span>
</a>

<!-- ADD THIS: -->
<a href="{{ url_for('main.analytics_dashboard') }}"
   class="nav-link {% if request.endpoint == 'main.analytics_dashboard' %}active{% endif %}">
    <span class="material-icons">analytics</span>
    <span>Analityka</span>
</a>
```

**Step 2: Commit**

```bash
git add templates/base.html
git commit -m "feat(analytics): add analytics link to sidebar navigation"
```

---

## Task 15: Integration Testing & Bug Fixes

**Files:**
- Various (as needed)

**Step 1: Manual testing checklist**

Start the app and test:

```bash
cd /c/Projects/faktura_scanner_flask/.worktrees/analytics-dashboard
python app.py
```

Visit `http://localhost:8083/analytics` and verify:

1. ✓ Page loads without errors
2. ✓ Period selector buttons work
3. ✓ KPI cards show data with change indicators
4. ✓ Revenue trend chart renders
5. ✓ Services bar chart renders
6. ✓ Employee table populates
7. ✓ Client split chart renders
8. ✓ At-risk clients list shows
9. ✓ Custom date range modal works
10. ✓ Switching periods updates all data

**Step 2: Check browser console for errors**

Open DevTools (F12) and verify no JavaScript errors.

**Step 3: Test with empty data**

Test with date range that has no appointments to verify graceful handling.

**Step 4: Document any bugs found and fix**

Create commits for each bug fix:

```bash
# Example bug fix commit
git commit -m "fix(analytics): handle division by zero in retention rate

When no repeat visits exist, return 0.0 instead of null"
```

**Step 5: Final commit**

```bash
git commit -m "test(analytics): verify dashboard integration

Manual testing completed:
- All charts render correctly
- Period switching works
- Empty state handling verified
- Custom date ranges functional"
```

---

## Task 16: Final Verification & Merge

**Files:**
- N/A

**Step 1: Run full application test**

```bash
python app.py
```

Navigate through:
1. Login
2. Dashboard
3. Analytics page
4. Switch periods
5. Check all charts

**Step 2: Check git status**

```bash
git status
```

Expected: Working tree clean

**Step 3: Review commit history**

```bash
git log --oneline
```

Verify all commits follow convention and tell a clear story.

**Step 4: Push to remote**

```bash
git push origin analytics-dashboard
```

**Step 5: Use finishing-a-development-branch skill**

Invoke `@superpowers:finishing-a-development-branch` to get options for:
- Creating pull request
- Merging to main
- Cleanup

---

## Summary

**Total Tasks**: 16
**Estimated Time**: 4-6 hours (incremental implementation)
**Files Created**: 5 new files
**Files Modified**: 5 existing files
**Lines Added**: ~1,450

**Key Features Delivered**:
- ✅ SQL-first analytics repository with date range support
- ✅ Polish employment cost tracking (22% employer rate)
- ✅ 5 API endpoints for metrics
- ✅ Chart.js visualizations (line, bar, doughnut)
- ✅ Employee performance table with profitability
- ✅ Client retention and at-risk analysis
- ✅ Period comparison (month-over-month, year-over-year)
- ✅ Custom date range selector

**Testing Strategy**:
- Unit tests for repository date calculations
- Mock tests for SQL queries
- Manual integration testing via browser
- Empty state validation

**Next Steps After Implementation**:
- Consider caching for expensive queries
- Add export to Excel for reports
- Implement drill-down capabilities
- Add forecasting/trending features
