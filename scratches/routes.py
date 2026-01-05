"""
Document routes for document lifecycle management.

This module handles all document-related operations:
- Creating new documents
- Viewing documents
- Editing draft documents
- Submitting for review
- Reviewing documents
- Approving/Rejecting documents
- Document listing and search
"""

import io
import logging
from datetime import datetime

from app.blueprints.documents import documents_bp
from app.decorators import role_required
from app.extensions import db
from app.models import Document, Revision, User, DocumentType, Language
from app.services.file_service import FileService
from app.services.workflow_service import (
	WorkflowService,
	InvalidStateTransitionError,
	UnauthorizedActionError,
	FileValidationError,
	RevisionNumberError,
	RevisionCreationError
	)
from flask import render_template, redirect, url_for, flash, request, abort, \
	send_file, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

logger = logging.getLogger(__name__)


@documents_bp.route('/list')
@login_required
def list_documents():
    """
    List all documents visible to the current user.

    Filters documents based on user role:
    - VIEWER: Only approved documents
    - EDITOR/APPROVER: All documents with optional status filtering

    Supports pagination, search, multi-status filtering, and sorting.

    Returns:
        Rendered document list template
    """
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Get search parameters
    search_query = request.args.get('q', '')
    doc_type = request.args.get('type', '')

    # Get status filters (can be multiple)
    status_filters = request.args.getlist('status')

    # Get sorting parameters
    sort_by = request.args.get('sort_by', 'updated')  # document_number, title, type, status, updated
    sort_dir = request.args.get('sort_dir', 'desc')  # asc or desc

    # Build base query - join with ALL revisions to show full revision history
    query = db.session.query(Document).join(
        Revision,
        Document.id == Revision.document_id
    ).add_columns(Revision)

    # Apply search filters
    if search_query:
        query = query.filter(
            or_(
                Document.document_number.ilike(f'%{search_query}%'),
                Document.title.ilike(f'%{search_query}%')
            )
        )

    if doc_type:
        query = query.filter(Document.document_type == doc_type)

    # Apply status filters
    if status_filters:
        query = query.filter(Revision.status.in_(status_filters))

    # If VIEWER, only show documents with approved revisions
    if current_user.role == 'VIEWER':
        query = query.filter(Revision.status == 'APPROVED')

    # Apply sorting
    # Always group by document first, then sort revisions within each document
    if sort_by == 'document_number':
        if sort_dir == 'asc':
            query = query.order_by(Document.document_number.asc(), Revision.id.desc())
        else:
            query = query.order_by(Document.document_number.desc(), Revision.id.desc())
    elif sort_by == 'title':
        if sort_dir == 'asc':
            query = query.order_by(Document.title.asc(), Revision.id.desc())
        else:
            query = query.order_by(Document.title.desc(), Revision.id.desc())
    elif sort_by == 'type':
        if sort_dir == 'asc':
            query = query.order_by(Document.document_type.asc(), Revision.id.desc())
        else:
            query = query.order_by(Document.document_type.desc(), Revision.id.desc())
    elif sort_by == 'status':
        if sort_dir == 'asc':
            query = query.order_by(Revision.status.asc(), Document.document_number.asc(), Revision.id.desc())
        else:
            query = query.order_by(Revision.status.desc(), Document.document_number.asc(), Revision.id.desc())
    else:  # default: updated
        if sort_dir == 'asc':
            query = query.order_by(Document.updated_at.asc(), Revision.id.desc())
        else:
            query = query.order_by(Document.updated_at.desc(), Revision.id.desc())

    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # Extract Document and Revision pairs for each row
    documents = []
    for row in pagination.items:
        # SQLAlchemy returns Row objects when using add_columns
        doc = row[0]  # First column is the Document
        revision = row[1] if len(row) > 1 else None  # Second column is the Revision

        # Create a dictionary to keep document and revision separate for this row
        # This prevents the same document object from being overwritten
        documents.append({
            'doc': doc,
            'revision': revision
        })

    # Get available document types for filters
    doc_types = DocumentType.query.order_by(DocumentType.type_description).all()
    doc_type_descriptions = [dt.type_description for dt in doc_types]

    # Get available languages for filters
    all_languages = Language.query.order_by(Language.language_name).all()
    language_names = [lang.language_name for lang in all_languages]

    logger.info(f'Document list accessed by user {current_user.username}')

    return render_template(
        'documents/list.html',
        documents=documents,
        pagination=pagination,
        search_query=search_query,
        doc_types=doc_type_descriptions,
        languages=language_names,
        selected_type=doc_type,
        selected_statuses=status_filters,
        sort_by=sort_by,
        sort_dir=sort_dir
    )


@documents_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN', 'SUPERUSER')
def create_document():
    """
    Create a new document with initial revision.

    GET: Display document creation form
    POST: Process form and create document + initial revision

    Returns:
        Rendered form template or redirect to document view on success
    """
    if request.method == 'POST':
        # Get form data
        document_number = request.form.get('document_number')
        title = request.form.get('title')
        document_type_id = request.form.get('document_type')  # This is the type_id from the dropdown
        document_language_id = request.form.get('document_language')  # This is the language_id from the dropdown
        revision_number_str = request.form.get('revision_number', '1')
        revision_date_str = request.form.get('revision_date')
        revision_change_note = request.form.get('revision_change_note', '')

        # Get uploaded file
        file = request.files.get('document_file')

        # Get document types and languages for error re-rendering
        document_types = DocumentType.query.order_by(DocumentType.type_description).all()
        languages = Language.query.order_by(Language.language_name).all()

        # Validate required fields
        if not all([document_number, title, document_type_id, document_language_id, revision_date_str]):
            flash('All required fields must be filled.', 'error')
            return render_template('documents/create.html', document_types=document_types, languages=languages)

        # Validate file upload
        if not file or file.filename == '':
            flash('Please select a file to upload.', 'error')
            return render_template('documents/create.html', document_types=document_types)

        is_valid, error = FileService.validate_uploaded_file(file)
        if not is_valid:
            flash(f'File validation failed: {error}', 'error')
            return render_template('documents/create.html', document_types=document_types)

        # Parse and validate revision number
        try:
            revision_number = int(revision_number_str)
        except (ValueError, TypeError):
            flash('Revision number must be a valid integer.', 'error')
            return render_template('documents/create.html', document_types=document_types)

        # Validate revision number against latest approved revision
        try:
            WorkflowService.validate_revision_number(document_number, revision_number)
        except RevisionNumberError as e:
            flash(str(e), 'error')
            return render_template('documents/create.html', document_types=document_types)

        # Check if document number already exists
        existing_doc = Document.query.filter_by(document_number=document_number).first()

        # Extract file data
        file_data_dict = FileService.extract_file_data(file)

        # Parse revision date
        try:
            revision_date = datetime.strptime(revision_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid revision date format. Use YYYY-MM-DD.', 'error')
            return render_template('documents/create.html', document_types=document_types, languages=languages)

        try:
            if existing_doc:
                # Document exists - check if we can create a new revision
                can_create, error_msg = WorkflowService.can_create_new_revision(existing_doc)

                if not can_create:
                    flash(error_msg, 'error')
                    return render_template('documents/create.html', document_types=document_types)

                # Redirect to new_revision page with pre-filled data
                flash(
                    f'Document {document_number} already exists. Redirecting to create new revision...',
                    'info'
                )

                # Calculate suggested revision number
                suggested_revision = revision_number

                return redirect(url_for(
                    'documents.new_revision',
                    doc_id=existing_doc.id,
                    prefilled='true',
                    suggested_revision=suggested_revision
                ))

            else:
                # New document - create document and initial revision
                needs_translation = request.form.get('needs_translation') == 'on'
                
                document = Document(
                    document_number=document_number,
                    title=title,
                    document_type_id=int(document_type_id),  # Use the foreign key
                    document_language_id=int(document_language_id),  # Use the language foreign key
                    created_by=current_user.id,
                    needs_translation=needs_translation
                )
                db.session.add(document)
                db.session.flush()  # Get document ID

                # Create initial revision with file data
                revision = Revision(
                    document_id=document.id,
                    revision_number=revision_number,
                    revision_date=revision_date,
                    revision_change_note=revision_change_note,
                    status='DRAFT',
                    file_data=file_data_dict['file_data'],
                    file_name=file_data_dict['file_name'],
                    file_size=file_data_dict['file_size'],
                    mime_type=file_data_dict['mime_type'],
                    editor_id=current_user.id
                )
                db.session.add(revision)
                db.session.commit()

                logger.info(
                    f'Document {document_number} created by user {current_user.username}'
                )
                flash(f'Document {document_number} created successfully!', 'success')
                return redirect(url_for('documents.view_document', doc_id=document.id))

        except Exception as e:
            db.session.rollback()
            logger.error(f'Error creating document: {str(e)}')
            flash(f'Error creating document: {str(e)}', 'error')
            return render_template('documents/create.html')


    # GET request - show form
    document_types = DocumentType.query.order_by(DocumentType.type_description).all()
    languages = Language.query.order_by(Language.language_name).all()
    return render_template('documents/create.html', document_types=document_types, languages=languages)


@documents_bp.route('/<int:doc_id>')
@login_required
def view_document(doc_id: int):
    """
    View document details including current and all revisions.

    Args:
        doc_id: Document ID

    Returns:
        Rendered document view template
    """
    document = Document.query.get_or_404(doc_id)

    # Check if user has permission to view
    if current_user.role == 'VIEWER':
        # Viewers can only see approved documents
        if not document.current_revision or document.current_revision.status != 'APPROVED':
            flash('You do not have permission to view this document.', 'error')
            abort(403)

    # Get all revisions for this document
    revisions = Revision.query.filter_by(document_id=doc_id).order_by(
        Revision.created_at.desc()
    ).all()

    # Get available actions for current revision
    available_actions = []
    latest_revision = None
    if revisions:
        latest_revision = revisions[0]
        available_actions = WorkflowService.get_available_actions(latest_revision, current_user)

    logger.info(f'Document {document.document_number} viewed by user {current_user.username}')

    return render_template(
        'documents/view.html',
        document=document,
        revisions=revisions,
        latest_revision=latest_revision,
        available_actions=available_actions
    )


@documents_bp.route('/<int:doc_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def edit_document(doc_id: int):
    """
    Edit document metadata and current revision.

    Only the document creator can edit, and only if the current revision
    is in DRAFT or REJECTED status.

    Args:
        doc_id: Document ID

    Returns:
        Rendered edit form or redirect to document view on success
    """
    document = Document.query.get_or_404(doc_id)

    # Get the latest revision
    latest_revision = Revision.query.filter_by(document_id=doc_id).order_by(
        Revision.created_at.desc()
    ).first()

    if not latest_revision:
        flash('No revision found for this document.', 'error')
        abort(404)

    # Check if user is the editor
    if latest_revision.editor_id != current_user.id:
        flash('Only the document editor can edit this document.', 'error')
        abort(403)

    # Check if revision is editable
    if not latest_revision.is_editable():
        flash(f'Cannot edit document in {latest_revision.status} status.', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))

    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        document_type_id = request.form.get('document_type')  # This is the type_id from dropdown
        document_language_id = request.form.get('document_language')  # This is the language_id from dropdown
        revision_date_str = request.form.get('revision_date')
        revision_change_note = request.form.get('revision_change_note', '')

        # Get uploaded file (optional - if not provided, keep existing file)
        file = request.files.get('document_file')

        # Get document types and languages for error re-rendering
        document_types = DocumentType.query.order_by(DocumentType.type_description).all()
        languages = Language.query.order_by(Language.language_name).all()

        # Validate required fields
        if not all([title, document_type_id, document_language_id, revision_date_str]):
            flash('All required fields must be filled.', 'error')
            return render_template('documents/edit.html', document=document, revision=latest_revision, document_types=document_types, languages=languages)

        # Validate and process file if a new one is uploaded
        file_data_dict = None
        if file and file.filename != '':
            is_valid, error = FileService.validate_uploaded_file(file)
            if not is_valid:
                flash(f'File validation failed: {error}', 'error')
                return render_template('documents/edit.html', document=document, revision=latest_revision, document_types=document_types, languages=languages)
            file_data_dict = FileService.extract_file_data(file)

        # Parse revision date
        try:
            revision_date = datetime.strptime(revision_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid revision date format. Use YYYY-MM-DD.', 'error')
            return render_template('documents/edit.html', document=document, revision=latest_revision, document_types=document_types)

        try:
            # Update document
            document.title = title
            document.document_type_id = int(document_type_id)  # Use the foreign key
            document.document_language_id = int(document_language_id)  # Use the language foreign key
            
            # Note: needs_translation flag is NOT updated here during draft editing
            # It will only be updated when the revision is APPROVED
            # This preserves the flag state of previous approved revisions

            # Update revision
            latest_revision.revision_date = revision_date
            latest_revision.revision_change_note = revision_change_note

            # Update file data if new file was uploaded
            if file_data_dict:
                latest_revision.file_data = file_data_dict['file_data']
                latest_revision.file_name = file_data_dict['file_name']
                latest_revision.file_size = file_data_dict['file_size']
                latest_revision.mime_type = file_data_dict['mime_type']
                logger.info(f'File replaced for revision {latest_revision.id}: {file_data_dict["file_name"]}')

            db.session.commit()

            logger.info(
                f'Document {document.document_number} updated by user {current_user.username}'
            )
            flash('Document updated successfully!', 'success')
            return redirect(url_for('documents.view_document', doc_id=doc_id))

        except Exception as e:
            db.session.rollback()
            logger.error(f'Error updating document: {str(e)}')
            flash(f'Error updating document: {str(e)}', 'error')

    # GET request - show form
    document_types = DocumentType.query.order_by(DocumentType.type_description).all()
    languages = Language.query.order_by(Language.language_name).all()
    return render_template('documents/edit.html', document=document, revision=latest_revision, document_types=document_types, languages=languages)


@documents_bp.route('/revision/<int:revision_id>/submit', methods=['POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def submit_for_review(revision_id: int):
    """
    Submit a document revision for approval to a designated approver.

    Transitions revision from DRAFT to SUBMISSION.
    Requires a designated approver to be selected.

    Args:
        revision_id: Revision ID

    Returns:
        Redirect to document view
    """
    revision = Revision.query.get_or_404(revision_id)
    
    # Get designated approver from form
    designated_approver_id = request.form.get('designated_approver_id', type=int)
    
    if not designated_approver_id:
        flash('Please select an approver for this submission.', 'error')
        return redirect(url_for('documents.view_document', doc_id=revision.document_id))

    try:
        WorkflowService.transition_to_submission(revision, current_user, designated_approver_id)
        
        # Get approver name for the success message
        approver = User.query.get(designated_approver_id)
        approver_name = approver.username if approver else 'selected approver'
        
        flash(
            f'Document {revision.document.document_number} submitted for approval to {approver_name}!',
            'success'
        )
    except (InvalidStateTransitionError, UnauthorizedActionError, FileValidationError) as e:
        flash(str(e), 'error')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error(f'Error submitting document for review: {str(e)}')
        flash('An error occurred while submitting the document.', 'error')

    return redirect(url_for('documents.view_document', doc_id=revision.document_id))


@documents_bp.route('/revision/<int:revision_id>/review', methods=['GET', 'POST'])
@login_required
@role_required('APPROVER', 'ADMIN')
def review_document(revision_id: int):
    """
    Approve or reject a document revision.

    GET: Display approval page with document details
    POST: Process approval or rejection

    Args:
        revision_id: Revision ID

    Returns:
        Rendered review template or redirect on POST
    """
    revision = Revision.query.get_or_404(revision_id)

    # Check if revision can be approved
    if not revision.can_be_approved():
        flash(f'Document cannot be approved in {revision.status} status.', 'error')
        return redirect(url_for('documents.view_document', doc_id=revision.document_id))

    # Check if user is authorized to review this document
    if not current_user.has_role('ADMIN'):
        if revision.designated_approver_id and revision.designated_approver_id != current_user.id:
            flash('You are not the designated approver for this document.', 'error')
            return redirect(url_for('documents.view_document', doc_id=revision.document_id))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'approve':
            try:
                # Update needs_translation before approval based on reviewer's decision
                needs_translation_value = request.form.get('needs_translation')
                if needs_translation_value is not None:
                    revision.document.needs_translation = (needs_translation_value == 'yes')
                    db.session.flush()
                
                WorkflowService.transition_to_approved(revision, current_user)
                flash(
                    f'Document {revision.document.document_number} approved successfully!',
                    'success'
                )
                return redirect(url_for('documents.view_document', doc_id=revision.document_id))
            except (InvalidStateTransitionError, UnauthorizedActionError) as e:
                flash(str(e), 'error')

        elif action == 'reject':
            comment = request.form.get('comment')
            if not comment or comment.strip() == '':
                flash('Rejection comment is mandatory.', 'error')
                return render_template('documents/review.html', revision=revision)

            try:
                WorkflowService.transition_to_rejected(revision, current_user, comment)
                flash(
                    f'Document {revision.document.document_number} rejected. '
                    f'Editor has been notified.',
                    'info'
                )
                return redirect(url_for('documents.view_document', doc_id=revision.document_id))
            except (InvalidStateTransitionError, UnauthorizedActionError) as e:
                flash(str(e), 'error')

    # GET request - show review page
    return render_template('documents/review.html', revision=revision)


@documents_bp.route('/<int:doc_id>/new-revision', methods=['GET', 'POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def new_revision(doc_id: int):
    """
    Create a new revision for an existing document.

    Only allowed if:
    1. There are no pending revisions (DRAFT or SUBMISSION status)
    2. There is at least one APPROVED revision

    Args:
        doc_id: Document ID

    Query Parameters (optional):
        prefilled: If 'true', indicates form should be pre-filled
        suggested_revision: Suggested revision number to pre-fill

    Returns:
        Rendered form or redirect to view on success
    """
    document = Document.query.get_or_404(doc_id)

    # Check if new revision can be created using the workflow service
    can_create, error_message = WorkflowService.can_create_new_revision(document)
    if not can_create:
        # Check if this is a translation document and redirect to original if so
        if document.original_document_id:
            return redirect(url_for(
                'documents.view_document', 
                doc_id=document.original_document_id,
                highlight='create_revision',
                translation_doc_number=document.document_number
            ))
            
        flash(error_message, 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))

    # Calculate next revision number automatically
    next_revision_number = 1
    if document.current_revision:
        next_revision_number = document.current_revision.revision_number + 1

    # Get query parameters for pre-filling
    prefilled = request.args.get('prefilled', 'false') == 'true'
    suggested_revision = request.args.get('suggested_revision', str(next_revision_number))

    if request.method == 'POST':
        # Get form data
        revision_number_str = request.form.get('revision_number')
        revision_date_str = request.form.get('revision_date')
        revision_change_note = request.form.get('revision_change_note', '')

        # Get uploaded file
        file = request.files.get('document_file')

        # Validate required fields
        if not all([revision_number_str, revision_date_str]):
            flash('All required fields must be filled.', 'error')
            languages = Language.query.order_by(Language.language_name).all()
            return render_template('documents/new_revision.html', document=document, languages=languages)

        # Validate file upload
        if not file or file.filename == '':
            flash('Please select a file to upload.', 'error')
            languages = Language.query.order_by(Language.language_name).all()
            return render_template('documents/new_revision.html', document=document, languages=languages)

        is_valid, error = FileService.validate_uploaded_file(file)
        if not is_valid:
            flash(f'File validation failed: {error}', 'error')
            languages = Language.query.order_by(Language.language_name).all()
            return render_template('documents/new_revision.html', document=document, languages=languages)

        # Parse and validate revision number
        try:
            revision_number = int(revision_number_str)
        except (ValueError, TypeError):
            flash('Revision number must be a valid integer.', 'error')
            languages = Language.query.order_by(Language.language_name).all()
            return render_template('documents/new_revision.html', document=document, languages=languages)

        # Validate revision number against latest approved revision
        try:
            WorkflowService.validate_revision_number(document.document_number, revision_number)
        except RevisionNumberError as e:
            flash(str(e), 'error')
            languages = Language.query.order_by(Language.language_name).all()
            return render_template('documents/new_revision.html', document=document, languages=languages)

        # Extract file data
        file_data_dict = FileService.extract_file_data(file)

        # Parse revision date
        try:
            revision_date = datetime.strptime(revision_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid revision date format. Use YYYY-MM-DD.', 'error')
            languages = Language.query.order_by(Language.language_name).all()
            return render_template('documents/new_revision.html', document=document, languages=languages)

        try:
            # Note: needs_translation flag is NOT updated here during draft creation
            # It will only be updated when this revision is APPROVED
            # This preserves the flag state of previous approved revisions
            
            # Update language if provided
            document_language_id = request.form.get('document_language')
            if document_language_id:
                document.document_language_id = int(document_language_id)
            
            # Create new revision with file data
            revision = Revision(
                document_id=document.id,
                revision_number=revision_number,
                revision_date=revision_date,
                revision_change_note=revision_change_note,
                status='DRAFT',
                file_data=file_data_dict['file_data'],
                file_name=file_data_dict['file_name'],
                file_size=file_data_dict['file_size'],
                mime_type=file_data_dict['mime_type'],
                editor_id=current_user.id
            )
            db.session.add(revision)
            db.session.commit()

            logger.info(
                f'New revision {revision_number} created for document {document.document_number} '
                f'by user {current_user.username}'
            )
            flash(f'New revision {revision_number} created successfully!', 'success')
            return redirect(url_for('documents.view_document', doc_id=doc_id))

        except Exception as e:
            db.session.rollback()
            logger.error(f'Error creating new revision: {str(e)}')
            flash(f'Error creating new revision: {str(e)}', 'error')

    # GET request - show form
    languages = Language.query.order_by(Language.language_name).all()
    return render_template(
        'documents/new_revision.html',
        document=document,
        prefilled=prefilled,
        next_revision_number=next_revision_number,
        languages=languages
    )


@documents_bp.route('/revision/<int:revision_id>/download')
@login_required
def download_file(revision_id: int):
    """
    Download file attached to a revision.

    Args:
        revision_id: Revision ID

    Returns:
        File download response
    """
    revision = Revision.query.get_or_404(revision_id)

    # Check if user has permission to view this document
    if current_user.role == 'VIEWER':
        # Viewers can only download approved documents
        if revision.status != 'APPROVED':
            flash('You do not have permission to download this file.', 'error')
            abort(403)

    # Check if file data exists
    if not revision.file_data:
        flash('No file attached to this revision.', 'error')
        abort(404)

    logger.info(
        f'File download: {revision.file_name} by user {current_user.username}'
    )

    # Send file from database
    return send_file(
        io.BytesIO(revision.file_data),
        mimetype=revision.mime_type,
        as_attachment=True,
        download_name=revision.file_name
    )


@documents_bp.route('/revision/<int:revision_id>/view')
@login_required
def view_file(revision_id: int):
    """
    View file attached to a revision inline (e.g., PDF in browser).

    Args:
        revision_id: Revision ID

    Returns:
        File view response
    """
    revision = Revision.query.get_or_404(revision_id)

    # Check if user has permission to view this document
    if current_user.role == 'VIEWER':
        # Viewers can only view approved documents
        if revision.status != 'APPROVED':
            flash('You do not have permission to view this file.', 'error')
            abort(403)

    # Check if file data exists
    if not revision.file_data:
        flash('No file attached to this revision.', 'error')
        abort(404)

    logger.info(
        f'File view: {revision.file_name} by user {current_user.username}'
    )

    # Send file for inline viewing (as_attachment=False)
    return send_file(
        io.BytesIO(revision.file_data),
        mimetype=revision.mime_type,
        as_attachment=False,
        download_name=revision.file_name
    )


@documents_bp.route('/api/check-document-number/<document_number>')
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def check_document_number(document_number: str):
    """
    API endpoint to check if a document number already exists.

    Args:
        document_number: Document number to check

    Returns:
        JSON response with document existence and details
    """
    existing_doc = Document.query.filter_by(document_number=document_number).first()

    if existing_doc:
        # Check if new revision can be created
        can_create, error_msg = WorkflowService.can_create_new_revision(existing_doc)

        # Get the next suggested revision number
        next_revision = 1
        if existing_doc.current_revision:
            next_revision = existing_doc.current_revision.revision_number + 1

        return jsonify({
            'exists': True,
            'document_id': existing_doc.id,
            'title': existing_doc.title,
            'document_type': existing_doc.document_type,
            'current_revision': existing_doc.current_revision.revision_number if existing_doc.current_revision else None,
            'current_status': existing_doc.current_revision.status if existing_doc.current_revision else None,
            'next_revision': next_revision,
            'is_approved': existing_doc.current_revision.status == 'APPROVED' if existing_doc.current_revision else False,
            'can_create_revision': can_create,
            'error_message': error_msg
        })
    else:
        return jsonify({
            'exists': False
        })


@documents_bp.route('/api/approvers')
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def get_approvers():
    """
    API endpoint to get list of available approvers.
    
    Returns users with APPROVER or ADMIN role who are active.
    Used for the designated approver dropdown in submission forms.

    Returns:
        JSON array of approver objects with id, username, email, and role
    """
    approvers = User.query.filter(
        User.role.in_(['APPROVER', 'ADMIN']),
        User.is_active == True
    ).order_by(User.username).all()
    
    return jsonify([{
        'id': a.id,
        'username': a.username,
        'email': a.email,
        'role': a.role
    } for a in approvers])

@documents_bp.route('/<int:doc_id>/delete', methods=['POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def delete_document(doc_id: int):
    """
    Delete a document and all its revisions.

    Access control:
    - ADMIN: Can delete any document
    - EDITOR/APPROVER: Can only delete their own DRAFT documents

    Args:
        doc_id: Document ID

    Returns:
        Redirect to documents list
    """
    document = Document.query.get_or_404(doc_id)

    # Get latest revision to check status
    latest_revision = Revision.query.filter_by(document_id=doc_id).order_by(
        Revision.created_at.desc()
    ).first()

    # Check permissions
    if current_user.role != 'ADMIN':
        # Non-admin users can only delete their own documents
        if document.created_by != current_user.id:
            flash('You can only delete documents you created.', 'error')
            abort(403)
        
        # Can only delete if latest revision is DRAFT
        if latest_revision and latest_revision.status != 'DRAFT':
            flash(f'Cannot delete document with status {latest_revision.status}. Only DRAFT documents can be deleted.', 'error')
            return redirect(url_for('documents.view_document', doc_id=doc_id))

    document_number = document.document_number

    try:
        # Check if this document has a translation and delete it first
        if document.translated_document_id:
            translated_doc = Document.query.get(document.translated_document_id)
            if translated_doc:
                translated_doc_number = translated_doc.document_number
                
                # Break the circular reference before deleting
                # Set both foreign keys to None to avoid circular dependency
                document.translated_document_id = None
                translated_doc.original_document_id = None
                db.session.flush()  # Ensure the changes are processed
                
                # Delete all revisions of the translation
                for revision in translated_doc.revisions:
                    db.session.delete(revision)
                # Delete the translation document
                db.session.delete(translated_doc)
                logger.info(f'Translation document {translated_doc_number} deleted along with original {document_number}')
        
        # Delete document (revisions will be cascade deleted due to relationship)
        db.session.delete(document)
        db.session.commit()

        logger.info(f'Document {document_number} deleted by user {current_user.username}')
        flash(f'Document "{document_number}" and all its revisions have been permanently deleted.', 'success')
        return redirect(url_for('documents.list_documents'))

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting document: {str(e)}')
        flash(f'Error deleting document: {str(e)}', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))


@documents_bp.route('/revision/<int:revision_id>/cancel-review', methods=['POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def cancel_review_request(revision_id: int):
    """
    Cancel a review request and return revision to DRAFT status.

    Only the editor who created the revision can cancel the review.
    Can only cancel if status is SUBMISSION.

    Args:
        revision_id: Revision ID

    Returns:
        Redirect to document view
    """
    revision = Revision.query.get_or_404(revision_id)

    # Check if user is the editor
    if revision.editor_id != current_user.id and current_user.role != 'ADMIN':
        flash('Only the document editor can cancel the review request.', 'error')
        abort(403)

    # Check if status is SUBMISSION
    if revision.status != 'SUBMISSION':
        flash(f'Cannot cancel review for revision with status {revision.status}.', 'error')
        return redirect(url_for('documents.view_document', doc_id=revision.document_id))

    try:
        # Change status back to DRAFT
        revision.status = 'DRAFT'
        revision.submitted_at = None
        db.session.commit()

        logger.info(
            f'Review cancelled for document {revision.document.document_number} '
            f'revision {revision.revision_number} by user {current_user.username}'
        )
        flash('Review request cancelled. Document returned to DRAFT status.', 'success')
        return redirect(url_for('documents.view_document', doc_id=revision.document_id))

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error cancelling review: {str(e)}')
        flash(f'Error cancelling review: {str(e)}', 'error')
        return redirect(url_for('documents.view_document', doc_id=revision.document_id))


@documents_bp.route('/revision/<int:revision_id>/delete', methods=['POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def delete_revision(revision_id: int):
    """
    Delete a specific revision.

    Access control:
    - ADMIN: Can delete any DRAFT revision
    - EDITOR/APPROVER: Can only delete their own DRAFT revisions

    Args:
        revision_id: Revision ID

    Returns:
        Redirect to document view or list
    """
    revision = Revision.query.get_or_404(revision_id)
    document = revision.document

    # Check if revision is DRAFT
    if revision.status != 'DRAFT':
        flash(f'Cannot delete revision with status {revision.status}. Only DRAFT revisions can be deleted.', 'error')
        return redirect(url_for('documents.view_document', doc_id=document.id))

    # Check permissions
    if current_user.role != 'ADMIN':
        # Non-admin users can only delete their own revisions
        if revision.editor_id != current_user.id:
            flash('You can only delete revisions you created.', 'error')
            abort(403)

    revision_number = revision.revision_number
    document_number = document.document_number
    document_id = document.id

    # Check if this is the current revision
    is_current = document.current_revision_id == revision_id

    # Check if this is the only revision
    total_revisions = Revision.query.filter_by(document_id=document.id).count()

    if total_revisions == 1:
        # This is the only revision - delete the entire document
        try:
            db.session.delete(document)
            db.session.commit()
            logger.info(
                f'Last revision deleted, document {document_number} removed by user {current_user.username}'
            )
            flash(
                f'Revision {revision_number} was the only revision. '
                f'Document "{document_number}" has been deleted.', 
                'success'
            )
            return redirect(url_for('documents.list_documents'))
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error deleting document: {str(e)}')
            flash(f'Error deleting document: {str(e)}', 'error')
            return redirect(url_for('documents.view_document', doc_id=document_id))

    try:
        # Delete the revision
        db.session.delete(revision)
        
        # If this was the current revision, update to the latest approved revision
        if is_current:
            latest_approved = Revision.query.filter_by(
                document_id=document.id,
                status='APPROVED'
            ).order_by(Revision.revision_number.desc()).first()
            
            document.current_revision_id = latest_approved.id if latest_approved else None
        
        db.session.commit()

        logger.info(
            f'Revision {revision_number} of document {document_number} '
            f'deleted by user {current_user.username}'
        )
        flash(f'Revision {revision_number} has been permanently deleted.', 'success')
        return redirect(url_for('documents.view_document', doc_id=document_id))

    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting revision: {str(e)}')
        flash(f'Error deleting revision: {str(e)}', 'error')
        return redirect(url_for('documents.view_document', doc_id=document_id))


@documents_bp.route('/revision/<int:revision_id>/cancel-approval', methods=['POST'])
@login_required
@role_required('APPROVER', 'ADMIN')
def cancel_approval(revision_id: int):
    """
    Cancel approval for a revision and restore the previous approved revision.
    
    This action:
    1. Sets the specified revision back to DRAFT status
    2. Sets the previous approved revision as the current valid revision
    
    Access control:
    - ADMIN and APPROVER only
    - Only allowed if there is more than one revision
    
    Args:
        revision_id: Revision ID to cancel approval for
    
    Returns:
        Redirect to document view
    """
    revision = Revision.query.get_or_404(revision_id)
    document = revision.document
    
    # Check if revision is currently approved
    if revision.status != 'APPROVED':
        flash(f'Cannot cancel approval for revision with status {revision.status}. Only APPROVED revisions can be cancelled.', 'error')
        return redirect(url_for('documents.view_document', doc_id=document.id))
    
    # Check if there are at least 2 revisions
    total_revisions = Revision.query.filter_by(document_id=document.id).count()
    if total_revisions < 2:
        flash('Cannot cancel approval. This is the only revision. Please delete the document instead.', 'error')
        return redirect(url_for('documents.view_document', doc_id=document.id))
    
    try:
        # Find the previous approved revision (by revision number)
        previous_approved = Revision.query.filter_by(
            document_id=document.id,
            status='APPROVED'
        ).filter(
            Revision.revision_number < revision.revision_number
        ).order_by(Revision.revision_number.desc()).first()
        
        if not previous_approved:
            flash('Cannot cancel approval. No previous approved revision found to restore.', 'error')
            return redirect(url_for('documents.view_document', doc_id=document.id))
        
        # Revert the current revision to DRAFT
        revision.status = 'DRAFT'
        revision.approved_at = None
        revision.approver_id = None
        revision.approval_comment = None
        
        # Set the previous approved revision as current
        document.current_revision_id = previous_approved.id
        
        db.session.commit()
        
        logger.info(
            f'Approval cancelled for document {document.document_number} '
            f'revision {revision.revision_number} by user {current_user.username}. '
            f'Restored to revision {previous_approved.revision_number}'
        )
        flash(
            f'Approval cancelled. Revision {revision.revision_number} returned to DRAFT. '
            f'Current valid revision is now {previous_approved.revision_number}.', 
            'success'
        )
        return redirect(url_for('documents.view_document', doc_id=document.id))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error cancelling approval: {str(e)}')
        flash(f'Error cancelling approval: {str(e)}', 'error')
        return redirect(url_for('documents.view_document', doc_id=document.id))


@documents_bp.route('/<int:doc_id>/create-translation', methods=['POST'])
@login_required
@role_required('APPROVER', 'ADMIN')
def create_translation(doc_id: int):
    """
    Redirect to translation file upload form.
    
    This does NOT create a database record yet - the translation will be
    created only when the file is actually uploaded.
    
    Access control:
    - APPROVER and ADMIN only
    
    Args:
        doc_id: Original document ID
    
    Returns:
        Redirect to translation file upload page
    """
    from app.services.translation_service import TranslationService, TranslationError
    
    document = Document.query.get_or_404(doc_id)
    
    # Validate that translation can be created (but don't create it yet)
    try:
        # Check if document can have a translation
        if not document.needs_translation:
            flash('This document is not marked as needing translation.', 'error')
            return redirect(url_for('documents.view_document', doc_id=doc_id))
        
        if document.translated_document_id:
            flash('This document already has a translation.', 'error')
            return redirect(url_for('documents.view_document', doc_id=doc_id))
        
        if not document.current_revision or document.current_revision.status != 'APPROVED':
            flash('Document must have an approved revision before creating translation.', 'error')
            return redirect(url_for('documents.view_document', doc_id=doc_id))
        
        # Redirect to upload form with original_doc_id parameter
        return redirect(url_for('documents.upload_translation_file', original_doc_id=doc_id))
    
    except Exception as e:
        logger.error(f'Error initiating translation: {str(e)}')
        flash('An error occurred while initiating the translation.', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))


@documents_bp.route('/upload-translation', methods=['GET', 'POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def upload_translation_file():
    """
    Upload translated file to complete translation workflow.
    
    GET: Display upload form
    POST: Create translation document and upload file in single transaction
    
    Query Parameters:
        original_doc_id: Original document ID (for new translations)
        doc_id: Translation document ID (for existing incomplete translations - legacy support)
    
    Returns:
        Rendered upload form or redirect on success
    """
    from app.services.translation_service import TranslationService, TranslationError
    
    # Get parameters - either original_doc_id (new translation) or doc_id (existing)
    original_doc_id = request.args.get('original_doc_id', type=int)
    doc_id = request.args.get('doc_id', type=int)
    
    # Determine if this is a new translation or completing an existing one
    if original_doc_id:
        # New translation workflow
        original_document = Document.query.get_or_404(original_doc_id)
        document = None  # Will be created during POST
        is_new_translation = True
    elif doc_id:
        # Existing incomplete translation (legacy support)
        document = Document.query.get_or_404(doc_id)
        
        # Validate this is a translation document
        can_upload, error_msg = TranslationService.can_upload_translation_file(document, current_user)
        if not can_upload:
            flash(error_msg, 'error')
            return redirect(url_for('documents.view_document', doc_id=doc_id))
        
        original_document = document.original_document
        if not original_document:
            flash('Original document not found.', 'error')
            abort(404)
        is_new_translation = False
    else:
        flash('Missing document identifier.', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        # Get form data
        revision_number_str = request.form.get('revision_number', '1')
        revision_date_str = request.form.get('revision_date')
        translation_language_id = request.form.get('translation_language')
        confirmed = request.form.get('confirm_translation') == 'on'
        
        # Get languages for error rendering
        languages = Language.query.order_by(Language.language_name).all()
        suggested_revision = 1
        if original_document.current_revision:
            suggested_revision = original_document.current_revision.revision_number
        
        # Validate translation language selection
        if not translation_language_id:
            flash('Please select a translation language.', 'error')
            return render_template('documents/upload_translation.html',
                                   document=document,
                                   original=original_document,
                                   languages=languages,
                                   suggested_revision=suggested_revision,
                                   is_new=is_new_translation)
        
        # Validate translation language is different from original
        if str(original_document.document_language_id) == str(translation_language_id):
            flash('Translation language must be different from the original document language.', 'error')
            return render_template('documents/upload_translation.html',
                                   document=document,
                                   original=original_document,
                                   languages=languages,
                                   suggested_revision=suggested_revision,
                                   is_new=is_new_translation)
        
        # Get language objects for change note generation
        original_lang = Language.query.get(original_document.document_language_id)
        translation_lang = Language.query.get(translation_language_id)
        
        # Auto-generate change note
        if original_lang and translation_lang:
            revision_change_note = f"Translation from {original_lang.language_name} to {translation_lang.language_name}"
        else:
            revision_change_note = "Translation uploaded"
        
        # Get uploaded file
        file = request.files.get('document_file')
        
        # Validate confirmation
        if not confirmed:
            flash('Please confirm that the uploaded file is the translated version.', 'error')
            return render_template('documents/upload_translation.html', 
                                   document=document, 
                                   original=original_document,
                                   languages=languages,
                                   suggested_revision=suggested_revision,
                                   is_new=is_new_translation)
        
        # Validate file upload
        if not file or file.filename == '':
            flash('Please select a file to upload.', 'error')
            return render_template('documents/upload_translation.html',
                                   document=document,
                                   original=original_document,
                                   languages=languages,
                                   suggested_revision=suggested_revision,
                                   is_new=is_new_translation)
        
        is_valid, error = FileService.validate_uploaded_file(file)
        if not is_valid:
            flash(f'File validation failed: {error}', 'error')
            return render_template('documents/upload_translation.html',
                                   document=document,
                                   original=original_document,
                                   languages=languages,
                                   suggested_revision=suggested_revision,
                                   is_new=is_new_translation)
        
        # Parse revision number
        try:
            revision_number = int(revision_number_str)
        except (ValueError, TypeError):
            flash('Revision number must be a valid integer.', 'error')
            return render_template('documents/upload_translation.html',
                                   document=document,
                                   original=original_document,
                                   languages=languages,
                                   suggested_revision=suggested_revision,
                                   is_new=is_new_translation)
        
        # Extract file data
        file_data_dict = FileService.extract_file_data(file)
        
        # Parse revision date
        try:
            revision_date = datetime.strptime(revision_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Invalid revision date format. Use YYYY-MM-DD.', 'error')
            return render_template('documents/upload_translation.html',
                                   document=document,
                                   original=original_document,
                                   languages=languages,
                                   suggested_revision=suggested_revision,
                                   is_new=is_new_translation)
        
        try:
            # If this is a NEW translation, create the document first
            if is_new_translation:
                translation_doc = TranslationService.create_translation_document(original_document, current_user)
                translation_doc.document_language_id = int(translation_language_id)
                db.session.flush()
            else:
                # Existing translation - just update language
                translation_doc = document
                translation_doc.document_language_id = int(translation_language_id)
                db.session.flush()
            
            # Complete the translation with file upload
            TranslationService.complete_translation(
                translation_doc,
                file_data_dict,
                revision_number,
                revision_date,
                revision_change_note,
                current_user
            )
            
            flash(
                f'Translation completed successfully! Original document '
                f'{original_document.document_number} updated.',
                'success'
            )
            return redirect(url_for('documents.view_document', doc_id=translation_doc.id))
        
        except TranslationError as e:
            db.session.rollback()
            flash(str(e), 'error')
            return render_template('documents/upload_translation.html',
                                   document=document,
                                   original=original_document,
                                   languages=languages,
                                   suggested_revision=suggested_revision,
                                   is_new=is_new_translation)
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error uploading translation file: {str(e)}')
            flash('An error occurred while uploading the translation.', 'error')
            return render_template('documents/upload_translation.html',
                                   document=document,
                                   original=original_document,
                                   languages=languages,
                                   suggested_revision=suggested_revision,
                                   is_new=is_new_translation)
    
    # GET request - show upload form
    # Suggest same revision number as original
    suggested_revision = 1
    if original_document.current_revision:
        suggested_revision = original_document.current_revision.revision_number
    
    # Get all languages for dropdown
    languages = Language.query.order_by(Language.language_name).all()
    
    return render_template(
        'documents/upload_translation.html',
        document=document,
        original=original_document,
        suggested_revision=suggested_revision,
        languages=languages,
        is_new=is_new_translation
    )


@documents_bp.route('/<int:doc_id>/delete-translation', methods=['POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def delete_translation(doc_id: int):
    """
    Delete a translation document.
    
    When deleted, the original document's needs_translation flag is set back to True.
    
    Access control:
    - ADMIN: Can delete any translation
    - Others: Can only delete translations they created
    
    Args:
        doc_id: Translation document ID
    
    Returns:
        Redirect to original document view or documents list
    """
    document = Document.query.get_or_404(doc_id)
    
    # Verify this is a translation document
    if not document.original_document_id:
        flash('This is not a translation document.', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    # Check permission: admin can delete any, others can only delete their own
    if current_user.role != 'ADMIN' and document.created_by != current_user.id:
        flash('You can only delete translations that you created.', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    original_doc_id = document.original_document_id
    original_document = Document.query.get(original_doc_id)
    translation_doc_number = document.document_number
    
    try:
        # Delete all revisions
        for revision in document.revisions:
            db.session.delete(revision)
        
        # Reset original document's needs_translation to True
        if original_document:
            original_document.needs_translation = True
            original_document.translation_status = None
            original_document.translated_document_id = None
        
        # Delete the translation document
        db.session.delete(document)
        db.session.commit()
        
        logger.info(
            f'Translation document {translation_doc_number} deleted by user {current_user.username}'
        )
        flash(f'Translation document {translation_doc_number} has been deleted.', 'success')
        
        # Redirect to original document if it exists, otherwise to list
        if original_document:
            return redirect(url_for('documents.view_document', doc_id=original_doc_id))
        else:
            return redirect(url_for('documents.list_documents'))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f'Error deleting translation: {str(e)}')
        flash(f'Error deleting translation: {str(e)}', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))


@documents_bp.route('/<int:doc_id>/edit-translation', methods=['GET', 'POST'])
@login_required
@role_required('EDITOR', 'APPROVER', 'ADMIN')
def edit_translation(doc_id: int):
    """
    Edit a translation document.
    
    Allows editing of:
    - Document file (replace)
    - Change note
    - Language
    
    Access control:
    - ADMIN: Can edit any translation
    - Others: Can only edit translations they created
    
    Args:
        doc_id: Translation document ID
    
    Returns:
        Rendered edit form or redirect on success
    """
    document = Document.query.get_or_404(doc_id)
    
    # Verify this is a translation document
    if not document.original_document_id:
        flash('This is not a translation document.', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    # Check permission: admin can edit any, others can only edit their own
    if current_user.role != 'ADMIN' and document.created_by != current_user.id:
        flash('You can only edit translations that you created.', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    # Get the latest revision
    latest_revision = document.revisions.order_by(Revision.revision_number.desc()).first()
    if not latest_revision:
        flash('No revision found for this translation.', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    original_document = Document.query.get(document.original_document_id)
    
    if request.method == 'POST':
        # Get form data
        revision_change_note = request.form.get('revision_change_note', '')
        document_language_id = request.form.get('document_language')
        
        # Get uploaded file (optional)
        file = request.files.get('document_file')
        
        # Get languages for error re-rendering
        languages = Language.query.order_by(Language.language_name).all()
        
        # Validate translation language selection
        if not document_language_id:
            flash('Please select a translation language.', 'error')
            return render_template('documents/edit_translation.html',
                                   document=document,
                                   revision=latest_revision,
                                   original=original_document,
                                   languages=languages)
        
        # Validate translation language is different from original
        if str(original_document.document_language_id) == str(document_language_id):
            flash('Translation language must be different from the original document language.', 'error')
            return render_template('documents/edit_translation.html',
                                   document=document,
                                   revision=latest_revision,
                                   original=original_document,
                                   languages=languages)
        
        # Validate and process file if a new one is uploaded
        file_data_dict = None
        if file and file.filename != '':
            is_valid, error = FileService.validate_uploaded_file(file)
            if not is_valid:
                flash(f'File validation failed: {error}', 'error')
                return render_template('documents/edit_translation.html',
                                       document=document,
                                       revision=latest_revision,
                                       original=original_document,
                                       languages=languages)
            file_data_dict = FileService.extract_file_data(file)
        
        try:
            # Check if language was changed from the ORIGINAL document language
            # The change note should always reflect: "Translation from [Original] to [New]"
            new_language_id = int(document_language_id)
            
            # Check if the new language is different from what's currently set on the translation document
            # OR if it's different from the original (which it should be based on earlier validation)
            language_changed = str(document.document_language_id) != str(new_language_id)
            
            if language_changed:
                # Get language objects for change note generation
                # Always use the ORIGINAL document's language as the "from" language
                original_lang = Language.query.get(original_document.document_language_id)
                translation_lang = Language.query.get(new_language_id)
                
                # Auto-generate change note
                if original_lang and translation_lang:
                    revision_change_note = f"Translation from {original_lang.language_name} to {translation_lang.language_name}"
                else:
                    revision_change_note = "Translation language updated"
            # If language didn't change, keep the existing change note from the form
            # (user might have manually edited it)
            
            # Update language
            document.document_language_id = new_language_id
            
            # Update revision change note
            # If language changed, use auto-generated note; otherwise use what user typed
            if language_changed:
                latest_revision.revision_change_note = revision_change_note
            else:
                # Keep the note from the form (user might have manually edited it)
                latest_revision.revision_change_note = request.form.get('revision_change_note', '')
            
            # Update file data if new file was uploaded
            if file_data_dict:
                latest_revision.file_data = file_data_dict['file_data']
                latest_revision.file_name = file_data_dict['file_name']
                latest_revision.file_size = file_data_dict['file_size']
                latest_revision.mime_type = file_data_dict['mime_type']
            
            db.session.commit()
            
            logger.info(
                f'Translation document {document.document_number} updated by user {current_user.username}'
            )
            flash('Translation updated successfully!', 'success')
            return redirect(url_for('documents.view_document', doc_id=doc_id))
        
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error updating translation: {str(e)}')
            flash(f'Error updating translation: {str(e)}', 'error')
    
    # GET request - show form
    languages = Language.query.order_by(Language.language_name).all()
    return render_template(
        'documents/edit_translation.html',
        document=document,
        revision=latest_revision,
        original=original_document,
        languages=languages
    )


@documents_bp.route('/<int:doc_id>/superedit', methods=['GET', 'POST'])
@login_required
def superedit_document(doc_id: int):
    """
    Super edit view for SUPERUSER role.
    Allows editing of system fields including timestamps and user assignments.
    
    Access: SUPERUSER only
    
    Args:
        doc_id: Document ID
        
    Returns:
        Rendered superedit form or redirect on success
    """
    # Check permission - SUPERUSER only
    if current_user.role != 'SUPERUSER':
        flash('Access denied. SUPERUSER role required.', 'error')
        return redirect(url_for('documents.list_documents'))
    
    # Block editing of translation documents
    document = Document.query.get_or_404(doc_id)
    if document.original_document_id:
        flash('Cannot super-edit translation documents.', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    # Get latest revision
    latest_revision = document.revisions.order_by(Revision.created_at.desc()).first()
    if not latest_revision:
        flash('No revision found for this document.', 'error')
        return redirect(url_for('documents.view_document', doc_id=doc_id))
    
    if request.method == 'POST':
        try:
            # Standard editable fields
            document.title = request.form.get('title')
            document.document_type_id = request.form.get('document_type')
            document.document_language_id = request.form.get('document_language')
            document.needs_translation = request.form.get('needs_translation') == 'on'
            
            # Revision fields
            revision_date_str = request.form.get('revision_date')
            if revision_date_str:
                latest_revision.revision_date = datetime.strptime(revision_date_str, '%Y-%m-%d').date()
            
            latest_revision.revision_change_note = request.form.get('revision_change_note')
            
            # Handle file upload if provided
            file = request.files.get('document_file')
            if file and file.filename != '':
                is_valid, error = FileService.validate_uploaded_file(file)
                if not is_valid:
                    flash(f'File validation failed: {error}', 'error')
                    return redirect(url_for('documents.superedit_document', doc_id=doc_id))
                
                file_data_dict = FileService.extract_file_data(file)
                latest_revision.file_data = file_data_dict['file_data']
                latest_revision.file_name = file_data_dict['file_name']
                latest_revision.file_size = file_data_dict['file_size']
                latest_revision.mime_type = file_data_dict['mime_type']
            
            # SYSTEM FIELDS (SUPERUSER only)
            # Document timestamps
            created_at_str = request.form.get('created_at')
            if created_at_str:
                document.created_at = datetime.strptime(created_at_str, '%Y-%m-%dT%H:%M')
            
            updated_at_str = request.form.get('updated_at')
            if updated_at_str:
                document.updated_at = datetime.strptime(updated_at_str, '%Y-%m-%dT%H:%M')
            
            # Document creator
            created_by_id = request.form.get('created_by')
            if created_by_id:
                document.created_by = int(created_by_id)
            
            # Revision fields
            editor_id = request.form.get('editor_id')
            if editor_id:
                latest_revision.editor_id = int(editor_id)
            
            designated_approver_id = request.form.get('designated_approver_id')
            if designated_approver_id and designated_approver_id != '':
                latest_revision.designated_approver_id = int(designated_approver_id)
            else:
                latest_revision.designated_approver_id = None
            
            submitted_at_str = request.form.get('submitted_at')
            if submitted_at_str and submitted_at_str != '':
                latest_revision.submitted_at = datetime.strptime(submitted_at_str, '%Y-%m-%dT%H:%M')
            else:
                latest_revision.submitted_at = None
            
            db.session.commit()
            
            logger.warning(
                f'SUPERUSER EDIT: Document {document.document_number} super-edited by user {current_user.username}. '
                f'System fields may have been modified.'
            )
            flash('Document super-edited successfully! System fields updated.', 'success')
            return redirect(url_for('documents.view_document', doc_id=document.id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error in superedit: {str(e)}')
            flash(f'Error: {str(e)}', 'error')
            return redirect(url_for('documents.superedit_document', doc_id=doc_id))
    
    # GET: Load form data
    # Get all users for dropdowns
    all_users = User.query.filter_by(is_active=True).order_by(User.username).all()
    
    # Get approvers for designated approver dropdown
    approvers = User.query.filter(
        User.is_active == True,
        User.role.in_(['APPROVER', 'ADMIN', 'SUPERUSER'])
    ).order_by(User.username).all()
    
    # Get document types and languages
    document_types = DocumentType.query.order_by(DocumentType.type_description).all()
    languages = Language.query.order_by(Language.language_name).all()
    
    return render_template(
        'documents/superedit.html',
        document=document,
        revision=latest_revision,
        document_types=document_types,
        languages=languages,
        all_users=all_users,
        approvers=approvers
    )
