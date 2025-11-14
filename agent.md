# 🧾 FakturaScanner - Agent Guide for Claude Code CLI

## 📌 Project Overview

**FakturaScanner** is a local Python desktop application for OCR processing of Polish PDF invoices. It extracts structured data (seller, invoice number, date, amount, bank account, etc.) using Tesseract OCR and stores results in SQLite database.

**Stack:**
- Python 3.11+
- Flet 0.28.3 (GUI framework, web view)
- Tesseract OCR + Polish language data
- SQLite database
- pdf2image, pytesseract, openpyxl

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
│   └── database.py            # SQLite connection singleton
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
│   └── export_service.py      # Excel/CSV export
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
    │   └── progress_dialog.py # Processing progress modal
    └── views/
        ├── main_view.py       # Invoice list, search, export
        ├── upload_view.py     # Multi-file PDF upload + sequential processing
        ├── edit_view.py       # Invoice edit form
        └── history_view.py    # Audit log viewer (WIP)
```

---

## 🎨 Design Principles

### **GUI (Flet):**
- **Layout:** Left navigation rail + main content area
- **Font:** Roboto (Material Design default)
- **Colors:** Light grays (#F5F7FA, #E8EDF2) + blue accents (#4472C4)
- **Style:** Minimal, modern, card-based UI
- **Responsiveness:** Min width 1000px, expandable

### **Key Components:**
- `AppStyles.card()` returns dict with `bgcolor`, `border_radius`, `padding=AppSpacing.MD`, `shadow` (BoxShadow)
  - Note: Uses `shadow` instead of `elevation` because we use `ft.Container` (not `ft.Card`)
  - Shadow creates subtle elevation effect compatible with Container
- **Never duplicate `padding=` after `**AppStyles.card()`** unless overriding (add comment if so)
- Use `AppColors`, `AppTypography`, `AppSpacing` constants from `gui/theme.py`

### **Code Style:**
- **Type hints:** Use for function signatures
- **Docstrings:** For classes and public methods
- **Error handling:** Try-except with user-friendly Snackbars
- **Separation of concerns:** Views call services, services call repositories

---

## 🔧 Key Implementation Details

### **OCR Pipeline (Variant A - Sequential Processing):**
```
1. User selects multiple PDFs
2. UploadView displays file list
3. User clicks "Przetwórz wszystkie"
4. For each PDF (sequentially):
   a. Copy to temp/
   b. PDFProcessor: PDF → images → Tesseract OCR → raw text
   c. TextExtractor: raw text → regex patterns → structured data
   d. ValidationService: validate NIP, IBAN, required fields
   e. DuplicateService: check by invoice_number
   f. Display result card (green=OK, yellow=warnings, red=errors)
5. User reviews, edits if needed, saves all or individually
```

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
          payment_due_date, pdf_path, ocr_confidence, 
          is_duplicate, created_at, updated_at)

audit_log (id, invoice_id, field_name, old_value, new_value, changed_at)

duplicate_detection (id, invoice_id, duplicate_of, similarity_score, detected_at)
```

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

### **Dependencies:**
- Tesseract OCR must be installed system-wide: `C:\Program Files\Tesseract-OCR\`
- Polish language data: `tessdata/pol.traineddata`
- Poppler for pdf2image: `C:\poppler\Library\bin`

---

## 🧪 Testing

### **Manual test flow:**
1. Start: `python main.py` (opens browser at localhost:8550)
2. Click "Import PDF" → select multiple PDFs
3. Click "Przetwórz wszystkie" → verify progress dialog
4. Review extracted data → check validation warnings
5. Save invoices → verify in "Lista Faktur"
6. Test edit, delete, search, export Excel/CSV

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

## 🔮 Future Enhancements (Variant B)

**Not yet implemented but architecture-ready:**
- Background queue processing (threading/asyncio)
- Retry mechanism for failed OCR
- AI/LLM integration (GPT-4 Vision, Claude) for better extraction
- PDF viewer component (inline preview)
- Batch operations (bulk edit, bulk delete)
- Advanced filters (date range, amount range)
- Full audit log viewer UI

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

**Last Updated:** 2024-11-12  
**Version:** 1.0.0  
**Status:** MVP complete, ready for testingv