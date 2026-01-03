# FakturaScanner (Gemini Context)

## 📌 Project Overview
**FakturaScanner** is a Flask-based web application designed for processing, managing, and archiving Polish invoices. It utilizes OCR (Tesseract) to extract data from PDF files, automatically validates key fields (NIP, IBAN), and provides a modern web interface for users.

**Version:** 2.0.0 (Web Migration)
**Status:** Production-ready (Migrated from Flet)

## 🛠 Tech Stack
- **Backend:** Python 3.11+, Flask 3.0.0
- **Database:** SQLite (managed via raw SQL in `database/schema.sql` and repositories)
- **Frontend:** Jinja2 Templates, TailwindCSS 3.4, Vanilla JavaScript
- **OCR Engine:** Tesseract OCR (with `pdf2image` and `opencv-python` preprocessing)
- **Email Integration:** `imaplib` for fetching invoices from email

## 📂 Project Structure
```
faktura_scanner_flask/
├── app.py                     # Application entry point (Factory pattern)
├── config/                    # Configuration (Settings, Database)
├── database/                  # SQL Schema and Models
├── repositories/              # Data Access Layer (CRUD)
├── services/                  # Business Logic (OCR, Validation, Email)
├── routes/                    # Flask Blueprints (Main, API, Upload)
├── templates/                 # HTML Templates (Jinja2)
├── static/                    # Static Assets (CSS, JS)
│   ├── css/
│   │   ├── input.css          # Tailwind Source (Edit this)
│   │   └── output.css         # Compiled CSS (Do not edit)
│   └── js/                    # Modular JavaScript
├── uploads/                   # Temporary storage for uploads
├── pdfs/                      # Permanent storage for processed PDFs
├── requirements.txt           # Python dependencies
├── package.json               # Node.js dependencies (Tailwind)
└── tailwind.config.js         # Tailwind configuration
```

## 🚀 Building and Running

### Prerequisites
1.  **System Dependencies (Windows):**
    *   **Tesseract OCR:** Installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`
    *   **Poppler:** Installed at `C:\poppler\Library\bin`
    *   **Tesseract Language Data:** `pol.traineddata` must be present.
2.  **Node.js:** Required for building TailwindCSS.

### Setup Commands
1.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Install Node.js Dependencies:**
    ```bash
    npm install
    ```

### Development Workflow
1.  **Build CSS (One-time):**
    ```bash
    npm run build:css
    ```
2.  **Watch CSS (Background process for UI dev):**
    ```bash
    npm run watch:css
    ```
3.  **Run Application:**
    ```bash
    python app.py
    ```
    *   Server starts at `http://localhost:8083` (Debug mode enabled)

## 🏗 Architecture & Conventions

### Design Pattern
The application follows a **Service-Repository** pattern:
*   **Routes (`routes/`)**: Handle HTTP requests/responses and delegate to Services.
*   **Services (`services/`)**: Contain business logic (OCR, Validation, Duplicate Check).
*   **Repositories (`repositories/`)**: Handle direct database interactions.

### Database
*   **Schema**: Defined in `database/schema.sql`.
*   **Key Tables**: `invoices`, `sellers`, `audit_log`, `upload_staging`.
*   **Access**: Raw SQL queries via Repositories (no ORM used).

### Frontend Development
*   **Styling**: Use **TailwindCSS**.
    *   **Edit:** `static/css/input.css`
    *   **Build:** `npm run build:css`
    *   **Do NOT Edit:** `static/css/output.css`
*   **JavaScript**: Vanilla JS using modular files in `static/js/`.
*   **UI Components**: Uses a custom "Workflow Step" indicator, Breadcrumbs, and Modal system.

### Configuration (`config/settings.py`)
*   **Paths**: `UPLOAD_FOLDER`, `PDF_FOLDER`, `TEMP_DIR`.
*   **OCR**: Configurable DPI (`300`), Preprocessing (`True`), and Tesseract path.
*   **Validation**: Flags for `VALIDATE_NIP` and `VALIDATE_IBAN`.

## 🔍 Key Workflows
1.  **Upload/Import**:
    *   User uploads PDF or imports via Email.
    *   Files are staged in `upload_staging`.
    *   Files are processed (OCR) -> Data extracted -> Validated.
    *   User reviews and saves to `invoices`.
2.  **Duplicate Detection**:
    *   Checks `invoice_number` and fuzzy matches on `seller_name` + `amount` + `date`.
3.  **Audit Trail**:
    *   Changes to invoices are logged in `audit_log` (Old Value -> New Value).

## ⚠️ Critical Notes
*   **Secrets**: `SECRET_KEY` is loaded from env vars (defaults to dev key).
*   **Email**: Credentials stored in `config/email_config.json` (Ensure this is gitignored).
*   **Localization**: UI is in **Polish**. Code/Comments are mixed (mostly English).
