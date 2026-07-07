"""
Tests for ImportRunner — threading, queue management, concurrent-import prevention.
DataImportService is mocked so no real imports run.
"""
import time
import pytest
from datetime import date
from unittest.mock import Mock, patch, MagicMock


class TestImportRunner:

    def test_start_spawns_thread_and_queue(self):
        from services.data_import_runner import ImportRunner

        with patch('services.data_import_runner.DataImportService') as MockSvc:
            MockSvc.return_value.run_import.side_effect = lambda *a, **kw: time.sleep(0.05) or {}

            runner = ImportRunner()
            runner.start_import(99, date(2026, 1, 1), date(2026, 1, 31), dry_run=False)

            assert runner.get_queue(99) is not None
            assert runner.has_queue(99) is True

    def test_queue_receives_events_and_done_sentinel(self):
        from services.data_import_runner import ImportRunner

        def fake_run_import(import_id, date_start, date_end, dry_run, progress_callback,
                            keep_xlsx=False):
            progress_callback({'type': 'log', 'message': 'hello'})
            return {}

        with patch('services.data_import_runner.DataImportService') as MockSvc:
            MockSvc.return_value.run_import.side_effect = fake_run_import

            runner = ImportRunner()
            runner.start_import(77, date(2026, 1, 1), date(2026, 1, 31), dry_run=False)

            time.sleep(0.1)
            q = runner.get_queue(77)
            events = []
            while not q.empty():
                events.append(q.get_nowait())
            types = [e['type'] for e in events]
            assert 'log' in types
            assert 'done' in types

    def test_thread_crash_pushes_failed_status(self):
        from services.data_import_runner import ImportRunner

        def bad_run(*args, **kwargs):
            raise RuntimeError("Boom")

        with patch('services.data_import_runner.DataImportService') as MockSvc, \
             patch('services.data_import_runner.ImportLogRepository'):
            MockSvc.return_value.run_import.side_effect = bad_run

            runner = ImportRunner()
            runner.start_import(88, date(2026, 1, 1), date(2026, 1, 31), dry_run=False)

            time.sleep(0.1)
            q = runner.get_queue(88)
            events = []
            while not q.empty():
                events.append(q.get_nowait())
            statuses = [e.get('status') for e in events if e.get('type') == 'status']
            assert 'failed' in statuses

    def test_has_queue_false_for_unknown_id(self):
        from services.data_import_runner import ImportRunner
        runner = ImportRunner()
        assert runner.has_queue(9999) is False
        assert runner.get_queue(9999) is None
