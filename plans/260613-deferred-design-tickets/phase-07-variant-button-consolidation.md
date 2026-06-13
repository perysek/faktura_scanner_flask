---
title: "Phase 07: VARIANT button consolidation"
description: "Consolidate the 11 base-extending pages' local .refined-btn-* copies into shared global size/density modifiers; keep the 3 standalone auth pages untouched."
skill: "ui-design:design-system-patterns"
status: pending
group: "buttons"
dependencies: [P02, P03]
tags: [phase, design-system, css, cleanup]
created: 2026-06-13
updated: 2026-06-13
---

# Phase 07: VARIANT button consolidation

**Context:** [[plan|Master Plan]] | **Dependencies:** P02, P03 | **Status:** Pending

---

## Overview

T7. The 260610 sweep removed duplicate `.refined-btn-*` blocks from CANON pages but
deliberately kept "VARIANT" pages (deliberate per-page densities) and STANDALONE auth
pages (no output.css). This phase folds the VARIANT copies into shared global
modifiers where they're genuinely the same, leaving true one-offs local. It runs
**after P02/P03** because several VARIANT pages (appointments/list, absences/my,
absences/management, services/categories, formy_zatrudnienia) are rewritten by the
card phases — editing them last avoids collisions.

**Goal:** Common button densities live as global modifiers; redundant local blocks
removed; every button pixel-equivalent (or deliberately improved) vs before.

---

## Context & Workflow

- **Edit:** `static/css/input.css` (extend globals) + the 11 VARIANT templates:
  appointments/{list,create,edit,calendar,calendar_week,calendar_month},
  absences/{my,management}, services/categories/list, employees/formy_zatrudnienia/list,
  auth/profile.
- **DO NOT TOUCH:** auth/login, auth/forgot_password, auth/reset_password (standalone,
  no output.css — their local button CSS is load-bearing).
- **Upstream:** P02, P03 (stabilized the shared pages).

---

## Prerequisites & Clarifications

### Questions for User
1. **One-off variants:** consolidate only buttons used on ≥2 pages, leaving true
   single-page variants local?
   - **Assumption:** yes — consolidating a one-off into a global is churn, not cleanup.

---

## Implementation

### Step 0 — Verification
Before/after screenshots (desktop + 375px) of each of the 11 pages on prod; buttons
must match or be deliberately improved.

### Step 1 — Inventory
For each of the 11 pages, diff its local `.refined-btn-*` block against the global
classes in `input.css`. Classify each delta: density (padding/font-size), color
override, layout addition (block/full-width), or genuine one-off. Note which deltas
recur across pages (those become global modifiers).

### Step 2 — Extend globals
Add the recurring modifiers to `input.css @layer components` (the global
`.refined-btn-sm` already exists — likely additions: a compact `.refined-btn-xs`
density and/or `.refined-btn-block`). Token-driven; rebuild CSS.

### Step 3 — Swap + remove
- Replace each page's local override with the global class + modifier in the markup.
- Delete the now-redundant local `.refined-btn-*` blocks.
- Leave genuine one-offs in place (documented as intentional).

### Step 4 — Build, deploy, verify per Step 0.

---

## Acceptance Criteria
- [ ] Recurring densities exist as global modifiers; CSS builds.
- [ ] Redundant local `.refined-btn-*` blocks removed from the 11 VARIANT pages.
- [ ] The 3 standalone auth pages are untouched.
- [ ] Before/after shows pixel-equivalent (or improved) buttons on all 11 pages,
      desktop + mobile.
- [ ] Committed, pushed, deployed, verified.

## Risks
- Easy to "consolidate" a deliberately-distinct variant into sameness — the
  before/after screenshots are the gate; if a button visibly changes, keep it local.
- Calendar pages share a layout; verify their action buttons together.
