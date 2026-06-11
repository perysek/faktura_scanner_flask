---
title: "Phase 11: App-Wide A11y/Responsive Verification + Docs"
description: "Cross-cutting axe/Playwright + /design-review + /qa regression pass confirming all 15 issues are closed and no 'Positive Observations' regressed, then update the docs."
skill: "playwright-e2e"
status: done
group: "verification"
dependencies: [P01, P02, P03, P04, P05, P06, P07, P08, P09, P10]
tags: [phase, verification, accessibility, documentation]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 11: App-Wide A11y/Responsive Verification + Docs

**Context:** [[plan|Master Plan]] | **Dependencies:** P01–P10 | **Status:** Pending

---

## Overview

The final gate. Every prior phase verified its own slice; this phase verifies the **whole**: re-runs the design review's representative pages through axe + keyboard + responsive checks, confirms all 15 issues are closed against their owning phase's criteria, confirms none of the review's "Positive Observations" regressed (skip-link, CSRF shim, reduced-motion, icon `aria-label`s, local-time dates, empty/skeleton macros), and updates the documentation so the canonical system and patterns survive into future sessions.

**Goal:** A signed-off, regression-checked, documented closure of `templates_20260609_220245.md`.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** Read-only verification across the 7 representative pages + migrated areas; no new feature code (only doc edits and any small regression fixes found).
- **Server Layer:** None.
- **Database Layer:** None.
- **Integrations:** axe-core, Playwright, gstack `/design-review` + `/qa`.

### User Workflow

**Trigger:** All P01–P10 merged; pre-release gate.

**Steps:**
1. Run the verification matrix (axe + keyboard + responsive) on the representative pages.
2. Tick each of the 15 issues against acceptance criteria.
3. Confirm "Positive Observations" intact.
4. Update docs; raise tickets for any deferred follow-ups (other tables, icon unification, sort-util mismatch).

**Success Outcome:** Reviewer can re-run `/ui-design:design-review` and see the issues resolved.

### Problem Being Solved

**Pain Point:** Per-phase checks miss cross-cutting regressions (e.g. the global button reconciliation breaking a page no single phase owned).

**Alternative Approach:** Shipping without a holistic pass risks a regression slipping through.

### Integration Points

**Upstream Dependencies:** P01–P10 (all).

**Downstream Consumers:** Future plans (invoices/appointments mobile cards; icon unification).

**Data Flow:**
```
representative pages ─▶ axe + keyboard + responsive matrix ─▶ issue checklist ─▶ docs + tickets
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Representative page set:** Verify the review's 7 (base/sidebar/form_fields/scrollable_table via a real page, `clients/list`, `dashboard/index`, `public/appointment_rate`) plus one migrated form + one macro table + one dashboard?
   - **Assumptions if unanswered:** Yes — the review's targets + 3 migration samples.
   - **Impact:** Too narrow misses migration regressions.

2. **Deploy after sign-off:** Auto commit/push and deploy to Vultr after verification (per the standing auto-deploy preference once ≥2 tasks land)?
   - **Context:** Memory: after ≥2 tasks implemented, auto commit+push+deploy to Vultr without confirmation.
   - **Assumptions if unanswered:** Yes — deploy via the `vultr-ssh` skill after the gate passes.
   - **Impact:** Verified work reaches production.

### Validation Checklist

- [ ] Representative page set confirmed.
- [ ] All P01–P10 merged and individually DONE.
- [ ] Deploy decision confirmed.

---

## Requirements

### Functional

- All 15 issues verified closed.
- axe 0 critical/serious on every verified page.
- Keyboard operability: sort, sidebar, forms, ratings, retry.
- Responsive: no iOS-zoom ≤1023px; clients cards ≤640px; no horizontal page scroll at 375px on touched pages.
- "Positive Observations" intact.
- Docs updated.

### Technical

- Use axe + Playwright/`/browse` + `/design-review` + `/qa`.
- Doc edits: `CLAUDE.md`, `flask-jinja2-gui-design-guide.md`, `DESIGN-TOKENS.md`.
- Small regression fixes allowed; large new work → new ticket.

---

## Decision Log

### Holistic gate before deploy (ADR-11-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Cross-phase regressions (esp. the global button reconciliation) aren't visible per-phase.

**Decision:** One app-wide verification pass gates the release + deploy.

**Consequences:** Slight extra time; catches integration regressions.

---

## Implementation Steps

### Step 0: Build the verification matrix (do first)

- [ ] Define the page × check grid:

| Page | axe | Keyboard | Responsive |
|------|-----|----------|------------|
| `clients/list.html` | ☐ | sort + retry | cards ≤640px, no zoom |
| `dashboard/index.html` | ☐ | — | flat buttons, no zoom |
| a migrated create form | ☐ | tab + cancel-link | no zoom |
| a macro table page | ☐ | sort button + aria-sort | — |
| `public/appointment_rate.html` | ☐ | radiogroup | — |
| any page w/ sidebar | ☐ | drawer trap + esc | drawer scroll-lock |

### Step 1: Run the matrix

- [ ] axe-core on each page → 0 critical/serious (record counts).
- [ ] Keyboard-only walkthroughs (record pass/fail).
- [ ] Responsive at 375/390/768/1440px (record).
- [ ] `/design-review` for visual consistency; `/qa` for a dogfood pass of clients + a form + a dashboard.

### Step 2: Issue closure checklist

- [ ] Tick each of the 15 issues against its owning phase's acceptance criteria (use the plan's Issue→Phase map). Record evidence (screenshot / assertion) per issue.

### Step 3: Regression guard — "Positive Observations"

- [ ] Skip-to-content link still works (Tab on load focuses it).
- [ ] CSRF `fetch`/XHR shim still injects (a mutating request carries `X-CSRFToken`).
- [ ] `prefers-reduced-motion` still suppresses toast/sidebar animation.
- [ ] Icon-only buttons still have `aria-label`+`title`.
- [ ] Local-time date parsing intact (no UTC off-by-one on clients dates).
- [ ] Empty/skeleton macros render.

### Step 4: Documentation

- [ ] `CLAUDE.md`: add the canonical design-system note + "edit `input.css`, rebuild with `npm run build:css`, never hand-edit `output.css`" + the `mobile_title` convention.
- [ ] `flask-jinja2-gui-design-guide.md`: record canonical tokens, the migrated macro patterns, the accessible sortable-header pattern, and the mobile stacked-card recipe.
- [ ] `DESIGN-TOKENS.md`: mark migration complete; list deferred items.

### Step 5: Deferred-items tickets

- [ ] Raise tickets for: invoices/appointments mobile cards; full icon-system unification (Material → SVG); `table-utils.js` `sortTable` key/index mismatch; optional `page_title` context processor.

### Step 6 (optional): Deploy

- [ ] If approved: commit/push and deploy via the `vultr-ssh` skill; run post-deploy smoke (`/canary` or a quick `/browse` of the live clients page).

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] All 15 issues verified closed with evidence.
- [ ] axe 0 critical/serious on every verified page.
- [ ] Keyboard operability confirmed for sort/sidebar/forms/ratings/retry.

**Quality Gates:**
- [ ] No iOS-zoom ≤1023px; clients cards ≤640px; no h-scroll at 375px on touched pages.
- [ ] "Positive Observations" all intact.
- [ ] Docs updated; deferred tickets raised.

**Integration:**
- [ ] `/design-review` re-run shows the issues resolved and one consistent language.

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Full keyboard pass:** Navigate clients → sort → error retry → open a form → cancel → open drawer → rate a visit, all keyboard-only.
  - Expected: fully operable; Actual: ___

#### Automated Testing
```bash
npm run build:css   # ensure latest CSS
# axe + Playwright matrix across representative pages
```

#### Performance Testing
- [ ] No background polling while a tab is hidden (re-confirm P03); Actual: ___

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` on any regression fixes; `/design-review` final; `/qa` dogfood; 0 critical.
- [ ] **Documentation:** `CLAUDE.md`, design guide, `DESIGN-TOKENS.md` updated.
- [ ] **Project Pattern Compliance:** Canonical system enforced; build pipeline.

---

## Dependencies

### Upstream (Required Before Starting)
- P01–P10 all DONE.

### Downstream (Will Use This Phase)
- Future plans (deferred items).

### External Services
- axe-core, Playwright, gstack tooling; `vultr-ssh` for deploy.

---

## Completion Gate

### Sign-off
- [ ] All 15 issues verified closed
- [ ] axe/keyboard/responsive matrix passed
- [ ] "Positive Observations" intact
- [ ] Docs updated + deferred tickets raised
- [ ] Plan.md all phases marked DONE
- [ ] Committed: `chore(ui): verify + document UI usability fixes (phase 11)`
- [ ] (Optional) Deployed to Vultr + smoke-checked

---

## Sign-off Record (2026-06-11)

**axe matrix (prod, 70.34.252.120):** clients ✅ 0 / dashboard ✅ 0 / services ✅ 0 /
invoices (minor only) / appointments (moderate only) — **0 critical/serious everywhere**.
Fixed during the gate: sidebar heading contrast token, seller-chip palette, 3 dashboard
scroll regions (tabindex+region), filter label associations, status-dropdown aria-labels,
"6 mies." opacity.

**Keyboard:** sort verified on services/appointments/invoices/employees/sellers/
superadmin/clients (Enter + aria-sort flip); drawer trap + Esc + focus return; rating
radiogroup arrows; error-retry focus. All on production.

**Responsive:** 16px inputs ≤1023px (login + clients verified); clients stacked cards
at 375px with zero horizontal overflow; desktop table intact at 1440px.

**Positive observations intact:** skip-link ("Przejdź do treści" → #main-content),
CSRF meta+patched fetch, prefers-reduced-motion rule in served CSS, action-icon
aria-labels, renderSkeleton present.

**Issue closure:** all 15 review issues closed (Issues 1–12 + S1–S3) across P01–P10;
deferred follow-ups recorded in DESIGN-TOKENS.md "Deferred items".

## Notes

### Technical Considerations
- The global `.refined-btn-*` reconciliation (P07) is the highest cross-page regression risk — give dashboards/analytics extra scrutiny here.

### Known Limitations
- Other data tables (invoices/appointments) remain horizontal-scroll on mobile until a follow-up (ADR-G-02).

### Future Enhancements
- A CI grep guard against re-introducing System-A utilities; a `page_title` context processor; full Material→SVG icon migration.

---

**Previous:** [[phase-10-rating-stars-a11y|Phase 10]]
**Next:** _none — plan complete_
