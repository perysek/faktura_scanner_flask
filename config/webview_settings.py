"""
Webview configuration settings
"""
import os
from pathlib import Path

# Webview upload directory (for files uploaded from browser)
WEBVIEW_UPLOAD_DIR = Path(__file__).parent.parent / "temp" / "webview_uploads"
WEBVIEW_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Webview server settings
WEBVIEW_PORT = 8550
WEBVIEW_HOST = "localhost"

# Secret key for file uploads (required by Flet for webview uploads)
# Set FLET_SECRET_KEY environment variable to override
# For production, use a strong random key (e.g., secrets.token_urlsafe(32))
WEBVIEW_SECRET_KEY = os.environ.get("FLET_SECRET_KEY", "faktura-scanner-local-dev-key-2024")

# View mode flag (can be used to detect if running in webview mode)
IS_WEBVIEW_MODE = False
