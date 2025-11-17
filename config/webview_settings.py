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

# View mode flag (can be used to detect if running in webview mode)
IS_WEBVIEW_MODE = False
