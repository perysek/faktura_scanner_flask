---
title: "Phase 01: Canonical Tokens + Mobile Input-Zoom Fix"
description: "Ratify and document the canonical CSS token set, add the app-wide mobile input-zoom rule (Issue 2), and formalize the shared sort-icon convention (S3)."
skill: "web-design-guidelines"
status: done
group: "design-foundation"
dependencies: []
tags: [phase, css, design-system, accessibility, responsive]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 01: Canonical Tokens + Mobile Input-Zoom Fix

**Context:** [[plan|Master Plan]] | **Dependencies:** None | **Status:** Pending

---

## Overview

This phase establishes the foundation every later phase builds on. The canonical token system already physically exists in `static/css/input.css :root` and is consumed by System B (`clients/list.html`, the `@layer components` "refined" classes). This phase **ratifies it as the system of record**, fills the small gaps the macro migration (P05/P06) will need, ships the single app-wide rule that kills iOS input-zoom on every page (Issue 2), and formalizes one sort-icon convention (Suggestion 3) so P06 has something concrete to apply.

**Goal:** A documented, gap-filled token set + a global `≤1023px → 16px` form-control rule live in `output.css`, with zero visual regression on desktop.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** No template markup changes. A new global CSS rule affects every input/select/textarea/SearchableSelect on mobile widths. A new shared `.th-sort-icon` styling convention is documented for P06/P08 to consume.
- **Server Layer:** None.
- **Database Layer:** None.
- **Integrations:** The Tailwind build (`npm run build:css`) regenerates `output.css`; `asset_url()` re-hashes it for cache-busting.

### User Workflow

**Trigger:** A user on a phone (Safari iOS) taps any text field — search box, a create-client input, the SearchableSelect trigger.

**Steps:**
1. User taps an input with font-size < 16px.
2. **Before:** Safari zooms the viewport in and does not zoom back out, breaking the fixed sidebar/header alignment.
3. **After:** The field is ≥16px at mobile widths, so Safari does not zoom; layout stays put.

**Success Outcome:** Data entry on phones no longer jolts the page into a zoomed state.

### Problem Being Solved

**Pain Point:** Issue 2 — "the single most felt mobile defect": every field below 16px triggers iOS auto-zoom. Also Issue 5's root cause — undocumented, duplicated styling tokens that let pages fork.

**Alternative Approach:** Without a global rule, each of the two design systems would need the zoom fix applied separately (and every future component too). One rule in `@layer base` covers both.

### Integration Points

**Upstream Dependencies:** None — this is the first phase.

**Downstream Consumers:**
- **P05/P06:** Migrate macros to consume these tokens and the `.th-sort-icon` convention.
- **P08/P09:** Clients-page work relies on the zoom fix already being global.

**Data Flow:**
```
static/css/input.css (edit)  ──npm run build:css──▶  static/css/output.css (minified)
        │                                                     │
   :root tokens + @layer base global rule            asset_url() re-hashes ──▶ browser
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Sort-icon vocabulary (S3):** Canonical = the System-B text glyphs (`▲` asc / `▼` desc / dimmed `▲` unsorted) to match `clients/list.html` and avoid the Material Icons dependency?
   - **Context:** The macro currently uses Material `unfold_more`/`expand_less`/`expand_more`; clients uses glyphs.
   - **Assumptions if unanswered:** Standardize on glyphs (matches canonical System B; the app is moving away from Material Icons toward inline SVG).
   - **Impact:** Wrong choice means re-doing icon markup in P06/P08.

2. **Zoom-rule breakpoint:** Use `max-width: 1023px` (matches Tailwind's `lg` boundary used elsewhere, e.g. `lg:hidden` sidebar toggle)?
   - **Context:** The review suggested `max-width: 1023px`.
   - **Assumptions if unanswered:** Yes, `1023px` — keeps 14px on `lg+` where desktop density is wanted.
   - **Impact:** A different breakpoint changes where desktop density resumes.

### Validation Checklist

- [ ] Sort-icon convention confirmed (glyphs).
- [ ] Breakpoint confirmed (`max-width: 1023px`).
- [ ] `npm` available and `npm run build:css` works locally.
- [ ] No other in-flight branch is editing `input.css`.

> [!CAUTION]
> Editing `output.css` by hand instead of `input.css` + rebuild will be silently overwritten on the next build. Always edit `input.css`.

---

## Requirements

### Functional

- All `input`, `select`, `textarea`, `.ss-trigger`, `.ss-search`, `.refined-input` render at ≥16px font-size at viewport ≤1023px.
- Desktop (`≥1024px`) typography is unchanged (14px/13px stays).
- A documented token set exists as the system of record.
- A single shared sort-icon styling convention is defined.

### Technical

- Edits confined to `static/css/input.css` (source) + a new `plans/260610-ui-usability-fixes/DESIGN-TOKENS.md`.
- Rebuild via `npm run build:css`; commit the regenerated `output.css`.
- No new Tailwind config changes required (tokens are CSS custom properties, not theme extensions).

---

## Decision Log

### Glyph sort-icons as canonical (ADR-01-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Two sort-icon vocabularies exist (Material vs. text glyphs). Suggestion 3 wants one.

**Decision:** Canonical sort icon = text glyphs `▲`(asc)/`▼`(desc)/dimmed `▲`(unsorted), exposed via a shared `.th-sort-icon` class already present in `clients/list.html`. Lift its styling into `input.css @layer components` so the macro (P06) reuses it.

**Consequences:**
- **Positive:** No Material Icons dependency for sorting; matches canonical System B; one styled element everywhere.
- **Negative:** Glyphs are slightly less crisp than icon-font; acceptable.
- **Neutral:** P06 swaps the macro's Material icon markup for the glyph span.

**Alternatives Considered:**
1. Material `unfold_more` everywhere — rejected: keeps the icon-font dependency the app is phasing out.

### Global zoom rule in `@layer base` (ADR-01-02)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Issue 2 spans both design systems; per-component fixes would duplicate.

**Decision:** One `@media (max-width:1023px)` rule in `@layer base` targeting form controls + the three custom-control classes.

**Consequences:** One rule, app-wide. Slightly increases mobile field height (acceptable, improves tap targets too).

---

## Implementation Steps

### Step 0: Define Verification (do first)

**Purpose:** Establish how we prove the fix before changing CSS.

- [ ] Write a Playwright check (or `/browse` script) that: loads `templates/clients/create.html` (a form page) at viewport 390×844 (iPhone 12), focuses the first text input, and asserts `getComputedStyle(input).fontSize` is `>= 16px`.
- [ ] Write the same assertion for `clients/list.html` `#search-input` (`.refined-input`) and the SearchableSelect `.ss-trigger` on any page that renders one (e.g. an appointment create page).
- [ ] Manual checklist drafted: desktop visual diff of one form + one refined page (must look unchanged at ≥1024px).

> [!WARNING]
> Confirm the assertions FAIL before the fix (fields read 13–14px) so you know the check is real.

### Step 1: Document the canonical token set

#### 1.1: Create the tokens-of-record artifact

- [ ] Create `plans/260610-ui-usability-fixes/DESIGN-TOKENS.md` listing every `:root` token group already in `input.css` (text/surface/border/brand/semantic/status/chart/star/easing/sidebar) with its value and intended use, plus the radius/font conventions.
- [ ] Mark System B as canonical and reference `clients/list.html` + the `@layer components` `.refined-*` classes as the reference implementation.

#### 1.2: Add the small gaps the macro migration needs

- [ ] In `input.css :root`, add explicit radius tokens so P05/P06 stop hardcoding:
```css
/* Radii — canonical (flat, minimal) */
--radius-sm: 2px;   /* inputs, buttons, badges */
--radius-md: 3px;   /* cards, modals */
```
- [ ] Confirm a flat primary-button colour token exists for buttons: canonical primary fill = `--color-ink` (`#1a1a1a`), hover `--color-ink-muted` (per `.refined-btn-primary` in `clients/list.html`). Document this in DESIGN-TOKENS.md (no new var needed).

### Step 2: Ship the global mobile input-zoom rule

#### 2.1: Add the rule to `@layer base`

- [ ] In `static/css/input.css`, inside `@layer base { ... }` (after the `:focus-visible` block, before the closing brace of the layer), add:
```css
/* ── iOS Safari input-zoom guard (Issue 2) ──
   Any form control under 16px makes mobile Safari zoom the viewport on focus
   and never zoom back. Force ≥16px at mobile widths; desktop keeps its denser
   14px/13px. Covers BOTH design systems + the custom SearchableSelect controls. */
@media (max-width: 1023px) {
    input,
    select,
    textarea,
    .ss-trigger,
    .ss-search,
    .refined-input {
        font-size: 16px;
    }
}
```

#### 2.2: Formalize the shared sort-icon convention (S3)

- [ ] In `input.css @layer components`, add a canonical `.th-sort-icon` rule (lifted from `clients/list.html:198-209`) so both the clients page and the migrated macro share it:
```css
/* Canonical sortable-header glyph icon (S3) — shared by clients list + table macro */
.th-sort-icon {
    display: inline-block;
    margin-left: 0.25rem;
    opacity: 0.35;
    font-size: 0.625rem;
    vertical-align: middle;
    transition: opacity 0.2s ease;
}
.th-sortable:hover .th-sort-icon { opacity: 0.7; }
.th-sortable.sort-active .th-sort-icon { opacity: 1; }
```
- [ ] Leave the page-local copy in `clients/list.html` for now (P08 removes the duplicate once it confirms the shared class is live). Document this hand-off in DESIGN-TOKENS.md.

### Step 3: Rebuild and verify

- [ ] Run `npm run build:css`.
- [ ] Confirm the new `@media` rule and `.th-sort-icon` exist in `static/css/output.css` (grep the minified file).
- [ ] Run the Step-0 Playwright/`/browse` assertions — they must now PASS (≥16px).
- [ ] Desktop visual diff: one form page + `clients/list.html` look unchanged at 1440px.

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] At ≤1023px, every `input`/`select`/`textarea`/`.ss-trigger`/`.ss-search`/`.refined-input` computes to ≥16px font-size.
- [ ] No iOS-zoom on focus (verified on a form page + a refined page).
- [ ] `DESIGN-TOKENS.md` exists and documents the canonical set + sort-icon convention.

**Quality Gates:**
- [ ] Desktop (≥1024px) typography visually identical to pre-change.
- [ ] `output.css` regenerated via build (not hand-edited); new rules present.
- [ ] axe: no new violations introduced on a sampled form + refined page.

**Integration:**
- [ ] `.th-sort-icon` class resolves (computed styles applied) on `clients/list.html` headers.
- [ ] Radius tokens (`--radius-sm/md`) resolve in DevTools.

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Mobile zoom:** Open a form page in Safari iOS (or `/browse` mobile emulation), tap each field type — no zoom. Expected: viewport static.
  - Expected: No zoom; Actual: ___
- [ ] **Desktop unchanged:** Compare before/after screenshots of `clients/create.html` + `clients/list.html` at 1440px.
  - Expected: pixel-identical; Actual: ___

#### Automated Testing
```bash
npm run build:css
# Playwright/browse: assert computed font-size >= 16px at 390px width on form + refined inputs
```

#### Performance Testing
- [ ] `output.css` size delta < 1KB (target), Actual: ___

### Review Checklist

- [ ] **Code Review Gate:**
  - [ ] Run `/code-review plans/260610-ui-usability-fixes/phase-01-design-tokens-foundation.md` (files: `static/css/input.css`, `static/css/output.css`, `DESIGN-TOKENS.md`)
  - [ ] Run `/design-review` on a form page + a refined page (before/after)
  - [ ] Critical findings addressed (0 remaining)
- [ ] **Code Quality:** Edits only in `input.css` + docs; `output.css` is build output.
- [ ] **Error Handling:** N/A (pure CSS).
- [ ] **Security:** N/A.
- [ ] **Documentation:** `DESIGN-TOKENS.md` created; note added to `CLAUDE.md` deferred to P11.
- [ ] **Project Pattern Compliance:** Tokens are CSS custom properties; build via `npm run build:css`; `asset_url()` untouched.

---

## Dependencies

### Upstream (Required Before Starting)
- None.

### Downstream (Will Use This Phase)
- P05/P06: consume radius tokens + `.th-sort-icon`.
- P08/P09: rely on global zoom fix.

### External Services
- Node/npm + Tailwind 3.4 (already in `devDependencies`).

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Verification assertions pass
- [ ] Code + design review passed
- [ ] `DESIGN-TOKENS.md` committed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `style(css): canonical tokens + mobile input-zoom guard (phase 01)`

---

## Notes

### Technical Considerations
- Tailwind JIT only emits utility classes it sees in `content` files. `.th-sort-icon`/`.refined-input` are author CSS in `@layer components`/page `<style>`, so they are always emitted — no purge risk. The zoom rule targets bare element selectors, also always emitted.
- The `16px` value is the iOS threshold exactly; do not drop to 15px.

### Known Limitations
- Bumping mobile fields to 16px slightly increases their height — desirable (bigger tap targets), but verify dense pages (e.g. table search rows) still fit.

### Future Enhancements
- A later pass could convert hardcoded `2px`/`3px` radii throughout `input.css` to the new `--radius-*` tokens (cosmetic; not required this plan).

---

**Previous:** _none_
**Next:** [[phase-02-mobile-sidebar-a11y|Phase 02: Mobile sidebar a11y + accordion resize]]
