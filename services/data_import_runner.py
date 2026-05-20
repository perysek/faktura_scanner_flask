"""
Background runner for the caldis.pl import pipeline.

Spawns one daemon thread per import, exposes a per-import_id queue for SSE
consumers, and prevents concurrent imports via:
  - DB-level check (find_running() before start)
  - Memory-level check (registry of active threads)

Single-process deployment is assumed. For multi-worker deployments, the
in-memory queue must be replaced with Redis pub/sub and the running-import
gate must use Postgres advisory locks.
"""
import logging
import threading
import queue as queue_module
from datetime import date, datetime, timedelta
from typing import Optional

from exceptions import ConflictError
from repositories.data_import.import_log_repository import ImportLogRepository
from services.data_import_service import DataImportService

logger = logging.getLogger(__name__)

# Retention: keep finished queues around for 1 hour so a reconnecting SSE
# client can still see the final 'done' event.
QUEUE_RETENTION = timedelta(hours=1)


class ImportRunner:
    """One-import-at-a-time scheduler with per-import progress queues."""

    def __init__(self):
        self._registry: dict = {}
        self._lock = threading.Lock()

    # ── public API ───────────────────────────────────────────────────────────
    def start_import(self, import_id: int, date_start: date, date_end: date,
                     dry_run: bool) -> None:
        """Start the background thread for an already-created import_id.

        The import_logs row must be created by the caller (route handler) before
        calling this, and the concurrent-import guard must already have been checked.
        """
        with self._lock:
            self._cleanup_stale_queues_locked()
            q: queue_module.Queue = queue_module.Queue()
            thread = threading.Thread(
                target=self._run_thread,
                args=(import_id, date_start, date_end, dry_run, q),
                daemon=True,
                name=f"import-{import_id}",
            )
            self._registry[import_id] = {
                'queue': q,
                'thread': thread,
                'finished_at': None,
            }
            thread.start()
            logger.info("Started import thread id=%d range=%s..%s dry_run=%s",
                        import_id, date_start, date_end, dry_run)

    def get_queue(self, import_id: int) -> Optional[queue_module.Queue]:
        with self._lock:
            entry = self._registry.get(import_id)
            return entry['queue'] if entry else None

    def has_queue(self, import_id: int) -> bool:
        with self._lock:
            return import_id in self._registry

    def is_running(self, import_id: int) -> bool:
        with self._lock:
            entry = self._registry.get(import_id)
            if not entry:
                return False
            return entry['thread'].is_alive()

    # ── thread body ──────────────────────────────────────────────────────────
    def _run_thread(self, import_id: int, date_start: date, date_end: date,
                    dry_run: bool, q: queue_module.Queue) -> None:
        """Thread entry — runs DataImportService, ensures cleanup."""
        try:
            svc = DataImportService()
            svc.run_import(
                import_id=import_id,
                date_start=date_start,
                date_end=date_end,
                dry_run=dry_run,
                progress_callback=q.put,
            )
        except Exception as exc:
            logger.exception("Import %d thread crashed", import_id)
            try:
                q.put({
                    'type': 'status',
                    'status': 'failed',
                    'message': str(exc) or type(exc).__name__,
                    'timestamp': datetime.now().isoformat(),
                })
                ImportLogRepository().mark_failed(import_id, str(exc) or type(exc).__name__)
            except Exception:
                logger.exception("Could not record thread-crash failure")
        finally:
            try:
                q.put({'type': 'done', 'timestamp': datetime.now().isoformat()})
            except Exception:
                pass
            with self._lock:
                if import_id in self._registry:
                    self._registry[import_id]['finished_at'] = datetime.now()

    # ── cleanup ──────────────────────────────────────────────────────────────
    def _cleanup_stale_queues_locked(self) -> None:
        """Drop queues finished more than QUEUE_RETENTION ago. Caller holds lock."""
        now = datetime.now()
        stale = [
            iid for iid, entry in self._registry.items()
            if entry['finished_at'] is not None
            and (now - entry['finished_at']) > QUEUE_RETENTION
        ]
        for iid in stale:
            del self._registry[iid]
        if stale:
            logger.info("Reaped %d stale import queue(s)", len(stale))


# Module-level singleton
IMPORT_RUNNER = ImportRunner()
