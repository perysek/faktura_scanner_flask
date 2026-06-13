---
title: "Phase 06: Material Icons page sweep + font removal"
description: "Convert every remaining Material Icons usage across 25 templates and 4 JS files to the P05 inline-SVG system, then remove the Google-Fonts icon link and leftover .material-icons CSS."
skill: "ui-design:create-component"
status: pending
group: "icons"
dependencies: [P05]
tags: [phase, icons, design-system, performance]
created: 2026-06-13
updated: 2026-06-13
---

# Phase 06: Material Icons page sweep + font removal

**Context:** [[plan|Master Plan]] | **Dependencies:** P05 | **Status:** Pending

---

## Overview

T3, part 2. With the inline-SVG system live (P05), sweep the remaining ~163 template
usages (25 templates) + ~43 JS usages (4 files) and convert them to `icon()` /
`Icons.svg()`. When the codebase is `material-icons`-free, remove the render-blocking
Google-Fonts icon `<link>` (base.html:75) and any leftover `.material-icons` CSS. This
is the widest-touch phase — **single phase per user decision 3, committed in 2–3
bisectable batches**.

**Goal:** Zero `material-icons` references; no tofu/ligature artifacts on any page; the
fonts.googleapis.com icon request gone from the network log.

---

## Context & Workflow

- **Templates (25):** clients/view, appointments/{view,edit,create,list},
  absences/{my,management,balances}, clients/{list,create,edit}, services/{view,edit,
  list,create}, employees/{view,list,edit,create}, income/dashboard, settings/sms,
  components/{scrollable_table,form_fields}, invoices/upload, base.html (font link).
- **JS (4 live):** `invoices/upload.js` (12), `sellers/{list,edit,create}.js`.
  (`invoices/list.js` + `upload_original.js.bak` were deleted in P04.)
- **Edit:** base.html:75 (font link), input.css (`.material-icons` rules if any).
- **Upstream:** P05 (icon system).

---

## Implementation

### Step 0 — Verification
Build a route checklist from the file list; after each batch deploys, `/browse` every
affected route on prod, scan for raw ligature text / tofu squares, axe each.

### Step 1 — Scripted sweep (MANDATORY safety rails)
Convert `<span class="material-icons {extra}">name</span>`:
- Templates → `{{ icon('name', class='{extra}') }}` (import the macro at top of each
  template: `{% from 'components/icons.html' import icon %}`).
- JS template literals → `Icons.svg('name', '{extra}')`.

**Safety rails (the \x01 incident — non-negotiable):**
1. Use replacement **functions**, never string backreferences.
2. After every scripted edit: `grep -rn $'[\x00-\x08]'` the touched files (zero hits).
3. `node --check` every touched inline `<script>` block (strip Jinja first) and every
   touched `.js` file.
4. Render-test: every touched route returns HTTP 200 on prod.

### Step 2 — Styled-icon cases
- Carried classes (`empty-icon`, `toast-icon`, `sort-icon`, etc.) move onto the SVG via
  the macro/helper `class` param.
- Any `.material-icons` selectors in page-local `<style>` blocks → retarget to `.icon`
  or the specific carried class.
- Icons inside buttons that have `aria-label`/`title` stay `aria-hidden` (default).

### Step 3 — Batched commits (2–3, bisectable)
Suggested batches: **(A)** invoices/upload + sellers JS + components macros; **(B)**
appointments + absences; **(C)** clients + services + employees + income + settings.
Deploy + verify each batch before the next.

### Step 4 — Font removal (only when grep is clean)
- `grep -rn "material-icons" templates static/js` must return **0**.
- Remove the icon `<link href="…Material+Icons">` at base.html:75.
- Remove any remaining `.material-icons` CSS (base.html toast rules were already
  retargeted in P05; double-check none linger).
- Deploy; confirm the fonts.googleapis.com icon request is gone (network log in
  `/browse`); full visual sweep.

---

## Acceptance Criteria
- [ ] `grep material-icons templates static/js` = 0.
- [ ] All 25 templates + 4 JS files render icons as inline SVG; no tofu/ligature text on
      any route (per-route check, not sampled).
- [ ] Font `<link>` removed; no fonts.googleapis.com icon request; leftover
      `.material-icons` CSS gone.
- [ ] axe clean on touched pages; no console errors.
- [ ] 2–3 batched commits, each pushed + deployed + verified on prod.

## Risks
- Widest blast radius in the plan — verification must be **per-route**. The batched
  commits make a bad conversion bisectable.
- A glyph name used in markup but missing from the P05 macro map renders an empty
  `<svg>` → add the path to `icons.html` and rebuild. Cross-check the inventory (62
  names) is fully populated before sweeping.
- Watch `scrollable_table.html`/`form_fields.html` — they're dead macros (zero
  consumers) but still converted for consistency; don't spend verification budget
  hunting their non-existent live pages.
