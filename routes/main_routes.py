"""
Main page routes - renders Jinja templates
"""
from flask import (
    Blueprint, render_template, redirect, url_for, current_app,
    request, jsonify, session,
)
from flask_login import login_required, current_user

from config.auth_config import module_permission_required, role_required
from config.admin_view import (
    admin_view_active, is_superuser, is_employee_hidden, own_data_active,
)
from config.database import get_db_connection

main_bp = Blueprint('main', __name__)


# ============================================================================
# ADMIN VIEW TOGGLES ("Widok administratora" + "Dane własne")
# ============================================================================

@main_bp.route('/api/admin-view', methods=['POST'])
@login_required
def toggle_admin_view():
    """Flip the session-scoped "Widok administratora" flag.

    Superuser-only: the flag is meaningless (and inert) for every other role, so a
    non-superuser POST is rejected with 403 rather than silently ignored. Logout
    clears the whole session, so the flag resets to OFF automatically on sign-out.

    Turning admin view OFF also clears "Dane własne" — that sub-toggle only exists
    while admin view is ON, so it must not silently persist into the next session.

    Body: ``{"enabled": bool}``. Response: ``{"ok": true, "enabled": bool}``.
    """
    if not is_superuser():
        return jsonify({'ok': False, 'error': 'Brak uprawnień.'}), 403

    payload = request.get_json(silent=True) or {}
    session['admin_view'] = bool(payload.get('enabled', False))
    if not session['admin_view']:
        session['own_data'] = False
    # Persist alongside the 30-day sliding session (matches login's permanent flag).
    session.permanent = True
    return jsonify({'ok': True, 'enabled': session['admin_view']})


@main_bp.route('/api/own-data', methods=['POST'])
@login_required
def toggle_own_data():
    """Flip the session-scoped "Dane własne" flag (show only the logged-in user's
    own employee data across every view).

    Superuser-only AND only while admin view is ON — the checkbox is editable only
    then, and the server enforces the same rule so a forged flag can't take effect
    without admin view. Rejects non-superusers (403) and any attempt to set it
    while admin view is OFF (400).

    Body: ``{"enabled": bool}``. Response: ``{"ok": true, "enabled": bool}``.
    """
    if not is_superuser():
        return jsonify({'ok': False, 'error': 'Brak uprawnień.'}), 403
    if not admin_view_active():
        return jsonify({'ok': False,
                        'error': 'Najpierw włącz widok administratora.'}), 400

    payload = request.get_json(silent=True) or {}
    session['own_data'] = bool(payload.get('enabled', False))
    session.permanent = True
    return jsonify({'ok': True, 'enabled': session['own_data']})


@main_bp.route('/')
def index():
    """Public entry point.

    Anonymous visitors see the marketing landing page (with a "Zaloguj się"
    button that routes to the login view); authenticated users get the app
    dashboard exactly as before. This makes the landing page the first thing a
    visitor hits at the site root, without disturbing the logged-in experience.
    """
    if current_user.is_authenticated:
        return render_template('dashboard/index.html')
    return render_template('landing/index.html')


@main_bp.route('/invoices')
@login_required
@module_permission_required('invoices')
def invoices_list():
    """Main view - invoice list with refined minimal design"""
    return render_template('invoices/list_refined.html')


@main_bp.route('/upload')
@login_required
@module_permission_required('invoices')
def upload():
    """Upload view - PDF import and OCR processing"""
    return render_template('invoices/upload.html')


@main_bp.route('/invoice/<int:invoice_id>/edit')
@login_required
@module_permission_required('invoices')
def edit_invoice(invoice_id):
    """Edit view - edit invoice data"""
    row = current_app.invoice_repo.get_by_id(invoice_id)
    if not row:
        return render_template('errors/404.html'), 404

    # Convert Row to Invoice object
    invoice = current_app.invoice_repo.row_to_invoice(row)

    return render_template('invoices/edit.html', invoice=invoice)


@main_bp.route('/invoice/create')
@login_required
@module_permission_required('invoices')
def create_invoice():
    """Create view - manual invoice entry"""
    return render_template('invoices/create.html')


@main_bp.route('/history')
@login_required
@module_permission_required('invoices')
def history():
    """History view with refined minimal design"""
    return render_template('history/list_refined.html')


@main_bp.route('/sellers')
@login_required
@module_permission_required('invoices')
def sellers_list():
    """Sellers list view with refined minimal design"""
    return render_template('sellers/list_refined.html')


@main_bp.route('/seller/create')
@login_required
@module_permission_required('invoices')
def create_seller():
    """Create new seller form"""
    return render_template('sellers/create.html')


@main_bp.route('/seller/<int:seller_id>/edit')
@login_required
@module_permission_required('invoices')
def edit_seller(seller_id):
    """Edit seller form"""
    row = current_app.seller_repo.get_by_id(seller_id)
    if not row:
        return render_template('errors/404.html'), 404
    seller = current_app.seller_repo.row_to_seller(row)
    return render_template('sellers/edit.html', seller=seller)


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard view - statistics and overview"""
    return render_template('dashboard/index.html')


# ============================================================================
# CLIENT MANAGEMENT ROUTES
# ============================================================================

@main_bp.route('/clients')
@login_required
@module_permission_required('clients')
def clients_list():
    """Client list view"""
    return render_template('clients/list.html')


@main_bp.route('/client/create')
@login_required
@module_permission_required('clients')
def create_client():
    """Create new client form"""
    return render_template('clients/create.html')


@main_bp.route('/client/<int:client_id>')
@login_required
@module_permission_required('clients')
def view_client(client_id):
    """View client details"""
    row = current_app.client_repo.get_by_id(client_id)
    if not row:
        return render_template('errors/404.html'), 404

    client = current_app.client_repo.row_to_client(row)
    return render_template('clients/view.html', client=client)


@main_bp.route('/client/<int:client_id>/edit')
@login_required
@module_permission_required('clients')
def edit_client(client_id):
    """Edit client form"""
    row = current_app.client_repo.get_by_id(client_id)
    if not row:
        return render_template('errors/404.html'), 404

    client = current_app.client_repo.row_to_client(row)
    return render_template('clients/edit.html', client=client)


# ============================================================================
# SERVICES ROUTES
# ============================================================================

@main_bp.route('/services')
@login_required
@module_permission_required('services')
def services_list():
    """Services list view"""
    return render_template('services/list.html')


@main_bp.route('/service/create')
@login_required
@module_permission_required('services')
def create_service():
    """Create new service form — inject categories from DB"""
    categories = current_app.service_category_repo.get_all()
    return render_template('services/create.html', categories=categories)


@main_bp.route('/service/<int:service_id>')
@login_required
@module_permission_required('services')
def view_service(service_id):
    """View service details"""
    row = current_app.service_repo.get_by_id(service_id)
    if not row:
        return render_template('errors/404.html'), 404

    service = current_app.service_repo.row_to_service(row)
    return render_template('services/view.html', service=service)


@main_bp.route('/service/<int:service_id>/edit')
@login_required
@module_permission_required('services')
def edit_service(service_id):
    """Edit service form — inject categories from DB"""
    row = current_app.service_repo.get_by_id(service_id)
    if not row:
        return render_template('errors/404.html'), 404

    service = current_app.service_repo.row_to_service(row)
    categories = current_app.service_category_repo.get_all()
    return render_template('services/edit.html', service=service, categories=categories)


@main_bp.route('/services/categories')
@login_required
@module_permission_required('services')
def service_categories_list():
    """Zarządzanie kategoriami usług"""
    return render_template('services/categories/list.html')


# ============================================================================
# EMPLOYEES ROUTES
# ============================================================================

@main_bp.route('/employees')
@login_required
@module_permission_required('employees')
def employees_list():
    """Employees list view"""
    return render_template('employees/list.html')


@main_bp.route('/employee/create')
@login_required
@module_permission_required('employees')
def create_employee():
    """Create new employee form"""
    from repositories.users.user_repository import UserRepository
    forma_options = current_app.forma_zatrudnienia_repo.get_all()
    user_options = UserRepository().get_active_users()
    return render_template('employees/create.html', forma_options=forma_options, user_options=user_options)


@main_bp.route('/employee/<int:employee_id>')
@login_required
@module_permission_required('employees')
def view_employee(employee_id):
    """View employee details"""
    # Widok administratora: the owner's employee page is 404 while admin view is OFF.
    if is_employee_hidden(employee_id):
        return render_template('errors/404.html'), 404
    row = current_app.employee_repo.get_by_id(employee_id)
    if not row:
        return render_template('errors/404.html'), 404

    employee = current_app.employee_repo.row_to_employee(row)
    forma_nazwa = None
    if employee.forma_zatrudnienia_id:
        forma_row = current_app.forma_zatrudnienia_repo.get_by_id(employee.forma_zatrudnienia_id)
        if forma_row:
            forma_nazwa = forma_row['nazwa']
    return render_template('employees/view.html', employee=employee, forma_nazwa=forma_nazwa)


@main_bp.route('/employee/<int:employee_id>/edit')
@login_required
@module_permission_required('employees')
def edit_employee(employee_id):
    """Edit employee form"""
    # Widok administratora: the owner's employee is non-existent (404) while OFF.
    if is_employee_hidden(employee_id):
        return render_template('errors/404.html'), 404
    row = current_app.employee_repo.get_by_id(employee_id)
    if not row:
        return render_template('errors/404.html'), 404

    employee = current_app.employee_repo.row_to_employee(row)
    from repositories.users.user_repository import UserRepository
    forma_options = current_app.forma_zatrudnienia_repo.get_all()
    user_options = UserRepository().get_active_users()

    # Direct reports section: all active employees except self
    all_employees = current_app.employee_repo.get_all(active_only=True)
    other_employees = [e for e in all_employees if e['id'] != employee_id]

    # Current direct reports of this employee (they report to employee_id)
    subordinate_rows = current_app.supervisor_repo.list_subordinates_for(employee_id)
    current_direct_report_ids = {r['id'] for r in subordinate_rows}

    # Employees who ARE supervisors of this employee — cannot be selected as direct reports
    supervisor_rows = current_app.supervisor_repo.list_supervisors_for(employee_id)
    my_supervisor_ids = {r['id'] for r in supervisor_rows}

    return render_template(
        'employees/edit.html',
        employee=employee,
        forma_options=forma_options,
        user_options=user_options,
        other_employees=other_employees,
        current_direct_report_ids=current_direct_report_ids,
        my_supervisor_ids=my_supervisor_ids,
    )


@main_bp.route('/formy-zatrudnienia')
@login_required
@module_permission_required('employees')
def formy_zatrudnienia_list():
    """Formy zatrudnienia — lista i zarządzanie"""
    return render_template('employees/formy_zatrudnienia/list.html')


# ============================================================================
# APPOINTMENTS ROUTES
# ============================================================================

@main_bp.route('/appointments')
@login_required
@module_permission_required('appointments')
def appointments_list():
    """Appointments list/calendar view"""
    return render_template('appointments/list.html')


@main_bp.route('/appointments/calendar')
@login_required
@module_permission_required('appointments')
def appointments_calendar():
    """Appointments calendar day view"""
    return render_template('appointments/calendar.html')


@main_bp.route('/appointments/calendar/week')
@login_required
@module_permission_required('appointments')
def appointments_calendar_week():
    """Appointments calendar week view"""
    return render_template('appointments/calendar_week.html')


@main_bp.route('/appointments/calendar/month')
@login_required
@module_permission_required('appointments')
def appointments_calendar_month():
    """Appointments calendar month view"""
    return render_template('appointments/calendar_month.html')


@main_bp.route('/appointment/create')
@login_required
@module_permission_required('appointments')
def create_appointment():
    """Create new appointment form"""
    return render_template('appointments/create.html')


@main_bp.route('/appointment/<int:appointment_id>')
@login_required
@module_permission_required('appointments')
def view_appointment(appointment_id):
    """View appointment details"""
    from repositories.sms.sms_repository import (
        SmsSettingsRepository, SmsMessageTypeRepository, SmsReminderRepository
    )
    sms_settings = SmsSettingsRepository().get_settings() or {}
    sms_types = SmsMessageTypeRepository().get_all() if sms_settings.get('is_active') else []
    sms_sent_keys = SmsReminderRepository().get_sent_type_keys_for_appointment(appointment_id)
    return render_template(
        'appointments/view.html',
        appointment_id=appointment_id,
        settings_sms_active=sms_settings.get('is_active', False),
        sms_message_types=sms_types,
        sms_sent_type_keys=sms_sent_keys,
    )


@main_bp.route('/appointment/<int:appointment_id>/edit')
@login_required
@module_permission_required('appointments')
def edit_appointment(appointment_id):
    """Edit appointment"""
    return render_template('appointments/edit.html', appointment_id=appointment_id)


@main_bp.route('/superadmin/visits/latest')
@login_required
@module_permission_required('data_correction')
def superadmin_edit_latest():
    """Redirect to the most recently created appointment in the power editor"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM appointments ORDER BY id DESC LIMIT 1')
        row = cur.fetchone()
    if not row:
        return redirect(url_for('main.appointments_list'))
    return redirect(url_for('main.superadmin_edit_visit', appointment_id=row[
        'id']))

@main_bp.route('/superadmin/visits/<int:appointment_id>')
@login_required
@module_permission_required('data_correction')
def superadmin_edit_visit(appointment_id):
    """Power editor for any appointment (requires data_correction module)"""
    return render_template('appointments/superadmin_edit.html', appointment_id=appointment_id)


@main_bp.route('/superadmin/visits/table')
@login_required
@module_permission_required('data_correction')
def superadmin_edit_table():
    """Editable table view for bulk appointment editing (requires data_correction module)"""
    return render_template('appointments/superadmin_edit_table.html')


# ============================================================================
# INCOME ROUTES
# ============================================================================

@main_bp.route('/income')
@login_required
@module_permission_required('appointments')
def income_dashboard():
    """Income dashboard view"""
    return render_template('income/dashboard.html')


# ============================================================================
# ANALYTICS ROUTES
# ============================================================================

@main_bp.route('/analytics')
@login_required
@module_permission_required('appointments')
def analytics_dashboard():
    """Analytics dashboard view"""
    return render_template('analytics/dashboard.html')


@main_bp.route('/analytics/wskazniki-biznesowe')
@login_required
@module_permission_required('appointments')
def kpi_matrix():
    """ISO 9001/IATF-style monthly business KPI matrix, one process row-group per indicator."""
    return render_template('analytics/kpi_matrix.html')


# ============================================================================
# SETTINGS ROUTES
# ============================================================================

@main_bp.route('/my-visits')
@login_required
def my_visits():
    """Mobile-first page: today's appointments for the logged-in employee."""
    from repositories.employees.employee_repository import EmployeeRepository
    from repositories.appointments.appointment_repository import AppointmentRepository
    from datetime import datetime, timedelta

    employee = EmployeeRepository().get_by_user_id(current_user.id)
    if not employee:
        return render_template('appointments/my_visits.html',
                               appointments=[], employee=None, no_employee=True)

    rows = AppointmentRepository().get_today_for_employee(employee['id'])
    now = datetime.now()
    appointments = []
    for row in rows:
        a = dict(row)
        a['start_time'] = str(a['start_time'])[:5]
        a['appointment_date'] = str(a['appointment_date'])
        # Compute minutes until start for the template
        try:
            h, m = a['start_time'].split(':')
            start_dt = datetime.combine(datetime.today(), datetime.min.time().replace(
                hour=int(h), minute=int(m)))
            a['minutes_until'] = int((start_dt - now).total_seconds() / 60)
        except Exception:
            a['minutes_until'] = 9999
        appointments.append(a)

    return render_template('appointments/my_visits.html',
                           appointments=appointments, employee=dict(employee),
                           no_employee=False)


@main_bp.route('/settings/email')
@login_required
@module_permission_required('invoices')
def email_settings():
    """Email settings view - IMAP configuration"""
    return render_template('settings/email.html')


@main_bp.route('/import')
@login_required
@module_permission_required('data_import')
def import_page():
    """Admin import page — caldis.pl Playwright import."""
    return render_template('data_import/index.html')


# ============================================================================
# USER MANUAL
# ============================================================================

@main_bp.route('/instrukcja')
@login_required
def user_manual():
    """In-app user manual / help center. Self-contained page (landing-page
    design language, no Tailwind/base.html dependency) open to every role —
    no module_permission_required gate, since it documents the whole app."""
    from datetime import date
    return render_template('manual/index.html', manual_updated=date.today().strftime('%d.%m.%Y'))
