"""
Upload Staging API Routes - New multi-step upload workflow
"""
import json
import logging
import os
import traceback
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from flask import Blueprint, jsonify, request, current_app, send_file, session, \
	Response
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

from database.models import Invoice, UploadStaging
from utils.validators import DateParser

upload_bp = Blueprint('upload', __name__)


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


def get_session_id():
    """Get or create session ID for tracking uploads"""
    if 'upload_session_id' not in session:
        session['upload_session_id'] = str(uuid.uuid4())
    return session['upload_session_id']


@upload_bp.route('/stage', methods=['POST'])
def stage_files():
    """Upload PDF files to staging area without processing"""
    try:
        session_id = get_session_id()
        
        if 'files[]' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'}), 400
        
        files = request.files.getlist('files[]')
        staged_files = []
        
        # Create temp directory for this session
        temp_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'temp' / session_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = temp_dir / filename
                file.save(str(file_path))
                
                # Get file size
                file_size = file_path.stat().st_size
                
                # Create staging entry
                staging = UploadStaging(
                    session_id=session_id,
                    filename=filename,
                    file_path=str(file_path),
                    file_size=file_size
                )
                
                staging_id = current_app.staging_repo.create(staging)
                
                staged_files.append({
                    'id': staging_id,
                    'filename': filename,
                    'file_size': file_size,
                    'file_path': str(file_path)
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Invalid file type: {file.filename if file else "unknown"}'
                }), 400
        
        return jsonify({
            'success': True,
            'files': staged_files,
            'session_id': session_id
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@upload_bp.route('/staged', methods=['GET'])
def get_staged_files():
    """Get list of staged files for current session"""
    try:
        session_id = get_session_id()
        rows = current_app.staging_repo.get_by_session(session_id)

        files = []
        for row in rows:
            staging = current_app.staging_repo.row_to_upload_staging(row)
            files.append({
                'id': staging.id,
                'filename': staging.filename,
                'file_size': staging.file_size,
                'email_subject': staging.email_subject,
                'email_sender': staging.email_sender,
                'email_folder': staging.email_folder,
                'email_date': staging.email_date,
                'uploaded_at': staging.uploaded_at.isoformat() if staging.uploaded_at else None
            })

        return jsonify({
            'success': True,
            'files': files
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# IMPORTANT: This route must be defined BEFORE /staged/<filename> to avoid
# Flask matching "clear" as a filename parameter
@upload_bp.route('/staged/clear', methods=['DELETE'])
def clear_all_staged_files():
    """Remove all staged files for current session"""
    try:
        session_id = get_session_id()

        # Get all files for this session
        rows = current_app.staging_repo.get_by_session(session_id)

        # Delete physical files
        for row in rows:
            file_path = row['file_path']
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Error deleting file {file_path}: {e}")

        # Delete from database
        current_app.staging_repo.delete_by_session(session_id)

        # Clean up empty temp directory
        temp_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'temp' / session_id
        if temp_dir.exists():
            try:
                temp_dir.rmdir()
            except:
                pass  # Directory might not be empty, ignore

        return jsonify({
            'success': True,
            'message': 'All files cleared'
        })

    except Exception as e:
        logger.error(f"Error clearing staged files: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@upload_bp.route('/staged/<filename>', methods=['DELETE'])
def remove_staged_file(filename: str):
    """Remove a staged file"""
    try:
        session_id = get_session_id()

        # Get file info before deleting
        rows = current_app.staging_repo.get_by_session(session_id)
        file_path = None

        for row in rows:
            if row['filename'] == filename:
                file_path = row['file_path']
                break

        # Delete from database
        deleted = current_app.staging_repo.delete_by_filename(session_id, filename)

        if not deleted:
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Delete physical file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        return jsonify({
            'success': True,
            'message': f'File {filename} removed'
        })

    except Exception as e:
        logger.error(f"Error removing staged file {filename}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@upload_bp.route('/process', methods=['POST'])
def process_staged_files():
    """Process staged files with OCR extraction (Streaming)"""
    session_id = get_session_id()
    
    # Get list of filenames to process from request
    data = request.get_json() or {}
    filenames_to_process = data.get('filenames', None)
    
    # Capture app objects for use in generator
    staging_repo = current_app.staging_repo
    ocr_service = current_app.ocr_service
    validation_service = current_app.validation_service
    duplicate_detection = current_app.duplicate_detection
    
    def generate():
        try:
            # Get staged files
            rows = staging_repo.get_by_session(session_id)
            
            if not rows:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No files to process'})}\n\n"
                return

            # Filter rows if specific filenames requested
            rows_to_process = []
            for row in rows:
                if filenames_to_process and row['filename'] not in filenames_to_process:
                    continue
                rows_to_process.append(row)
            
            total_files = len(rows_to_process)
            if total_files == 0:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No matching files to process'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'start', 'total': total_files})}\n\n"
            
            for idx, row in enumerate(rows_to_process, 1):
                staging = staging_repo.row_to_upload_staging(row)
                file_path = Path(staging.file_path)
                
                # Emit start file event
                yield f"data: {json.dumps({'type': 'file_start', 'filename': staging.filename, 'current': idx, 'total': total_files})}\n\n"
                
                if not file_path.exists():
                    error_res = {
                        'filename': staging.filename,
                        'success': False,
                        'error': 'File not found on disk'
                    }
                    yield f"data: {json.dumps({'type': 'file_complete', 'result': error_res})}\n\n"
                    continue
                
                try:
                    # Preprocessing & OCR
                    yield f"data: {json.dumps({'type': 'progress', 'filename': staging.filename, 'message': 'OCR: Rozpoznawanie tekstu...', 'percent': 20})}\n\n"
                    logger.info(f"[PROCESS] Processing file: {staging.filename}")
                    
                    # Call OCR service
                    extracted_data = ocr_service.process_pdf(str(file_path))
                    
                    yield f"data: {json.dumps({'type': 'progress', 'filename': staging.filename, 'message': 'Ekstrakcja danych...', 'percent': 60})}\n\n"
                    
                    # Parse dates
                    invoice_date = parse_date_string(extracted_data.get('issue_date'))
                    if not invoice_date:
                        invoice_date = datetime.now().date()
                    
                    payment_due_date_str = extracted_data.get('payment_due_date')
                    payment_due_date = None
                    payment_term = extracted_data.get('payment_method')
                    
                    if payment_due_date_str:
                        if payment_due_date_str == 'POBRANIE':
                            payment_term = 'POBRANIE'
                        else:
                            payment_due_date = parse_date_string(payment_due_date_str)
                    
                    # Create invoice object
                    yield f"data: {json.dumps({'type': 'progress', 'filename': staging.filename, 'message': 'Walidacja...', 'percent': 80})}\n\n"
                    
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
                    validation_result = validation_service.validate_invoice(invoice)
                    validation_errors = validation_result.get('errors', [])
                    validation_warnings = validation_result.get('warnings', [])
                    
                    # Check duplicates
                    yield f"data: {json.dumps({'type': 'progress', 'filename': staging.filename, 'message': 'Sprawdzanie duplikatów...', 'percent': 90})}\n\n"
                    is_duplicate, duplicate_info = duplicate_detection.check_duplicate(invoice)
                    
                    # Success Result
                    result = {
                        'filename': staging.filename,
                        'success': True,
                        'extracted_data': extracted_data,
                        'validation_errors': validation_errors,
                        'validation_warnings': validation_warnings,
                        'is_duplicate': is_duplicate,
                        'duplicate_info': duplicate_info,
                        'email_subject': staging.email_subject,
                        'email_sender': staging.email_sender,
                        'email_folder': staging.email_folder,
                        'email_date': staging.email_date
                    }
                    
                    yield f"data: {json.dumps({'type': 'file_complete', 'result': result})}\n\n"
                    logger.info(f"[PROCESS] File processed successfully: {staging.filename}")
                    
                except Exception as e:
                    logger.error(f"[PROCESS] Error processing {staging.filename}: {str(e)}")
                    logger.error(f"[PROCESS] Traceback: {traceback.format_exc()}")
                    
                    error_res = {
                        'filename': staging.filename,
                        'success': False,
                        'error': str(e)
                    }
                    yield f"data: {json.dumps({'type': 'file_complete', 'result': error_res})}\n\n"
            
            # All done
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            logger.error(f"Global processing error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@upload_bp.route('/finalize', methods=['POST'])
def finalize_uploads():
    """Save selected processed invoices to database"""
    session_id = get_session_id()
    data = request.get_json()

    invoices_to_save = data.get('invoices', [])

    if not invoices_to_save:
        return jsonify({'success': False, 'error': 'No invoices to save'}), 400

    saved_invoices = []
    failed_invoices = []
    seller_warnings = []  # Track seller-related warnings

    # Get staged files for file path resolution
    rows = current_app.staging_repo.get_by_session(session_id)
    staged_files_map = {}
    for row in rows:
        staged_files_map[row['filename']] = row['file_path']
    
    for invoice_data in invoices_to_save:
        filename = invoice_data.get('filename')
        temp_file_path = staged_files_map.get(filename)
        
        if not temp_file_path or not os.path.exists(temp_file_path):
            failed_invoices.append({
                'filename': filename,
                'error': 'File not found in staging'
            })
            continue
        
        # Determine permanent path
        permanent_dir = Path(current_app.config['UPLOAD_FOLDER'])
        permanent_path = permanent_dir / filename
        
        # Handle duplicate filenames in destination
        counter = 1
        while permanent_path.exists():
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) == 2:
                permanent_path = permanent_dir / f"{name_parts[0]}_{counter}.{name_parts[1]}"
            else:
                permanent_path = permanent_dir / f"{filename}_{counter}"
            counter += 1
        
        file_moved = False
        try:
            # Move file from temp to permanent storage
            os.rename(temp_file_path, str(permanent_path))
            file_moved = True
            
            # Create Invoice object
            extracted_data = invoice_data.get('extracted_data', {})
            
            invoice_date = parse_date_string(extracted_data.get('issue_date'))
            if not invoice_date:
                invoice_date = datetime.now().date()
            
            payment_due_date_str = extracted_data.get('payment_due_date')
            payment_due_date = None
            payment_term = extracted_data.get('payment_method')
            
            if payment_due_date_str:
                if payment_due_date_str == 'POBRANIE':
                    payment_term = 'POBRANIE'
                else:
                    payment_due_date = parse_date_string(payment_due_date_str)
            
            # Set default values
            seller_name = (extracted_data.get('seller_name') or '').strip() or '(brak danych)'
            invoice_number = (extracted_data.get('invoice_number') or '').strip() or '(brak danych)'
            
            invoice = Invoice(
                seller_name=seller_name,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                amount=extracted_data.get('total_amount', 0.0),
                currency=extracted_data.get('currency', 'PLN'),
                seller_nip=extracted_data.get('seller_nip'),
                bank_account=extracted_data.get('bank_account'),
                payment_due_date=payment_due_date,
                payment_term=payment_term,
                status='Nieopłacona',
                pdf_path=str(permanent_path),
                ocr_confidence=extracted_data.get('ocr_confidence'),
                is_duplicate=False
            )

            # Seller lookup/creation (same logic as /api/upload endpoint)
            seller_id = None
            if invoice.seller_nip:
                try:
                    seller_id, created, conflict = current_app.seller_service.get_or_create_seller(
                        nip=invoice.seller_nip,
                        name=invoice.seller_name,
                        address=None
                    )

                    if conflict:
                        # Add conflict warning but continue saving
                        seller_warnings.append({
                            'filename': filename,
                            'message': conflict['message']
                        })
                    elif created:
                        logger.info(f"[FINALIZE] Created new seller: {invoice.seller_name} (NIP: {invoice.seller_nip})")
                except Exception as e:
                    logger.warning(f"[FINALIZE] Seller lookup failed for {filename}: {str(e)}")

            # Save to database with seller_id
            invoice_id = current_app.invoice_repo.create(invoice, seller_id=seller_id)

            # Increment seller invoice count if seller was linked
            if seller_id:
                current_app.seller_repo.increment_invoice_count(seller_id)
            
            # Success
            saved_invoices.append({
                'invoice_id': invoice_id,
                'filename': filename
            })
            
            # Remove from staging DB (optional here, or cleanup all at end)
            # It's better to remove individual successful ones to prevent retry issues
            current_app.staging_repo.delete_by_filename(session_id, filename)
            
        except Exception as e:
            error_msg = str(e)
            if "UNIQUE constraint failed" in error_msg:
                error_msg = f"Duplikat numeru faktury: {invoice_number}"
            
            logger.error(f"[FINALIZE] Failed to save {filename}: {error_msg}")
            
            # Rollback file move if it happened
            if file_moved and os.path.exists(permanent_path):
                try:
                    os.rename(str(permanent_path), temp_file_path)
                except Exception as rollback_err:
                    logger.error(f"[FINALIZE] Rollback failed: {rollback_err}")
            
            failed_invoices.append({
                'filename': filename,
                'error': error_msg
            })

    # If all saved successfully
    if not failed_invoices:
        # Clean up empty temp directory
        temp_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'temp' / session_id
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        # Clear session
        session.pop('upload_session_id', None)

        response_data = {
            'success': True,
            'saved_invoices': saved_invoices,
            'count': len(saved_invoices)
        }
        # Include seller warnings if any (non-blocking)
        if seller_warnings:
            response_data['seller_warnings'] = seller_warnings
        return jsonify(response_data)
    else:
        # Partial success
        response_data = {
            'success': False,
            'saved_invoices': saved_invoices,
            'failed_invoices': failed_invoices,
            'error': f"Zapisano {len(saved_invoices)} faktur, wystąpiły błędy przy {len(failed_invoices)}."
        }
        # Include seller warnings if any
        if seller_warnings:
            response_data['seller_warnings'] = seller_warnings
        return jsonify(response_data)


@upload_bp.route('/view-pdf/<filename>', methods=['GET'])
def view_pdf(filename: str):
    """View a staged PDF file"""
    try:
        session_id = get_session_id()
        
        # Get file from staging
        rows = current_app.staging_repo.get_by_session(session_id)
        
        for row in rows:
            if row['filename'] == filename:
                file_path = Path(row['file_path'])
                if file_path.exists():
                    return send_file(
                        str(file_path),
                        mimetype='application/pdf'
                    )
        
        return jsonify({'success': False, 'error': 'PDF not found'}), 404
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
