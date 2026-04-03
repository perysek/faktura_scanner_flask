"""
Tests for exception class hierarchy.

Verifies that:
- DatabaseConnectionError is a subclass of AppError with status_code 503
- AppointmentError is a subclass of AppError with status_code 400
- OCRExtractionError is a subclass of AppError with status_code 422
"""
import pytest
from exceptions import AppError, DatabaseConnectionError
from services.appointment_service import AppointmentError
from services.ocr_service import OCRExtractionError


class TestExceptionHierarchy:
    def test_database_connection_error_is_subclass_of_app_error(self):
        assert issubclass(DatabaseConnectionError, AppError)

    def test_appointment_error_is_subclass_of_app_error(self):
        assert issubclass(AppointmentError, AppError)

    def test_ocr_extraction_error_is_subclass_of_app_error(self):
        assert issubclass(OCRExtractionError, AppError)

    def test_appointment_error_isinstance_app_error(self):
        assert isinstance(AppointmentError("test"), AppError)

    def test_ocr_extraction_error_isinstance_app_error(self):
        assert isinstance(OCRExtractionError("test"), AppError)

    def test_database_connection_error_isinstance_app_error(self):
        assert isinstance(DatabaseConnectionError("test"), AppError)

    def test_appointment_error_status_code(self):
        assert AppointmentError("Conflict").status_code == 400

    def test_appointment_error_preserves_message(self):
        assert str(AppointmentError("Pracownik zajety")) == "Pracownik zajety"

    def test_database_connection_error_status_code(self):
        assert DatabaseConnectionError("db down").status_code == 503

    def test_ocr_extraction_error_status_code(self):
        assert OCRExtractionError("failed").status_code == 422
