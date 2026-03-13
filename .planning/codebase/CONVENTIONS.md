# Coding Conventions

**Analysis Date:** 2026-03-13

## Naming Patterns

**Files:**
- Snake case for all Python files: `invoice_repository.py`, `appointment_service.py`, `validation_service.py`
- Organized in functional directories: `repositories/`, `services/`, `routes/`, `utils/`
- Route blueprints follow `[feature]_routes.py` pattern: `appointment_routes.py`, `client_preference_routes.py`
- Repository files use `[entity]_repository.py`: `invoice_repository.py`, `client_repository.py`
- Service files use `[feature]_service.py`: `appointment_service.py`, `email_service.py`
- Test files use `test_[feature].py` pattern: `test_analytics_repository.py`

**Functions:**
- Snake case for all function names: `get_by_id()`, `validate_invoice()`, `create_appointment()`
- Helper functions prefixed with underscore: `_audit()`, `_canonical()`, `_parse_date()`
- Private/internal methods use underscore prefix: `_get_conn()`, `_execute()`, `_fetch_one()`
- Factory/converter methods follow `row_to_[entity]()` pattern: `row_to_invoice()`, `row_to_client()`, `row_to_user()`

**Variables:**
- Snake case for all variables: `invoice_date`, `seller_name`, `appointment_id`, `is_active`
- Boolean variables prefixed with `is_` or `has_`: `is_active`, `is_duplicate`, `is_authenticated`
- Private/internal variables use underscore prefix: `_conn`, `_cursor`, `_result`
- Collection variables use plural nouns: `appointments`, `errors`, `warnings`, `results`

**Types:**
- PascalCase for classes: `Invoice`, `Seller`, `Client`, `Employee`, `AppointmentBusinessService`
- Exception classes suffixed with `Error`: `AppointmentError`, `OCRExtractionError`
- Model classes are dataclasses (see `database/models.py`): `@dataclass`
- Repository classes follow `[Entity]Repository` pattern: `InvoiceRepository`, `ClientRepository`, `EmployeeRepository`

## Code Style

**Formatting:**
- Soft tabs (spaces) — 4 spaces per indent level
- No explicit formatter configured (no `.pylintrc`, `.flake8`, or `pyproject.toml` linting config found)
- Line length follows Python convention (implicit ~79-100 char target based on readability)

**Linting:**
- No linting tool configured (no `.pylintrc`, `.flake8`, `pyproject.toml` with `[tool.black]` or `[tool.ruff]`)
- Code follows implicit PEP 8-adjacent conventions observed across codebase

**Module Docstrings:**
- First line is descriptive module purpose in English or Polish: `"""Modele danych (dataclasses)"""`
- Docstrings are triple-quoted strings at module top

**Class Docstrings:**
- First line is short description: `"""Repository dla operacji na pracownikach (employees)"""`
- Used for repository and service classes to document responsibility

**Function Docstrings:**
- Used for complex functions, service methods, and public APIs
- Format: Summary line, optional Args/Returns sections
- Polish documentation acceptable: `"""Utwórz nową wizytę z usługami."""`
- Example from `services/appointment_service.py`:
  ```python
  def create_appointment(self, client_id: int, employee_id: int,
                          service_ids: List[int], appt_date: date,
                          start_time: time, notes: Optional[str] = None,
                          created_by: Optional[int] = None) -> dict:
      """Utwórz nową wizytę z usługami.

      Kroki:
      1. Oblicz cenę i czas dla każdej usługi (COALESCE)
      2. Oblicz end_time na podstawie łącznego czasu
      3. Sprawdź konflikty czasowe
      4. Utwórz wizytę + appointment_services ze snapshotem cen

      Returns: dict z appointment_id i szczegółami
      Raises: AppointmentError jeśli walidacja nie przejdzie
      """
  ```

## Import Organization

**Order:**
1. Standard library imports: `import os`, `import logging`, `from datetime import datetime`
2. Third-party imports: `from flask import Flask`, `from flask_login import LoginManager`
3. Local application imports: `from config.settings import APP_NAME`, `from repositories.invoice_repository import InvoiceRepository`

**Path Aliases:**
- No path aliases configured in codebase
- All imports use absolute paths from project root: `from repositories.clients.client_repository import ClientRepository`
- No `sys.path` manipulation or circular import patterns observed

**Example from `app.py`:**
```python
import base64
import logging
import os
from datetime import datetime, date, time
from decimal import Decimal

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_login import LoginManager

from config.settings import APP_NAME, VERSION, UPLOAD_FOLDER, PDF_FOLDER
from config.database import initialize_database
from repositories.invoice_repository import InvoiceRepository
```

## Error Handling

**Patterns:**
- Custom exception classes for domain errors: `AppointmentError`, `OCRExtractionError` in `services/appointment_service.py`
- Try/except blocks for recovery: catch specific exceptions (`KeyError`, `TypeError`, `ValueError`)
- Silent failures logged to stderr in some cases: `except Exception as e: print(..., file=sys.stderr)`
- Service methods raise domain exceptions, routes catch and convert to JSON responses

**Domain Exceptions:**
```python
class AppointmentError(Exception):
    """Błąd operacji na wizycie"""
    pass
```

**Route Error Handling:**
- Routes in `routes/api_routes.py` wrap service calls with try/except blocks
- Validation result dicts return `{'errors': [...], 'warnings': [...]}`
- Example from `services/validation_service.py`:
  ```python
  def validate_invoice(self, invoice: Invoice) -> Dict[str, List[str]]:
      """
      Waliduj fakturę

      Returns:
          Dict z ostrzeżeniami i błędami:
          {
              'errors': ['Brak numeru faktury', ...],
              'warnings': ['NIP niepoprawny', ...]
          }
      """
      errors = []
      warnings = []
      # ... validation logic ...
      return {
          'errors': errors,
          'warnings': warnings
      }
  ```

**Authentication Errors:**
- Return tuples with status flag: `Tuple[bool, Optional[User], Optional[str]]` from `auth_service.py`
- Format: `(success: bool, result: Optional[T], error_message: Optional[str])`

## Logging

**Framework:** Python standard `logging` module (see `app.py` lines 19-28)

**Patterns:**
- Centrally configured in `app.py` with `logging.basicConfig()`
- Named loggers for specific modules: `logging.getLogger(__name__)`
- Example from `services/ocr_service.py`:
  ```python
  logger = logging.getLogger(__name__)
  logger.info("[OCR] Final result using profile 'legacy'")
  logger.debug(f"[OCR RAW TEXT] First 2000 chars:\n{raw_text[:2000]}")
  logger.warning(f"[Retry] Profile '{profile}' failed: {e}")
  logger.error("[Retry] All OCR attempts failed")
  ```
- Audit logging via `AuditRepository.log_event()` for business actions
- Structured audit entries with entity type, action, user context
- Audit failures logged to stderr but don't block operations: `print(..., file=sys.stderr)`

**When/how to log:**
- DEBUG: Detailed diagnostic information (OCR profiles, retry attempts)
- INFO: Significant operations (successful extraction, status changes)
- WARNING: Issues that don't block operations (failed retry attempt, low OCR confidence)
- ERROR: Critical failures that need investigation
- Use `[PREFIX]` in messages for easy filtering: `[OCR]`, `[AUDIT]`, `[Retry]`

## Comments

**When to Comment:**
- Complex business logic requiring explanation: State transitions, pricing calculations
- Non-obvious validation rules: Date ordering, Polish NIP/IBAN algorithms
- Workarounds or compromises: Why a particular approach was chosen
- Avoid comments for self-documenting code (clear function names eliminate need)

**JSDoc/TSDoc:**
- Not used in this Python codebase
- Python uses docstrings instead (see "Code Style" section above)

**Example from `services/appointment_service.py`:**
```python
# Dozwolone przejścia statusów
STATUS_TRANSITIONS = {
    'scheduled': ['confirmed', 'cancelled', 'no_show'],
    'confirmed': ['in_progress', 'cancelled'],
    'in_progress': ['completed', 'cancelled'],
}

# 3b. Sprawdź konflikty klienta (czy klient ma już wizytę w tym czasie)
client_conflicts = self.appt_repo.check_client_conflicts(
    client_id, appt_date, start_time, end_time
)
```

## Function Design

**Size:**
- Most functions 5-50 lines
- Service methods (like pricing calculation) 20-40 lines
- Repository methods (CRUD operations) 10-30 lines
- Helper functions like `_canonical()`, `_parse_date()` 5-15 lines

**Parameters:**
- Type hints used throughout: `def create_appointment(self, client_id: int, employee_id: int, ...) -> dict:`
- Optional parameters use `Optional[Type]`: `notes: Optional[str] = None`
- Complex parameter sets documented in docstrings (rare in this codebase)

**Return Values:**
- Single values for simple operations: `get_by_id() -> Optional[Invoice]`
- Dicts for complex results: `validate_invoice() -> Dict[str, List[str]]`
- Tuples for multiple return values: `authenticate() -> Tuple[bool, Optional[User], Optional[str]]`
- Model objects from factories: `row_to_invoice(row) -> Invoice`

**Example from `services/auth/auth_service.py`:**
```python
def authenticate(self, email: str, password: str) -> Tuple[bool, Optional[User], Optional[str]]:
    """
    Autentykuj użytkownika

    Args:
        email: Adres email
        password: Hasło w postaci jawnej

    Returns:
        Tuple (success: bool, user: Optional[User], error_message: Optional[str])
    """
```

## Module Design

**Exports:**
- Repository classes instantiated in `app.py` and attached as Flask app attributes
- Service classes instantiated in `app.py`: `app.ocr_service = OCRService()`
- Routes registered as Flask blueprints: `app.register_blueprint(auth_bp)`
- No `__all__` defined in modules (all public members exportable)

**Barrel Files:**
- Found in feature directories: `repositories/__init__.py`, `services/__init__.py`, `routes/__init__.py`
- Typically empty (no re-exports defined)
- Used as namespace/package markers

**Layer Organization:**
```
repositories/          # Data access layer (CRUD)
├── base_repository.py # Common CRUD methods
├── [entity]_repository.py
└── [feature]/
    └── [entity]_repository.py

services/              # Business logic layer
├── [feature]_service.py
└── auth/
    └── auth_service.py

routes/                # HTTP handler layer (Flask)
├── [feature]_routes.py
└── [feature]/
    └── routes.py
```

## Data Type Conventions

**Date/Time Handling:**
- Use `datetime.date` for date-only values
- Use `datetime.datetime` for timestamp values
- Use `datetime.time` for time-only values
- ISO format strings for serialization: `date.isoformat()`
- Date parsing centralized in `utils/validators.py` via `DateParser` class

**Decimal vs Float:**
- Use `Decimal` for financial calculations: `from decimal import Decimal`
- Use `float` for OCR confidence scores, ratios
- Database stores numeric as PostgreSQL types, convert on retrieval

**Custom Model Types:**
- All models are dataclasses (see `database/models.py`)
- Fields use `Optional[Type]` for nullable columns
- Include `id: Optional[int] = None` for new entities (populated on creation)
- Include `created_at`, `updated_at` timestamps using `field(default_factory=datetime.now)`

**Example from `database/models.py`:**
```python
@dataclass
class Invoice:
    """Model faktury"""
    seller_name: str
    invoice_number: str
    invoice_date: date
    amount: float
    currency: str = "PLN"
    seller_nip: Optional[str] = None
    bank_account: Optional[str] = None
    payment_due_date: Optional[date] = None
    ocr_confidence: Optional[float] = None
    is_duplicate: bool = False
    id: Optional[int] = None
    created_at: Optional[datetime] = field(default_factory=datetime.now)
```

---

*Convention analysis: 2026-03-13*
