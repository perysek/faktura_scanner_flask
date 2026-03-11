"""
Main page routes - renders Jinja templates
"""
from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user

from config.auth_config import module_permission_required, role_required

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    """Redirect to dashboard"""
    return render_template('dashboard/index.html')


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
    """Create new service form"""
    return render_template('services/create.html')


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
    """Edit service form"""
    row = current_app.service_repo.get_by_id(service_id)
    if not row:
        return render_template('errors/404.html'), 404

    service = current_app.service_repo.row_to_service(row)
    return render_template('services/edit.html', service=service)


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
    row = current_app.employee_repo.get_by_id(employee_id)
    if not row:
        return render_template('errors/404.html'), 404

    employee = current_app.employee_repo.row_to_employee(row)
    from repositories.users.user_repository import UserRepository
    forma_options = current_app.forma_zatrudnienia_repo.get_all()
    user_options = UserRepository().get_active_users()
    return render_template('employees/edit.html', employee=employee, forma_options=forma_options, user_options=user_options)


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
    return render_template('appointments/view.html', appointment_id=appointment_id)


@main_bp.route('/appointment/<int:appointment_id>/edit')
@login_required
@module_permission_required('appointments')
def edit_appointment(appointment_id):
    """Edit appointment"""
    return render_template('appointments/edit.html', appointment_id=appointment_id)


@main_bp.route('/superadmin/visits/<int:appointment_id>')
@login_required
@role_required('superuser')
def superadmin_edit_visit(appointment_id):
    """Superuser-only power editor for any appointment"""
    return render_template('appointments/superadmin_edit.html', appointment_id=appointment_id)


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


# ============================================================================
# SETTINGS ROUTES
# ============================================================================

@main_bp.route('/settings/email')
@login_required
@module_permission_required('invoices')
def email_settings():
    """Email settings view - IMAP configuration"""
    return render_template('settings/email.html')
