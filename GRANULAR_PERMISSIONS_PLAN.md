# Granular Permissions Implementation Plan
**Status: AWAITING APPROVAL — do not implement until approved**
**Created: 2026-05-13**
**Preceding work: migration p0q1r2s3t4u5 added `read_only` + `own_data` cols to `role_permissions`**

---

## Problem Statement

The current permission system has **9 broad module-level toggles** (`invoices`, `appointments`,
`clients`, `employees`, `services`, `settings`, `reports`, `data_correction`, `absences`).
Each toggle unlocks everything inside that module with no distinction between view-only access,
create access, destructive actions, or sensitive data visibility.

**Goal:** Replace with ~45 narrow, specific permission keys so admins can compose precise role
profiles (e.g. "can view appointments and clients but cannot create or delete anything").

---

## 1. Permission Manifest (Full List)

Format: `group.action` — stored as-is in `role_permissions.module_name` column (no schema
change to column structure needed, just extend valid values).

### Group: `invoices` — Faktury / Koszty
| Permission Key            | Polish Label                     | Notes |
|---------------------------|----------------------------------|-------|
| `invoices.view`           | Podgląd listy faktur             | View list + details |
| `invoices.upload`         | Wgrywanie / skanowanie PDF       | OCR upload pipeline |
| `invoices.create`         | Ręczne dodawanie faktur          | Manual entry form |
| `invoices.edit`           | Edycja danych faktury            | Edit fields on existing |
| `invoices.delete`         | Usuwanie faktur                  | Soft-delete |
| `invoices.export`         | Eksport (CSV / PDF)              | Download exports |
| `invoices.manage_sellers` | Zarządzanie sprzedawcami         | Seller CRUD + PDF passwords |
| `invoices.view_history`   | Historia zmian faktur            | Audit log for invoices |

### Group: `clients` — Klienci
| Permission Key              | Polish Label                      | Notes |
|-----------------------------|-----------------------------------|-------|
| `clients.view`              | Podgląd listy klientów            | List view |
| `clients.view_details`      | Szczegóły profilu klienta         | Full profile + notes |
| `clients.create`            | Dodawanie klientów                | Create form |
| `clients.edit`              | Edycja danych klienta             | Edit form |
| `clients.delete`            | Usuwanie klientów                 | Soft-delete |
| `clients.manage_preferences`| Preferencje klientów (stylista)   | Client-stylist service prefs |

### Group: `services` — Usługi
| Permission Key             | Polish Label                     | Notes |
|----------------------------|----------------------------------|-------|
| `services.view`            | Podgląd katalogu usług           | List + details |
| `services.create`          | Dodawanie usług / kategorii      | Create form |
| `services.edit`            | Edycja usług                     | Edit form |
| `services.delete`          | Usuwanie usług                   | Soft-delete |
| `services.manage_addons`   | Mikrousługi i dodatki            | Addon CRUD + assignments |

### Group: `employees` — Pracownicy
| Permission Key               | Polish Label                     | Notes |
|------------------------------|----------------------------------|-------|
| `employees.view`             | Podgląd listy pracowników        | Basic list |
| `employees.view_details`     | Profil pracownika (szczegóły)    | Skills, schedule, position |
| `employees.view_salary`      | Dane finansowe pracownika        | Salary, commission, cost rate — SENSITIVE |
| `employees.create`           | Dodawanie pracowników            | Create form |
| `employees.edit`             | Edycja profilu pracownika        | Non-financial fields |
| `employees.edit_salary`      | Edycja danych finansowych        | Salary/commission/cost rate — SENSITIVE |
| `employees.delete`           | Dezaktywacja / usuwanie          | Soft-delete / status change |
| `employees.manage_services`  | Przypisywanie usług do prac.     | Employee-service assignments + rates |
| `employees.manage_supervisors`| Zarządzanie hierarchią przeł.   | Supervisor relationship CRUD |

### Group: `appointments` — Wizyty
| Permission Key              | Polish Label                     | Notes |
|-----------------------------|----------------------------------|-------|
| `appointments.view`         | Podgląd wizyt                    | List + calendar |
| `appointments.create`       | Tworzenie wizyt                  | Booking form |
| `appointments.edit`         | Edycja szczegółów wizyty         | Modify existing |
| `appointments.cancel`       | Anulowanie wizyt                 | Cancel flow |
| `appointments.complete`     | Zamykanie / rozliczenie wizyty   | Mark completed + income record |
| `appointments.status_change`| Zmiana statusu wizyty            | In-progress, no-show, etc. |
| `appointments.force_edit`   | Edycja zakończonych / anulowanych| Data correction on closed appts |
| `appointments.view_income`  | Podgląd przychodów z wizyt       | Income records |

### Group: `analytics` — Raporty / Analityka  *(NEW — currently under `appointments`)*
| Permission Key              | Polish Label                     | Notes |
|-----------------------------|----------------------------------|-------|
| `analytics.view_dashboard`  | Pulpit analityczny               | Main analytics dashboard |
| `analytics.view_employee`   | Statystyki pracowników           | Per-employee performance |
| `analytics.view_revenue`    | Raporty przychodów               | Revenue / income analysis |
| `analytics.export`          | Eksport raportów                 | Download analytics data |

### Group: `absences` — Nieobecności
| Permission Key              | Polish Label                     | Notes |
|-----------------------------|----------------------------------|-------|
| `absences.view_own`         | Własne nieobecności              | "Moje nieobecności" page — ALL employees |
| `absences.submit_request`   | Składanie wniosków               | Submit absence request |
| `absences.view_team`        | Nieobecności zespołu             | See other employees' absences |
| `absences.approve_reject`   | Zatwierdzanie / odrzucanie       | Approve / reject requests |
| `absences.create_manual`    | Manualna rejestracja (L4 itp.)   | Auto-approved, for subordinates only |
| `absences.edit_delete`      | Edycja / usuwanie nieobecności   | Edit manual, soft-delete |
| `absences.manage_categories`| Kategorie nieobecności           | Admin CRUD for categories |
| `absences.manage_balances`  | Limity i korekty bilansu         | Set limits + adjustments |

### Group: `system` — System / Konta  *(NEW — replaces hardcoded `@role_required`)*
| Permission Key              | Polish Label                     | Notes |
|-----------------------------|----------------------------------|-------|
| `system.view_users`         | Podgląd użytkowników             | User list |
| `system.create_users`       | Tworzenie kont                   | Create user + link employee |
| `system.edit_users`         | Edycja kont użytkowników         | Change role, password reset |
| `system.delete_users`       | Dezaktywacja kont                | Soft-delete / deactivate |
| `system.manage_roles`       | Zarządzanie rolami i uprawnieniami| Role CRUD + permission editor |

### Group: `data_correction` — Korekta Danych
| Permission Key                  | Polish Label                  | Notes |
|---------------------------------|-------------------------------|-------|
| `data_correction.invoices`      | Korekta faktur                | Merge, re-classify invoices |
| `data_correction.clients`       | Korekta klientów              | Fix client data |
| `data_correction.appointments`  | Korekta wizyt                 | Force-edit closed appointments |
| `data_correction.services`      | Korekta usług                 | Catalog corrections |

**Total: 47 permission keys across 9 groups.**

---

## 2. Default Role Seedings

Define what each system role gets out of the box (migration seed data):

| Group.Permission               | superuser | admin | receptionist | stylist | accountant |
|--------------------------------|:---------:|:-----:|:------------:|:-------:|:----------:|
| `invoices.view`                | ✓ | ✓ | — | — | ✓ |
| `invoices.upload`              | ✓ | ✓ | — | — | ✓ |
| `invoices.create`              | ✓ | ✓ | — | — | ✓ |
| `invoices.edit`                | ✓ | ✓ | — | — | ✓ |
| `invoices.delete`              | ✓ | — | — | — | — |
| `invoices.export`              | ✓ | ✓ | — | — | ✓ |
| `invoices.manage_sellers`      | ✓ | ✓ | — | — | ✓ |
| `invoices.view_history`        | ✓ | ✓ | — | — | ✓ |
| `clients.view`                 | ✓ | ✓ | ✓ | ✓ | — |
| `clients.view_details`         | ✓ | ✓ | ✓ | ✓ | — |
| `clients.create`               | ✓ | ✓ | ✓ | — | — |
| `clients.edit`                 | ✓ | ✓ | ✓ | — | — |
| `clients.delete`               | ✓ | ✓ | — | — | — |
| `clients.manage_preferences`   | ✓ | ✓ | ✓ | ✓ | — |
| `services.view`                | ✓ | ✓ | ✓ | ✓ | — |
| `services.create`              | ✓ | ✓ | — | — | — |
| `services.edit`                | ✓ | ✓ | — | — | — |
| `services.delete`              | ✓ | — | — | — | — |
| `services.manage_addons`       | ✓ | ✓ | — | — | — |
| `employees.view`               | ✓ | ✓ | ✓ | — | — |
| `employees.view_details`       | ✓ | ✓ | ✓ | — | — |
| `employees.view_salary`        | ✓ | ✓ | — | — | — |
| `employees.create`             | ✓ | ✓ | — | — | — |
| `employees.edit`               | ✓ | ✓ | — | — | — |
| `employees.edit_salary`        | ✓ | — | — | — | — |
| `employees.delete`             | ✓ | — | — | — | — |
| `employees.manage_services`    | ✓ | ✓ | — | — | — |
| `employees.manage_supervisors` | ✓ | ✓ | — | — | — |
| `appointments.view`            | ✓ | ✓ | ✓ | ✓ | — |
| `appointments.create`          | ✓ | ✓ | ✓ | — | — |
| `appointments.edit`            | ✓ | ✓ | ✓ | — | — |
| `appointments.cancel`          | ✓ | ✓ | ✓ | — | — |
| `appointments.complete`        | ✓ | ✓ | ✓ | ✓ | — |
| `appointments.status_change`   | ✓ | ✓ | ✓ | ✓ | — |
| `appointments.force_edit`      | ✓ | — | — | — | — |
| `appointments.view_income`     | ✓ | ✓ | — | — | ✓ |
| `analytics.view_dashboard`     | ✓ | ✓ | — | — | ✓ |
| `analytics.view_employee`      | ✓ | ✓ | — | — | — |
| `analytics.view_revenue`       | ✓ | ✓ | — | — | ✓ |
| `analytics.export`             | ✓ | ✓ | — | — | ✓ |
| `absences.view_own`            | ✓ | ✓ | ✓ | ✓ | ✓ |
| `absences.submit_request`      | ✓ | ✓ | ✓ | ✓ | ✓ |
| `absences.view_team`           | ✓ | ✓ | — | — | — |
| `absences.approve_reject`      | ✓ | ✓ | — | — | — |
| `absences.create_manual`       | ✓ | ✓ | — | — | — |
| `absences.edit_delete`         | ✓ | ✓ | — | — | — |
| `absences.manage_categories`   | ✓ | ✓ | — | — | — |
| `absences.manage_balances`     | ✓ | ✓ | — | — | — |
| `system.view_users`            | ✓ | ✓ | — | — | — |
| `system.create_users`          | ✓ | ✓ | — | — | — |
| `system.edit_users`            | ✓ | ✓ | — | — | — |
| `system.delete_users`          | ✓ | — | — | — | — |
| `system.manage_roles`          | ✓ | — | — | — | — |
| `data_correction.invoices`     | ✓ | — | — | — | — |
| `data_correction.clients`      | ✓ | — | — | — | — |
| `data_correction.appointments` | ✓ | — | — | — | — |
| `data_correction.services`     | ✓ | — | — | — | — |

> **Supervisor-via-employee-supervisors table** gets: `absences.view_team`, `absences.approve_reject`,
> `absences.create_manual` (for subordinates only, not self), `absences.edit_delete` — this is
> granted dynamically via `absence_management_required` decorator, NOT via the role_permissions table.
> The `own_data` flag on `absences.view_team` means "only see your direct reports".

---

## 3. DB Changes

### Migration: `q1r2s3t4u5v6_granular_permissions_manifest.py`

```python
# No structural changes to role_permissions table —
# module_name column continues to store the permission key.
# read_only + own_data already exist from migration p0q1r2s3t4u5.

# Steps:
# 1. Insert new granular permission rows for all existing roles (see seed table above)
# 2. Migrate old broad rows: map old module_name → new keys
#    e.g. old 'invoices' row → becomes individual 'invoices.view', 'invoices.upload', etc.
#    preserving the old has_access value for each new key
# 3. Delete old broad rows (invoices, clients, etc.) — they are replaced
# 4. seed `absences.view_own` + `absences.submit_request` TRUE for ALL roles
```

### Migration logic (old → new mapping):
```
'invoices'        → invoices.view, .upload, .create, .edit  (if had_access=T)
                  → invoices.delete, .export, .manage_sellers, .view_history  (superuser/admin only)
'clients'         → clients.view, .view_details, .create, .edit  (if had_access=T)
'services'        → services.view, .create, .edit  (if had_access=T)
'employees'       → employees.view, .view_details, .create, .edit, .manage_services  (if had_access=T)
'appointments'    → appointments.view, .create, .edit, .cancel, .complete, .status_change  (if had_access=T)
                    analytics.view_dashboard, .view_revenue  (if had_access=T)
'absences'        → absences.view_team, .approve_reject, .create_manual, .edit_delete,
                    .manage_categories, .manage_balances  (if had_access=T)
                    absences.view_own + .submit_request  → TRUE for ALL roles
'reports'         → analytics.view_dashboard, .view_revenue, .export  (if had_access=T)
'data_correction' → data_correction.invoices, .clients, .appointments, .services  (if had_access=T)
'settings'        → system.view_users, .create_users, .edit_users (if had_access=T)
                    system.manage_roles  → superuser only
```

---

## 4. Code Changes

### Phase A — `repositories/roles/role_repository.py`

1. Replace `ALL_MODULES` list with `ALL_PERMISSIONS` dict:
```python
ALL_PERMISSIONS = {
    'invoices.view':            {'group': 'invoices',  'label': 'Podgląd listy faktur'},
    'invoices.upload':          {'group': 'invoices',  'label': 'Wgrywanie / skanowanie PDF'},
    # ... all 47 entries
}

PERMISSION_GROUPS = {
    'invoices':        'Faktury / Koszty',
    'clients':         'Klienci',
    'services':        'Usługi',
    'employees':       'Pracownicy',
    'appointments':    'Wizyty',
    'analytics':       'Raporty / Analityka',
    'absences':        'Nieobecności',
    'system':          'System / Konta',
    'data_correction': 'Korekta Danych',
}
```

2. Update `get_permissions(role_id)` — returns grouped dict:
```python
{
  'invoices': {
    'view':   {'has_access': True,  'read_only': False, 'own_data': False},
    'upload': {'has_access': True,  'read_only': False, 'own_data': False},
    'delete': {'has_access': False, 'read_only': False, 'own_data': False},
    ...
  },
  'absences': { ... },
  ...
}
```

3. Update `set_permissions(role_id, permissions)` — accepts flat or grouped dict:
```python
# flat:    {'invoices.view': {'has_access': True, 'read_only': False, 'own_data': False}}
# grouped: {'invoices': {'view': {'has_access': True, ...}}}
```

4. Replace `role_has_module_access(role_name, module_name)` with:
```python
def role_has_permission(role_name, permission_key) -> bool:
    # exact match: 'invoices.view'

def group_has_any_access(role_name, group_name) -> bool:
    # True if ANY permission in the group is granted
    # Used for sidebar nav + backward-compat @module_permission_required('invoices')
```

5. Keep `get_user_module_permissions(role_name)` returning `{group: bool}` for
   the context processor + sidebar nav (uses `group_has_any_access` internally).

---

### Phase B — `config/auth_config.py`

1. Add `@permission_required('invoices.upload')` decorator:
```python
def permission_required(*permission_keys):
    """Require ANY of the listed permission keys (OR logic)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Musisz być zalogowany', 'error')
                return redirect(url_for('auth.login'))
            from repositories.roles.role_repository import RoleRepository
            repo = RoleRepository()
            if not any(repo.role_has_permission(current_user.role, k) for k in permission_keys):
                flash('Brak uprawnień', 'error')
                return redirect(url_for('main.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

2. Keep `module_permission_required(group)` as a backward-compat wrapper around
   `group_has_any_access` — so existing decorators don't need to change in Phase B
   (they can be refined gradually in Phase C).

3. Update `absence_management_required` to check `absences.view_team` permission.

4. Update `MODULE_PERMISSIONS` static fallback to cover new keys (for when DB is not reachable).

---

### Phase C — Route Wiring (per-route permission precision)

Replace broad `@module_permission_required('invoices')` with specific keys on each route.
Examples:

```python
# main_routes.py
@module_permission_required('invoices')      → @permission_required('invoices.view')
@module_permission_required('invoices')      → @permission_required('invoices.upload')     # /upload
@module_permission_required('invoices')      → @permission_required('invoices.create')     # /invoice/create
@module_permission_required('invoices')      → @permission_required('invoices.edit')       # /invoice/<id>/edit

# absence_routes.py
@module_permission_required('absences')      → @permission_required('absences.manage_categories')
@absence_management_required                 → @permission_required('absences.view_team')  # management_index
(approve route)                              → @permission_required('absences.approve_reject')
(manual route)                              → @permission_required('absences.create_manual')
(delete route)                              → @permission_required('absences.edit_delete')

# users/routes.py (currently @role_required)
@role_required('superuser', 'admin')         → @permission_required('system.view_users')   # list
@role_required('superuser', 'admin')         → @permission_required('system.create_users') # create
# etc.

# roles/routes.py
@role_required('superuser')                  → @permission_required('system.manage_roles')
```

**This phase has the most files to touch (~15 route files, ~200 decorator occurrences).**
Do it module-by-module. Each sub-phase: update routes → test → commit.

---

### Phase D — UI: Roles Edit Page

Replace the current flat list of 9 module toggles with grouped, collapsible sections:

```
┌─ FAKTURY / KOSZTY ─────────────────────────────── [expand/collapse] ┐
│  Podgląd listy faktur         [● access] [○ read-only] [○ own-data] │
│  Wgrywanie / skanowanie PDF   [● access] [○ read-only] [○ own-data] │
│  Ręczne dodawanie faktur      [○ access] [·disabled··] [·disabled··] │
│  Edycja danych faktury        [○ access] ...                         │
│  Usuwanie faktur              [○ access] ...                         │
│  Eksport (CSV / PDF)          [○ access] ...                         │
│  Zarządzanie sprzedawcami     [○ access] ...                         │
│  Historia zmian faktur        [○ access] ...                         │
└──────────────────────────────────────────────────────────────────────┘
┌─ KLIENCI ──────────────── ...
```

Features:
- Group header has a "select all in group" master toggle
- Each permission row: access toggle (large) + read-only + own-data (small, dimmed when access=OFF)
- JS payload: flat dict `{'invoices.view': {has_access, read_only, own_data}, ...}`
- Ctrl+S saves, Esc cancels (existing shortcuts kept)

---

### Phase E — `templates/` Guard Updates

Anywhere templates check `user_permissions['invoices']` for showing nav links or action buttons,
update to check the appropriate sub-permission or the group-level bool:

```jinja2
{# OLD: #}
{% if user_permissions.invoices %}

{# NEW: still works because get_user_module_permissions returns group-level bool #}
{% if user_permissions.invoices %}  {# no change needed for sidebar nav #}

{# But for action buttons inside views: #}
{% if user_permission_flags('invoices.delete') %}  {# add template helper #}
    <button>Usuń</button>
{% endif %}
```

Add a Jinja2 global helper `user_can(permission_key)` injected via context processor that
calls `role_has_permission(current_user.role, key)`.

---

## 5. Implementation Order (Phases)

| Phase | What | Risk | Est. effort |
|-------|------|------|-------------|
| **P0** | Write `ALL_PERMISSIONS` manifest in role_repository.py (no DB yet) | Low | 30 min |
| **P1** | DB migration: insert new rows, migrate old rows, delete broad rows | Medium | 45 min |
| **P2** | `RoleRepository` updated methods + `permission_required` decorator | Low | 45 min |
| **P3** | `module_permission_required` backward-compat shim verified working | Low | 20 min |
| **P4** | Roles edit UI redesign (grouped sections + 3 toggles per row) | Low | 60 min |
| **P5** | Route wiring — absence routes (highest priority, fixes the bug area) | Medium | 45 min |
| **P6** | Route wiring — system/users/roles routes | Low | 20 min |
| **P7** | Route wiring — invoices, clients, services, employees, appointments | Medium | 90 min |
| **P8** | Template `user_can()` helper + action button guards in key templates | Medium | 60 min |
| **P9** | Seed default roles re-verified, deploy, smoke test all role scenarios | Low | 30 min |

**Total estimate: ~7–8 hours of implementation across phases.**

---

## 6. Key Design Decisions

1. **Dotted key in existing `module_name` column** — no ALTER TABLE needed for the key column.
   The 47 rows per role (vs 9 previously) is fine for PostgreSQL.

2. **`absences.view_own` + `absences.submit_request` are given to ALL roles** by default —
   every employee needs to file absences. These are the only permissions granted to all roles.

3. **`analytics` is a new group** split off from `appointments`. Routes in `analytics_routes.py`
   currently use `@module_permission_required('appointments')` — this is confusing and will be
   corrected to `analytics.*` permissions.

4. **`system.*` replaces hardcoded `@role_required('superuser', 'admin')`** — user management
   becomes DB-configurable instead of hardcoded, enabling e.g. a "HR Manager" custom role with
   `system.view_users` + `system.create_users` but not `system.manage_roles`.

5. **Supervisor dynamic access** for absences stays via the `absence_management_required`
   decorator logic — it checks both `absences.view_team` permission AND the employee_supervisors
   table. This means a supervisor who loses their DB permission would also lose the dynamic access.

6. **`read_only` flag semantics**: On a write permission like `absences.create_manual`, `read_only=TRUE`
   means the user can see the form but cannot submit it (useful for training/shadowing scenarios).
   On view permissions it is a no-op. The flag is stored but enforcement is per-route/per-template.

7. **`own_data` flag semantics**: Applied at the query/filter level per module:
   - `employees.view` + `own_data` → only sees own employee record
   - `appointments.view` + `own_data` → only sees own appointments
   - `absences.view_team` + `own_data` → only sees direct reports (already enforced by supervisor logic)

---

## 7. Files to Modify

```
repositories/roles/role_repository.py     — ALL_PERMISSIONS, ALL methods
config/auth_config.py                     — permission_required(), absence_management_required()
routes/main_routes.py                     — ~20 decorator updates
routes/api_routes.py                      — ~50 decorator updates (biggest file)
routes/absence_routes.py                  — ~10 decorator updates
routes/absence_balance_routes.py          — ~12 decorator updates
routes/appointment_routes.py              — ~15 decorator updates
routes/analytics_routes.py               — ~20 decorator updates (invoices→analytics group)
routes/users/routes.py                    — ~8 decorator updates
routes/roles/routes.py                    — ~7 decorator updates
routes/income_routes.py                   — ~3 decorator updates
routes/employee_service_routes.py         — ~7 decorator updates
routes/service_addon_routes.py            — ~6 decorator updates
routes/client_preference_routes.py        — ~5 decorator updates
templates/roles/edit.html                 — full redesign (grouped sections)
alembic/versions/q1r2s3t4u5v6_*.py       — new migration
```

---

## 8. Rollback Plan

If anything goes wrong during migration:
- `alembic downgrade -1` removes the new rows but also drops the old broad rows.
- Keep `MODULE_PERMISSIONS` static dict in `auth_config.py` as final fallback for all decorators.
- The `module_permission_required` backward-compat shim ensures the app still functions
  even if the DB has no rows for a given permission key.

---

*Plan ready for review. Do not implement until approved.*
