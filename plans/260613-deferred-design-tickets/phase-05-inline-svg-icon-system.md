---
title: "Phase 05: Inline-SVG icon system + shared-component conversion"
description: "Build a Jinja icon() macro and Icons.svg() JS helper rendering Material Symbols outline paths as inline SVG, and convert the shared infrastructure (toasts, modals, notifications, keyboard shortcuts, ui.js) off the Material Icons font."
skill: "ui-design:create-component"
status: pending
group: "icons"
dependencies: []
tags: [phase, icons, design-system, performance]
created: 2026-06-13
updated: 2026-06-13
---

# Phase 05: Inline-SVG icon system + shared-component conversion

**Context:** [[plan|Master Plan]] | **Dependencies:** none | **Status:** Pending

---

## Overview

T3, part 1. The app renders icons via the Material Icons web-font (62 distinct glyphs,
one render-blocking Google-Fonts request). This phase builds the **replacement
system** — a Jinja macro + a JS helper that emit inline `<svg>` — and converts the
**shared infrastructure** that ships icons from JS (toasts, modals, notifications,
keyboard-shortcut overlay, ui.js). The bulk page sweep + font removal is P06; this
phase must leave the font `<link>` in place (pages still use it until P06).

**Goal:** `icon()` and `Icons.svg()` exist with all needed glyphs; every JS-rendered
icon in shared infra renders as inline SVG at correct size/color; visual parity with
the font; axe clean.

---

## Context & Workflow

- **New:** `templates/components/icons.html` (macro), `static/js/icons.js` (helper).
- **Edit:** `templates/base.html` (load `icons.js`; toast markup + `.toast-*
  .material-icons` color rules :187–190), `static/js/modals.js`,
  `static/js/notifications.js`, `static/js/keyboard-shortcuts.js`, `static/js/ui.js`.
- **Downstream:** P06 consumes this system for the page sweep.

---

## Prerequisites & Clarifications

### Questions for User
1. **Icon set source:** use Material Symbols *outlined* paths (closest to the current
   Material Icons font) so glyphs look the same?
   - **Assumption:** yes — outlined, `viewBox="0 0 24 24"`, `fill="currentColor"`.
2. **Accessibility default:** `aria-hidden="true"` on every icon (all current usages are
   decorative beside text or sit in a button that already has `aria-label`)?
   - **Assumption:** yes; expose an `label` param for the rare standalone-icon case.

---

## Implementation

### Step 0 — Verification
After deploy: `/browse` the toast (trigger all 4 types), confirm modal, keyboard-
shortcut overlay, sidebar; computed `width/height/color` of the SVGs; axe clean.

### Step 1 — `templates/components/icons.html`
```jinja
{% macro icon(name, class='', size=None) -%}
<svg class="icon {{ class }}" viewBox="0 0 24 24" fill="currentColor"
     {% if size %}width="{{ size }}" height="{{ size }}"{% endif %}
     aria-hidden="true" focusable="false"><path d="{{ _ICON_PATHS[name] }}"/></svg>
{%- endmacro %}
```
- Hold the 62 `name → path d` entries in a macro-file-local map (`{% set _ICON_PATHS = {…} %}`).
- Extract `d` attributes from the Material Symbols outlined set for the inventory names
  (save(12), add(11), delete(9), hourglass_empty(8), close(8), edit(7), warning(6),
  sync(6), check_circle(6), … full list from the plan's grounded findings).

### Step 2 — `static/css/input.css`: default icon sizing
- Add an `.icon` base in `@layer components`: `width:1em; height:1em;
  vertical-align:-0.125em; flex-shrink:0;` so SVGs inherit the font-size sizing model
  the font used (avoids touching every call-site's CSS). Rebuild.

### Step 3 — `static/js/icons.js`
```js
const Icons = (() => {
  const P = { save:'…', add:'…', /* ~25 JS-used names only */ };
  function svg(name, cls='') {
    return `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><path d="${P[name]||''}"/></svg>`;
  }
  return { svg };
})();
window.Icons = Icons;
```
- Only the ~25 names actually rendered from JS (don't ship 62 paths client-side twice).
  Header comment: "source of truth = components/icons.html; keep in sync."
- Load it in `base.html` **before** modals/notifications/keyboard-shortcuts.

### Step 4 — Convert shared infra
- `base.html` toast template: `<span class="material-icons">…</span>` → `Icons.svg(…)`
  (or the macro if server-rendered); retarget `.toast-success .material-icons` → `.toast-success svg`/`.toast-success .icon` (and the other 3, :187–190).
- `modals.js` (3 icons), `notifications.js` (2), `keyboard-shortcuts.js` (2), `ui.js`
  (4): replace each `material-icons` span with `Icons.svg('name','cls')`.
- **Safety rails** (\x01 lesson): replacement *functions*; grep `[\x00-\x08]`;
  `node --check` each edited JS file.

### Step 5 — Build, deploy, verify per Step 0. **Leave the font `<link>` in place** (P06).

---

## Acceptance Criteria
- [ ] `icons.html` macro renders all 62 glyphs; `icons.js` covers the JS-used subset.
- [ ] `.icon` base sizing makes SVGs match the font's visual size; color inherits
      (`currentColor`) so `.toast-*` tints still work.
- [ ] Toasts (×4), confirm modal, keyboard overlay, sidebar icons render as inline SVG,
      correct size/color; axe clean; no console errors.
- [ ] Font `<link>` still present (pages untouched this phase).
- [ ] Committed, pushed, deployed, verified.

## Risks
- Sizing drift: the font sized by `font-size`; if any call-site set icon size via
  `font-size`, the `1em` SVG base covers it — but spot-check dense spots (table action
  icons, sidebar) on prod.
- Two sources of paths (macro + JS) can drift; the JS header comment + the P09 grep
  gate mitigate. Keep the JS subset minimal.
