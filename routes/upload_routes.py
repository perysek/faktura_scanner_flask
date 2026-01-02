"""
Upload Staging API Routes - New multi-step upload workflow
"""
from flask import Blueprint, jsonify, request, current_app, send_file, session
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import datetime, date
from typing import Optional
import uuid
import os
import logging

logger = logging.getLogger(__name__)

from database.models import Invoice, UploadStaging
from utils.text_extractor import TextExtractor

upload_bp = Blueprint('upload', __name__)

# Create TextExtractor instance for date parsing
_text_extractor = TextExtractor()


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
    Parse date string to date object using TextExtractor's normalization
    Handles multiple date formats: YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY
    """
    if not date_str:
        return None
    
    normalized = _text_extractor._normalize_date(date_str)
    
    if not normalized:
        return None
    
    try:
        return datetime.strptime(normalized, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


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
        return jsonify({'success': False, 'error': str(e)}), 500


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
                    print(f"Error deleting file {file_path}: {e}")
        
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
        return jsonify({'success': False, 'error': str(e)}), 500


@upload_bp.route('/process', methods=['POST'])
def process_staged_files():
    """Process staged files with OCR extraction"""
    try:
        session_id = get_session_id()
        
        # Get list of filenames to process from request (or process all if not specified)
        data = request.get_json() or {}
        filenames_to_process = data.get('filenames', None)
        
        # Get staged files
        rows = current_app.staging_repo.get_by_session(session_id)
        
        if not rows:
            return jsonify({'success': False, 'error': 'No files to process'}), 400
        
        results = []
        
        for row in rows:
            staging = current_app.staging_repo.row_to_upload_staging(row)
            
            # Skip if specific filenames requested and this isn't one of them
            if filenames_to_process and staging.filename not in filenames_to_process:
                continue
            
            file_path = Path(staging.file_path)
            
            if not file_path.exists():
                results.append({
                    'filename': staging.filename,
                    'success': False,
                    'error': 'File not found on disk'
                })
                continue
            
            # Process with OCR
            # Process with OCR
            try:
                
                logger.info(f"[PROCESS] Processing file: {staging.filename}")
                extracted_data = current_app.ocr_service.process_pdf(str(file_path))
                
                # Log extracted data
                logger.info(f"[PROCESS] Extracted data:")
                logger.info(f"  - invoice_number: {extracted_data.get('invoice_number')}")
                logger.info(f"  - seller_name: {extracted_data.get('seller_name')}")
                logger.info(f"  - seller_nip: {extracted_data.get('seller_nip')}")
                logger.info(f"  - total_amount: {extracted_data.get('total_amount')}")
                logger.info(f"  - issue_date: {extracted_data.get('issue_date')}")
                logger.info(f"  - ocr_confidence: {extracted_data.get('ocr_confidence')}")
                
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
                
                logger.info(f"[PROCESS] Validation errors: {validation_errors}")
                logger.info(f"[PROCESS] Validation warnings: {validation_warnings}")
                
                # Check duplicates
                is_duplicate, duplicate_info = current_app.duplicate_detection.check_duplicate(invoice)
                
                results.append({
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
                })
                
                logger.info(f"[PROCESS] File processed successfully: {staging.filename}")
                
            except Exception as e:
                import traceback
                logger.error(f"[PROCESS] Error processing {staging.filename}: {str(e)}")
                logger.error(f"[PROCESS] Traceback: {traceback.format_exc()}")
                results.append({
                    'filename': staging.filename,
                    'success': False,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'results': results
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@upload_bp.route('/finalize', methods=['POST'])
def finalize_uploads():
    """Save selected processed invoices to database"""
    try:
        session_id = get_session_id()
        data = request.get_json()
        
        invoices_to_save = data.get('invoices', [])
        
        if not invoices_to_save:
            return jsonify({'success': False, 'error': 'No invoices to save'}), 400
        
        saved_invoices = []
        
        # Get staged files for file path resolution
        rows = current_app.staging_repo.get_by_session(session_id)
        staged_files_map = {}
        for row in rows:
            staged_files_map[row['filename']] = row['file_path']
        
        for invoice_data in invoices_to_save:
            filename = invoice_data.get('filename')
            temp_file_path = staged_files_map.get(filename)
            
            if not temp_file_path or not os.path.exists(temp_file_path):
                continue
            
            # Move file from temp to permanent storage
            permanent_dir = Path(current_app.config['UPLOAD_FOLDER'])
            permanent_path = permanent_dir / filename
            
            # Handle duplicate filenames
            counter = 1
            while permanent_path.exists():
                name_parts = filename.rsplit('.', 1)
                if len(name_parts) == 2:
                    permanent_path = permanent_dir / f"{name_parts[0]}_{counter}.{name_parts[1]}"
                else:
                    permanent_path = permanent_dir / f"{filename}_{counter}"
                counter += 1
            
            # Move file
            os.rename(temp_file_path, str(permanent_path))
            
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
            
            # Set default values for missing required fields
            seller_name = (extracted_data.get('seller_name') or '').strip()
            if not seller_name:
                seller_name = '(brak danych)'
            
            invoice_number = (extracted_data.get('invoice_number') or '').strip()
            if not invoice_number:
                invoice_number = '(brak danych)'
            
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
            
            # Save to database
            invoice_id = current_app.invoice_repo.create(invoice)
            saved_invoices.append({
                'invoice_id': invoice_id,
                'filename': filename
            })
        
        # Clean up staging data
        current_app.staging_repo.delete_by_session(session_id)
        
        # Clean up temp directory
        temp_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'temp' / session_id
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Clear session
        session.pop('upload_session_id', None)
        
        return jsonify({
            'success': True,
            'saved_invoices': saved_invoices,
            'count': len(saved_invoices)
        })
    
    except Exception as e:
        import traceback
        logger.error(f"[FINALIZE] Error: {str(e)}")
        logger.error(f"[FINALIZE] Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
