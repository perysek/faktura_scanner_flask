---
title: "Phase 09: Full regression verification + docs closeout"
description: "App-wide axe/responsive regression pass on production, grep gates for the cleanups (icons, table-utils, radii, CI guard), and documentation closeout (DESIGN-TOKENS.md, CLAUDE.md, memory)."
skill: "qa"
status: pending
group: "verification"
dependencies: [P01, P02, P03, P04, P05, P06, P07, P08]
tags: [phase, verification, accessibility, docs]
created: 2026-06-13
updated: 2026-06-13
---

# Phase 09: Full regression verification + docs closeout

**Context:** [[plan|Master Plan]] | **Dependencies:** all prior phases | **Status:** Pending

---

## Overview

The gate. Verify on production that all 8 tickets (+ the 13-table mobile mandate) are
closed and nothing regressed, then document the closeout. No new feature work — this
phase proves the plan and updates the records so the next session inherits accurate
state.

**Goal:** Production passes the a11y + responsive + grep gates; DESIGN-TOKENS.md,
CLAUDE.md, and project memory reflect the resolved state.

---

## Context & Workflow

- **Verify:** production `http://70.34.252.120` via `/browse` + axe-core.
- **Edit (docs):** `plans/260610-ui-usability-fixes/DESIGN-TOKENS.md`, `CLAUDE.md`,
  `~/.claude/.../memory/project_design_system_state.md` + `MEMORY.md`.
- **Depends on:** every prior phase.

---

## Implementation

### Step 1 — Accessibility pass (prod, axe-core)
On dashboard, clients, invoices, appointments, sellers, employees, users, roles,
services, services/categories, absences/{management,balances,my}, employee view,
formy_zatrudnienia: **0 critical/serious**. Specifically assert gone:
`empty-table-header` (invoices), `heading-order` + `region` (appointments).

### Step 2 — Responsive pass (prod, 375px)
All **13 tables** card-render (labelled cards, no horizontal scroll); no input zoom on
focus; no horizontal page scroll. Spot-check desktop (≥1024px) unchanged on a sample.

### Step 3 — Grep gates
- `grep -rn "material-icons" templates static/js` → **0**.
- `grep -rn "table-utils" templates static` → **0**.
- `grep -rnE "border-radius:\s*[23]px" static/css/input.css` → **0** (outside the
  `--radius-*` token definitions).
- CI design-guard job is **green** on the latest push; confirm it still fails on a
  seeded violation if in doubt.
- `grep -rn "stack-cards" templates` → 13 tables (+ clients) all opted in.

### Step 4 — Docs closeout
- **DESIGN-TOKENS.md:** rewrite "Deferred items" → "Resolved (260613 plan)" with
  per-ticket disposition; add the `.stack-cards` component to the documented patterns
  (replacing the per-page recipe note); record the inline-SVG icon system.
- **CLAUDE.md** "Design system" section: add the icon rule ("icons = inline SVG via the
  `icon()` macro / `Icons.svg()` — never the Material Icons font"); add the
  `.stack-cards` mobile-table recipe; remove any stale `table-utils`/Material-Icons
  references.
- **Memory:** update `project_design_system_state.md` (shared `.stack-cards` component;
  table-utils deleted; icons inline-SVG; 13 tables carded) and the `MEMORY.md` index.

### Step 5 — Final commit + deploy + smoke test
Docs commit, push, deploy, one final `/browse` smoke pass.

---

## Acceptance Criteria
- [ ] axe 0 critical/serious on all listed pages; the 3 named violations gone.
- [ ] All 13 tables card-render at 375px; no h-scroll; no input zoom; desktop unchanged.
- [ ] All grep gates pass; CI guard green.
- [ ] DESIGN-TOKENS.md + CLAUDE.md + memory updated to the resolved state.
- [ ] Final docs commit pushed + deployed; production smoke pass clean.

## Risks
- A late regression in one table (e.g. a colspan empty-state breaking the card layout)
  surfaces here — fix in the owning phase's file area, re-verify, don't band-aid in P09.
- Keep the production verification read-only: minted session cookie, no DB writes, never
  submit the public rating form.
