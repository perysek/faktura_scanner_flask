"""
Upload Staging API Routes - New multi-step upload workflow
"""
import json
import logging
import mimetypes
import os
import shutil
import traceback
import uuid
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from flask import Blueprint, jsonify, request, current_app, send_file, session, \
	Response, stream_with_context
from flask_login import login_required
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

from config.auth_config import module_permission_required
from config.database import DatabaseConnection
from database.models import Invoice, UploadStaging
from exceptions import AppError, ValidationError, NotFoundError
from services.ocr_service import PDFPasswordRequired
from utils.validators import DateParser

upload_bp = Blueprint('upload', __name__)

# ── P1-1: Authentication guard for all upload routes ──
@upload_bp.before_request
@login_required
@module_permission_required('invoices')
def _require_auth():
	"""All upload endpoints require authenticated user with invoices permission."""
	pass

# ── P1-4: Per-file size limit (10 MB) ──
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per individual file


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
            raise ValidationError('Brak plikow')

        files = request.files.getlist('files[]')
        staged_files = []

        # Create temp directory for this session
        temp_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'temp' / session_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        for file in files:
            if file and allowed_file(file.filename):
                # P1-7: UUID prefix to prevent collisions and empty names
                safe_name = secure_filename(file.filename)
                if not safe_name:
                    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'pdf'
                    safe_name = f'upload.{ext}'
                filename = f"{uuid.uuid4().hex[:8]}_{safe_name}"
                file_path = temp_dir / filename
                file.save(str(file_path))

                # P1-4: Per-file size check after save
                file_size = file_path.stat().st_size
                if file_size > MAX_FILE_SIZE:
                    file_path.unlink(missing_ok=True)
                    raise ValidationError(
                        f'Plik {file.filename} przekracza limit {MAX_FILE_SIZE // (1024*1024)} MB'
                    )

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
                raise ValidationError(
                    f'Niedozwolony typ pliku: {file.filename if file else "unknown"}'
                )

        return jsonify({
            'success': True,
            'files': staged_files,
            'session_id': session_id
        })

    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in stage_files')
        raise AppError('Blad podczas przesylania plikow')


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

    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in get_staged_files')
        raise AppError('Blad pobierania listy plikow')


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
            except OSError:
                pass  # Directory might not be empty, ignore

        return jsonify({
            'success': True,
            'message': 'All files cleared'
        })

    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in clear_all_staged_files')
        raise AppError('Blad usuwania plikow')


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
            raise NotFoundError('Plik nie istnieje')

        # Delete physical file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        return jsonify({
            'success': True,
            'message': f'File {filename} removed'
        })

    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in remove_staged_file')
        raise AppError('Blad usuwania pliku')


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

                    # Call OCR service — with password auto-lookup for encrypted PDFs
                    try:
                        extracted_data = ocr_service.process_pdf(str(file_path))
                    except PDFPasswordRequired:
                        # Encrypted PDF — try to find password
                        pdf_password = None

                        # 1. Try email sender pattern match
                        if staging.email_sender:
                            pdf_password = current_app.seller_password_repo.find_password_for_file(
                                email_sender=staging.email_sender
                            )
                            if pdf_password:
                                logger.info(f"[PROCESS] Found PDF password for email sender: {staging.email_sender}")

                        # 2. Try all stored passwords (for manual uploads without email metadata)
                        if not pdf_password:
                            all_pw_rows = current_app.seller_password_repo.get_all()
                            for pw_row in all_pw_rows:
                                candidate = pw_row['pdf_password']
                                if candidate and ocr_service.pdf_processor.try_unlock_pdf(str(file_path), candidate):
                                    pdf_password = candidate
                                    logger.info(f"[PROCESS] Found matching PDF password by trial (seller: {pw_row.get('seller_name', 'N/A')})")
                                    break

                        if not pdf_password:
                            # No password available — report error to user
                            error_msg = (
                                f"Plik PDF jest zabezpieczony hasłem. "
                                f"Dodaj hasło w Sprzedawcy → Hasła PDF"
                                f"{' (nadawca: ' + staging.email_sender + ')' if staging.email_sender else ''}."
                            )
                            error_res = {
                                'filename': staging.filename,
                                'success': False,
                                'error': error_msg,
                                'error_type': 'password_required',
                                'email_sender': staging.email_sender,
                            }
                            yield f"data: {json.dumps({'type': 'file_complete', 'result': error_res})}\n\n"
                            continue

                        # Retry with password
                        yield f"data: {json.dumps({'type': 'progress', 'filename': staging.filename, 'message': 'Odblokowywanie PDF hasłem...', 'percent': 30})}\n\n"
                        extracted_data = ocr_service.process_pdf(str(file_path), password=pdf_password)

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

                    # Enrich seller data from sellers table
                    seller_nip = extracted_data.get('seller_nip')
                    seller_name_ocr = (extracted_data.get('seller_name') or '').strip()
                    if seller_nip:
                        try:
                            normalized_nip = current_app.seller_service.normalize_nip(seller_nip)
                            existing_seller = current_app.seller_repo.find_by_nip(normalized_nip)
                            if existing_seller:
                                extracted_data['seller_name'] = existing_seller['seller_name']
                                logger.info(f"[PROCESS] Enriched seller_name from DB: {existing_seller['seller_name']} (NIP: {normalized_nip})")
                        except Exception as e:
                            logger.warning(f"[PROCESS] Seller NIP lookup for enrichment failed: {e}")
                    elif seller_name_ocr:
                        # No NIP extracted — try to find seller by name and fill NIP
                        try:
                            existing_seller = current_app.seller_repo.find_by_exact_name(seller_name_ocr)
                            if existing_seller and existing_seller.get('seller_nip'):
                                extracted_data['seller_nip'] = existing_seller['seller_nip']
                                logger.info(f"[PROCESS] Enriched seller_nip from DB: {existing_seller['seller_nip']} (name: {seller_name_ocr})")
                        except Exception as e:
                            logger.warning(f"[PROCESS] Seller name lookup for enrichment failed: {e}")

                    # Create invoice object
                    yield f"data: {json.dumps({'type': 'progress', 'filename': staging.filename, 'message': 'Walidacja...', 'percent': 80})}\n\n"

                    invoice = Invoice(
                        seller_name=extracted_data.get('seller_name', ''),
                        invoice_number=extracted_data.get('invoice_number', ''),
                        invoice_date=invoice_date,
                        amount=Decimal(str(extracted_data.get('total_amount') or 0)),
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
                        'error': 'Blad przetwarzania pliku'
                    }
                    yield f"data: {json.dumps({'type': 'file_complete', 'result': error_res})}\n\n"

            # All done
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            logger.error(f"Global processing error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Wystapil blad podczas przetwarzania'})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@upload_bp.route('/finalize', methods=['POST'])
def finalize_uploads():
    """Save selected processed invoices to database"""
    try:
        session_id = get_session_id()
        data = request.get_json()

        invoices_to_save = data.get('invoices', []) if data else []

        if not invoices_to_save:
            raise ValidationError('Brak faktur do zapisania')

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
                shutil.move(temp_file_path, str(permanent_path))
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
                    amount=Decimal(str(extracted_data.get('total_amount') or 0)),
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

                # Seller lookup/creation
                seller_id = None
                if invoice.seller_nip:
                    try:
                        seller_id, created, conflict = current_app.seller_service.get_or_create_seller(
                            nip=invoice.seller_nip,
                            name=invoice.seller_name,
                            address=None
                        )

                        if conflict:
                            # Use existing seller's name for the invoice
                            existing_seller = conflict.get('existing_seller')
                            if existing_seller:
                                invoice.seller_name = existing_seller.seller_name
                            # Add conflict warning but continue saving
                            seller_warnings.append({
                                'filename': filename,
                                'message': conflict['message']
                            })
                        elif not created:
                            # Existing seller found (no conflict) — use DB name
                            existing_row = current_app.seller_repo.find_by_nip(
                                current_app.seller_service.normalize_nip(invoice.seller_nip)
                            )
                            if existing_row:
                                invoice.seller_name = existing_row['seller_name']
                        elif created:
                            logger.info(f"[FINALIZE] Created new seller: {invoice.seller_name} (NIP: {invoice.seller_nip})")
                    except Exception as e:
                        logger.warning(f"[FINALIZE] Seller lookup failed for {filename}: {str(e)}")
                elif invoice.seller_name and invoice.seller_name != '(brak danych)':
                    # No NIP but have name — try to find seller by name and fill NIP + link
                    try:
                        existing_row = current_app.seller_repo.find_by_exact_name(invoice.seller_name)
                        if existing_row:
                            seller_id = existing_row['id']
                            if existing_row.get('seller_nip'):
                                invoice.seller_nip = existing_row['seller_nip']
                            logger.info(f"[FINALIZE] Linked seller by name: {invoice.seller_name} → ID {seller_id}")
                    except Exception as e:
                        logger.warning(f"[FINALIZE] Seller name lookup failed for {filename}: {str(e)}")

                # Save to database with seller_id
                invoice_id = current_app.invoice_repo.create(invoice, seller_id=seller_id)

                # Log import event
                try:
                    from repositories.audit_repository import AuditRepository
                    from flask_login import current_user
                    uid = current_user.id if current_user.is_authenticated else None
                    uname = current_user.full_name if current_user.is_authenticated else None
                    AuditRepository().log_event(
                        entity_type='import', action='IMPORT',
                        entity_id=invoice_id,
                        entity_label=f"{invoice.invoice_number} — {invoice.seller_name}",
                        new_value=filename,
                        user_id=uid, user_name=uname,
                        invoice_id=invoice_id,
                    )
                except Exception:
                    pass

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
                # Rollback the aborted PostgreSQL transaction so the shared connection
                # is usable again for the next invoice in the batch.
                try:
                    DatabaseConnection.get_connection().rollback()
                except Exception:
                    pass

                error_msg = str(e)
                if "duplicate key value violates unique constraint" in error_msg:
                    error_msg = f"Duplikat numeru faktury: {invoice_number}"

                logger.error(f"[FINALIZE] Failed to save {filename}: {error_msg}")

                # Rollback file move if it happened
                if file_moved and os.path.exists(str(permanent_path)):
                    try:
                        shutil.move(str(permanent_path), temp_file_path)
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
                'error': f"Zapisano {len(saved_invoices)} faktur, wystapily bledy przy {len(failed_invoices)}."
            }
            # Include seller warnings if any
            if seller_warnings:
                response_data['seller_warnings'] = seller_warnings
            return jsonify(response_data)

    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in finalize_uploads')
        raise AppError('Blad podczas zapisywania faktur')


@upload_bp.route('/view-pdf/<filename>', methods=['GET'])
def view_pdf(filename: str):
    """View a staged PDF file"""
    try:
        session_id = get_session_id()

        # Get file from staging
        rows = current_app.staging_repo.get_by_session(session_id)

        upload_root = Path(current_app.config['UPLOAD_FOLDER']).resolve()
        for row in rows:
            if row['filename'] == filename:
                file_path = Path(row['file_path']).resolve()
                # P1-2: Validate path is within upload directory
                if not file_path.is_relative_to(upload_root):
                    logger.warning(f"Path traversal attempt: {file_path}")
                    raise ValidationError('Niedozwolona sciezka')
                if file_path.exists():
                    # P4-7: Serve with correct MIME type based on extension
                    mime_type = mimetypes.guess_type(str(file_path))[0] or 'application/pdf'
                    return send_file(str(file_path), mimetype=mime_type)

        raise NotFoundError('PDF nie istnieje')

    except AppError:
        raise
    except Exception as e:
        logging.exception('Unexpected error in view_pdf')
        raise AppError('Blad wyswietlania pliku')


# ── P4-3 & P4-4: Cleanup stale temp files and staging records ──

def cleanup_stale_uploads(app, max_age_hours: int = 24):
    """
    Remove temp upload files and staging DB records older than max_age_hours.
    Call from app startup or a scheduled task.
    """
    import time

    with app.app_context():
        temp_root = Path(app.config['UPLOAD_FOLDER']) / 'temp'
        if not temp_root.exists():
            return

        cutoff = time.time() - (max_age_hours * 3600)
        cleaned_dirs = 0

        for session_dir in temp_root.iterdir():
            if not session_dir.is_dir():
                continue
            # Check if directory is older than cutoff
            try:
                dir_mtime = session_dir.stat().st_mtime
                if dir_mtime < cutoff:
                    shutil.rmtree(session_dir, ignore_errors=True)
                    cleaned_dirs += 1
                    # Also clean staging records for this session
                    session_id = session_dir.name
                    try:
                        app.staging_repo.delete_by_session(session_id)
                    except Exception:
                        pass
            except OSError:
                continue

        if cleaned_dirs > 0:
            logger.info(f"[Cleanup] Removed {cleaned_dirs} stale upload session(s)")
