# Gunicorn production configuration for Vultr VPS deployment

# Network
bind = "127.0.0.1:8083"        # Nginx proxies to this; never expose directly

# Workers — 2 is safe for a 1-2 vCPU VPS; OCR is CPU-heavy so don't over-provision
workers = 2
worker_class = "sync"

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
