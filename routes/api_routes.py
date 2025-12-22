"""
API routes - JSON endpoints for AJAX calls
"""
from flask import Blueprint, jsonify, request, current_app, send_file, session
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
                # Convert amount to float
                elif key == 'amount':
                    if isinstance(value, str):
                        value = float(value) if value and value.strip() else 0.0
                    elif value is None:
                        value = 0.0
                # Convert ocr_confidence to float if present
                elif key == 'ocr_confidence' and isinstance(value, str):
                    value = float(value) if value else None
                setattr(invoice, key, value)

        # Validate
        validation_result = current_app.validation_service.validate_invoice(invoice)
        
        # Only fail if there are actual errors (not just warnings)
        if validation_result.get('errors'):
            return jsonify({
                'success': False,
                'error': 'Validation failed',
                'validation_errors': validation_result
            }), 400

        # Save
        current_app.invoice_repo.update(invoice_id, invoice)
        
        # TODO: Refactor audit logging to log individual field changes
        # current_app.audit_repo.log_change(
        #     invoice_id=invoice_id,
        #     action='UPDATE',
        #     changed_fields=list(data.keys()),
        #     old_values={},
        #     new_values=data
        # )

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
