# Technology Stack

**Analysis Date:** 2026-03-13

## Languages

**Primary:**
- Python 3.11 - Main backend language for Flask application
- JavaScript (ES6+) - Frontend interactivity and UI enhancements
- SQL - PostgreSQL database queries

**Secondary:**
- HTML/Jinja2 - Server-side template rendering
- CSS (Tailwind) - UI styling

## Runtime

**Environment:**
- Python 3.11-slim-bookworm (Docker base image: `python:3.11-slim-bookworm`)

**Package Manager:**
- pip - Python package management
- npm - Node.js package manager for frontend dependencies

## Frameworks

**Core:**
- Flask 3.0.0 - Web framework for request handling, routing, blueprints
- Flask-Login 0.6.3 - User session management and authentication

**Templating:**
- Jinja2 (built-in Flask) - Server-side HTML template rendering

**Styling & Build:**
- Tailwind CSS 3.4.0 - Utility-first CSS framework

**Database:**
- SQLAlchemy (via Alembic) - Database migrations and schema management
- Alembic 1.13.1 - Database version control and migrations
- psycopg2-binary 2.9.9 - PostgreSQL database driver

## Key Dependencies

**Critical:**
- pytesseract 0.3.13 - OCR (Tesseract wrapper) for invoice scanning
- PyMuPDF 1.24.0 - Direct text extraction from text-based PDFs
- pdf2image 1.17.0 - PDF to image conversion for OCR processing
- opencv-python 4.8.0+ - Image preprocessing (deskewing, binarization, contrast)
- numpy 1.24.0+ - Numerical array operations for image processing
- Pillow 10.4.0 - Image library for PDF and image manipulation

**Data Processing & Export:**
- openpyxl 3.1.5 - Excel file generation for export functionality
- python-dateutil 2.9.0 - Date parsing and manipulation
- schwifty 2024.6.1 - IBAN/SEPA validation for bank account fields

**Security & Utilities:**
- bcrypt 4.1.2 - Password hashing for user authentication
- python-dotenv 1.0.1 - Environment variable management (.env files)

**Production Server:**
- gunicorn 21.2.0 - WSGI application server for production deployment

## Configuration

**Environment:**
- Configuration sources: `config/settings.py` (default paths, OCR settings)
- Environment variables: `.env` file (secrets, paths, database credentials)
- Key configs: `SECRET_KEY`, `DATABASE_URL`, `TESSERACT_CMD`, `POPPLER_PATH`, `UPLOAD_FOLDER`, `PDF_FOLDER`

**OCR Configuration:**
- OCR_DPI: 300 (default resolution for PDF→image conversion)
- OCR_ENHANCED_PREPROCESSING: True (OpenCV preprocessing enabled)
- OCR_RETRY_ENABLED: True (retry with different profiles if extraction quality is low)
- OCR_MAX_RETRIES: 3 (max additional attempts after initial failure)
- OCR_PREPROCESSING_PROFILES: 4 profiles (default, high_contrast, high_resolution, minimal)

**Build:**
- `tailwind.config.js` - Tailwind CSS configuration
- `package.json` - npm scripts for CSS building and watching

## System Dependencies (Docker)

**Required for OCR/PDF Processing:**
- tesseract-ocr - Tesseract OCR engine
- tesseract-ocr-pol - Polish language support for OCR
- poppler-utils - PDF utilities (`pdftoimage` via pdf2image)
- libgl1-mesa-glx - OpenCV graphics dependency
- libglib2.0-0 - OpenCV system dependency

**Required for Frontend Build:**
- nodejs - JavaScript runtime for Tailwind build
- npm - Package manager for npm dependencies

## Platform Requirements

**Development:**
- Python 3.11+ with pip
- Node.js 16+ with npm
- System packages: tesseract-ocr, poppler-utils (Linux) or equivalent (Windows)

**Production:**
- Docker runtime (containerized deployment)
- PostgreSQL 12+ (connected via DATABASE_URL)
- Linux server with 2GB+ RAM (Dockerfile configured for Gunicorn with memory limits)
- Port 8083 (exposed in Docker)

## Deployment Configuration

**Docker Deployment:**
- Base image: Python 3.11-slim-bookworm
- Port: 8083
- Worker configuration: 2 workers, 2 threads per worker (threaded workers for I/O)
- Timeout: 300 seconds (5 minutes for long OCR operations)
- Memory limits: 1500M per container (configurable for different VPS sizes)
- Health check: HTTP GET `/api/invoices/statistics` every 60 seconds

**Database Setup:**
- Schema initialization: `config/database.initialize_database()` (runs on app startup)
- Connection pooling: Per-request connections via Flask's g object
- Connection factory: `psycopg2.extras.RealDictCursor` (returns dicts, not tuples)

---

*Stack analysis: 2026-03-13*
