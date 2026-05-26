---
title: "Step-0 Entity Import — Implementation Plan"
description: "Pre-flight sync of clients, employees, services, and service addons from caldis.pl into the app DB before each appointment import, eliminating the silent-skip failure mode of Step-1."
status: draft
priority: P0
depends_on: plans/260519-data-import-playwright/IMPLEMENTATION_KNOWLEDGE_BASE.md
created: 2026-05-22
updated: 2026-05-22
tags: [import, playwright, entity-sync, postgres, sse, follow-up]
---

# Step-0: Entity Import — Implementation Plan

> **Read this first:** This plan presupposes complete familiarity with the Step-1 implementation. The authoritative reference for the existing system is
> [`IMPLEMENTATION_KNOWLEDGE_BASE.md`](../260519-data-import-playwright/IMPLEMENTATION_KNOWLEDGE_BASE.md).
> Do **not** rely on the phase plan files of Step-1 — use the knowledge base.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Driving Problem](#2-the-driving-problem)
3. [Scope and Non-Goals](#3-scope-and-non-goals)
4. [Architecture Overview](#4-architecture-overview)
5. [⚠ Critical Decisions Required Before Implementation](#5--critical-decisions-required-before-implementation)
6. [Phase Roadmap](#6-phase-roadmap)
7. [Detailed Phase Specifications](#7-detailed-phase-specifications)
8. [Cross-Cutting Concerns](#8-cross-cutting-concerns)
9. [Risk Register](#9-risk-register)
10. [Rollout Plan](#10-rollout-plan)
11. [Open Questions / TODOs](#11-open-questions--todos)

---

## 1. Executive Summary

**The Mission:** Add a pre-flight entity sync (Step-0) that runs before every appointment
import (Step-1). Step-0 fetches the **clients**, **employees**, **services**, and
**service addons** from caldis.pl and reconciles them with the app's PostgreSQL DB so that
Step-1 can resolve every appointment row without falling into the silent-skip path.

**The Big Shift:** Step-1's `_process_row` increments `skipped_no_client` /
`skipped_no_employee` whenever the resolver returns `None`, **without surfacing which
specific names were skipped**. Today the admin has no signal that the skip happened
because of a missing entity (vs. a deliberate "wolne" slot, vs. a typo). Step-0 closes the
loop by guaranteeing entity completeness **before** the appointment pass starts.

**Primary Deliverables:**

1. **Discovery** — A reverse-engineered catalogue of caldis.pl's entity pages (route,
   columns, export buttons, pagination), captured as fixtures and a doc.
2. **Entity Fetchers** — `fetch_entities_playwright(...)` async function that produces
   three pandas dataframes (`clients_df`, `employees_df`, `services_df`).
3. **Resolution Helpers** — `match_existing_client`, `match_existing_employee`,
   `match_existing_service` — reuse the same key strategies as Step-1's resolvers but
   reversed (caldis row → existing app id, or `None` if new).
4. **Entity Sync Service** — `EntityImportService.run_sync(...)` mirroring
   `DataImportService.run_import(...)` — same SSE event schema, same `IMPORT_RUNNER`
   integration, same dry-run semantics.
5. **HTTP + UI** — A new `/api/import/sync-entities` endpoint, an entity-stats panel on
   `/import`, and (per Decision 5.1) a wiring strategy from the existing "Importuj" button.
6. **Audit Trail** — Entity-level counts stored alongside `import_logs.stats` (or in a
   sibling `entity_import_logs` table — see Decision 5.3).

---

## 2. The Driving Problem

### What Goes Wrong Today

Three failure modes — all silent — that Step-0 eliminates:

**Mode A: New client in caldis, appointment imported, client skipped.**
A walk-in client books in caldis on Monday. On Friday the admin runs Step-1 with a
Mon–Fri date range. `resolve_client_id()` returns `None` because the client doesn't yet
exist in the app DB. The row is counted in `skipped_no_client` and the appointment is lost
— no human-readable signal of *why*.

**Mode B: New employee hired in caldis.**
Same problem: `resolve_employee_id()` returns `None`, the row goes to
`skipped_no_employee`, and the import looks "successful" with zero errors.

**Mode C: New service added in caldis.**
Slightly different — `resolve_service_id()` falls back to `DEFAULT_SERVICE_ID = 20`
(Manicure klasyczny) with a `WARNING` log line, so the appointment **does** import but is
tagged with the wrong service. This is arguably worse than skipping, because it corrupts
analytics without any flag in the stats panel.

### Evidence in the Existing Code

- `services/data_import_helpers.py`:
  - `DEFAULT_SERVICE_ID = 20` — the fallback constant
  - `KALENDARZ_OVERRIDES = {"zrecepcja asia": (3, 24)}` — a manual workaround for one
    specific Joanna whose caldis "Kalendarz" name doesn't match any employee row
- `services/data_import_service.py`:
  - `stats['skipped_no_client']` and `stats['skipped_no_employee']` counters with no
    accompanying detail array

`KALENDARZ_OVERRIDES` is the single best piece of evidence that this feature is needed.
That hardcoded mapping is technical debt accumulated because we have no sync mechanism. A
successful Step-0 rollout removes the need for *any* future entries in that dict.

### Success Criteria (Concrete, Measurable)

After Step-0 ships, the following must hold:

- For a normal weekly import, `skipped_no_client` should approach **0** (any non-zero
  value is now either a deleted/anonymous caldis row or a real data quality issue worth
  inspecting).
- `skipped_no_employee` should be **0** unless an employee was deleted in caldis between
  Step-0 and Step-1.
- The `DEFAULT_SERVICE_ID` fallback should fire **0** times in production runs (we keep
  the constant only for defensive coding).
- The `KALENDARZ_OVERRIDES` dict can be emptied within one release after Step-0 lands.

---

## 3. Scope and Non-Goals

### In Scope

- One-way sync: **caldis → app DB**
- Four entity types: `clients`, `employees`, `services`, plus `service_addons` (if the
  caldis services page exposes them as a separate list — confirmed in Phase 01)
- Reuse of the existing `caldis_session.json`, `IMPORT_RUNNER`, SSE channel, and
  `/import` UI
- Dry-run mode (parse + diff, no writes)
- Multi-sheet XLSX audit export (analogous to Step-1's existing
  `caldis_import_<...>.xlsx`)

### Out of Scope (Explicitly)

| Excluded | Why |
|---|---|
| Two-way sync (app → caldis) | caldis is the source of truth; mutation in reverse would create conflict semantics we don't need |
| Auto-deletion of entities removed in caldis | Too risky: a transient caldis bug could nuke real app data. Manual review only. |
| Fuzzy name matching (Levenshtein etc.) | Adds complexity for marginal gain; Step-0 prevents the new-entity case, which is 95% of the problem |
| Backfilling historical caldis exports | One-time work; can be done with a separate CLI script if ever needed |
| User-facing entity-conflict resolution UI | Admin can read the XLSX audit and run a follow-up manual edit; full conflict UI is a v2 feature |
| SMS/email notifications to clients about merges | Separate concern, never part of an import |

### Explicit Compatibility Constraints

- **MUST NOT** break the existing Step-1 button if the user chooses to skip Step-0 (per
  Decision 5.1).
- **MUST NOT** modify `import_logs` schema in a way that breaks orphan cleanup or the
  history table.
- **MUST NOT** introduce a second `IMPORT_RUNNER` — the in-process singleton stays
  singular; Step-0 and Step-1 share the same run-state gate.
- **MUST NOT** require a second caldis login flow — `caldis_session.json` is the only
  auth surface.

---

## 4. Architecture Overview

### High-Level Flow (Combined Run, Decision 5.1 = Option C "checkbox")

```
Browser  ─── GET /import ──────────────────► main.import_page()
             POST /api/import/start ───────► start_import(
             │                                 date_start,
             │                                 date_end,
             │                                 dry_run,
             │                                 sync_entities=true)
             │                                       │
             │                                 ImportLogRepository.create(
             │                                   …, includes_entity_sync=true)
             │                                 IMPORT_RUNNER.start_import(id, ..., sync_entities=true)
             │                                       │
             │                              threading.Thread(daemon=True)
             │                                       │
             │                              ┌────────┴────────┐
             │                              │  STEP-0 PHASE   │
             │                              │ EntityImportSvc │
             │                              │  ↓ (commit)     │
             │                              ├─────────────────┤
             │                              │  STEP-1 PHASE   │
             │                              │ DataImportSvc   │
             │                              │  ↓ (commit)     │
             │                              └─────────────────┘
             │                                       │
             GET /api/import/<id>/stream ──────────► SSE stream (Step-0 events
             │                                       then Step-1 events, same queue)
             │
             GET /api/import/history ─────────────► history with combined stats
```

### Layering (Same as Step-1)

```
Routes (HTTP)
  → IMPORT_RUNNER (background thread)
    → EntityImportService.run_sync()  ← NEW
      → entity_import_helpers          ← NEW
      → fetch_entities_playwright()    ← NEW
      → ImportLogRepository (extended for entity stats)
      → ClientRepository, EmployeeRepository, ServiceRepository (existing)
    → DataImportService.run_import()  ← UNCHANGED
```

### Cardinality Rule (Carried Over From Step-1)

**One running import at a time** — `IMPORT_RUNNER.start_import` raises `ConflictError`
if anything is `status='running'`. Step-0 + Step-1 in a combined run count as **one**
import row. A standalone "Sync encji" click (Option B / C) is also one import row, but
with `dry_run=False` and Step-1 phase skipped (per Decision 5.1).

---

## 5. ⚠ Critical Decisions Required Before Implementation

> **The next three decisions are not implementation details — they change the database
> schema, route surface, and UI. Please read each section, evaluate the trade-offs, and
> commit to a choice before any code is written.** My recommendation is marked, but the
> domain knowledge here is yours (especially Decision 5.2, which is a data-loss risk
> question only you can answer).

---

### Decision 5.1 — Trigger Model

**Question:** How does the user initiate Step-0?

| Option | UX | Pros | Cons |
|---|---|---|---|
| **A** Auto-run before every Step-1 | Single "Importuj" button | Simplest UX, impossible to forget | Cannot run entity sync standalone (e.g., to seed a fresh DB); adds latency to every appointment import |
| **B** Separate "Synchronizuj encje" button | Two buttons | Total independence, can sync without importing | User can forget to sync, defeating the whole point |
| **C** Checkbox on existing button (default ON) ⭐ | One button + toggle | Auto-protective default + manual override | Slightly more UI; need a way to do entity-only sync (could be: leave dates empty?) |
| **D** Two buttons: "Synchronizuj" AND "Importuj" | Two buttons, no toggle | Each action is explicit | Highest friction; admin must remember the order |

**Recommendation:** **Option C** — checkbox `[x] Synchronizuj encje przed importem` on
the main button, defaulting to ON. Adds an "Tylko synchronizuj encje" link button that
runs Step-0 with no Step-1 phase (the route handler treats `date_start=None,
date_end=None` as "entity sync only").

**Why C wins:** The dominant failure mode today is the admin running Step-1 without
realizing new entities exist. A default-on checkbox eliminates that failure path while
preserving the "I just need to sync entities" escape hatch.

> ### ✋ YOUR INPUT NEEDED — Decision 5.1
>
> Below this line, write your final choice and any additional UX rules you want enforced.
> Five to ten lines is enough. Examples of rules to consider:
> - Should the checkbox state be remembered across page loads?
> - If the user clicks "Tylko synchronizuj encje" with a date range filled in, do we
>   ignore the dates or refuse to start?
> - Should there be a confirmation modal when the checkbox is OFF ("Are you sure you
>   want to skip entity sync?")?
>
> **DECISION: Option C — checkbox default ON + "Tylko synchronizuj" button.**
> - Checkbox label: "Synchronizuj encje przed importem", default checked
> - Checkbox state persisted in localStorage
> - "Tylko synchronizuj encje" link-button runs Step-0 with no Step-1 (dates not required)
> - If dates are filled in and user clicks "Tylko synchronizuj", dates are ignored (entity sync only)
> - No confirmation modal when checkbox is unchecked

---

### Decision 5.2 — Update Policy for Existing Entities

**Question:** When Step-0 encounters a caldis entity whose name matches an existing app
entity, but with different contact info (phone/email/etc.) — what should happen?

| Option | Behaviour | Risk |
|---|---|---|
| **A** Insert-only — never modify existing rows | Caldis changes (e.g., updated phone number) are ignored after first sync | Stale data in app DB |
| **B** Full upsert — overwrite all changed fields | Caldis is single source of truth | **Wipes any manual admin edits** (notes, preferences, hand-entered emails) |
| **C** Smart merge — fill only NULL fields ⭐ | Adds caldis info where app has nothing; never overwrites existing values | Caldis updates to existing values are still ignored — but admin edits are safe |
| **D** Diff + queue for manual review | Detects all differences, writes them to a "pending changes" table for admin approval | Massive UI work; ships months later |

**Recommendation:** **Option C** (smart merge), but with one explicit exception:
`last_visit_date` is **always** overwritten if caldis has a later date (this matches the
existing Step-1 behaviour in `_process_row`).

**Why C wins:** Mode A is too restrictive (caldis is the source of truth for things like
phone numbers); Mode B has destroyed admin work in the past at similar salons (per
analogous projects); Mode D adds 2–3 weeks of UI work. Mode C is the pragmatic middle
ground and has a clean rollback story: if a field is wrong, the admin can manually edit
it back, and Step-0 will not re-overwrite.

**Important corollary:** Step-0 must record per-field "what would have changed" in the
audit XLSX so the admin can spot-check whether the smart-merge policy is leaving
important caldis updates on the table. If after one month the admin sees lots of
"would-have-updated phone" rows, we can revisit and move toward Option B for specific
fields.

> ### ✋ YOUR INPUT NEEDED — Decision 5.2
>
> Below this line, write your final policy. Be specific about which fields are protected
> from overwrite (per-table) — and whether any fields should always overwrite (like
> `last_visit_date`). Examples:
>
> **DECISION: Option C — smart merge (fill NULL fields only).**
>
> CLIENTS:
>   - first_name, last_name: protect if app value is non-null
>   - phone:                 protect if app value is non-null
>   - email:                 protect if app value is non-null (moot — all NULL in caldis)
>   - notes:                 always protect (manual field, never overwrite)
>   - last_visit_date:       always overwrite if caldis date is later
>
> EMPLOYEES: skipped in Step-0 (manual add only)
>
> SERVICES:
>   - name:             protect if app value is non-null
>   - price:            protect if app value is non-null (price changes need accountant review)
>   - duration_minutes: protect if app value is non-null
>   - category:         always protect (not in caldis; app value is manually set)
>
> Audit XLSX records all "would_have_updated" fields so admin can spot drift.

---

### Decision 5.3 — Audit Trail Storage

**Question:** Where do we record what Step-0 did?

| Option | Storage | Pros | Cons |
|---|---|---|---|
| **A** Extend `import_logs.stats` JSONB ⭐ | One row per combined run | No migration, reuses history UI, atomic with appointment stats | Stats blob grows; cannot query "all client inserts in May" easily |
| **B** Separate `entity_import_logs` table | One row per entity-sync run | Indexable, queryable, decoupled | New migration, new repository, new history endpoint, doubles UI work |
| **C** Per-entity rows in a `entity_import_events` table | One row per affected entity | Full audit grain ("client #42 phone updated 2026-05-22") | Significant scope creep, hundreds of rows per run |

**Recommendation:** **Option A** for now — extend `import_logs.stats`. Reserve the right
to migrate to Option C later if compliance/audit needs grow.

**Proposed JSONB structure (Option A):**

```json
{
  "appointments": {
    "inserted": 142,
    "skipped_zero": 8,
    "skipped_no_client": 0,
    "skipped_no_employee": 0,
    "skipped_duplicate": 3,
    "errors": 0
  },
  "entities": {
    "clients":   { "inserted": 3, "updated": 1, "matched": 412, "skipped": 0, "errors": 0 },
    "employees": { "inserted": 0, "updated": 0, "matched": 7,   "skipped": 0, "errors": 0 },
    "services":  { "inserted": 1, "updated": 0, "matched": 24,  "skipped": 0, "errors": 0 },
    "addons":    { "inserted": 0, "updated": 0, "matched": 8,   "skipped": 0, "errors": 0 }
  },
  "phase_durations_seconds": {
    "step0_entities": 12.4,
    "step1_appointments": 67.1
  }
}
```

The **XLSX audit file** continues to be the human-readable record — Step-0 adds three
sheets to it: `Encje_klienci`, `Encje_pracownicy`, `Encje_uslugi`.

> ### ✋ YOUR INPUT NEEDED — Decision 5.3
>
> Confirm Option A or override. If you pick A, weigh in on the JSONB structure above —
> specifically whether you want a `details` array under each entity type that lists
> affected IDs and field changes (useful for compliance, expensive for storage).
>
> **DECISION: Option A — extend import_logs.stats JSONB.**
> Use the structure proposed above. No `details` array (no per-row IDs in the blob).
> Per-row detail lives in the XLSX audit file only.

---

## 6. Phase Roadmap

Nine phases, two groups, ~3–4 days of focused work. Each phase is sized for a single
implementation session (2–3 hours, including review).

| Phase | Title | Group | Focus | Est. KB |
|:----:|:----------------------------------|:----------|:-----------------------------|:----:|
| **01** | Caldis Entity Page Discovery | discovery | Reverse-engineer caldis entity pages, capture fixtures | 8 |
| **02** | Entity Schema Extensions + Module Permission | foundation | Decision 5.3 result; module permission seed (`entity_import` or extend `data_import`) | 10 |
| **03** | Entity Resolution Helpers | foundation | `match_existing_client`/`employee`/`service` + diff functions | 12 |
| **04** | Playwright Entity Fetcher | engine | `fetch_entities_playwright()` — extends the existing session module | 14 |
| **05** | Entity Import Service Core | engine | `EntityImportService.run_sync(...)` — orchestration + insert/update | 15 |
| **06** | Runner Integration (Combined Run) | engine | Make `IMPORT_RUNNER` execute Step-0 → Step-1 in one thread | 10 |
| **07** | Routes + Validation | http | `/api/import/start` extension (sync_entities flag) + new entity-only endpoint | 11 |
| **08** | Template + Frontend JS Updates | ui | Checkbox, "Tylko synchronizuj" button, entity-stats panel, history extension | 12 |
| **09** | Tests, Cleanup, KALENDARZ_OVERRIDES Removal | quality | Unit + route tests, empty out the overrides dict, doc update | 10 |

**Group Summary**

| Group | Phases | Purpose |
|---|---|---|
| **discovery** | 01 | Cannot build anything until caldis page structure is known. **Single-session investigation that produces fixtures + a discovery doc; no production code.** |
| **foundation** | 02–03 | DB extensions, RBAC, and the pure-Python diff/match layer that every later phase depends on |
| **engine** | 04–06 | Playwright integration, the new service class, and the runner extension that wires it in |
| **http** | 07 | Route changes (extension + new endpoint) |
| **ui** | 08 | Template + JS updates — the only user-visible deliverable |
| **quality** | 09 | Tests + cleanup. **MUST NOT** be skipped; the overrides removal is a success-criteria gate. |

**Group ordering:** discovery → foundation → engine → http → ui → quality. Dependencies
flow top to bottom; no phase reaches back upstream.

---

## 7. Detailed Phase Specifications

> Each spec uses the same structure as Step-1's phase files:
> overview, integration points, work plan, acceptance criteria, edge cases, test plan.

---

### Phase 01 — Caldis Entity Page Discovery

**Skill:** none (manual investigation phase)
**Dependencies:** working `caldis_session.json` locally
**Status:** Pending
**Estimated time:** 2 hours

#### Goal

Produce a written specification of caldis.pl's entity surfaces (clients, employees,
services) so that Phase 04 can confidently build the Playwright extractors. **Zero
production code in this phase.**

#### Deliverables

1. `plans/260522-entity-import-step0/CALDIS_ENTITY_DISCOVERY.md` containing for each
   entity type:
   - URL path on caldis.pl
   - DOM structure of the listing page (table selectors, pagination, search)
   - Column headers and their order
   - Whether an export button exists (XLSX/CSV/JSON) — preferred path
   - If no export: pagination behaviour and the per-row extraction strategy
   - Sample of 3 rows (anonymised — replace surnames with "X.")
2. Three XLSX fixture files in `tests/fixtures/caldis_entities/`:
   - `clients_sample.xlsx` (~10 rows)
   - `employees_sample.xlsx` (all rows, since employee count is small)
   - `services_sample.xlsx` (all rows)
3. A photo of the caldis entity page UI (optional, but useful for the doc).

#### Work Plan

1. Run `python scripts/create_caldis_session.py` locally to refresh the session if
   needed (headed mode required for the captcha).
2. Manually navigate to caldis.pl and find the entity pages. Typical guesses to try:
   - `/Klienci`, `/Klienci/Lista`, `/Klienci/Eksport`
   - `/Pracownicy`, `/Personel`
   - `/Uslugi`, `/Cennik`, `/Katalog`
3. For each page found:
   - Press F12 → Network → look for an XHR that returns the list data (preferred over
     DOM scraping)
   - Identify any "Eksportuj" / "Pobierz" button — note the resulting file format
4. If an export button exists, download a sample and save it to the fixtures folder.
5. If no export exists, sketch out the DOM extraction strategy: which selector for the
   row, which `<td>` indices for which column.
6. Document caldis-side quirks: e.g., does the clients page show deleted/archived rows
   by default? Is there a filter that should be applied?

#### Acceptance Criteria

- [ ] Discovery doc exists with all three entity sections filled in
- [ ] Three fixture files are committed under `tests/fixtures/caldis_entities/`
- [ ] Each fixture has documented column mappings (column header → app DB field)
- [ ] For at least one entity type, an export-button path is confirmed (vs. DOM scrape)
- [ ] **If service addons are not a separate caldis concept**, document that finding
      and remove addons from the scope of all subsequent phases.

#### Edge Cases / Open Questions to Resolve

- Does caldis show deleted clients? If yes, how do we filter them out?
- Are employees paginated? (Probably small enough to fit on one page.)
- Do services have category/grouping info in caldis? If so, can it inform our
  `services.category` column?
- Are there any per-row "is_active" / "is_archived" flags we should respect?

---

### Phase 02 — Entity Schema Extensions + Module Permission

**Skill:** `postgres-expert`
**Dependencies:** Phase 01 discovery complete; Decision 5.3 finalized
**Status:** Pending
**Estimated time:** 1.5 hours

#### Goal

Lock in the database changes implied by Decision 5.3 and ensure the new
`/api/import/sync-entities` route surface is gated by an RBAC permission.

#### Work Plan (assumes Decision 5.3 = Option A)

1. **Create a single alembic migration:**
   `alembic/versions/<rev>_extend_import_logs_for_entity_sync.py`
   with `down_revision = 'v7w8x9y0z1a2'` (the existing Step-1 migration head).
2. The migration does **two** things:
   - Adds a `includes_entity_sync BOOLEAN NOT NULL DEFAULT FALSE` column to
     `import_logs` (so we can filter history by run type).
   - Updates the `check_import_logs_status` constraint **only if** Decision 5.1 requires
     a new status (it shouldn't — `running`/`completed`/`failed`/`cancelled` still
     cover all Step-0 outcomes).
3. **No new tables.** The `import_logs.stats` JSONB blob carries everything per the
   Decision 5.3 structure.
4. **Module permission:** Reuse the existing `data_import` permission. **Do not** create
   a separate `entity_import` permission — the cognitive load on the admin isn't worth
   it, and the two surfaces are always invoked by the same role (`superuser` + `admin`).

#### Acceptance Criteria

- [ ] Migration runs up + down cleanly on a local PostgreSQL DB
- [ ] `import_logs` history endpoint still returns 200 with old rows that have
      `includes_entity_sync IS NULL` (default backfill handles this)
- [ ] No new entries in `MODULE_PERMISSIONS` (auth_config.py)
- [ ] No new entries in `ALL_MODULES` (roles/role_repository.py)
- [ ] An ALTER on the existing CHECK constraint is documented as a no-op if the status
      enum didn't change

#### Reference Files

- `alembic/versions/v7w8x9y0z1a2_create_import_logs_and_module_permission.py` — the
  existing Step-1 migration; mimic its style (especially the down-revision wiring and
  the conditional drop).

---

### Phase 03 — Entity Resolution Helpers

**Skill:** `service-builder` (this is pure-Python service-layer code)
**Dependencies:** Phase 02
**Status:** Pending
**Estimated time:** 2.5 hours

#### Goal

Build the pure-Python "given a caldis row, find the matching app row or None" helpers,
and the "given an app row + a caldis row, compute what would change" diff helpers.
These functions are what make Decision 5.2 (smart merge) tractable — they are deliberately
separate from any DB writes.

#### Module to Create

`services/entity_import_helpers.py`

#### Functions

```python
# --- Match functions (caldis row → app id or None) ---

def match_existing_client(
    caldis_row: dict,
    client_index: ClientIndex,    # built once at the start of the sync
) -> Optional[int]:
    """
    Match strategy (in order):
      1. exact (first_name_lower, last_name_lower) match
      2. reversed (last_name_lower, first_name_lower) match (caldis flips occasionally)
      3. normalized phone match
      4. None
    """
    ...

def match_existing_employee(caldis_row: dict, employee_index: EmployeeIndex) -> Optional[int]:
    """Match by first_name_lower exact; never substring (employees are few)."""
    ...

def match_existing_service(caldis_row: dict, service_index: ServiceIndex) -> Optional[int]:
    """Match by name_lower exact; never substring (we already know substring is fragile)."""
    ...

# --- Diff functions (returns a per-field plan for the smart-merge policy) ---

def diff_client(app_row: dict, caldis_row: dict, policy: ClientMergePolicy) -> ClientDiff:
    """
    Returns ClientDiff with:
      - to_update: {field: new_value} -- only fields where app is NULL and caldis has a value
      - would_have_updated: {field: (app_value, caldis_value)} -- for the audit XLSX
    """
    ...

def diff_employee(app_row, caldis_row, policy) -> EmployeeDiff:
    ...

def diff_service(app_row, caldis_row, policy) -> ServiceDiff:
    ...
```

#### Index Builders

```python
def build_client_index(conn) -> ClientIndex:
    """One SELECT, build all match maps at once for memory efficiency."""
    # Returns a dataclass containing:
    #   by_full_name: dict[(fn_lower, ln_lower), client_dict]
    #   by_phone:     dict[normalized_phone, client_dict]
    ...

def build_employee_index(conn) -> EmployeeIndex: ...
def build_service_index(conn) -> ServiceIndex: ...
```

#### Critical Reuse

- `normalize_phone()` — already exists in `services/data_import_helpers.py`. **Import,
  do not duplicate.**
- The (first_name_lower, last_name_lower) tuple normalization should be a single shared
  helper extracted into a private `_normalize_name_pair()` function — extract once,
  reuse in both `data_import_helpers.py` and `entity_import_helpers.py`.

#### Acceptance Criteria

- [ ] All `match_*` functions have unit tests covering: exact match, reversed name
      match, phone fallback, no match, blank-input handling
- [ ] All `diff_*` functions have unit tests covering: identical rows (no diff), one
      field different (correct diff produced), app has NULL field (caldis fills it),
      app has value and caldis has different value (no overwrite, recorded in
      `would_have_updated`)
- [ ] No DB access inside `match_*` or `diff_*` functions (pure functions only)
- [ ] Index builders use a single SELECT each (no N+1)

#### Test Coverage Target

~20 unit tests for this module. Mirror the structure of
`tests/services/test_data_import_helpers.py`.

---

### Phase 04 — Playwright Entity Fetcher

**Skill:** `playwright-e2e` mindset, but executed as a backend module
**Dependencies:** Phase 01 (discovery), Phase 03
**Status:** Pending
**Estimated time:** 3 hours

#### Goal

Build `scripts/fetch_entities_playwright.py` — an async coroutine that loads the
caldis session, navigates to each entity page, and returns three pandas dataframes.

#### Function Signature

```python
async def fetch_entities_playwright(
    session_file: Path,
    output_dir: Path,
    progress_callback: Callable[[dict], None],
    headed: bool = False,
) -> dict[str, Path]:
    """
    Returns:
      {
        'clients':   Path("caldis_entities_clients_<ts>.xlsx"),
        'employees': Path("caldis_entities_employees_<ts>.xlsx"),
        'services':  Path("caldis_entities_services_<ts>.xlsx"),
      }
    Raises:
      ImportError("Sesja wygasla") | ImportError("Brak zapisanej sesji")  -- same
        exception strings as the appointment fetcher, so EntityImportService can
        reuse the session-status detection logic.
    """
    ...
```

#### Implementation Notes

- **Reuse Playwright setup** from `scripts/import_appointments_playwright.py` — extract
  a shared `_open_caldis_browser(session_file)` helper into a new module
  `scripts/caldis_playwright_common.py`. Both fetchers import from it.
- **Per-entity download** — depending on Phase 01 findings, each entity uses either:
  - Direct XLSX/CSV download (preferred — same pattern as appointments)
  - Paginated DOM scrape that yields a synthesised XLSX
- **Progress events:** emit one event per entity-type completion:
  ```json
  {"type": "log", "message": "Pobrano 415 klientów z caldis", "phase": "entities"}
  ```
- **Cleanup:** the three XLSX files are persisted to `output_dir` so the service can
  read them after Playwright closes; service is responsible for deletion.

#### Acceptance Criteria

- [ ] `fetch_entities_playwright()` produces three XLSX files for a real caldis session
      on a local dev machine
- [ ] If the session is expired, raises `ImportError("Sesja wygasla")` — never a bare
      Playwright timeout
- [ ] Emits at least one progress event per entity type
- [ ] Function is fully importable from `services/entity_import_service.py` without
      side effects (no `if __name__ == '__main__'` running at import time)

#### Edge Cases

- Caldis renders a "loading…" overlay while the list fetches → use `wait_for_selector`
  with an explicit "rows loaded" selector, not a hard sleep
- Pagination state survives across navigations → always navigate to page 1 explicitly
  before scraping
- A caldis-side filter that excludes inactive employees → must be turned OFF, or we
  miss real entities (Phase 01 must confirm)

---

### Phase 05 — Entity Import Service Core

**Skill:** `service-builder`
**Dependencies:** Phase 03, Phase 04
**Status:** Pending
**Estimated time:** 3 hours

#### Goal

Build `services/entity_import_service.py` — the orchestration class that ties together
the Playwright fetch, the resolution helpers, the DB writes, and the SSE progress
events. Same structural pattern as `DataImportService`.

#### Class Skeleton

```python
class EntityImportService:
    def run_sync(
        self,
        import_id: int,
        dry_run: bool,
        progress_callback: Callable[[dict], None],
    ) -> dict:
        """
        Runs synchronously inside the same background thread that will run
        DataImportService.run_import() after this returns.

        Phases inside run_sync():
          1. emit log: "Start synchronizacji encji"
          2. fetch_entities_playwright(...) -- gets 3 xlsx files
          3. pool.getconn() -- thread-local connection
          4. build_*_index(conn) -- 3 in-memory maps
          5. for each entity type:
              a. pd.read_excel() the file
              b. for each row:
                  - match_existing_*(...) -> existing_id | None
                  - if None: INSERT new entity, increment 'inserted'
                  - if exists: diff_*(...) -> compute updates
                      - if to_update non-empty AND NOT dry_run: UPDATE, increment 'updated'
                      - else: increment 'matched'
                  - on any per-row exception: increment 'errors', continue
                  - every 25 rows: emit stats event
          6. commit (or rollback in dry_run)
          7. update import_logs.stats with the entity block
          8. _export_entity_xlsx() -- 3 sheets added to the main audit XLSX
          9. emit log: "Synchronizacja encji zakończona"
        """
        ...
```

#### Key Implementation Rules

- **Same connection handling pattern as Step-1** — `pool.getconn()` before any work that
  needs to log failure, `finally: pool.putconn(conn)`.
- **No new repository methods needed on `ClientRepository`/`EmployeeRepository`/`ServiceRepository`** for inserts
  — use the existing `.create()` methods. **Updates require new methods** named
  `update_partial(id, fields: dict)` on each repo (Phase 05 sub-task: add these).
  Rationale: existing `update()` overwrites all fields; partial update is genuinely
  new functionality required by Decision 5.2 smart-merge.
- **Progress event schema** — same `{type, message, stats, status, timestamp}` envelope
  as Step-1, with one additional field:
  ```json
  {"phase": "entities" | "appointments"}
  ```
  so the frontend can route the event into the correct panel section.

#### Acceptance Criteria

- [ ] `run_sync()` is a single public method; everything else is private
- [ ] On per-row failure, `errors` counter increments and processing continues (mirrors
      `_process_row` in Step-1)
- [ ] On Playwright session expiry, calls `repo.update_session_status('expired')` and
      raises so the runner marks the import failed
- [ ] Dry-run path NEVER calls `INSERT` or `UPDATE` — verified via SQL mock count
- [ ] XLSX audit gets three new sheets: `Encje_klienci`, `Encje_pracownicy`,
      `Encje_uslugi` — each lists `(matched|inserted|updated|skipped|error)` per row

#### Test Plan

- Mock `fetch_entities_playwright()` to return pre-canned XLSX fixtures from Phase 01
- Mock the DB pool with `mock_db` fixture
- Verify each row's path: insert / update / matched / error
- Verify dry-run skips all writes
- Verify session-expiry exception is converted to `'expired'` status before re-raise

---

### Phase 06 — Runner Integration (Combined Run)

**Skill:** `service-builder`
**Dependencies:** Phase 05
**Status:** Pending
**Estimated time:** 1.5 hours

#### Goal

Extend `services/data_import_runner.py` so the same thread executes Step-0 first (if
requested), then Step-1 (if dates are present). Single `import_logs` row, single
progress queue.

#### Change Surface

`ImportRunner.start_import` gets two new parameters:

```python
def start_import(
    self,
    import_id: int,
    date_start: Optional[date],
    date_end: Optional[date],
    dry_run: bool,
    sync_entities: bool = False,      # NEW
) -> threading.Thread:
    ...
```

And `_run_thread` becomes:

```python
def _run_thread(self, import_id, date_start, date_end, dry_run, sync_entities):
    q = self._registry[import_id]['queue']
    try:
        if sync_entities:
            EntityImportService().run_sync(import_id, dry_run, progress_callback=q.put)
        if date_start is not None and date_end is not None:
            DataImportService().run_import(
                import_id, date_start, date_end, dry_run, progress_callback=q.put
            )
    except Exception as exc:
        # belt-and-suspenders: same as today
        ...
    finally:
        q.put({"type": "done"})
        ...
```

#### Validation Cases (in `routes/import_routes.py`)

- `sync_entities=False` AND `date_start is None` → `ValidationError`
  ("Musisz wybrać co najmniej jedno: synchronizację encji lub import wizyt")
- `sync_entities=True` AND dates supplied → run both, Step-0 first
- `sync_entities=True` AND dates absent → run only Step-0
- `sync_entities=False` AND dates supplied → run only Step-1 (current behaviour)

#### Acceptance Criteria

- [ ] Existing Step-1-only path is unchanged when `sync_entities=False`
- [ ] Failures in Step-0 short-circuit Step-1 (don't run Step-1 on a half-synced DB)
- [ ] The `done` sentinel still fires exactly once at the end of the combined run
- [ ] `ConflictError` (another import running) still works correctly when a Step-0+Step-1
      combined run is starting

---

### Phase 07 — Routes + Validation

**Skill:** `service-builder` (Flask route layer)
**Dependencies:** Phase 06
**Status:** Pending
**Estimated time:** 1.5 hours

#### Endpoints

| Route | Method | Purpose | Body |
|---|---|---|---|
| `/api/import/start` | POST | EXTENDED — accepts `sync_entities` boolean | `{date_start, date_end, dry_run, sync_entities}` |
| `/api/import/sync-entities` | POST | NEW — convenience endpoint for entity-only sync | `{dry_run}` |

The second endpoint is **sugar** — internally it calls the same handler as
`/api/import/start` with `date_start=None, date_end=None, sync_entities=true`. Worth
having for clarity in the frontend.

#### Validation Chain Updates

In `start_import()` (the route handler):

1. If `sync_entities=False` AND no dates → 422 ValidationError
2. If `sync_entities=False` AND dates present → existing logic, unchanged
3. If `sync_entities=True` AND no dates → entity-only sync (dates pass through as None)
4. If `sync_entities=True` AND dates present → existing date validation + run both

#### Acceptance Criteria

- [ ] All four logical cases above have a route test
- [ ] The new endpoint mirrors the response shape of `/api/import/start` (returns
      `{success, import_id}`, HTTP 202)
- [ ] The history endpoint surfaces both `entities` and `appointments` stats blocks in
      the JSON response (frontend can render either)

---

### Phase 08 — Template + Frontend JS Updates

**Skill:** none (vanilla JS / Jinja edits)
**Dependencies:** Phase 07
**Status:** Pending
**Estimated time:** 2.5 hours

#### Template Changes (`templates/data_import/index.html`)

Add to the form section:

```html
<label class="flex items-center gap-2 mt-3">
  <input type="checkbox" id="sync-entities" checked>
  <span>Synchronizuj encje przed importem
    <span class="tooltip">Pobiera nowych klientów, pracowników i usługi z caldis</span>
  </span>
</label>

<button id="btn-sync-only" class="btn-secondary mt-2">
  Tylko synchronizuj encje
</button>
```

Add a new panel section that appears during Step-0:

```html
<section id="entity-stats-panel" class="hidden">
  <h3>Synchronizacja encji</h3>
  <div class="grid grid-cols-4 gap-3">
    <!-- 4 stat cards: klienci / pracownicy / usługi / dodatki -->
  </div>
</section>
```

#### JS Changes

Three new behaviours, marked here as TODOs that need *minor* user judgement on UX
copy (Polish wording etc.). All structural logic is implementation, not design:

```javascript
// 1. Wire sync-entities checkbox into the start payload
async function startImport() {
  const payload = {
    date_start: dateStartEl.value || null,
    date_end:   dateEndEl.value || null,
    dry_run:    dryRunEl.checked,
    sync_entities: syncEntitiesEl.checked,  // NEW
  };
  // ...existing POST logic
}

// 2. New "Tylko synchronizuj" button
btnSyncOnly.addEventListener('click', async () => {
  await fetch('/api/import/sync-entities', {
    method: 'POST',
    body: JSON.stringify({ dry_run: dryRunEl.checked }),
    headers: { 'Content-Type': 'application/json' },
  });
  // ...open EventSource same as main flow
});

// 3. SSE handler routes by phase
source.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.phase === 'entities') {
    appendEntityLog(data);
    updateEntityStats(data.stats);
  } else {
    appendLog(data);
    updateAppointmentStats(data.stats);
  }
};
```

#### Acceptance Criteria

- [ ] Checkbox state persists in localStorage across page reloads (small UX win)
- [ ] Entity stats panel only appears when a sync is happening or just finished
- [ ] History table shows a small icon column distinguishing entity-only vs combined
      runs (e.g., 📊 vs 🔄)
- [ ] All Polish copy is consistent in tone with the existing Step-1 wording

---

### Phase 09 — Tests, Cleanup, KALENDARZ_OVERRIDES Removal

**Skill:** `service-builder` + `playwright-e2e` for the optional E2E
**Dependencies:** Phase 08
**Status:** Pending
**Estimated time:** 2 hours

#### Goal

Lock the feature down with tests, retire the technical debt the feature was designed to
eliminate, and document the new system.

#### Tasks

1. **Unit tests** (target: ~30 new tests across the three new files)
   - `tests/services/test_entity_import_helpers.py` (~20 tests, covered in Phase 03 AC)
   - `tests/services/test_entity_import_service.py` (~8 tests for dry-run, error paths,
     session-expiry, smart-merge policy)
   - `tests/routes/test_entity_routes.py` (~6 tests for the four validation cases plus
     the new sync-only endpoint)

2. **Empty `KALENDARZ_OVERRIDES`** in `services/data_import_helpers.py`:
   - Run one combined Step-0+Step-1 import on a real-ish dataset
   - Verify `skipped_no_employee == 0`
   - Delete the dict entries; keep the dict as `KALENDARZ_OVERRIDES: dict = {}` (so
     callers still work)
   - Add a `logger.warning("KALENDARZ_OVERRIDES dict accessed but empty — this is
     expected post-Step-0")` to catch any regression

3. **Update the knowledge base** —
   `plans/260519-data-import-playwright/IMPLEMENTATION_KNOWLEDGE_BASE.md`:
   - Update section 5 (Service Layer) to mention `EntityImportService`
   - Update section 11 (Business Rules) — rules 5 and 6 about `KALENDARZ_OVERRIDES`
     and `DEFAULT_SERVICE_ID` need a note that they're now defensive-only
   - Update section 14 — mark Step-0 as completed, point to this plan
   - Add a section 15 covering the entity sync (or extend section 5)

4. **Create a sibling `IMPLEMENTATION_KNOWLEDGE_BASE.md`** for Step-0:
   `plans/260522-entity-import-step0/IMPLEMENTATION_KNOWLEDGE_BASE.md`
   following the same 14-section structure as Step-1's.

#### Acceptance Criteria

- [ ] All 30 new tests pass
- [ ] `KALENDARZ_OVERRIDES` dict is empty in `main`
- [ ] One real combined run completed successfully in production with
      `skipped_no_*` all zero
- [ ] Knowledge base files updated and reviewed

---

## 8. Cross-Cutting Concerns

### 8.1 Single-Worker Gunicorn Constraint (Unchanged)

`IMPORT_RUNNER` remains a single-process singleton. Step-0 inherits this constraint. If
multi-worker scaling is ever needed, the Redis pub/sub migration plan in section 8 of
Step-1's knowledge base applies equally to entity-sync events.

### 8.2 Session File Safety

Step-0 reuses `assets/temp/caldis_session.json`. The file is NEVER:
- Served to clients
- Returned by any API
- Logged in plaintext

Same as Step-1.

### 8.3 Logging & Observability

Every Step-0 phase emits log lines at INFO level with structured prefixes:
- `[ENTITY-SYNC]` for orchestration events
- `[ENTITY-MATCH]` for the per-row match decisions
- `[ENTITY-DIFF]` for smart-merge decisions

This makes production debugging tractable without flooding the SSE stream.

### 8.4 Backwards Compatibility

- The existing `/api/import/start` request body **without** the `sync_entities` field
  must continue to work — default to `False` server-side
- The existing `import_logs.stats` shape (flat `{inserted, skipped_zero, ...}`) must
  still be readable — Phase 02 migration adds the `entities` block as optional, and
  the history serializer in `import_routes.py:_serialize_history` handles both shapes
- The Step-1 button (without checkbox change) must behave identically to today

### 8.5 Internationalization

All user-facing strings are Polish, consistent with the existing UI. Internal log
messages can be English (consistent with the existing codebase).

---

## 9. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Caldis has no entity export buttons → Phase 04 becomes DOM-scrape only | Medium | Medium | Phase 01 explicitly confirms this before Phase 04 starts; fallback strategy documented |
| 2 | Smart-merge policy too conservative → caldis updates lost | Medium | Low | Audit XLSX shows `would_have_updated` rows; admin can flag fields to flip to overwrite later |
| 3 | Smart-merge policy too aggressive → admin edits overwritten | Low (given Decision 5.2 = Option C) | High | Decision 5.2 explicitly protects existing non-null fields |
| 4 | Step-0 succeeds but Step-1 fails → DB in half-synced state | Medium | Low | Step-0 commits are independently valid; partial sync is better than no sync |
| 5 | Combined run exceeds Gunicorn worker timeout (currently 30s for requests) | Low | Medium | Requests just start the thread; the thread itself has no timeout. Confirm gunicorn.conf.py timeout settings allow long requests for SSE. |
| 6 | New caldis client has same `(fn, ln)` as existing app client (e.g., two "Anna Nowak") | Medium | Medium | Match strategy tries phone fallback; if phone differs, treat as different person and insert; admin reviews in audit XLSX |
| 7 | Caldis API/HTML changes break the fetcher | Low | High | Document the discovery findings in Phase 01 so the next developer can re-do discovery quickly |
| 8 | Frontend SSE handler breaks when `phase` field is added to events | Low | Medium | Backwards-compatible: events without `phase` field route to the appointments panel by default |

---

## 10. Rollout Plan

### Step-by-Step Deploy

1. **Phase 01 in isolation** — merge the discovery doc + fixtures to `main` first; no
   production code touched. This unblocks all later phases for parallel work.
2. **Phases 02–06 on a feature branch** (`entity-import-step0`) — these are server-side
   only and have no user surface. Can be merged behind a feature flag (`Config.ENABLE_ENTITY_SYNC`)
   that defaults to `False` in production.
3. **Phases 07–08 on the same branch** — adds the UI. Merge with feature flag still
   `False`.
4. **Manual QA on staging** — flip the flag, run a dry-run combined import, inspect the
   audit XLSX, run a real import, verify counts.
5. **Phase 09** — empty `KALENDARZ_OVERRIDES`, ship to production with the flag ON.
6. **One-week observation** — monitor `import_logs.stats` for any `entities.errors > 0`
   or unexpected `would_have_updated` patterns in the audit XLSX.

### Feature Flag

Add `ENABLE_ENTITY_SYNC: bool = False` to `config/settings.py`. The
`/api/import/sync-entities` route returns 503 when flag is OFF. The checkbox is hidden in
the template when flag is OFF. This gives a clean kill-switch if the rollout goes
sideways.

### Database Migration Strategy

The single migration in Phase 02 is **additive only** — no destructive ALTERs, no data
backfill that could fail. Run it on staging first, then production. Rollback is the
`downgrade()` step in the migration which drops the new column.

---

## 11. Open Questions / TODOs

These need answers before Phase 04 starts in earnest:

- [x] **Decision 5.1** — checkbox default ON + "Tylko synchronizuj" button ✓
- [x] **Decision 5.2** — smart merge, protect non-null fields, last_visit_date always overwrites ✓
- [x] **Decision 5.3** — extend import_logs.stats JSONB, no per-row details array ✓
- [x] **Phase 01 outcome** — service addons NOT a caldis concept; out of scope for all phases ✓
- [ ] **Caldis pagination quirks** — Phase 01 must confirm whether the clients page
      paginates and how many rows total exist (informs memory footprint estimate)
- [ ] **Audit XLSX file location** — same project-root location as Step-1's audit
      file? Or a sibling `audit/` directory? (Suggested: same location for consistency.)
- [ ] **Naming** — `EntityImportService` vs `EntitySyncService`? The plan uses
      `EntityImport` for consistency with Step-1, but `Sync` is arguably more accurate
      semantically. Final call deferred to implementation.

---

## Appendix A — Reference File Inventory (Predicted)

### New Files

```
alembic/versions/
  <rev>_extend_import_logs_for_entity_sync.py

scripts/
  caldis_playwright_common.py             ← shared Playwright setup
  fetch_entities_playwright.py            ← Phase 04 deliverable

services/
  entity_import_helpers.py                ← Phase 03 deliverable
  entity_import_service.py                ← Phase 05 deliverable

routes/import_routes.py                   ← MODIFIED (Phase 07)
services/data_import_runner.py            ← MODIFIED (Phase 06)
templates/data_import/index.html          ← MODIFIED (Phase 08)

tests/services/
  test_entity_import_helpers.py
  test_entity_import_service.py
tests/routes/
  test_entity_routes.py
tests/fixtures/caldis_entities/
  clients_sample.xlsx
  employees_sample.xlsx
  services_sample.xlsx

plans/260522-entity-import-step0/
  PLAN.md                                 ← this file
  CALDIS_ENTITY_DISCOVERY.md              ← Phase 01 deliverable
  IMPLEMENTATION_KNOWLEDGE_BASE.md        ← Phase 09 deliverable
```

### Modified Existing Files

```
config/settings.py
  → Add ENABLE_ENTITY_SYNC flag

repositories/clients/client_repository.py
repositories/employees/employee_repository.py
repositories/services/service_repository.py
  → Add update_partial(id, fields: dict) method on each

services/data_import_helpers.py
  → Extract _normalize_name_pair() into shared helper
  → Empty KALENDARZ_OVERRIDES dict (Phase 09)

plans/260519-data-import-playwright/IMPLEMENTATION_KNOWLEDGE_BASE.md
  → Cross-reference Step-0 in section 14; update sections 5, 11
```

---

## Appendix B — Approximate Effort Estimate

| Phase | Hours | Notes |
|---|---|---|
| 01 | 2.0 | Manual discovery, can be done by anyone with caldis access |
| 02 | 1.5 | Migration + RBAC |
| 03 | 2.5 | Pure-Python helpers + tests |
| 04 | 3.0 | Playwright work; risk of caldis quirks |
| 05 | 3.0 | Service orchestration; reuses a lot from Step-1 |
| 06 | 1.5 | Runner extension |
| 07 | 1.5 | Routes + validation |
| 08 | 2.5 | Template + JS + localStorage |
| 09 | 2.0 | Tests + KALENDARZ_OVERRIDES cleanup + docs |
| **Total** | **~19.5 h** | ~3 focused dev days |

---

**End of plan.** Awaiting Decisions 5.1, 5.2, 5.3 before Phase 01 starts.
