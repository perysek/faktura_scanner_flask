---
title: "Phase 08: Clients Table A11y & Polish"
description: "Make clients/list.html sorting keyboard/SR-accessible, replace text loading with a skeleton, give the sparkline a non-color cue + label, and move focus to retry on error (Issues 1-clients, 9, 11, 12)."
skill: "none"
status: pending
group: "clients-table"
dependencies: [P01]
tags: [phase, accessibility, javascript, clients]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 08: Clients Table A11y & Polish

**Context:** [[plan|Master Plan]] | **Dependencies:** P01 | **Status:** Pending

---

## Overview

`templates/clients/list.html` is canonical System B but carries four accessibility/polish gaps, all local to this one file: sortable headers are `<th onclick="sortBy(...)">` with no keyboard/SR semantics (Issue 1, clients half); the initial load shows a plain "Ładowanie klientów..." string instead of a skeleton (Issue 9); the trend sparkline conveys direction by line color alone (Issue 11); and when a fetch fails the injected "Spróbuj ponownie" button doesn't receive focus (Issue 12). This phase fixes all four in `clients/list.html`'s markup + inline script, mirroring the accessible-sort pattern P06 established for the macro.

**Goal:** Clients-page sorting, loading, trend, and error states are fully accessible.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** `templates/clients/list.html` — the `<thead>` headers (lines ~576–605), the inline `<script>` (`sortBy`/`updateSortHeaders` ~726–746, `sparklineSvg`/`trendColor` ~666–696, `loadClients` error branches ~912–935, initial `<tbody>` ~608–615).
- **Server Layer:** None — consumes existing `/api/clients*` endpoints.
- **Database Layer:** None.

### User Workflow

**Trigger:** A keyboard/SR user loads the clients page, sorts, waits for data, hits an error, or reads a trend.

**Steps:**
1. **Sort:** Tab to a header `<button>`, Enter sorts, `aria-sort` flips, SR announces.
2. **Load:** Skeleton rows show while fetching (consistent with other tables).
3. **Trend:** Sparkline has an `aria-label`/`<title>` ("Trend: rosnący") + a tiny ▲/▼/→ glyph — not color-only.
4. **Error:** On failure, focus jumps to the "Spróbuj ponownie" button so keyboard users find it.

**Success Outcome:** The data-heavy clients page is operable and legible without a mouse or color perception.

### Problem Being Solved

**Pain Point:** Issues 1 (clients), 9, 11, 12 — keyboard/SR sort exclusion, inconsistent loading, color-only trend, lost focus on error.

**Alternative Approach:** Without these, the busiest page excludes assistive-tech users from sort + error recovery and fails color-blind users on trend.

### Integration Points

**Upstream Dependencies:** P01 (`.th-sort-icon` now global; `.skeleton` already exists in `input.css`).

**Downstream Consumers:** P09 (mobile cards) builds on the same `renderClients` markup; keep `data-*` hooks compatible.

**Data Flow:**
```
sortBy(field) ─▶ updateSortHeaders() sets aria-sort + glyph
loadClients() start ─▶ skeleton rows ; error ─▶ retry button + focus()
renderClients() ─▶ sparklineSvg() with <title> + trend glyph
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Sort markup:** Mirror P06 — inner `<button>` per sortable `<th>`, `aria-sort` on the `<th>`, glyph via shared `.th-sort-icon`?
   - **Assumptions if unanswered:** Yes — identical pattern to P06 for consistency.
   - **Impact:** Divergent patterns would re-fragment.

2. **Skeleton shape:** Reuse the `.skeleton` shimmer (already in `input.css`) as 5 rows × 9 cells matching the colgroup?
   - **Assumptions if unanswered:** Yes — 5 skeleton rows, 9 cells.
   - **Impact:** Consistency with the macro `loading_skeleton`.

3. **Trend glyph + label:** Add a small ▲ (rosnący) / ▼ (spadkowy) / → (stabilny) next to the sparkline AND an `aria-label`/`<title>` on the SVG?
   - **Assumptions if unanswered:** Yes — both (glyph for sighted color-blind users, label for SR).
   - **Impact:** Without, trend stays color-only.

### Validation Checklist

- [ ] Sort pattern confirmed (matches P06).
- [ ] P01 merged (`.th-sort-icon` global; `.skeleton` available).
- [ ] Polish/pl trend wording confirmed ("rosnący/spadkowy/stabilny").

> [!CAUTION]
> `renderClients()` builds rows as HTML strings via `escapeHtml`. Any new dynamic text (trend label) must go through `escapeHtml` or be static — never raw-interpolate API data into `innerHTML`.

---

## Requirements

### Functional

- Each sortable header is a focusable `<button>`; Enter/Space sorts; `<th aria-sort>` reflects state; SR announces.
- Initial load shows skeleton rows, not a text string.
- Sparkline has a text alternative (`aria-label`/`<title>`) and a non-color direction glyph.
- On fetch error, focus moves to the retry button.

### Technical

- Edits confined to `templates/clients/list.html`.
- Reuse global `.th-sort-icon` (remove page-local duplicate now that P01 provides it).
- Keep `aria-live="polite"` on the table container (already present — good for SR announcement of new content).

---

## Decision Log

### Mirror the P06 sort pattern (ADR-08-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Issue 1 has a clients-local implementation separate from the macro.

**Decision:** Use the same inner-`<button>` + `aria-sort` + glyph pattern as P06; update `updateSortHeaders()` to set `aria-sort` on each `.th-sortable` th.

**Consequences:** One mental model for sorting across the app.

### Trend: glyph + SR label (ADR-08-02)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Sparkline is color-only (Issue 11).

**Decision:** `trendColor` already computes delta; extend to also return a direction key; `sparklineSvg` emits `<title>` + an `aria-label` on the cell and a tiny glyph.

**Consequences:** Accessible to color-blind + SR users; minimal markup.

---

## Implementation Steps

### Step 0: Define Verification (do first)

- [ ] `/browse`: Tab to a clients header → it's a `<button>`; Enter sorts; assert the `<th>` `aria-sort` flips `ascending`/`descending` and others reset to `none`.
- [ ] Throttle/slow the `/api/clients` response (or assert during initial paint) → skeleton rows visible (`.skeleton`), not "Ładowanie klientów...".
- [ ] Assert a sparkline cell has `aria-label` starting "Trend:" and contains a direction glyph.
- [ ] Force an error (mock 500) → assert `document.activeElement` is the retry button.
- [ ] Confirm all four FAIL before the fix.

### Step 1: Accessible sort headers

- [ ] In the `<thead>`, convert each `<th class="th-sortable" onclick="sortBy('X')" id="th-X">` to wrap its label + icon in a real button and add `aria-sort="none"`:
```html
<th class="th-sortable" aria-sort="none" id="th-full_name">
  <button type="button" class="th-sort-btn" onclick="sortBy('full_name')">
    Imię i&nbsp;nazwisko
    <span class="th-sort-icon" id="si-full_name" aria-hidden="true">▲</span>
  </button>
</th>
```
(Repeat for phone, last_visit_date, completed_visits, no_show_count, cancelled_count, is_active.)
- [ ] Update `updateSortHeaders()` to also manage `aria-sort`:
```js
function updateSortHeaders() {
    document.querySelectorAll('.th-sortable').forEach(th => {
        th.classList.remove('sort-active');
        th.setAttribute('aria-sort', 'none');
    });
    const activeEl = document.getElementById(`th-${currentSort.field}`);
    if (activeEl) {
        activeEl.classList.add('sort-active');
        activeEl.setAttribute('aria-sort', currentSort.dir === 'asc' ? 'ascending' : 'descending');
    }
    document.querySelectorAll('.th-sort-icon').forEach(el => el.textContent = '▲');
    const icon = document.getElementById(`si-${currentSort.field}`);
    if (icon) icon.textContent = currentSort.dir === 'asc' ? '▲' : '▼';
}
```
- [ ] Add the `.th-sort-btn` reuse (defined globally in P06's `input.css` addition) — ensure it's in `output.css`. Remove the page-local `.th-sort-icon` CSS block (now global from P01).

### Step 2: Skeleton loading (Issue 9)

- [ ] Replace the initial `<tbody>` placeholder (lines ~608–615) with skeleton rows:
```html
<tbody id="clients-tbody">
  <!-- skeleton injected by renderSkeleton() on load -->
</tbody>
```
- [ ] Add a `renderSkeleton()` helper and call it at the top of `loadClients()` (before the fetch) and on `DOMContentLoaded` before data arrives:
```js
function renderSkeleton(rows = 6) {
    const tbody = document.getElementById('clients-tbody');
    let html = '';
    for (let i = 0; i < rows; i++) {
        html += '<tr>' + Array.from({length: 9}).map(() =>
            '<td><div class="skeleton" style="height:1rem;border-radius:2px;"></div></td>'
        ).join('') + '</tr>';
    }
    tbody.innerHTML = html;
}
```

### Step 3: Accessible sparkline (Issue 11)

- [ ] Extend `trendColor` (or add `trendDirection(weeks)`) to return `'up' | 'down' | 'flat'` from the same delta logic.
- [ ] In `sparklineSvg(months)`, add `<title>` and return a wrapper with `aria-label` + glyph:
```js
function trendDirection(weeks) {
    if (!weeks || weeks.length < 4) return 'flat';
    const half = Math.floor(weeks.length / 2);
    const firstAvg = weeks.slice(0, half).reduce((a,b)=>a+b,0)/half;
    const lastAvg  = weeks.slice(weeks.length-half).reduce((a,b)=>a+b,0)/half;
    const d = lastAvg - firstAvg;
    return d > 0.15 ? 'up' : (d < -0.15 ? 'down' : 'flat');
}
const TREND_LABEL = { up: 'rosnący', down: 'spadkowy', flat: 'stabilny' };
const TREND_GLYPH = { up: '▲', down: '▼', flat: '→' };
```
- [ ] Wrap the SVG so the cell exposes `aria-label="Trend: ${TREND_LABEL[dir]}"` and renders a tiny `<span aria-hidden="true">${TREND_GLYPH[dir]}</span>` beside it; add `<title>Trend: …</title>` inside the `<svg>`. (All static label text — no API interpolation.)

### Step 4: Error focus (Issue 12)

- [ ] In both error branches of `loadClients()` (lines ~912–935), after setting `tbody.innerHTML` with the retry button, give the button an id and focus it:
```js
// after injecting the retry button markup (add id="clients-retry-btn"):
const retry = document.getElementById('clients-retry-btn');
if (retry) retry.focus();
```
- [ ] Ensure the error `<td>` has a heading or the `aria-live="polite"` container announces the message (container already has `aria-live`).

### Step 5: Verify

- [ ] Run Step-0 assertions — all PASS.
- [ ] `npm run build:css` only if any global CSS changed (the `.th-sort-btn`/`.th-sort-icon` should already be global from P01/P06).

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] Sortable headers are focusable buttons; Enter/Space sorts; `aria-sort` reflects state.
- [ ] Skeleton rows show on load (no text string).
- [ ] Sparkline has `aria-label`/`<title>` + a non-color glyph.
- [ ] Focus moves to the retry button on error.

**Quality Gates:**
- [ ] axe 0 critical/serious on `clients/list.html`.
- [ ] No page-local `.th-sort-icon` duplicate (uses global).
- [ ] No XSS: all dynamic strings escaped/static.

**Integration:**
- [ ] `renderClients` markup stays compatible with P09's `data-label` additions.

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Keyboard sort:** Tab + Enter on each header; SR announces column + direction.
  - Expected: operable + announced; Actual: ___
- [ ] **Loading:** Hard refresh → skeleton, not text.
  - Expected: skeleton; Actual: ___
- [ ] **Trend:** Inspect a row with up/down/flat trend → glyph + label correct.
  - Expected: matches data; Actual: ___
- [ ] **Error:** Disconnect API → retry button focused.
  - Expected: focused; Actual: ___

#### Automated Testing
```bash
# /browse: aria-sort toggling, skeleton presence, sparkline aria-label, retry focus
```

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` (file: `templates/clients/list.html`); `/design-review`; 0 critical.
- [ ] **Code Quality:** Helpers small + reused; no duplicated CSS.
- [ ] **Error Handling:** Existing `.catch` + escaped error text preserved.
- [ ] **Security:** `escapeHtml` on any dynamic content; static trend labels.
- [ ] **Documentation:** Note the shared sort pattern in `DESIGN-TOKENS.md`.
- [ ] **Project Pattern Compliance:** Inline ES6 matches file; reuses global tokens.

---

## Dependencies

### Upstream (Required Before Starting)
- P01 (`.th-sort-icon` global, `.skeleton`); P06 provides `.th-sort-btn` globally (or add it here if P06 not yet merged — coordinate).

### Downstream (Will Use This Phase)
- P09 (mobile cards reuse `renderClients`).

### External Services
- Existing `/api/clients`, `/api/clients/visit-trends`, `/api/clients/statistics`.

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Verification passes
- [ ] Code + design review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `fix(clients): accessible sort, skeleton, sparkline a11y, error focus (phase 08)`

---

## Notes

### Technical Considerations
- `.th-sort-btn` must exist globally before this page relies on it. If P06 is sequenced after P08 in practice, add `.th-sort-btn` to `input.css` here instead and note the move.
- The table container already has `aria-live="polite"` — keep it so the new-content/error announcements work.

### Known Limitations
- Sparkline `<title>` tooltips appear on hover only for mouse users; the `aria-label` + glyph cover SR + color-blind users.

### Future Enhancements
- Model the interactive parts as a proper sortable grid (`role="grid"`) if the table grows more interactive.

---

**Previous:** [[phase-07-page-sweep-consistency|Phase 07]]
**Next:** [[phase-09-clients-mobile-cards|Phase 09: Clients mobile stacked-card layout]]
