---
title: "Phase 04: JS hygiene + radius tokens + CI design-guard"
description: "Delete the dead table-utils.js and orphaned JS, tokenize the 6 hardcoded radii in input.css, and add a CI grep guard that fails on System-A regressions."
skill: "shell-scripting:bash-defensive-patterns"
status: pending
group: "guardrails"
dependencies: []
tags: [phase, cleanup, ci, design-system]
created: 2026-06-13
updated: 2026-06-13
---

# Phase 04: JS hygiene + radius tokens + CI design-guard

**Context:** [[plan|Master Plan]] | **Dependencies:** none | **Status:** Pending

---

## Overview

Three independent hygiene wins (T2, T4, T6). `table-utils.js` is loaded on every page
from `base.html:271` but has **zero live consumers** (ADR-D-02) — deleting it kills
the global-`sortTable` shadowing trap permanently. Six hardcoded radii in `input.css`
become `--radius-*` tokens. And a CI grep step fails the build if System-A debris
(`rounded-xl` etc.) reappears in authenticated templates, locking in the 260610
migration.

**Goal:** Dead JS gone with no behavior change; radii tokenized; CI guard proven to
fail on a seeded violation and pass on clean.

---

## Context & Workflow

- **Files:** `templates/base.html`, `static/js/table-utils.js` (delete),
  `static/js/invoices/list.js` (delete), `static/js/invoices/upload_original.js.bak`
  (delete), `templates/absences/balances.html`, `static/css/input.css`,
  `.github/workflows/ci.yml`.
- **Independent** of all other phases.

---

## Implementation

### Step 0 — Verification plan
- Sort/filter/CSV smoke test on every list page on prod after deploy (zero console
  errors).
- Push a throwaway commit with a seeded `rounded-xl` in a template → CI guard FAILS →
  revert; clean push → CI guard PASSES.

### Step 1 — Remove dead JS (T2 / ADR-D-02)
- Delete `<script src="{{ asset_url('js/table-utils.js') }}"></script>` from
  `base.html:271`.
- Delete files: `static/js/table-utils.js`, `static/js/invoices/list.js`,
  `static/js/invoices/upload_original.js.bak`. (Git history preserves all three.)
- `absences/balances.html:425`: `window.filterTable = function () {…}` →
  `function filterTable() {…}` (the `window.` indirection only existed to beat the now-
  deleted global; the inline `onclick="filterTable()"` still resolves to it).
- **Sweep check:** grep all `templates/**` + `static/js/**` for
  `sortTable|filterTable|initializeTable|applyAllFilters|clearFilters|updateRowCount|parseTableDate|exportToCSV`
  and confirm every remaining hit is page-local (definition + caller in the same file).

### Step 2 — Radius tokens (T4)
- Replace the 6 hardcoded radii in `input.css` (lines 635, 735, 821, 843, 864, 886):
  `2px` → `var(--radius-sm)`, `3px` → `var(--radius-md)`. Pure refactor (identical
  values). Run `npm run build:css`; spot-check the affected components visually.

### Step 3 — CI design-guard (T6)
Add to `.github/workflows/ci.yml` (a fast `guard` job, or a step before pytest):
```yaml
  - name: Design-system guard (no System-A regressions)
    run: |
      if grep -rnE 'rounded-xl|rounded-2xl|from-primary-|to-primary-' templates \
           --include='*.html' \
           --exclude=login.html --exclude=forgot_password.html --exclude=reset_password.html; then
        echo "::error::System-A class reappeared in an authenticated template"; exit 1
      fi
```
- Excludes = the 3 standalone auth pages (never migrated; no output.css). **Verify the
  exclusion list against reality** at implementation time (grep current hits first).
- Prove it: seed a violation, confirm red on GitHub, revert, confirm green.

### Step 4 — Deploy, verify
Deploy (CSS changed → rebuild on server). Smoke-test sort/filter/CSV on prod.

---

## Acceptance Criteria
- [ ] `table-utils.js` + 2 orphans deleted; `base.html` script tag removed; balances
      `filterTable` de-`window.`d.
- [ ] Every list page sorts/filters/exports with zero console errors on prod.
- [ ] 6 radii tokenized; CSS builds; components visually identical.
- [ ] CI guard fails on a seeded violation and passes clean (demonstrated).
- [ ] Committed, pushed, deployed, verified.

## Risks
- If any page secretly relied on a `table-utils.js` function (sweep should catch it),
  restore just that function inline in the page. Verify the sweep grep is exhaustive
  before deleting.
- `grep` exit-code semantics: the step must exit non-zero ONLY on a match — the `if
  grep …; then exit 1` form above is correct (don't use bare `! grep` which can mask
  pipefail under `set -e`).
