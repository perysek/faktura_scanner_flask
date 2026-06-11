---
title: "Phase 05: Migrate form_fields Macros to Tokens + Cancel Link"
description: "Rewrite the form_fields.html macros onto canonical token-based component classes (flat, 2px, --color-*) and make Cancel a real <a href> (Issue 5-forms + Issue 8)."
skill: "web-design-guidelines"
status: done
group: "design-system-migration"
dependencies: [P01]
tags: [phase, design-system, jinja, accessibility, css]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 05: Migrate form_fields Macros to Tokens + Cancel Link

**Context:** [[plan|Master Plan]] | **Dependencies:** P01 | **Status:** Pending

---

## Overview

`templates/components/form_fields.html` is System A: `input_base_classes` is `… rounded-xl border border-slate-300 focus:ring-2 focus:ring-primary-500 … text-sm …`, and `form_actions` renders a gradient submit button plus a Cancel **button** that navigates via `onclick="window.location.href=…"` (Issue 8). This phase introduces canonical, token-driven form component classes in `input.css` (flat, 2px radius, `--color-*`, focus ring matching `.refined-input`) and rewrites every macro to use them, so forms look identical to the canonical System-B pages. Cancel becomes an `<a href>` styled as a secondary button.

**Goal:** Every form rendered through these macros uses the canonical flat token language, and Cancel is a real link.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** `templates/components/form_fields.html` (all macros) + new `.form-*` classes in `static/css/input.css @layer components`. Affects every create/edit page that imports these macros (clients, sellers, employees, services, invoices, appointments, users, roles, settings).
- **Server Layer:** None — markup/classes only.
- **Database Layer:** None.
- **Integrations:** `npm run build:css` rebuilds; P01 global zoom rule already covers the new inputs at mobile widths.

### User Workflow

**Trigger:** User opens any create/edit form.

**Steps:**
1. Inputs/selects/textareas render flat (2px, token border, token focus ring) — matching the rest of the app.
2. Submit is a flat token-primary button (`--color-ink`); Cancel is a link the user can middle-click / open in a new tab / hover-preview.

**Success Outcome:** Forms stop looking like a different app; Cancel behaves like a link.

### Problem Being Solved

**Pain Point:** Issue 5 (forms half) — divergent affordances; Issue 8 — Cancel can't be middle-clicked/previewed/crawled.

**Alternative Approach:** Leaving macros on System A keeps the two-systems split and the fake-link Cancel.

### Integration Points

**Upstream Dependencies:** P01 (tokens, radius vars, zoom rule).

**Downstream Consumers:** P07 page sweep verifies all form pages; P06 migrates the table macros in parallel style.

**Data Flow:**
```
input.css: .form-input/.form-label/.form-select/.form-btn-* (token-based)
   └─ form_fields.html macros use them ─▶ every create/edit page inherits canonical look
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Class strategy:** Introduce dedicated `.form-*` component classes in `input.css` (token-based) and point macros at them, rather than inlining Tailwind utilities?
   - **Context:** Inlining utilities can't reference `--color-*` cleanly; author classes centralize the canonical look.
   - **Assumptions if unanswered:** Yes — `.form-input`, `.form-label`, `.form-select`, `.form-textarea`, `.form-btn-primary`, `.form-btn-secondary`, `.form-paste-btn`, `.form-card`.
   - **Impact:** Without it, the macros stay forked.

2. **Material Icons in labels/paste:** Keep the small Material icons (paste button, select chevron, error icon) for now, or swap to inline SVG?
   - **Assumptions if unanswered:** Keep Material for this phase (icon-system unification is out of scope here; the table sort icon is handled in P06). Note for a future pass.
   - **Impact:** Mixing icon systems lingers but doesn't block consistency of inputs/buttons.

3. **`form_section`/`form_card` radius:** Flatten `rounded-2xl` card to `--radius-md` (3px) flat card?
   - **Assumptions if unanswered:** Yes — `.form-card` flat, matching `.refined-card`-style.
   - **Impact:** Visual consistency with System B cards.

### Validation Checklist

- [ ] Class strategy confirmed.
- [ ] P01 merged (radius tokens + zoom rule live).
- [ ] List of form pages to spot-check identified (see Downstream).

> [!CAUTION]
> Changing `input_base_classes` ripples to EVERY field on EVERY form. Verify a representative create page and edit page before declaring done; full sweep is P07.

---

## Requirements

### Functional

- All macro-rendered inputs/selects/textareas/checkboxes use canonical flat token styling.
- Submit button = token-primary (flat `--color-ink`); Cancel = `<a href="{{ cancel_url }}">` styled secondary.
- Paste buttons, select chevrons, currency input, readonly field, error/helper text all migrated.
- No `rounded-xl`/`rounded-2xl`/`from-primary-` left in `form_fields.html`.

### Technical

- New classes in `input.css @layer components` consuming `--color-*`, `--radius-sm/md`, `--ease-*`.
- Focus ring matches `.refined-input` (`border-color: var(--color-ink-muted); box-shadow: 0 0 0 3px rgba(26,26,26,.04)`).
- Mobile font-size handled by P01 global rule (do not re-add `text-sm` that would drop below 16px on mobile — the global rule overrides, but keep desktop 14px via the class).
- Rebuild + commit `output.css`.

---

## Decision Log

### Token-based `.form-*` component classes (ADR-05-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Macros used Tailwind utilities (`rounded-xl`, `slate-*`, gradient) — can't consume `--color-*`.

**Decision:** Define `.form-*` author classes in `input.css` mirroring the canonical `.refined-input`/`.refined-btn-*` (flat token) language; macros reference them.

**Consequences:**
- **Positive:** One canonical implementation; future tweaks in one place.
- **Negative:** New class names to learn (documented in DESIGN-TOKENS.md).
- **Neutral:** `.refined-btn-*` global gradient/flat conflict (input.css:463 vs clients/list.html:106) is reconciled separately in P07 — `.form-btn-*` are independent so P05 isn't blocked on it.

### Cancel as `<a href>` (ADR-05-02)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Issue 8 — Cancel was `<button onclick=location>`.

**Decision:** Render `<a href="{{ cancel_url }}" class="form-btn-secondary">`; keep label/`role` semantics natural.

**Consequences:** Middle-click/new-tab/hover-preview work; crawlable. No JS needed.

---

## Implementation Steps

### Step 0: Define Verification (do first)

- [ ] Pick reference pages: `templates/clients/create.html` (create) + `templates/clients/edit.html` (edit) — confirm they import `form_fields` macros.
- [ ] `/browse` baseline screenshots (before) of both at 1440px + 390px.
- [ ] Assertions: after migration, computed `border-radius` of a `.form-input` = 2px; Cancel is an `<a>` with a real `href`; submit background = `rgb(26,26,26)`.
- [ ] axe baseline (must stay ≥ parity).

### Step 1: Add canonical form component classes to `input.css`

- [ ] In `@layer components`, add (consuming tokens + P01 radii):
```css
/* ── Canonical form controls (token-based; P05 migration of form_fields macros) ── */
.form-label {
    display: block; font-size: 0.8125rem; font-weight: 500;
    color: var(--color-ink-muted); margin-bottom: 0.375rem;
}
.form-input, .form-select, .form-textarea {
    width: 100%; padding: 0.5rem 0.75rem;
    font-family: var(--font-body); font-size: 0.875rem; font-weight: 400;
    color: var(--color-ink); background: white;
    border: 1px solid var(--color-border); border-radius: var(--radius-sm);
    transition: border-color 0.2s ease, box-shadow 0.2s ease; outline: none;
}
.form-input::placeholder, .form-textarea::placeholder { color: var(--color-ink-subtle); }
.form-input:focus, .form-select:focus, .form-textarea:focus {
    border-color: var(--color-ink-muted); box-shadow: 0 0 0 3px rgba(26,26,26,.04);
}
.form-input:disabled, .form-input[readonly] { background: var(--color-surface); cursor: not-allowed; }
.form-select { appearance: none; cursor: pointer; padding-right: 2.5rem; }
.form-card {
    background: white; border: 1px solid var(--color-border);
    border-radius: var(--radius-md); padding: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.form-btn-primary {
    display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem;
    padding: 0.625rem 1.25rem; font-size: 0.875rem; font-weight: 500;
    color: white; background: var(--color-ink); border: none; border-radius: var(--radius-sm);
    cursor: pointer; transition: all 0.25s var(--ease-out-expo); text-decoration: none;
}
.form-btn-primary:hover { background: var(--color-ink-muted); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,.15); }
.form-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
.form-btn-secondary {
    display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem;
    padding: 0.625rem 1.25rem; font-size: 0.875rem; font-weight: 500;
    color: var(--color-ink-muted); background: white;
    border: 1px solid var(--color-border); border-radius: var(--radius-sm);
    cursor: pointer; transition: all 0.2s ease; text-decoration: none;
}
.form-btn-secondary:hover { border-color: var(--color-ink-muted); background: var(--color-surface); }
.form-paste-btn {
    display: inline-flex; align-items: center; justify-content: center; padding: 0.5rem;
    color: var(--color-ink-subtle); background: var(--color-surface);
    border: 1px solid var(--color-border); border-radius: var(--radius-sm);
    cursor: pointer; flex-shrink: 0; transition: color 0.2s ease, background 0.2s ease;
}
.form-paste-btn:hover { color: var(--color-ink); background: white; }
```
- [ ] `npm run build:css`; confirm classes present in `output.css`.

### Step 2: Rewrite the macros

In `templates/components/form_fields.html`:

- [ ] Replace the top-of-file `{% set %}` blocks:
```jinja
{% set input_base_classes = 'form-input' %}
{% set label_classes = 'form-label' %}
{% set paste_btn_classes = 'form-paste-btn btn-press' %}
```
- [ ] `text_input` / `number_input` / `date_input` / `textarea_input`: the inputs already use `{{ input_base_classes }}` — now resolves to `.form-input`. Drop `text-sm`/`rounded-xl` remnants and the readonly `bg-slate-50` (handled by `.form-input[readonly]`). For `textarea_input`, add `.form-textarea` alongside (or set its base to `form-textarea` + resize class).
- [ ] `select_input` / `currency_input` selects: use `.form-select` (keep the Material chevron overlay div; reposition for `padding-right: 2.5rem`).
- [ ] `checkbox_input`: keep checkbox sizing but swap `text-primary-600 focus:ring-primary-500` ring to token focus (rely on global `:focus-visible`); label → `.form-label`-ish or keep small.
- [ ] `form_section`: change wrapper `bg-white rounded-2xl shadow-sm border border-slate-200 p-6` → `form-card animate-fade-up`; keep the grid + title (swap `text-primary-500` icon to token color if desired).
- [ ] `form_actions`: 
  - Submit → `<button type="submit" class="form-btn-primary btn-press" {…loading…}>` (drop gradient utilities).
  - **Cancel (Issue 8)** → replace the `<button onclick="window.location.href=…">` with:
```jinja
{% if cancel_url %}
<a href="{{ cancel_url }}" class="form-btn-secondary btn-press">{{ cancel_label }}</a>
{% endif %}
```
- [ ] `readonly_field`: wrapper → flat token (`.form-input`-like read style or keep, but swap `rounded-xl bg-slate-50` to token surface + `--radius-sm`).
- [ ] `field_error` / `field_helper`: swap `text-red-600`→`var(--color-error)` and `text-slate-500`→`var(--color-ink-subtle)` (inline style or small classes).

### Step 3: Rebuild + verify on reference pages

- [ ] `npm run build:css`.
- [ ] `/browse` after-screenshots of `clients/create.html` + `clients/edit.html`; compare to Step-0 baseline — flat token look, no broken layout.
- [ ] Confirm Cancel is `<a href>` (DevTools), middle-click opens new tab.
- [ ] `git grep -n "rounded-xl\|rounded-2xl\|from-primary-\|slate-300" templates/components/form_fields.html` → no matches.

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] Inputs/selects/textareas render flat token style (2px, token border/focus).
- [ ] Submit = flat `--color-ink`; Cancel = `<a href>` secondary.
- [ ] No System-A utilities (`rounded-xl`, `from-primary-`, `slate-300`) remain in `form_fields.html`.

**Quality Gates:**
- [ ] Mobile inputs ≥16px (P01 rule holds with new classes).
- [ ] axe parity or better on reference create/edit pages.
- [ ] No console errors; forms still submit.

**Integration:**
- [ ] A page using `form_section` + `form_actions` (e.g. clients/create) looks consistent with `clients/list.html`.

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Visual parity:** Open clients/create + an invoices/create form — inputs/buttons match the refined pages.
  - Expected: one language; Actual: ___
- [ ] **Cancel link:** Middle-click Cancel → opens target in new tab; hover shows URL.
  - Expected: real link; Actual: ___
- [ ] **Submit:** Form still posts; loading state shows.
  - Expected: works; Actual: ___

#### Automated Testing
```bash
npm run build:css
git grep -n "rounded-xl\|rounded-2xl\|from-primary-" templates/components/form_fields.html   # expect empty
# /browse: .form-input border-radius == 2px; Cancel is <a>[href]
```

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` (files: `templates/components/form_fields.html`, `static/css/input.css`, `static/css/output.css`); `/design-review` before/after; 0 critical.
- [ ] **Code Quality:** Macros DRY; classes centralized.
- [ ] **Error Handling:** Required/maxlength/pattern attrs preserved.
- [ ] **Security:** Field values still rendered via Jinja autoescape; no raw HTML.
- [ ] **Documentation:** `.form-*` classes added to `DESIGN-TOKENS.md`.
- [ ] **Project Pattern Compliance:** Token classes + build pipeline; `asset_url()` untouched.

---

## Dependencies

### Upstream (Required Before Starting)
- P01 (tokens, radii, zoom rule).

### Downstream (Will Use This Phase)
- P06 (table macros, same approach), P07 (page sweep verifies all forms).

### External Services
- None.

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Verification passes (reference pages)
- [ ] Code + design review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `style(forms): migrate form_fields macros to canonical tokens + cancel link (phase 05)`

---

## Notes

### Technical Considerations
- Keep `btn-press` (already in `input.css`) on buttons for the tactile press feedback the app uses everywhere.
- The global `:focus-visible` ring (input.css) covers keyboard focus; component focus styles cover all focus — both coexist by cascade.

### Known Limitations
- Material Icons remain in form labels/paste/error for now; full icon unification is a separate future pass.
- The `.refined-btn-*` global gradient/flat duplication is intentionally deferred to P07.

### Future Enhancements
- Convert form icons to inline SVG to drop the Material Icons font dependency.

---

**Previous:** [[phase-04-mobile-header-title|Phase 04]]
**Next:** [[phase-06-migrate-table-macros|Phase 06: Migrate table macros + accessible sortable header]]
