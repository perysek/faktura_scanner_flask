# Phase 4: Appointments Core + Business Logic Refactoring

## Problem Analysis

### Current State Gaps

The current data model has several design limitations that need to be addressed before building appointments:

1. **Service pricing is flat** — `services.price` stores a single price, but the business requires per-employee pricing (senior stylist vs junior charges differently for the same service)
2. **Commission is global** — `employees.commission_rate` is one percentage for all services, but commission should vary per service (e.g., 50% on coloring, 30% on cuts)
3. **No employee-service capability mapping** — which employees can perform which services is stored only as free-text JSON `skills`, not as a queryable relationship
4. **Client preferences are unstructured** — `clients.preferences` is a JSON blob with no schema for "preferred employee per service"

All of these must be resolved before appointments can work correctly.

---

## Data Model Design

### New Tables

#### 1. `employee_services` (Employee-Service Pricing & Capabilities)

**Purpose**: Links employees to services they can perform, with per-employee pricing and commission rates.

```
employee_services
├── id                  INTEGER PK
├── employee_id         INTEGER FK → employees.id
├── service_id          INTEGER FK → services.id
├── custom_price        NUMERIC(10,2) NULL   — NULL = use services.price (base price)
├── commission_rate     NUMERIC(5,2)  NULL   — NULL = use employees.commission_rate (default)
├── duration_override   INTEGER       NULL   — NULL = use services.duration_minutes
├── is_active           BOOLEAN DEFAULT 1
├── created_at          TIMESTAMP
├── updated_at          TIMESTAMP
└── UNIQUE(employee_id, service_id)
```

**Business Logic**:
- `services.price` = **base price** (catalog/list price shown to new clients)
- `employee_services.custom_price` = **employee-specific price** (overrides base when set)
- **Effective price** = `COALESCE(employee_services.custom_price, services.price)`
- **Effective commission** = `COALESCE(employee_services.commission_rate, employees.commission_rate, 0)`
- **Effective duration** = `COALESCE(employee_services.duration_override, services.duration_minutes)`

**Example data**:
| employee   | service     | base_price | custom_price | effective | commission |
|-----------|-------------|------------|--------------|-----------|------------|
| Anna (Sr) | Strzyżenie  | 80 zł      | 120 zł       | 120 zł    | 45%        |
| Kasia (Jr)| Strzyżenie  | 80 zł      | NULL         | 80 zł     | 30%        |
| Anna (Sr) | Koloryzacja | 250 zł     | 350 zł       | 350 zł    | 50%        |

#### 2. `client_preferences` (Client Preferred Employee per Service)

**Purpose**: Stores which employee a client prefers for each service category or specific service.

```
client_preferences
├── id                      INTEGER PK
├── client_id               INTEGER FK → clients.id
├── service_id              INTEGER FK → services.id  NULL  — NULL = category-level pref
├── service_category        TEXT NULL                       — e.g., 'Koloryzacja'
├── preferred_employee_id   INTEGER FK → employees.id
├── notes                   TEXT NULL   — e.g., "Woli ciche środowisko"
├── created_at              TIMESTAMP
├── updated_at              TIMESTAMP
└── UNIQUE(client_id, service_id, service_category)
```

**Business Logic**:
- A preference can be **service-specific** (service_id set) OR **category-level** (service_category set)
- When booking, lookup order: service-specific → category-level → no preference
- This allows: "Client prefers Anna for all Koloryzacja, but Marta specifically for Balayage"

#### 3. `appointments` (Core Appointment)

```
appointments
├── id                  INTEGER PK
├── client_id           INTEGER FK → clients.id
├── employee_id         INTEGER FK → employees.id
├── status              TEXT CHECK('scheduled','confirmed','in_progress','completed','cancelled','no_show')
├── appointment_date    DATE NOT NULL
├── start_time          TIME NOT NULL
├── end_time            TIME NOT NULL        — calculated from total duration of services
├── total_price         NUMERIC(10,2)        — sum of effective prices at time of booking
├── total_duration      INTEGER              — sum of effective durations (minutes)
├── discount_amount     NUMERIC(10,2) DEFAULT 0
├── notes               TEXT NULL
├── cancellation_reason TEXT NULL
├── cancelled_at        TIMESTAMP NULL
├── created_by          INTEGER FK → users.id NULL   — which staff member created it
├── created_at          TIMESTAMP
├── updated_at          TIMESTAMP
```

**Indexes**: `(appointment_date, employee_id)`, `(client_id)`, `(status)`

#### 4. `appointment_services` (Services within an Appointment)

```
appointment_services
├── id                  INTEGER PK
├── appointment_id      INTEGER FK → appointments.id ON DELETE CASCADE
├── service_id          INTEGER FK → services.id
├── price_charged       NUMERIC(10,2) NOT NULL   — snapshot of effective price at booking time
├── duration_minutes    INTEGER NOT NULL          — snapshot of effective duration
├── commission_rate     NUMERIC(5,2) NOT NULL     — snapshot of commission at booking time
├── commission_amount   NUMERIC(10,2) NOT NULL    — pre-calculated: price_charged * commission_rate / 100
```

**Why snapshot pricing?** Prices and commission rates change over time. When an appointment was booked at 120 zl, that's what the client pays even if the price later changes to 150 zl. Same for commission — the employee earns based on the rate at booking time.

#### 5. `income_records` (Revenue from Completed Appointments)

```
income_records
├── id                  INTEGER PK
├── appointment_id      INTEGER FK → appointments.id UNIQUE
├── client_id           INTEGER FK → clients.id
├── employee_id         INTEGER FK → employees.id
├── total_amount        NUMERIC(10,2) NOT NULL    — what client paid
├── discount_amount     NUMERIC(10,2) DEFAULT 0
├── net_amount          NUMERIC(10,2) NOT NULL    — total - discount
├── commission_total    NUMERIC(10,2) NOT NULL    — sum of all service commissions
├── payment_method      TEXT NULL                  — 'cash', 'card', 'transfer'
├── payment_date        DATE NOT NULL
├── notes               TEXT NULL
├── created_at          TIMESTAMP
```

**Generated automatically** when appointment status changes to `completed`.

---

## Business Logic Rules

### Pricing Resolution Chain
```
1. Check employee_services for (employee_id, service_id)
2. If custom_price is set → use it
3. If custom_price is NULL → fall back to services.price
4. Apply same logic for duration and commission
```

### Commission Calculation
```
For each service in appointment:
  commission_rate = COALESCE(
    employee_services.commission_rate,   -- per-service override
    employees.commission_rate,            -- employee default
    0                                     -- fallback
  )
  commission_amount = price_charged * commission_rate / 100

Total commission = SUM(all service commission_amounts)
Employee earns = base_salary + total_commission (monthly)
```

### Appointment Status Workflow
```
scheduled → confirmed → in_progress → completed
    ↓           ↓            ↓
cancelled    cancelled    cancelled (rare)

scheduled → no_show (client didn't arrive)
```

**Status transition effects**:
- `→ completed`: Creates income_record, updates client.last_visit_date
- `→ cancelled`: Sets cancellation_reason, cancelled_at
- `→ no_show`: Logged for client history (no income generated)

### Booking Conflict Detection
```
An employee cannot have overlapping appointments:
  WHERE employee_id = ?
  AND appointment_date = ?
  AND start_time < proposed_end_time
  AND end_time > proposed_start_time
  AND status NOT IN ('cancelled', 'no_show')
```

### Client Preference Lookup (for booking form)
```python
def get_suggested_employee(client_id, service_id, service_category):
    # 1. Service-specific preference
    pref = client_preferences WHERE client_id AND service_id
    if pref: return pref.preferred_employee_id

    # 2. Category-level preference
    pref = client_preferences WHERE client_id AND service_category
    if pref: return pref.preferred_employee_id

    # 3. No preference — show all available employees
    return None
```

---

## Implementation Steps

### Step 1: Alembic Migration — `employee_services` table
- Create `employee_services` junction table
- Add indexes on (employee_id, service_id)
- **Note**: `employees.commission_rate` stays as the default — NOT removed

### Step 2: Alembic Migration — `client_preferences` table
- Create `client_preferences` table
- Add indexes on (client_id), (preferred_employee_id)

### Step 3: Alembic Migration — `appointments` + `appointment_services` + `income_records`
- Create all three tables
- Add all necessary indexes and foreign keys

### Step 4: Data Models (database/models.py)
- Add `EmployeeService` dataclass
- Add `ClientPreference` dataclass
- Add `Appointment` dataclass
- Add `AppointmentService` dataclass
- Add `IncomeRecord` dataclass

### Step 5: Repositories
- `repositories/employees/employee_service_repository.py` — CRUD for employee-service pricing
  - `get_services_for_employee(employee_id)` — list all services an employee can do with pricing
  - `get_employees_for_service(service_id)` — list all employees who can do a service
  - `get_effective_price(employee_id, service_id)` — resolve pricing chain
  - `bulk_assign_services(employee_id, service_ids)` — assign multiple services at once
- `repositories/clients/client_preference_repository.py` — CRUD for client preferences
  - `get_preferences_for_client(client_id)` — all preferences
  - `get_suggested_employee(client_id, service_id, category)` — preference resolution
- `repositories/appointments/appointment_repository.py` — CRUD for appointments
  - `get_by_date_range(start, end, employee_id=None)` — calendar data
  - `check_conflicts(employee_id, date, start_time, end_time)` — overlap detection
  - `get_daily_schedule(employee_id, date)` — employee's day view
- `repositories/appointments/income_repository.py` — CRUD for income records
  - `get_by_date_range(start, end)` — income reports
  - `get_by_employee(employee_id, month)` — employee earnings
  - `get_monthly_summary()` — revenue dashboard

### Step 6: Service Layer
- `services/appointment_service.py` — Business logic orchestrator
  - `create_appointment(client_id, employee_id, service_ids, date, time)` — validates, resolves pricing, checks conflicts
  - `complete_appointment(appointment_id, payment_method)` — transitions status, creates income record
  - `cancel_appointment(appointment_id, reason)` — cancellation logic
  - `get_available_slots(employee_id, date)` — compute free time slots from schedule + existing appointments
- `services/pricing_service.py` — Pricing resolution
  - `resolve_price(employee_id, service_id)` → effective price
  - `resolve_commission(employee_id, service_id)` → effective commission rate
  - `calculate_appointment_total(employee_id, service_ids)` → total price + breakdown

### Step 7: API Routes
- `routes/appointment_routes.py` (new blueprint `/api/appointments`)
  - `GET /api/appointments?date_from=&date_to=&employee_id=` — list/calendar
  - `POST /api/appointments` — create appointment
  - `GET /api/appointments/<id>` — details
  - `PUT /api/appointments/<id>` — update
  - `PUT /api/appointments/<id>/status` — transition status
  - `DELETE /api/appointments/<id>` — cancel
  - `GET /api/appointments/available-slots?employee_id=&date=` — free slots
- `routes/employee_service_routes.py` (extends employees API)
  - `GET /api/employees/<id>/services` — services with pricing
  - `POST /api/employees/<id>/services` — assign services
  - `PUT /api/employees/<id>/services/<sid>` — update pricing
  - `DELETE /api/employees/<id>/services/<sid>` — remove capability
- `routes/client_preference_routes.py` (extends clients API)
  - `GET /api/clients/<id>/preferences` — all preferences
  - `POST /api/clients/<id>/preferences` — add preference
  - `DELETE /api/clients/<id>/preferences/<pid>` — remove preference
- `routes/income_routes.py` (new blueprint `/api/income`)
  - `GET /api/income?month=&employee_id=` — income list
  - `GET /api/income/summary` — dashboard stats

### Step 8: Page Routes + Templates
- `templates/employees/services.html` — manage employee service pricing (sub-page of employee view)
- `templates/clients/preferences.html` — manage client preferences (sub-page of client view)
- `templates/appointments/list.html` — appointment list view
- `templates/appointments/calendar.html` — calendar view (day/week/month)
- `templates/appointments/create.html` — booking form
- `templates/appointments/view.html` — appointment detail
- `templates/income/dashboard.html` — income overview

### Step 9: Sidebar Navigation Update
- Add "WIZYTY" (Appointments) section to sidebar
- Add "PRZYCHODY" (Income) section to sidebar
- Group navigation: Finanse (Faktury, Przychody) | Salon (Wizyty, Klienci, Usługi, Pracownicy) | System (Historia, Ustawienia)

### Step 10: Calendar JavaScript Component
- Day view: time slots with appointments as blocks
- Week view: 7 columns with appointment blocks
- Month view: day cells with appointment counts
- Drag to select time → opens booking form
- Uses Fetch API (no external libraries) per project conventions

---

## Build Sequence (Recommended Order)

```
Migration 1: employee_services table        ← foundation for pricing
Migration 2: client_preferences table       ← foundation for preferences
Migration 3: appointments + appointment_services + income_records

Models:       all 5 dataclasses
Repos:        employee_service_repo → client_preference_repo → appointment_repo → income_repo
Services:     pricing_service → appointment_service
API Routes:   employee-services → client-preferences → appointments → income
Templates:    employee services tab → client preferences tab → appointments CRUD → calendar → income

Total estimate: ~15-20 files new, ~8-10 files modified
```

---

## Questions Resolved from refactoring_answers.txt

| Requirement | How Addressed |
|------------|---------------|
| Dynamic pricing per employee | `employee_services.custom_price` overrides `services.price` |
| Commission as % of service price + base salary | `employee_services.commission_rate` (per-service) with fallback to `employees.commission_rate` (default) |
| Skills with level rating | Kept in `employees.skills` JSON for display; `employee_services` for queryable capability mapping |
| Appointment links ONE client, ONE employee, multiple services | `appointments` (client+employee) + `appointment_services` (multiple services) |
| Completed appointments generate income records | `income_records` created on status → `completed` |
| Client preferred employee per service | `client_preferences` with service-specific and category-level preferences |
| Hard delete with logs | Appointments use soft delete (cancel status); income records are permanent |
