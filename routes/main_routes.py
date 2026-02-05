"""
Main page routes - renders Jinja templates
"""
from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user

from config.auth_config import module_permission_required

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


@main_bp.route('/settings/email')
@login_required
@module_permission_required('invoices')
def email_settings():
    """Email settings view - IMAP configuration"""
    return render_template('settings/email.html')
