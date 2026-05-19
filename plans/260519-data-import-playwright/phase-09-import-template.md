---
title: "Phase 09: Import Page Template + Sidebar Link"
description: "Build templates/data_import/index.html — the admin import page with session badge, date pickers, dry-run toggle, live log panel, result card, and history table — plus the gated sidebar link."
skill: vercel-react-best-practices
status: pending
group: "ui"
dependencies: [phase-08-import-routes]
tags: [phase, implementation, jinja2, tailwind, template, ui]
created: 2026-05-20
updated: 2026-05-20
---

# Phase 09: Import Page Template + Sidebar Link

**Context:** [[plan|Master Plan]] | **Dependencies:** Phase 08 | **Status:** Pending

---

## Overview

Create the Jinja2 template for the import admin page and add a gated sidebar link. This phase is pure server-rendered HTML with TailwindCSS — no JavaScript behaviour (Phase 10 handles all JS). The template must render correctly with no JS enabled.

**Goal:** Navigating to `/import` as an admin renders a fully structured page. All interactive elements exist with correct `id` attributes so Phase 10 can wire them up. The sidebar shows "Import danych" only for users with `data_import` permission.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** New page template + sidebar update.
- **Server Layer:** `main.import_page` route (Phase 08) renders this template.
- **Database Layer:** None — template is pure HTML; Phase 10 JS fetches data at runtime.
- **Integrations:** None.

### User Workflow

1. Admin navigates to `/import` via sidebar link "Import danych"
2. Page loads with:
   - Session status badge (initially empty — Phase 10 JS fills it on DOMContentLoaded)
   - Date range pickers pre-filled with defaults (today − 90 days to today, computed by Phase 10 JS)
   - Dry-run checkbox (unchecked by default)
   - "Importuj" button (enabled)
   - Live log panel (empty, shows placeholder text)
   - Result card (hidden)
   - History table (empty, shows placeholder — Phase 10 JS fills on DOMContentLoaded)

### Integration Points

**Upstream:** Phase 08 → `url_for('main.import_page')` exists
**Downstream:** Phase 10 binds JS to the element IDs defined in this template

---

## Prerequisites & Clarifications

### Questions for User

1. **Page section placement for import link:** Should "Import danych" go in the System section (alongside SMS settings, Users) or in a separate standalone section?
   - **Assumptions if unanswered:** System section, gated on `user_permissions.data_import`. No new section required — System section already contains admin-only links.
   - **Impact:** Determines which `sidebar_section_start` block to insert into.

2. **Log panel height:** Should the live log panel have a fixed height with internal scroll, or grow to fit content?
   - **Assumptions if unanswered:** Fixed height (`h-64`, 16rem) with `overflow-y-auto scroll-smooth`. This keeps the page layout stable during streaming.

3. **History table columns:** The plan specifies date, user, range, status badge, stats. Any additional columns?
   - **Assumptions if unanswered:** Columns: Started at | Range | Triggered by | Status | Inserted | Skipped | Errors | Dry run? | Duration.

### Validation Checklist

- [ ] Phase 08 merged — `url_for('main.import_page')` resolves
- [ ] `user_permissions.data_import` is injected into templates by the app context processor (same mechanism as other `user_permissions.*` flags — verify in `app.py`)
- [ ] `templates/data_import/` directory can be created (no naming conflict)

---

## Requirements

### Functional

**Template structure (`templates/data_import/index.html`):**

```
{% extends "base.html" %}
{% block title %}Import danych — MyWay{% endblock %}
{% block content %}
  <!-- Page header -->
  <!-- Session status card -->
  <!-- Import form card -->
  <!-- Live log panel card -->
  <!-- Result summary card (hidden by default) -->
  <!-- Import history table card -->
{% endblock %}
```

**Session status card:**
- Contains a `<span id="session-badge">` element with placeholder text "Sprawdzanie..."
- "Odnów sesję" button: `<button id="reconnect-btn" class="hidden ...">Odnów sesję</button>` — hidden by default, Phase 10 shows it when status != active
- Manual instructions `<p id="reconnect-manual" class="hidden ...">` — shown by Phase 10 on 503

**Import form card:**
- Date start: `<input type="date" id="date-start" name="date_start">`
- Date end: `<input type="date" id="date-end" name="date_end">`
- Dry-run toggle: `<input type="checkbox" id="dry-run" name="dry_run">` + label
- Submit button: `<button id="import-btn" type="button">Importuj</button>`
- Spinner: `<span id="import-spinner" class="hidden">` (animated SVG)

**Live log panel card:**
- Title: "Log importu"
- Log container: `<div id="log-panel" class="font-mono text-xs bg-gray-900 text-green-400 rounded-lg p-3 h-64 overflow-y-auto scroll-smooth whitespace-pre-wrap">` with placeholder text "Brak aktywnego importu."
- Progress bar: `<div id="progress-bar" class="hidden h-1 bg-primary-500 rounded transition-all duration-300" style="width: 0%">`

**Result summary card:**
- `<div id="result-card" class="hidden ...">` — Phase 10 shows this on `done` event
- Inner content driven by Phase 10 JS (fills in inserted/skipped/errors counts)

**History table card:**
- Title: "Historia importów (ostatnie 20)"
- `<tbody id="history-tbody">` with a placeholder row: `<tr id="history-placeholder"><td colspan="9" class="text-center text-gray-400 py-4">Ładowanie...</td></tr>`
- Column headers: "Rozpoczęto | Zakres | Przez | Status | Wstawiono | Pominięto | Błędy | Suchy | Czas"

### Technical

**Full template scaffold:**

```html
{% extends "base.html" %}
{% block title %}Import danych — MyWay{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto px-4 py-6 space-y-6">

  <!-- Page header -->
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold" style="color: var(--text-primary);">
        Import danych z caldis.pl
      </h1>
      <p class="text-sm mt-1" style="color: var(--text-secondary);">
        Pobiera rezerwacje z caldis.pl przez Playwright i importuje do bazy danych.
      </p>
    </div>
  </div>

  <!-- Session status card -->
  <div class="rounded-xl border p-4" style="background: var(--card-bg); border-color: var(--card-border);">
    <h2 class="text-sm font-semibold mb-3" style="color: var(--text-primary);">Sesja caldis.pl</h2>
    <div class="flex items-center gap-3 flex-wrap">
      <span id="session-badge"
            class="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-700 text-gray-300">
        Sprawdzanie...
      </span>
      <button id="reconnect-btn"
              class="hidden inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                     bg-yellow-600 hover:bg-yellow-500 text-white transition-colors">
        <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Odnów sesję
      </button>
      <p id="reconnect-manual"
         class="hidden text-xs text-yellow-400">
        Serwer bez interfejsu graficznego. Uruchom raz: <code class="font-mono bg-gray-800 px-1 rounded">python scripts/import_appointments_playwright.py --headed</code>
      </p>
    </div>
    <p id="session-age" class="mt-2 text-xs hidden" style="color: var(--text-secondary);"></p>
  </div>

  <!-- Import form card -->
  <div class="rounded-xl border p-4" style="background: var(--card-bg); border-color: var(--card-border);">
    <h2 class="text-sm font-semibold mb-3" style="color: var(--text-primary);">Parametry importu</h2>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label for="date-start" class="block text-xs font-medium mb-1" style="color: var(--text-secondary);">
          Data od
        </label>
        <input type="date" id="date-start" name="date_start"
               class="w-full rounded-lg border px-3 py-2 text-sm"
               style="background: var(--input-bg); border-color: var(--input-border); color: var(--text-primary);">
      </div>
      <div>
        <label for="date-end" class="block text-xs font-medium mb-1" style="color: var(--text-secondary);">
          Data do
        </label>
        <input type="date" id="date-end" name="date_end"
               class="w-full rounded-lg border px-3 py-2 text-sm"
               style="background: var(--input-bg); border-color: var(--input-border); color: var(--text-primary);">
      </div>
    </div>
    <div class="mt-3 flex items-center gap-2">
      <input type="checkbox" id="dry-run" name="dry_run"
             class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-primary-500 focus:ring-primary-500">
      <label for="dry-run" class="text-sm" style="color: var(--text-secondary);">
        Suchy przebieg (parsuj, nie zapisuj do bazy)
      </label>
    </div>
    <div class="mt-4 flex items-center gap-3">
      <button id="import-btn" type="button"
              class="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                     bg-primary-600 hover:bg-primary-500 text-white transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
        <span id="import-btn-label">Importuj</span>
      </button>
      <svg id="import-spinner" class="hidden w-5 h-5 animate-spin text-primary-400"
           fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
      </svg>
      <span id="import-status-msg" class="text-xs" style="color: var(--text-secondary);"></span>
    </div>
  </div>

  <!-- Live log panel card -->
  <div class="rounded-xl border p-4" style="background: var(--card-bg); border-color: var(--card-border);">
    <div class="flex items-center justify-between mb-2">
      <h2 class="text-sm font-semibold" style="color: var(--text-primary);">Log importu</h2>
      <div id="progress-bar-wrapper" class="hidden flex-1 ml-4">
        <div class="h-1 rounded bg-gray-700 overflow-hidden">
          <div id="progress-bar" class="h-full bg-primary-500 transition-all duration-300" style="width:0%"></div>
        </div>
      </div>
    </div>
    <div id="log-panel"
         class="font-mono text-xs rounded-lg p-3 h-64 overflow-y-auto scroll-smooth whitespace-pre-wrap leading-relaxed"
         style="background: #0f172a; color: #4ade80;">
      <span class="text-gray-500">Brak aktywnego importu.</span>
    </div>
  </div>

  <!-- Result summary card (hidden until done) -->
  <div id="result-card" class="hidden rounded-xl border p-4"
       style="background: var(--card-bg); border-color: var(--card-border);">
    <h2 class="text-sm font-semibold mb-3" style="color: var(--text-primary);">Wynik importu</h2>
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3" id="result-stats"></div>
    <p id="result-error" class="hidden mt-3 text-sm text-red-400"></p>
  </div>

  <!-- Import history table card -->
  <div class="rounded-xl border p-4" style="background: var(--card-bg); border-color: var(--card-border);">
    <h2 class="text-sm font-semibold mb-3" style="color: var(--text-primary);">Historia importów (ostatnie 20)</h2>
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <thead>
          <tr class="text-left" style="color: var(--text-secondary);">
            <th class="pb-2 pr-3 font-medium">Rozpoczęto</th>
            <th class="pb-2 pr-3 font-medium">Zakres</th>
            <th class="pb-2 pr-3 font-medium">Przez</th>
            <th class="pb-2 pr-3 font-medium">Status</th>
            <th class="pb-2 pr-3 font-medium text-right">Wstawiono</th>
            <th class="pb-2 pr-3 font-medium text-right">Pominięto</th>
            <th class="pb-2 pr-3 font-medium text-right">Błędy</th>
            <th class="pb-2 pr-3 font-medium">Suchy</th>
            <th class="pb-2 font-medium text-right">Czas</th>
          </tr>
        </thead>
        <tbody id="history-tbody">
          <tr id="history-placeholder">
            <td colspan="9" class="text-center py-6" style="color: var(--text-secondary);">
              Ładowanie historii...
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

</div>
{% endblock %}
```

**Sidebar link** — edit `templates/components/sidebar.html`:

1. Add `'main.import_page'` to the `system_active` variable (line ~23):
   ```jinja2
   {% set system_active = request.endpoint in ['main.history', 'main.email_settings', 'users.users_list', 'roles.roles_list', 'auth.profile', 'sms.sms_settings', 'sms.sms_log', 'main.import_page'] %}
   ```

2. Inside the System `sidebar_section_start` block, after the SMS link and before the Profile link, add:
   ```jinja2
   {% if user_permissions.data_import %}
   {{ sidebar_link(
       url_for('main.import_page'), 'Import danych',
       'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4',
       request.endpoint == 'main.import_page') }}
   {% endif %}
   ```

---

## Decision Log

### Template in base.html Inheritance (ADR-09-01)

**Date:** 2026-05-20
**Status:** Accepted

**Context:** Options: (a) `{% extends "base.html" %}` like all other authenticated pages, (b) standalone template like `auth/login.html`.

**Decision:** Extend `base.html`. The import page is an authenticated admin feature; it needs the sidebar, topbar, and theme variables.

**Consequences:**
- **Positive:** Consistent layout, sidebar, user info footer — zero extra work.
- **Negative:** None.

### No Server-Side Data in Template (ADR-09-02)

**Date:** 2026-05-20
**Status:** Accepted

**Context:** Options: (a) pre-render session status and history in Jinja2 (pass data from route handler), (b) load all data client-side via fetch on DOMContentLoaded.

**Decision:** Client-side loading only. The route handler renders an empty shell; Phase 10 JS fills in session status and history via fetch. This separates the template from data shape changes and avoids a slow server-side Playwright call blocking the initial page render.

**Consequences:**
- **Positive:** Page renders instantly; data loads asynchronously. Route handler is a trivial `render_template()`.
- **Negative:** Slight flash of "Ładowanie..." placeholders — acceptable for an admin page.

---

## Implementation Steps

### Step 0: Manual Check (No Unit Tests for Pure HTML)

Templates are verified by visual inspection and functional tests in Phase 10:

- [ ] `GET /import` returns HTTP 200
- [ ] All expected `id` attributes present in the response HTML: `session-badge`, `reconnect-btn`, `reconnect-manual`, `session-age`, `date-start`, `date-end`, `dry-run`, `import-btn`, `import-btn-label`, `import-spinner`, `import-status-msg`, `log-panel`, `progress-bar`, `progress-bar-wrapper`, `result-card`, `result-stats`, `result-error`, `history-tbody`, `history-placeholder`

Automate the ID check with a simple test:

```python
# tests/routes/test_import_page.py
def test_import_page_renders(client, login_admin):
    resp = client.get('/import')
    assert resp.status_code == 200
    html = resp.data.decode()
    required_ids = [
        'session-badge', 'reconnect-btn', 'date-start', 'date-end',
        'dry-run', 'import-btn', 'log-panel', 'result-card', 'history-tbody',
    ]
    for id_ in required_ids:
        assert f'id="{id_}"' in html, f'Missing id="{id_}" in rendered template'

def test_import_page_requires_login(client):
    resp = client.get('/import', follow_redirects=False)
    assert resp.status_code == 302
```

### Step 1: Create Template Directory and File

```
mkdir templates\data_import\
```

Create `templates/data_import/index.html` with the full scaffold from Requirements.

### Step 2: Edit Sidebar

Edit `templates/components/sidebar.html`:
1. Add `'main.import_page'` to the `system_active` set
2. Add the gated `sidebar_link` for "Import danych" inside the System section

### Step 3: Verify

- [ ] Navigate to `/import` as admin → page renders
- [ ] Navigate to `/import` as stylist → 302 redirect (permission denied)
- [ ] Sidebar shows "Import danych" for admin, hidden for stylist
- [ ] `pytest tests/routes/test_import_page.py -v` — all pass

---

## Verifiable Acceptance Criteria

**Critical Path:**

- [ ] `templates/data_import/index.html` exists and extends `base.html`
- [ ] All required `id` attributes present in rendered HTML
- [ ] `GET /import` returns 200 for admin, 302 for non-admin
- [ ] Sidebar shows "Import danych" only when `user_permissions.data_import`
- [ ] Sidebar System section becomes active when `request.endpoint == 'main.import_page'`
- [ ] Template tests pass

**Visual:**

- [ ] Page sections are clearly separated (card layout)
- [ ] Log panel has dark monospace background
- [ ] Result card is hidden on initial render
- [ ] History table has "Ładowanie..." placeholder before JS runs

---

## Quality Assurance

### Review Checklist

- [ ] No hardcoded strings in English — all user-facing text is Polish
- [ ] All `id` attributes match the list expected by Phase 10 (cross-check during Phase 10 implementation)
- [ ] `{% if user_permissions.data_import %}` gate on sidebar link
- [ ] `system_active` variable updated in sidebar
- [ ] `url_for('main.import_page')` used in sidebar — NOT a hardcoded `/import` string

---

## Dependencies

### Upstream

- **Phase 08** — `main.import_page` endpoint registered so `url_for` resolves
- `user_permissions.data_import` context processor (Phase 01 seeds the permission)

### Downstream

- **Phase 10** — wires JS to all element `id`s defined here

---

## Completion Gate

### Sign-off

- [ ] All acceptance criteria met
- [ ] Template tests passing
- [ ] Visual inspection: page renders correctly in browser
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(import): phase 09 — import page template + sidebar link`

---

**Previous:** [[phase-08-import-routes|Phase 08: Start Import + History Endpoints + Page Route]]
**Next:** [[phase-10-frontend-js|Phase 10: Frontend JS — SSE Client + UI Wiring]]
