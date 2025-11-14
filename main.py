"""
FakturaScanner - Aplikacja do OCR faktur PDF
Entry point aplikacji
"""
import flet as ft
from gui.app import create_app

def main():
    """Główna funkcja uruchomieniowa"""
    ft.app(
        target=create_app,
        # Use FLET_APP for desktop window mode (required for file picker)
        # WEB_BROWSER mode doesn't support file.path access
        view=ft.AppView.FLET_APP,
    )


if __name__ == "__main__":
    main()