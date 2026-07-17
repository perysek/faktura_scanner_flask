"""
Caldis.pl import — HTTP routes.

Endpoints:
  GET  /api/import/<id>/stream           — SSE progress stream    [phase 06]
  GET  /api/import/<id>/status           — Polling status         [phase 06]
  GET  /api/import/session-status        — Caldis session check   [phase 07]
  POST /api/import/reconnect-session     — Headed re-login         [phase 07]
  POST /api/import/start                 — Kick off import         [phase 08]
  GET  /api/import/history               — Last 20 runs            [phase 08]
  GET  /api/import/conflict-scan         — Scan past visits for reschedule duplicates
  POST /api/import/conflict-scan/apply   — Soft-delete the superseded duplicates found above

All routes are admin-only via @module_permission_required('data_import').
The page route GET /import lives on main_bp (routes/main_routes.py).
"""
import asyncio
import json
import logging
import os
import queue as queue_module
import sys
import time as _time_module
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Blueprint, Response, jsonify, request, stream_with_context
from flask_login import login_required, current_user

from config.auth_config import module_permission_required
from exceptions import AppError, NotFoundError, ValidationError, ConflictError
from repositories.data_import.import_log_repository import ImportLogRepository
from services.data_import_runner import IMPORT_RUNNER
from services.visit_conflict_scan_service import VisitConflictScanService

logger = logging.getLogger(__name__)

import_bp = Blueprint('data_import', __name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = PROJECT_ROOT / 'assets' / 'temp' / 'caldis_session.json'
SESSION_MAX_AGE_DAYS = 30


# ─── helpers ──────────────────────────────────────────────────────────────────

def _serialize_row(row: dict) -> dict:
    """Convert an import_logs row to a JSON-safe dict."""
    def _iso(v):
        if v is None:
            return None
        if hasattr(v, 'isoformat'):
            return v.isoformat()
        return str(v)

    return {
        'id': row['id'],
        'status': row['status'],
        'stats': row.get('stats') or {},
        'error_message': row.get('error_message'),
        'started_at': _iso(row.get('started_at')),
        'finished_at': _iso(row.get('finished_at')),
        'date_range_start': _iso(row.get('date_range_start')),
        'date_range_end': _iso(row.get('date_range_end')),
        'session_status': row.get('session_status'),
        'dry_run': bool(row.get('dry_run')),
        'triggered_by_user_id': row.get('triggered_by_user_id'),
    }


def _build_sse_generator(import_id: int,
                         queue: Optional[queue_module.Queue],
                         row: dict,
                         heartbeat_seconds: int = 15):
    """Yield SSE frames for the given import.

    Extracted from the view function so it can be unit-tested without spinning
    up the Flask test client.
    """
    # No queue — emit a synthetic 'done' from the DB row and stop.
    if queue is None:
        synthetic = {
            'type': 'done',
            'status': row.get('status') or 'unknown',
            'stats': row.get('stats') or {},
            'error_message': row.get('error_message'),
            'timestamp': datetime.now().isoformat(),
        }
        yield f"data: {json.dumps(synthetic)}\n\n"
        return

    # Drain the queue with heartbeats on idle.
    while True:
        try:
            event = queue.get(timeout=heartbeat_seconds)
        except queue_module.Empty:
            yield ": hb\n\n"
            continue

        yield f"data: {json.dumps(event, default=str)}\n\n"
        if event.get('type') == 'done':
            return


def _is_headless_server() -> bool:
    """Return True when the host cannot open a visible browser window.

    On Linux: no DISPLAY env var → headless.
    On Windows/macOS: always has a display.
    """
    if sys.platform.startswith('linux'):
        return not os.environ.get('DISPLAY')
    return False


async def _do_reconnect_playwright() -> None:
    """Launch a headed Playwright browser, wait for manual login, save session."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context(accept_downloads=False)
        page = await ctx.new_page()

        await page.goto('https://caldis.pl/logowanie', wait_until='networkidle')
        logger.info('Czekam na reczne logowanie admina (max 120s)...')

        await page.wait_for_url(
            lambda url: 'logowanie' not in url.lower(),
            timeout=120_000,
        )
        logger.info('Zalogowano pomyslnie — zapisuje sesje.')

        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        await ctx.storage_state(path=str(SESSION_FILE))
        logger.info('Sesja zapisana: %s', SESSION_FILE.name)
        await browser.close()


# ─── SSE stream ───────────────────────────────────────────────────────────────

@import_bp.route('/import/<int:import_id>/stream')
@login_required
@module_permission_required('data_import')
def import_stream(import_id: int):
    """SSE: live progress events for a single import."""
    repo = ImportLogRepository()
    row = repo.get_by_id(import_id)
    if row is None:
        raise NotFoundError('Import nie znaleziony')

    q = IMPORT_RUNNER.get_queue(import_id)
    generator = _build_sse_generator(import_id, q, row)

    resp = Response(stream_with_context(generator), mimetype='text/event-stream')
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    return resp


# ─── polling status ───────────────────────────────────────────────────────────

@import_bp.route('/import/<int:import_id>/status', methods=['GET'])
@login_required
@module_permission_required('data_import')
def import_status(import_id: int):
    """Polling fallback: latest snapshot of an import_logs row."""
    try:
        row = ImportLogRepository().get_by_id(import_id)
        if row is None:
            raise NotFoundError('Import nie znaleziony')
        return jsonify(_serialize_row(row))
    except AppError:
        raise
    except Exception:
        logger.exception('Unexpected error in import_status')
        raise AppError('Wystapil blad serwera')


# ─── session management ───────────────────────────────────────────────────────

@import_bp.route('/import/session-status', methods=['GET'])
@login_required
@module_permission_required('data_import')
def get_session_status():
    """Return caldis.pl session file health."""
    if not SESSION_FILE.exists():
        return jsonify({'status': 'missing', 'age_days': None})
    age_days = (_time_module.time() - SESSION_FILE.stat().st_mtime) / 86400
    status = 'active' if age_days < SESSION_MAX_AGE_DAYS else 'expired'
    return jsonify({'status': status, 'age_days': round(age_days, 1)})


@import_bp.route('/import/reconnect-session', methods=['POST'])
@login_required
@module_permission_required('data_import')
def reconnect_session():
    """Launch headed Playwright browser for manual caldis.pl re-login."""
    try:
        if _is_headless_server():
            raise AppError(
                'Serwer nie ma interfejsu graficznego. '
                'Uruchom recznie: python scripts/import_appointments_playwright.py --headed',
                status_code=503,
            )
        asyncio.run(_do_reconnect_playwright())
        return jsonify({'status': 'active'})
    except AppError:
        raise
    except RuntimeError as exc:
        logger.exception('Playwright reconnect failed')
        raise AppError(f'Blad polaczenia z caldis.pl: {exc}')
    except Exception:
        logger.exception('Unexpected error in reconnect_session')
        raise AppError('Wystapil blad serwera')


# ─── start import ─────────────────────────────────────────────────────────────

@import_bp.route('/import/start', methods=['POST'])
@login_required
@module_permission_required('data_import')
def start_import():
    """Start a background import from caldis.pl for the given date range."""
    try:
        data = request.get_json() or {}

        date_start_str = (data.get('date_start') or '').strip()
        date_end_str   = (data.get('date_end') or '').strip()
        dry_run        = bool(data.get('dry_run', False))
        keep_xlsx      = bool(data.get('keep_xlsx', False))

        if not date_start_str or not date_end_str:
            raise ValidationError('Wymagane: date_start, date_end')

        try:
            date_start = datetime.strptime(date_start_str, '%Y-%m-%d').date()
            date_end   = datetime.strptime(date_end_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError('Nieprawidlowy format daty (oczekiwano YYYY-MM-DD)')

        if date_start > date_end:
            raise ValidationError('date_start musi byc przed lub rowny date_end')

        # No upper bound on date_end: importing future appointments is allowed.
        # Future-dated visits are inserted with status 'scheduled' (see
        # DataImportService._process_row), so they show up as upcoming bookings.

        repo = ImportLogRepository()
        if repo.has_running_import():
            raise ConflictError('Import jest juz w toku — poczekaj na zakonczenie.')

        import_id = repo.create(
            date_start=date_start,
            date_end=date_end,
            dry_run=dry_run,
            triggered_by_user_id=current_user.id,
        )
        IMPORT_RUNNER.start_import(import_id, date_start, date_end, dry_run,
                                   keep_xlsx=keep_xlsx)

        logger.info('Import %d started (range: %s to %s, dry_run=%s, keep_xlsx=%s)',
                    import_id, date_start, date_end, dry_run, keep_xlsx)

        return jsonify({'success': True, 'import_id': import_id}), 202

    except AppError:
        raise
    except Exception:
        logger.exception('Unexpected error in start_import')
        raise AppError('Wystapil blad serwera')


# ─── history ──────────────────────────────────────────────────────────────────

@import_bp.route('/import/history', methods=['GET'])
@login_required
@module_permission_required('data_import')
def import_history():
    """Return last 20 import_logs rows with user display names."""
    try:
        rows = ImportLogRepository().get_history(limit=20)

        def _serialize_history(row):
            def _iso(v):
                if v is None:
                    return None
                if hasattr(v, 'isoformat'):
                    return v.isoformat()
                return str(v)
            return {
                'id':                   row['id'],
                'status':               row['status'],
                'stats':                row.get('stats') or {},
                'error_message':        row.get('error_message'),
                'started_at':           _iso(row.get('started_at')),
                'finished_at':          _iso(row.get('finished_at')),
                'date_range_start':     _iso(row.get('date_range_start')),
                'date_range_end':       _iso(row.get('date_range_end')),
                'dry_run':              bool(row.get('dry_run')),
                'triggered_by_user_id': row.get('triggered_by_user_id'),
                'triggered_by_name':    row.get('triggered_by_name'),
                'session_status':       row.get('session_status'),
            }

        history = [_serialize_history(r) for r in rows]
        return jsonify({'success': True, 'history': history, 'count': len(history)})

    except AppError:
        raise
    except Exception:
        logger.exception('Unexpected error in import_history')
        raise AppError('Wystapil blad serwera')


# ─── conflict scan (duplicate/rescheduled past visits) ─────────────────────────

def _parse_scan_range(date_start_str: str, date_end_str: str) -> tuple:
    date_start_str = (date_start_str or '').strip()
    date_end_str   = (date_end_str or '').strip()
    if not date_start_str or not date_end_str:
        raise ValidationError('Wymagane: date_start, date_end')
    try:
        date_start = datetime.strptime(date_start_str, '%Y-%m-%d').date()
        date_end   = datetime.strptime(date_end_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError('Nieprawidlowy format daty (oczekiwano YYYY-MM-DD)')
    return date_start, date_end


@import_bp.route('/import/conflict-scan', methods=['GET'])
@login_required
@module_permission_required('data_import')
def conflict_scan():
    """Skanuj przeszłe wizyty pod kątem duplikatów/przełożeń (tylko odczyt)."""
    try:
        date_start, date_end = _parse_scan_range(
            request.args.get('date_start'), request.args.get('date_end'))
        result = VisitConflictScanService().scan(date_start, date_end)
        return jsonify({'success': True, **result})
    except AppError:
        raise
    except Exception:
        logger.exception('Unexpected error in conflict_scan')
        raise AppError('Wystapil blad serwera')


@import_bp.route('/import/conflict-scan/apply', methods=['POST'])
@login_required
@module_permission_required('data_import')
def conflict_scan_apply():
    """Soft-delete wizyt nadpisanych przez przełożenia w zadanym zakresie (odwracalne)."""
    try:
        data = request.get_json() or {}
        date_start, date_end = _parse_scan_range(data.get('date_start'), data.get('date_end'))
        result = VisitConflictScanService().apply(date_start, date_end)
        logger.info('Conflict scan apply: %d appointments superseded (range %s to %s) by user %s',
                    result['removed_count'], date_start, date_end, current_user.id)
        return jsonify({'success': True, **result})
    except AppError:
        raise
    except Exception:
        logger.exception('Unexpected error in conflict_scan_apply')
        raise AppError('Wystapil blad serwera')
