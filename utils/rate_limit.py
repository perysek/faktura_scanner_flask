"""
Rate limiting (Flask-Limiter) for the unauthenticated, SMS-triggering endpoints.

Storage is in-process memory: correct for the one gunicorn worker production runs
(gunicorn.conf.py enforces workers == 1) but it resets on restart and is per-process —
set RATELIMIT_STORAGE_URI=redis://… before ever running more than one worker.

Keyed on the real visitor IP (`utils.client_ip`), never `remote_addr` (a Cloudflare edge).
"""
from flask_limiter import Limiter

from utils.client_ip import client_ip

limiter = Limiter(key_func=client_ip, default_limits=[], headers_enabled=False)
