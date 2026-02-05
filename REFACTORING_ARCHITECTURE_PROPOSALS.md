# FakturaScanner → Beauty Salon Management System
## Architecture Refactoring Proposals

**Date:** 2026-02-05
**Current State:** Single-module invoice management Flask application
**Target State:** Multi-module beauty salon management system with appointments, clients, employees, and services

---

## Table of Contents

1. [Requirements Summary](#requirements-summary)
2. [Approach 1: Minimal Viable Refactoring](#approach-1-minimal-viable-refactoring)
3. [Approach 2: Clean Architecture](#approach-2-clean-architecture)
4. [Approach 3: Pragmatic Migration Strategy](#approach-3-pragmatic-migration-strategy)
5. [Comparison Matrix](#comparison-matrix)
6. [Recommendation](#recommendation)

---

## Requirements Summary

### User Requirements (from refactoring_answers.txt)

**Authentication & Roles:**
- New `users` table + `employees` table (separate from invoice sellers)
- 5 roles: Superuser, Admin, Receptionist, Stylist, Accountant
- Flask-Login for session management

**Data Relationships:**
- Appointments: 1 client, 1 employee, multiple services
- Services have dynamic pricing (employee-specific)
- Separate `income` table generated from completed appointments
- Client stats: Calculated on-demand (not denormalized)

**Database Strategy:**
- Migrate to Alembic for version control
- Plan migration path to PostgreSQL
- Hard deletes with comprehensive audit logs

**Module Features:**
- **Appointments:** Calendar (day/week/month), status workflow, email/SMS reminders, NO recurring
- **Clients:** Contact info (no address), notes/preferences, GDPR consent, NO photos
- **Services:** Dynamic pricing, duration, categories, employee-specific rates
- **Employees:** Schedule, commission (% + base salary), skills with ratings, performance metrics

**Code Organization:**
- Option C (Hybrid): Sub-packages in `repositories/` and `services/` folders
- Shared code: `core/` for base classes, `auth/` module separate
- Backward compatibility: Preserve existing invoice API endpoints

**Frontend:**
- Module-grouped navigation
- Component library approach

---

## Approach 1: Minimal Viable Refactoring

### Executive Summary

**Philosophy:** Add structure with ZERO breaking changes to existing functionality. Additive architecture where new modules coexist with legacy code.

**Timeline:** 3 phases over 2-4 weeks
**Risk Level:** Low (maximum backward compatibility)
**Implementation Effort:** Medium

### Key Characteristics

- **Dual migration system:** Alembic for new tables, manual migrations for invoices
- **Optional authentication (Phase 1):** Invoice routes work without login initially
- **Additive folder structure:** New modules added alongside existing files
- **SQLite first:** Defer PostgreSQL migration to Phase 4

### Directory Structure

```
faktura_scanner_flask/
├── app.py                          [MODIFY] Add Flask-Login + auth blueprint
├── requirements.txt                [MODIFY] Add Flask-Login, Alembic, psycopg2-binary
├── alembic/                        [NEW] Migration management
│   ├── env.py
│   └── versions/
│       ├── 001_add_users_employees.py
│       ├── 002_add_clients_services.py
│       └── 003_add_appointments.py
│
├── config/
│   ├── settings.py                 [UNCHANGED]
│   ├── database.py                 [MODIFY] Add Alembic support
│   └── auth_config.py              [NEW] Flask-Login, roles, permissions
│
├── database/
│   ├── schema.sql                  [UNCHANGED] Keep for backward compat
│   └── models.py                   [MODIFY] Add new models (User, Employee, Client, etc.)
│
├── repositories/
│   ├── base_repository.py          [UNCHANGED]
│   ├── invoice_repository.py       [UNCHANGED]
│   ├── audit_repository.py         [UNCHANGED]
│   ├── seller_repository.py        [UNCHANGED]
│   │
│   ├── auth/                       [NEW] Auth module repositories
│   │   ├── user_repository.py
│   │   └── employee_repository.py
│   │
│   ├── clients/                    [NEW]
│   │   └── client_repository.py
│   │
│   ├── services/                   [NEW]
│   │   ├── service_repository.py
│   │   └── category_repository.py
│   │
│   └── appointments/               [NEW]
│       └── appointment_repository.py
│
├── services/                       [KEEP AS-IS] Existing services remain
│   ├── ocr_service.py              [UNCHANGED]
│   ├── validation_service.py       [UNCHANGED]
│   ├── duplicate_detection_service.py [UNCHANGED]
│   ├── email_service.py            [UNCHANGED]
│   ├── export_service.py           [UNCHANGED]
│   ├── seller_service.py           [UNCHANGED]
│   │
│   ├── auth/                       [NEW]
│   │   ├── auth_service.py
│   │   └── permission_service.py
│   │
│   ├── clients/                    [NEW]
│   │   └── client_service.py
│   │
│   ├── salon_services/             [NEW] Renamed to avoid conflict
│   │   └── service_catalog_service.py
│   │
│   └── appointments/               [NEW]
│       ├── appointment_service.py
│       ├── calendar_service.py
│       └── reminder_service.py
│
├── routes/
│   ├── main_routes.py              [MODIFY] Add new module pages
│   ├── api_routes.py               [UNCHANGED] Invoice API preserved
│   ├── upload_routes.py            [UNCHANGED]
│   │
│   ├── auth_routes.py              [NEW]
│   ├── client_routes.py            [NEW]
│   ├── service_routes.py           [NEW]
│   ├── employee_routes.py          [NEW]
│   └── appointment_routes.py       [NEW]
│
├── templates/
│   ├── base.html                   [MODIFY] Add auth status, module nav
│   ├── invoices/                   [UNCHANGED] All existing
│   ├── auth/                       [NEW]
│   ├── clients/                    [NEW]
│   ├── services/                   [NEW]
│   ├── employees/                  [NEW]
│   └── appointments/               [NEW]
│
└── static/
    ├── css/                        [UNCHANGED]
    └── js/
        ├── api.js                  [UNCHANGED]
        ├── utils.js                [UNCHANGED]
        ├── auth/                   [NEW]
        ├── clients/                [NEW]
        ├── services/               [NEW]
        ├── employees/              [NEW]
        └── appointments/           [NEW]
```

### Database Schema

**Existing Tables:** All preserved without modification
- `invoices` (no foreign keys added initially)
- `sellers`, `audit_log`, `duplicate_detection`, `upload_staging`

**New Tables (via Alembic):**

```sql
-- Migration 001: Authentication
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'receptionist',
    is_active BOOLEAN DEFAULT 1,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    position VARCHAR(100),
    employment_status VARCHAR(50) DEFAULT 'active',
    hourly_rate DECIMAL(10, 2),
    commission_rate DECIMAL(5, 2),
    skills TEXT,  -- JSON
    work_schedule TEXT,  -- JSON
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Migration 002: Clients & Services
CREATE TABLE clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) UNIQUE,
    email VARCHAR(255) UNIQUE,
    marketing_consent BOOLEAN DEFAULT 0,
    first_visit_date DATE,
    last_visit_date DATE,
    total_visits INTEGER DEFAULT 0,
    total_spent DECIMAL(10, 2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    base_price DECIMAL(10, 2) NOT NULL,
    duration_minutes INTEGER NOT NULL,
    buffer_minutes INTEGER DEFAULT 15,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (category_id) REFERENCES service_categories(id)
);

-- Migration 003: Appointments
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    appointment_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status VARCHAR(50) DEFAULT 'scheduled',
    price DECIMAL(10, 2) NOT NULL,
    payment_status VARCHAR(50) DEFAULT 'pending',
    reminder_sent BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE RESTRICT
);
```

### Implementation Phases

**Phase 1: Foundation (3-5 days)**
- Day 1-2: Folder structure + Alembic setup + User tables
- Day 3: Authentication (login/logout routes)
- Day 4-5: Navigation update + testing

**Phase 2: Core Modules (5-7 days)**
- Day 6-7: Clients module (CRUD + templates)
- Day 8-9: Services module (catalog + pricing)
- Day 10-12: Employees module (profiles + schedules)

**Phase 3: Advanced Features (4-6 days)**
- Day 13-15: Appointments module (booking + status workflow)
- Day 16-18: Calendar integration (FullCalendar.js)

### Backward Compatibility Strategy

**Invoice API Endpoints - 100% Preserved:**
```
✓ GET    /api/invoices                [UNCHANGED]
✓ GET    /api/invoices/<id>           [UNCHANGED]
✓ POST   /api/invoices                [UNCHANGED]
✓ PUT    /api/invoices/<id>           [UNCHANGED]
✓ DELETE /api/invoices/<id>           [UNCHANGED]
✓ GET    /api/invoices/statistics     [UNCHANGED]
✓ POST   /api/upload/files            [UNCHANGED]
```

**New Endpoints Added Separately:**
```
NEW POST   /api/auth/login
NEW POST   /api/auth/logout
NEW GET    /api/clients
NEW POST   /api/clients
NEW GET    /api/appointments
...
```

### Authentication Integration

**Minimal Flask-Login Setup:**

```python
# config/auth_config.py
ROLE_HIERARCHY = {
    'superuser': 5,
    'admin': 4,
    'receptionist': 3,
    'stylist': 2,
    'accountant': 1,
}

MODULE_PERMISSIONS = {
    'invoices': ['superuser', 'admin', 'accountant'],
    'appointments': ['superuser', 'admin', 'receptionist', 'stylist'],
    'clients': ['superuser', 'admin', 'receptionist', 'stylist'],
    'employees': ['superuser', 'admin'],
    'services': ['superuser', 'admin'],
}

def role_required(*roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                flash('Brak uprawnień', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

### Trade-offs

**Sacrifices for Speed:**

1. **Dual Migration System**
   - Alembic for new tables, manual for invoices
   - Compromise: Accept hybrid for 6 months
   - Benefit: Zero risk to existing invoice data

2. **Optional Authentication (Phase 1)**
   - Invoice routes work without login initially
   - Compromise: Partial open system during transition
   - Benefit: Existing users not disrupted

3. **Hard Deletes + Audit Logs**
   - No soft deletes (deleted_at pattern)
   - Compromise: Harder to recover, but simpler queries
   - Benefit: Audit log provides recovery path

4. **SQLite First**
   - Not ideal for concurrent writes
   - Compromise: Launch on SQLite, migrate to Postgres after testing
   - Benefit: Faster initial deployment

### Success Criteria

- ✅ All existing invoice functionality preserved
- ✅ Login working with role-based navigation in 1 week
- ✅ First new module (Clients) functional in 2 weeks
- ✅ Complete system ready in 4 weeks

---

## Approach 2: Clean Architecture

**Status:** ⚠️ Agent hit rate limit during analysis

**Planned Focus:**
- Layered architecture (Domain, Application, Infrastructure, Presentation)
- Comprehensive dependency injection
- Design pattern implementation (Factory, Strategy, Observer)
- Testing infrastructure (unit, integration, fixtures)
- Long-term scalability (5+ year foundation)

**Key Principles:**
- Proper separation of concerns across layers
- Reusable abstractions (base services, base controllers)
- Module boundaries with clear interfaces
- Normalized database schema with constraints
- Future-proofing (background jobs, caching, multi-tenancy)

**Implementation Complexity:** High
**Timeline:** Longer (6-8 weeks estimated)
**Benefit:** Maximum maintainability and scalability

*Note: This approach requires more upfront design but provides strongest foundation for long-term growth. Recommended if timeline permits and team has strong architecture experience.*

---

## Approach 3: Pragmatic Migration Strategy

### Executive Summary

**Philosophy:** Balance speed with quality through incremental delivery. Ship working features fast, refine later. Strangler Fig Pattern - new modules coexist with legacy, gradual replacement.

**Timeline:** 6 phases over 12-16 weeks (2-3 weeks per phase)
**Risk Level:** Medium (mitigated through careful sequencing)
**Implementation Effort:** High (but spread over time)

### Key Characteristics

- **Incremental value delivery:** Each phase ships working features, not just infrastructure
- **Parallel work streams:** Backend, Frontend, Integration, Testing teams work simultaneously
- **Battle-tested libraries:** FullCalendar.js, Twilio, Chart.js, Flask-APScheduler
- **Phased refactoring:** Invoices stay legacy until Phase 6
- **80/20 rule:** Focus on high-value features, defer polish

### Directory Structure

```
faktura_scanner_flask/
├── app.py
├── requirements.txt
├── alembic.ini
├── alembic/
│   └── versions/
│       ├── 001_create_users_tables.py
│       ├── 002_create_clients_table.py
│       ├── 003_create_services_tables.py
│       ├── 004_create_employees_tables.py
│       └── 005_create_appointments_table.py
│
├── config/
│   ├── settings.py                 # Add AUTH_SECRET_KEY, TWILIO_*, DB_URL
│   ├── database.py                 # Support Alembic + PostgreSQL
│   └── roles.py                    [NEW] Role enum
│
├── repositories/                   # Organized by module (sub-packages)
│   ├── base_repository.py          # Enhanced with soft delete support
│   ├── invoices/                   [NEW] Sub-package
│   │   ├── invoice_repo.py
│   │   └── audit_repo.py
│   ├── clients/
│   │   ├── client_repo.py
│   │   └── note_repo.py
│   ├── services/
│   │   ├── service_repo.py
│   │   └── category_repo.py
│   ├── employees/
│   │   ├── employee_repo.py
│   │   └── schedule_repo.py
│   ├── appointments/
│   │   └── appointment_repo.py
│   └── users/
│       └── user_repo.py
│
├── services/                       # Business logic (sub-packages)
│   ├── invoices/
│   │   ├── ocr_service.py
│   │   ├── validation_service.py
│   │   ├── duplicate_detection_service.py
│   │   └── export_service.py
│   ├── clients/
│   │   └── client_service.py
│   ├── services/                   # Consider 'salon_services/'
│   │   └── service_management.py
│   ├── employees/
│   │   ├── employee_service.py
│   │   └── commission_calculator.py
│   ├── appointments/
│   │   ├── appointment_service.py
│   │   ├── conflict_checker.py
│   │   └── status_machine.py       # FSM for status workflow
│   ├── notifications/
│   │   ├── email_service.py
│   │   ├── sms_service.py
│   │   └── reminder_scheduler.py
│   └── auth/
│       ├── auth_service.py
│       └── permission_service.py
│
├── routes/                         # Flask blueprints (module-grouped)
│   ├── invoices/                   [NEW] Sub-package
│   │   ├── routes.py               # HTML views
│   │   └── api.py                  # JSON API
│   ├── clients/
│   │   ├── routes.py
│   │   └── api.py
│   ├── services/
│   │   ├── routes.py
│   │   └── api.py
│   ├── employees/
│   │   ├── routes.py
│   │   └── api.py
│   ├── appointments/
│   │   ├── routes.py
│   │   └── api.py
│   └── auth/
│       └── routes.py
│
├── templates/
│   ├── base.html                   # Role-based nav + user menu
│   ├── auth/
│   │   ├── login.html
│   │   └── reset_password.html
│   ├── dashboard/
│   │   └── index.html              # Role-specific dashboard
│   ├── invoices/                   # Keep existing
│   ├── clients/
│   │   ├── list.html
│   │   ├── detail.html
│   │   └── edit.html
│   ├── services/
│   │   ├── list.html
│   │   └── edit.html
│   ├── employees/
│   │   ├── list.html
│   │   ├── detail.html
│   │   └── edit.html
│   └── appointments/
│       ├── calendar.html
│       ├── list.html
│       └── detail.html
│
├── static/
│   ├── css/
│   │   ├── input.css
│   │   └── output.css
│   └── js/
│       ├── api.js                  # Enhanced with auth headers
│       ├── utils.js
│       ├── auth/
│       │   └── login.js
│       ├── clients/
│       │   ├── list.js
│       │   └── detail.js
│       ├── services/
│       │   └── list.js
│       ├── employees/
│       │   └── list.js
│       └── appointments/
│           ├── calendar.js         # FullCalendar integration
│           └── booking.js
│
└── tests/                          [NEW] Test suite
    ├── unit/
    │   ├── test_auth_service.py
    │   └── test_client_service.py
    ├── integration/
    │   └── test_appointment_flow.py
    └── fixtures/
        └── sample_data.py
```

### Implementation Phases

**Phase 1: Foundation + Quick Win (Week 1-2)**
- **Goal:** Authentication working + First visible change
- **Deliverables:**
  - ✅ User can log in with email/password
  - ✅ Role-based sidebar navigation
  - ✅ Existing invoice module works for authenticated users
  - ✅ Alembic migrations initialized

**Phase 2: Client Management (Week 3-4)**
- **Goal:** First complete new module
- **Deliverables:**
  - ✅ Client list with search/filter
  - ✅ Add/edit client form
  - ✅ Client detail page with notes
  - ✅ GDPR consent upload
  - ✅ Audit log for changes

**Phase 3: Services & Employee Basics (Week 5-7)**
- **Goal:** Service catalog + Employee profiles
- **Deliverables:**
  - ✅ Service list with categories
  - ✅ Dynamic pricing (base + duration)
  - ✅ Employee profiles
  - ✅ Skill tagging (employee → services)
  - ✅ Commission settings

**Phase 4: Appointments Core (Week 8-10)**
- **Goal:** Book appointments + Status workflow
- **Deliverables:**
  - ✅ Calendar view (weekly grid)
  - ✅ Appointment booking form
  - ✅ Status workflow (Zarezerwowane → Potwierdzone → Wykonane → Anulowane)
  - ✅ Conflict detection
  - ✅ Appointment list view

**Phase 5: Advanced Features (Week 11-13)**
- **Goal:** Reminders + Reporting
- **Deliverables:**
  - ✅ SMS reminders (Twilio, 24h before)
  - ✅ Email reminders
  - ✅ Employee metrics dashboard
  - ✅ Financial reports
  - ✅ Client history page

**Phase 6: Polish + Migration (Week 14-16)**
- **Goal:** Refactor invoices + Optimization
- **Deliverables:**
  - ✅ Invoice module migrated to sub-package structure
  - ✅ Unified audit system
  - ✅ API documentation (Swagger)
  - ✅ Performance optimization
  - ✅ Production deployment

### Database Schema (Start Simple)

**Phase 1 Tables:**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_roles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,  -- 'superuser', 'admin', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Phase 2 Tables:**
```sql
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20) NOT NULL,
    birth_date DATE,
    notes TEXT,
    consent_document_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id)
);

CREATE TABLE client_notes (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Phase 3 Tables:**
```sql
CREATE TABLE service_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    display_order INTEGER DEFAULT 0
);

CREATE TABLE services (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES service_categories(id),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    base_price DECIMAL(10, 2) NOT NULL,
    duration_minutes INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    photo_path VARCHAR(500),
    commission_type VARCHAR(20) DEFAULT 'percentage',
    commission_value DECIMAL(10, 2) DEFAULT 0.00,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE employee_skills (
    employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,
    service_id INTEGER REFERENCES services(id) ON DELETE CASCADE,
    skill_level VARCHAR(20) DEFAULT 'proficient',
    PRIMARY KEY (employee_id, service_id)
);
```

**Phase 4 Tables:**
```sql
CREATE TABLE appointments (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    service_id INTEGER REFERENCES services(id) ON DELETE SET NULL,
    appointment_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status VARCHAR(50) DEFAULT 'zarezerwowane',
    notes TEXT,
    cancellation_reason TEXT,
    reminder_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id)
);

CREATE INDEX idx_appointments_date ON appointments(appointment_date);
CREATE INDEX idx_appointments_employee ON appointments(employee_id);
CREATE INDEX idx_appointments_client ON appointments(client_id);
```

### Technology Choices (Battle-Tested)

| Component | Library | Rationale |
|-----------|---------|-----------|
| **Authentication** | Flask-Login | Standard Flask auth, well-documented |
| **Password Hashing** | bcrypt | Industry standard |
| **Migrations** | Alembic | PostgreSQL-ready, supports rollbacks |
| **Calendar UI** | FullCalendar.js (MIT) | Drag-and-drop, 50k+ stars, mobile-responsive |
| **Background Jobs** | Flask-APScheduler | Lightweight, no Redis needed |
| **SMS** | Twilio | Reliable, $0.02-0.05 per SMS |
| **Charts** | Chart.js | Simple, responsive |
| **API Docs** | Flasgger | Auto-generates Swagger UI |
| **Testing** | pytest + pytest-flask | Standard Python testing |
| **Load Testing** | Locust | Python-based scenarios |

### Parallel Work Streams

**Stream A: Backend (Database + API)**
- Phase 1: Alembic + User tables
- Phase 2: Client repository
- Phase 3: Services + Employees
- Phase 4: Appointments + conflict logic
- Phase 5: Reports + metrics

**Stream B: Frontend (Templates + JS)**
- Phase 1: Login page + navigation
- Phase 2: Client pages
- Phase 3: Service catalog + employee profiles
- Phase 4: Calendar UI (FullCalendar.js)
- Phase 5: Charts (Chart.js)

**Stream C: Integrations (Email + SMS)**
- Phase 1: Email service refactor
- Phase 5: Twilio SMS integration
- Phase 5: APScheduler setup
- Phase 6: Production deployment

**Stream D: Testing + Docs**
- Phase 1-2: Unit tests
- Phase 3-4: Integration tests
- Phase 5: Load testing
- Phase 6: API documentation

### Quick Wins (First 2 Weeks)

**Week 1: Authentication MVP**
- Day 1-2: User model + login routes
- Day 3-4: Role-based navigation
- Day 5: Protect invoice routes
- **Demo:** User logs in, sees personalized menu

**Week 2: Client Module MVP**
- Day 1-2: Client table + repository
- Day 3-4: Client list + edit pages
- Day 5: Client notes feature
- **Demo:** Receptionist adds client, searches, adds note

### Risk Mitigation

**Risk 1: Calendar Complexity**
- **Mitigation:** Use FullCalendar.js (battle-tested library)
- **Contingency:** Simple list view + time slots fallback

**Risk 2: Migration Breaks Invoices**
- **Mitigation:** Integration tests before refactor, feature flags
- **Contingency:** Revert migration, continue with flat structure

**Risk 3: Alembic Conflicts**
- **Mitigation:** One owner per phase, descriptive names
- **Contingency:** Manual merge (Alembic supports this)

**Risk 4: SMS Costs Runaway**
- **Mitigation:** Manual approve Phase 5, rate limiting, opt-in
- **Contingency:** Disable SMS, email-only reminders

**Risk 5: Performance Degradation**
- **Mitigation:** Index critical columns, paginate, cache stats
- **Contingency:** PostgreSQL partitioning by year

### Trade-offs & Technical Debt

| Decision | Trade-off | When to Revisit |
|----------|-----------|-----------------|
| SQLite in Phase 1-4 | No concurrent writes | Phase 6 (PostgreSQL) |
| No soft deletes | Can't recover deleted | Phase 5 (if requested) |
| Simple role enum | Can't customize per user | Phase 5+ (if needed) |
| File system storage | No CDN, manual backups | Phase 6 (if scaling) |
| Synchronous reminders | Blocks request | Phase 5 (Celery queue) |
| No API versioning | Breaking changes affect clients | Phase 6 (/api/v1/) |
| Manual invoice linking | User links invoice to appointment | Phase 5 (auto-create) |

**Acceptable Technical Debt:**
- Test coverage <50% in Phase 1-4 (add in Phase 6)
- No API rate limiting (add in production)
- Hardcoded Polish language (i18n deferred)
- No email queue (switch to Celery if >100/day)
- No frontend bundler (add Webpack/Vite if >50 files)

### Success Metrics

**Phase 1-2:**
- ✅ User logs in successfully (100%)
- ✅ Client CRUD works (no errors)
- ✅ Invoices still accessible

**Phase 3-4:**
- ✅ 20+ services entered
- ✅ 10+ employees with skills
- ✅ 50+ appointments on calendar
- ✅ 0 double-booking overlaps

**Phase 5-6:**
- ✅ 90%+ reminder delivery rate
- ✅ Dashboard loads <2 seconds
- ✅ 1000+ appointments without issues
- ✅ 80%+ API documentation coverage

### Implementation Checklist

**Before Starting:**
```
□ Stakeholder approval
□ Dev environment setup
□ Git branch strategy
□ Team role assignments
□ Project board (Trello/Jira)
```

**Phase 1 Kickoff (Week 1, Day 1):**
```
□ Install: Flask-Login, Alembic, bcrypt
□ Initialize Alembic: `alembic init alembic`
□ Create first migration
□ Update config/database.py
□ Create auth blueprint
□ Create login.html
□ Test login locally
```

---

## Comparison Matrix

| Aspect | Minimal Refactoring | Clean Architecture | Pragmatic Migration |
|--------|--------------------|--------------------|---------------------|
| **Timeline** | 2-4 weeks | 6-8 weeks | 12-16 weeks |
| **Complexity** | Low-Medium | High | Medium |
| **Risk Level** | Low | Medium | Medium |
| **Backward Compat** | 100% preserved | 90% preserved | 100% preserved |
| **Testing Coverage** | Minimal | Comprehensive | Progressive |
| **Scalability** | Medium | High | High |
| **Maintenance** | Medium | High | High |
| **Learning Curve** | Low | High | Medium |
| **Value Delivery** | Fast (single drop) | Slow (big bang) | Incremental |
| **Technical Debt** | Medium | Low | Low-Medium |
| **Team Size** | 1-2 devs | 3-4 devs | 2-3 devs |
| **PostgreSQL Ready** | Phase 4+ | Day 1 | Phase 6 |
| **Alembic Migrations** | Yes (new tables) | Yes (all tables) | Yes (all tables) |
| **Auth Implementation** | Optional → Required | Required from start | Required Phase 1 |
| **Parallel Work** | Limited | Yes | Yes |
| **Production Ready** | Week 4 | Week 8 | Week 16 |

### Scoring (1-5, 5 = best)

| Criteria | Minimal | Clean | Pragmatic |
|----------|---------|-------|-----------|
| **Speed to MVP** | 5 | 2 | 4 |
| **Long-term Maintainability** | 3 | 5 | 4 |
| **Risk Management** | 5 | 3 | 4 |
| **Code Quality** | 3 | 5 | 4 |
| **Team Productivity** | 4 | 3 | 5 |
| **Flexibility** | 3 | 5 | 4 |
| **Cost (dev time)** | 5 | 2 | 3 |
| **Scalability** | 3 | 5 | 4 |
| **TOTAL** | **31/40** | **30/40** | **32/40** |

---

## Recommendation

### **Recommended Approach: Pragmatic Migration Strategy**

**Reasoning:**

1. **Best Balance:** Combines speed of Minimal with quality of Clean Architecture
2. **Incremental Value:** Each phase delivers working features (not just infrastructure)
3. **Risk Mitigation:** Parallel work streams reduce bottlenecks, careful sequencing avoids breakage
4. **Production-Grade:** By Week 16, system is fully tested, documented, optimized
5. **Team Alignment:** Clear phases allow multiple developers to work simultaneously
6. **Battle-Tested Tech:** Uses proven libraries (FullCalendar.js, Twilio) instead of reinventing wheels

**When to Choose Minimal Instead:**
- Single developer working alone
- Need working system in 1 month
- Limited budget for refactoring
- Willing to accept technical debt

**When to Choose Clean Architecture Instead:**
- Large team (4+ developers)
- Long-term product (5+ year horizon)
- High complexity requirements (multi-tenancy, microservices)
- Budget allows 2+ month refactor

### Implementation Plan

**Immediate Next Steps (Week 1):**

1. **Monday:**
   - Stakeholder review of this document
   - Approve Pragmatic Migration approach
   - Assign team roles (Backend, Frontend, Integration, Testing)

2. **Tuesday:**
   - Install dependencies: `pip install Flask-Login alembic bcrypt twilio flask-apscheduler`
   - Initialize Alembic: `alembic init alembic`
   - Create development branch: `git checkout -b feature/multi-module-foundation`

3. **Wednesday-Thursday:**
   - Create migration 001 (users table)
   - Implement auth routes (login/logout)
   - Build login.html template
   - Update base.html with role-based navigation

4. **Friday:**
   - Test authentication end-to-end
   - Protect existing invoice routes with @login_required
   - Demo to stakeholders
   - Plan Phase 2 (Client module) for next week

**Critical Success Factors:**

- ✅ **Clear Ownership:** Each phase has a designated owner
- ✅ **Weekly Demos:** Show progress, get feedback early
- ✅ **Parallel Streams:** Backend and Frontend work simultaneously
- ✅ **Test in Production:** Use real data from Week 3 onward
- ✅ **Ruthless Prioritization:** Ship working features, defer polish

**Expected Outcome:**

By following the Pragmatic Migration Strategy, you will have:
- ✅ Working authentication in 2 weeks
- ✅ First new module (Clients) in 4 weeks
- ✅ Core business value (Appointments with Calendar) in 10 weeks
- ✅ Full-featured, production-ready system in 16 weeks

---

## Appendix: Resources

### Documentation
- **Flask-Login:** https://flask-login.readthedocs.io/
- **Alembic:** https://alembic.sqlalchemy.org/
- **FullCalendar.js:** https://fullcalendar.io/
- **Twilio API:** https://www.twilio.com/docs/sms
- **Chart.js:** https://www.chartjs.org/

### Best Practices
- **Flask Project Structure:** https://flask.palletsprojects.com/en/latest/patterns/packages/
- **Repository Pattern:** https://martinfowler.com/eaaCatalog/repository.html
- **Strangler Fig Migration:** https://martinfowler.com/bliki/StranglerFigApplication.html

### Polish Resources
- **NIP Validation:** https://pl.wikipedia.org/wiki/NIP#Sprawdzanie_poprawności_numeru
- **RODO/GDPR Compliance:** https://uodo.gov.pl/

---

**Document Version:** 1.0
**Last Updated:** 2026-02-05
**Status:** Ready for Implementation

**Next Action:** Review with stakeholders → Approve approach → Begin Phase 1
