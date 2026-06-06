# Gunicorn production configuration for Vultr VPS deployment
import os
import sys

# Ensure the app root is importable at config-load time, before Gunicorn adds it
# to sys.path (the runtime guard below lives in the config package).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.runtime_guards import assert_single_worker

# Network
bind = "127.0.0.1:8083"        # Nginx proxies to this; never expose directly

# Workers — single process required for in-memory state (IMPORT_RUNNER queue,
# scheduler). Thread-based concurrency handles SSE streaming + concurrent API
# requests without splitting shared state across OS processes.
workers = 1
worker_class = "gthread"
threads = 4

# Hard guard (improvement #3): refuse to boot multi-worker rather than break
# imports/SMS mysteriously at runtime. This runs in the Gunicorn master at
# config-load time (before forking), so a bad WEB_CONCURRENCY or an edited
# `workers` value aborts startup with a clear, actionable message. The invariant
# is now enforced in code, not trusted to the comment above.
assert_single_worker(workers, os.environ.get("WEB_CONCURRENCY"))

# Timeouts — OCR on high-DPI PDFs can take 60+ seconds
timeout = 180
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "/var/log/my-way-beauty-salon/access.log"
errorlog  = "/var/log/my-way-beauty-salon/error.log"
loglevel  = "info"

# Process naming (visible in `ps aux`)
proc_name = "my-way-beauty-salon"
