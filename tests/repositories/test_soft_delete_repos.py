"""
Tests for AppointmentRepository and ServiceRepository soft-delete filtering.

Both repositories use get_db_connection() directly (not BaseRepository).
Tests mock at the module level where get_db_connection is imported.
"""
import pytest
from datetime import date, time
from unittest.mock import Mock, patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_appt_db():
    """Mock for AppointmentRepository using get_db_connection() context manager."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cm = MagicMock()
    mock_cm.__enter__ = Mock(return_value=mock_conn)
    mock_cm.__exit__ = Mock(return_value=False)
    with patch(
        'repositories.appointments.appointment_repository.get_db_connection',
        return_value=mock_cm
    ):
        yield type('MockDB', (), {'connection': mock_conn, 'cursor': mock_cursor})()


@pytest.fixture
def mock_svc_db():
    """Mock for ServiceRepository using get_db_connection() context manager."""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cm = MagicMock()
    mock_cm.__enter__ = Mock(return_value=mock_conn)
    mock_cm.__exit__ = Mock(return_value=False)
    with patch(
        'repositories.services.service_repository.get_db_connection',
        return_value=mock_cm
    ):
        yield type('MockDB', (), {'connection': mock_conn, 'cursor': mock_cursor})()


# ---------------------------------------------------------------------------
# AppointmentRepository tests
# ---------------------------------------------------------------------------

class TestAppointmentSoftDelete:
    """AppointmentRepository soft-delete: delete() must UPDATE, all SELECTs must filter."""

    def test_delete_is_soft_delete(self, mock_appt_db):
        """delete() must use UPDATE SET is_deleted = TRUE, not DELETE FROM."""
        mock_appt_db.cursor.rowcount = 1
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        result = repo.delete(1)
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'UPDATE' in sql, f"delete() should use UPDATE, got: {sql}"
        assert 'is_deleted = TRUE' in sql, f"delete() should set is_deleted = TRUE, got: {sql}"
        assert 'DELETE FROM' not in sql, f"delete() must not use DELETE FROM, got: {sql}"
        assert result is True

    def test_restore(self, mock_appt_db):
        """restore() must UPDATE SET is_deleted = FALSE."""
        mock_appt_db.cursor.rowcount = 1
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        result = repo.restore(1)
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'UPDATE' in sql, f"restore() should use UPDATE, got: {sql}"
        assert 'is_deleted = FALSE' in sql, f"restore() should set is_deleted = FALSE, got: {sql}"
        assert 'deleted_at = NULL' in sql, f"restore() should clear deleted_at, got: {sql}"
        assert result is True

    def test_get_by_id_excludes_deleted(self, mock_appt_db):
        mock_appt_db.cursor.fetchone.return_value = None
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        repo.get_by_id(1)
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_by_id() missing is_deleted filter: {sql}"

    def test_get_by_date_range_excludes_deleted(self, mock_appt_db):
        mock_appt_db.cursor.fetchall.return_value = []
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        repo.get_by_date_range(date(2026, 1, 1), date(2026, 12, 31))
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_by_date_range() missing is_deleted filter: {sql}"

    def test_get_latest_excludes_deleted(self, mock_appt_db):
        mock_appt_db.cursor.fetchall.return_value = []
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        repo.get_latest(10)
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_latest() missing is_deleted filter: {sql}"

    def test_get_daily_schedule_excludes_deleted(self, mock_appt_db):
        mock_appt_db.cursor.fetchall.return_value = []
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        repo.get_daily_schedule(1, date(2026, 1, 15))
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_daily_schedule() missing is_deleted filter: {sql}"

    def test_check_conflicts_excludes_deleted(self, mock_appt_db):
        mock_appt_db.cursor.fetchall.return_value = []
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        repo.check_conflicts(1, date(2026, 1, 15), time(10, 0), time(11, 0))
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"check_conflicts() missing is_deleted filter: {sql}"

    def test_get_client_appointments_excludes_deleted(self, mock_appt_db):
        mock_appt_db.cursor.fetchall.return_value = []
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        repo.get_client_appointments(1)
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"get_client_appointments() missing is_deleted filter: {sql}"
        )

    def test_count_by_date_excludes_deleted(self, mock_appt_db):
        mock_appt_db.cursor.fetchone.return_value = {'cnt': 0}
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        repo.count_by_date(date(2026, 1, 15))
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"count_by_date() missing is_deleted filter: {sql}"

    def test_get_past_pending_excludes_deleted(self, mock_appt_db):
        mock_appt_db.cursor.fetchall.return_value = []
        from repositories.appointments.appointment_repository import AppointmentRepository
        repo = AppointmentRepository()
        repo.get_past_pending_appointments()
        sql = mock_appt_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"get_past_pending_appointments() missing is_deleted filter: {sql}"
        )


# ---------------------------------------------------------------------------
# ServiceRepository tests
# ---------------------------------------------------------------------------

class TestServiceSoftDelete:
    """ServiceRepository soft-delete: delete() must UPDATE, all SELECTs must filter."""

    def test_delete_is_soft_delete(self, mock_svc_db):
        """delete() must use UPDATE SET is_deleted = TRUE, not deactivate (is_active = FALSE)."""
        mock_svc_db.cursor.rowcount = 1
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        result = repo.delete(1)
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'UPDATE' in sql, f"delete() should use UPDATE, got: {sql}"
        assert 'is_deleted = TRUE' in sql, f"delete() should set is_deleted = TRUE, got: {sql}"
        assert 'is_active = FALSE' not in sql, (
            f"delete() must not call deactivate (is_active = FALSE), got: {sql}"
        )
        assert result is True

    def test_restore(self, mock_svc_db):
        """restore() must UPDATE SET is_deleted = FALSE."""
        mock_svc_db.cursor.rowcount = 1
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        result = repo.restore(1)
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'UPDATE' in sql, f"restore() should use UPDATE, got: {sql}"
        assert 'is_deleted = FALSE' in sql, f"restore() should set is_deleted = FALSE, got: {sql}"
        assert 'deleted_at = NULL' in sql, f"restore() should clear deleted_at, got: {sql}"
        assert result is True

    def test_get_by_id_excludes_deleted(self, mock_svc_db):
        mock_svc_db.cursor.fetchone.return_value = None
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        repo.get_by_id(1)
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_by_id() missing is_deleted filter: {sql}"

    def test_get_all_active_excludes_deleted(self, mock_svc_db):
        mock_svc_db.cursor.fetchall.return_value = []
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        repo.get_all(active_only=True)
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"get_all(active_only=True) missing is_deleted filter: {sql}"
        )

    def test_get_all_inactive_excludes_deleted(self, mock_svc_db):
        mock_svc_db.cursor.fetchall.return_value = []
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        repo.get_all(active_only=False)
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, (
            f"get_all(active_only=False) missing is_deleted filter: {sql}"
        )

    def test_search_excludes_deleted(self, mock_svc_db):
        mock_svc_db.cursor.fetchall.return_value = []
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        repo.search("strzyżenie")
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"search() missing is_deleted filter: {sql}"

    def test_get_by_category_excludes_deleted(self, mock_svc_db):
        mock_svc_db.cursor.fetchall.return_value = []
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        repo.get_by_category("Włosy")
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_by_category() missing is_deleted filter: {sql}"

    def test_get_statistics_excludes_deleted(self, mock_svc_db):
        mock_svc_db.cursor.fetchone.return_value = {
            'total_services': 0,
            'active_services': 0,
            'total_categories': 0,
            'avg_price': None,
            'avg_duration': None,
        }
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        repo.get_statistics()
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_statistics() missing is_deleted filter: {sql}"

    def test_get_main_services_excludes_deleted(self, mock_svc_db):
        mock_svc_db.cursor.fetchall.return_value = []
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        repo.get_main_services()
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_main_services() missing is_deleted filter: {sql}"

    def test_get_addon_services_excludes_deleted(self, mock_svc_db):
        mock_svc_db.cursor.fetchall.return_value = []
        from repositories.services.service_repository import ServiceRepository
        repo = ServiceRepository()
        repo.get_addon_services()
        sql = mock_svc_db.cursor.execute.call_args[0][0]
        assert 'is_deleted = FALSE' in sql, f"get_addon_services() missing is_deleted filter: {sql}"
