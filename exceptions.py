"""
Application-specific exception classes.

Usage:
    from exceptions import ValidationError, NotFoundError

    raise NotFoundError('Invoice not found')
    raise ValidationError('Invalid date format')

Flask error handler in app.py converts these to JSON responses automatically.
"""


class AppError(Exception):
    """Base application error with HTTP status code."""
    status_code = 500

    def __init__(self, message: str = 'Internal server error', status_code: int = None):
        super().__init__(message)
        if status_code is not None:
            self.status_code = status_code


class ValidationError(AppError):
    """Invalid input data — maps to HTTP 400."""
    status_code = 400


class NotFoundError(AppError):
    """Resource not found — maps to HTTP 404."""
    status_code = 404


class PermissionDeniedError(AppError):
    """Insufficient permissions — maps to HTTP 403."""
    status_code = 403


class ConflictError(AppError):
    """Resource conflict (e.g. duplicate, schedule overlap) — maps to HTTP 409."""
    status_code = 409


class DatabaseConnectionError(AppError):
    """Database unreachable or connection failed — maps to HTTP 503."""
    status_code = 503
