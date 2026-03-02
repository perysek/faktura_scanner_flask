"""
API routes - JSON endpoints for AJAX calls
"""
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from flask import Blueprint, jsonify, request, current_app, send_file, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from config.auth_config import module_permission_required
from database.models import Invoice
from utils.validators import DateParser
from repositories.audit_repository import AuditRepository

api_bp = Blueprint('api', __name__)


def _audit(entity_type, action, entity_id=None, entity_label=None,
           field_name=None, old_value=None, new_value=None):
    """Log audit event with current user context. Logs errors to stderr."""
    try:
        uid = current_user.id if current_user.is_authenticated else None
        uname = current_user.full_name if current_user.is_authenticated else None
        AuditRepository().log_event(
            entity_type=entity_type, action=action,
            entity_id=entity_id, entity_label=entity_label,
            field_name=field_name, old_value=old_value, new_value=new_value,
            user_id=uid, user_name=uname,
        )
    except Exception as e:
        import sys
        print(f"[AUDIT ERROR] {entity_type}/{action} id={entity_id}: {e}", file=sys.stderr)


def _canonical(value) -> str:
    """Return a canonical string for a value so numeric type differences
    (DB float 2000.0 vs JSON int 2000) do not produce false change detections."""
    if value is None or value == '':
        return ''
    try:
        f = float(str(value))
        # Whole numbers: drop the decimal so "2000.0" == "2000"
        return str(int(f)) if f == int(f) else str(f)
    except (ValueError, TypeError):
        return str(value).strip()


def _audit_changes(entity_type: str, entity_id: int, entity_label: str,
                   old_dict: dict, new_dict: dict, tracked_fields: list):
    """Log one audit UPDATE entry per changed field.

    Compares old_dict[field] vs new_dict[field] for each field in
    tracked_fields and calls _audit for every field whose value changed.
    Values are normalised via _canonical() before comparison so that type
    differences (e.g. DB float 2000.0 vs JSON int 2000) are not treated as changes.
    """
    for field in tracked_fields:
        if field not in new_dict:   # field was not sent — not a change
            continue
        old_raw = old_dict.get(field)
        new_raw = new_dict.get(field)
        old_val = _canonical(old_raw)
        new_val = _canonical(new_raw)
        if old_val != new_val:
            _audit(entity_type, 'UPDATE', entity_id=entity_id,
                   entity_label=entity_label,
                   field_name=field,
                   old_value=old_val or None,
                   new_value=new_val or None)


# Supported file extensions for upload
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'tiff', 'tif', 'bmp'}
IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'tiff', 'tif', 'bmp'}


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed (PDF or image files)"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_image_file(filename: str) -> bool:
    """Check if file is an image (not PDF)"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in IMAGE_EXTENSIONS


def parse_date_string(date_str: Optional[str]) -> Optional[date]:
    """
    Parse date string to date object.
    Wrapper around centralized DateParser for backward compatibility.
    """
    return DateParser.parse(date_str)


@api_bp.route('/invoices', methods=['GET'])
@login_required
@module_permission_required('invoices')
def get_invoices():
    """Get all invoices with optional filtering"""
    search_query = request.args.get('search', '').strip()

    try:
        if search_query:
            rows = current_app.invoice_repo.search(search_query)
        else:
            rows = current_app.invoice_repo.get_all()

        # Convert Row objects to Invoice objects, then to dicts for JSON serialization
        invoices = [current_app.invoice_repo.row_to_invoice(row) for row in rows]
        invoices_data = [vars(invoice) for invoice in invoices]

        return jsonify({
            'success': True,
            'invoices': invoices_data,
            'count': len(invoices_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/invoices', methods=['POST'])
@login_required
@module_permission_required('invoices')
def create_invoice_manual():
    """Create invoice manually with optional PDF upload"""
    try:
        # Check if it's multipart/form-data (has files) or JSON
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.form.to_dict()
        else:
            data = request.get_json()
        
        # Create Invoice object from form data
        invoice = Invoice(
            id=None,  # Will be set by database
            invoice_number=data.get('invoice_number'),
            seller_name=data.get('seller_name'),
            seller_nip=data.get('seller_nip'),
            invoice_date=parse_date_string(data.get('invoice_date')),
            amount=float(data.get('amount', 0)),
            currency=data.get('currency', 'PLN'),
            status=data.get('status', 'Nieopłacona'),
            payment_due_date=parse_date_string(data.get('payment_due_date')) if data.get('payment_due_date') else None,
            payment_term=data.get('payment_term'),
            bank_account=data.get('bank_account'),
            pdf_path=None,  # Will be set after file upload
            ocr_confidence=None,  # Manual entry, no OCR
            created_at=None,  # Will be set by database
            updated_at=None
        )
        
        # Validate invoice
        validation_result = current_app.validation_service.validate_invoice(invoice)
        validation_warnings = validation_result.get('warnings', [])
        
        if validation_result.get('errors'):
            return jsonify({
                'success': False,
                'error': 'Validation failed',
                'validation_errors': validation_result
            }), 400
        
        # Check if this is a confirmation resubmission
        seller_action = data.get('seller_action')
        seller_id = None
        
        if seller_action:
            # User confirmed an action - process it
            normalized_nip = current_app.seller_service.normalize_nip(invoice.seller_nip)
            normalized_name = current_app.seller_service.normalize_seller_name(invoice.seller_name)
            
            if seller_action == 'create_new':
                # Create new seller
                seller_id, created = current_app.seller_repo.get_or_create(
                    nip=normalized_nip,
                    name=normalized_name,
                    address=data.get('seller_address')
                )
                validation_warnings.append(f"✓ Utworzono nowego sprzedawcę: {normalized_name}")
                
            elif seller_action == 'use_existing':
                # Use existing seller
                existing_seller_id = int(data.get('existing_seller_id'))
                seller_row = current_app.seller_repo.get_by_id(existing_seller_id)
                if seller_row:
                    seller = current_app.seller_repo.row_to_seller(seller_row)
                    invoice.seller_name = seller.seller_name
                    invoice.seller_nip = seller.seller_nip
                    seller_id = existing_seller_id
                    validation_warnings.append(f"✓ Używam istniejącego sprzedawcy: {seller.seller_name}")
                    
            elif seller_action == 'update_seller':
                # Update seller name
                existing_seller_id = int(data.get('existing_seller_id'))
                current_app.seller_repo.update_name(existing_seller_id, normalized_name)
                seller_id = existing_seller_id
                validation_warnings.append(f"✓ Zaktualizowano sprzedawcę na: {normalized_name}")
        else:
            # First submission - validate seller
            if invoice.seller_nip:
                try:
                    # Normalize seller data
                    normalized_nip = current_app.seller_service.normalize_nip(invoice.seller_nip)
                    normalized_name = current_app.seller_service.normalize_seller_name(invoice.seller_name)
                    
                    # Check if seller exists
                    existing_seller_row = current_app.seller_repo.find_by_nip(normalized_nip)
                    
                    if existing_seller_row:
                        # Seller exists
                        existing_seller = current_app.seller_repo.row_to_seller(existing_seller_row)
                        existing_name_normalized = current_app.seller_service.normalize_seller_name(existing_seller.seller_name)
                        
                        if existing_name_normalized == normalized_name:
                            # Perfect match - use existing seller
                            seller_id = existing_seller.id
                            validation_warnings.append(f"✓ Powiązano z istniejącym sprzedawcą: {existing_seller.seller_name}")
                        else:
                            # Name mismatch - return conflict
                            seller_conflict = {
                                'existing_seller': {
                                    'id': existing_seller.id,
                                    'seller_nip': existing_seller.seller_nip,
                                    'seller_name': existing_seller.seller_name
                                },
                                'proposed_name': normalized_name,
                                'conflict_type': 'name_mismatch',
                                'message': f"⚠️ NIP {normalized_nip} już istnieje z nazwą '{existing_seller.seller_name}'. Czy chcesz użyć istniejącego sprzedawcy?"
                            }
                            
                            return jsonify({
                                'success': False,
                                'error': 'Konflikt danych sprzedawcy',
                                'seller_conflict': seller_conflict,
                                'message': seller_conflict['message']
                            }), 409
                    else:
                        # New seller - require confirmation
                        seller_info = {
                            'new_seller': True,
                            'seller_nip': normalized_nip,
                            'seller_name': normalized_name
                        }
                        
                        return jsonify({
                            'success': False,
                            'error': 'Nowy sprzedawca wymaga potwierdzenia',
                            'seller_info': seller_info,
                            'message': f"⚠️ Sprzedawca z NIP {normalized_nip} nie istnieje. Czy chcesz utworzyć nowego sprzedawcę?"
                        }), 409
                        
                except Exception as e:
                    validation_warnings.append(f"Błąd walidacji sprzedawcy: {str(e)}")
        
        # Handle PDF file upload if present
        pdf_path = None
        if 'pdf_file' in request.files:
            pdf_file = request.files['pdf_file']
            if pdf_file and pdf_file.filename:
                # Save PDF file
                import os
                from werkzeug.utils import secure_filename
                
                # Create uploads directory if it doesn't exist
                upload_dir = os.path.join(current_app.root_path, 'uploads', 'invoices')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Generate unique filename
                filename = secure_filename(pdf_file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                pdf_path = os.path.join(upload_dir, unique_filename)
                
                # Save file
                pdf_file.save(pdf_path)
                invoice.pdf_path = pdf_path
        
        # Save invoice to database
        invoice_id = current_app.invoice_repo.create(invoice, seller_id=seller_id)
        
        # Log creation
        current_app.audit_repo.log_change(
            invoice_id=invoice_id,
            field_name='status',
            old_value='',
            new_value=invoice.status,
            action='CREATE'
        )
        
        if seller_id:
            # Increment invoice count for seller
            current_app.seller_repo.increment_invoice_count(seller_id)
        
        return jsonify({
            'success': True,
            'message': 'Faktura została dodana pomyślnie',
            'invoice_id': invoice_id,
            'warnings': validation_warnings
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
@login_required
@module_permission_required('invoices')
def get_invoice(invoice_id: int):
    """Get single invoice by ID"""
    try:
        row = current_app.invoice_repo.get_by_id(invoice_id)
        if not row:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        # Convert Row to Invoice object
        invoice = current_app.invoice_repo.row_to_invoice(row)

        return jsonify({
            'success': True,
            'invoice': vars(invoice)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/invoices/<int:invoice_id>', methods=['PUT'])
@login_required
@module_permission_required('invoices')
def update_invoice(invoice_id: int):
    """Update invoice"""
    try:
        data = request.get_json()
        row = current_app.invoice_repo.get_by_id(invoice_id)

        if not row:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        # Convert Row to Invoice object
        invoice = current_app.invoice_repo.row_to_invoice(row)
        
        # Track if seller-related fields changed
        old_seller_nip = invoice.seller_nip
        old_seller_name = invoice.seller_name
        seller_fields_changed = False
        changes_to_log = []

        # Update invoice fields
        for key, value in data.items():
            if hasattr(invoice, key):
                # Capture old value
                old_val = getattr(invoice, key)

                # Convert date strings to date objects
                if key in ('invoice_date', 'payment_due_date') and isinstance(value, str):
                    value = parse_date_string(value)
                # Convert amount to float
                elif key == 'amount':
                    if isinstance(value, str):
                        value = float(value) if value and value.strip() else 0.0
                    elif value is None:
                        value = 0.0
                # Convert ocr_confidence to float if present
                elif key == 'ocr_confidence' and isinstance(value, str):
                    value = float(value) if value else None
                
                # Track seller field changes (NIP or name)
                if key in ('seller_nip', 'seller_name'):
                    seller_fields_changed = True
                
                # Record change if value is different
                if old_val != value:
                    changes_to_log.append({
                        'field': key,
                        'old': str(old_val) if old_val is not None else '',
                        'new': str(value) if value is not None else ''
                    })
                
                setattr(invoice, key, value)

        # Validate
        validation_result = current_app.validation_service.validate_invoice(invoice)
        validation_warnings = validation_result.get('warnings', [])
        
        # Only fail if there are actual errors (not just warnings)
        if validation_result.get('errors'):
            return jsonify({
                'success': False,
                'error': 'Validation failed',
                'validation_errors': validation_result
            }), 400
        
        # Handle seller changes - VALIDATE ONLY, DON'T AUTO-CREATE
        # This validation works for:
        # 1. When NIP is modified (check if new NIP exists)
        # 2. When seller name is modified (check if NIP exists with different name)
        # 3. When both are modified
        new_seller_id = None
        seller_conflict = None
        seller_info = None
        
        if seller_fields_changed and invoice.seller_nip:
            # NIP or name was changed - validate against existing sellers
            try:
                # Normalize first
                normalized_nip = current_app.seller_service.normalize_nip(invoice.seller_nip)
                normalized_name = current_app.seller_service.normalize_seller_name(invoice.seller_name)
                
                # Check if seller exists by NIP (this handles both scenarios)
                existing_seller_row = current_app.seller_repo.find_by_nip(normalized_nip)
                
                if existing_seller_row:
                    # Seller with this NIP exists
                    existing_seller = current_app.seller_repo.row_to_seller(existing_seller_row)
                    existing_name_normalized = current_app.seller_service.normalize_seller_name(existing_seller.seller_name)
                    
                    if existing_name_normalized == normalized_name:
                        # Perfect match - use existing seller
                        # This means: NIP exists AND name matches (or was unchanged)
                        new_seller_id = existing_seller.id
                        validation_warnings.append(f"✓ Powiązano z istniejącym sprzedawcą: {existing_seller.seller_name}")
                       
                        # Update invoice count if seller changed
                        # sqlite3.Row: check if column exists and get value
                        old_seller_id = row['seller_id'] if 'seller_id' in row.keys() else None
                        if old_seller_id and old_seller_id != new_seller_id:
                            current_app.seller_repo.decrement_invoice_count(old_seller_id)
                            current_app.seller_repo.increment_invoice_count(new_seller_id)
                    else:
                        # NIP exists but name doesn't match - CONFLICT!
                        # This catches:
                        # - User modified name but NIP already exists with different name
                        # - User modified NIP to one that exists with different name
                        seller_conflict = {
                            'existing_seller': {
                                'id': existing_seller.id,
                                'seller_nip': existing_seller.seller_nip,
                                'seller_name': existing_seller.seller_name
                            },
                            'proposed_name': normalized_name,
                            'conflict_type': 'name_mismatch', 
                            'message': f"⚠️ NIP {normalized_nip} już istnieje z nazwą '{existing_seller.seller_name}'. Czy chcesz zaktualizować fakturę z istniejącym sprzedawcą?"
                        }
                        
                        # Return error - don't save until user confirms
                        return jsonify({
                            'success': False,
                            'error': 'Konflikt danych sprzedawcy',
                            'seller_conflict': seller_conflict,
                            'message': seller_conflict['message']
                        }), 409  # 409 Conflict status code
                        
                else:
                    # NIP doesn't exist - would need to create new seller
                    # Don't auto-create, require user confirmation
                    seller_info = {
                        'new_seller': True,
                        'seller_nip': normalized_nip,
                        'seller_name': normalized_name
                    }
                    
                    return jsonify({
                        'success': False,
                        'error': 'Nowy sprzedawca wymaga potwierdzenia', 
                        'seller_info': seller_info,
                        'message': f"⚠️ Sprzedawca z NIP {normalized_nip} nie istnieje w bazie. Czy chcesz utworzyć nowego sprzedawcę '{normalized_name}'?"
                    }), 409  # 409 Conflict status code
                
            except Exception as e:
                validation_warnings.append(f"Błąd walidacji sprzedawcy: {str(e)}")
        
        # Save invoice
        if new_seller_id is not None:
            current_app.invoice_repo.update(invoice_id, invoice, seller_id=new_seller_id)
        else:
            current_app.invoice_repo.update(invoice_id, invoice)
        
        # Log changes
        for change in changes_to_log:
            current_app.audit_repo.log_change(
                invoice_id=invoice_id,
                field_name=change['field'],
                old_value=change['old'],
                new_value=change['new'],
                action='UPDATE'
            )

        response_data = {
            'success': True,
            'message': 'Invoice updated successfully',
            'invoice': vars(invoice)
        }
        
        # Add warnings if any
        if validation_warnings:
            response_data['warnings'] = validation_warnings
        
        if seller_conflict:
            response_data['seller_conflict'] = seller_conflict

        return jsonify(response_data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/invoices/<int:invoice_id>/confirm-seller', methods=['PUT'])
@login_required
@module_permission_required('invoices')
def confirm_seller_and_update(invoice_id: int):
    """Confirm seller action (create new or use existing) and update invoice"""
    try:
        data = request.get_json()
        action = data.get('action')  # 'create_new' or 'use_existing'
        invoice_data = data.get('invoice_data')
        
        if not action or not invoice_data:
            return jsonify ({'success': False, 'error': 'Missing action or invoice_data'}), 400
        
        row = current_app.invoice_repo.get_by_id(invoice_id)
        if not row:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404
        
        # Convert Row to Invoice object
        invoice = current_app.invoice_repo.row_to_invoice(row)
        
        # Update invoice fields from submitted data
        for key, value in invoice_data.items():
            if hasattr(invoice, key):
                if key in ('invoice_date', 'payment_due_date') and isinstance(value, str):
                    value = parse_date_string(value)
                elif key == 'amount':
                    value = float(value) if value else 0.0
                setattr(invoice, key, value)
        
        # Normalize seller data
        normalized_nip = current_app.seller_service.normalize_nip(invoice.seller_nip)
        normalized_name = current_app.seller_service.normalize_seller_name(invoice.seller_name)
        
        seller_id = None
        message = ""
        
        if action == 'create_new':
            # Create new seller
            seller_id, created = current_app.seller_repo.get_or_create(
                nip=normalized_nip,
                name=normalized_name,
                address=None
            )
            
            if created:
                message = f"✓ Utworzono nowego sprzedawcę: {normalized_name}"
                # Increment count for new seller
                current_app.seller_repo.increment_invoice_count(seller_id)
            else:
                message = f"✓ Używam istniejącego sprzedawcy: {normalized_name}"
            
        elif action == 'use_existing':
            # Use existing seller (from conflict resolution)
            existing_seller_id = data.get('existing_seller_id')
            if not existing_seller_id:
                return jsonify({'success': False, 'error': 'Missing existing_seller_id'}), 400
            
            seller_id = existing_seller_id
            
            # Get existing seller name
            seller_row = current_app.seller_repo.get_by_id(seller_id)
            if seller_row:
                seller = current_app.seller_repo.row_to_seller(seller_row)
                # Update invoice to use existing seller's data
                invoice.seller_name = seller.seller_name
                invoice.seller_nip = seller.seller_nip
                message = f"✓ Używam istniejącego sprzedawcy: {seller.seller_name}"
        
        elif action == 'update_seller':
            # Update the seller's name in sellers table with new name
            existing_seller_id = data.get('existing_seller_id')
            if not existing_seller_id:
                return jsonify({'success': False, 'error': 'Missing existing_seller_id'}), 400
            
            seller_id = existing_seller_id
            
            # Update seller name in database
            current_app.seller_repo.update_name(seller_id, normalized_name)
            
            # Update invoice to use new name
            invoice.seller_name = normalized_name
            message = f"✓ Zaktualizowano sprzedawcę na: {normalized_name}"
            
        else:
            return jsonify({'success': False, 'error': f'Invalid action: {action}'}), 400
        
        # Update invoice counts if seller changed
        # sqlite3.Row: check if column exists and get value
        old_seller_id = row['seller_id'] if 'seller_id' in row.keys() else None
        if old_seller_id and old_seller_id != seller_id:
            current_app.seller_repo.decrement_invoice_count(old_seller_id)
            current_app.seller_repo.increment_invoice_count(seller_id)
        
        # Save invoice with seller link
        current_app.invoice_repo.update(invoice_id, invoice, seller_id=seller_id)
        
        return jsonify({
            'success': True,
            'message': message,
            'invoice': vars(invoice),
            'seller_id': seller_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/invoices/<int:invoice_id>', methods=['DELETE'])
@login_required
@module_permission_required('invoices')
def delete_invoice(invoice_id: int):
    """Delete invoice"""
    try:
        row = current_app.invoice_repo.get_by_id(invoice_id)
        if not row:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        # Convert Row to Invoice object for audit log
        invoice = current_app.invoice_repo.row_to_invoice(row)

        # Get seller_id before deletion (for decrementing count)
        seller_id = row['seller_id'] if 'seller_id' in row.keys() else None

        current_app.invoice_repo.delete(invoice_id)

        # Decrement seller invoice count if seller was linked
        if seller_id:
            current_app.seller_repo.decrement_invoice_count(seller_id)
        
        # Log deletion (using special field 'status' or just generic 'deleted')
        # FIXME: Logging DELETE action causes IntegrityError because audit_log has 
        # FOREIGN KEY(invoice_id) ON DELETE CASCADE. The log entry is either rejected
        # (if logged after) or deleted (if logged before).
        # To fix this, we need soft delete or removing FK constraint.
        # current_app.audit_repo.log_change(
        #    invoice_id=invoice_id,
        #    field_name='status',
        #    old_value='active',
        #    new_value='deleted',
        #    action='DELETE'
        # )


        return jsonify({
            'success': True,
            'message': 'Invoice deleted successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/invoices/statistics', methods=['GET'])
@login_required
@module_permission_required('invoices')
def get_statistics():
    """Get invoice statistics"""
    try:
        # Use repository's get_statistics method
        stats = current_app.invoice_repo.get_statistics()

        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/dashboard/recent-invoices', methods=['GET'])
def get_recent_invoices():
    """Get recent invoices for dashboard"""
    try:
        limit = request.args.get('limit', 5, type=int)
        rows = current_app.invoice_repo.get_recent(limit)

        invoices = [current_app.invoice_repo.row_to_invoice(row) for row in rows]
        invoices_data = [vars(invoice) for invoice in invoices]

        return jsonify({
            'success': True,
            'invoices': invoices_data,
            'count': len(invoices_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/dashboard/upcoming-payments', methods=['GET'])
def get_upcoming_payments():
    """Get upcoming payment deadlines for dashboard"""
    try:
        limit = request.args.get('limit', 5, type=int)
        rows = current_app.invoice_repo.get_upcoming_payments(limit)

        invoices = [current_app.invoice_repo.row_to_invoice(row) for row in rows]
        invoices_data = [vars(invoice) for invoice in invoices]

        return jsonify({
            'success': True,
            'invoices': invoices_data,
            'count': len(invoices_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/dashboard/overdue-payments', methods=['GET'])
def get_overdue_payments():
    """Get overdue payments for dashboard"""
    try:
        limit = request.args.get('limit', 5, type=int)
        rows = current_app.invoice_repo.get_overdue_payments(limit)

        invoices = [current_app.invoice_repo.row_to_invoice(row) for row in rows]
        invoices_data = [vars(invoice) for invoice in invoices]

        return jsonify({
            'success': True,
            'invoices': invoices_data,
            'count': len(invoices_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/dashboard/top-sellers', methods=['GET'])
def get_top_sellers():
    """Get top sellers by invoice count for dashboard"""
    try:
        limit = request.args.get('limit', 5, type=int)
        rows = current_app.seller_repo.get_top_sellers(limit)

        sellers_data = []
        for row in rows:
            # Use calculated count if available, otherwise fallback to stored count
            inv_count = row['actual_invoice_count'] if 'actual_invoice_count' in row.keys() else 0
            if inv_count == 0 and 'invoice_count' in row.keys():
                inv_count = row['invoice_count']
                
            seller_dict = {
                'id': row['id'],
                'seller_nip': row['seller_nip'],
                'seller_name': row['seller_name'],
                'invoice_count': inv_count,
                'total_amount': row['total_amount'] if 'total_amount' in row.keys() else 0.0
            }
            sellers_data.append(seller_dict)

        return jsonify({
            'success': True,
            'sellers': sellers_data,
            'count': len(sellers_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/dashboard/monthly-totals', methods=['GET'])
def get_monthly_totals():
    """Get monthly invoice totals for last 12 months (for bar chart)"""
    try:
        from datetime import datetime, timedelta
        from collections import defaultdict

        # Get all invoices
        rows = current_app.invoice_repo.get_all()
        invoices = [current_app.invoice_repo.row_to_invoice(row) for row in rows]

        # Calculate date range (last 12 months)
        today = datetime.now()
        twelve_months_ago = today - timedelta(days=365)

        # Group invoices by month
        monthly_totals = defaultdict(float)

        for invoice in invoices:
            if invoice.invoice_date:
                invoice_datetime = datetime.combine(invoice.invoice_date, datetime.min.time())

                # Only include invoices from last 12 months
                if invoice_datetime >= twelve_months_ago:
                    # Create month key (YYYY-MM format)
                    month_key = invoice_datetime.strftime('%Y-%m')
                    monthly_totals[month_key] += (invoice.amount or 0)

        # Generate list of last 12 months in order
        months = []
        labels = []
        month_names_pl = ['Sty', 'Lut', 'Mar', 'Kwi', 'Maj', 'Cze',
                          'Lip', 'Sie', 'Wrz', 'Paź', 'Lis', 'Gru']

        for i in range(11, -1, -1):  # 11 to 0 (last 12 months, oldest to newest)
            month_date = today - timedelta(days=30 * i)
            month_key = month_date.strftime('%Y-%m')
            month_label = f"{month_names_pl[month_date.month - 1]} {month_date.strftime('%y')}"

            months.append(month_key)
            labels.append(month_label)

        # Build data array matching the months order
        data = [monthly_totals.get(month, 0) for month in months]

        return jsonify({
            'success': True,
            'labels': labels,  # ['Sty 25', 'Lut 25', ...]
            'data': data,      # [1234.56, 2345.67, ...]
            'months': months   # ['2025-01', '2025-02', ...] for reference
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/upload', methods=['POST'])
@login_required
@module_permission_required('invoices')
def upload_files():
    """Upload and process PDF files"""
    import sys
    import traceback as tb
    print("=== UPLOAD ENDPOINT CALLED ===", flush=True)
    sys.stdout.flush()

    try:
        if 'files[]' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'}), 400

        files = request.files.getlist('files[]')
        print(f"Files received: {len(files)}", flush=True)
        sys.stdout.flush()
        results = []

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = Path(current_app.config['UPLOAD_FOLDER']) / filename
                file.save(str(file_path))

                # Process PDF
                try:
                    # Extract data using OCR
                    extracted_data = current_app.ocr_service.process_pdf(str(file_path))

                    # Parse dates from strings to date objects
                    invoice_date = parse_date_string(extracted_data.get('issue_date'))
                    if not invoice_date:
                        invoice_date = datetime.now().date()

                    # Handle payment_due_date and payment_term
                    payment_due_date_str = extracted_data.get('payment_due_date')
                    payment_due_date = None
                    payment_term = extracted_data.get('payment_method')

                    if payment_due_date_str:
                        # Check for special payment terms like 'POBRANIE'
                        if payment_due_date_str == 'POBRANIE':
                            payment_term = 'POBRANIE'
                        else:
                            # Try to parse as date
                            payment_due_date = parse_date_string(payment_due_date_str)

                    # Create invoice object (matching Invoice dataclass fields)
                    invoice = Invoice(
                        seller_name=extracted_data.get('seller_name', ''),
                        invoice_number=extracted_data.get('invoice_number', ''),
                        invoice_date=invoice_date,
                        amount=extracted_data.get('total_amount', 0.0),
                        currency=extracted_data.get('currency', 'PLN'),
                        seller_nip=extracted_data.get('seller_nip'),
                        bank_account=extracted_data.get('bank_account'),
                        payment_due_date=payment_due_date,
                        payment_term=payment_term,
                        status='Nieopłacona',
                        pdf_path=str(file_path),
                        ocr_confidence=extracted_data.get('ocr_confidence'),
                        is_duplicate=False
                    )

                    # Validate
                    validation_result = current_app.validation_service.validate_invoice(invoice)
                    validation_errors = validation_result.get('errors', [])
                    validation_warnings = validation_result.get('warnings', [])

                    # Check for duplicates
                    is_duplicate, duplicate_info = current_app.duplicate_detection.check_duplicate(invoice)
                    
                    # Seller lookup/creation
                    seller_id = None
                    seller_conflict = None
                    if invoice.seller_nip:
                        try:
                            seller_id, created, conflict = current_app.seller_service.get_or_create_seller(
                                nip=invoice.seller_nip,
                                name=invoice.seller_name,
                                address=None
                            )
                            
                            if conflict:
                                # Add conflict to warnings
                                seller_conflict = conflict
                                validation_warnings.append(conflict['message'])
                            elif created:
                                # New seller created
                                validation_warnings.append(f"✓ Nowy sprzedawca: {invoice.seller_name}")
                        except Exception as e:
                            validation_warnings.append(f"Seller lookup failed: {str(e)}")

                    results.append({
                        'filename': filename,
                        'success': True,
                        'extracted_data': extracted_data,
                        'validation_errors': validation_errors,
                        'validation_warnings': validation_warnings,
                        'is_duplicate': is_duplicate,
                        'duplicate_info': duplicate_info,
                        'seller_id': seller_id,
                        'seller_conflict': seller_conflict,
                        'processing_profile': extracted_data.get('processing_profile', 'default')
                    })

                    # Save if no validation errors and not duplicate
                    if len(validation_errors) == 0 and not is_duplicate:
                        saved_invoice_id = current_app.invoice_repo.create(invoice, seller_id=seller_id)
                        results[-1]['invoice_id'] = saved_invoice_id
                        results[-1]['saved'] = True
                        
                        # Increment seller invoice count if seller was linked
                        if seller_id:
                            current_app.seller_repo.increment_invoice_count(seller_id)
                    else:
                        results[-1]['saved'] = False

                except Exception as e:
                    # Log the full error with traceback
                    import traceback
                    print(f"ERROR processing {filename}: {str(e)}")
                    print(traceback.format_exc())

                    results.append({
                        'filename': filename,
                        'success': False,
                        'error': str(e)
                    })
            else:
                results.append({
                    'filename': file.filename if file else 'unknown',
                    'success': False,
                    'error': 'Invalid file type'
                })

        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        import sys
        print(f"=== TOP LEVEL ERROR ===", flush=True)
        print(f"Error: {str(e)}", flush=True)
        print(tb.format_exc(), flush=True)
        sys.stdout.flush()
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/export/<format>', methods=['GET'])
@login_required
@module_permission_required('invoices')
def export_invoices(format: str):
    """Export invoices to Excel or CSV"""
    try:
        if format not in ['excel', 'csv']:
            return jsonify({'success': False, 'error': 'Invalid format'}), 400

        rows = current_app.invoice_repo.get_all()
        
        # Convert Row objects to Invoice objects
        invoices = [current_app.invoice_repo.row_to_invoice(row) for row in rows]

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{format}') as tmp:
            if format == 'excel':
                file_path = current_app.export_service.export_to_excel(invoices, tmp.name)
                mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                filename = f'invoices_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            else:  # csv
                file_path = current_app.export_service.export_to_csv(invoices, tmp.name)
                mimetype = 'text/csv'
                filename = f'invoices_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

        return send_file(
            file_path,
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/email/import', methods=['POST'])
@login_required
@module_permission_required('invoices')
def import_from_email():
    """Import PDFs from email - Stage files with metadata (NEW WORKFLOW)"""
    import json
    import uuid
    
    # Get request data BEFORE generator (within request context)
    data = request.get_json()
    
    # Capture app objects BEFORE generator (within app context)
    email_service = current_app.email_service
    staging_repo = current_app.staging_repo
    upload_folder = current_app.config['UPLOAD_FOLDER']
    
    # Get or create session ID BEFORE generator (within request context)
    if 'upload_session_id' not in session:
        session['upload_session_id'] = str(uuid.uuid4())
        session.modified = True  # Explicitly mark session as modified
    session_id = session['upload_session_id']
    
    # CRITICAL: Force session save before SSE starts
    # SSE responses don't trigger automatic session saving
    from flask import current_app as app
    session_interface = app.session_interface
    response = app.make_response('')
    session_interface.save_session(app, session, response)
    
    def generate():
        try:
            
            # Get email settings
            from config.email_settings import load_email_settings
            email_config = load_email_settings()

            # Connect to email service
            server_msg = f"Łączenie z {email_config.get('imap_server')}..."
            yield f"data: {json.dumps({'type': 'progress', 'message': server_msg})}\n\n"
            
            connected = email_service.connect(
                email_address=email_config.get('email'),
                password=email_config.get('password'),
                imap_server=email_config.get('imap_server'),
                imap_port=email_config.get('imap_port', 993)
            )

            if not connected:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to connect to email server'})}\n\n"
                return

            success_msg = f"✅ Połączono z {email_config.get('imap_server')} jako {email_config.get('email')}"
            yield f"data: {json.dumps({'type': 'success', 'message': success_msg})}\n\n"

            # Parse date parameters
            from_date = parse_date_string(data.get('date_from')) if data.get('date_from') else None
            to_date = parse_date_string(data.get('date_to')) if data.get('date_to') else None
            
            # Get folders parameter (optional)
            folders = data.get('folders')  # Expected to be a list of folder names or None

            # Create temp directory for this session
            from pathlib import Path
            temp_dir = Path(upload_folder) / 'temp' / session_id
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Fetch PDFs - NOW returns list of dicts with metadata
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Przeszukiwanie folderów...'})}\n\n"
            
            # Progress messages buffer
            progress_messages = []
            
            # Define progress callback to capture messages
            def progress_callback(main_msg, sub_msg, progress):
                msg = main_msg
                if sub_msg:
                    msg = f"{main_msg} - {sub_msg}"
                
                # Determine message type based on content
                msg_type = 'info'
                if '✅' in msg or 'Pobrano' in msg or 'zapisano' in msg:
                    msg_type = 'success'
                elif '❌' in msg or 'Błąd' in msg:
                    msg_type = 'error'
                elif '⚠' in msg:
                    msg_type = 'warning'
                
                # Store message to be yielded
                progress_messages.append(f"data: {json.dumps({'type': msg_type, 'message': msg})}\n\n")
            
            # Fetch PDFs with progress callback - returns dicts with metadata
            pdf_files = email_service.fetch_pdf_attachments(
                from_date=from_date,
                to_date=to_date,
                save_dir=str(temp_dir),  # Save to temp directory
                folders=folders,
                progress_callback=progress_callback
            )
            
            # Yield all captured progress messages
            for progress_msg in progress_messages:
                yield progress_msg

            # Disconnect from email
            email_service.disconnect()
            
            files_msg = f"📧 Znaleziono {len(pdf_files)} plików PDF"
            yield f"data: {json.dumps({'type': 'success', 'message': files_msg})}\n\n"

            # Stage each PDF file with email metadata
            staged_count = 0
            total = len(pdf_files)
            
            for idx, file_data in enumerate(pdf_files, 1):
                try:
                    # file_data is a dict with: filename, filepath, folder, email_subject, email_sender, email_date
                    filename = file_data['filename']
                    filepath = file_data['filepath']
                    
                    stage_msg = f"Zapisywanie {idx}/{total}: {filename}"
                    yield f"data: {json.dumps({'type': 'progress', 'message': stage_msg, 'current': idx, 'total': total})}\n\n"
                    
                    # Get file size
                    from pathlib import Path
                    file_size = Path(filepath).stat().st_size
                    
                    # Create staging entry with email metadata
                    from database.models import UploadStaging
                    staging = UploadStaging(
                        session_id=session_id,
                        filename=filename,
                        file_path=filepath,
                        file_size=file_size,
                        email_subject=file_data.get('email_subject'),
                        email_sender=file_data.get('email_sender'),
                        email_folder=file_data.get('folder'),  # Note: 'folder' not 'email_folder' in dict
                        email_date=file_data.get('email_date')
                    )
                    
                    staging_repo.create(staging)
                    staged_count += 1
                    
                    success_msg = f"✓ {filename} - zapisano do przeglądu"
                    yield f"data: {json.dumps({'type': 'success', 'message': success_msg})}\n\n"
                    
                except Exception as e:
                    error_msg = f"✗ {file_data.get('filename', 'unknown')} - błąd: {str(e)}"
                    yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"

            # Send final results
            yield f"data: {json.dumps({'type': 'complete', 'total_processed': staged_count})}\n\n"
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f"Błąd: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
    
    from flask import Response
    return Response(generate(), mimetype='text/event-stream')


@api_bp.route('/email/test', methods=['POST'])
def test_email_connection():
    """Test email connection"""
    try:
        data = request.get_json()

        # Build settings dict matching EmailService.test_connection signature
        settings = {
            'imap_server': data.get('imap_server'),
            'imap_port': int(data.get('imap_port', 993)),
            'email_address': data.get('email'),
            'password': data.get('password')
        }

        success = current_app.email_service.test_connection(settings)

        if success:
            return jsonify({
                'success': True,
                'message': 'Połączenie udane'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Połączenie nieudane - sprawdź dane logowania'
            }), 400
    except Exception as e:
        logger.error(f"Email test connection error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/email/folders', methods=['POST'])
def get_email_folders():
    """Get list of email folders"""
    try:
        # Get email settings
        from config.email_settings import load_email_settings
        email_config = load_email_settings()

        # Connect to email service
        connected = current_app.email_service.connect(
            email_address=email_config.get('email'),
            password=email_config.get('password'),
            imap_server=email_config.get('imap_server'),
            imap_port=email_config.get('imap_port', 993)
        )

        if not connected:
            return jsonify({
                'success': False,
                'error': 'Failed to connect to email server'
            }), 500

        # Get folders
        folders = current_app.email_service._list_folders()

        # Disconnect
        current_app.email_service.disconnect()

        return jsonify({
            'success': True,
            'folders': folders
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/email/settings', methods=['GET', 'POST'])
def email_settings():
    """Get or save email settings"""
    from config.email_settings import load_email_settings, save_email_settings

    if request.method == 'GET':
        try:
            settings = load_email_settings()
            return jsonify({
                'success': True,
                'settings': settings
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    else:  # POST
        try:
            data = request.get_json()
            save_email_settings(data)
            return jsonify({
                'success': True,
                'message': 'Settings saved successfully'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/history', methods=['GET'])
@login_required
def get_history():
    """Get audit history — all entity types"""
    try:
        invoice_id = request.args.get('invoice_id', type=int)
        entity_type = request.args.get('entity_type')  # filter by type

        entries = current_app.audit_repo.get_all(
            invoice_id=invoice_id,
            entity_type=entity_type,
        )

        return jsonify({
            'success': True,
            'entries': entries,
            'count': len(entries)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/history/details', methods=['POST'])
def get_history_details():
    """Get detailed changes for specific audit entries"""
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        
        # If passed as string "1,2,3"
        if isinstance(ids, str):
            ids = ids.split(',')
            
        if not ids:
             return jsonify({'success': False, 'error': 'No IDs provided'}), 400
             
        # Convert to ints
        ids_int = []
        for x in ids:
            try:
                ids_int.append(int(x))
            except (ValueError, TypeError):
                pass
        
        if not ids_int:
             return jsonify({'success': False, 'error': 'No valid IDs provided'}), 400

        details = current_app.audit_repo.get_details_by_ids(ids_int)
        
        return jsonify({
            'success': True,
            'details': details
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/pdf/<int:invoice_id>', methods=['GET'])
def view_pdf(invoice_id: int):
    """View PDF or image file for invoice"""
    try:
        row = current_app.invoice_repo.get_by_id(invoice_id)
        if not row:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        # Convert Row to Invoice object
        invoice = current_app.invoice_repo.row_to_invoice(row)

        if not invoice.pdf_path:
            return jsonify({'success': False, 'error': 'Document not found'}), 404

        pdf_path = Path(invoice.pdf_path)
        if not pdf_path.exists():
            return jsonify({'success': False, 'error': 'Document file not found on disk'}), 404

        # Detect file type and set appropriate MIME type
        file_ext = pdf_path.suffix.lower()
        mime_types = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
            '.webp': 'image/webp',
        }
        mimetype = mime_types.get(file_ext, 'application/octet-stream')

        return send_file(
            str(pdf_path),
            mimetype=mimetype
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# SELLER MANAGEMENT ENDPOINTS
# ============================================================================

@api_bp.route('/sellers', methods=['GET'])
@login_required
@module_permission_required('invoices')
def get_sellers():
    """Get all sellers with statistics"""
    try:
        search_query = request.args.get('search', '').strip()

        if search_query:
            # Search by name or NIP
            rows = current_app.seller_repo.find_by_name(search_query)
        else:
            # Get all sellers with stats
            rows = current_app.seller_repo.get_all_with_stats()

        # Convert to seller objects and include stats
        sellers_data = []
        for row in rows:
            seller_dict = {
                'id': row['id'],
                'seller_nip': row['seller_nip'],
                'seller_name': row['seller_name'],
                'address': row['address'] if 'address' in row.keys() else None,
                'first_seen': row['first_seen'].isoformat() if row.get('first_seen') else None,
                'last_updated': row['last_updated'].isoformat() if row.get('last_updated') else None,
                'invoice_count': row['invoice_count'] if 'invoice_count' in row.keys() else 0,
                # Stats from JOIN (if available)
                'actual_invoice_count': row['actual_invoice_count'] if 'actual_invoice_count' in row.keys() else 0,
                'total_paid': row['total_paid'] if 'total_paid' in row.keys() else 0.0,
                'total_unpaid': row['total_unpaid'] if 'total_unpaid' in row.keys() else 0.0
            }
            sellers_data.append(seller_dict)

        # Get global stats (total from invoices table, including orphaned invoices)
        cursor = current_app.invoice_repo._execute("SELECT COUNT(*) as cnt FROM invoices")
        total_invoices = cursor.fetchone()['cnt']

        cursor = current_app.invoice_repo._execute("""
            SELECT
                SUM(CASE WHEN status = 'Opłacona' THEN amount ELSE 0 END) as total_paid,
                SUM(CASE WHEN status = 'Nieopłacona' THEN amount ELSE 0 END) as total_unpaid
            FROM invoices
        """)
        global_stats = cursor.fetchone()

        return jsonify({
            'success': True,
            'sellers': sellers_data,
            'count': len(sellers_data),
            'global_stats': {
                'total_invoices': total_invoices,
                'total_paid': float(global_stats['total_paid'] or 0.0),
                'total_unpaid': float(global_stats['total_unpaid'] or 0.0)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/<int:seller_id>', methods=['GET'])
def get_seller(seller_id: int):
    """Get single seller with details and related invoices"""
    try:
        row = current_app.seller_repo.get_by_id(seller_id)
        if not row:
            return jsonify({'success': False, 'error': 'Seller not found'}), 404

        seller = current_app.seller_repo.row_to_seller(row)

        # Get related invoices
        invoice_rows = current_app.invoice_repo.get_by_seller(seller_id)
        invoices = [current_app.invoice_repo.row_to_invoice(inv_row) for inv_row in invoice_rows]
        invoices_data = [vars(inv) for inv in invoices]

        # Get actual invoice count (live count from database)
        actual_count = len(invoices_data)

        # Convert seller to dict and update invoice_count with actual count
        seller_dict = vars(seller)
        seller_dict['invoice_count'] = actual_count  # Override with actual count

        return jsonify({
            'success': True,
            'seller': seller_dict,
            'invoices': invoices_data,
            'invoice_count': actual_count  # Also return as separate field for backward compatibility
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/<int:seller_id>', methods=['PUT'])
def update_seller(seller_id: int):
    """Update seller information"""
    try:
        data = request.get_json()
        row = current_app.seller_repo.get_by_id(seller_id)
        
        if not row:
            return jsonify({'success': False, 'error': 'Seller not found'}), 404
        
        seller = current_app.seller_repo.row_to_seller(row)
        
        # Track what changed
        changes = []
        
        # Update seller_name if provided
        if 'seller_name' in data and data['seller_name'] != seller.seller_name:
            new_name = current_app.seller_service.normalize_seller_name(data['seller_name'])
            seller.seller_name = new_name
            current_app.seller_repo.update_name(seller_id, new_name)
            changes.append(f"Name updated to: {new_name}")
        
        # Update address if provided
        if 'address' in data:
            seller.address = data['address']
            current_app.seller_repo.update_address(seller_id, data['address'])
            changes.append("Address updated")
        
        _audit('seller', 'UPDATE', entity_id=seller_id,
               entity_label=seller.seller_name,
               new_value='; '.join(changes) if changes else 'no changes')

        return jsonify({
            'success': True,
            'message': 'Seller updated successfully',
            'seller': vars(seller),
            'changes': changes
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/<int:seller_id>/bulk-update', methods=['POST'])
def bulk_update_seller_invoices(seller_id: int):
    """Propagate seller changes to all related invoices"""
    try:
        row = current_app.seller_repo.get_by_id(seller_id)
        if not row:
            return jsonify({'success': False, 'error': 'Seller not found'}), 404
        
        seller = current_app.seller_repo.row_to_seller(row)
        
        # Get all invoices for this seller
        invoice_rows = current_app.invoice_repo.get_by_seller(seller_id)
        
        updated_count = 0
        errors = []
        
        for inv_row in invoice_rows:
            try:
                invoice = current_app.invoice_repo.row_to_invoice(inv_row)
                
                # Update seller name and NIP
                invoice.seller_name = seller.seller_name
                invoice.seller_nip = seller.seller_nip
                
                # Save invoice
                if current_app.invoice_repo.update(invoice.id, invoice):
                    updated_count += 1
                    
            except Exception as e:
                errors.append(f"Invoice {invoice.id}: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} invoices',
            'updated_count': updated_count,
            'total_invoices': len(invoice_rows),
            'errors': errors if errors else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/conflicts', methods=['GET'])
def get_seller_conflicts():
    """Get list of potential seller conflicts (same NIP, different names)"""
    try:
        # This would require querying historical data or audit logs
        # For now, return a simple implementation that checks current state

        all_sellers = current_app.seller_repo.get_all()

        # Group by NIP to find duplicates (shouldn't happen due to UNIQUE constraint)
        # Instead, we can check invoices that have seller_nip but different seller_name
        # than the linked seller

        conflicts = []

        for seller_row in all_sellers:
            seller = current_app.seller_repo.row_to_seller(seller_row)

            # Get invoices for this seller
            invoice_rows = current_app.invoice_repo.get_by_seller(seller.id)

            for inv_row in invoice_rows:
                invoice = current_app.invoice_repo.row_to_invoice(inv_row)

                # Check if invoice's seller_name differs from seller's name
                normalized_inv_name = current_app.seller_service.normalize_seller_name(invoice.seller_name)
                normalized_seller_name = current_app.seller_service.normalize_seller_name(seller.seller_name)

                if normalized_inv_name != normalized_seller_name:
                    conflicts.append({
                        'seller_id': seller.id,
                        'seller_nip': seller.seller_nip,
                        'seller_name': seller.seller_name,
                        'invoice_id': invoice.id,
                        'invoice_number': invoice.invoice_number,
                        'invoice_seller_name': invoice.seller_name,
                        'conflict_type': 'name_mismatch'
                    })

        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'count': len(conflicts)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers', methods=['POST'])
@login_required
@module_permission_required('invoices')
def create_seller():
    """Create a new seller with duplicate validation"""
    try:
        data = request.get_json()

        nip = data.get('seller_nip', '').strip()
        name = data.get('seller_name', '').strip()
        address = data.get('address', '').strip() if data.get('address') else None

        if not nip:
            return jsonify({'success': False, 'error': 'NIP jest wymagany'}), 400
        if not name:
            return jsonify({'success': False, 'error': 'Nazwa sprzedawcy jest wymagana'}), 400

        # Normalize data
        normalized_nip = current_app.seller_service.normalize_nip(nip)
        normalized_name = current_app.seller_service.normalize_seller_name(name)

        # Check for existing seller by NIP
        existing_by_nip = current_app.seller_repo.find_by_nip(normalized_nip)

        if existing_by_nip:
            existing_seller = current_app.seller_repo.row_to_seller(existing_by_nip)
            existing_name_normalized = current_app.seller_service.normalize_seller_name(existing_seller.seller_name)

            if existing_name_normalized == normalized_name:
                # Exact match - return existing seller
                return jsonify({
                    'success': True,
                    'message': 'Sprzedawca juz istnieje',
                    'seller': vars(existing_seller),
                    'already_exists': True
                })
            else:
                # NIP exists with different name - conflict
                return jsonify({
                    'success': False,
                    'error': 'Konflikt NIP',
                    'conflict_type': 'nip_exists_different_name',
                    'existing_seller': {
                        'id': existing_seller.id,
                        'seller_nip': existing_seller.seller_nip,
                        'seller_name': existing_seller.seller_name
                    },
                    'proposed_name': normalized_name,
                    'message': f"NIP {normalized_nip} juz istnieje z nazwa '{existing_seller.seller_name}'."
                }), 409

        # Check for existing seller by name (different NIP)
        existing_by_name = current_app.seller_repo.find_by_name(normalized_name)
        name_conflict = None
        for row in existing_by_name:
            seller = current_app.seller_repo.row_to_seller(row)
            if current_app.seller_service.normalize_seller_name(seller.seller_name) == normalized_name:
                name_conflict = seller
                break

        if name_conflict:
            # Name exists with different NIP - warning (not blocking)
            return jsonify({
                'success': False,
                'error': 'Konflikt nazwy',
                'conflict_type': 'name_exists_different_nip',
                'existing_seller': {
                    'id': name_conflict.id,
                    'seller_nip': name_conflict.seller_nip,
                    'seller_name': name_conflict.seller_name
                },
                'proposed_nip': normalized_nip,
                'message': f"Sprzedawca o nazwie '{name_conflict.seller_name}' juz istnieje z innym NIP ({name_conflict.seller_nip})."
            }), 409

        # No conflicts - create seller
        from database.models import Seller
        new_seller = Seller(
            seller_nip=normalized_nip,
            seller_name=normalized_name,
            address=address,
            invoice_count=0
        )

        seller_id = current_app.seller_repo.create(new_seller)
        new_seller.id = seller_id

        _audit('seller', 'CREATE', entity_id=seller_id,
               entity_label=f"{normalized_name} ({normalized_nip})")

        return jsonify({
            'success': True,
            'message': 'Sprzedawca zostal utworzony',
            'seller': vars(new_seller)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/<int:seller_id>', methods=['DELETE'])
def delete_seller(seller_id: int):
    """Delete seller with cascade delete of linked invoices"""
    try:
        row = current_app.seller_repo.get_by_id(seller_id)
        if not row:
            return jsonify({'success': False, 'error': 'Sprzedawca nie znaleziony'}), 404

        seller = current_app.seller_repo.row_to_seller(row)

        # Get all linked invoices
        invoice_rows = current_app.invoice_repo.get_by_seller(seller_id)
        invoice_count = len(invoice_rows)

        # Collect invoice numbers for response
        deleted_invoices = []

        # Delete all linked invoices first
        for inv_row in invoice_rows:
            invoice = current_app.invoice_repo.row_to_invoice(inv_row)
            deleted_invoices.append({
                'id': invoice.id,
                'invoice_number': invoice.invoice_number
            })
            current_app.invoice_repo.delete(invoice.id)

        # Delete the seller
        current_app.seller_repo.delete(seller_id)

        _audit('seller', 'DELETE', entity_id=seller_id,
               entity_label=f"{seller.seller_name} ({seller.seller_nip})",
               old_value=f"{invoice_count} faktur")

        return jsonify({
            'success': True,
            'message': f'Sprzedawca i {invoice_count} faktur zostalo usunietych',
            'deleted_seller': {
                'id': seller.id,
                'seller_nip': seller.seller_nip,
                'seller_name': seller.seller_name
            },
            'deleted_invoices': deleted_invoices,
            'invoice_count': invoice_count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/<int:seller_id>/invoices', methods=['GET'])
def get_seller_invoices(seller_id: int):
    """Get all invoices linked to a seller (for delete confirmation)"""
    try:
        row = current_app.seller_repo.get_by_id(seller_id)
        if not row:
            return jsonify({'success': False, 'error': 'Sprzedawca nie znaleziony'}), 404

        seller = current_app.seller_repo.row_to_seller(row)

        # Get all linked invoices
        invoice_rows = current_app.invoice_repo.get_by_seller(seller_id)

        invoices = []
        for inv_row in invoice_rows:
            invoice = current_app.invoice_repo.row_to_invoice(inv_row)
            invoices.append({
                'id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'amount': invoice.amount,
                'currency': invoice.currency,
                'invoice_date': str(invoice.invoice_date) if invoice.invoice_date else None,
                'status': invoice.status
            })

        return jsonify({
            'success': True,
            'seller': vars(seller),
            'invoices': invoices,
            'count': len(invoices)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/sync', methods=['POST'])
def sync_sellers():
    """Synchronize seller data with invoices - detect discrepancies"""
    try:
        # Get all invoices
        all_invoice_rows = current_app.invoice_repo.get_all()

        # Get all sellers indexed by NIP
        all_seller_rows = current_app.seller_repo.get_all()
        sellers_by_nip = {}
        for row in all_seller_rows:
            seller = current_app.seller_repo.row_to_seller(row)
            sellers_by_nip[seller.seller_nip] = seller

        # Track results
        missing_sellers = {}  # NIP -> {name, count, invoices}
        name_discrepancies = []  # List of {seller, invoice, diff}

        for inv_row in all_invoice_rows:
            invoice = current_app.invoice_repo.row_to_invoice(inv_row)

            if not invoice.seller_nip:
                continue

            normalized_nip = current_app.seller_service.normalize_nip(invoice.seller_nip)

            if normalized_nip not in sellers_by_nip:
                # Seller not in database
                if normalized_nip not in missing_sellers:
                    missing_sellers[normalized_nip] = {
                        'nip': normalized_nip,
                        'name': invoice.seller_name,
                        'count': 0,
                        'invoices': []
                    }
                missing_sellers[normalized_nip]['count'] += 1
                missing_sellers[normalized_nip]['invoices'].append({
                    'id': invoice.id,
                    'invoice_number': invoice.invoice_number
                })
            else:
                # Check for name discrepancy
                seller = sellers_by_nip[normalized_nip]
                normalized_inv_name = current_app.seller_service.normalize_seller_name(invoice.seller_name)
                normalized_seller_name = current_app.seller_service.normalize_seller_name(seller.seller_name)

                if normalized_inv_name != normalized_seller_name:
                    name_discrepancies.append({
                        'seller_id': seller.id,
                        'seller_nip': seller.seller_nip,
                        'seller_name': seller.seller_name,
                        'invoice_id': invoice.id,
                        'invoice_number': invoice.invoice_number,
                        'invoice_seller_name': invoice.seller_name
                    })

        # Summary stats
        total_sellers = len(sellers_by_nip)
        total_invoices = len(all_invoice_rows)
        invoices_without_nip = sum(1 for inv_row in all_invoice_rows
                                   if not current_app.invoice_repo.row_to_invoice(inv_row).seller_nip)

        return jsonify({
            'success': True,
            'missing_sellers': list(missing_sellers.values()),
            'name_discrepancies': name_discrepancies,
            'summary': {
                'total_sellers': total_sellers,
                'total_invoices': total_invoices,
                'invoices_without_nip': invoices_without_nip,
                'missing_sellers_count': len(missing_sellers),
                'discrepancies_count': len(name_discrepancies)
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/sync/add-missing', methods=['POST'])
def add_missing_seller():
    """Add a missing seller from sync results"""
    try:
        data = request.get_json()

        nip = data.get('nip', '').strip()
        name = data.get('name', '').strip()

        if not nip or not name:
            return jsonify({'success': False, 'error': 'NIP i nazwa sa wymagane'}), 400

        # Normalize
        normalized_nip = current_app.seller_service.normalize_nip(nip)
        normalized_name = current_app.seller_service.normalize_seller_name(name)

        # Create seller
        seller_id, created = current_app.seller_repo.get_or_create(
            nip=normalized_nip,
            name=normalized_name,
            address=None
        )

        # Link existing invoices with this NIP to the seller
        linked_count = 0
        all_invoices = current_app.invoice_repo.get_all()
        for inv_row in all_invoices:
            invoice = current_app.invoice_repo.row_to_invoice(inv_row)
            if invoice.seller_nip:
                inv_nip = current_app.seller_service.normalize_nip(invoice.seller_nip)
                if inv_nip == normalized_nip:
                    # Link this invoice to seller
                    current_app.invoice_repo.update(invoice.id, invoice, seller_id=seller_id)
                    linked_count += 1

        # Update invoice count
        for _ in range(linked_count):
            current_app.seller_repo.increment_invoice_count(seller_id)

        return jsonify({
            'success': True,
            'message': f'Utworzono sprzedawce i powiazano {linked_count} faktur',
            'seller_id': seller_id,
            'linked_invoices': linked_count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/sync/fix-discrepancy', methods=['POST'])
def fix_discrepancy():
    """Fix a name discrepancy - update invoice or seller"""
    try:
        data = request.get_json()

        action = data.get('action')  # 'use_seller_name' or 'use_invoice_name'
        invoice_id = data.get('invoice_id')
        seller_id = data.get('seller_id')

        if not action or not invoice_id or not seller_id:
            return jsonify({'success': False, 'error': 'Brak wymaganych parametrow'}), 400

        # Get seller and invoice
        seller_row = current_app.seller_repo.get_by_id(seller_id)
        if not seller_row:
            return jsonify({'success': False, 'error': 'Sprzedawca nie znaleziony'}), 404

        invoice_row = current_app.invoice_repo.get_by_id(invoice_id)
        if not invoice_row:
            return jsonify({'success': False, 'error': 'Faktura nie znaleziona'}), 404

        seller = current_app.seller_repo.row_to_seller(seller_row)
        invoice = current_app.invoice_repo.row_to_invoice(invoice_row)

        if action == 'use_seller_name':
            # Update invoice to use seller's name
            old_name = invoice.seller_name
            invoice.seller_name = seller.seller_name
            current_app.invoice_repo.update(invoice.id, invoice)

            return jsonify({
                'success': True,
                'message': f'Zaktualizowano fakture - zmieniono nazwe z "{old_name}" na "{seller.seller_name}"'
            })

        elif action == 'use_invoice_name':
            # Update seller to use invoice's name
            old_name = seller.seller_name
            new_name = current_app.seller_service.normalize_seller_name(invoice.seller_name)
            current_app.seller_repo.update_name(seller_id, new_name)

            return jsonify({
                'success': True,
                'message': f'Zaktualizowano sprzedawce - zmieniono nazwe z "{old_name}" na "{new_name}"'
            })
        else:
            return jsonify({'success': False, 'error': f'Nieznana akcja: {action}'}), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/sync/invoice-counts', methods=['POST'])
def sync_seller_invoice_counts():
    """
    Synchronize seller invoice counts with actual data.
    Recalculates invoice_count for all sellers based on current invoices table.
    """
    try:
        # Sync all seller invoice counts
        updated_count = current_app.seller_repo.sync_invoice_counts()

        return jsonify({
            'success': True,
            'message': f'Zsynchronizowano liczniki faktur dla {updated_count} sprzedawców',
            'updated_count': updated_count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/sellers/check-duplicate', methods=['POST'])
def check_seller_duplicate():
    """Check if seller with NIP or name already exists"""
    try:
        data = request.get_json()

        nip = data.get('nip', '').strip()
        name = data.get('name', '').strip()

        result = {
            'success': True,
            'nip_exists': False,
            'name_exists': False,
            'existing_by_nip': None,
            'existing_by_name': None
        }

        if nip:
            normalized_nip = current_app.seller_service.normalize_nip(nip)
            existing = current_app.seller_repo.find_by_nip(normalized_nip)
            if existing:
                seller = current_app.seller_repo.row_to_seller(existing)
                result['nip_exists'] = True
                result['existing_by_nip'] = {
                    'id': seller.id,
                    'seller_nip': seller.seller_nip,
                    'seller_name': seller.seller_name
                }

        if name:
            normalized_name = current_app.seller_service.normalize_seller_name(name)
            existing_list = current_app.seller_repo.find_by_name(normalized_name)
            for row in existing_list:
                seller = current_app.seller_repo.row_to_seller(row)
                if current_app.seller_service.normalize_seller_name(seller.seller_name) == normalized_name:
                    result['name_exists'] = True
                    result['existing_by_name'] = {
                        'id': seller.id,
                        'seller_nip': seller.seller_nip,
                        'seller_name': seller.seller_name
                    }
                    break

        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# CLIENT MANAGEMENT ENDPOINTS
# ============================================================================

@api_bp.route('/clients', methods=['GET'])
@login_required
@module_permission_required('clients')
def get_clients():
    """Get all clients with optional search"""
    try:
        search_query = request.args.get('search', '').strip()

        if search_query:
            rows = current_app.client_repo.search(search_query)
        else:
            rows = current_app.client_repo.get_active_clients()

        # Convert to Client objects then to dicts
        clients = [current_app.client_repo.row_to_client(row) for row in rows]
        clients_data = []

        for client in clients:
            client_dict = vars(client).copy()
            # Convert dates to ISO format for JSON
            if client.date_of_birth:
                client_dict['date_of_birth'] = client.date_of_birth.isoformat()
            if client.first_visit_date:
                client_dict['first_visit_date'] = client.first_visit_date.isoformat()
            if client.last_visit_date:
                client_dict['last_visit_date'] = client.last_visit_date.isoformat()
            if client.created_at:
                client_dict['created_at'] = client.created_at.isoformat()
            if client.updated_at:
                client_dict['updated_at'] = client.updated_at.isoformat()
            # Add computed properties
            client_dict['full_name'] = client.full_name
            client_dict['age'] = client.age
            clients_data.append(client_dict)

        return jsonify({
            'success': True,
            'clients': clients_data,
            'count': len(clients_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/clients/<int:client_id>', methods=['GET'])
@login_required
@module_permission_required('clients')
def get_client(client_id):
    """Get single client by ID"""
    try:
        row = current_app.client_repo.get_by_id(client_id)
        if not row:
            return jsonify({'success': False, 'error': 'Client not found'}), 404

        client = current_app.client_repo.row_to_client(row)
        client_dict = vars(client).copy()

        # Convert dates to ISO format
        if client.date_of_birth:
            client_dict['date_of_birth'] = client.date_of_birth.isoformat()
        if client.first_visit_date:
            client_dict['first_visit_date'] = client.first_visit_date.isoformat()
        if client.last_visit_date:
            client_dict['last_visit_date'] = client.last_visit_date.isoformat()
        if client.created_at:
            client_dict['created_at'] = client.created_at.isoformat()
        if client.updated_at:
            client_dict['updated_at'] = client.updated_at.isoformat()

        # Add computed properties
        client_dict['full_name'] = client.full_name
        client_dict['age'] = client.age

        return jsonify({
            'success': True,
            'client': client_dict
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/clients', methods=['POST'])
@login_required
@module_permission_required('clients')
def create_client_endpoint():
    """Create new client"""
    try:
        data = request.get_json()

        # Check for duplicate email if provided
        if data.get('email'):
            existing = current_app.client_repo.find_by_email(data['email'])
            if existing:
                return jsonify({
                    'success': False,
                    'error': 'Klient z tym adresem email już istnieje',
                    'field': 'email'
                }), 400

        # Create Client object
        from database.models import Client
        client = Client(
            first_name=data.get('first_name', '').strip(),
            last_name=data.get('last_name', '').strip(),
            phone=data.get('phone', '').strip() if data.get('phone') else None,
            email=data.get('email', '').strip() if data.get('email') else None,
            date_of_birth=parse_date_string(data.get('date_of_birth')) if data.get('date_of_birth') else None,
            notes=data.get('notes', '').strip() if data.get('notes') else None,
            preferences=data.get('preferences') if data.get('preferences') else None,
            first_visit_date=parse_date_string(data.get('first_visit_date')) if data.get('first_visit_date') else None,
            last_visit_date=parse_date_string(data.get('last_visit_date')) if data.get('last_visit_date') else None,
            is_active=data.get('is_active', True)
        )

        # Validate required fields
        if not client.first_name or not client.last_name:
            return jsonify({
                'success': False,
                'error': 'Imię i nazwisko są wymagane'
            }), 400

        # Save to database
        client_id = current_app.client_repo.create(client)

        _audit('client', 'CREATE', entity_id=client_id,
               entity_label=f"{client.first_name} {client.last_name}")

        return jsonify({
            'success': True,
            'message': 'Klient został utworzony',
            'client_id': client_id
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/clients/<int:client_id>', methods=['PUT'])
@login_required
@module_permission_required('clients')
def update_client(client_id):
    """Update client"""
    try:
        data = request.get_json()
        row = current_app.client_repo.get_by_id(client_id)

        if not row:
            return jsonify({'success': False, 'error': 'Client not found'}), 404

        # Convert row to Client object
        client = current_app.client_repo.row_to_client(row)

        # Check email uniqueness if changed
        if data.get('email') and data['email'] != client.email:
            existing = current_app.client_repo.find_by_email(data['email'])
            if existing and existing['id'] != client_id:
                return jsonify({
                    'success': False,
                    'error': 'Klient z tym adresem email już istnieje',
                    'field': 'email'
                }), 400

        # Snapshot old values before mutation
        _client_old = {
            'first_name': client.first_name,
            'last_name': client.last_name,
            'phone': client.phone,
            'email': client.email,
            'date_of_birth': client.date_of_birth,
            'notes': client.notes,
            'preferences': client.preferences,
            'is_active': client.is_active,
        }

        # Update fields
        client.first_name = data.get('first_name', client.first_name).strip()
        client.last_name = data.get('last_name', client.last_name).strip()
        client.phone = data.get('phone', '').strip() if data.get('phone') else None
        client.email = data.get('email', '').strip() if data.get('email') else None
        client.date_of_birth = parse_date_string(data.get('date_of_birth')) if 'date_of_birth' in data else client.date_of_birth
        client.notes = data.get('notes', client.notes)
        client.preferences = data.get('preferences', client.preferences)
        client.is_active = data.get('is_active', client.is_active)

        # Update in database
        success = current_app.client_repo.update(client_id, client)

        if success:
            entity_label = f"{client.first_name} {client.last_name}"
            _audit_changes('client', client_id, entity_label,
                           _client_old, data,
                           ['first_name', 'last_name', 'phone', 'email',
                            'date_of_birth', 'notes', 'preferences', 'is_active'])
            return jsonify({
                'success': True,
                'message': 'Klient został zaktualizowany'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Nie udało się zaktualizować klienta'
            }), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/clients/<int:client_id>', methods=['DELETE'])
@login_required
@module_permission_required('clients')
def delete_client(client_id):
    """Deactivate client (soft delete)"""
    try:
        row = current_app.client_repo.get_by_id(client_id)
        if not row:
            return jsonify({'success': False, 'error': 'Client not found'}), 404

        client_name = f"{row.get('first_name','')} {row.get('last_name','')}".strip()
        success = current_app.client_repo.deactivate(client_id)

        if success:
            _audit('client', 'DELETE', entity_id=client_id, entity_label=client_name)
            return jsonify({
                'success': True,
                'message': 'Klient został dezaktywowany'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Nie udało się dezaktywować klienta'
            }), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/clients/<int:client_id>/activate', methods=['POST'])
@login_required
@module_permission_required('clients')
def activate_client(client_id):
    """Reactivate client"""
    try:
        row = current_app.client_repo.get_by_id(client_id)
        if not row:
            return jsonify({'success': False, 'error': 'Client not found'}), 404

        success = current_app.client_repo.activate(client_id)

        if success:
            return jsonify({
                'success': True,
                'message': 'Klient został aktywowany'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Nie udało się aktywować klienta'
            }), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/clients/statistics', methods=['GET'])
@login_required
@module_permission_required('clients')
def get_client_statistics():
    """Get client statistics"""
    try:
        stats = current_app.client_repo.get_statistics()

        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/clients/birthdays', methods=['GET'])
@login_required
@module_permission_required('clients')
def get_upcoming_birthdays():
    """Get clients with upcoming birthdays"""
    try:
        days_ahead = request.args.get('days', 30, type=int)
        rows = current_app.client_repo.get_upcoming_birthdays(days_ahead)

        # Convert to Client objects
        clients = [current_app.client_repo.row_to_client(row) for row in rows]
        clients_data = []

        for client in clients:
            client_dict = {
                'id': client.id,
                'full_name': client.full_name,
                'phone': client.phone,
                'email': client.email,
                'date_of_birth': client.date_of_birth.isoformat() if client.date_of_birth else None,
                'age': client.age
            }
            clients_data.append(client_dict)

        return jsonify({
            'success': True,
            'clients': clients_data,
            'count': len(clients_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# SERVICES API ENDPOINTS
# ============================================================================

@api_bp.route('/services', methods=['GET'])
@login_required
@module_permission_required('services')
def get_services():
    """Get all services with optional filtering"""
    search_query = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    service_type = request.args.get('type', '').strip()
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    try:
        if search_query:
            rows = current_app.service_repo.search(search_query, active_only)
        elif category:
            rows = current_app.service_repo.get_by_category(category, active_only)
        elif service_type in ('main', 'addon'):
            rows = current_app.service_repo.get_by_type(service_type, active_only)
        else:
            rows = current_app.service_repo.get_all(active_only)

        # Convert Row objects to Service objects
        services = [current_app.service_repo.row_to_service(row) for row in rows]
        services_data = []

        for service in services:
            service_dict = {
                'id': service.id,
                'name': service.name,
                'description': service.description,
                'category': service.category,
                'duration_minutes': service.duration_minutes,
                'formatted_duration': service.formatted_duration,
                'price': service.price,
                'currency': service.currency,
                'formatted_price': service.formatted_price,
                'service_type': service.service_type,
                'is_active': service.is_active,
                'created_at': service.created_at.isoformat() if service.created_at else None,
                'updated_at': service.updated_at.isoformat() if service.updated_at else None
            }
            services_data.append(service_dict)

        return jsonify({
            'success': True,
            'services': services_data,
            'count': len(services_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/services/<int:service_id>', methods=['GET'])
@login_required
@module_permission_required('services')
def get_service(service_id):
    """Get single service by ID"""
    try:
        row = current_app.service_repo.get_by_id(service_id)
        if not row:
            return jsonify({'success': False, 'error': 'Usługa nie znaleziona'}), 404

        service = current_app.service_repo.row_to_service(row)
        service_dict = {
            'id': service.id,
            'name': service.name,
            'description': service.description,
            'category': service.category,
            'duration_minutes': service.duration_minutes,
            'formatted_duration': service.formatted_duration,
            'price': service.price,
            'currency': service.currency,
            'formatted_price': service.formatted_price,
            'service_type': service.service_type,
            'is_active': service.is_active,
            'created_at': service.created_at.isoformat() if service.created_at else None,
            'updated_at': service.updated_at.isoformat() if service.updated_at else None
        }

        return jsonify({
            'success': True,
            'service': service_dict
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/services', methods=['POST'])
@login_required
@module_permission_required('services')
def create_service_endpoint():
    """Create new service"""
    try:
        data = request.get_json()

        # Validate required fields
        service_type = data.get('service_type', 'main')
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Nazwa usługi jest wymagana'}), 400
        if service_type == 'main' and not data.get('category'):
            return jsonify({'success': False, 'error': 'Kategoria jest wymagana dla usługi głównej'}), 400
        if data.get('duration_minutes') is None:
            return jsonify({'success': False, 'error': 'Czas trwania jest wymagany'}), 400
        if data.get('price') is None:
            return jsonify({'success': False, 'error': 'Cena jest wymagana'}), 400

        from database.models import Service
        service = Service(
            name=data.get('name'),
            description=data.get('description'),
            category=data.get('category') if service_type == 'main' else None,
            duration_minutes=int(data.get('duration_minutes')),
            price=float(data.get('price')),
            currency=data.get('currency', 'PLN'),
            service_type=service_type,
            is_active=data.get('is_active', True)
        )

        service_id = current_app.service_repo.create(service)

        _audit('service', 'CREATE', entity_id=service_id,
               entity_label=service.name,
               new_value=f"{service.price} {service.currency} / {service.duration_minutes}min")

        return jsonify({
            'success': True,
            'service_id': service_id,
            'message': 'Usługa została utworzona pomyślnie'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/services/<int:service_id>', methods=['PUT'])
@login_required
@module_permission_required('services')
def update_service(service_id):
    """Update existing service"""
    try:
        # Check if service exists
        existing = current_app.service_repo.get_by_id(service_id)
        if not existing:
            return jsonify({'success': False, 'error': 'Usługa nie znaleziona'}), 404

        data = request.get_json()
        service_type = data.get('service_type', 'main')

        from database.models import Service
        service = Service(
            id=service_id,
            name=data.get('name'),
            description=data.get('description'),
            category=data.get('category') if service_type == 'main' else None,
            duration_minutes=int(data.get('duration_minutes')),
            price=float(data.get('price')),
            currency=data.get('currency', 'PLN'),
            service_type=service_type,
            is_active=data.get('is_active', True)
        )

        success = current_app.service_repo.update(service_id, service)

        if success:
            _audit_changes('service', service_id, service.name,
                           existing, data,
                           ['name', 'description', 'category', 'duration_minutes',
                            'price', 'currency', 'service_type', 'is_active'])
            return jsonify({
                'success': True,
                'message': 'Usługa została zaktualizowana pomyślnie'
            })
        else:
            return jsonify({'success': False, 'error': 'Nie udało się zaktualizować usługi'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/services/<int:service_id>', methods=['DELETE'])
@login_required
@module_permission_required('services')
def delete_service(service_id):
    """Delete (deactivate) service"""
    try:
        existing = current_app.service_repo.get_by_id(service_id)
        service_name = existing['name'] if existing else str(service_id)
        success = current_app.service_repo.delete(service_id)

        if success:
            _audit('service', 'DELETE', entity_id=service_id, entity_label=service_name)
            return jsonify({
                'success': True,
                'message': 'Usługa została dezaktywowana'
            })
        else:
            return jsonify({'success': False, 'error': 'Nie udało się dezaktywować usługi'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/services/statistics', methods=['GET'])
@login_required
@module_permission_required('services')
def get_service_statistics():
    """Get service statistics"""
    try:
        stats = current_app.service_repo.get_statistics()

        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/services/categories', methods=['GET'])
@login_required
@module_permission_required('services')
def get_service_categories():
    """Get all service categories"""
    try:
        categories = current_app.service_repo.get_categories()

        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# EMPLOYEES API ENDPOINTS
# ============================================================================

@api_bp.route('/employees', methods=['GET'])
@login_required
@module_permission_required('employees')
def get_employees():
    """Get all employees with optional filtering"""
    search_query = request.args.get('search', '').strip()
    position = request.args.get('position', '').strip()
    active_only = request.args.get('active_only', 'true').lower() == 'true'

    try:
        if search_query:
            rows = current_app.employee_repo.search(search_query, active_only)
        elif position:
            rows = current_app.employee_repo.get_by_position(position, active_only)
        else:
            rows = current_app.employee_repo.get_all(active_only)

        # Convert Row objects to Employee objects
        employees = [current_app.employee_repo.row_to_employee(row) for row in rows]
        employees_data = []

        for employee in employees:
            employee_dict = {
                'id': employee.id,
                'user_id': employee.user_id,
                'full_name': employee.full_name,
                'first_name': employee.first_name,
                'last_name': employee.last_name,
                'phone': employee.phone,
                'email': employee.email,
                'position': employee.position,
                'employment_status': employee.employment_status,
                'hire_date': employee.hire_date.isoformat() if employee.hire_date else None,
                'termination_date': employee.termination_date.isoformat() if employee.termination_date else None,
                'base_salary': employee.base_salary,
                'commission_rate': employee.commission_rate,
                'is_active': employee.is_active,
                'created_at': employee.created_at.isoformat() if employee.created_at else None
            }
            employees_data.append(employee_dict)

        return jsonify({
            'success': True,
            'employees': employees_data,
            'count': len(employees_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/employees/<int:employee_id>', methods=['GET'])
@login_required
@module_permission_required('employees')
def get_employee(employee_id):
    """Get single employee by ID"""
    try:
        row = current_app.employee_repo.get_by_id(employee_id)
        if not row:
            return jsonify({'success': False, 'error': 'Pracownik nie znaleziony'}), 404

        employee = current_app.employee_repo.row_to_employee(row)
        employee_dict = {
            'id': employee.id,
            'user_id': employee.user_id,
            'full_name': employee.full_name,
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'phone': employee.phone,
            'email': employee.email,
            'position': employee.position,
            'employment_status': employee.employment_status,
            'hire_date': employee.hire_date.isoformat() if employee.hire_date else None,
            'termination_date': employee.termination_date.isoformat() if employee.termination_date else None,
            'base_salary': employee.base_salary,
            'commission_rate': employee.commission_rate,
            'skills': employee.get_skills_dict(),
            'specializations': employee.get_specializations_list(),
            'work_schedule': employee.get_work_schedule_dict(),
            'max_appointments_per_day': employee.max_appointments_per_day,
            'notes': employee.notes,
            'photo_path': employee.photo_path,
            'is_active': employee.is_active,
            'created_at': employee.created_at.isoformat() if employee.created_at else None,
            'updated_at': employee.updated_at.isoformat() if employee.updated_at else None
        }

        return jsonify({
            'success': True,
            'employee': employee_dict
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/employees', methods=['POST'])
@login_required
@module_permission_required('employees')
def create_employee_endpoint():
    """Create new employee"""
    try:
        data = request.get_json()

        # Validate required fields
        if not data.get('first_name'):
            return jsonify({'success': False, 'error': 'Imię jest wymagane'}), 400
        if not data.get('last_name'):
            return jsonify({'success': False, 'error': 'Nazwisko jest wymagane'}), 400

        # Check email uniqueness if provided
        if data.get('email'):
            existing = current_app.employee_repo.find_by_email(data.get('email'))
            if existing:
                return jsonify({'success': False, 'error': 'Pracownik z tym adresem email już istnieje'}), 400

        from database.models import Employee
        import json

        employee = Employee(
            user_id=data.get('user_id'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            phone=data.get('phone'),
            email=data.get('email'),
            position=data.get('position'),
            employment_status=data.get('employment_status', 'active'),
            hire_date=parse_date_string(data.get('hire_date')) if data.get('hire_date') else None,
            base_salary=float(data.get('base_salary')) if data.get('base_salary') else None,
            commission_rate=float(data.get('commission_rate')) if data.get('commission_rate') else None,
            skills=json.dumps(data.get('skills')) if data.get('skills') else None,
            specializations=json.dumps(data.get('specializations')) if data.get('specializations') else None,
            work_schedule=json.dumps(data.get('work_schedule')) if data.get('work_schedule') else None,
            max_appointments_per_day=int(data.get('max_appointments_per_day', 8)),
            notes=data.get('notes'),
            is_active=data.get('is_active', True)
        )

        employee_id = current_app.employee_repo.create(employee)

        _audit('employee', 'CREATE', entity_id=employee_id,
               entity_label=f"{employee.first_name} {employee.last_name}",
               new_value=employee.position)

        return jsonify({
            'success': True,
            'employee_id': employee_id,
            'message': 'Pracownik został utworzony pomyślnie'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/employees/<int:employee_id>', methods=['PUT'])
@login_required
@module_permission_required('employees')
def update_employee(employee_id):
    """Update existing employee"""
    try:
        # Check if employee exists
        existing = current_app.employee_repo.get_by_id(employee_id)
        if not existing:
            return jsonify({'success': False, 'error': 'Pracownik nie znaleziony'}), 404

        data = request.get_json()

        # Check email uniqueness if changed
        if data.get('email') and data.get('email') != existing['email']:
            email_check = current_app.employee_repo.find_by_email(data.get('email'))
            if email_check and email_check['id'] != employee_id:
                return jsonify({'success': False, 'error': 'Pracownik z tym adresem email już istnieje'}), 400

        from database.models import Employee
        import json

        employee = Employee(
            id=employee_id,
            user_id=data.get('user_id'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            phone=data.get('phone'),
            email=data.get('email'),
            position=data.get('position'),
            employment_status=data.get('employment_status', 'active'),
            hire_date=parse_date_string(data.get('hire_date')) if data.get('hire_date') else None,
            termination_date=parse_date_string(data.get('termination_date')) if data.get('termination_date') else None,
            base_salary=float(data.get('base_salary')) if data.get('base_salary') else None,
            commission_rate=float(data.get('commission_rate')) if data.get('commission_rate') else None,
            skills=json.dumps(data.get('skills')) if data.get('skills') else None,
            specializations=json.dumps(data.get('specializations')) if data.get('specializations') else None,
            work_schedule=json.dumps(data.get('work_schedule')) if data.get('work_schedule') else None,
            max_appointments_per_day=int(data.get('max_appointments_per_day', 8)),
            notes=data.get('notes'),
            photo_path=data.get('photo_path'),
            is_active=data.get('is_active', True)
        )

        success = current_app.employee_repo.update(employee_id, employee)

        if success:
            entity_label = f"{employee.first_name} {employee.last_name}"
            _audit_changes('employee', employee_id, entity_label,
                           existing, data,
                           ['first_name', 'last_name', 'phone', 'email',
                            'position', 'employment_status', 'hire_date',
                            'termination_date', 'base_salary', 'commission_rate',
                            'max_appointments_per_day', 'notes', 'is_active'])
            return jsonify({
                'success': True,
                'message': 'Pracownik został zaktualizowany pomyślnie'
            })
        else:
            return jsonify({'success': False, 'error': 'Nie udało się zaktualizować pracownika'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/employees/<int:employee_id>', methods=['DELETE'])
@login_required
@module_permission_required('employees')
def delete_employee(employee_id):
    """Delete (deactivate) employee"""
    try:
        existing = current_app.employee_repo.get_by_id(employee_id)
        emp_name = f"{existing['first_name']} {existing['last_name']}" if existing else str(employee_id)
        success = current_app.employee_repo.delete(employee_id)

        if success:
            _audit('employee', 'DELETE', entity_id=employee_id, entity_label=emp_name)
            return jsonify({
                'success': True,
                'message': 'Pracownik został dezaktywowany'
            })
        else:
            return jsonify({'success': False, 'error': 'Nie udało się dezaktywować pracownika'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/employees/statistics', methods=['GET'])
@login_required
@module_permission_required('employees')
def get_employee_statistics():
    """Get employee statistics"""
    try:
        stats = current_app.employee_repo.get_statistics()

        return jsonify({
            'success': True,
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/employees/positions', methods=['GET'])
@login_required
@module_permission_required('employees')
def get_employee_positions():
    """Get all employee positions"""
    try:
        positions = current_app.employee_repo.get_positions()

        return jsonify({
            'success': True,
            'positions': positions
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
