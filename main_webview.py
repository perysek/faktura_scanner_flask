"""
FakturaScanner - Webview Entry Point
Runs the app as a Flet webview application
"""
import flet as ft
from gui.app_webview import create_app_webview
from config.webview_settings import WEBVIEW_PORT, WEBVIEW_HOST, WEBVIEW_UPLOAD_DIR

def main():
    """Główna funkcja uruchomieniowa dla trybu webview"""
    print(f"🌐 Starting FakturaScanner in WEBVIEW mode...")
    print(f"📁 Upload directory: {WEBVIEW_UPLOAD_DIR}")
    print(f"🔗 Server will be available at: http://{WEBVIEW_HOST}:{WEBVIEW_PORT}")

    ft.app(
        target=create_app_webview,
        # WEB_BROWSER mode for webview functionality
        view=ft.AppView.WEB_BROWSER,
        # Upload directory for file uploads from browser
        upload_dir=str(WEBVIEW_UPLOAD_DIR),
        # Server settings
        port=WEBVIEW_PORT,
        host=WEBVIEW_HOST,
    )


if __name__ == "__main__":
    main()
