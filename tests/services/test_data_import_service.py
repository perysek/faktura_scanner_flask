"""
Tests for DataImportService._process_row — specifically the auto-create-client
path: a caldis.pl row whose name matches no existing client must create a new
client and still import the visit, instead of silently skipping it.
"""
from unittest.mock import Mock

import pandas as pd

from services.data_import_service import DataImportService


def _make_row(**overrides):
    base = {
        'Imię i nazwisko': 'p. Nowy Klient',
        'Telefon': '504020116',
        'Kalendarz': 'Kasia',
        'Kategoria': 'Manicure',
        'Suma brutto': '100',
        'Od': '2026-05-19 10:00:00',
        'Do': '2026-05-19 11:00:00',
        'Data utworzenia': '2026-05-19 09:00:00',
    }
    base.update(overrides)
    return pd.Series(base)


class TestProcessRowAutoCreatesClient:

    def test_unmatched_name_creates_client_and_imports_visit(self):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        # fetchone() call order inside _process_row for this scenario:
        #   1. duplicate check                -> None (not a duplicate)
        #   2. create_client RETURNING id      -> new client id 777
        #   3. employees.commission_rate SELECT
        #   4. INSERT appointments RETURNING id
        mock_cursor.fetchone.side_effect = [
            None,
            {'id': 777},
            {'commission_rate': 10},
            {'id': 555},
        ]

        svc = DataImportService(log_repo=Mock())
        stats = svc._zero_stats()
        employee_map = {'kasia': 2}
        client_map = {}
        phone_map = {}
        service_list = [(20, 'manicure')]
        row_data = {'appointments': [], 'appointment_services': [], 'income_records': []}
        events = []

        svc._process_row(_make_row(), 0, mock_conn, False, stats,
                         employee_map, client_map, phone_map, service_list,
                         events.append, row_data=row_data)

        assert stats['errors'] == 0
        assert stats['skipped_no_client'] == 0
        assert stats['inserted'] == 1
        assert stats['clients_created'] == 1

        # 'p.' prefix stripped before the client row was created.
        create_call = [c for c in mock_cursor.execute.call_args_list
                       if 'INSERT INTO clients' in c.args[0]][0]
        assert create_call.args[1] == ('Nowy', 'Klient', '48504020116')

        # New client registered in the in-memory map for repeat rows in the
        # same file, keyed by the stripped (not 'p.'-prefixed) name.
        assert client_map[('nowy', 'klient')] == 777

        log_messages = [e['message'] for e in events if e.get('type') == 'log']
        assert any('Nowy klient utworzony' in m for m in log_messages)

    def test_wolne_placeholder_still_skipped_not_created(self):
        """'Wolne' marks blocked calendar time, not a client — must never
        create a client for it, even though it's a non-blank name cell."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        svc = DataImportService(log_repo=Mock())
        stats = svc._zero_stats()
        row_data = {'appointments': [], 'appointment_services': [], 'income_records': []}

        svc._process_row(_make_row(**{'Imię i nazwisko': 'Wolne'}), 0, mock_conn, False,
                         stats, {'kasia': 2}, {}, {}, [(20, 'manicure')],
                         lambda e: None, row_data=row_data)

        assert stats['skipped_no_client'] == 1
        assert stats['clients_created'] == 0
        create_calls = [c for c in mock_cursor.execute.call_args_list
                        if 'INSERT INTO clients' in c.args[0]]
        assert create_calls == []

    def test_dry_run_new_client_not_written_but_counted(self):
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        # dry_run: duplicate check + commission_rate lookup hit the DB, but
        # no client/appointment INSERT (no create_client call, no commit).
        mock_cursor.fetchone.side_effect = [None, {'commission_rate': 10}]

        svc = DataImportService(log_repo=Mock())
        stats = svc._zero_stats()
        row_data = {'appointments': [], 'appointment_services': [], 'income_records': []}

        svc._process_row(_make_row(), 0, mock_conn, True, stats,
                         {'kasia': 2}, {}, {}, [(20, 'manicure')],
                         lambda e: None, row_data=row_data)

        assert stats['inserted'] == 1
        assert stats['clients_created'] == 1
        create_calls = [c for c in mock_cursor.execute.call_args_list
                        if 'INSERT INTO clients' in c.args[0]]
        assert create_calls == []  # dry-run: nothing actually written
        assert row_data['appointments'][0]['client_id'] is None
