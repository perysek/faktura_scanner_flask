# Gunicorn production configuration for Vultr VPS deployment

# Network
bind = "127.0.0.1:8083"        # Nginx proxies to this; never expose directly

# Workers — single process required for in-memory state (IMPORT_RUNNER queue,
# scheduler). Thread-based concurrency handles SSE streaming + concurrent API
# requests without splitting shared state across OS processes.
workers = 1
worker_class = "gthread"
threads = 4

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
