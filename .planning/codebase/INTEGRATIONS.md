# External Integrations

**Analysis Date:** 2026-03-13

## APIs & External Services

**Email Integration:**
- IMAP email protocol - Fetch invoice PDFs from email accounts
  - SDK/Client: Python built-in `imaplib.IMAP4_SSL`
  - Configuration: `config/email_settings.py`
  - Service: `services/email_service.py` - EmailService class
  - Auth: Email address + password (stored in `config/email_config.json`)

**No third-party API integrations detected:** Project does not currently integrate with external REST APIs (Stripe, AWS, cloud SDKs, etc.)

## Data Storage

**Databases:**
- PostgreSQL (primary)
  - Connection: `DATABASE_URL` environment variable (`postgresql://user:password@host:port/dbname`)
  - Schema: `database/schema.sql` (created on app startup)
  - Connection pooling: Per-request via Flask's g object (`config/database.DatabaseConnection`)
  - Client: psycopg2 with `RealDictCursor` for dictionary results
  - Cursor factory: `psycopg2.extras.RealDictCursor`

**File Storage:**
- Local filesystem (application controlled)
  - Uploaded invoices: `UPLOAD_FOLDER` environment variable (e.g., `/opt/faktura-scanner/data/uploads`)
  - Processed PDFs: `PDF_FOLDER` environment variable (e.g., `/opt/faktura-scanner/data/pdfs`)
  - Temporary files: `TEMP_DIR` environment variable (e.g., `/opt/faktura-scanner/data/temp`)
  - In Docker: volumes mounted at `./uploads`, `./pdfs`, `./data`

**Caching:**
- None detected - No Redis, Memcached, or other caching layer

## Authentication & Identity

**Auth Provider:**
- Custom implementation (in-application)
  - Implementation: `services/auth/auth_service.py`, `config/auth_config.py`, `routes/auth/routes.py`
  - Session management: Flask-Login 0.6.3
  - Password hashing: bcrypt 4.1.2
  - User model: `models/user.py` (UserMixin from Flask-Login)
  - Database table: `users` table (stores credentials, roles, permissions)
  - Login endpoint: POST `/auth/login`
  - Logout endpoint: `/auth/logout`
  - Role-based access control: Roles (superuser, admin, accountant, receptionist, stylist) with module-level permissions

**No OAuth/OIDC integration:** Application uses custom login form, not external identity providers

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, Rollbar, or similar service)

**Logs:**
- Console/Stream logging via Python `logging` module
  - Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
  - Configuration: `app.py` (lines 19-28)
  - Debug loggers: `utils.pdf_processor`, `services.ocr_service` set to DEBUG level
  - In Docker: logs output to container stdout

**Health Monitoring:**
- Docker health check: HTTP GET to `/api/invoices/statistics` every 60 seconds
  - Endpoint defined in `routes/api_routes.py`
  - Timeout: 30 seconds per check, 3 retries

## CI/CD & Deployment

**Hosting:**
- Docker-based deployment (self-hosted)
- docker-compose 3.8 for orchestration
- Target environments: Vultr VPS (Linux) or local development

**CI Pipeline:**
- None detected - No GitHub Actions, GitLab CI, or automated testing pipeline

**Deployment Method:**
- Docker container deployment via `docker-compose`
  - Build: `docker build -t faktura_scanner .`
  - Container image: Pulls base `python:3.11-slim-bookworm`, installs system + Python + Node deps, builds app
  - Application server: Gunicorn (port 8083)
  - Startup command: `gunicorn --bind 0.0.0.0:8083 --timeout 300 --workers 2 --threads 2 --worker-class gthread app:create_app()`

## Environment Configuration

**Required env vars:**
- `SECRET_KEY` - Flask session key (must be long random string in production)
- `DATABASE_URL` - PostgreSQL connection string (format: `postgresql://user:password@host:port/dbname`)
- `TESSERACT_CMD` - Path to tesseract executable (Linux: `/usr/bin/tesseract`, Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
- `POPPLER_PATH` - Path to poppler bin directory (Linux: `/usr/bin`, Windows: `C:\poppler\Library\bin`)
- `UPLOAD_FOLDER` - Path to store uploaded PDF files
- `PDF_FOLDER` - Path to store processed PDF files
- `TEMP_DIR` - Path to temporary directory for processing

**Optional env vars:**
- `FLASK_ENV` - Environment mode (`development` or `production`, default: `production`)
- `FLASK_DEBUG` - Debug mode (default: `0` for production)

**Secrets location:**
- `.env` file (local development)
- Docker container environment variables (via `docker-compose.yml` `environment:` section or CI/CD secrets)
- Vultr/production: Environment variables set in server configuration (not in code)

**Configuration files:**
- `config/email_config.json` - Email account settings (email, password, imap_server, imap_port)
- `.env` or `.env.local` - Local development environment file (Git-ignored)
- `.env.example` - Template for required environment variables

## Webhooks & Callbacks

**Incoming:**
- None detected - Application does not receive webhooks from external services

**Outgoing:**
- None detected - Application does not send webhooks to external services

## File Processing & External Tools

**PDF Processing:**
- pytesseract 0.3.13 → Tesseract OCR engine (system binary)
- pdf2image 1.17.0 → poppler-utils (system binary)
- PyMuPDF 1.24.0 → Direct text extraction from PDFs

**Image Processing:**
- opencv-python 4.8.0+ → Image preprocessing (deskew, binarize, contrast)
- Pillow 10.4.0 → Image manipulation

## Data Import/Export

**Import Sources:**
- Email attachments (IMAP) - Fetch PDF invoices from email
  - Implementation: `services/email_service.py` (EmailService.fetch_pdf_attachments)
  - Endpoint: POST `/api/upload/from-email` (via `routes/upload_routes.py`)

**Export Formats:**
- XLSX (Excel) - openpyxl 3.1.5
  - Endpoint: `/api/invoices/export` (via `services/export_service.py`)
- CSV - CSV export capability (referenced in `config/settings.py`: `EXPORT_FORMATS = ["xlsx", "csv"]`)

**Data Validation:**
- NIP validation - Polish National Identification Number (schwifty 2024.6.1)
- IBAN validation - Bank account format (schwifty 2024.6.1)
- Configuration: `config/settings.py` (`VALIDATE_NIP = True`, `VALIDATE_IBAN = True`)

---

*Integration audit: 2026-03-13*
