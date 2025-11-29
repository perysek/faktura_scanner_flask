# 🧾 FakturaScanner - Agent Guide for Claude Code CLI

## 📌 Project Overview

**FakturaScanner** is a local Python desktop application for OCR processing of Polish PDF invoices. It extracts structured data (seller, invoice number, date, amount, bank account, etc.) using Tesseract OCR and stores results in SQLite database. Features email integration for automatic PDF import from IMAP mailboxes.

**Stack:**
- Python 3.11+
- Flet 0.28.3 (GUI framework, web view)
- Tesseract OCR + Polish language data
- SQLite database
- pdf2image, pytesseract, openpyxl
- imaplib (email IMAP integration)

**Target Users:** Single local user, no authentication required

---

## 🏗️ Architecture

### **Layered Architecture:**
```
GUI (Flet views) 
    ↓
Services (business logic)
    ↓
Repositories (data access)
    ↓
SQLite Database
```

### **Project Structure:**
```
faktura_scanner/
├── main.py                    # Entry point (Flet app)
├── requirements.txt
│
├── config/                    # Configuration
│   ├── settings.py            # App settings (paths, OCR params)
│   ├── database.py            # SQLite connection singleton
│   └── email_settings.py      # Email account settings (IMAP config)
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
└── gui/                       # Flet UI
    ├── app.py                 # Main app, navigation rail layout
    ├── theme.py               # Colors, fonts (Roboto), styles
    ├── components/
    │   ├── navigation_rail.py # Left sidebar navigation
    │   ├── invoice_table.py   # DataTable for invoices
    │   ├── progress_dialog.py # Processing progress modal
    │   ├── notification_panel.py       # Bottom notification panel (last 3 notifications)
    │   └── processing_results_table.py # Compact results table for processed invoices
    └── views/
        ├── main_view.py       # Invoice list, search, export, PDF preview
        ├── upload_view.py     # Multi-file PDF upload + email import + sequential processing
        ├── edit_view.py       # Invoice edit form
        ├── email_settings_view.py # Email IMAP configuration view
        └── history_view.py    # Audit log viewer
```

---

## 🎨 Design Principles

### **GUI (Flet):**
- **Layout:** Left navigation rail + main content area
- **Font:** Roboto (Material Design default)
- **Colors:** Light grays (#F5F7FA, #E8EDF2) + blue accents (#4472C4)
- **Style:** Minimal, modern, card-based UI
- **Responsiveness:** Min width 1000px, expandable, app start in maximized window

### **Language:**
- The application's user interface and all user-facing strings must be in **Polish**.

### **Key Components:**
- `AppStyles.card()` returns dict with `bgcolor`, `border_radius`, `padding=AppSpacing.MD`, `shadow` (BoxShadow)
  - Note: Uses `shadow` instead of `elevation` because we use `ft.Container` (not `ft.Card`)
  - Shadow creates subtle elevation effect compatible with Container
- **Never duplicate `padding=` after `**AppStyles.card()`** unless overriding (add comment if so)
- Use `AppColors`, `AppTypography`, `AppSpacing` constants from `gui/theme.py`

### **Custom Table Component with Search Fields:**

The application uses a **custom table implementation** (not `ft.DataTable`) to support inline search fields in header cells. See `gui/components/invoice_table.py` for the complete implementation.

#### **Architecture:**
```python
ft.Column (main table)
├── Container (header row with grey background, height=80px)
│   └── ft.Row (header cells)
│       ├── Container (column 1 - with search, expand=3)
│       │   └── ft.Column (tight=True, horizontal_alignment=START)
│       │       ├── ft.Row (column title + sort button IconButton)
│       │       └── Container (search TextField, white bg, height=37)
│       ├── Container (column 2 - simple, expand=2)
│       │   └── ft.Column (tight=True, horizontal_alignment=CENTER)
│       │       ├── ft.Row (column title + invisible sort button)
│       │       └── Container (invisible search TextField, visible=False)
│       └── ...
└── Container (data rows container, border top)
    └── ft.Column (scrollable data container, self.data_container)
        ├── ft.Row (data row 1, height=30)
        ├── Container (divider, height=1)
        ├── ft.Row (data row 2, height=30)
        └── ...
```

**Key differences from standard DataTable:**
- Custom header cells with embedded search TextFields
- Simple headers use invisible elements to match searchable header height
- Persistent `data_container` allows filtering without rebuilding headers
- Integer-based expand ratios for precise column width control
- Inline status dropdown for direct editing

#### **Key Implementation Details:**

1. **Column Width Management:**
```python
# MUST use INTEGER values for expand property
self.column_expansions = {
    'seller_name': 3,
    'invoice_number': 3,
    'invoice_date': 2,
    'amount': 2,
    'seller_nip': 2,
    'bank_account': 3,
    'payment_due_date': 2,
    'status': 3,
    'created_at': 2,
    'ocr_confidence': 1,
    'actions': 2,
}

# Apply consistently in BOTH header and data cells
create_cell(control, 'seller_name')  # Uses column_expansions['seller_name']
```

2. **Header Cell with Search Field:**
```python
def create_column_header(self, label: str, field_name: str,
                        with_search: bool = False, expand: int = 1):
    # Column name with sort button
    header_row = ft.Row(
        controls=[
            ft.Text(label, weight=ft.FontWeight.W_600, size=12, color="#424242"),
            ft.IconButton(icon=sort_icon, icon_size=14, on_click=lambda e: self.toggle_sort(field_name))
        ],
        spacing=4,
        alignment=ft.MainAxisAlignment.CENTER
    )

    if with_search:
        # White search field below column name
        search_field = ft.TextField(
            hint_text="Search...",
            value=self.column_filters.get(field_name, ''),
            on_change=lambda e: self.on_filter_change(field_name, e.control.value),
            text_size=12,
            height=37,
            content_padding=ft.padding.symmetric(horizontal=6, vertical=4),
            border_color="#BDBDBD",      # Darker grey
            focused_border_color="#90CAF9",
            border_width=1,
            border_radius=3,
            bgcolor="#FFFFFF",           # White background
            filled=True,
            dense=True,
            cursor_color="#2196F3",
        )

        # Wrap in container with padding
        search_container = ft.Container(
            content=search_field,
            padding=ft.padding.Padding(left=0, top=2, right=5, bottom=2)
        )

        # Stack vertically: title + search
        header_column = ft.Column(
            controls=[header_row, search_container],
            spacing=2,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            alignment=ft.MainAxisAlignment.START,
        )

        return ft.Container(
            content=header_column,
            expand=expand,  # INTEGER from column_expansions
            padding=ft.padding.symmetric(horizontal=4, vertical=4),
            alignment=ft.alignment.top_left,
            border=ft.border.only(right=ft.BorderSide(1, "#EEEEEE"))
        )
    else:
        # Column header without search - simpler structure
        return ft.Container(
            content=header_row,
            expand=expand,
            padding=ft.padding.symmetric(horizontal=4, vertical=4),
            alignment=ft.alignment.top_left,
            border=ft.border.only(right=ft.BorderSide(1, "#EEEEEE"))
        )
```

3. **Simple Headers (Maintaining Layout Consistency):**

For columns without search fields (NIP, Konto, OCR, Akcje), use invisible elements to maintain consistent height and alignment:

```python
@staticmethod
def create_simple_header(label: str, expand: int = 1) -> ft.Container:
    """Create header cell with invisible elements to match searchable headers"""

    # Invisible sort button to maintain structure
    invisible_sort_button = ft.IconButton(
        icon=ft.Icons.UNFOLD_MORE,
        icon_size=14,
        icon_color="#F5F5F5",  # Same as header background
        disabled=True,
        style=ft.ButtonStyle(padding=ft.padding.all(4)),
    )

    # Header row with label and invisible sort button
    header_row = ft.Row(
        controls=[
            ft.Text(label, weight=ft.FontWeight.W_600, size=12, color="#424242"),
            invisible_sort_button,
        ],
        spacing=4,
        alignment=ft.MainAxisAlignment.START
    )

    # Invisible search field to match structure of headers with search
    invisible_search = ft.TextField(
        hint_text="",
        text_size=12,
        height=37,
        content_padding=ft.padding.symmetric(horizontal=6, vertical=4),
        border_width=1,
        border_radius=3,
        filled=True,
        dense=True,
        visible=False,  # Hidden to maintain layout
    )

    search_container = ft.Container(
        content=invisible_search,
        padding=ft.padding.symmetric(horizontal=5, vertical=2),
    )

    # Stack vertically: title + invisible search (matches searchable headers)
    header_column = ft.Column(
        controls=[header_row, search_container],
        spacing=2,
        tight=True,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.START,
    )

    return ft.Container(
        content=header_column,
        expand=expand,
        padding=ft.padding.symmetric(horizontal=4, vertical=4),
        alignment=ft.alignment.top_left,
        border=ft.border.only(right=ft.BorderSide(1, "#EEEEEE"))
    )
```

**Why invisible elements?** This pattern ensures ALL headers have identical height and vertical alignment, preventing misalignment between searchable and non-searchable columns. Without invisible elements, simple headers would be shorter and cause visual inconsistency.

4. **Efficient Filtering (Only Rebuild Data Rows):**
```python
def __init__(self):
    # Persistent container for data rows only
    self.data_container = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, expand=True)

def on_filter_change(self, field_name: str, value: str):
    """Handle filter change - ONLY rebuild data rows"""
    self.column_filters[field_name] = value.lower()

    # Re-apply filters and sorting
    self.apply_filters()
    self.apply_sorting()

    # FIX: Only update data rows, NOT entire table
    # This prevents header from rebuilding and losing focus
    self.data_container.controls = self.build_data_rows()

    if self.page:
        self.page.update()
```

5. **Header Styling:**
```python
header_row = ft.Row(controls=cells)

return ft.Container(
    content=header_row,
    height=80,              # Accommodates search fields
    bgcolor="#F5F5F5",      # Light grey background
)
```

6. **Data Cell Creation (Matching Expansion Ratios):**
```python
def create_cell(control: ft.Control, field_name: str, alignment=ft.alignment.center_left):
    return ft.Container(
        content=control,
        expand=self.column_expansions[field_name],  # MUST match header expand value
        padding=ft.padding.symmetric(horizontal=6, vertical=4),
        alignment=alignment,
        border=ft.border.only(right=ft.BorderSide(1, "#EEEEEE"))
    )
```

7. **Data Row Styling:**
```python
row = ft.Row(
    controls=[...],
    height=30,  # Consistent row height
)
# Add divider between rows
rows_controls.append(row)
rows_controls.append(ft.Container(height=1, bgcolor="#EEEEEE"))
```

#### **Critical Rules for Custom Tables:**

1. **Column expansions MUST be integers** - Flet's `expand` property only accepts int, not float
2. **Expansion values MUST match** between header and data cells - otherwise columns won't align
3. **Key names MUST be consistent** - If you use `'ocr_confidence'` in expansions dict, use it everywhere (not `'ocr'`)
4. **Filter updates should only rebuild data rows** - Use persistent `data_container` to avoid rebuilding header
5. **Header height must accommodate search fields** - Use 80px for headers (adjusted for 37px search fields)
6. **Search fields should be white** - Use `bgcolor="#FFFFFF"` with darker border `#BDBDBD` for contrast against grey header
7. **Search field dimensions** - Use `text_size=12` and `height=37` for consistent appearance
8. **Use `tight=True`** on header Column to prevent extra spacing around search fields
9. **Never use `expand=True` on search TextField** - Let container control width with integer expand value
10. **Use invisible elements in simple headers** - Add invisible sort buttons and search fields to maintain consistent height with searchable columns
11. **Header alignment** - Use `ft.alignment.top_left` for headers to ensure consistent vertical alignment
12. **Data row height** - Use `height=30` for data rows with 1px dividers between rows

#### **Common Mistakes:**

❌ **Wrong:** Using float or 'True' for expand
```python
self.column_expansions = {'seller_name': 1.5}  # Float not supported
create_cell(control, expand=True)              # Won't align with numeric expand values
```

✅ **Correct:** Integer expand values
```python
self.column_expansions = {'seller_name': 4}    # Integer only
create_cell(control, expand=4)                 # Matches header
```

❌ **Wrong:** Rebuilding entire table on filter change
```python
def on_filter_change(self, field, value):
    self.build_table()  # Rebuilds header too - loses focus
```

✅ **Correct:** Only rebuild data rows
```python
def on_filter_change(self, field, value):
    self.data_container.controls = self.build_data_rows()  # Header untouched
```

❌ **Wrong:** Mismatched key names
```python
self.column_expansions = {'ocr': 1}           # Key name 'ocr'
create_cell(control, 'ocr_confidence')         # KeyError!
```

✅ **Correct:** Consistent key names
```python
self.column_expansions = {'ocr_confidence': 1}
create_cell(control, 'ocr_confidence')
```

❌ **Wrong:** Simple headers without invisible elements
```python
def create_simple_header(label: str):
    # Just a text label - will be shorter than searchable headers
    return ft.Container(content=ft.Text(label))
```

✅ **Correct:** Simple headers WITH invisible elements
```python
def create_simple_header(label: str):
    # Include invisible sort button AND invisible search field
    # This matches the height of searchable headers exactly
    invisible_sort_button = ft.IconButton(..., disabled=True, icon_color="#F5F5F5")
    invisible_search = ft.TextField(..., visible=False, height=37)
    # Stack them vertically to match searchable header structure
```

### **Inline Status Editing in Invoice Table:**

The invoice table includes inline status editing via a dropdown in the Status column:

```python
# In build_data_rows()
create_cell(
    ft.Dropdown(
        value=invoice.status,
        options=[
            ft.dropdown.Option("Nieopłacona"),
            ft.dropdown.Option("Opłacona"),
        ],
        dense=True,
        on_change=lambda e, inv=invoice: self.on_status_change(e, inv),
        text_size=13,
        content_padding=ft.padding.symmetric(horizontal=0, vertical=2),
        border_width=0,
        text_align=ft.alignment.center_left,
        expand=False,
    ),
    'status',
    alignment=ft.alignment.center_left
)

def on_status_change(self, e, invoice: Invoice):
    """Handle status change - update database and refresh table"""
    try:
        invoice.status = e.control.value
        self.invoice_repo.update(invoice.id, invoice)
        # Refresh table to update colors (overdue invoices)
        if self.on_refresh_callback:
            self.on_refresh_callback()
    except Exception as ex:
        # Revert dropdown on error
        e.control.value = invoice.status
        if e.control.page:
            e.control.page.update()
```

**Key features:**
- **Immediate updates** - Changes saved to database on dropdown change
- **Error handling** - Reverts dropdown value if update fails
- **Table refresh** - Triggers callback to update row colors (e.g., overdue highlighting)
- **No borders** - Uses `border_width=0` for cleaner inline appearance

### **Invoice Table Cell Styling Patterns:**

The invoice table uses specific styling for different data types:

```python
# 1. Seller Name - Bold, dark color
ft.Text(
    invoice.seller_name,
    size=13,
    color="#424242",
    style=ft.TextStyle(weight=ft.FontWeight.W_600),  # Bold
    overflow=ft.TextOverflow.ELLIPSIS,
    no_wrap=True
)

# 2. Invoice Number, Dates - Medium grey
ft.Text(
    invoice.invoice_number,
    size=13,
    color="#616161",
    overflow=ft.TextOverflow.ELLIPSIS,
    no_wrap=True
)

# 3. Amount - Medium bold, right-aligned
ft.Text(
    f"{invoice.amount:.2f} {invoice.currency}",
    size=13,
    weight=ft.FontWeight.W_500,
    color="#424242"
)

# 4. NIP, Bank Account - Light grey
ft.Text(
    invoice.seller_nip or "-",
    size=13,
    color="#757575"
)

# 5. Overdue Payment - Red background with white text
ft.Container(
    content=ft.Text(
        invoice.payment_due_date.strftime('%Y-%m-%d'),
        size=13,
        color="white" if (overdue and not paid) else AppColors.TEXT_PRIMARY
    ),
    bgcolor=AppColors.ERROR if (overdue and not paid) else None,
    padding=ft.padding.symmetric(horizontal=6, vertical=2),
    border_radius=4,
)

# 6. OCR Confidence Badge - Color-coded by threshold
ft.Container(
    content=ft.Text(
        f"{invoice.ocr_confidence:.0f}%",
        size=13,
        color="white" if confidence >= 80 else AppColors.TEXT_PRIMARY,
        weight=ft.FontWeight.BOLD
    ),
    bgcolor=AppColors.SUCCESS if confidence >= 80 else (
        AppColors.WARNING if confidence >= 60 else AppColors.ERROR
    ),
    padding=ft.padding.symmetric(horizontal=6, vertical=2),
    border_radius=3,
)
```

**Color coding guide:**
- **Seller names:** `#424242` (dark grey) with `W_600` weight - emphasizes primary identifier
- **Regular text:** `#616161` (medium grey) - invoice numbers, dates
- **Secondary info:** `#757575` (light grey) - NIP, bank accounts
- **Amount:** `#424242` with `W_500` weight - highlights financial value
- **Overdue payments:** Red background (`AppColors.ERROR`) with white text - urgent attention
- **OCR confidence:**
  - ≥80%: Green background (`AppColors.SUCCESS`) - high confidence
  - 60-79%: Orange background (`AppColors.WARNING`) - medium confidence
  - <60%: Red background (`AppColors.ERROR`) - low confidence, review needed

**Alignment patterns:**
- **Left-aligned** (default): Seller name, invoice number, NIP, bank account, status
- **Center-aligned:** Invoice date, payment due date, created date, OCR confidence
- **Right-aligned:** Amount (financial convention)

### **Notification System:**
- **NotificationPanel:** Fixed panel at bottom of navigation rail (260px width)
- Shows last 3 notifications with icon, message, and timestamp (HH:MM:SS format)
- 4 types: success (green), error (red), warning (orange), info (blue)
- Clear all button to remove all notifications
- Auto-limits to 3 most recent notifications
- Usage in views: `self.notification_panel.add_notification(message, type)`

### **Code Style:**
- **Type hints:** Use for function signatures
- **Docstrings:** For classes and public methods
- **Error handling:** Try-except with user-friendly messages via notification panel
- **Separation of concerns:** Views call services, services call repositories

---

## 🧭 Navigation Structure

The application uses a left navigation rail with 5 main views:

1. **LISTA FAKTUR** (Main View)
   - Invoice table with search functionality
   - Statistics cards (totals, VAT, by currency)
   - Export to Excel/CSV
   - Actions: View PDF, Edit, Delete
   - Refresh button

2. **IMPORT PDF** (Upload View)
   - File picker for local PDFs
   - Email import from IMAP mailbox
   - File list with sizes
   - Sequential processing with progress bar
   - ProcessingResultsTable with validation results
   - Individual or batch save

3. **EKSPORT** (Export View)
   - Currently placeholder (export functionality in Main View)
   - Reserved for future batch export features

4. **HISTORIA** (History View)
   - Audit log viewer
   - Shows field changes with old/new values
   - Timestamps for all modifications

5. **USTAWIENIA E-MAIL** (Email Settings View)
   - IMAP server configuration
   - Email address and password (or app-specific password)
   - Port settings (default 993 for SSL)
   - Date range for email search
   - Test connection button
   - Save configuration

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

## 🚀 Common Tasks

### **Adding a new field to invoices:**
1. Update `database/schema.sql` (add column)
2. Update `database/models.py` (Invoice dataclass)
3. Update `repositories/invoice_repository.py` (create/update methods)
4. Add regex pattern to `utils/text_extractor.py`
5. Update `gui/views/edit_view.py` (form field)
6. Update `gui/components/invoice_table.py` (table column)
7. Update `services/export_service.py` (Excel/CSV headers)

### **Improving OCR accuracy:**
- Increase `OCR_DPI` in `config/settings.py` (default 300)
- Enable preprocessing in `utils/pdf_processor.py::preprocess_image()`
- Add more regex patterns in `utils/text_extractor.py`

### **Adding a new view:**
1. Create `gui/views/new_view.py` inheriting from `ft.Column`
2. Add navigation destination to `gui/components/navigation_rail.py`
3. Add view to routing in `gui/app.py::load_view()`

### **Debugging OCR extraction:**
```python
# In upload_view.py::start_processing(), add:
print("=== RAW OCR TEXT ===")
print(raw_text)
print("=== EXTRACTED DATA ===")
print(extracted_data)
```

### **PDF Preview Feature:**
- Located in `main_view.py::view_invoice()`
- Opens PDF in system's default viewer (not in-app)
- Cross-platform support:
  - Windows: `os.startfile()`
  - macOS: `subprocess.run(['open', ...])`
  - Linux: `subprocess.run(['xdg-open', ...])`
- Checks file existence before opening
- Shows error notifications if PDF missing or cannot be opened

### **Adding email import to a view:**
```python
from services.email_service import EmailService
from config.email_settings import EmailSettings

# Load settings
email_settings = EmailSettings()
settings = email_settings.get_settings()

# Connect and fetch PDFs
email_service = EmailService()
if email_service.connect(
    settings['email_address'],
    settings['password'],
    settings['imap_server'],
    settings['imap_port']
):
    pdf_files = email_service.fetch_pdf_attachments(
        from_date=from_date,  # date object or None
        to_date=to_date,      # date object or None
        save_dir=TEMP_DIR,
        progress_callback=my_progress_handler  # Optional
    )
    # pdf_files is list of (filename, path) tuples
    email_service.disconnect()
```

---

## ⚠️ Important Constraints

### **What NOT to do:**
1. **Never duplicate `padding=` after `**AppStyles.card()`** (already includes `padding=AppSpacing.MD`)
   - If overriding, use: `card_styles = AppStyles.card(); card_styles['padding'] = AppSpacing.XXL`
   - Add comment explaining why you need different padding
2. **Never use `elevation=` parameter** with `ft.Container` - use `shadow=` instead
   - Container doesn't support elevation (that's for ft.Card only)
   - AppStyles.card() already includes BoxShadow for elevated effect
3. **Never use `localStorage`** in Flet (not supported)
4. **Never block UI thread** - long operations should show progress dialog
5. **Never hardcode paths** - use `config/settings.py` constants
6. **Never skip validation** before saving invoices
7. **Never commit email credentials** - `config/email_config.json` should be in .gitignore

### **Dependencies:**
- Tesseract OCR must be installed system-wide: `C:\Program Files\Tesseract-OCR\`
- Polish language data: `tessdata/pol.traineddata`
- Poppler for pdf2image: `C:\poppler\Library\bin`
- Email settings stored in: `config/email_config.json` (auto-created on first save)

---

## 🧪 Testing

### **Manual test flow:**
1. Start: `python main.py` (opens browser at localhost:8550)
2. Configure email settings (optional):
   - Navigate to "USTAWIENIA E-MAIL"
   - Enter IMAP credentials
   - Test connection
   - Save configuration
3. Import PDFs (choose one method):
   - Method A: Click "Import PDF" → "Wybierz pliki PDF" → select multiple PDFs
   - Method B: Click "Import PDF" → "Import from E-mail" → fetch PDFs from mailbox
4. Click "Przetwórz wszystkie" → verify progress bar and status updates
5. Review ProcessingResultsTable:
   - Check status icons and OCR confidence badges
   - View raw OCR text if needed
   - Review validation warnings/errors
6. Save invoices → verify notifications appear
7. Navigate to "Lista Faktur" → verify invoices are saved
8. Test PDF preview (click eye icon) → verify opens in system viewer
9. Test edit, delete, search, export Excel/CSV
10. Check notification panel for recent activity

### **Test data:**
Create sample Polish invoice PDF with:
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

**Completed and working:**
- ✅ Email IMAP integration for automatic PDF import
- ✅ Notification panel with last 3 notifications
- ✅ Processing results table with compact view
- ✅ PDF preview via system default viewer
- ✅ Payment status tracking (Nieopłacona, Opłacona, Przeterminowana)
- ✅ Payment terms field
- ✅ Email settings configuration view
- ✅ Progress feedback during email import
- ✅ OCR confidence color-coded badges
- ✅ Detailed validation warnings/errors display
- ✅ Inline status editing with dropdown in invoice table (Nov 2025)
- ✅ Custom table with search fields and invisible element pattern (Nov 2025)
- ✅ Enhanced cell styling with color-coded priorities and bold seller names (Nov 2025)
- ✅ Optimized header alignment and search field dimensions (Nov 2025)
- ✅ Overdue payment highlighting with red background (Nov 2025)

## 🔮 Future Enhancements

**Not yet implemented but architecture-ready:**
- Background queue processing (threading/asyncio)
- Retry mechanism for failed OCR
- AI/LLM integration (GPT-4 Vision, Claude) for better extraction
- In-app PDF viewer component (currently opens in external viewer)
- Batch operations (bulk edit, bulk delete)
- Advanced filters (date range, amount range)
- Email OAuth2 authentication (currently password-based only)

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

## 💡 Code Patterns to Follow

### **Good:**
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

### **Bad:**
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

---

**Last Updated:** 2025-11-19
**Version:** 1.1.1
**Status:** Production-ready with email integration, notification system, enhanced UI with inline editing, and improved table styling

**Latest improvements:**
- Inline status editing with dropdown in invoice table
- Enhanced table cell styling with color-coded priorities
- Improved header alignment with invisible elements for consistent layout
- Optimized search field dimensions (text_size=12, height=37)
- Seller name bold styling (FontWeight.W_600) for better readability
- Color-coded OCR confidence badges and overdue payment highlighting