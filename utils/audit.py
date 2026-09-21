"""Shared helper for route-level audit logging with the current Flask-Login user."""
from flask_login import current_user

from repositories.audit_repository import AuditRepository


def audit_event(entity_type, action, entity_id=None, entity_label=None,
                field_name=None, old_value=None, new_value=None):
    """Log a non-critical audit event attributed to the logged-in user.

    Uses safe_log_event so a failed audit write is logged at ERROR without
    breaking the business operation.
    """
    authenticated = current_user.is_authenticated
    AuditRepository().safe_log_event(
        entity_type=entity_type, action=action,
        entity_id=entity_id, entity_label=entity_label,
        field_name=field_name, old_value=old_value, new_value=new_value,
        user_id=current_user.id if authenticated else None,
        user_name=current_user.full_name if authenticated else None,
    )
