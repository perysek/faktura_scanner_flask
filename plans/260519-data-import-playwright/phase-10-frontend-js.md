---
title: "Phase 10: Frontend JS — SSE Client + UI Wiring"
description: "Wire all JavaScript for the import page: SSE EventSource client, session status badge, reconnect flow, history table rendering, date defaults, and import button state management."
skill: vercel-react-best-practices
status: pending
group: "ui"
dependencies: [phase-09-import-template]
tags: [phase, implementation, javascript, sse, ui, frontend]
created: 2026-05-20
updated: 2026-05-20
---

# Phase 10: Frontend JS — SSE Client + UI Wiring

**Context:** [[plan|Master Plan]] | **Dependencies:** Phase 09 | **Status:** Pending

---

## Overview

Add inline JavaScript to `templates/data_import/index.html` that wires the static shell from Phase 09 into a fully interactive admin page. All JS lives in a single `<script>` block at the bottom of the `{% block content %}` section — matching the existing pattern in `templates/appointments/calendar.html` and similar pages.

**Goal:** An admin can click "Importuj", watch live log lines stream into the log panel, see the result card appear on completion, and browse import history — all without page reloads.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** Completes the UI group. After this phase, the entire feature is end-to-end functional.
- **Server Layer:** Consumes all endpoints from Phases 06–08.
- **Database Layer:** Indirect — via the API endpoints.
- **Integrations:** Browser `EventSource` API (native, no polyfill needed for Chrome/Firefox/Edge).

### User Workflow

**On page load:**
1. JS sets default date range: `date-start = today − 90 days`, `date-end = today`
2. JS calls `GET /api/import/session-status` → updates session badge + shows/hides reconnect button
3. JS calls `GET /api/import/history` → renders history table rows

**Triggering an import:**
1. Admin adjusts dates, optionally checks dry-run, clicks "Importuj"
2. JS validates client-side (both dates filled, start <= end)
3. POSTs to `/api/import/start` → receives `{import_id}`
4. Disables import button, shows spinner
5. Opens `EventSource('/api/import/<import_id>/stream')`
6. On each `log` event → appends coloured line to `#log-panel`, auto-scrolls to bottom
7. On each `progress` event → updates `#import-status-msg` with running counts
8. On `done` event → shows `#result-card` with stats, re-enables import button, closes EventSource
9. Refreshes history table after 1s delay

**Reconnect flow:**
1. Admin clicks "Odnów sesję"
2. Button disabled + spinner shown
3. POSTs to `/api/import/reconnect-session`
4. On 200 → re-fetches session status, updates badge
5. On 503 → shows `#reconnect-manual` message (server is headless)
6. On other error → shows generic error in `#import-status-msg`

---

## Prerequisites & Clarifications

### Questions for User

1. **SSE retry on disconnect:** If the browser loses the EventSource connection mid-import (e.g. brief WiFi drop), should JS automatically reconnect?
   - **Assumptions if unanswered:** Yes — browser's native `EventSource` already retries automatically (spec-defined reconnect delay). No manual retry logic needed unless `close()` was called explicitly.
   - **Impact:** Missed events during the reconnect gap won't be replayed (queue-based SSE, no event-id support). The final `done` event is always in the queue so the user sees the result.

2. **Log line colours:** Should different log levels have different colours in the log panel?
   - **Assumptions if unanswered:** Yes. `info` → green (`#4ade80`); `warning` → yellow (`#facc15`); `error` → red (`#f87171`); `progress` type → cyan (`#67e8f9`).

3. **History table: auto-refresh after import?** Should the history table refresh automatically after an import completes?
   - **Assumptions if unanswered:** Yes — after the `done` event, wait 1s then call `loadHistory()` again.

### Validation Checklist

- [ ] Phase 09 merged — all required `id` attributes exist in the DOM
- [ ] All API endpoints from Phases 06–08 are reachable
- [ ] `EventSource` is supported in the target browsers (Chrome/Firefox/Edge — all modern)
- [ ] No Content Security Policy blocks `EventSource` to same origin (check `app.py` CSP headers if set)

---

## Requirements

### Functional

**Date defaults (on DOMContentLoaded):**

```javascript
const today = new Date();
const ninetyDaysAgo = new Date(today);
ninetyDaysAgo.setDate(today.getDate() - 90);

function fmtDate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

document.getElementById('date-start').value = fmtDate(ninetyDaysAgo);
document.getElementById('date-end').value   = fmtDate(today);
```

> [!NOTE]
> `new Date()` is correct here — we want local dates for the input, not UTC. The `YYYY-MM-DD` string produced feeds the `<input type="date">` which treats the value as a local date. This matches the global date-formatting rule: avoid UTC-midnight off-by-one.

**Session status fetch:**

```javascript
async function loadSessionStatus() {
    const badge = document.getElementById('session-badge');
    const reconnectBtn = document.getElementById('reconnect-btn');
    const ageEl = document.getElementById('session-age');

    try {
        const resp = await fetch('/api/import/session-status');
        const data = await resp.json();

        const statusMap = {
            active:  { label: 'Aktywna',     cls: 'bg-green-700 text-green-100' },
            expired: { label: 'Wygasła',      cls: 'bg-yellow-700 text-yellow-100' },
            missing: { label: 'Brak sesji',   cls: 'bg-red-700 text-red-100' },
        };
        const s = statusMap[data.status] || { label: data.status, cls: 'bg-gray-700 text-gray-300' };

        badge.textContent = s.label;
        badge.className = `inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${s.cls}`;

        if (data.status !== 'active') {
            reconnectBtn.classList.remove('hidden');
        } else {
            reconnectBtn.classList.add('hidden');
        }

        if (data.age_days !== null) {
            ageEl.textContent = `Wiek sesji: ${data.age_days} dni`;
            ageEl.classList.remove('hidden');
        }
    } catch (e) {
        badge.textContent = 'Błąd sprawdzania';
        badge.className = 'inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-gray-700 text-gray-400';
    }
}
```

**Reconnect button:**

```javascript
document.getElementById('reconnect-btn').addEventListener('click', async function () {
    const btn = this;
    const manualMsg = document.getElementById('reconnect-manual');
    btn.disabled = true;
    btn.textContent = 'Łączę...';

    try {
        const resp = await fetch('/api/import/reconnect-session', { method: 'POST' });
        if (resp.status === 503) {
            manualMsg.classList.remove('hidden');
        } else if (resp.ok) {
            await loadSessionStatus();
            manualMsg.classList.add('hidden');
        } else {
            const data = await resp.json().catch(() => ({}));
            setStatusMsg(data.error || 'Błąd podczas odnawiania sesji.', 'error');
        }
    } catch (e) {
        setStatusMsg('Błąd połączenia z serwerem.', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Odnów sesję';
    }
});
```

**Import button + SSE client:**

```javascript
let activeEventSource = null;

document.getElementById('import-btn').addEventListener('click', async function () {
    const dateStart = document.getElementById('date-start').value;
    const dateEnd   = document.getElementById('date-end').value;
    const dryRun    = document.getElementById('dry-run').checked;

    if (!dateStart || !dateEnd) {
        setStatusMsg('Wybierz zakres dat.', 'error'); return;
    }
    if (dateStart > dateEnd) {
        setStatusMsg('Data od musi być wcześniejsza niż data do.', 'error'); return;
    }

    setImportBusy(true);
    clearLog();
    hideResult();
    setStatusMsg('Uruchamiam import...', 'info');

    let importId;
    try {
        const resp = await fetch('/api/import/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date_start: dateStart, date_end: dateEnd, dry_run: dryRun }),
        });
        if (resp.status === 409) {
            setStatusMsg('Import już trwa — poczekaj na zakończenie.', 'error');
            setImportBusy(false); return;
        }
        if (!resp.ok) {
            const d = await resp.json().catch(() => ({}));
            setStatusMsg(d.error || 'Błąd uruchamiania importu.', 'error');
            setImportBusy(false); return;
        }
        const data = await resp.json();
        importId = data.import_id;
        setStatusMsg(`Import #${importId} — trwa...`, 'info');
    } catch (e) {
        setStatusMsg('Błąd połączenia z serwerem.', 'error');
        setImportBusy(false); return;
    }

    // Open SSE stream
    if (activeEventSource) activeEventSource.close();
    activeEventSource = new EventSource(`/api/import/${importId}/stream`);

    activeEventSource.onmessage = function (evt) {
        let event;
        try { event = JSON.parse(evt.data); } catch { return; }
        handleImportEvent(event, importId);
    };

    activeEventSource.onerror = function () {
        appendLog('[WARN] Połączenie SSE przerwane — czekam na reconnect...', 'warning');
    };
});
```

**SSE event handler:**

```javascript
function handleImportEvent(event, importId) {
    if (event.type === 'log') {
        appendLog(event.message, event.level || 'info');
    } else if (event.type === 'progress') {
        setStatusMsg(
            `Wstawiono: ${event.inserted} | Pominięto: ${event.skipped} | Błędy: ${event.errors}`,
            'info'
        );
    } else if (event.type === 'done') {
        activeEventSource.close();
        activeEventSource = null;
        setImportBusy(false);

        const ok = event.status === 'completed';
        setStatusMsg(ok ? 'Import zakończony.' : `Import zakończony ze statusem: ${event.status}`, ok ? 'success' : 'error');
        showResult(event.stats || {}, event.error_message);
        appendLog(`— Koniec (${event.status}) —`, ok ? 'info' : 'error');

        setTimeout(loadHistory, 1000);
    }
}
```

**History table:**

```javascript
async function loadHistory() {
    const tbody = document.getElementById('history-tbody');
    const placeholder = document.getElementById('history-placeholder');

    try {
        const resp = await fetch('/api/import/history');
        const data = await resp.json();

        if (!data.history || data.history.length === 0) {
            placeholder.querySelector('td').textContent = 'Brak historii importów.';
            return;
        }

        placeholder.remove();
        tbody.innerHTML = '';

        data.history.forEach(function (row) {
            const statusBadge = {
                completed: '<span class="px-2 py-0.5 rounded-full bg-green-800 text-green-200 text-xs">Ukończony</span>',
                running:   '<span class="px-2 py-0.5 rounded-full bg-blue-800 text-blue-200 text-xs">W toku</span>',
                failed:    '<span class="px-2 py-0.5 rounded-full bg-red-800 text-red-200 text-xs">Błąd</span>',
                cancelled: '<span class="px-2 py-0.5 rounded-full bg-gray-700 text-gray-300 text-xs">Anulowany</span>',
            }[row.status] || `<span class="text-xs">${row.status}</span>`;

            const started = row.started_at
                ? new Date(row.started_at).toLocaleString('pl-PL', {dateStyle:'short',timeStyle:'short'})
                : '—';

            const range = (row.date_range_start && row.date_range_end)
                ? `${row.date_range_start.slice(0,10)} → ${row.date_range_end.slice(0,10)}`
                : '—';

            let duration = '—';
            if (row.started_at && row.finished_at) {
                const ms = new Date(row.finished_at) - new Date(row.started_at);
                duration = ms < 60000 ? `${Math.round(ms / 1000)}s` : `${Math.round(ms / 60000)}m`;
            }

            const s = row.stats || {};
            const tr = document.createElement('tr');
            tr.style.borderTop = '1px solid var(--card-border)';
            tr.innerHTML = `
                <td class="py-2 pr-3 text-xs" style="color:var(--text-primary)">${started}</td>
                <td class="py-2 pr-3 text-xs" style="color:var(--text-secondary)">${range}</td>
                <td class="py-2 pr-3 text-xs" style="color:var(--text-secondary)">${row.triggered_by_name || '—'}</td>
                <td class="py-2 pr-3">${statusBadge}</td>
                <td class="py-2 pr-3 text-xs text-right" style="color:var(--text-primary)">${s.inserted ?? '—'}</td>
                <td class="py-2 pr-3 text-xs text-right" style="color:var(--text-secondary)">${s.skipped ?? (s.skipped_duplicate ?? '—')}</td>
                <td class="py-2 pr-3 text-xs text-right" style="color:${(s.errors ?? 0) > 0 ? '#f87171' : 'var(--text-secondary)'}">${s.errors ?? '—'}</td>
                <td class="py-2 pr-3 text-xs">${row.dry_run ? '✓' : ''}</td>
                <td class="py-2 text-xs text-right" style="color:var(--text-secondary)">${duration}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        if (placeholder) placeholder.querySelector('td').textContent = 'Błąd ładowania historii.';
    }
}
```

**Helper functions:**

```javascript
function setImportBusy(busy) {
    const btn = document.getElementById('import-btn');
    const spinner = document.getElementById('import-spinner');
    btn.disabled = busy;
    busy ? spinner.classList.remove('hidden') : spinner.classList.add('hidden');
}

function setStatusMsg(msg, level) {
    const el = document.getElementById('import-status-msg');
    const colours = { info: 'var(--text-secondary)', error: '#f87171', success: '#4ade80' };
    el.textContent = msg;
    el.style.color = colours[level] || colours.info;
}

function clearLog() {
    document.getElementById('log-panel').innerHTML =
        '<span style="color:#4b5563">— Start importu —</span>\n';
}

function appendLog(msg, level) {
    const panel = document.getElementById('log-panel');
    const colour = { info: '#4ade80', warning: '#facc15', error: '#f87171', progress: '#67e8f9' }[level] || '#4ade80';
    const span = document.createElement('span');
    span.style.color = colour;
    span.textContent = msg + '\n';
    panel.appendChild(span);
    panel.scrollTop = panel.scrollHeight;
}

function hideResult() {
    document.getElementById('result-card').classList.add('hidden');
}

function showResult(stats, errorMsg) {
    const card = document.getElementById('result-card');
    const statsEl = document.getElementById('result-stats');
    const errEl = document.getElementById('result-error');

    const metrics = [
        { label: 'Wstawiono',  value: stats.inserted  ?? 0, colour: '#4ade80' },
        { label: 'Duplikaty',  value: stats.skipped_duplicate ?? 0, colour: '#facc15' },
        { label: 'Pominięto',  value: (stats.skipped_zero ?? 0) + (stats.skipped_no_client ?? 0) + (stats.skipped_no_employee ?? 0), colour: '#94a3b8' },
        { label: 'Błędy',      value: stats.errors    ?? 0, colour: '#f87171' },
    ];

    statsEl.innerHTML = metrics.map(m => `
        <div class="text-center rounded-lg p-3" style="background:var(--card-bg-deep)">
            <div class="text-2xl font-bold" style="color:${m.colour}">${m.value}</div>
            <div class="text-xs mt-1" style="color:var(--text-secondary)">${m.label}</div>
        </div>
    `).join('');

    if (errorMsg) {
        errEl.textContent = `Błąd: ${errorMsg}`;
        errEl.classList.remove('hidden');
    } else {
        errEl.classList.add('hidden');
    }

    card.classList.remove('hidden');
}
```

**Full `<script>` block placement** — append to the `{% block content %}` in `templates/data_import/index.html`, just before the closing `</div>` of the outer container.

---

## Decision Log

### Native EventSource (No Polyfill) (ADR-10-01)

**Date:** 2026-05-20
**Status:** Accepted

**Context:** The `EventSource` API is natively supported in all modern browsers (Chrome 6+, Firefox 6+, Edge 79+). A polyfill would add ~8KB to the page.

**Decision:** Use native `EventSource`. The admin page is an internal tool — browser compatibility is not a concern.

**Consequences:**
- **Positive:** Zero extra JS dependencies.
- **Negative:** IE11 is unsupported (fine — IE11 is end-of-life).

### Inline JS (No Separate File) (ADR-10-02)

**Date:** 2026-05-20
**Status:** Accepted

**Context:** The codebase uses inline JS in most templates (`calendar.html`, `sms.html`, etc.). There is no webpack/bundler — JS files in `static/` are loaded via plain `<script src>` tags with no build step.

**Decision:** Inline JS in the template. Matches project convention. No new static files needed.

**Consequences:**
- **Positive:** Consistent with codebase. Easy to find and edit alongside the template.
- **Negative:** Not cacheable separately. Acceptable for a low-traffic admin page.

### Local Date for Input Defaults (ADR-10-03)

**Date:** 2026-05-20
**Status:** Accepted

**Context:** The global date-formatting rule (`.claude/rules/date-formatting.md`) warns: `new Date('YYYY-MM-DD')` parses as UTC midnight, which shifts back a day in western timezones. The date range inputs must show the correct local date by default.

**Decision:** Compute defaults by calling `new Date()` (local time) and formatting with `getFullYear()`, `getMonth() + 1`, `getDate()` — NOT by calling `.toISOString().slice(0,10)` (which returns UTC date).

**Consequences:**
- **Positive:** Correct "today" in all timezones.
- **Negative:** None.

---

## Implementation Steps

### Step 0: Test Definition

Functional tests for JS behaviour require either Playwright E2E tests or JSDOM. For this phase, rely on manual testing (admin-only feature, low test ROI for pure JS):

- [ ] Manual: page loads → dates filled with 90-day range
- [ ] Manual: session badge shows correct colour
- [ ] Manual: click Importuj → SSE stream fills log panel → result card shows
- [ ] Manual: click Odnów sesję on a headless server → manual instructions appear

Add a basic smoke test that doesn't require JS execution:

```python
# tests/routes/test_import_page.py (extend from Phase 09)
def test_import_page_has_script_block(client, login_admin):
    resp = client.get('/import')
    html = resp.data.decode()
    assert 'EventSource' in html, 'SSE client JS not found in template'
    assert 'loadHistory' in html
    assert 'loadSessionStatus' in html
```

### Step 1: Add the `<script>` Block

Append the full JS to `templates/data_import/index.html`:

```html
<script>
// ── Utilities ──────────────────────────────────────────────────────────────
function fmtDate(d) { /* ... */ }
function setImportBusy(busy) { /* ... */ }
function setStatusMsg(msg, level) { /* ... */ }
function clearLog() { /* ... */ }
function appendLog(msg, level) { /* ... */ }
function hideResult() { /* ... */ }
function showResult(stats, errorMsg) { /* ... */ }

// ── API calls ───────────────────────────────────────────────────────────────
async function loadSessionStatus() { /* ... */ }
async function loadHistory() { /* ... */ }

// ── SSE event handler ───────────────────────────────────────────────────────
let activeEventSource = null;
function handleImportEvent(event, importId) { /* ... */ }

// ── Event listeners ─────────────────────────────────────────────────────────
document.getElementById('reconnect-btn').addEventListener('click', ...);
document.getElementById('import-btn').addEventListener('click', ...);

// ── Init ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    // Set date defaults
    const today = new Date();
    const ninetyDaysAgo = new Date(today);
    ninetyDaysAgo.setDate(today.getDate() - 90);
    document.getElementById('date-start').value = fmtDate(ninetyDaysAgo);
    document.getElementById('date-end').value   = fmtDate(today);

    // Load async data
    loadSessionStatus();
    loadHistory();
});
</script>
```

Use the full function bodies from the Requirements section above.

### Step 2: Verify End-to-End

- [ ] Open `/import` — dates auto-filled, session badge populated
- [ ] Trigger import with a small date range — log lines stream in, result card appears
- [ ] Reload page — history table shows the just-completed import
- [ ] Run `pytest tests/routes/test_import_page.py -v` — all pass

---

## Verifiable Acceptance Criteria

**Critical Path:**

- [ ] Page loads: dates pre-filled with today − 90 days → today
- [ ] Session badge shows correct status within 1s of page load
- [ ] Clicking "Importuj" with valid dates → SSE log fills in real time
- [ ] `done` event → result card appears, import button re-enabled
- [ ] History table populated on load, refreshes 1s after import completes
- [ ] Reconnect button: 503 → manual instruction shown; 200 → badge updates
- [ ] Import button disabled while import is running (prevents double-submit)
- [ ] Date validation: empty dates → error message; start > end → error message

**Quality:**

- [ ] No `console.error` in browser DevTools during a normal import flow
- [ ] Log panel auto-scrolls to bottom as lines arrive
- [ ] `activeEventSource.close()` called on `done` event (no dangling connections)

---

## Quality Assurance

### Review Checklist

- [ ] Date defaults use local `getFullYear()/getMonth()/getDate()` — NOT `.toISOString().slice(0,10)`
- [ ] `EventSource` is closed on `done` and on reconnect
- [ ] `setImportBusy(false)` called in all error paths (no permanently-disabled button)
- [ ] `fetch` calls include `credentials: 'same-origin'` is implicit (same-origin `fetch` sends cookies by default — no explicit header needed for Flask session auth)
- [ ] History date strings formatted via `toLocaleString('pl-PL')` — not raw ISO

---

## Dependencies

### Upstream

- **Phase 09** — template element IDs
- **Phase 06** — `/api/import/<id>/stream` SSE endpoint
- **Phase 07** — `/api/import/session-status`, `/api/import/reconnect-session`
- **Phase 08** — `/api/import/start`, `/api/import/history`

### Downstream

- None. This is the final phase.

---

## Completion Gate

### Sign-off

- [ ] Full end-to-end import flow confirmed in browser
- [ ] Session reconnect flow confirmed (or 503 path confirmed on headless)
- [ ] History table populates and refreshes correctly
- [ ] `pytest tests/` — all passing, no regressions
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(import): phase 10 — frontend SSE client + UI wiring`

---

## Notes

### Technical Considerations

- `fetch` in a same-origin Flask app sends session cookies automatically — no CSRF token needed for these endpoints because they're session-authenticated, not form-submitted. If the app adds CSRF protection via Flask-WTF in the future, `fetch` calls must include the CSRF token header.
- The `EventSource` object reconnects automatically on network errors (per the SSE spec). Calling `.close()` explicitly prevents unwanted reconnects after a `done` event.
- `panel.scrollTop = panel.scrollHeight` after each `appendLog()` call is correct for auto-scroll. It must be called after the DOM update — which it is, since `appendChild` is synchronous.

### Known Limitations

- No event replay on SSE reconnect (missed events during a brief disconnect are lost). The result card always shows the final stats, so the user knows the outcome.
- History table doesn't auto-refresh during a running import (only refreshes once on `done`). The user can manually reload the page to see an in-progress import in history.

### Future Enhancements

- Add a "Zatrzymaj" (stop) button that calls a `POST /api/import/<id>/cancel` endpoint (not in scope for this plan — requires a cancellation flag on `IMPORT_RUNNER`).
- WebSocket upgrade for bidirectional progress reporting (not needed — SSE is sufficient for read-only streams).
- Notification badge on the sidebar "Import danych" link when an import is in progress.

---

**Previous:** [[phase-09-import-template|Phase 09: Import Page Template + Sidebar Link]]

---

*This is the final phase. All 10 phases complete the Caldis.pl Playwright Import feature.*
