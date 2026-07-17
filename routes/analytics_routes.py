"""
Analytics API routes
"""
from flask import Blueprint, jsonify, request
from flask_login import login_required
from datetime import date

from config.auth_config import module_permission_required
from repositories.analytics.analytics_repository import AnalyticsRepository
from repositories.analytics.kpi_matrix_repository import KpiMatrixRepository


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


@analytics_bp.route('/analytics/profit', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_profit():
    """Get profit breakdown: revenue - employee costs - invoice costs"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, prev_start, prev_end = ranges

    # Current period data
    revenue_data = repo.get_revenue_summary(current_start, current_end)
    employee_data = repo.get_employee_performance(current_start, current_end)
    invoice_data = repo.get_invoice_costs(current_start, current_end)

    revenue = float(revenue_data.get('total_revenue', 0) or 0)
    employee_costs = sum(
        float(e.get('total_employer_cost', 0) or 0) for e in employee_data
    )
    invoice_costs = float(invoice_data.get('total_costs', 0) or 0)
    gross_profit = revenue - employee_costs
    net_profit = gross_profit - invoice_costs
    profit_margin_pct = round((net_profit / revenue * 100), 1) if revenue > 0 else 0.0

    # Previous period comparison (when not custom range)
    change = None
    if prev_start and prev_end:
        prev_revenue_data = repo.get_revenue_summary(prev_start, prev_end)
        prev_employee_data = repo.get_employee_performance(prev_start, prev_end)
        prev_invoice_data = repo.get_invoice_costs(prev_start, prev_end)

        prev_revenue = float(prev_revenue_data.get('total_revenue', 0) or 0)
        prev_employee_costs = sum(
            float(e.get('total_employer_cost', 0) or 0) for e in prev_employee_data
        )
        prev_invoice_costs = float(prev_invoice_data.get('total_costs', 0) or 0)
        prev_net_profit = prev_revenue - prev_employee_costs - prev_invoice_costs

        def pct_change(curr, prev):
            if prev == 0:
                return 0.0
            return round(((curr - prev) / prev) * 100, 1)

        change = {
            'net_profit_pct': pct_change(net_profit, prev_net_profit)
        }

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        "revenue": revenue,
        "employee_costs": round(employee_costs, 2),
        "invoice_costs": round(invoice_costs, 2),
        "gross_profit": round(gross_profit, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin_pct": profit_margin_pct,
        "invoice_details": {
            "invoice_count": int(invoice_data.get('invoice_count', 0) or 0),
            "unpaid_count": int(invoice_data.get('unpaid_count', 0) or 0),
            "unpaid_amount": float(invoice_data.get('unpaid_amount', 0) or 0)
        },
        "change": change
    })


@analytics_bp.route('/analytics/occupancy', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_occupancy():
    """Get salon occupancy and visit quality metrics"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, _, _ = ranges

    data = repo.get_occupancy_stats(current_start, current_end)

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        **data
    })


@analytics_bp.route('/analytics/peak-hours', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_peak_hours():
    """Get appointment count by hour-of-day and day-of-week for heatmap"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, _, _ = ranges

    data = repo.get_peak_hours(current_start, current_end)

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        "data": data
    })


@analytics_bp.route('/analytics/service-analysis', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_service_analysis():
    """Get service price discipline analysis (catalogue vs charged)"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, _, _ = ranges

    services = repo.get_service_price_analysis(current_start, current_end)

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        "services": services
    })


@analytics_bp.route('/analytics/monthly-trend', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_monthly_trend():
    """12-month rolling income/costs/profit — always relative to today, no period param"""
    months = repo.get_monthly_profit_trend()
    return jsonify({"success": True, "months": months})


@analytics_bp.route('/analytics/top-clients', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_top_clients():
    """Top 10 klientów wg wyniku (wizyty × przychód) dla wybranego okresu"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, _, _ = ranges
    clients = repo.get_top_clients(current_start, current_end)
    return jsonify({"success": True, "clients": clients})


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


@analytics_bp.route('/analytics/rolling/satisfaction-rating', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_rolling_satisfaction_rating():
    """Średnia ocena klientów (1–5) ogółem + per pracownik — ruchome okno 12M"""
    data = repo.get_satisfaction_rating_monthly()
    return jsonify({"success": True, **data})


@analytics_bp.route('/analytics/kpi-matrix', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_kpi_matrix():
    """Macierz 20 wskaźników biznesowych (10 procesów × eff./effic.) dla wybranego roku."""
    kpi_repo = KpiMatrixRepository()
    min_year, max_year = kpi_repo.get_available_year_range()

    year_param = request.args.get('year')
    try:
        year = int(year_param) if year_param else max_year
    except ValueError:
        return jsonify({"success": False, "error": "Nieprawidłowy rok"}), 400

    if year < min_year or year > max_year:
        return jsonify({"success": False, "error": f"Rok poza zakresem danych ({min_year}-{max_year})"}), 400

    matrix = kpi_repo.get_kpi_matrix(year)

    return jsonify({
        "success": True,
        "year": year,
        "min_year": min_year,
        "max_year": max_year,
        "processes": matrix['processes'],
    })


@analytics_bp.route('/analytics/insights', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_insights():
    """Get algorithmic business insights for the selected period"""
    ranges, error = parse_period_params()
    if error:
        return jsonify({"success": False, **error}), 400

    current_start, current_end, _, _ = ranges

    insights = repo.get_business_insights(current_start, current_end)

    return jsonify({
        "success": True,
        "period": request.args.get('period', 'current_month'),
        "insights": insights
    })


# ============================================================================
# PER-EMPLOYEE ANALYTICS ENDPOINTS
# ============================================================================

def _get_employee_analytics_repo(employee_id: int):
    """Return (repo, None) or (None, error_response) if employee not found.

    Widok administratora: a superuser-linked employee is treated as non-existent
    (404) while admin view is OFF — this single guard covers all eight per-employee
    analytics endpoints below, so the owner's drill-down is unreachable by default.
    """
    from flask import current_app
    from config.admin_view import is_employee_hidden
    from repositories.employees.employee_analytics_repository import EmployeeAnalyticsRepository
    if is_employee_hidden(employee_id):
        return None, (jsonify({"success": False, "error": "Pracownik nie znaleziony"}), 404)
    row = current_app.employee_repo.get_by_id(employee_id)
    if not row:
        return None, (jsonify({"success": False, "error": "Pracownik nie znaleziony"}), 404)
    return EmployeeAnalyticsRepository(employee_id), None


@analytics_bp.route('/employees/<int:employee_id>/analytics/summary', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_summary(employee_id: int):
    """KPI summary: revenue, employer cost, net profit, avg ticket, total appointments."""
    emp_repo, err = _get_employee_analytics_repo(employee_id)
    if err:
        return err
    months = int(request.args.get('months', 12))
    data = emp_repo.get_summary(months)
    return jsonify({"success": True, "employee_id": employee_id, "data": data})


@analytics_bp.route('/employees/<int:employee_id>/analytics/revenue-trend', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_revenue_trend(employee_id: int):
    """Monthly revenue + commission + appointments trend."""
    emp_repo, err = _get_employee_analytics_repo(employee_id)
    if err:
        return err
    months = int(request.args.get('months', 12))
    data = emp_repo.get_revenue_trend(months)
    return jsonify({"success": True, "employee_id": employee_id, "data": data})


@analytics_bp.route('/employees/<int:employee_id>/analytics/services-mix', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_services_mix(employee_id: int):
    """Top 10 services by appointment count."""
    emp_repo, err = _get_employee_analytics_repo(employee_id)
    if err:
        return err
    data = emp_repo.get_services_mix()
    return jsonify({"success": True, "employee_id": employee_id, "data": data})


@analytics_bp.route('/employees/<int:employee_id>/analytics/peak-hours', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_peak_hours(employee_id: int):
    """Appointment heatmap data by day-of-week and hour-of-day."""
    emp_repo, err = _get_employee_analytics_repo(employee_id)
    if err:
        return err
    data = emp_repo.get_peak_hours()
    return jsonify({"success": True, "employee_id": employee_id, "data": data})


@analytics_bp.route('/employees/<int:employee_id>/analytics/client-split', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_client_split(employee_id: int):
    """Monthly new vs returning client split."""
    emp_repo, err = _get_employee_analytics_repo(employee_id)
    if err:
        return err
    months = int(request.args.get('months', 12))
    data = emp_repo.get_client_split(months)
    return jsonify({"success": True, "employee_id": employee_id, "data": data})


@analytics_bp.route('/employees/<int:employee_id>/analytics/skills-radar', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_skills_radar(employee_id: int):
    """Skills parsed from employee record as [{skill, rating}]."""
    emp_repo, err = _get_employee_analytics_repo(employee_id)
    if err:
        return err
    data = emp_repo.get_skills_radar()
    return jsonify({"success": True, "employee_id": employee_id, "data": data})


@analytics_bp.route('/employees/<int:employee_id>/analytics/commission-trend', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_commission_trend(employee_id: int):
    """Monthly base_salary vs commission_earned vs gross_salary trend."""
    emp_repo, err = _get_employee_analytics_repo(employee_id)
    if err:
        return err
    months = int(request.args.get('months', 12))
    data = emp_repo.get_commission_trend(months)
    return jsonify({"success": True, "employee_id": employee_id, "data": data})


@analytics_bp.route('/employees/<int:employee_id>/analytics/satisfaction', methods=['GET'])
@login_required
@module_permission_required('appointments')
def get_employee_satisfaction(employee_id: int):
    """Satisfaction stats: avg_score, distribution, by_service_category, monthly_trend."""
    emp_repo, err = _get_employee_analytics_repo(employee_id)
    if err:
        return err
    months = int(request.args.get('months', 12))
    data = emp_repo.get_satisfaction_stats(months)
    return jsonify({"success": True, "employee_id": employee_id, "data": data})
