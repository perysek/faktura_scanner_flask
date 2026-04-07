"""
Tests: AppointmentStatus enum adoption — verify zero hardcoded status strings remain
in SQL query contexts. File-scanning tests (no DB required).
"""
import inspect
import re


def _source(module):
    return inspect.getsource(module)


def _sql_status_occurrences(source, status):
    """
    Find hardcoded status strings in SQL contexts only.
    Matches patterns like: = 'status', IN ('status', NOT IN ('status',
    WHEN status = 'status', FILTER (WHERE status = 'status'
    but NOT Python dict keys like row['status'] or return {'status': ...}
    """
    # SQL context patterns for status strings
    sql_patterns = [
        rf"=\s*'{re.escape(status)}'",          # = 'completed'
        rf"IN\s*\([^)]*'{re.escape(status)}'",   # IN ('completed', ...
        rf"FILTER.*=\s*'{re.escape(status)}'",   # FILTER (WHERE status = 'completed')
    ]
    for pattern in sql_patterns:
        if re.search(pattern, source, re.IGNORECASE):
            return True
    return False


class TestAppointmentStatusEnumAdoption:
    """Verify no hardcoded status strings remain in SQL query contexts."""

    # --- appointment_repository ---

    def test_appointment_repo_imports_enum(self):
        from repositories.appointments import appointment_repository
        assert 'from config.appointment_statuses import AppointmentStatus' in _source(appointment_repository)

    def test_appointment_repo_no_hardcoded_completed(self):
        from repositories.appointments import appointment_repository
        assert not _sql_status_occurrences(_source(appointment_repository), 'completed'), \
            "Hardcoded 'completed' found in SQL context in appointment_repository"

    def test_appointment_repo_no_hardcoded_cancelled(self):
        from repositories.appointments import appointment_repository
        assert not _sql_status_occurrences(_source(appointment_repository), 'cancelled'), \
            "Hardcoded 'cancelled' found in SQL context in appointment_repository"

    def test_appointment_repo_no_hardcoded_no_show(self):
        from repositories.appointments import appointment_repository
        assert not _sql_status_occurrences(_source(appointment_repository), 'no_show'), \
            "Hardcoded 'no_show' found in SQL context in appointment_repository"

    # --- analytics_repository ---

    def test_analytics_repo_imports_enum(self):
        from repositories.analytics import analytics_repository
        assert 'from config.appointment_statuses import AppointmentStatus' in _source(analytics_repository)

    def test_analytics_repo_no_hardcoded_completed(self):
        from repositories.analytics import analytics_repository
        assert not _sql_status_occurrences(_source(analytics_repository), 'completed'), \
            "Hardcoded 'completed' found in SQL context in analytics_repository"

    def test_analytics_repo_no_hardcoded_cancelled(self):
        from repositories.analytics import analytics_repository
        assert not _sql_status_occurrences(_source(analytics_repository), 'cancelled'), \
            "Hardcoded 'cancelled' found in SQL context in analytics_repository"

    def test_analytics_repo_no_hardcoded_no_show(self):
        from repositories.analytics import analytics_repository
        assert not _sql_status_occurrences(_source(analytics_repository), 'no_show'), \
            "Hardcoded 'no_show' found in SQL context in analytics_repository"

    # --- appointment_service ---

    def test_appointment_service_imports_enum(self):
        from services import appointment_service
        assert 'from config.appointment_statuses import AppointmentStatus' in _source(appointment_service)

    def test_appointment_service_no_local_transitions_dict(self):
        from services import appointment_service
        source = _source(appointment_service)
        # Local STATUS_TRANSITIONS dict must be gone; only AppointmentStatus.VALID_TRANSITIONS
        lines = [l for l in source.split('\n')
                 if not l.strip().startswith('#') and 'VALID_TRANSITIONS' not in l]
        code = '\n'.join(lines)
        assert 'STATUS_TRANSITIONS' not in code, "Local STATUS_TRANSITIONS dict still present"

    def test_appointment_service_uses_enum_transitions(self):
        from services import appointment_service
        assert 'AppointmentStatus' in _source(appointment_service)

    # --- appointment_routes ---

    def test_appointment_routes_no_allowed_final_statuses(self):
        from routes import appointment_routes
        assert 'ALLOWED_FINAL_STATUSES' not in _source(appointment_routes), \
            "ALLOWED_FINAL_STATUSES still present in appointment_routes"

    def test_appointment_routes_uses_enum_final(self):
        from routes import appointment_routes
        assert 'AppointmentStatus.FINAL' in _source(appointment_routes)
