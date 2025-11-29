"""
Main page routes - renders Jinja templates
"""
from flask import Blueprint, render_template, current_app

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@main_bp.route('/invoices')
def invoices_list():
    """Main view - invoice list with search and statistics"""
    return render_template('invoices/list.html')


@main_bp.route('/upload')
def upload():
    """Upload view - PDF import and OCR processing"""
    return render_template('invoices/upload.html')


@main_bp.route('/invoice/<int:invoice_id>/edit')
def edit_invoice(invoice_id):
    """Edit view - edit invoice data"""
    invoice = current_app.invoice_repo.get_by_id(invoice_id)
    if not invoice:
        return render_template('errors/404.html'), 404
    return render_template('invoices/edit.html', invoice=invoice)


@main_bp.route('/history')
def history():
    """History view - audit trail"""
    return render_template('history/list.html')


@main_bp.route('/settings/email')
def email_settings():
    """Email settings view - IMAP configuration"""
    return render_template('settings/email.html')
