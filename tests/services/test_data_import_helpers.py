"""
Unit tests for data_import_helpers — pure resolvers + DB lookup builders.
DB builders use the mock_db fixture; pure resolvers need no mocks.
"""
import pytest
from datetime import datetime


# ── pure resolvers (no DB needed) ────────────────────────────────────────────

class TestNormalizePhone:
    def test_9_digit_plain(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone('504020116') == '48504020116'

    def test_with_spaces(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone(' 504 020 116') == '48504020116'

    def test_with_plus48(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone('+48504020116') == '48504020116'

    def test_with_0048(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone('0048504020116') == '48504020116'

    def test_blank_returns_none(self):
        from services.data_import_helpers import normalize_phone
        assert normalize_phone('') is None
        assert normalize_phone(None) is None


class TestResolveEmployeeId:
    def test_exact_match(self):
        from services.data_import_helpers import resolve_employee_id
        emp_map = {'anna': 1, 'kasia': 2}
        assert resolve_employee_id('Anna', emp_map) == 1
        assert resolve_employee_id('KASIA', emp_map) == 2

    def test_substring_longest_wins(self):
        from services.data_import_helpers import resolve_employee_id
        emp_map = {'anna': 1, 'annabelle': 2}
        assert resolve_employee_id('zRecepcja Annabelle', emp_map) == 2

    def test_unknown_returns_none(self):
        from services.data_import_helpers import resolve_employee_id
        assert resolve_employee_id('Unknown Name', {'anna': 1}) is None

    def test_blank_returns_none(self):
        from services.data_import_helpers import resolve_employee_id
        assert resolve_employee_id('', {}) is None
        assert resolve_employee_id(None, {}) is None


class TestResolveClientId:
    def test_strip_prefix_p_dot(self):
        from services.data_import_helpers import resolve_client_id
        client_map = {('anna', 'kowalska'): 5}
        assert resolve_client_id('p. Anna Kowalska', client_map) == 5

    def test_phone_fallback(self):
        from services.data_import_helpers import resolve_client_id
        phone_map = {'48504020116': 99}
        assert resolve_client_id('Unknown Person', {}, '504020116', phone_map) == 99

    def test_returns_none_when_nothing_matches(self):
        from services.data_import_helpers import resolve_client_id
        assert resolve_client_id('Unknown', {}, None, {}) is None

    def test_wolne_returns_none(self):
        from services.data_import_helpers import resolve_client_id
        assert resolve_client_id('wolne', {}) is None


class TestParseClientName:
    def test_strip_prefix_p_dot(self):
        from services.data_import_helpers import parse_client_name
        assert parse_client_name('p. Anna Kowalska') == ('Anna', 'Kowalska')

    def test_first_name_only(self):
        from services.data_import_helpers import parse_client_name
        assert parse_client_name('Anna') == ('Anna', '')

    def test_blank_returns_none(self):
        from services.data_import_helpers import parse_client_name
        assert parse_client_name('') is None
        assert parse_client_name(None) is None

    def test_wolne_returns_none(self):
        from services.data_import_helpers import parse_client_name
        assert parse_client_name('Wolne') is None
        assert parse_client_name('wolne') is None


class TestCreateClient:
    def test_inserts_and_returns_id(self, mock_db):
        mock_db.cursor.fetchone.return_value = {'id': 123}
        from services.data_import_helpers import create_client
        new_id = create_client(mock_db.connection, 'Anna', 'Kowalska', '48504020116')
        assert new_id == 123
        sql = mock_db.cursor.execute.call_args[0][0]
        params = mock_db.cursor.execute.call_args[0][1]
        assert 'INSERT INTO clients' in sql
        assert params == ('Anna', 'Kowalska', '48504020116')


class TestResolveServiceId:
    def test_exact(self):
        from services.data_import_helpers import resolve_service_id
        svc_list = [(20, 'manicure klasyczny'), (47, 'uzupelnienie zelu')]
        assert resolve_service_id('Manicure klasyczny', svc_list) == 20

    def test_prefix_match(self):
        from services.data_import_helpers import resolve_service_id
        svc_list = [(47, 'uzupelnienie zelu 1')]
        assert resolve_service_id('Uzupelnienie zelu', svc_list) == 47

    def test_default_fallback(self):
        from services.data_import_helpers import resolve_service_id, DEFAULT_SERVICE_ID
        assert resolve_service_id('Nieznana usluga', []) == DEFAULT_SERVICE_ID


class TestDateTimeParsers:
    def test_parse_appointment_date_string(self):
        from services.data_import_helpers import parse_appointment_date
        assert parse_appointment_date('2026-05-19 10:30:00') == '2026-05-19'

    def test_parse_appointment_date_datetime(self):
        from services.data_import_helpers import parse_appointment_date
        assert parse_appointment_date(datetime(2026, 5, 19, 10, 30)) == '2026-05-19'

    def test_parse_appointment_date_none(self):
        from services.data_import_helpers import parse_appointment_date
        assert parse_appointment_date(None) is None

    def test_parse_time(self):
        from services.data_import_helpers import parse_time
        assert parse_time('2026-05-19 10:30:00') == '10:30:00'

    def test_calc_duration_minutes(self):
        from services.data_import_helpers import calc_duration_minutes
        assert calc_duration_minutes('2026-05-19 10:00:00', '2026-05-19 11:30:00') == 90

    def test_calc_duration_zero_on_bad_input(self):
        from services.data_import_helpers import calc_duration_minutes
        assert calc_duration_minutes(None, None) == 0


# ── DB builders (mock_db) ────────────────────────────────────────────────────

class TestBuildersUsePostgresPlaceholders:

    def test_build_employee_map(self, mock_db):
        mock_db.cursor.fetchall.return_value = [
            {'id': 1, 'first_name': 'Anna'},
            {'id': 2, 'first_name': 'Kasia'},
        ]
        from services.data_import_helpers import build_employee_map
        emp_map = build_employee_map(mock_db.connection)
        assert emp_map == {'anna': 1, 'kasia': 2}
        sql = mock_db.cursor.execute.call_args[0][0]
        assert '?' not in sql
        assert 'employees' in sql.lower()

    def test_build_client_map_both_orderings(self, mock_db):
        mock_db.cursor.fetchall.return_value = [
            {'id': 5, 'first_name': 'Anna', 'last_name': 'Kowalska'}
        ]
        from services.data_import_helpers import build_client_map
        cm = build_client_map(mock_db.connection)
        assert cm[('anna', 'kowalska')] == 5
        assert cm[('kowalska', 'anna')] == 5

    def test_build_phone_map(self, mock_db):
        mock_db.cursor.fetchall.return_value = [
            {'id': 1, 'phone': '48504020116'},
        ]
        from services.data_import_helpers import build_phone_map
        pm = build_phone_map(mock_db.connection)
        assert pm == {'48504020116': 1}
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'phone IS NOT NULL' in sql

    def test_build_service_map_sorted(self, mock_db):
        mock_db.cursor.fetchall.return_value = [
            {'id': 20, 'name': 'Manicure'},
            {'id': 47, 'name': 'Pedicure'},
        ]
        from services.data_import_helpers import build_service_map
        sl = build_service_map(mock_db.connection)
        assert sl == [(20, 'manicure'), (47, 'pedicure')]
        sql = mock_db.cursor.execute.call_args[0][0]
        assert 'ORDER BY id' in sql
