"""
Konfiguracja aplikacji
"""
import os
from pathlib import Path

# Ścieżki bazowe
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
TEMP_DIR = ASSETS_DIR / "temp"
DB_PATH = BASE_DIR / "faktury.db"

# Tesseract
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_LANG = "pol"

# Poppler (for pdf2image)
# Download from: https://github.com/oschwartz10612/poppler-windows/releases/
# Extract and set path to the bin folder
POPPLER_PATH = r"C:\poppler\Library\bin"

# OCR settings
OCR_DPI = 300  # DPI dla konwersji PDF → obrazy
OCR_PREPROCESSING = True  # Preprocessing obrazów

# GUI settings
APP_TITLE = "FakturaScanner"
APP_WIDTH = 1200
APP_HEIGHT = 800

# Database
DB_ECHO = False  # SQL logging

# Walidacja
VALIDATE_NIP = True
VALIDATE_IBAN = True

# Export
EXPORT_FORMATS = ["xlsx", "csv"]

# Stwórz katalogi
TEMP_DIR.mkdir(parents=True, exist_ok=True)