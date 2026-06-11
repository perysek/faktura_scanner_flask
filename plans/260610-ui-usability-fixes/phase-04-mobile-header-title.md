---
title: "Phase 04: Mobile Header Page-Title"
description: "Show the current page title (and small logo) in the header on < lg so collapsed-sidebar mobile users know where they are (Issue 7)."
skill: "none"
status: done
group: "shared-behavior"
dependencies: [P01]
tags: [phase, mobile, orientation, jinja]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 04: Mobile Header Page-Title

**Context:** [[plan|Master Plan]] | **Dependencies:** P01 | **Status:** Pending

---

## Overview

On mobile the sidebar is collapsed, so the header (`base.html` lines ~213–229) shows only a hamburger and optional page actions — no app name, logo, or current-page title. Branding/title live only inside the drawer, so users lose orientation. This phase adds a `{% block mobile_title %}` rendered `lg:hidden` in the header, opts the highest-traffic pages into it, and documents the pattern for new pages. A small logo mark sits beside it.

**Goal:** Mobile users see the current page name in the header without opening the drawer, with zero change to desktop.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** `templates/base.html` header. A new `{% block mobile_title %}` shown only `< lg`. Top pages set it (clients, dashboard, invoices, appointments, sellers, employees, services).
- **Server Layer:** None (uses existing per-page template blocks; no route changes).
- **Database Layer:** None.

### User Workflow

**Trigger:** Mobile user lands on any page with the drawer collapsed.

**Steps:**
1. Header renders a small logo + the page title (e.g. "Klienci") on the left, hamburger to its left, actions on the right.
2. User immediately knows which page they're on.

**Success Outcome:** Orientation restored on mobile; desktop header unchanged.

### Problem Being Solved

**Pain Point:** Issue 7 — no page context in the mobile header.

**Alternative Approach:** Users must open the drawer to confirm location — extra taps.

### Integration Points

**Upstream Dependencies:** P01 (foundation; consistent header typography via tokens).

**Downstream Consumers:** P11 verification confirms coverage; future pages follow the documented pattern.

**Data Flow:**
```
page template: {% block mobile_title %}Klienci{% endblock %}
   └─ base.html header (lg:hidden) renders logo + title
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Source of the title:** A dedicated `{% block mobile_title %}` that pages set (clean, opt-in) vs. deriving from the existing `{% block title %}` (which is "Klienci — {{ app_name }}")?
   - **Assumptions if unanswered:** Dedicated `mobile_title` block — avoids the `— app_name` suffix and lets each page give a short label.
   - **Impact:** Deriving from `title` would show the app-name suffix on mobile.

2. **Logo in header:** Include the small inverted logo mark (`logo_data_uri`, already used in the sidebar) next to the title on mobile?
   - **Assumptions if unanswered:** Yes — small (h-6) logo + title.
   - **Impact:** Branding presence on mobile.

3. **Rollout breadth:** Set `mobile_title` on the 7 high-traffic pages now; document the rest as a follow-up?
   - **Assumptions if unanswered:** Yes — top 7 now (clients, dashboard, invoices `list_refined`, appointments `list`, sellers `list_refined`, employees `list`, services `list`), pattern documented.
   - **Impact:** Pages without it simply show no title on mobile (no regression vs. today).

### Validation Checklist

- [ ] Block-vs-derive decision confirmed.
- [ ] `logo_data_uri` is available in the header context (it is — used by sidebar).
- [ ] Rollout list confirmed.

---

## Requirements

### Functional

- Header shows logo + page title on `< lg`; hidden on `≥ lg`.
- Title comes from `{% block mobile_title %}`; empty block → no title shown.
- Top 7 pages set the block.

### Technical

- Edits in `templates/base.html` + the 7 page templates.
- Use token typography (`.page-subtitle`-like sizing or a small dedicated class).
- No layout shift on desktop.

---

## Decision Log

### Dedicated `mobile_title` block (ADR-04-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Need a short page label on mobile without the `<title>` suffix.

**Decision:** Add `{% block mobile_title %}{% endblock %}`; render `lg:hidden` with a small logo.

**Consequences:** Opt-in; pages without it match today's behavior. Slightly more per-page boilerplate (one line).

---

## Implementation Steps

### Step 0: Define Verification (do first)

- [ ] `/browse` at 390px on `clients/list.html`: assert the header shows text "Klienci" and a logo `img`, and that the same element is `display:none` at 1440px.
- [ ] Assert a page WITHOUT the block (e.g. an error page) renders no broken/empty title element.
- [ ] Confirm assertion FAILS before the change (no title on mobile today).

### Step 1: Add the header title slot in `base.html`

- [ ] In the `<header>` (after the `#sidebar-toggle` button, before the `ml-auto` actions div), insert:
```html
<!-- Mobile page context (Issue 7): logo + current page title, < lg only -->
<div class="lg:hidden flex items-center gap-2 min-w-0">
    {% if logo_data_uri %}
    <img src="{{ logo_data_uri }}" alt="" class="h-6 w-auto object-contain" aria-hidden="true">
    {% endif %}
    <span class="truncate text-sm font-semibold" style="color: var(--color-ink);">
        {% block mobile_title %}{% endblock %}
    </span>
</div>
```
- [ ] Confirm the existing `{% block page_actions %}` (in the `ml-auto` div) still sits right-aligned.

### Step 2: Opt the top 7 pages in

For each of these, add `{% block mobile_title %}…{% endblock %}` near the top (after `{% block title %}`):

- [ ] `templates/clients/list.html` → `Klienci`
- [ ] `templates/dashboard/index.html` → `Koszty` (matches sidebar label)
- [ ] `templates/invoices/list_refined.html` → `Faktury`
- [ ] `templates/appointments/list.html` → `Wizyty`
- [ ] `templates/sellers/list_refined.html` → `Sprzedawcy`
- [ ] `templates/employees/list.html` → `Pracownicy`
- [ ] `templates/services/list.html` → `Usługi`

### Step 3: Verify

- [ ] `/browse` mobile + desktop checks from Step 0 pass.
- [ ] No desktop layout shift (the block is `lg:hidden`).

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] Header shows logo + correct title on the 7 pages at `< lg`.
- [ ] Title element is hidden at `≥ lg`.
- [ ] Pages without the block render no empty/broken element.

**Quality Gates:**
- [ ] Title truncates (no overflow) on narrow screens.
- [ ] axe: image has empty alt + `aria-hidden` (decorative), title is plain text — 0 violations.

**Integration:**
- [ ] Coexists with `page_actions` (both visible, no overlap) at 375px.

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Orientation:** Visit each of the 7 pages on a phone — title visible without opening drawer.
  - Expected: correct label; Actual: ___
- [ ] **Desktop unchanged:** Header identical at 1440px.
  - Expected: no title shown; Actual: ___

#### Automated Testing
```bash
# /browse: title text present at 390px, hidden at 1440px
```

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` + `/design-review` on a mobile viewport; 0 critical.
- [ ] **Code Quality:** One reusable block; minimal per-page addition.
- [ ] **Security:** N/A.
- [ ] **Documentation:** Pattern noted in `DESIGN-TOKENS.md`/design guide (the `mobile_title` convention) — consolidated in P11.
- [ ] **Project Pattern Compliance:** Uses Jinja blocks + tokens; `logo_data_uri` reused.

---

## Dependencies

### Upstream (Required Before Starting)
- P01.

### Downstream (Will Use This Phase)
- New pages adopt `mobile_title`.

### External Services
- None.

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Verification passes
- [ ] Code + design review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(header): mobile page-title for orientation (phase 04)`

---

## Notes

### Technical Considerations
- The logo uses `aria-hidden` + empty `alt` because the adjacent text already names the page; avoids double announcement.

### Known Limitations
- Only 7 pages covered now; the rest show no mobile title until a follow-up sweep (documented).

### Future Enhancements
- A `page_title` context processor could auto-populate the block from the route, removing per-page boilerplate.

---

**Previous:** [[phase-03-status-toast-scroll-lock|Phase 03]]
**Next:** [[phase-05-migrate-form-fields|Phase 05: Migrate form_fields macros to tokens + Cancel link]]
