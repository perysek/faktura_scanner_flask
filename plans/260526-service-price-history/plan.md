# Service Price History — Implementation Plan
**Date:** 2026-05-26  
**Feature:** Track service catalogue price changes over time with full audit trail and UI integration  
**Branch:** invoices-app

---

## ✅ Status: IMPLEMENTED & DEPLOYED — 2026-06-03

All 11 phases implemented inline (Phase 9 intentionally a no-op per its own spec), committed as `37c882a`, pushed to `origin/invoices-app`, and deployed to the Vultr production server. Migration `w8x9y0z1a2b3` applied live (alembic head confirmed); 49 initial price rows seeded; `service_prices` RBAC module registered. Verified on-server via an SSH test harness — **22/22 functional checks passed** against the live DB with all writes rolled back (zero residue). A 30 MB pre-deploy DB backup was taken first.

**Deviations from this plan (all deliberate improvements):**
1. **`idx_sph_open_entries` is a partial UNIQUE index**, not a plain index — the "one open price per service" invariant is now DB-enforced (verified: a second open row is rejected).
2. **`accountant` granted read-only `service_prices`** (per the RBAC *table* in this plan, which overrides the `[superuser, admin]`-only code snippet in Phase 4). Price *changes* remain gated by the `services` module, which accountants cannot access.
3. **`price` dropped from the redundant `_audit_changes()` UPDATE list** — so a price change now produces exactly one (richer) `PRICE_CHANGE` audit entry instead of a duplicate.

**Note:** No separate dev DB exists (local `.env.local` tunnels to production), so the migration first ran on prod; it applied cleanly inside PostgreSQL's transactional DDL.

---

## Problem Statement

The `services` table has a single `price: float` column. When a price is updated, the old value is overwritten. Currently:
- `appointment_services.price_charged` preserves the _charged_ price per appointment (historical revenue is safe)
- But the service catalogue itself has no audit trail — "when was this price 80 zł and when did it become 100 zł?" is unanswerable

The existing `audit_log` table already records `entity_type='service', action='UPDATE', field_name='price'` via `_audit_changes()` in `api_routes.py:3226` — so single-entry changes are logged. However, this is not query-friendly for analytics or point-in-time lookups.

---

## Chosen Approach

**Option (a): Dedicated `service_price_history` table** with `(service_id, price, effective_from, effective_to)`.

Additionally: emit a `PRICE_CHANGE` action to `audit_log` (new action type alongside existing `UPDATE`, `CREATE`, etc.) so that price changes surface distinctly in the History page.

---

## Schema Design

```sql
CREATE TABLE service_price_history (
    id              SERIAL PRIMARY KEY,
    service_id      INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    price           NUMERIC(10, 2) NOT NULL,
    currency        VARCHAR(3) NOT NULL DEFAULT 'PLN',
    effective_from  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to    TIMESTAMPTZ,          -- NULL = current active price
    changed_by      INTEGER REFERENCES users(id),
    change_reason   VARCHAR(255),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sph_service_id      ON service_price_history(service_id);
CREATE INDEX idx_sph_effective_range ON service_price_history(service_id, effective_from DESC);
CREATE INDEX idx_sph_open_entries    ON service_price_history(service_id) WHERE effective_to IS NULL;
```

**Invariant:** at most one row per service has `effective_to IS NULL` (the current price).

**On CREATE service:** insert initial row (`effective_from = now()`, `effective_to = NULL`).  
**On price UPDATE:**
1. `UPDATE service_price_history SET effective_to = NOW() WHERE service_id = %s AND effective_to IS NULL`
2. `INSERT INTO service_price_history (service_id, price, currency, effective_from, changed_by, change_reason) VALUES (...)`
3. Log to `audit_log` with `action='PRICE_CHANGE'`, `entity_type='service'`, `field_name='price'`

---

## RBAC — New Module: `service_prices`

Added to the role-based access system for fine-grained control over who can view or change service prices.

**Register in:**
- `config/auth_config.py` → `MODULE_PERMISSIONS` dict
- `repositories/roles/role_repository.py` → `ALL_MODULES` list and `MODULE_DISPLAY_NAMES` dict
- Protect price history API endpoints with `@module_permission_required('service_prices')`

**Suggested defaults (overridable via roles admin):**

| Role          | Has Access | Read-only | Notes                                |
|---------------|-----------|-----------|--------------------------------------|
| `superuser`   | ✅        | No        | Full: view history + change prices   |
| `admin`       | ✅        | No        | Full: view history + change prices   |
| `accountant`  | ✅        | Yes       | View history only, cannot change     |
| `receptionist`| No        | —         | No access                            |
| `stylist`     | No        | —         | No access                            |

**In `templates/roles/edit.html`:**  
The new module will appear automatically in the `{% for module in all_modules %}` loop once added to `ALL_MODULES`. No template changes needed — only backend registration.

Display name in `MODULE_DISPLAY_NAMES`: `'service_prices': 'Ceny usług (historia)'`

---

## Phases

### Phase 1 — Database Migration
**File:** `alembic/versions/w8x9y0z1a2b3_create_service_price_history.py`

- Create `service_price_history` table with columns, FK, and indexes
- Seed migration: populate initial entries for all existing services from their current `services.price` value, `effective_from = now()`, `changed_by = NULL`, `change_reason = 'Migracja danych — wartość początkowa'`
- Downgrade: `DROP TABLE service_price_history`

### Phase 2 — Repository: `ServicePriceHistoryRepository`
**File:** `repositories/services/service_price_history_repository.py`

Methods:
```python
def record_price_change(
    self, service_id: int, new_price: float, currency: str,
    changed_by: int | None, change_reason: str | None
) -> int:
    """Close the current open entry, insert new. Returns new row id."""

def get_history(self, service_id: int) -> list[dict]:
    """Return all rows ordered by effective_from DESC."""

def get_price_at(self, service_id: int, at_time: datetime) -> float | None:
    """Point-in-time price query. Returns the price effective at `at_time`."""

def get_last_change_dates(self, service_ids: list[int]) -> dict[int, datetime]:
    """Batch fetch: {service_id: most_recent_effective_from}. For list UI."""
```

### Phase 3 — Backend Integration in `api_routes.py`

**`PUT /api/services/<id>` — `update_service()`:**
- Before saving, compare `float(data.get('price'))` against `existing['price']`
- If price changed:
  - Call `service_price_history_repo.record_price_change(…)`
  - Call `_audit('service', 'PRICE_CHANGE', entity_id=service_id, entity_label=service.name, field_name='price', old_value=str(existing['price']), new_value=str(service.price))`
  - The existing `_audit_changes()` call continues to work for all other fields including price (redundant for price but harmless)
- Accept optional `change_reason` from request JSON body

**`POST /api/services` — `create_service_endpoint()`:**
- After `service_repo.create(service)`, call `service_price_history_repo.record_price_change(service_id, price, …, change_reason='Cena początkowa')`

**New API endpoint:**
```
GET /api/services/<int:service_id>/price-history
```
- Protected: `@login_required`, `@module_permission_required('service_prices')`
- Returns: `{ success: true, history: [ {id, price, currency, effective_from, effective_to, changed_by_name, change_reason}, … ] }`

**Update service list API** (`GET /api/services`):
- Join with `service_price_history` (LEFT JOIN, `WHERE effective_to IS NULL`) to return `last_price_change_date` per service — used for the list page trend indicator

### Phase 4 — RBAC Registration

**`config/auth_config.py`:**
```python
MODULE_PERMISSIONS = {
    ...existing...,
    'service_prices': ['superuser', 'admin'],
}
```

**`repositories/roles/role_repository.py`:**
```python
ALL_MODULES = [...existing..., 'service_prices']

MODULE_DISPLAY_NAMES = {
    ...existing...,
    'service_prices': 'Ceny usług (historia)',
}
```

No template changes needed — `roles/edit.html` iterates `all_modules` dynamically.

### Phase 5 — `templates/services/view.html`

**Location:** After the "Opis" card, before the "Akcje" card.

**UI: Collapsible `<details>` panel (like the SMS log in `appointments/view.html`)**

```html
<details id="price-history-panel" class="refined-card" style="padding: 0;">
    <summary style="padding: 1rem 1.5rem; cursor: pointer; …">
        Historia cen
        <span class="badge-count" id="price-history-count"></span>
    </summary>
    <div style="padding: 0 1.5rem 1rem;">
        <!-- Mini sparkline chart (Chart.js, height ~120px) -->
        <div style="height: 120px; margin-bottom: 1rem;">
            <canvas id="priceSparklineChart"></canvas>
        </div>
        <!-- Table -->
        <table class="refined-table">
            <thead>
                <tr>
                    <th>Data od</th>
                    <th>Data do</th>
                    <th>Cena</th>
                    <th>Powód</th>
                    <th>Zmienił</th>
                </tr>
            </thead>
            <tbody id="price-history-tbody">…</tbody>
        </table>
    </div>
</details>
```

**JS:** Load on `<details>` toggle (lazy). Draw sparkline with Chart.js (already loaded on analytics — include only if needed). Format `effective_to = NULL` as `"aktualnie"`.

**RBAC guard in template:** Wrap in `{% if user_permissions.get('service_prices') %}` (context processor provides this).

### Phase 6 — `templates/services/edit.html`

**Price change reason field — conditional slide-in:**

Below the "Cena" input, add a hidden field that reveals when the price is changed:

```html
<div id="price-change-reason-wrapper" style="display: none; margin-top: 0.75rem;">
    <label for="change_reason" class="refined-label">Powód zmiany ceny</label>
    <input type="text" id="change_reason" name="change_reason"
           class="refined-input" maxlength="255"
           placeholder="np. Podwyżka inflacyjna, nowy cennik 2026…">
    <p class="input-hint">Opcjonalnie — pojawi się w historii cen</p>
</div>
```

**JS:** In `DOMContentLoaded`, capture `originalPrice = parseFloat(document.getElementById('price').value)`. Add `input` event listener on `#price`:

```js
document.getElementById('price').addEventListener('input', function () {
    const changed = parseFloat(this.value) !== originalPrice;
    document.getElementById('price-change-reason-wrapper').style.display = changed ? 'block' : 'none';
});
```

**On form submit:** Include `change_reason: document.getElementById('change_reason').value.trim() || null` in the JSON payload.

**RBAC:** Only render the reason field if `{{ user_permissions.get('service_prices') }}` — otherwise submitting without `change_reason` is fine (backend ignores missing key).

### Phase 7 — `templates/services/list.html`

**Price trend indicator in table row:**

In the `tbody` render (JS), for each service that has `last_price_change_date` within the last 90 days, add a small directional chip next to the price:

```js
// In loadServices() response handling, the API now returns last_price_change_date
const recentChange = service.last_price_change_date
    && (Date.now() - new Date(service.last_price_change_date).getTime()) < 90 * 86400000;
const changeTip = recentChange
    ? `<span class="price-trend-chip" title="Zmieniono ${formatDaysSince(service.last_price_change_date)} dni temu">↕</span>`
    : '';
// Price cell:
`<td style="font-weight: 500;">${price}${changeTip}</td>`
```

**CSS:** Add `.price-trend-chip` — small inline badge, `font-size: 0.625rem`, `color: var(--color-ink-muted)`, `cursor: default`.

This is a minimal change: no extra API calls, just the `last_price_change_date` field piggy-backed on the existing `/api/services` response.

### Phase 8 — `templates/appointments/view.html`

**Price deviation indicator in service list:**

In the `svc-item` render within `loadAppointment()`, add a subtle note when `price_charged` differs from the current catalogue price. The `/api/appointments/<id>` response already returns services with `price_charged`; we need to also return `current_catalogue_price` (join with `services` table in the appointment API).

**UI in each `svc-item`:**
```html
<!-- When price_charged != current_catalogue_price: -->
<span style="font-size:0.6875rem; color:var(--color-ink-subtle); margin-left:0.5rem;"
      title="Aktualna cena katalogowa: ${fmtPrice(s.current_catalogue_price)}">
    (cat. ${fmtPrice(s.current_catalogue_price)})
</span>
```

This gives the user context: "this appointment was booked at 80 zł; the service now costs 100 zł."

**Backend change:** `GET /api/appointments/<id>` — join `appointment_services` with `services` to return `current_catalogue_price` per line item.

### Phase 9 — `templates/appointments/list.html`

**No structural change needed.** `price_charged` is already stored and displayed correctly. The list is for scanning appointments, not auditing prices.

**Optional micro-improvement** (low priority): In the "Kwota" column tooltip, show if `total_price != sum(current catalogue prices)`. Skip for this implementation.

### Phase 10 — `templates/analytics/dashboard.html`

**In the "Analiza cen usług" table (`#nav-services`):**

Add two new columns to the `get_service_price_analysis()` query and table:

| Column (new)          | Data source                                          |
|-----------------------|------------------------------------------------------|
| **Ost. zmiana ceny**  | `MAX(sph.effective_from)` from `service_price_history` — date of last price change |
| **Trend ceny**        | Compare `services.price` (current) with price at `start_date` from `service_price_history` — show ↑ / ↓ / = |

**Template table headers:**
```html
<th class="text-right">Ost. zmiana ceny</th>
<th class="text-right">Trend w okresie</th>
```

**JS rendering:**
```js
// last_price_change: ISO date string or null
const lastChange = row.last_price_change
    ? new Date(row.last_price_change).toLocaleDateString('pl-PL')
    : '—';
const trendIcon = row.price_at_period_start == null ? '—'
    : row.catalogue_price > row.price_at_period_start ? '↑'
    : row.catalogue_price < row.price_at_period_start ? '↓'
    : '=';
const trendColor = trendIcon === '↑' ? 'var(--color-error)' : trendIcon === '↓' ? 'var(--color-success)' : 'var(--color-ink-subtle)';
```

**`analytics_repository.py` — update `get_service_price_analysis()`:**
```sql
LEFT JOIN LATERAL (
    SELECT price FROM service_price_history
    WHERE service_id = s.id AND effective_from <= %s   -- start_date
    ORDER BY effective_from DESC LIMIT 1
) sph_start ON true
LEFT JOIN (
    SELECT service_id, MAX(effective_from) AS last_change
    FROM service_price_history GROUP BY service_id
) sph_last ON sph_last.service_id = s.id
```
Add to SELECT: `sph_start.price AS price_at_period_start, sph_last.last_change AS last_price_change`

### Phase 11 — `templates/history/list_refined.html`

**Add `PRICE_CHANGE` action type to `ACTION_LABELS`:**

```js
const ACTION_LABELS = {
    ...existing...,
    PRICE_CHANGE: { label: 'Zmiana ceny', cls: 'action-price-change' },
};
```

**Add CSS class (amber-toned, distinct from UPDATE):**
```css
.action-price-change {
    background: rgba(180, 83, 9, 0.10);
    color: #92400e;
}
```

**Result in UI:** Price change events appear in the "Usługi" tab as:
- Module badge: `Usługa` (entity_type = 'service', existing `.entity-service` styling)
- Action badge: `Zmiana ceny` (amber)
- Pole: `price`
- Było: `80.00`
- Zmieniono na: `100.00`
- Użytkownik: `Jan K.`

No new tab is needed — price changes are naturally grouped under the existing Usługi tab.

---

## File Change Summary

| File | Change type |
|------|-------------|
| `alembic/versions/w8x9y0z1a2b3_create_service_price_history.py` | **NEW** — migration |
| `repositories/services/service_price_history_repository.py` | **NEW** — repository |
| `repositories/roles/role_repository.py` | **EDIT** — add `service_prices` to `ALL_MODULES` + `MODULE_DISPLAY_NAMES` |
| `config/auth_config.py` | **EDIT** — add `service_prices` to `MODULE_PERMISSIONS` |
| `routes/api_routes.py` | **EDIT** — 3 changes: update_service, create_service_endpoint, new price-history endpoint |
| `repositories/analytics/analytics_repository.py` | **EDIT** — extend `get_service_price_analysis()` with JOIN |
| `templates/services/view.html` | **EDIT** — add collapsible price history panel + sparkline |
| `templates/services/edit.html` | **EDIT** — add conditional reason field |
| `templates/services/list.html` | **EDIT** — add trend indicator chip in JS renderer |
| `templates/appointments/view.html` | **EDIT** — show catalogue price deviation in service list |
| `templates/analytics/dashboard.html` | **EDIT** — two new columns in service price table |
| `templates/history/list_refined.html` | **EDIT** — add `PRICE_CHANGE` action label + CSS |

---

## Execution Order

1. Phase 1 (migration) + Phase 2 (repository) — must come first
2. Phase 3 (api_routes) + Phase 4 (RBAC) — depends on Phase 2
3. Phase 5–11 (UI) — all depend on Phase 3 API endpoints being live

Phases 5–11 are independent of each other and can be implemented in any order.

---

## Out of Scope

- Retroactive price history before this feature's deployment date (no historical data to reconstruct)
- Price history for `employee_services.custom_price` overrides — those are employee-level overrides, not catalogue prices
- Versioning/rollback of prices (read-only history only)

---

## Addendum — Post-plan enhancements (2026-06-03)

Shipped after the original 11 phases as commit `c9361d7` (migration `x9y0z1a2b3c4`), deployed to Vultr and verified live with an SSH test harness (**19/19 functional checks passed**, all writes rolled back). This deliberately **supersedes the "read-only history only" scope line above** — limited, RBAC-gated deletion is now supported.

1. **Bug fix — count badge loads eagerly.** The `Historia cen` badge on `services/view.html` now fetches on page load so the entry count shows immediately; the Chart.js sparkline still draws lazily on first expand (a hidden `<details>` canvas sizes to 0px).

2. **New RBAC sub-permission `can_edit_price_history`** (label: *Edycja historii zmian ceny*). A 3rd toggle inside the **services** section of `roles/edit.html` only. New boolean column on `role_permissions` (default FALSE, seeds superuser/admin TRUE), threaded through `role_repository` (`role_can_edit_price_history()`), `auth_config.can_edit_service_price_history()`, and the template context processor (`can_edit_price_history`).

3. **Delete price-history entries.** Per-row delete icon in `services/view.html`, visible only with **`services` access AND `can_edit_price_history`**. Endpoint `DELETE /api/services/<id>/price-history/<entry_id>` (same dual gate). `ServicePriceHistoryRepository.delete_entry()` heals the effective-dated chain:
   - Deleting the **current/open** row reopens the previous row (keeping its original `effective_from`) as the new current price and syncs `services.price`/`currency` to it.
   - Deleting a **closed** row extends the previous row's `effective_to` to close the gap.
   - The **only remaining** row cannot be deleted.
   - Deletes the target *before* reopening the previous row, to avoid a transient two-open-rows violation of the `idx_sph_open_entries` partial unique index.

**Files touched:** `alembic/versions/x9y0z1a2b3c4_add_can_edit_price_history_flag.py` (NEW), `repositories/services/service_price_history_repository.py`, `repositories/roles/role_repository.py`, `config/auth_config.py`, `app.py`, `routes/api_routes.py`, `templates/roles/edit.html`, `templates/services/view.html`.
