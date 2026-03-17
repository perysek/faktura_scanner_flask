# Codebase Structure

**Analysis Date:** 2026-03-13

## Directory Layout

```
faktura_scanner_flask/
├── alembic/                    # Database migration versions and env
│   └── versions/               # Individual migration scripts
├── config/                     # Configuration files
│   ├── auth_config.py          # RBAC rules and decorators
│   ├── database.py             # PostgreSQL connection pooling
│   ├── email_settings.py       # Email configuration
│   └── settings.py             # App-wide settings (paths, OCR config)
├── database/                   # Data models
│   └── models.py               # Dataclasses for all entities
├── repositories/               # Data access layer (CRUD operations)
│   ├── base_repository.py      # Base class with common patterns
│   ├── analytics/              # Analytics data repositories
│   ├── appointments/           # Appointment and income repositories
│   ├── clients/                # Client and preference repositories
│   ├── employees/              # Employee and form employment repositories
│   ├── roles/                  # Role-based access control repository
│   ├── services/               # Service and add-on repositories
│   ├── users/                  # User account repository
│   ├── invoice_repository.py   # Invoice CRUD
│   ├── seller_repository.py    # Seller management
│   └── audit_repository.py     # Audit trail logging
├── routes/                     # HTTP request handlers (blueprints)
│   ├── auth/                   # Authentication (login, logout, profile)
│   ├── roles/                  # Role management endpoints
│   ├── users/                  # User management endpoints
│   ├── main_routes.py          # Main pages (dashboard, invoices, clients, etc.)
│   ├── api_routes.py           # JSON API endpoints (CRUD, search, export)
│   ├── upload_routes.py        # PDF/image upload and OCR
│   ├── appointment_routes.py   # Appointment calendar and booking
│   ├── analytics_routes.py     # Analytics and reporting endpoints
│   ├── employee_service_routes.py  # Employee skill ratings
│   ├── service_addon_routes.py # Additional service options
│   ├── client_preference_routes.py # Client preferences
│   └── income_routes.py        # Income tracking endpoints
├── services/                   # Business logic layer
│   ├── auth/                   # Authentication service
│   ├── appointment_service.py  # Appointment workflow orchestration
│   ├── ocr_service.py          # PDF/image OCR extraction
│   ├── validation_service.py   # Data validation rules
│   ├── email_service.py        # Email sending (notifications, invoices)
│   ├── export_service.py       # Excel export functionality
│   ├── duplicate_detection_service.py # Invoice duplicate detection
│   ├── seller_service.py       # Seller data management
│   └── pricing_service.py      # Service pricing calculations
├── utils/                      # Cross-cutting utilities
│   ├── pdf_processor.py        # PDF parsing and preprocessing
│   ├── text_extractor.py       # OCR text extraction pipeline
│   └── validators.py           # NIP, IBAN, date validation
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Main layout (sidebar, header, footer)
│   ├── auth/                   # Login, password reset, profile
│   ├── dashboard/              # Dashboard and home page
│   ├── invoices/               # Invoice list, edit, upload
│   ├── appointments/           # Calendar, booking, list views
│   ├── clients/                # Client list, details, preferences
│   ├── employees/              # Staff list, profiles, skills
│   ├── services/               # Service catalog management
│   ├── roles/                  # Role assignment and permissions
│   ├── users/                  # User account management
│   ├── analytics/              # Reports and dashboards
│   ├── income/                 # Income tracking views
│   ├── sellers/                # Supplier management
│   ├── components/             # Reusable template components (sidebar, modals, forms)
│   ├── errors/                 # Error pages (404, 500)
│   └── history/                # Audit trail and change history
├── static/                     # Static assets
│   ├── css/                    # TailwindCSS output and custom CSS
│   ├── js/                     # JavaScript modules
│   │   ├── api.js              # AJAX wrapper and API calls
│   │   ├── utils.js            # DOM utilities, helpers
│   │   ├── notifications.js    # Toast and flash messages
│   │   ├── modals.js           # Modal dialog management
│   │   ├── table-utils.js      # Table sorting, pagination, filtering
│   │   ├── keyboard-shortcuts.js # Keyboard bindings
│   │   ├── ui.js               # General UI utilities
│   │   ├── analytics/          # Analytics-specific scripts
│   │   ├── employees/          # Employee-specific scripts
│   │   ├── invoices/           # Invoice-specific scripts
│   │   └── sellers/            # Seller-specific scripts
│   └── Logo.png
├── uploads/                    # User-uploaded invoice PDFs
│   ├── invoices/               # Processed invoice files
│   └── temp/                   # Temporary staging for uploads
├── assets/                     # Generated/temporary assets
│   └── temp/                   # Temporary files during processing
├── scripts/                    # Utility scripts (data migration, seeding)
│   └── seed_users.py           # Create test users with demo roles
├── tests/                      # Test suites
│   └── repositories/           # Repository unit tests
│       └── analytics/
├── docs/                       # Project documentation
│   └── plans/                  # Implementation plans and designs
├── .planning/                  # GSD analysis documents
│   └── codebase/               # Architecture, structure, conventions (this file location)
├── app.py                      # Flask application factory
├── run_dev.py                  # Development server wrapper
├── gunicorn.conf.py            # Production Gunicorn configuration
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker container definition
├── .env                        # Environment variables (secrets, not committed)
└── tailwind.config.js          # TailwindCSS build configuration
```

## Directory Purposes

**alembic/:**
- Purpose: Database schema version control and migrations
- Contains: Migration scripts with up/down SQL
- Key files: `env.py` (migration config), `versions/` (individual migration files)

**config/:**
- Purpose: Centralize application configuration and decorators
- Contains: Database connection pooling, auth rules, email setup, app settings
- Key files: `auth_config.py` (RBAC decorators), `database.py` (connection), `settings.py` (paths)

**database/:**
- Purpose: Define data structures as Python dataclasses
- Contains: Type-safe entity models with optional fields and conversion methods
- Key files: `models.py` (all entity definitions)

**repositories/:**
- Purpose: Abstract database access and provide CRUD operations
- Contains: SQL queries, row-to-object mapping, transaction management
- Pattern: One repository per entity type, inherits from `BaseRepository`
- Key organization: Subfolders for multi-table modules (appointments, employees, clients, services)

**routes/:**
- Purpose: Handle HTTP requests and return responses
- Contains: Flask blueprints organized by feature area
- Pattern: Each blueprint handles one feature domain (auth, invoices, appointments, etc.)
- Key distinction: `main_routes.py` = server-side rendered pages; API routes = JSON endpoints

**services/:**
- Purpose: Implement business logic and domain workflows
- Contains: Service classes that coordinate repositories, validate data, orchestrate operations
- Pattern: Services are feature-specific (appointment booking, OCR processing, pricing calculations)

**utils/:**
- Purpose: Reusable utility functions for cross-cutting concerns
- Contains: PDF processing, text extraction, validation functions
- Key files: `pdf_processor.py` (parse PDFs), `validators.py` (NIP/IBAN validation)

**templates/:**
- Purpose: Server-side rendered Jinja2 HTML templates
- Contains: Page layouts, components, forms
- Pattern: Organized by feature area; `base.html` is main layout; `components/` has reusable pieces
- Key structure: `{% block content %}` for main content area; sidebar and header injected via `base.html`

**static/:**
- Purpose: Client-side CSS and JavaScript
- Contains: TailwindCSS output, JavaScript modules for interactivity
- Pattern: `api.js` is core AJAX wrapper; feature-specific scripts in subdirectories
- Built: npm script compiles `tailwind.config.js` to `css/output.css`

**uploads/ and assets/:**
- Purpose: Store user-generated and temporary files
- Contains: Invoice PDFs, temporary staging files during processing
- Not committed: Files generated at runtime

**scripts/:**
- Purpose: Standalone Python utilities for data operations
- Contains: Database seeding, migrations, one-off data fixes
- Examples: `seed_users.py` creates test users

**tests/:**
- Purpose: Unit and integration tests
- Current scope: Repository tests primarily
- Location: Mirrors `repositories/` structure

**docs/ and .planning/:**
- Purpose: Project documentation and analysis
- Contains: Implementation plans, design documents, GSD analysis

## Key File Locations

**Entry Points:**

- `app.py`: Main application factory and startup (Flask app initialization, blueprint registration)
- `run_dev.py`: Development server launcher with hot-reloading
- `gunicorn.conf.py`: Production WSGI server configuration

**Configuration:**

- `config/settings.py`: App constants (folder paths, OCR settings, version)
- `config/auth_config.py`: Role definitions, module permissions, decorator implementations
- `config/database.py`: PostgreSQL connection pooling and schema initialization
- `tailwind.config.js`: CSS framework configuration

**Core Logic:**

- `routes/main_routes.py`: Primary page handlers (dashboard, invoices list, etc.)
- `routes/api_routes.py`: JSON API endpoints for AJAX (largest file ~3200 LOC)
- `routes/appointment_routes.py`: Appointment calendar and booking endpoints
- `services/appointment_service.py`: Appointment workflow orchestration
- `services/ocr_service.py`: OCR and text extraction pipeline
- `repositories/invoice_repository.py`: Invoice CRUD operations
- `database/models.py`: All entity dataclass definitions

**Testing:**

- `tests/repositories/`: Repository unit tests
- `scripts/seed_users.py`: Test user initialization

**Database:**

- `alembic/versions/`: Migration scripts by date and description
- `database/schema.sql`: (if exists) Initial schema definition

## Naming Conventions

**Files:**

- `*_routes.py`: Flask blueprint definitions (e.g., `appointment_routes.py`, `auth/routes.py`)
- `*_repository.py`: Data access classes (e.g., `invoice_repository.py`, `user_repository.py`)
- `*_service.py`: Business logic classes (e.g., `ocr_service.py`, `validation_service.py`)
- Template files: `snake_case.html` (e.g., `list_refined.html`, `edit.html`)
- JavaScript modules: `snake_case.js` (e.g., `table-utils.js`, `keyboard-shortcuts.js`)
- Migration files: `YYYYMMDDHHMMSS_description.py` (Alembic standard)

**Directories:**

- Feature-based: `/routes/{feature}`, `/templates/{feature}`, `/repositories/{feature}`
- Utility modules: `/services`, `/utils` (function-based rather than feature-based)
- Static assets: `/static/{css,js}` with subfolders for feature-specific code

**Python Code:**

- Classes: `PascalCase` (e.g., `InvoiceRepository`, `AppointmentBusinessService`, `OCRService`)
- Functions/methods: `snake_case` (e.g., `get_by_id()`, `create_appointment()`, `validate_nip()`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `ALLOWED_EXTENSIONS`, `STATUS_TRANSITIONS`)
- Decorators: `snake_case` (e.g., `@login_required`, `@module_permission_required()`)

**Database:**

- Tables: `snake_case` plural (e.g., `invoices`, `appointments`, `audit_trail`)
- Columns: `snake_case` (e.g., `seller_name`, `invoice_date`, `payment_due_date`)
- Constraints: Implicit via schema (unique, foreign keys, indexes)

## Where to Add New Code

**New Feature (e.g., "Reports" module):**

1. **Routes:** Create `routes/report_routes.py` with Flask blueprint `report_bp`
   - Register blueprint in `app.py` with appropriate URL prefix
   - Apply auth decorators (`@login_required`, `@module_permission_required('reports')`)
   - Call services, render templates or return JSON

2. **Services:** Create `services/report_service.py` if complex business logic needed
   - Coordinate multiple repositories for data aggregation
   - Implement business rules and calculations
   - Handle errors with domain-specific exceptions

3. **Repositories:** Create `repositories/report_repository.py` if new data access patterns needed
   - Inherit from `BaseRepository` or implement specific queries
   - Provide methods for filtering, aggregation, export

4. **Models:** Add dataclass to `database/models.py` if new entity type
   - Include `id` field and timestamps (`created_at`, `updated_at`)
   - Add optional fields with `Optional[Type] = None` defaults

5. **Templates:** Create `templates/reports/` directory
   - Extend `base.html` for authenticated pages
   - Use TailwindCSS utility classes (configured in `tailwind.config.js`)
   - Include component fragments from `templates/components/`

6. **Database:** Create migration in `alembic/versions/`
   - Use descriptive filename: `YYYYMMDDHHMMSS_add_reports_table.py`
   - Include both `upgrade()` and `downgrade()` functions

7. **Tests:** Add unit tests in `tests/repositories/reports/`
   - Test data access methods with mock or test database
   - Mock external service dependencies

**New Component (e.g., Modal, Form):**

1. Create template in `templates/components/{name}.html`
2. Use Jinja2 macros if parameterized (e.g., `{% macro button(label, onclick) %}`)
3. Include in parent template via `{% include 'components/{name}.html' %}`
4. Implement JavaScript behavior if needed in `static/js/{feature}/{component}.js`

**Utilities (Reusable Functions):**

- Add to `utils/` if general-purpose (PDF processing, validation)
- Prefix module with type (e.g., `utils/validators.py` for validation functions)
- Avoid duplicating code across services; move common patterns to utils

## Special Directories

**uploads/ and assets/:**
- Purpose: Store runtime-generated files
- Generated: Yes (created during application operation)
- Committed: No (listed in `.gitignore`)
- Cleanup: Old uploads should be pruned via maintenance scripts

**.planning/codebase/:**
- Purpose: GSD (Godspeed Development) analysis documents
- Generated: Yes (by GSD commands like `/gsd:map-codebase`)
- Committed: Yes (for knowledge preservation)
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md

**alembic/versions/:**
- Purpose: Track schema evolution
- Generated: No (manually created by developers)
- Committed: Yes (critical for reproducibility)
- Pattern: Each migration is idempotent and reversible

**tests/**
- Purpose: Verify code correctness
- Generated: No (manually written)
- Committed: Yes (part of test suite)
- Running: `pytest` or test runner (if configured)

---

*Structure analysis: 2026-03-13*
