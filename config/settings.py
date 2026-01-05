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

# Enhanced preprocessing settings (requires opencv-python)
OCR_ENHANCED_PREPROCESSING = True  # Use advanced preprocessing (OpenCV)
OCR_DENOISE_STRENGTH = 3  # Reduced: phone photos don't need heavy denoising (0-20)
OCR_DESKEW_ENABLED = True  # Auto-correct document rotation
OCR_BINARIZATION_MODE = 'otsu'  # Changed to 'otsu' - better for varied lighting
OCR_CONTRAST_ENHANCEMENT = True  # New: enhance contrast before OCR

# OCR Retry Logic - Preprocessing profiles for retry attempts
# When >3 critical fields are missing, retry with different profiles
OCR_RETRY_ENABLED = True
OCR_MAX_RETRIES = 3  # Max additional attempts after first failure
OCR_MISSING_FIELDS_THRESHOLD = 3  # Trigger retry if this many fields missing

# Preprocessing profiles for retry logic
# Each profile optimizes for different document types/conditions
OCR_PREPROCESSING_PROFILES = {
    'default': {
        'dpi': 300,
        'denoise_strength': 3,
        'binarization_mode': 'otsu',
        'clahe_clip_limit': 2.0,
        'deskew_enabled': True,
        'description': 'Standard documents, good quality scans',
    },
    'high_contrast': {
        'dpi': 300,
        'denoise_strength': 0,
        'binarization_mode': 'adaptive',
        'clahe_clip_limit': 3.5,
        'deskew_enabled': True,
        'description': 'Faded documents, low contrast, washed out text',
    },
    'high_resolution': {
        'dpi': 450,
        'denoise_strength': 5,
        'binarization_mode': 'otsu',
        'clahe_clip_limit': 2.0,
        'deskew_enabled': True,
        'description': 'Small text, poor quality scans, detailed documents',
    },
    'minimal': {
        'dpi': 300,
        'denoise_strength': 0,
        'binarization_mode': 'none',
        'clahe_clip_limit': 0,
        'deskew_enabled': False,
        'description': 'Already clean PDFs, digital-native documents',
    },
}

# Profile order for retry attempts (after default fails)
OCR_RETRY_PROFILE_ORDER = ['high_contrast', 'high_resolution', 'minimal']

# GUI settings (legacy)
APP_TITLE = "FakturaScanner"
APP_WIDTH = 1200
APP_HEIGHT = 800

# Web app settings
APP_NAME = "FakturaScanner"
VERSION = "2.0.0"
UPLOAD_FOLDER = BASE_DIR / "uploads"
PDF_FOLDER = BASE_DIR / "pdfs"

# Create upload directories
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
PDF_FOLDER.mkdir(parents=True, exist_ok=True)

# Database
DB_ECHO = False  # SQL logging

# Walidacja
VALIDATE_NIP = True
VALIDATE_IBAN = True

# Export
EXPORT_FORMATS = ["xlsx", "csv"]

# Stwórz katalogi
TEMP_DIR.mkdir(parents=True, exist_ok=True)