"""
API routes - JSON endpoints for AJAX calls
"""
from flask import Blueprint, jsonify, request, current_app, send_file
from werkzeug.utils import secure_filename
from pathlib import Path
import tempfile
from datetime import datetime, date
from typing import Optional

from database.models import Invoice
from utils.text_extractor import TextExtractor

api_bp = Blueprint('api', __name__)

# Create TextExtractor instance for date parsing
_text_extractor = TextExtractor()


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_date_string(date_str: Optional[str]) -> Optional[date]:
    """
    Parse date string to date object using TextExtractor's normalization
    Handles multiple date formats: YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY

    Args:
        date_str: Date string in various formats or None

    Returns:
        date object or None
    """
    if not date_str:
        return None

    # Use TextExtractor to normalize the date string to ISO format
    normalized = _text_extractor._normalize_date(date_str)

    if not normalized:
        return None

    # Convert normalized ISO string to date object
    try:
        return datetime.strptime(normalized, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


@api_bp.route('/invoices', methods=['GET'])
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


@api_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
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
def update_invoice(invoice_id: int):
    """Update invoice"""
    try:
        data = request.get_json()
        row = current_app.invoice_repo.get_by_id(invoice_id)

        if not row:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        # Convert Row to Invoice object
        invoice = current_app.invoice_repo.row_to_invoice(row)

        # Update invoice fields
        for key, value in data.items():
            if hasattr(invoice, key):
                # Convert date strings to date objects
                if key in ('invoice_date', 'payment_due_date') and isinstance(value, str):
                    value = parse_date_string(value)
                setattr(invoice, key, value)

        # Validate
        validation_errors = current_app.validation_service.validate_invoice(invoice)
        if validation_errors:
            return jsonify({
                'success': False,
                'error': 'Validation failed',
                'validation_errors': validation_errors
            }), 400

        # Save
        current_app.invoice_repo.update(invoice)
        current_app.audit_repo.log_change(
            invoice_id=invoice_id,
            action='UPDATE',
            changed_fields=list(data.keys()),
            old_values={},
            new_values=data
        )

        return jsonify({
            'success': True,
            'message': 'Invoice updated successfully',
            'invoice': vars(invoice)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/invoices/<int:invoice_id>', methods=['DELETE'])
def delete_invoice(invoice_id: int):
    """Delete invoice"""
    try:
        row = current_app.invoice_repo.get_by_id(invoice_id)
        if not row:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        # Convert Row to Invoice object for audit log
        invoice = current_app.invoice_repo.row_to_invoice(row)

        current_app.invoice_repo.delete(invoice_id)
        current_app.audit_repo.log_change(
            invoice_id=invoice_id,
            action='DELETE',
            changed_fields=[],
            old_values=vars(invoice),
            new_values={}
        )

        return jsonify({
            'success': True,
            'message': 'Invoice deleted successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/invoices/statistics', methods=['GET'])
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


@api_bp.route('/upload', methods=['POST'])
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

                    results.append({
                        'filename': filename,
                        'success': True,
                        'extracted_data': extracted_data,
                        'validation_errors': validation_errors,
                        'validation_warnings': validation_warnings,
                        'is_duplicate': is_duplicate,
                        'duplicate_info': duplicate_info
                    })

                    # Save if no validation errors and not duplicate
                    if len(validation_errors) == 0 and not is_duplicate:
                        saved_invoice_id = current_app.invoice_repo.create(invoice)
                        results[-1]['invoice_id'] = saved_invoice_id
                        results[-1]['saved'] = True
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
def export_invoices(format: str):
    """Export invoices to Excel or CSV"""
    try:
        if format not in ['excel', 'csv']:
            return jsonify({'success': False, 'error': 'Invalid format'}), 400

        invoices = current_app.invoice_repo.get_all()

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
def import_from_email():
    """Import PDFs from email"""
    try:
        data = request.get_json()

        # Get email settings
        from config.email_settings import load_email_settings
        email_config = load_email_settings()

        # Connect and fetch PDFs
        pdf_files = current_app.email_service.fetch_pdfs_from_email(
            server=email_config.get('imap_server'),
            username=email_config.get('email'),
            password=email_config.get('password'),
            folder=data.get('folder', 'INBOX'),
            date_from=data.get('date_from'),
            date_to=data.get('date_to')
        )

        # Process each PDF
        results = []
        for pdf_data in pdf_files:
            # Save temporarily
            temp_path = Path(current_app.config['UPLOAD_FOLDER']) / pdf_data['filename']
            with open(temp_path, 'wb') as f:
                f.write(pdf_data['content'])

            # Process using OCR
            try:
                extracted_data = current_app.ocr_service.process_pdf(str(temp_path))

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
                    pdf_path=str(temp_path),
                    ocr_confidence=extracted_data.get('ocr_confidence'),
                    is_duplicate=False
                )

                validation_result = current_app.validation_service.validate_invoice(invoice)
                validation_errors = validation_result.get('errors', [])
                validation_warnings = validation_result.get('warnings', [])
                is_duplicate, duplicate_info = current_app.duplicate_detection.check_duplicate(invoice)

                if len(validation_errors) == 0 and not is_duplicate:
                    saved_invoice_id = current_app.invoice_repo.create(invoice)
                    results.append({
                        'filename': pdf_data['filename'],
                        'success': True,
                        'invoice_id': saved_invoice_id,
                        'saved': True
                    })
                else:
                    results.append({
                        'filename': pdf_data['filename'],
                        'success': False,
                        'validation_errors': validation_errors,
                        'validation_warnings': validation_warnings,
                        'is_duplicate': is_duplicate,
                        'saved': False
                    })
            except Exception as e:
                results.append({
                    'filename': pdf_data['filename'],
                    'success': False,
                    'error': str(e)
                })

        return jsonify({
            'success': True,
            'results': results,
            'total_processed': len(results)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/email/test', methods=['POST'])
def test_email_connection():
    """Test email connection"""
    try:
        data = request.get_json()

        success = current_app.email_service.test_connection(
            server=data.get('imap_server'),
            username=data.get('email'),
            password=data.get('password')
        )

        if success:
            return jsonify({
                'success': True,
                'message': 'Connection successful'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Connection failed'
            }), 400
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
def get_history():
    """Get audit history"""
    try:
        invoice_id = request.args.get('invoice_id', type=int)

        if invoice_id:
            entries = current_app.audit_repo.get_by_invoice_id(invoice_id)
        else:
            entries = current_app.audit_repo.get_all()

        entries_data = [vars(entry) for entry in entries]

        return jsonify({
            'success': True,
            'entries': entries_data,
            'count': len(entries_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/pdf/<int:invoice_id>', methods=['GET'])
def view_pdf(invoice_id: int):
    """View PDF file"""
    try:
        row = current_app.invoice_repo.get_by_id(invoice_id)
        if not row:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        # Convert Row to Invoice object
        invoice = current_app.invoice_repo.row_to_invoice(row)

        if not invoice.pdf_path:
            return jsonify({'success': False, 'error': 'PDF not found'}), 404

        pdf_path = Path(invoice.pdf_path)
        if not pdf_path.exists():
            return jsonify({'success': False, 'error': 'PDF file not found on disk'}), 404

        return send_file(
            str(pdf_path),
            mimetype='application/pdf'
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
