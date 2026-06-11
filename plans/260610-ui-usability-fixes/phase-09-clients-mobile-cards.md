---
title: "Phase 09: Clients Mobile Stacked-Card Layout"
description: "Give clients/list.html a stacked-card layout below ~640px (each row → a labelled card) so the 9-column table is legible on phones without horizontal scrolling (Issue 4, clients-first)."
skill: "web-design-guidelines"
status: pending
group: "clients-table"
dependencies: [P01, P08]
tags: [phase, responsive, mobile, clients]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 09: Clients Mobile Stacked-Card Layout

**Context:** [[plan|Master Plan]] | **Dependencies:** P01, P08 | **Status:** Pending

---

## Overview

The clients table enforces `min-width: 860px` inside an `overflow:auto` container, so on a phone the 9-column table becomes a sideways-scrolling strip showing 2–3 columns and the actions column is off-screen (Issue 4). Per ADR-G-02 (clients-first), this phase adds a CSS-only stacked-card layout below ~640px: the table collapses to `display:block`, the header row hides, and each cell becomes a labelled line via `data-label` + `::before`. The name + actions stay prominent. The pattern is documented so invoices/appointments can adopt it later.

**Goal:** At ≤640px, each client renders as a readable card (label: value per field) with name and actions visible — no horizontal scroll.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** `templates/clients/list.html` — the `{% block extra_css %}` (responsive `@media` block, currently only restacks header/stats at 768px) and `renderClients()` (adds `data-label` to each `<td>`).
- **Server Layer:** None.
- **Database Layer:** None.

### User Workflow

**Trigger:** Mobile user opens the clients list at ≤640px.

**Steps:**
1. Each client row renders as a card: a header line with avatar + name + status, then labelled rows ("Telefon: …", "Ostatnia wizyta: …", "Wizyt: …", etc.), with the action icons in the card.
2. User scans the list vertically; no horizontal scrolling; actions reachable.

**Success Outcome:** The primary "scan the list" task works on a phone.

### Problem Being Solved

**Pain Point:** Issue 4 — mobile users see ~2–3 of 9 columns and must scroll sideways to read one row; actions off-screen.

**Alternative Approach:** Horizontal scroll (current) is slow/error-prone; pinning columns is a weaker interim the user did not choose.

### Integration Points

**Upstream Dependencies:** P01 (zoom fix so any in-card inputs behave), P08 (final `renderClients` markup; this phase only adds `data-label` attributes to it).

**Downstream Consumers:** A future plan applies this documented pattern to invoices/appointments.

**Data Flow:**
```
renderClients() td's gain data-label="Telefon" etc.
@media (max-width:640px): table/thead/tbody/tr/td → block; thead hidden;
   td::before { content: attr(data-label) }  ─▶ card rows
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Breakpoint:** Stacked cards at `≤640px`, normal table above (keeps the desktop/tablet table intact)?
   - **Assumptions if unanswered:** Yes — `max-width: 640px`.
   - **Impact:** A higher breakpoint would card-ify tablets unnecessarily.

2. **Card field set:** Show all 9 fields as labelled rows, or hide low-value ones (e.g. the 6-month trend sparkline) on mobile cards?
   - **Assumptions if unanswered:** Show name+status in the card header; phone, last visit, visits, no-shows, cancelled as labelled rows; render the sparkline compactly or hide it (`display:none` on mobile card) since it's decorative.
   - **Impact:** Too many rows make tall cards; hiding the sparkline keeps cards scannable.

3. **Actions placement:** Keep the action icons as a labelled "Akcje" row, or pin them top-right of the card?
   - **Assumptions if unanswered:** A clear "Akcje" row at the card bottom (simplest, reliable tap targets).
   - **Impact:** Pinning needs absolute positioning; a row is robust.

### Validation Checklist

- [ ] Breakpoint + field set + actions placement confirmed.
- [ ] P08 merged (stable `renderClients` markup).
- [ ] Test at 375px (iPhone SE) and 390px.

> [!CAUTION]
> `renderClients` builds `<td>` strings; add `data-label` to the SAME cells. The first cell (name/avatar) and last (actions) need special card treatment, not a generic label.

---

## Requirements

### Functional

- At ≤640px: table → block cards; `<thead>` hidden; each labelled cell shows "Label: value".
- Name+status form the card header; actions reachable; no horizontal scroll at 375px.
- Above 640px: unchanged table (with `min-width:860px` + horizontal scroll as today).

### Technical

- CSS in `clients/list.html` `{% block extra_css %}`; `data-label` attributes added in `renderClients()`.
- Relax `.refined-table { min-width: 860px }` to `min-width:0` only within the ≤640px media query.
- Use tokens for card borders/spacing.

---

## Decision Log

### CSS-only card-ification via data-label (ADR-09-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Rows are JS-generated; a DOM restructure per breakpoint is brittle.

**Decision:** Keep one `<table>` DOM; at ≤640px restyle to blocks and surface `data-label` via `::before`. Add `data-label` in `renderClients`.

**Consequences:** One render path, responsive via CSS. Slightly verbose `::before` labels, but robust and reusable.

### Sparkline hidden on mobile cards (ADR-09-02)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** The 60×20 sparkline adds little in a stacked card and is decorative.

**Decision:** `display:none` the trend cell at ≤640px (the P08 `aria-label` still serves SR on desktop).

**Consequences:** Shorter cards; trend remains available on larger screens.

---

## Implementation Steps

### Step 0: Define Verification (do first)

- [ ] `/browse` at 375px: assert no horizontal scrollbar on the table container; assert a `<td>` shows its label text via `::before` (e.g. "Telefon"); assert the actions are visible without scrolling.
- [ ] At 1024px: assert the normal table layout (no card transform) is intact.
- [ ] Confirm card assertions FAIL before the change (currently horizontal scroll).

### Step 1: Add `data-label` in `renderClients()`

- [ ] In the row template inside `renderClients()`, add `data-label` to each non-name/non-actions `<td>`:
```js
<td data-label="Telefon">${phone}</td>
<td data-label="Ostatnia wizyta">${lastVisit}</td>
<td data-label="Wizyt"><span class="visit-count">${client.completed_visits || 0}</span></td>
<td data-label="No-shows">${noShowCell}</td>
<td data-label="Odwołał"><span class="visit-count">${client.cancelled_count || 0}</span></td>
<td class="trend-cell" data-label="Trend">${sparklineSvg(clientTrends[client.id])}</td>
<td data-label="Status">${statusBadge}</td>
```
- [ ] Keep the first cell (avatar+name) and the actions cell as-is; mark the name cell `class="cell-name"` and the actions cell `class="cell-actions"` for card-header/footer styling.
- [ ] Apply the same `data-label`s to the skeleton (P08) optionally (or leave skeleton as plain blocks).

### Step 2: Add the ≤640px card CSS

- [ ] In `{% block extra_css %}`, add a new media block (separate from the existing 768px one):
```css
@media (max-width: 640px) {
    .table-container { overflow: visible; border: none; box-shadow: none; background: transparent; }
    .refined-table { min-width: 0; display: block; }
    .refined-table thead { display: none; }
    .refined-table tbody { display: block; }
    .refined-table tbody tr {
        display: block; background: white; border: 1px solid var(--color-border);
        border-radius: 2px; padding: 0.75rem 1rem; margin-bottom: 0.75rem;
        box-shadow: 0 1px 3px rgba(0,0,0,.04);
    }
    .refined-table td {
        display: flex; justify-content: space-between; align-items: center;
        gap: 1rem; padding: 0.375rem 0; border: none; white-space: normal;
        text-overflow: clip; overflow: visible;
    }
    .refined-table td::before {
        content: attr(data-label); font-size: 0.6875rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.06em; color: var(--color-ink-subtle);
        flex-shrink: 0;
    }
    /* Name cell = card header (no label, full width) */
    .refined-table td.cell-name { padding-bottom: 0.5rem; margin-bottom: 0.25rem;
        border-bottom: 1px solid var(--color-border-subtle); }
    .refined-table td.cell-name::before { content: none; }
    /* Actions = card footer row */
    .refined-table td.cell-actions { justify-content: flex-end; padding-top: 0.5rem; }
    .refined-table td.cell-actions::before { content: "Akcje"; }
    .refined-table td.cell-actions .action-icons { justify-content: flex-end; }
    /* Hide decorative sparkline on cards */
    .refined-table td.trend-cell { display: none; }
}
```
- [ ] Note: these `--color-*` are page-available (used elsewhere in the file). No build step needed (page `<style>`), but rebuild if you instead promote to `input.css`.

### Step 3: Verify

- [ ] Run Step-0 assertions — all PASS.
- [ ] Visual check at 375/390px: clean cards, name header, actions reachable, no sideways scroll.
- [ ] Desktop/tablet unchanged.

### Step 4: Document the reusable pattern

- [ ] Add a short "Mobile stacked-card table pattern" section to `DESIGN-TOKENS.md` (the data-label + ≤640px recipe) so invoices/appointments can adopt it next.

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] At ≤640px the table renders as labelled cards; no horizontal scroll at 375px.
- [ ] Name+status are the card header; actions reachable.
- [ ] At ≥641px the table is unchanged.

**Quality Gates:**
- [ ] axe 0 critical/serious at mobile width.
- [ ] Tap targets ≥40px for actions.
- [ ] No layout shift / overflow at 360–640px.

**Integration:**
- [ ] `data-label`s don't affect desktop rendering (labels hidden by `::before` only firing in the media query).
- [ ] Compatible with P08's accessible markup (sort still works on desktop).

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Phone scan:** 375px — scroll the list vertically; read a client's phone/last-visit/visits without horizontal scroll.
  - Expected: cards, no h-scroll; Actual: ___
- [ ] **Actions:** Tap view/edit on a card — works, targets adequate.
  - Expected: reachable; Actual: ___
- [ ] **Desktop intact:** 1440px — normal table.
  - Expected: unchanged; Actual: ___

#### Automated Testing
```bash
# /browse: no horizontal overflow at 375px; td::before label present; desktop unaffected
```

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` (file: `templates/clients/list.html`); `/design-review` mobile; 0 critical.
- [ ] **Code Quality:** Media query isolated; `data-label`s consistent.
- [ ] **Security:** `data-label`s are static strings; values still `escapeHtml`'d.
- [ ] **Documentation:** Pattern documented for reuse.
- [ ] **Project Pattern Compliance:** Tokens; responsive via CSS.

---

## Dependencies

### Upstream (Required Before Starting)
- P01 (zoom fix), P08 (final `renderClients` markup).

### Downstream (Will Use This Phase)
- Future plan: invoices/appointments mobile cards via this documented pattern.

### External Services
- None.

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Verification passes (375/390/1440px)
- [ ] Code + design review passed
- [ ] Pattern documented
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(clients): mobile stacked-card table layout (phase 09)`

---

## Notes

### Technical Considerations
- The existing 768px media block (restacks header/stats) stays; this is a separate 640px block for the table only. Keep both.
- `data-label` adds negligible markup; it's inert above 640px.

### Known Limitations
- Only clients adopts the pattern this plan (ADR-G-02). Invoices/appointments still horizontal-scroll until a follow-up.

### Future Enhancements
- Promote the card CSS to a reusable `.responsive-card-table` utility in `input.css` so other tables opt in by adding `data-label`s only.

---

**Previous:** [[phase-08-clients-table-a11y|Phase 08]]
**Next:** [[phase-10-rating-stars-a11y|Phase 10: Accessible read-only star rating]]
