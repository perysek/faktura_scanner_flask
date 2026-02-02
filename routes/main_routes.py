"""
Main page routes - renders Jinja templates
"""
from flask import Blueprint, render_template, current_app

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/invoices')
def invoices_list():
    """Main view - invoice list with refined minimal design"""
    return render_template('invoices/list_refined.html')


@main_bp.route('/upload')
def upload():
    """Upload view - PDF import and OCR processing"""
    return render_template('invoices/upload.html')


@main_bp.route('/invoice/<int:invoice_id>/edit')
def edit_invoice(invoice_id):
    """Edit view - edit invoice data"""
    row = current_app.invoice_repo.get_by_id(invoice_id)
    if not row:
        return render_template('errors/404.html'), 404

    # Convert Row to Invoice object
    invoice = current_app.invoice_repo.row_to_invoice(row)

    return render_template('invoices/edit.html', invoice=invoice)


@main_bp.route('/invoice/create')
def create_invoice():
    """Create view - manual invoice entry"""
    return render_template('invoices/create.html')


@main_bp.route('/history')
def history():
    """History view with refined minimal design"""
    return render_template('history/list_refined.html')


@main_bp.route('/sellers')
def sellers_list():
    """Sellers list view with refined minimal design"""
    return render_template('sellers/list_refined.html')


@main_bp.route('/seller/create')
def create_seller():
    """Create new seller form"""
    return render_template('sellers/create.html')


@main_bp.route('/seller/<int:seller_id>/edit')
def edit_seller(seller_id):
    """Edit seller form"""
    row = current_app.seller_repo.get_by_id(seller_id)
    if not row:
        return render_template('errors/404.html'), 404
    seller = current_app.seller_repo.row_to_seller(row)
    return render_template('sellers/edit.html', seller=seller)


@main_bp.route('/dashboard')
def dashboard():
    """Dashboard view - statistics and overview"""
    return render_template('dashboard/index.html')


@main_bp.route('/settings/email')
def email_settings():
    """Email settings view - IMAP configuration"""
    return render_template('settings/email.html')
