# Architecture

**Analysis Date:** 2026-03-13

## Pattern Overview

**Overall:** Layered MVC (Model-View-Controller) with Repository pattern for data access

**Key Characteristics:**
- Clear separation between Flask routes (controllers), repositories (data access), services (business logic)
- Modular blueprint-based route organization by feature area
- Per-request database connections managed via Flask's `g` object
- Mix of Server-Side Rendering (Jinja2 templates) + JSON API endpoints for rich client-side interactivity

## Layers

**Presentation (UI):**
- Purpose: Render HTML templates and serve static assets
- Location: `templates/`, `static/`
- Contains: Jinja2 templates (page layouts, components), TailwindCSS, JavaScript modules
- Depends on: Flask routes, API endpoints
- Used by: Web browsers, authenticated users

**Routing/Controllers:**
- Purpose: Handle HTTP requests, parse inputs, coordinate business logic, return responses
- Location: `routes/`
- Contains: Flask blueprints organized by feature (`auth/`, `users/`, `appointments/`, `analytics/`, etc.)
- Depends on: Repositories, services, models
- Used by: Client requests via HTTP

**Business Logic/Services:**
- Purpose: Orchestrate domain operations, implement business rules, coordinate across repositories
- Location: `services/`
- Contains: `AppointmentBusinessService`, `OCRService`, `ValidationService`, `EmailService`, `PricingService`, `SellerService`, auth services
- Depends on: Repositories, utilities, models
- Used by: Routes, other services

**Data Access (Repository):**
- Purpose: Encapsulate SQL queries, handle CRUD operations on database entities
- Location: `repositories/`
- Contains: Base repository with common patterns; specialized repos for invoices, users, appointments, clients, employees, services, etc.
- Depends on: Database connection, models, utility functions
- Used by: Services and routes

**Data Models:**
- Purpose: Define data structures and application entities
- Location: `database/models.py`
- Contains: Dataclasses for Invoice, User, Appointment, Client, Employee, Service, AuditEntry, etc.
- Depends on: Python stdlib, Flask-Login (for UserMixin)
- Used by: Repositories, services, routes

**Database Layer:**
- Purpose: Manage PostgreSQL connection pooling, schema initialization, transaction management
- Location: `config/database.py`
- Contains: `DatabaseConnection` class with per-request connection via `g` object, schema initialization
- Depends on: psycopg2, Flask's g object
- Used by: Repositories

**Configuration:**
- Purpose: Centralize app settings, authentication/authorization rules, environment setup
- Location: `config/`
- Contains: Database config, auth decorators/rules, email settings, app settings
- Depends on: Environment variables, decorator framework
- Used by: App initialization, route protection

**Utilities:**
- Purpose: Reusable functions for cross-cutting concerns (PDF processing, validation, text extraction)
- Location: `utils/`
- Contains: PDF processor, text extractor, validators (NIP, IBAN, dates)
- Depends on: External libraries (PyMuPDF, pytesseract, OpenCV, etc.)
- Used by: Services, routes, upload handling

## Data Flow

**Synchronous Request Flow (HTML Page):**

1. User navigates to route (e.g., `/invoices`)
2. Flask route handler (`main_routes.py`) receives request
3. Route applies decorators (`@login_required`, `@module_permission_required`)
4. Route retrieves data from repositories (e.g., `current_app.invoice_repo.get_all()`)
5. Template renders data with `render_template()`
6. HTML with embedded JavaScript returns to browser

**AJAX/JSON Flow (API Calls):**

1. Client JavaScript calls `API.get('/api/appointments/list')`
2. Flask API route (`api_routes.py` or specialized routes) handles request
3. Route validates input, calls service or repository
4. Business logic executes (e.g., `AppointmentBusinessService.list_appointments()`)
5. Repository queries database, returns rows
6. Route converts database rows to objects/dicts via repository methods
7. JSON response sent back to client
8. Client JavaScript updates DOM

**Upload/Processing Flow:**

1. User uploads PDF via `/api/upload` endpoint
2. `upload_routes.py` receives file, stores in temp folder
3. `OCRService` (from `services/ocr_service.py`) extracts text from PDF
4. `ValidationService` validates extracted fields (NIP, IBAN, dates)
5. `DuplicateDetectionService` checks for existing invoices
6. Routes save processed invoice to database via `InvoiceRepository`
7. Audit trail logged via `AuditRepository`
8. JSON response with invoice data returned

**State Management:**

- **User Sessions:** Flask-Login manages via `current_user` and session cookies
- **Database Transactions:** Per-request connections via `g.db`, auto-commit after each query
- **Request Context:** Decorators (`@login_required`, `@module_permission_required`) enforce auth before business logic
- **Audit Trail:** `AuditRepository` logs all changes for compliance/debugging

## Key Abstractions

**Repository Pattern:**
- Purpose: Decouple data access from business logic
- Examples: `InvoiceRepository`, `UserRepository`, `AppointmentRepository`, `ClientRepository` in `repositories/`
- Pattern: Base class `BaseRepository` provides `_fetch_one()`, `_fetch_all()`, `_execute()`, `get_by_id()`; subclasses override with entity-specific queries

**Service Pattern (Business Logic):**
- Purpose: Implement domain workflows, coordinate multiple repositories
- Examples: `AppointmentBusinessService` orchestrates appointment creation with validations; `OCRService` handles PDF extraction pipeline
- Pattern: Services receive repositories in `__init__`, expose high-level methods, throw domain-specific exceptions

**Model Objects:**
- Purpose: Type-safe data containers with Flask-Login integration (User)
- Examples: `Invoice`, `User`, `Appointment`, `Client` from `database/models.py`
- Pattern: Dataclasses with optional fields and conversion methods

**Blueprint Organization:**
- Purpose: Group routes by feature area for modularity
- Examples: `auth_bp` (login, logout, profile), `appointment_bp` (appointment CRUD), `analytics_bp` (reports)
- Pattern: Each feature has dedicated blueprint registered with prefix in `app.py`

**Decorator-Based Authorization:**
- Purpose: Enforce authentication and role-based access control at route level
- Examples: `@login_required`, `@module_permission_required('invoices')`, `@role_required('admin')`
- Pattern: Decorators check Flask-Login's `current_user` and role against static config or dynamic role repository

## Entry Points

**Web Application:**
- Location: `app.py`
- Triggers: `python app.py` (dev) or gunicorn launcher (production)
- Responsibilities:
  - Create Flask app with JSON provider
  - Initialize database schema
  - Set up repositories and services
  - Register blueprints
  - Configure error handlers
  - Set up Flask-Login and context processors

**Development Server:**
- Location: `run_dev.py`
- Triggers: `python run_dev.py` for hot-reloading during development
- Responsibilities: Wrap `create_app()` with Flask development server

**CLI/Database Scripts:**
- Locations: `scripts/seed_users.py`, migration scripts in `alembic/versions/`
- Responsibilities: Initialize test users, manage schema migrations

**Celery/Background Tasks:**
- Current status: Not detected; email sending may be synchronous or basic async

## Error Handling

**Strategy:** Mix of try-catch blocks, flash messages, and HTTP error codes

**Patterns:**

- **Route-Level Validation:** Input validation returns 400/422 with error messages to client
- **Service-Level Exceptions:** Custom exceptions (e.g., `AppointmentError` in `appointment_service.py`) propagate to routes which convert to HTTP responses
- **Database Errors:** psycopg2 exceptions caught in repositories, logged, re-raised to routes
- **Audit Logging:** All errors and state changes logged via `AuditRepository.log_event()`
- **Error Templates:** `templates/errors/404.html`, `500.html` for unhandled exceptions
- **Flash Messages:** Client receives user-friendly error text via Flask's flash system
- **Client-Side:** JavaScript API wrapper catches fetch errors, displays toast notifications via `notifications.js`

## Cross-Cutting Concerns

**Logging:**
- Framework: Python's logging module with console output
- Special loggers for debug: `utils.pdf_processor`, `services.ocr_service`
- Timestamps and structured format for production debugging

**Validation:**
- Input validation in routes before passing to services
- Entity-level validation via `ValidationService` (dates, NIP, IBAN, amounts)
- Repository-level data integrity (e.g., unique constraints in database schema)

**Authentication:**
- Framework: Flask-Login with user session management
- Strategy: Email + bcrypt password hash verification
- Routes protected via `@login_required` decorator
- User object loaded on each request via `LoginManager.user_loader`

**Authorization (RBAC):**
- Module-level: `@module_permission_required('invoices')` checks role against `MODULE_PERMISSIONS`
- Role-level: `@role_required('admin', 'superuser')` for admin-only routes
- Fallback: Static config in `config/auth_config.py` + dynamic lookup in role repository

**Audit Trail:**
- All data mutations logged to `audit_trail` table with entity type, action, field changes, user, timestamp
- Used for compliance, debugging, and undo/revision features

**Transactions:**
- Per-request auto-commit after each SQL statement
- Flask's `teardown_appcontext` hook closes connection after response
- No explicit transaction wrapping for complex workflows

---

*Architecture analysis: 2026-03-13*
