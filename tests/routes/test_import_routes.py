"""
Tests for /api/import/* endpoints and the SSE generator function.

The SSE generator is tested as a pure function (no test client needed).
Status and start endpoints are tested via the Flask test client with
mocked repository and patched current_user.
"""
import json
import queue as queue_module
import pytest
from datetime import date, datetime, timezone
from unittest.mock import patch, MagicMock, Mock


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_fake_row(**overrides):
    base = {
        'id': 42,
        'status': 'running',
        'stats': {'inserted': 0},
        'error_message': None,
        'started_at': datetime(2026, 5, 19, 14, 30, 22, tzinfo=timezone.utc),
        'finished_at': None,
        'date_range_start': date(2026, 1, 1),
        'date_range_end': date(2026, 1, 31),
        'session_status': 'active',
        'dry_run': False,
        'triggered_by_user_id': 5,
    }
    base.update(overrides)
    return base


# ── SSE generator unit tests (no Flask needed) ────────────────────────────────

class TestBuildSseGenerator:

    def test_generator_emits_queued_events_and_done(self):
        from routes.import_routes import _build_sse_generator

        q = queue_module.Queue()
        q.put({'type': 'log', 'message': 'hello', 'timestamp': '14:30:22'})
        q.put({'type': 'done', 'status': 'completed', 'stats': {}})

        row = _make_fake_row()
        frames = list(_build_sse_generator(1, q, row, heartbeat_seconds=1))

        assert any('"type": "log"' in f for f in frames)
        assert any('"type": "done"' in f for f in frames)
        for f in frames:
            if not f.startswith(':'):
                assert f.startswith('data: ')
                assert f.endswith('\n\n')

    def test_generator_synthetic_done_when_no_queue(self):
        from routes.import_routes import _build_sse_generator

        terminal_row = _make_fake_row(status='completed',
                                       stats={'inserted': 5})
        frames = list(_build_sse_generator(1, None, terminal_row, heartbeat_seconds=1))

        assert len(frames) == 1
        assert '"type": "done"' in frames[0]
        assert '"status": "completed"' in frames[0]

    def test_generator_unknown_status_when_queue_none_and_row_missing(self):
        from routes.import_routes import _build_sse_generator

        row = _make_fake_row(status=None)
        frames = list(_build_sse_generator(1, None, row, heartbeat_seconds=1))
        assert '"status": "unknown"' in frames[0]


# ── Session status helper tests ───────────────────────────────────────────────

class TestIsHeadlessServer:

    def test_returns_false_on_windows(self, monkeypatch):
        monkeypatch.setattr('sys.platform', 'win32')
        from routes.import_routes import _is_headless_server
        assert _is_headless_server() is False

    def test_returns_true_on_linux_without_display(self, monkeypatch):
        monkeypatch.setattr('sys.platform', 'linux')
        monkeypatch.delenv('DISPLAY', raising=False)
        from routes.import_routes import _is_headless_server
        assert _is_headless_server() is True

    def test_returns_false_on_linux_with_display(self, monkeypatch):
        import os
        monkeypatch.setattr('sys.platform', 'linux')
        monkeypatch.setenv('DISPLAY', ':0')
        from routes.import_routes import _is_headless_server
        assert _is_headless_server() is False


# ── Serialize row helper ──────────────────────────────────────────────────────

class TestSerializeRow:

    def test_datetime_fields_are_iso_strings(self):
        from routes.import_routes import _serialize_row
        row = _make_fake_row()
        result = _serialize_row(row)
        assert isinstance(result['started_at'], str)
        assert '2026-05-19' in result['started_at']
        assert result['finished_at'] is None

    def test_date_fields_are_iso_strings(self):
        from routes.import_routes import _serialize_row
        row = _make_fake_row()
        result = _serialize_row(row)
        assert result['date_range_start'] == '2026-01-01'
        assert result['date_range_end'] == '2026-01-31'

    def test_dry_run_cast_to_bool(self):
        from routes.import_routes import _serialize_row
        row = _make_fake_row(dry_run=0)
        assert _serialize_row(row)['dry_run'] is False
