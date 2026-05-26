---
title: "Phase 01: Caldis Entity Page Discovery"
description: "Reverse-engineer caldis.pl's clients/employees/services pages: URLs, DOM structure, export buttons, column mappings. Produce a discovery document and anonymised XLSX fixtures consumed by all later phases."
skill: none
status: pending
group: "discovery"
dependencies: []
tags: [phase, discovery, manual, no-code, playwright, fixtures]
created: 2026-05-22
updated: 2026-05-22
---

# Phase 01: Caldis Entity Page Discovery

**Context:** [[PLAN|Step-0 Master Plan]] | **Dependencies:** Working `caldis_session.json` | **Status:** Pending

---

## Overview

Reverse-engineer the three entity surfaces on caldis.pl that Step-0 will scrape:
**clients**, **employees**, **services**. Capture the URL, the page structure
(table vs. XHR), the column layout, the export button (if any), and three small XLSX
fixture files that every later phase will consume for tests.

**This is a manual, no-code phase.** Its only deliverables are a documentation file and
fixture XLSX files. Treat it as a small research task — 2 hours, one focused session.

**Goal:** After this phase, anyone implementing Phase 04 (the Playwright fetcher) has a
deterministic spec to code against — no guesswork, no caldis trial-and-error inside the
implementation phase.

---

## Why This Phase Exists (Read Before Starting)

Step-1 had the luxury of knowing the appointments XLSX format ahead of time — the
reference script `scripts/import_appointments_playwright.py` already exported it for us
and we knew every column. Step-0 has no such head start. We must discover:

1. **Does each entity even have a dedicated caldis page?** It's possible that "service
   addons" are not a separate concept in caldis — they may be modelled as service
   variants under the main services page. Until we look, we don't know.
2. **Is there an export button?** If yes, Phase 04 becomes trivial (mimic the
   appointments XLSX download pattern). If no, Phase 04 must scrape the DOM, which is
   substantially more fragile and time-consuming to build.
3. **What columns does caldis expose?** We need to map every caldis column to either an
   existing app DB column or to "ignore." The mapping informs Phase 03's helpers and
   Phase 05's insert/update statements.

**Skipping or under-investing in this phase is the single biggest predictor of Phase 04
slipping its 3-hour estimate.** Take the time here.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** None.
- **Server Layer:** None.
- **Database Layer:** None.
- **Integrations:** Manual interaction with caldis.pl via a real browser — Playwright
  not required (yet).

### Investigation Workflow

**Trigger:** Developer (you) decides to start Step-0 implementation.

**Steps:**

1. Refresh the caldis session if expired (`python scripts/create_caldis_session.py`
   locally with `--headed`).
2. Open caldis.pl in a regular browser — **not** headless, because we want to use
   DevTools.
3. For each entity type (clients → employees → services):
   - Navigate to the suspected URL (see the URL guess list below)
   - Open DevTools → Network tab → filter `XHR`
   - Reload the page
   - Identify the request that returns the list data (look for JSON responses)
   - Note: URL, query params, response shape, total row count if exposed
   - Look on the page for an "Eksportuj", "Pobierz", "XLSX", or "CSV" button
   - If present, click it and capture the resulting file
   - If not present, document the DOM structure of the list table
4. Anonymise the captured XLSX (see Anonymisation Protocol below) and commit to
   `tests/fixtures/caldis_entities/`.
5. Fill in `CALDIS_ENTITY_DISCOVERY.md` using the template at the bottom of this phase
   doc.

**Success Outcome:** A merge-ready PR containing the discovery doc + three fixture
files. Zero production code touched.

### Problem Being Solved

**Pain Point:** Without this phase, Phase 04 starts by spending its first two hours
clicking around caldis — interleaved with code-writing — and almost certainly produces
a fetcher that has to be rewritten when the developer realises an entity has a
different structure than assumed.

**Alternative Approach:** Skip discovery, let Phase 04 figure it out as it goes.
Rejected — it conflates investigation work (where mistakes are cheap) with code
authoring (where mistakes are expensive in review cycles).

### Integration Points

**Upstream Dependencies:**
- A valid `assets/temp/caldis_session.json` (or willingness to refresh it via the
  headed login flow)
- Local Python environment with `pandas` + `openpyxl` available (for the
  anonymisation script)

**Downstream Consumers:**
- Phase 03 (resolver helpers) — reads fixture XLSX files in unit tests
- Phase 04 (Playwright fetcher) — reads the discovery doc to know URLs and selectors
- Phase 05 (service core) — reads fixture XLSX files in unit tests

**Data Flow:**

```
You + caldis.pl in browser
   │
   ├── observe URL paths      ───► CALDIS_ENTITY_DISCOVERY.md (URL section)
   ├── observe DOM/XHR        ───► CALDIS_ENTITY_DISCOVERY.md (Structure section)
   ├── observe column layout  ───► CALDIS_ENTITY_DISCOVERY.md (Mapping section)
   └── download sample data   ───► tests/fixtures/caldis_entities/*.xlsx (anonymised)
```

---

## ✋ Your Input Needed — Pre-Investigation Shortcuts

Before you start clicking around caldis blind, fill in the table below with anything
you already know. You use caldis daily — this is your domain knowledge, and putting it
here will likely cut investigation time in half.

| Entity | URL you know exists                                | Notes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
|---|----------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Clients | `https://caldis.pl/Client`                         | Export dropdown list item: on_click - saves clients in xlsx file. Full XPatch: '/html/body/nav/div[1]/div[2]/div[2]/div[2]/div/ul/li[2]/a', selector:<br/>'body > nav > div.container-fluid.navbar-main > div.navbar-toolbar > div.toolbar-filters > div:nth-child(3) > div > ul > li:nth-child(2) > a'                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Employees | `Only one new employee to be added manualy - skip` | N/A                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Services | `https://caldis.pl/Services`                       | selector: '#dynamic-content > div > table'<br/>full <br/>Xpath:'/html/body/div[4]/div/div/div/table'<br/>Request url: 'https://caldis.pl/Services/List?f.Pagination.CurrentPage=1&f.Order.Name=Name&f.Order.Descending=True&f.Search=&X-Requested-With=XMLHttpRequest&_=1779749044'<br/>Column 'NAZWA' is for service name<br/>Column 'Cena brutto' is for service price [PLN](format: #.00)<br/>Column 'czas usługi' is for duration [minutes](integer value, no decimals)<br/>Response: 'send @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 ajax @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 i @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:281 (anonymous) @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:281 dispatch @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 y.handle @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 trigger @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 (anonymous) @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 each @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 each @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 trigger @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 (anonymous) @ https://caldis.pl/bundles/portal-common?v=NnXRnQEDBlCw0R37t5NuWLxQoi6BsnxRDrKZ9Ivut601:5195 dispatch @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264 y.handle @ https://caldis.pl/bundles/jquery-and-plugins?v=ZjY6HEwn6VutF9uIJI1YzDJu72pS7IjkggigAuxogqU1:264'<br/>'Other columns are not relevant - skip |
| Service addons | `not a concept in Caldis - skip` | N/A |
s
> **Replace the TODOs above with what you already know.** If you genuinely don't know,
> leave them and the investigator will discover them from scratch. Either way, complete
> this table before starting the manual investigation.

---~~~~

## Work Plan

### Pre-Flight Checks

- [ ] `assets/temp/caldis_session.json` exists and is less than 30 days old
  (`/api/import/session-status` returns `"active"`)
- [ ] Local Python venv has `pandas`, `openpyxl`, `python-dotenv` installed
- [ ] You can manually log in to caldis.pl in your regular browser
- [ ] You have a side window with this phase doc open for note-taking

### Step 1 — Clients Investigation (~30 min)

1. Navigate to your suspected clients URL (from the table above, or start at
   `caldis.pl/Klienci`).
2. Open DevTools (F12) → Network → XHR filter → Reload page (Ctrl+R).
3. Identify the row-loading request. Note in CALDIS_ENTITY_DISCOVERY.md:
   - Full URL with query params
   - HTTP method
   - Response content-type (JSON / HTML fragment / XML)
   - Sample of the response shape (first row, anonymised)
4. Inspect the list table in DOM:
   - Note `<table>` or `<div>` root selector
   - Note column header labels (in Polish, as caldis displays them)
   - Note whether pagination exists; if yes, the per-page size and total-count
     indicator
5. Look for an export button. Try:
   - Top-right area of the list
   - A "..." or kebab menu near the title
   - Right-clicking on the table (some caldis pages have a context menu)
6. If an export exists:
   - Click it — observe what file downloads (XLSX, CSV, JSON?)
   - Save the file to `tests/fixtures/caldis_entities/clients_raw.xlsx` (do **not**
     commit this — it has real PII; we'll anonymise next)
   - In Network tab, note the request URL that produced the download — Phase 04 can
     hit it directly instead of clicking the button
7. Anonymise: run the snippet in **Anonymisation Protocol** below.
8. Commit `tests/fixtures/caldis_entities/clients_sample.xlsx` (~10 rows, anonymised).

### Step 2 — Employees Investigation (~20 min)

Same procedure as Step 1. Employees are typically a small set (single-digit count),
so:
- Capture **all** employees in the fixture, not just a sample
- Pay extra attention to fields that map to `employees.commission_rate` — does caldis
  even expose this, or is it set only in the app?
- Note any caldis-side "is_active" / "is_archived" flag

### Step 3 — Services Investigation (~30 min)

Same procedure. Services have more variety:
- Look specifically for whether **service addons** appear as:
  - A separate page entirely (best case — clean separation)
  - Sub-rows under each service (nested in the same list)
  - Independent services with a "this is an addon" flag column
  - Not a concept at all (caldis just has one flat services list)
- Note the price column format (is it `15.00` or `15,00 zł`?)
- Note the duration format (minutes? `HH:MM`? a `duration_minutes` field?)
- Note any category/group field — could populate `services.category`

### Step 4 — Anonymisation and Commit (~30 min)

Apply Anonymisation Protocol (below) to all three raw XLSX files. Commit the sanitised
versions. Delete the raw files. Fill in CALDIS_ENTITY_DISCOVERY.md using the template
at the bottom of this doc. Open a PR.

---

## Anonymisation Protocol

Real caldis data contains PII (full names, phone numbers, emails). Fixtures committed
to git must be anonymised. **Never commit a raw caldis download.**

### Anonymisation Script

Save the following as `scripts/anonymize_caldis_fixture.py` (a one-off utility — does
not need tests, may be deleted after Phase 01 completes if not useful elsewhere):

```python
"""
Anonymise a raw caldis XLSX export for committing as a test fixture.

Usage:
    python scripts/anonymize_caldis_fixture.py \
        --input  tests/fixtures/caldis_entities/clients_raw.xlsx \
        --output tests/fixtures/caldis_entities/clients_sample.xlsx \
        --entity clients

Rules:
  - Surnames: replaced with "X." (single letter + period)
  - First names: replaced with synthetic Polish names from a static list
  - Phone numbers: replaced with deterministic 9-digit numbers starting "500"
  - Emails: replaced with "anon{N}@example.invalid"
  - Notes: dropped
  - All other fields preserved
"""
import argparse
from pathlib import Path
import pandas as pd

SYNTHETIC_FIRST_NAMES = [
    "Anna", "Maria", "Katarzyna", "Joanna", "Magdalena",
    "Piotr", "Tomasz", "Jakub", "Marcin", "Andrzej",
]

def anonymise_clients(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['first_name'] = [SYNTHETIC_FIRST_NAMES[i % len(SYNTHETIC_FIRST_NAMES)]
                        for i in range(len(df))]
    df['last_name']  = ['X.' for _ in range(len(df))]
    if 'phone' in df.columns:
        df['phone']  = [f"500{str(100000 + i).zfill(6)}" for i in range(len(df))]
    if 'email' in df.columns:
        df['email']  = [f"anon{i}@example.invalid" for i in range(len(df))]
    for col in ('notes', 'uwagi', 'komentarz'):
        if col in df.columns:
            df[col] = ''
    return df

def anonymise_employees(df: pd.DataFrame) -> pd.DataFrame:
    # Employees are not PII in the salon context, but anonymise anyway
    return anonymise_clients(df)

def anonymise_services(df: pd.DataFrame) -> pd.DataFrame:
    # Services don't contain PII — keep names + prices as-is for realism
    return df.copy()

ANONYMISERS = {
    'clients':   anonymise_clients,
    'employees': anonymise_employees,
    'services':  anonymise_services,
}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input',  required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--entity', required=True, choices=list(ANONYMISERS))
    p.add_argument('--limit',  type=int, default=10,
                   help='Max rows in output fixture (default: 10)')
    args = p.parse_args()

    df = pd.read_excel(args.input, dtype=str)
    df = df.head(args.limit if args.entity != 'employees' else len(df))
    df = ANONYMISERS[args.entity](df)
    df.to_excel(args.output, index=False)
    print(f"Wrote {len(df)} rows to {args.output}")

if __name__ == '__main__':
    main()
```

### Anonymisation Checklist

- [ ] Raw downloaded XLSX files are added to `.gitignore` (or deleted) before commit
- [ ] Anonymised fixtures contain no real surnames, phones, emails, or notes
- [ ] Fixture row count is small: 10 for clients/services, all rows for employees
- [ ] Git history is clean — no accidental commits of raw files (use `git log
      --follow` on the fixture path to verify)

---

## CALDIS_ENTITY_DISCOVERY.md — Output Template

Copy this template into `plans/260522-entity-import-step0/CALDIS_ENTITY_DISCOVERY.md`
and fill it in as you investigate. Every `[TODO: ...]` placeholder must be replaced
or explicitly marked "N/A — confirmed not present."

```markdown
# Caldis.pl Entity Page Discovery

**Investigated:** [TODO: YYYY-MM-DD] by [TODO: name]
**Session file used:** assets/temp/caldis_session.json (age: [TODO: N days])
**Browser:** [TODO: Chrome 132 / Firefox / etc.]

---

## 1. Clients

**Listing URL:** `https://caldis.pl/[TODO]`
**Total rows in production today:** ~[TODO: N]
**Pagination:** [TODO: yes/no; if yes, page size + how to advance]
**Export button present:** [TODO: yes/no]
**If yes, export format:** [TODO: XLSX / CSV / JSON]
**Direct download URL:** `https://caldis.pl/[TODO]` (from Network tab)

### DOM Structure (if no export)

- Table root selector: `[TODO: e.g., #clients-table > tbody]`
- Row selector: `[TODO: e.g., tr.client-row]`
- Columns (in order):
  - Col 0: `[TODO: header label]` → maps to app field `clients.[TODO]`
  - Col 1: `[TODO]` → `clients.[TODO]`
  - ...

### Column → App Field Mapping

| Caldis Column | App DB Field | Notes |
|---|---|---|
| Imię | clients.first_name | direct |
| Nazwisko | clients.last_name | direct |
| Telefon | clients.phone | normalise via normalize_phone() before insert |
| Email | clients.email | direct |
| [TODO] | [TODO] | [TODO] |
| [TODO: caldis-only column] | (ignored) | not in app schema |
| (none in caldis) | clients.notes | will remain NULL on insert; protected by smart-merge |

### Quirks / Gotchas

- [TODO: e.g., caldis shows archived clients by default — filter button must be clicked first]
- [TODO: e.g., phone numbers come in two formats; some have "+48", some don't]

### Fixture File

`tests/fixtures/caldis_entities/clients_sample.xlsx` — 10 anonymised rows

---

## 2. Employees

**Listing URL:** `https://caldis.pl/[TODO]`
**Total employees today:** [TODO: N]
**Export button present:** [TODO]

### Column → App Field Mapping

| Caldis Column | App DB Field | Notes |
|---|---|---|
| Imię | employees.first_name | direct |
| [TODO] | [TODO] | [TODO] |
| (none in caldis) | employees.commission_rate | NOT synced — set manually in app |
| (none in caldis) | employees.base_salary | NOT synced — set manually in app |

### Quirks

- [TODO: e.g., "zrecepcja asia" appears in caldis appointments but not in employees list — Joanna shares the receptionist account; this is the source of KALENDARZ_OVERRIDES tech debt]

### Fixture File

`tests/fixtures/caldis_entities/employees_sample.xlsx` — all employees (small set)

---

## 3. Services

**Listing URL:** `https://caldis.pl/[TODO]`
**Total services today:** [TODO: N]
**Export button present:** [TODO]
**Service addons handling:** [TODO: one of:
  (a) separate page at /[TODO]
  (b) sub-rows under each service
  (c) flat services list with an addon flag column [TODO: which column?]
  (d) not a concept in caldis — addons exist only in the app DB
]

### Column → App Field Mapping

| Caldis Column | App DB Field | Notes |
|---|---|---|
| Nazwa | services.name | direct |
| Cena | services.price | strip "zł" suffix, replace "," with "." |
| Czas trwania | services.duration_minutes | [TODO: format conversion needed?] |
| Kategoria | services.category | [TODO: free text or fixed list?] |

### Quirks

- [TODO]

### Fixture File

`tests/fixtures/caldis_entities/services_sample.xlsx` — 10 rows covering category variety

---

## 4. Cross-Cutting Findings

- **Auth state:** Confirmed that `caldis_session.json` is sufficient for all three
  pages — no additional permissions or sub-accounts needed. [TODO: confirm or
  document any escalation]
- **Rate limits:** [TODO: did you observe any throttling when fetching multiple
  pages quickly?]
- **Browser language:** Confirmed Polish UI throughout. No locale switch needed.
  [TODO: confirm or document any exception]
- **Concurrent access:** [TODO: did you test fetching while someone else uses
  caldis in another tab? Any session conflicts?]

---

## 5. Implementation Recommendations for Phase 04

Based on these findings, Phase 04 should:

1. [TODO: e.g., "Use the direct download URL for clients (one HTTP GET, no DOM
   interaction)"]
2. [TODO: e.g., "Scrape DOM for employees because no export exists; use the
   table selector above"]
3. [TODO: e.g., "Combine services + addons into a single fetch since they share
   the same page"]

### Estimated Phase 04 Effort

[TODO: confirm or revise the 3-hour estimate based on what you found]
```

---

## Acceptance Criteria

- [ ] `plans/260522-entity-import-step0/CALDIS_ENTITY_DISCOVERY.md` exists and every
      `[TODO: ...]` placeholder is either replaced or explicitly marked N/A
- [ ] Three anonymised XLSX fixtures exist under
      `tests/fixtures/caldis_entities/` and contain no real PII
- [ ] No raw (un-anonymised) caldis exports are in git history (verified with
      `git log --all --full-history -- tests/fixtures/caldis_entities/`)
- [ ] For at least one entity type, an export-button path is documented (vs. DOM
      scrape) — this is a hard requirement; if no export exists for any entity,
      escalate to a re-scoping discussion before proceeding to Phase 04
- [ ] If `service_addons` is not a separate caldis concept, the discovery doc says
      so explicitly and addons are removed from the scope of Phases 04, 05, and 09
- [ ] PR is opened and reviewed by one other person familiar with caldis (catches
      cases where the investigator missed a quirk)

---

## Edge Cases / Open Questions

These are the questions Phase 01 must answer; they're listed here so the
investigator doesn't forget any:

| # | Question | Why it matters |
|---|---|---|
| 1 | Does caldis show deleted/archived clients in the default list view? | If yes and we sync them, we'll re-insert deleted records into the app DB |
| 2 | Are employees paginated, or does the full list fit on one page? | Affects Phase 04's scraping strategy |
| 3 | Are service addons a separate concept in caldis? | Determines whether `service_addons` table is touched at all |
| 4 | What's caldis's phone number format? Single format or multiple? | Determines whether `normalize_phone()` covers all cases |
| 5 | Does the clients page expose a "last_visit_date" or similar field? | If yes, Step-0 can sync it directly and Step-1's update logic stays untouched |
| 6 | Is there a "client_id" or stable unique identifier in caldis? | If yes, we could match by ID instead of fuzzy name — huge reliability improvement |
| 7 | Does the page require any non-default filter clicks (e.g., "Pokaż wszystkich") to show the full list? | Phase 04's Playwright script must replicate the filter state |
| 8 | Are caldis column headers the same in different browser languages, or is the Polish UI baked in? | Affects column-mapping robustness |

Question #6 is the most important — **if caldis exposes a stable client ID**, the
entire Step-0 design becomes simpler and more reliable. Investigate this first.

---

## Test Plan

This phase produces no code, so there are no unit tests. However, the fixtures it
produces are tested implicitly in Phase 03 (which mounts them into the resolver tests)
and Phase 05 (which mounts them into the service tests).

**Manual verification before merging:**

1. Open each anonymised fixture in Excel/LibreOffice — confirm no real surnames,
   phone numbers, or emails are present.
2. Run `git diff --stat tests/fixtures/caldis_entities/` — confirm only the three
   expected files are added.
3. Open CALDIS_ENTITY_DISCOVERY.md — confirm zero remaining `[TODO: ...]`
   placeholders.
4. (Optional) Have a non-investigator skim the discovery doc and try to predict
   what Phase 04 will do; if they can predict it cleanly, the doc is good.

---

## Out of Scope for Phase 01

- Writing the Playwright fetcher (that's Phase 04)
- Writing match/diff helpers (that's Phase 03)
- Any database changes (that's Phase 02)
- Building automated tests (this phase is exempt — its deliverables are docs +
  fixtures)
- Confirming that the existing `caldis_session.json` works in production (it's
  shared infrastructure from Step-1; Phase 01 assumes it works locally)

---

## Risks Specific to This Phase

| Risk | Mitigation |
|---|---|
| Investigator misses a quirk because they don't use that part of caldis daily | Acceptance criteria requires a second-reviewer pass |
| Caldis UI changes between Phase 01 and Phase 04 | Phase 01 to Phase 04 should ideally happen within the same week; if longer gap, re-verify Phase 04 selectors before coding |
| Investigator captures real PII in fixtures by accident | Anonymisation script makes this hard to do by accident; checklist catches it on review |
| Discovery reveals caldis exposes no useful entity pages at all | Worst case: re-scope Step-0 to extract entities from the appointments XLSX itself (degraded mode); document this as a contingency in the discovery doc |

---

**End of Phase 01.** Estimated effort: 2 hours of investigation + 30 minutes of
write-up. Output unblocks Phase 02 through Phase 05.
