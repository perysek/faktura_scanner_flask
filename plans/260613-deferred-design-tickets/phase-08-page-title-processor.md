---
title: "Phase 08: page_title context processor"
description: "Auto-populate the mobile header title per route via a request.endpoint→label map exposed from the existing inject_globals() context processor; explicit per-page mobile_title blocks still win."
skill: "postgres-expert"
status: pending
group: "navigation"
dependencies: []
tags: [phase, navigation, flask, python, tests]
created: 2026-06-13
updated: 2026-06-13
---

# Phase 08: page_title context processor

**Context:** [[plan|Master Plan]] | **Dependencies:** none | **Status:** Pending

---

## Overview

T5 (kept per user decision 1). Only 7 of ~70 base-extending pages define
`{% block mobile_title %}`; the rest show an empty mobile header. This phase adds a
`request.endpoint → Polish label` map exposed as `page_title` and makes the
`base.html` mobile-title default to it, so every routed page gets a header for free
while the 7 explicit blocks (and any future ones) still override. This is the plan's
only Python-touching phase.

**Goal:** Every authenticated route shows a correct mobile header title; explicit
blocks still win; pytest covers the mapping; CI green.

---

## Context & Workflow

- **Edit:** `app.py` (extend the existing `inject_globals()` at :299–~340),
  `templates/base.html` (mobile-title block default), `tests/` (new test).
- **Server Layer:** the context processor (no DB, no user data — static label dict).
- **Independent** of all other phases.

---

## Prerequisites & Clarifications

### Questions for User
1. **Coverage:** map the main authenticated routes (lists, views, forms, dashboard)?
   Unmapped endpoints fall back to empty (today's behavior).
   - **Assumption:** map the ~40 primary endpoints; unmapped → `''` (no regression).
2. **Label source:** a hand-maintained dict in `app.py` (vs. deriving from
   `<h1 class="page-title">`)?
   - **Assumption:** explicit dict — simplest, testable, no parsing.

---

## Implementation

### Step 0 — Verification
- `pytest` (new test) green locally + CI.
- `/browse` on prod: 3–4 previously-empty pages now show a mobile header; the 7
  explicit-block pages unchanged.

### Step 1 — Extend `inject_globals()` (`app.py`)
- Add a module-level dict, e.g.:
  ```python
  PAGE_TITLES = {
      'main.invoices_list': 'Faktury',
      'main.clients_list': 'Klienci',
      'appointments.list': 'Wizyty',
      # … ~40 primary endpoints
  }
  ```
- In `inject_globals()`, compute `page_title = PAGE_TITLES.get(request.endpoint, '')`
  (import `request` from flask; guard for `request` being None outside a request
  context → return `''`). Add `page_title` to the returned dict.

### Step 2 — `base.html` default
- The mobile-title block currently is `{%- block mobile_title %}{% endblock -%}`.
  Change the default to `{%- block mobile_title %}{{ page_title or '' }}{% endblock -%}`.
- Jinja block override semantics: the 7 pages that define their own
  `{% block mobile_title %}Label{% endblock %}` still win (they replace the default
  body). No change needed to those 7.

### Step 3 — Tests (`tests/`)
- `test_page_title_known_endpoint`: processor/dict returns the right label for a known
  endpoint.
- `test_page_title_unmapped`: returns `''` for an unmapped endpoint.
- `test_page_title_no_request_context`: no crash when called outside a request context.
- Run the full suite + coverage gate (`pytest --cov --cov-fail-under=25`) locally
  before push — CI mirrors it.

### Step 4 — Build (no CSS), deploy, verify per Step 0.

---

## Acceptance Criteria
- [ ] `PAGE_TITLES` map covers the ~40 primary endpoints; `page_title` exposed from
      `inject_globals()`.
- [ ] `base.html` mobile-title defaults to `page_title`; the 7 explicit blocks still
      override.
- [ ] Previously-empty pages show a correct mobile header on prod; explicit-block pages
      unchanged.
- [ ] New pytest passes; full suite + coverage gate green locally and in CI.
- [ ] Committed, pushed, deployed, verified.

## Risks
- Endpoint names must match Flask's actual `request.endpoint` (blueprint.view) — grep
  `routes/*.py` / `url_for(...)` for the real names; a typo yields a silent empty
  header (caught by the per-route spot check).
- Keep the dict free of user data — it's static labels only (no security surface).
