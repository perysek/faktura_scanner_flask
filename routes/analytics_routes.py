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
