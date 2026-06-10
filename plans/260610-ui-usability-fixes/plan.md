---
title: "UI Usability & Design-System Fixes — Master Plan"
description: "Fix the 15 usability/a11y issues from design review templates_20260609_220245 and unify the two divergent design systems onto one canonical token set."
status: pending
priority: P1
tags: [ui, accessibility, design-system, responsive, planning]
created: 2026-06-10
updated: 2026-06-10
---

# UI Usability & Design-System Fixes — Master Plan

## Executive Summary

**The Mission:** Resolve all 15 issues raised in design review `templates_20260609_220245.md` — the keyboard/screen-reader, mobile-responsive, and consistency defects that multiply across ~70 pages because they live in shared foundation code — and collapse the app's **two parallel design systems** into one canonical token-driven language.

**The Big Shift:** Today the app runs **two visual languages side by side**:
- **System A (Tailwind macros):** `templates/components/form_fields.html`, `templates/components/scrollable_table.html` — `rounded-xl`/`rounded-2xl`, `slate-*`/`primary-*` utilities, gradient buttons, Material Icons.
- **System B ("refined" tokens):** `templates/clients/list.html`, `*list_refined.html`, `templates/dashboard/index.html`, and the `@layer components` block in `static/css/input.css` — `--color-ink`, 2px radii, flat semantic fills, glyph icons.

The canonical token system (`:root` in `static/css/input.css`) **already exists and is already consumed by System B**. This plan ratifies System B as canonical and **migrates the System-A macros (and the pages that depend on them) onto the same tokens**, so identical actions look and behave the same on every page — and a single fix (e.g. the iOS input-zoom rule) applies everywhere at once.

> [!NOTE]
> User decisions captured at plan kickoff (2026-06-10):
> 1. **Issue 5 (design system):** **Full migration** — make System-A macros consume the canonical tokens and sweep dependent pages. Not a doc-only/cheap unify.
> 2. **Issue 4 (mobile tables):** **Clients-first** — build the stacked-card responsive pattern on `clients/list.html` only; invoices/appointments adopt it in a later plan.

**Primary Deliverables:**

1. **Design Foundation:** One documented canonical token set + an app-wide mobile input-zoom fix (Issue 2), both in `static/css/input.css`.
2. **Shared-Behaviour A11y:** Accessible mobile sidebar (Issue 3), a well-behaved status-toast poller (Issue 6), a mobile page-title header (Issue 7), modal/sidebar scroll-lock (Suggestion 1), accordion resize-safety (Suggestion 2).
3. **Design-System Migration:** Token-migrated `form_fields.html` + `scrollable_table.html` macros (Issue 5), accessible Cancel-as-link (Issue 8), accessible + icon-unified sortable headers (Issue 1 macro-half, Suggestion 3), and a page sweep that proves visual consistency.
4. **Clients Table:** Keyboard/SR-accessible sorting (Issue 1 clients-half), skeleton loading (Issue 9), accessible sparkline (Issue 11), error-state focus management (Issue 12), and a mobile stacked-card layout (Issue 4).
5. **Public-Page A11y:** Accessible read-only star rating (Issue 10).
6. **Verification:** App-wide accessibility + responsive regression pass.

---

## Issue → Phase Coverage Map

Every one of the 15 issues (6 Major, 6 Minor, 3 Suggestions) is mapped to exactly one owning phase. Where an issue has two independent implementations in two files, it is split and noted.

| # | Issue (severity) | Owning Phase(s) |
|---|------------------|-----------------|
| 1 | Sort keyboard/SR-inaccessible (Major) | **P06** (macro `sortable_header`) + **P08** (clients `sortBy`) |
| 2 | iOS input auto-zoom <16px (Major) | **P01** (global rule, both systems) |
| 3 | Mobile sidebar ARIA/focus/scroll (Major) | **P02** |
| 4 | Tables horizontal-scroll only on mobile (Major) | **P09** (clients only, per decision) |
| 5 | Two divergent design systems (Major) | **P01 → P05 → P06 → P07** |
| 6 | Status-toast poller undismissable/background (Major) | **P03** |
| 7 | No page context in mobile header (Minor) | **P04** |
| 8 | Cancel is `<button onclick=location>` not link (Minor) | **P05** |
| 9 | Clients uses text loading not skeleton (Minor) | **P08** |
| 10 | Read-only star rating no accessible value (Minor) | **P10** |
| 11 | Sparkline trend color-only (Minor) | **P08** |
| 12 | Error/retry states don't move focus (Minor) | **P08** |
| S1 | Lock body scroll behind overlays (Suggestion) | **P03** |
| S2 | Accordion resize handler (Suggestion) | **P02** |
| S3 | Standardize sort-icon vocabulary (Suggestion) | **P01** (token) + **P06** (apply) |

---

## Phasing Strategy (Roadmap)

We follow a **shared-foundation-first** strategy: fixes that live in shared code are done first so each one improves every page at once, the canonical tokens are established before any migration consumes them, and visual-language changes happen on a stable a11y base. This mirrors the review's own "Next Steps" ordering.

### Phase Constraints

- **Size:** 10–15KB max per phase document; each phase = a single implementation session.
- **Scope:** One concern per phase; file-ownership kept inside one group to avoid cross-group edit collisions.
- **Dependencies:** Explicit in each phase header.
- **Review gate:** Every phase ends with the project's review tooling — `/code-review` (and `/design-review` for visual phases) — plus a CSS rebuild and a live `/browse` check before DONE.

### Phase File Naming

- Pattern: `phase-NN-descriptive-slug.md` — flat sequential numbering, no sub-phases.

### Phase Table

| Phase  | Title | Group | Focus | Status |
| :----- | :---- | :---- | :---- | :----- |
| **01** | [Canonical tokens + mobile input-zoom fix](./phase-01-design-tokens-foundation.md) | design-foundation | Tokens of record + Issue 2 + S3 token | **DONE** |
| **02** | [Mobile sidebar a11y + accordion resize](./phase-02-mobile-sidebar-a11y.md) | shared-behavior | Issue 3 + S2 | Pending |
| **03** | [Status-toast poller + overlay scroll-lock](./phase-03-status-toast-scroll-lock.md) | shared-behavior | Issue 6 + S1 | Pending |
| **04** | [Mobile header page-title](./phase-04-mobile-header-title.md) | shared-behavior | Issue 7 | Pending |
| **05** | [Migrate form_fields macros to tokens + Cancel link](./phase-05-migrate-form-fields.md) | design-system-migration | Issue 5 (forms) + Issue 8 | Pending |
| **06** | [Migrate table macros + accessible sortable header](./phase-06-migrate-table-macros.md) | design-system-migration | Issue 5 (tables) + Issue 1 (macro) + S3 | Pending |
| **07** | [Page-sweep migration & consistency verification](./phase-07-page-sweep-consistency.md) | design-system-migration | Issue 5 (pages) | Pending |
| **08** | [Clients table a11y & polish](./phase-08-clients-table-a11y.md) | clients-table | Issues 1(clients), 9, 11, 12 | Pending |
| **09** | [Clients mobile stacked-card layout](./phase-09-clients-mobile-cards.md) | clients-table | Issue 4 | Pending |
| **10** | [Accessible read-only star rating](./phase-10-rating-stars-a11y.md) | public-a11y | Issue 10 | Pending |
| **11** | [App-wide a11y/responsive verification + docs](./phase-11-verification-docs.md) | verification | Regression + sign-off | Pending |

### Group Summary

Groups define audit boundaries — connected phases are reviewed together after the group completes. Ordered so dependencies flow top-to-bottom.

| Group | Phases | Description |
|-------|--------|-------------|
| **design-foundation** | P01 | Ratify & document the canonical token set; add the app-wide mobile input-zoom rule and the shared sort-icon token. Everything downstream consumes this. |
| **shared-behavior** | P02–P04 | Behaviour/a11y fixes in non-macro shared code (`base.html`, `sidebar.html`): sidebar drawer, toast poller, mobile header. Independent of visual language, so safe to do before the macro migration. |
| **design-system-migration** | P05–P07 | The big one. Migrate the System-A macros onto canonical tokens, fold in the macro-side sort a11y + Cancel-link + icon unification, then sweep dependent pages and prove consistency. |
| **clients-table** | P08–P09 | All `clients/list.html`-local work: keyboard/SR sort, skeleton, sparkline a11y, error focus, and the mobile stacked-card pattern. Isolated to one page → its own group. |
| **public-a11y** | P10 | Standalone public `appointment_rate.html` (no `base.html`): accessible read-only stars. Single-phase group. |
| **verification** | P11 | Cross-cutting axe/Playwright + `/design-review` + `/qa` regression pass, plus documentation updates. Depends on every prior group. |

**Group ordering rationale:** `design-foundation` must precede everything (tokens + global rules are consumed downstream). `shared-behavior` is independent of visual language and touches files the migration does **not** rewrite, so it slots in safely before the migration. `design-system-migration` rewrites the macros and must own them exclusively. `clients-table` and `public-a11y` touch page-local files only. `verification` is last by definition.

---

## Architectural North Star

**Purpose:** Immutable patterns every phase must follow. This is a **Flask + Jinja2 + TailwindCSS** project — there is no React/Next.js, no Supabase, no server actions. Do not introduce them.

### 1. One Canonical Token System

- **Core Principle:** Colour, radius, spacing, and typography come from the CSS custom properties in `static/css/input.css :root` (the `--color-*`, `--font-*`, `--ease-*`, `--sidebar-*` tokens). The "refined" `@layer components` classes are the reference implementation.
- **Enforcement:** No new `slate-*`/`primary-*` gradient buttons, no `rounded-xl`/`rounded-2xl` on migrated components. Flat fills, 2px radii, token colours. After migration, `git grep "rounded-xl"` in migrated files must return nothing.

### 2. CSS Build Pipeline Is Source-of-Truth

- **Core Principle:** `static/css/input.css` is the **only** editable stylesheet. `static/css/output.css` is a generated, minified artifact — never hand-edit it.
- **Enforcement:** After any `input.css` change (or any new utility class used in templates/JS), run `npm run build:css`. `asset_url()` re-hashes `output.css` automatically for cache-busting. Tailwind's `content` scan covers `./templates/**/*.html` and `./static/js/**/*.js`, so any class string referenced from an inline `<script>` or `.js` file is JIT-detected — but verify it survived the build.

### 3. Progressive-Enhancement Accessibility

- **Core Principle:** Keyboard and screen-reader parity for every interaction. Real semantic elements (`<button>`, `<a href>`) over `<th onclick>`/`<button onclick=location>`. State reflected in ARIA (`aria-sort`, `aria-expanded`, `aria-current`), not in glyphs/colour alone.
- **Enforcement:** Each interactive phase verifies with keyboard-only navigation and an axe/Playwright pass. `prefers-reduced-motion` (already respected for toasts/sidebar) must not regress.

### 4. Don't Break What Works

- **Core Principle:** Preserve the genuinely good foundation the review praised — skip-to-content link, automatic CSRF `fetch`/XHR shim, `prefers-reduced-motion` handling, `aria-label`+`title` on icon buttons, local-time date parsing, and the empty/skeleton macros.
- **Enforcement:** Regression checks in P11 confirm none of the "Positive Observations" regressed.

---

## Project Framework Alignment

Deviating from established project patterns causes inconsistency and maintenance burden. This codebase's real conventions:

### Component Usage Priority

1. **First:** Existing Jinja macros (`components/form_fields.html`, `components/scrollable_table.html`) and the `@layer components` classes (`.refined-*`, `.modal-*`, `.page-title`, `.stat-*`).
2. **Second:** Canonical tokens via inline `style="…var(--color-…)"` for page-local one-offs (the System-B pattern).
3. **Last resort:** New bespoke CSS — and if added, it goes in `input.css`, token-driven.

### Required Patterns

| Task | Pattern |
|------|---------|
| Route / page | Flask blueprint route → `render_template(...)`; auth via `@login_required` + `@module_permission_required(...)` |
| Template | Extend `base.html`; use `{% block extra_css %}` / `{% block extra_scripts %}` / `{% block page_actions %}` |
| Styling | Canonical tokens in `static/css/input.css`; rebuild with `npm run build:css` |
| Asset refs | `{{ asset_url('css/output.css') }}` / `{{ asset_url('js/foo.js') }}` — never hardcode paths (content-hash cache busting) |
| Icons | Material Icons (legacy, being phased toward inline SVG) or inline SVG; unify per Suggestion 3 |
| Tables (macro) | `components/scrollable_table.html` macros (`table_card`, `sortable_header`, `empty_state`, `loading_skeleton`) |
| Forms (macro) | `components/form_fields.html` macros (`text_input`, `select_input`, `form_actions`, …) |
| Client JS | Plain ES5/ES6 in `static/js/*.js` or inline `<script>`; `fetch` (CSRF auto-injected); `Modals.confirm(...)`, `showToast(...)` helpers |
| CSRF | Automatic via the `<head>` shim in `base.html` — do not add manual tokens to `fetch` calls |

### Testing Reality

There is **no JS unit-test runner** (`package.json` has only Tailwind). Python `pytest` exists under `tests/` but these changes are template/CSS/JS with no Python logic. Therefore the **test strategy for this plan is verification-based, not unit-TDD**:

- **Primary:** Playwright (installed in `.venv`) and the gstack `/browse` daemon for live keyboard/responsive/visual checks, plus axe-core for automated a11y.
- **Secondary:** Manual keyboard-only + mobile-viewport walkthroughs against per-phase checklists.
- **Python `pytest`** only where a phase touches a Flask route/helper (e.g. a new `page_title` context value) — most phases will not.

> [!NOTE]
> Each phase's "Step 0" is therefore **"Define verification"** (write the Playwright/axe assertions and the manual checklist *first*), not "write failing unit tests." This is the project-appropriate adaptation of the template's TDD step.

---

## Global Decision Log (Project ADRs)

### ADR-G-01 — Canonical design system = System B ("refined" tokens)

**Status:** Accepted (user decision, 2026-06-10)

**Context:** Two design systems coexist (Issue 5). One must win to stop per-page re-learning and double-maintenance.

**Decision:** System B (token-driven "refined" language: `--color-*`, 2px radii, flat fills) is canonical. The System-A Tailwind macros migrate onto it. Full migration including a page sweep.

**Consequences:** Macros and ~70 dependent pages shift visual language (flat vs. gradient/rounded). Requires before/after visual verification. Long-term: one fix applies everywhere.

### ADR-G-02 — Mobile table strategy = clients-first stacked cards

**Status:** Accepted (user decision, 2026-06-10)

**Context:** Data tables only horizontal-scroll on mobile (Issue 4). Stacked-card layout is real work; review named clients/invoices/appointments as top 3.

**Decision:** Build the reusable stacked-card pattern on `clients/list.html` only this plan. Invoices/appointments adopt it later.

**Consequences:** One proven pattern shipped; other tables still scroll horizontally until a follow-up plan. P09 must document the pattern so reuse is mechanical.

### ADR-G-03 — Verification-based testing (no JS unit runner)

**Status:** Accepted

**Context:** No JS test framework configured; changes are presentational.

**Decision:** Use Playwright + `/browse` + axe + manual checklists as the acceptance mechanism; `pytest` only for the rare Python-touching phase.

**Consequences:** "Tests-first" means "assertions/checklist-first." CI has no JS test job to gate on; the per-phase `/browse` + `/design-review` gate substitutes.

---

## Security Requirements

These are presentational changes with a **low security surface**, but the existing protections must not regress:

- **CSRF:** The `base.html` `fetch`/XHR shim auto-injects `X-CSRFToken`. Do not bypass it or add a second token path.
- **XSS:** All dynamic table cells in `clients/list.html` go through `escapeHtml(...)`. Any new dynamically-rendered content (skeletons, card labels, sparkline titles) must use the same escaping or static template text — never interpolate raw API strings into `innerHTML`.
- **No secrets / no new endpoints:** This plan adds no env vars, no routes that return sensitive data. The status-events poller (P03) already exists; we only change its client-side cadence/UX.
- **Error messages:** Keep client error text generic (the existing "Błąd połączenia z serwerem" style); do not surface internal stack details.

---

## Implementation Standards

### Global Verification Strategy

- **A11y:** axe-core 0 critical/serious violations on every touched page; keyboard-only operability for sort, sidebar, forms, retry buttons; SR announces sort state, menu state, ratings.
- **Responsive:** No iOS-zoom on focus at ≤1023px; clients table readable as cards at ≤640px; no horizontal page scroll at 375px on touched pages.
- **Visual:** `/design-review` before/after screenshots show one consistent language; no orphaned System-A styling on migrated pages.
- **Build:** `npm run build:css` succeeds; `output.css` re-hashes; no console errors on load.

### Global Documentation Standard

Update after the relevant phases (consolidated in P11):

1. `CLAUDE.md` — note the canonical design system + the "edit `input.css`, never `output.css`, rebuild" rule.
2. `flask-jinja2-gui-design-guide.md` (the project's referenced design guide) — record the canonical tokens, the macro patterns post-migration, and the mobile-card table pattern.
3. `plans/260610-ui-usability-fixes/DESIGN-TOKENS.md` — created in P01 as the tokens-of-record artifact.

---

## Success Metrics & Quality Gates

### Project Success Metrics

- **WCAG 2.1 AA**: 0 axe critical/serious violations on the 7 reviewed representative pages + all migrated macro pages.
- **Zero iOS-zoom**: no viewport zoom on input focus at mobile widths, app-wide.
- **One design language**: a reviewer cannot tell "which page am I on" from button/inputs/sort affordances; `git grep "rounded-xl\|rounded-2xl\|from-primary-"` returns nothing in `components/form_fields.html` and `components/scrollable_table.html`.
- **Mobile clients table**: 9-column data legible without horizontal scrolling at 375px.

### Global Quality Gates (Pre-Release)

- [ ] All 15 review issues closed and verified against their owning phase's acceptance criteria.
- [ ] `npm run build:css` clean; no hand-edits to `output.css`.
- [ ] axe pass on every touched page (0 critical/serious).
- [ ] Keyboard-only walkthrough of sort, sidebar, forms, ratings passes.
- [ ] `/design-review` confirms consistency; no regressions to the review's "Positive Observations."
- [ ] Docs (`CLAUDE.md`, design guide, `DESIGN-TOKENS.md`) updated.

---

## Resources & References

- **Design review (source of work):** `.ui-design/reviews/templates_20260609_220245.md`
- **Token source:** `static/css/input.css` (`:root` + `@layer components`)
- **Build:** `package.json` scripts `build:css` / `watch:css`; config `tailwind.config.js`
- **Reference canonical page:** `templates/clients/list.html`, `templates/dashboard/index.html`, `templates/invoices/list_refined.html`
- **Macros to migrate:** `templates/components/form_fields.html`, `templates/components/scrollable_table.html`
- **Project design guide:** `flask-jinja2-gui-design-guide.md`
- **Review/QA tooling:** `/code-review`, `/design-review`, `/qa`, `/browse` (gstack)

---

**Next:** [[phase-01-design-tokens-foundation|Phase 01: Canonical tokens + mobile input-zoom fix]]
