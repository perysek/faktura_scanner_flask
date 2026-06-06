"""
Runtime invariant guards (improvement area #3).

The app holds three pieces of in-process, in-memory state that make a single
worker process mandatory:

  * IMPORT_RUNNER — the in-memory per-import progress queue feeding the SSE
    stream (services/data_import_runner.py). The SSE endpoint must be served by
    the SAME process that owns the import's queue.
  * the APScheduler instance firing SMS every 15 minutes (scheduler.py).
  * the SSE stream itself.

Running multiple workers silently breaks imports (the browser's SSE request can
land on a worker that doesn't own the import) and — without the advisory lock in
scheduler.py — would fire SMS once per worker. Rather than let that fail
mysteriously at runtime, this guard refuses to boot multi-worker, making the
``workers == 1`` invariant explicit and enforced in code instead of a comment.
"""


def assert_single_worker(workers, web_concurrency) -> None:
    """Raise if the process is configured to run more than one worker.

    Args:
        workers: the resolved Gunicorn ``workers`` value (int).
        web_concurrency: the raw ``WEB_CONCURRENCY`` env value (str or None) —
            Gunicorn honours it, so a value > 1 is also a multi-worker request
            even when the config file says ``workers = 1``.

    Raises:
        RuntimeError: with a remediation message, if either signal asks for >1.
    """
    requested = None
    if web_concurrency not in (None, ""):
        try:
            requested = int(web_concurrency)
        except (TypeError, ValueError):
            requested = None

    if workers != 1 or (requested is not None and requested != 1):
        raise RuntimeError(
            "MyWay Beauty Salon must run with exactly ONE worker process "
            f"(got workers={workers}, WEB_CONCURRENCY={web_concurrency!r}). "
            "The data-import SSE progress stream uses an in-memory per-process "
            "queue, so a second worker would serve import progress from a "
            "process that doesn't own the import (frozen progress bar / "
            "duplicate-import conflicts). The SMS scheduler is advisory-lock "
            "guarded so it won't double-send, but the import transport is not "
            "yet externalized. Externalize import progress (DB-polling or Redis "
            "pub/sub) and move long imports to a task queue before scaling out. "
            "See IMPROVEMENT_AREAS.md #3 for the migration path."
        )
