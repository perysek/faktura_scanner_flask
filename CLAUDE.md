# 🧾 FakturaScanner - Agent Guide for Claude Code CLI

## 📌 Project Overview

**FakturaScanner** is a modern Flask web application for OCR processing of Polish PDF invoices. It extracts structured data (seller, invoice number, date, amount, bank account, etc.) using Tesseract OCR and stores results in SQLite database. Features email integration for automatic PDF import from IMAP mailboxes and a responsive TailwindCSS-based UI.

**Migration Status:** Successfully migrated from Flet (Python GUI) to Flask web application (2025-11-29)

**Stack:**
- Python 3.11+ (Flask 3.0.0)
- Flask + Jinja2 templates for server-side rendering
- TailwindCSS 3.4.0 for responsive styling
- Vanilla JavaScript with Fetch API for AJAX interactions
- Material Icons for consistent iconography
- Tesseract OCR + Polish language data
- SQLite database
- pdf2image, pytesseract, openpyxl
- imaplib (email IMAP integration)

**Target Users:** Single local user, no authentication required (accessible at http://localhost:5000)

---

## 🏗️ Architecture

### **Layered Architecture:**
```
Web Browser (HTML/CSS/JS)
    ↓
Flask Routes (blueprints)
    ↓
Services (business logic)
    ↓
Repositories (data access)
    ↓
SQLite Database
```

### **Project Structure:**
```
faktura_scanner_flask/
├── app.py                     # Entry point (Flask application factory)
├── requirements.txt           # Python dependencies
├── package.json              # Node.js dependencies (TailwindCSS)
├── tailwind.config.js        # TailwindCSS configuration
│
├── config/                    # Configuration
│   ├── settings.py            # App settings (paths, OCR params, version)
│   ├── database.py            # SQLite connection singleton, schema initialization
│   └── (no email_settings.py) # Email settings now in database
│
├── database/                  # Data layer
│   ├── models.py              # Dataclass models (Invoice, AuditEntry)
│   └── schema.sql             # SQL schema (invoices, audit_log, duplicate_detection)
│
├── repositories/              # Data access (CRUD)
│   ├── base_repository.py     # Base repository with common CRUD
│   ├── invoice_repository.py  # Invoice-specific queries
│   └── audit_repository.py    # Audit log operations
│
├── services/                  # Business logic
│   ├── ocr_service.py         # Orchestrates PDF → text → Invoice
│   ├── validation_service.py  # NIP, IBAN validation
│   ├── duplicate_detection_service.py
│   ├── export_service.py      # Excel/CSV export
│   └── email_service.py       # IMAP email integration for PDF download
│
├── utils/                     # Helpers
│   ├── pdf_processor.py       # PDF → images, Tesseract OCR
│   ├── text_extractor.py      # Regex patterns for Polish invoices
│   └── validators.py          # NIP checksum, IBAN mod-97
│
├── routes/                    # Flask blueprints
│   ├── __init__.py           # Routes package
│   ├── main_routes.py        # Page routes (HTML views)
│   └── api_routes.py         # API endpoints (JSON responses)
│
├── templates/                 # Jinja2 HTML templates
│   ├── base.html             # Base layout with navigation sidebar
│   ├── invoices/
│   │   ├── list.html         # Invoice list view (table with search)
│   │   ├── upload.html       # Upload & processing view (drag-drop, email import)
│   │   └── edit.html         # Edit invoice form
│   ├── history/
│   │   └── list.html         # Audit trail view
│   ├── settings/
│   │   └── email.html        # Email configuration
│   └── errors/
│       ├── 404.html
│       └── 500.html
│
├── static/                    # Static assets
│   ├── css/
│   │   ├── input.css         # TailwindCSS source
│   │   └── output.css        # TailwindCSS compiled (generated)
│   └── js/                   # Vanilla JavaScript
│       ├── api.js            # API wrapper (GET, POST, PUT, DELETE)
│       ├── utils.js          # Utility functions (format, validate, XSS escape)
│       ├── notifications.js  # Toast notification system
│       ├── modals.js         # Modal dialog system
│       └── invoices/
│           ├── list.js       # Invoice list page interactivity
│           └── upload.js     # File upload and processing
│
└── WEB_APP_README.md         # Migration documentation and setup guide
```

---

## 🎨 Design Principles

### **Web UI (TailwindCSS):**
- **Layout:** Left sidebar (260px) + main content area with flexbox
- **Font:** Roboto via Google Fonts (Material Design default)
- **Colors:** Light backgrounds (#F5F7FA, #FFFFFF) + blue accents (#4472C4)
- **Style:** Minimal, modern, card-based UI with shadow effects
- **Responsiveness:** Responsive design with Tailwind breakpoints (works mobile, tablet, desktop)
- **Icons:** Material Icons from Google Fonts (consistent iconography)

### **Language:**
- The application's user interface and all user-facing strings must be in **Polish**.

### **CSS Architecture (TailwindCSS):**
- **Input Source:** `static/css/input.css` - Contains Tailwind directives and custom components
- **Output Generated:** `static/css/output.css` - Auto-generated by tailwind CLI (do not edit)
- **Custom Components:** Defined in `@layer components` (buttons, cards, tables, badges, modals, toasts)
- **Build Command:** `npm run build:css` - One-time minified build
- **Watch Mode:** `npm run watch:css` - Development auto-rebuild on template/js changes

### **TailwindCSS Custom Components:**
- `.btn-primary`, `.btn-secondary`, `.btn-success`, `.btn-danger`, `.btn-warning` - Button variants
- `.card` - Card styling (white background, rounded, shadow, padding)
- `.badge-success`, `.badge-warning`, `.badge-error`, `.badge-info` - Status badges
- `.table`, `.table thead`, `.table th`, `.table td` - Table styling
- `.modal-overlay`, `.modal-content`, `.modal-header`, `.modal-body`, `.modal-footer` - Modal components
- `.toast`, `.toast-success`, `.toast-error`, `.toast-warning`, `.toast-info` - Toast notifications
- `.nav-link`, `.nav-link.active` - Navigation links with active state

### **Color Palette:**
- Primary: `#4472C4` (blue)
- Success: `#28A745` (green)
- Warning: `#FFC107` (orange)
- Error: `#DC3545` (red)
- Info: `#17A2B8` (cyan)
- Surface: `#FFFFFF` (white), `#F5F7FA` (light grey)

### **Frontend Architecture (JavaScript):**
- **Modular structure** with separate JS files for different concerns
- **API wrapper** (`api.js`) provides consistent fetch abstraction
- **Vanilla JavaScript** (no frameworks) for lightweight footprint
- **Utility functions** (`utils.js`) for date/currency formatting, XSS escaping, HTML manipulation
- **Notification system** (`notifications.js`) for toast messages
- **Modal system** (`modals.js`) for dialogs and confirmations
- **Page-specific JS** (`invoices/list.js`, `invoices/upload.js`) for view logic

### **Template System (Jinja2):**
- **Inheritance:** `base.html` provides layout with sidebar, all pages extend it
- **Block structure:** `{% block title %}`, `{% block page_title %}`, `{% block content %}`, `{% block extra_scripts %}`
- **Sidebar navigation:** Active link highlighting with `{% if request.endpoint == 'main.page_name' %}active{% endif %}`
- **Global context:** App name and version injected via Flask context processor
- **Material Icons:** Used in navigation, buttons, tables, and status badges

### **Route Structure:**
- **Main routes** (`routes/main_routes.py`): Render HTML templates
  - `/` or `/invoices` → Invoice list view
  - `/upload` → Upload and processing view
  - `/invoice/<id>/edit` → Edit invoice form
  - `/history` → Audit trail view
  - `/settings/email` → Email configuration
- **API routes** (`routes/api_routes.py`): Return JSON responses
  - `GET/POST /api/invoices` - CRUD operations
  - `GET /api/invoices/statistics` - Dashboard statistics
  - `POST /api/upload` - File upload and processing
  - `POST /api/email/import` - Import from email
  - `GET /api/export/excel` - Export invoices

### **Frontend JavaScript Patterns:**

1. **API Wrapper Usage:**
```javascript
// API module provides consistent interface
const data = await API.invoices.getAll(searchQuery);
const response = await API.upload.files(fileList, onProgress);
const result = await API.put('/invoices/123', { field: value });
```

2. **Utility Functions:**
```javascript
// Format date and currency in Polish locale
formatDate(dateString)           // "2024-11-29"
formatCurrency(amount, currency) // "1 234,56 zł"

// Security
escapeHtml(text)  // Prevent XSS in dynamic HTML
getCsrfToken()    // Get CSRF token from meta tag

// File handling
formatFileSize(bytes) // "2.5 MB"
```

3. **Notifications:**
```javascript
Notifications.init();  // Initialize system on page load
Notifications.success('Saved successfully');
Notifications.error('An error occurred');
Notifications.warning('Warning message');
Notifications.info('Info message');
```

4. **Modals:**
```javascript
Modals.show({
    title: 'Confirm Delete',
    content: 'Are you sure?',
    size: 'medium',  // small, medium, large
    buttons: [
        { label: 'Cancel', onClick: (e) => {...} },
        { label: 'Delete', onClick: (e) => {...} }
    ]
});
```

### **Code Style (Flask/Python):**
- **Type hints:** Use for function signatures
- **Docstrings:** For classes and public methods (Polish language)
- **Error handling:** Try-except with user-friendly messages via API responses
- **Separation of concerns:** Routes → Services → Repositories → Database

---

## 🧭 Navigation Structure

The application uses a left sidebar with 5 main navigation links:

1. **LISTA FAKTUR** (Invoice List - `/invoices`)
   - HTML: `templates/invoices/list.html`
   - JavaScript: `static/js/invoices/list.js`
   - Features:
     - Invoice table with sortable columns
     - Search by invoice number, seller name, NIP
     - Statistics dashboard (totals, paid/unpaid, amounts by currency)
     - Export to Excel/CSV
     - Actions: Edit, Delete invoice (via modals)

2. **IMPORT PDF** (Upload & Processing - `/upload`)
   - HTML: `templates/invoices/upload.html`
   - JavaScript: `static/js/invoices/upload.js`
   - Features:
     - Drag-and-drop PDF upload area
     - File picker for local PDFs
     - Email import integration (IMAP)
     - File list with sizes
     - Batch processing with progress
     - Validation results table
     - Save to database button

3. **HISTORIA** (Audit Trail - `/history`)
   - HTML: `templates/history/list.html`
   - Features:
     - Audit log viewer showing all changes
     - Field changes with old/new values
     - Timestamps for modifications
     - Optional invoice filter

4. **USTAWIENIA E-MAIL** (Email Settings - `/settings/email`)
   - HTML: `templates/settings/email.html`
   - Features:
     - IMAP server configuration form
     - Email address and password fields
     - Port settings (default 993 for SSL)
     - Date range filter for email search
     - Test connection button
     - Save configuration to database

5. **Error Pages**
   - `/errors/404.html` - Page not found
   - `/errors/500.html` - Server error

---

## 🔧 Key Implementation Details

### **OCR Pipeline (Sequential Processing):**
```
1. User selects multiple PDFs (via file picker OR email import)
   - File picker: Select local PDF files
   - Email import: Connect to IMAP, download PDF attachments from date range
2. UploadView displays file list with file names and sizes
3. User clicks "Przetwórz wszystkie"
4. For each PDF (sequentially with progress bar):
   a. Copy to temp/
   b. PDFProcessor: PDF → images → Tesseract OCR → raw text
   c. TextExtractor: raw text → regex patterns → structured data
   d. ValidationService: validate NIP, IBAN, required fields
   e. DuplicateService: check by invoice_number
   f. Add to processing results
5. Display ProcessingResultsTable with:
   - Status icons (green=OK, yellow=warnings, red=errors)
   - Invoice data (seller, number, date, amount, NIP, due date)
   - OCR confidence badge (color-coded: green≥80%, yellow≥60%, red<60%)
   - Warnings/errors column with expandable details
   - Action buttons: View OCR, Delete, Save (disabled if errors)
6. User reviews, views raw OCR text if needed, saves individually or all at once
```

### **Email Import Feature:**
- IMAP integration via `EmailService` (services/email_service.py)
- Configuration stored in `config/email_config.json` (via EmailSettings)
- EmailSettingsView for managing connection settings
- Supports date range filtering for email search
- Downloads PDF attachments to TEMP_DIR
- Progress updates during email processing
- File handle management for Windows compatibility (delays + retries)

### **ProcessingResultsTable Component:**
- Compact DataTable showing processed invoices
- Columns: Status, Sprzedawca, Nr Faktury, Data, Kwota, NIP, Termin, OCR, Ostrzeżenia, Akcje
- Color-coded OCR confidence:
  - Green badge (≥80%): High confidence
  - Yellow badge (60-79%): Medium confidence
  - Red badge (<60%): Low confidence
- Warnings/Errors column:
  - Shows first 2 warnings with ellipsis if more
  - Error icon (red) for validation errors
  - Warning icon (orange) for validation warnings
- Action buttons:
  - View OCR: Opens modal with raw OCR text
  - Delete: Removes from processing queue
  - Save: Saves to database (disabled if validation errors present)
- Usage: `ProcessingResultsTable(processed_invoices, on_delete, on_save, on_view_ocr)`

### **Regex Patterns (Polish Invoices):**
Located in `utils/text_extractor.py`:
- Invoice number: `FV/123/2024`, `FA-100-24`
- NIP: `123-456-78-90` or `1234567890`
- IBAN: `PL 12 1234 1234 1234 1234 1234 1234`
- Amount: `1 234,56 zł` or `1234.56 PLN`
- Dates: `2024-11-12`, `12.11.2024`, `12/11/2024`

**To add new pattern:**
```python
PATTERNS = {
    'invoice_number': [
        r'existing pattern',
        r'new pattern here',  # Add comment explaining format
    ],
}
```

### **Validation:**
- **NIP:** 10-digit checksum validation (weights: 6,5,7,2,3,4,5,6,7)
- **IBAN:** Polish format `PL + 26 digits`, mod-97 algorithm
- **Errors** block save, **warnings** allow save

### **Flet Modal Dialogs & Snackbars:**

**CRITICAL: Proper Dialog Pattern (Lesson Learned)**

Flet dialogs MUST be implemented correctly or they won't display at all. Here's the working pattern:

#### **✅ CORRECT Pattern:**
```python
class MyView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page

        # 1. Create dialog instance variables (initialized as None)
        self.delete_dialog = None
        self.info_dialog = None
        self.current_item_to_delete = None

    def delete_item(self, item):
        """Delete confirmation dialog"""
        # Store item reference
        self.current_item_to_delete = item

        # 2. Create dialog once (lazy initialization)
        if self.delete_dialog is None:
            self.delete_dialog = ft.AlertDialog(
                modal=True,  # REQUIRED for proper modal behavior
                title=ft.Text("Confirmation", weight=ft.FontWeight.BOLD),
                content=ft.Text(""),  # Will be updated dynamically
                actions=[
                    ft.TextButton("Cancel", on_click=self.cancel_delete),
                    ft.TextButton("Delete", on_click=self.confirm_delete,
                                style=ft.ButtonStyle(color=AppColors.ERROR)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

        # 3. Update content dynamically
        self.delete_dialog.content = ft.Text(f"Delete {item.name}?")

        # 4. Open dialog (CRITICAL ORDER)
        self.page.dialog = self.delete_dialog  # Assign to page.dialog
        self.delete_dialog.open = True          # Set open = True
        self.page.update()                      # Update page

    def cancel_delete(self, e):
        """Close dialog"""
        self.delete_dialog.open = False
        self.page.update()
        self.current_item_to_delete = None

    def confirm_delete(self, e):
        """Execute delete and close dialog"""
        if self.current_item_to_delete:
            # Do deletion
            self.repo.delete(self.current_item_to_delete.id)

            # Close dialog
            self.delete_dialog.open = False
            self.page.update()

            # Show success snackbar
            self.show_success("Deleted", f"Item deleted successfully")

            # Cleanup
            self.current_item_to_delete = None
```

#### **✅ Snackbar Pattern:**
**IMPORTANT**: Snackbars also require the same lazy initialization pattern as dialogs to work reliably.

```python
class MyView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page

        # 1. Create snackbar instance variables (initialized as None)
        self.success_snackbar = None
        self.error_snackbar = None

def show_success(self, title: str, message: str):
    """Show success snackbar"""
    # 2. Lazy initialization
    if self.success_snackbar is None:
        self.success_snackbar = ft.SnackBar(
            content=ft.Text(""),
            bgcolor=AppColors.SUCCESS,
        )

    # 3. Update content dynamically
    self.success_snackbar.content = ft.Text(f"{title}: {message}")

    # 4. Show snackbar
    self.page.snack_bar = self.success_snackbar
    self.success_snackbar.open = True
    self.page.update()

def show_error(self, title: str, message: str):
    """Show error snackbar"""
    # Lazy initialization
    if self.error_snackbar is None:
        self.error_snackbar = ft.SnackBar(
            content=ft.Text(""),
            bgcolor=AppColors.ERROR,
        )

    # Update content
    self.error_snackbar.content = ft.Text(f"{title}: {message}")

    # Show snackbar
    self.page.snack_bar = self.error_snackbar
    self.error_snackbar.open = True
    self.page.update()
```

#### **❌ WRONG Patterns (Will NOT work):**
```python
# ❌ Creating dialog inline without storing reference
dialog = ft.AlertDialog(...)
self.page.dialog = dialog
dialog.open = True
self.page.update()
# Problem: Dialog object gets garbage collected

# ❌ Creating snackbar inline without storing reference
snackbar = ft.SnackBar(content=ft.Text("..."), bgcolor=AppColors.SUCCESS)
self.page.snack_bar = snackbar
snackbar.open = True
self.page.update()
# Problem: Snackbar object gets garbage collected and won't display

# ❌ Missing modal=True
dialog = ft.AlertDialog(title=..., content=...)  # No modal=True
# Problem: Dialog may not display properly or backdrop won't work

# ❌ Using page.overlay.append() AND page.dialog
self.page.overlay.append(dialog)  # Don't do this
self.page.dialog = dialog          # Only use page.dialog
# Problem: Creates duplicate modal backdrops

# ❌ Wrong open pattern
self.page.dialog.open = True  # Don't use page.dialog.open
# Correct: dialog.open = True (use dialog object reference)

# ❌ Not calling page.update()
dialog.open = True  # Missing: self.page.update()
# Problem: Dialog state change won't be reflected in UI
```

#### **Key Rules:**
1. **Store dialogs AND snackbars as instance variables** (`self.dialog = None`, `self.success_snackbar = None`)
2. **Use lazy initialization** (create on first use with `if self.dialog is None`)
3. **Always include `modal=True`** in AlertDialog constructor
4. **Update content dynamically** for reusable dialogs and snackbars
5. **Three-step open (dialogs):** `page.dialog = dialog`, `dialog.open = True`, `page.update()`
6. **Three-step open (snackbars):** `page.snack_bar = snackbar`, `snackbar.open = True`, `page.update()`
7. **Two-step close:** `dialog.open = False`, `page.update()`
8. **Never use `page.overlay.append()`** for AlertDialog (only for page.dialog)
9. **Store state** if dialog needs to remember context (e.g., `self.current_item_to_delete`)

#### **Why This Pattern?**
- Flet dialogs and snackbars require persistent object references (can't be garbage collected)
- `modal=True` enables proper backdrop and focus management for dialogs
- `page.dialog` is the official way to display dialogs (not overlay)
- `page.snack_bar` is the official way to display snackbars
- Lazy initialization allows dynamic content updates while reusing same dialog/snackbar
- Separate handler methods (cancel/confirm) keep code clean and testable
- Without persistent references, UI elements may not appear at all

### **Database Schema:**
```sql
invoices (id, seller_name, seller_nip, invoice_number UNIQUE,
          invoice_date, bank_account, amount, currency,
          payment_due_date, payment_term, status DEFAULT 'Nieopłacona',
          pdf_path, ocr_confidence, is_duplicate,
          created_at, updated_at)

audit_log (id, invoice_id, field_name, old_value, new_value, changed_at)

duplicate_detection (id, invoice_id, duplicate_of, similarity_score, detected_at)
```

**New Fields:**
- `payment_term`: TEXT - Payment terms (e.g., "7 dni", "14 dni")
- `status`: TEXT - Payment status ("Nieopłacona", "Opłacona", "Przeterminowana")

---

<!-- AUTO:BUILD_COMMANDS -->
## 🚀 Build & Run Commands

```bash
# 1. Python environment setup
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 2. Node.js dependencies (TailwindCSS)
npm install

# 3. Build CSS (TailwindCSS)
npm run build:css             # One-time minified build
# npm run watch:css           # Development mode (auto-rebuild)

# 4. Initialize database (auto on first run, or manually)
python -c "from config.database import initialize_database; initialize_database()"

# 5. Run Flask application
python app.py                  # Starts at http://localhost:5000

# Development: Run TailwindCSS watcher in separate terminal
npm run watch:css
```

### **System Dependencies:**
- Tesseract OCR: `C:\Program Files\Tesseract-OCR\` (Windows)
- Poppler: `C:\poppler\Library\bin` (Windows - for pdf2image)
- Polish language data: `tessdata/pol.traineddata`
<!-- /AUTO:BUILD_COMMANDS -->

---

## 🚀 Common Tasks

### **Adding a new field to invoices:**
1. Update `database/schema.sql` (add column)
2. Update `database/models.py` (Invoice dataclass)
3. Update `repositories/invoice_repository.py` (create/update methods)
4. Add regex pattern to `utils/text_extractor.py`
5. Update `routes/api_routes.py` (if exposed via API)
6. Update table template or form template
7. Update `services/export_service.py` (Excel/CSV headers)

### **Improving OCR accuracy:**
- Increase `OCR_DPI` in `config/settings.py` (default 300)
- Enable preprocessing in `utils/pdf_processor.py::preprocess_image()`
- Add more regex patterns in `utils/text_extractor.py`

### **Adding a new page/route:**
1. Create route in `routes/main_routes.py` (for HTML) or `routes/api_routes.py` (for JSON)
2. Create template in `templates/` if HTML response
3. Create/update JavaScript in `static/js/` if needed
4. Add navigation link in `templates/base.html` sidebar
5. Run `npm run watch:css` to rebuild styles for new template

### **Debugging PDF/OCR extraction:**
```python
# In routes/api_routes.py or services/ocr_service.py, add:
import logging
logger = logging.getLogger(__name__)

logger.debug("=== RAW OCR TEXT ===")
logger.debug(raw_text)
logger.debug("=== EXTRACTED DATA ===")
logger.debug(extracted_data)
```

### **Working with TailwindCSS:**
- **Add new class:** Define in `static/css/input.css` under `@layer components`
- **Watch mode:** `npm run watch:css` (rebuilds output.css when templates/js change)
- **Production build:** `npm run build:css` (minified output.css)
- **Custom colors:** Edit `tailwind.config.js` theme section

### **Setting up email import API:**
```python
from services.email_service import EmailService

email_service = EmailService()
if email_service.connect(email, password, imap_server, imap_port):
    pdf_files = email_service.fetch_pdf_attachments(
        from_date=date(2024, 1, 1),
        to_date=date(2024, 12, 31),
        save_dir=TEMP_DIR,
        progress_callback=lambda p: print(f"{p}%")
    )
    email_service.disconnect()
```

---

## ⚠️ Important Constraints

### **What NOT to do:**
1. **Never hardcode paths** - always use constants from `config/settings.py`
2. **Never skip validation** before saving invoices
3. **Never commit sensitive files:**
   - Database files (`*.db`)
   - Email credentials or config files
   - Environment files (`.env`)
4. **Never edit `static/css/output.css` directly** - it's auto-generated by TailwindCSS
   - Edit `static/css/input.css` instead
   - Run `npm run build:css` or `npm run watch:css` after changes
5. **Never block request** with long-running operations
   - Use `current_app` to access app context in async handlers
   - Return progress response immediately, process asynchronously if needed
6. **Never expose error details** to frontend in production
   - Log errors server-side
   - Return generic error messages to client
7. **Never modify database schema directly** - always update `database/schema.sql` and run migrations

### **System Dependencies:**
- **Tesseract OCR:** `C:\Program Files\Tesseract-OCR\` (Windows)
- **Polish language data:** `tessdata/pol.traineddata`
- **Poppler:** `C:\poppler\Library\bin` (Windows - required for pdf2image)
- **Node.js:** Required for TailwindCSS build process
- **Python 3.11+:** Required for Flask app

---

## 🧪 Testing

### **Manual test flow:**
1. **Setup:**
   - `npm install && npm run build:css`
   - `pip install -r requirements.txt`
   - `python app.py` (starts at http://localhost:5000)

2. **Test Invoice List Page:**
   - Verify sidebar navigation shows active link
   - Check table loads with sample data
   - Test search functionality with debounce
   - Verify statistics dashboard shows correct totals
   - Test export to Excel/CSV

3. **Test Upload Page:**
   - Drag-and-drop PDF file to upload area
   - Verify file list shows with sizes
   - Click "Przetwórz wszystkie" and verify processing
   - Check notifications appear for success/errors

4. **Test Email Integration (optional):**
   - Navigate to "USTAWIENIA E-MAIL"
   - Enter IMAP credentials
   - Click "Test connection"
   - Save configuration
   - Return to "IMPORT PDF" and test email import

5. **Test Invoice Editing:**
   - Click "Edit" on an invoice → verify form loads
   - Modify field → save
   - Navigate back to list and verify changes
   - Test delete with confirmation modal

6. **Test Audit Trail:**
   - Navigate to "HISTORIA"
   - Verify entries show recent changes
   - Check timestamp and field changes are logged

7. **Test Error Handling:**
   - Upload invalid file (non-PDF) → verify error notification
   - Test validation errors on save
   - Navigate to non-existent invoice → verify 404 page

### **Test Sample Data:**
Create Polish invoice PDF with:
```
FAKTURA VAT
Nr: FV/2024/001
Sprzedawca: ABC Sp. z o.o.
NIP: 1234567890
Konto: PL 12 1234 1234 1234 1234 1234 1234
Kwota: 1845,00 PLN
Data: 2024-11-12
```

---

## 🔒 Security Considerations

### **Email Credentials Storage:**
- Stored in plaintext in `config/email_config.json` (local file)
- **IMPORTANT:** Add `config/email_config.json` to `.gitignore`
- **NEVER** commit email credentials to version control
- For production: Consider encryption or OS keyring integration
- Recommended: Use app-specific passwords (not main email password)
  - Gmail: Generate at https://myaccount.google.com/apppasswords
  - Other providers: Check provider-specific app password settings

### **IMAP Security:**
- Always uses SSL/TLS (IMAP4_SSL) on port 993
- Validates server certificates
- Connection test available before saving credentials
- Timeout handling for network issues

### **File Access:**
- PDF files stored in `TEMP_DIR` with read/write permissions
- No arbitrary file access - only user-selected or email-downloaded PDFs
- File existence checks before opening
- Cross-platform path handling via `pathlib.Path`

---

## ✅ Recently Implemented Features

**Web Application (2025-11-29 Migration):**
- ✅ Flask web application with Jinja2 templates
- ✅ TailwindCSS responsive styling framework
- ✅ Vanilla JavaScript with Fetch API (no frameworks)
- ✅ Material Icons integration for UI consistency
- ✅ Left sidebar navigation with active link highlighting
- ✅ Toast notification system (success, error, warning, info)
- ✅ Modal dialog system for confirmations and forms
- ✅ Responsive design (mobile, tablet, desktop compatible)
- ✅ Invoice list page with sortable table and search
- ✅ Upload page with drag-and-drop PDF support
- ✅ Email integration page for IMAP configuration
- ✅ History/audit log page with change tracking
- ✅ Error pages (404, 500)
- ✅ API endpoints for all CRUD operations
- ✅ File upload with progress tracking
- ✅ Excel/CSV export functionality

**Core Features (Preserved from Flet):**
- ✅ Email IMAP integration for automatic PDF import
- ✅ PDF OCR extraction using Tesseract
- ✅ Payment status tracking (Nieopłacona, Opłacona)
- ✅ Payment terms field
- ✅ OCR confidence color-coded badges
- ✅ Detailed validation warnings/errors display
- ✅ Audit trail for all invoice changes

## 🔮 Future Enhancements

**Architecture-ready for future development:**
- Background queue processing (Celery/RQ for async jobs)
- Retry mechanism for failed OCR
- AI/LLM integration (Claude, GPT-4 Vision) for better extraction
- In-app PDF viewer component
- Batch operations (bulk edit, bulk delete)
- Advanced filters (date range, amount range)
- Email OAuth2 authentication (currently password-based)
- Dark mode support
- Multi-user authentication and role-based access
- Webhook integrations for third-party services

---

## 📞 When to Ask for Clarification

**Always ask before:**
- Changing database schema (breaking change)
- Adding new external dependencies
- Modifying OCR regex patterns (test first!)
- Changing validation rules
- Removing existing features

**Questions to ask:**
- "Should this override the default `card()` padding?"
- "Do you want errors or warnings for this validation?"
- "Should this be synchronous or background processing?"
- "What regex pattern format should I support?"

---

## 🎯 Project Goals

**Primary:** Reliable, fast, local OCR for Polish invoices  
**Secondary:** Scalable architecture for future SaaS deployment  
**Tertiary:** Clean, maintainable code for learning purposes

---

## 📚 Key Documentation

- Flet: https://flet.dev/docs/
- Tesseract: https://tesseract-ocr.github.io/
- Polish NIP validation: https://pl.wikipedia.org/wiki/NIP#Sprawdzanie_poprawności_numeru
- IBAN validation: https://en.wikipedia.org/wiki/International_Bank_Account_Number#Validating_the_IBAN

---

<!-- AUTO:CODE_PATTERNS -->
## 💡 Code Patterns & Conventions

### **Naming Conventions**
- **Files/modules:** `snake_case` (e.g., `ocr_service.py`, `invoice_table.py`)
- **Classes:** `PascalCase` (e.g., `OCRService`, `InvoiceTable`, `AppColors`)
- **Functions/variables:** `snake_case` (e.g., `process_invoice_pdf`, `raw_text`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `TEMP_DIR`, `OCR_DPI`)

### **Type Hints**
- Use type hints for all function signatures
- Use `Optional[T]` for nullable types
- Use `tuple[A, B]` for tuples (Python 3.11+ syntax)
- Example: `def process_invoice_pdf(self, pdf_path: str) -> tuple[Invoice, str]:`

### **Imports**
- Absolute imports from project root (e.g., `from database.models import Invoice`)
- Standard library imports first, then third-party, then local
- Group imports by category

### **Docstrings**
- Polish language docstrings for all classes and public methods
- Clear parameter descriptions and return values
- Example: `"""Przetworz PDF faktury - Returns: (Invoice object, raw_text)"""`

### **Error Handling**
- Try-except blocks with user-friendly messages
- Use notification panel for user feedback
- Never silent failures (`except: pass`)

### **Style Patterns**

**Good:**
```python
# Use theme constants
ft.Container(**AppStyles.card())  # No padding= unless overriding

# Override padding correctly
card_styles = AppStyles.card()
card_styles['padding'] = AppSpacing.XXL  # Override: larger padding for upload area
ft.Container(**card_styles)

# Clear error messages
self.show_error("Błąd walidacji", "\n".join(validation['errors']))

# Type hints
def create_invoice(self, invoice: Invoice) -> int:
```

**Bad:**
```python
# Hardcoded colors
ft.Container(bgcolor="#FFFFFF")  # Use AppColors.SURFACE

# Duplicate padding - CAUSES RUNTIME ERROR
ft.Container(**AppStyles.card(), padding=AppSpacing.MD)

# Using elevation with Container - CAUSES RUNTIME ERROR
ft.Container(elevation=2)  # Use shadow= instead

# Silent failures
try:
    something()
except:
    pass  # Don't hide errors!
```
<!-- /AUTO:CODE_PATTERNS -->

---

<!-- AUTO:METADATA -->
**Last Updated:** 2025-11-29
**Version:** 2.0.0
**Status:** Production-ready Flask web application with full feature parity to Flet version
**Migration Completed:** From Flet (Python GUI) to Flask (Web application)

**Architecture Changes:**
- Migrated from Flet 0.28.3 (desktop GUI) to Flask 3.0.0 (web framework)
- Server-side rendering with Jinja2 templates
- TailwindCSS for responsive styling (replaces Flet theme system)
- Vanilla JavaScript with Fetch API (replaces Flet's built-in events)
- Blueprint-based route organization (main_routes, api_routes)
- Client-server architecture with REST API endpoints

**Key Improvements:**
- Responsive design works on mobile, tablet, desktop
- Faster load times with compiled CSS and optimized JavaScript
- Better separation of concerns (backend/frontend)
- Easier to extend with new pages/features
- Standard web technologies (HTML/CSS/JS) instead of desktop framework
- TailwindCSS components for consistent UI

**Preserved Features:**
- All OCR and PDF processing functionality
- Email IMAP integration
- Invoice management and audit trail
- Validation and duplicate detection
- Export to Excel/CSV

**Auto-Memory:** Enabled (BUILD_COMMANDS section managed)
<!-- /AUTO:METADATA -->