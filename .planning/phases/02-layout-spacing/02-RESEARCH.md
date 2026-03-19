# Phase 2: Layout & Spacing - Research

**Researched:** 2026-03-19
**Domain:** Flask/Jinja2 template layout — CSS specificity, padding inheritance, max-width conventions
**Confidence:** HIGH (pure codebase audit — no external library research needed)

## Summary

This phase is a pure template surgery task. The problem is fully diagnosed: `base.html` line 44 adds `p-2` (0.5rem padding) to `#main-content`, causing 13 templates to fight it with `padding: ... !important`. The fix is surgical: change `p-2` to `p-0` in one place, then remove all `!important` padding overrides from 13 templates and ensure every template provides its own padding via its `.refined-page` wrapper or equivalent.

The codebase uses two established wrapper patterns that already coexist: (1) `.refined-page` class defined in `{% block extra_css %}` — used by appointments, employees, services, roles, users, income, auth; and (2) inline style on the first `<div>` in `{% block content %}` — used by clients, employees/list. Both are valid per user decision ("per-template wrapper"). The standard padding to restore after removing `!important` is `1rem 1.5rem` (the value 12 of 13 overriding templates use).

The max-width audit reveals 6 distinct current values that must be normalized to 3: 900px (forms/detail), 1400px (lists), no constraint (calendars + dashboard). Several templates already have the target values; others need adjustment. Three templates have no page-level max-width at all (`analytics/dashboard.html`, `auth/profile.html`, `invoices/create.html`, `invoices/edit.html`) and need audit decisions.

**Primary recommendation:** Treat as two sequential waves: Wave 1 — single-line change to `base.html`. Wave 2 — per-template cleanup grouped by feature area, removing `!important` and normalizing `max-width`. Each wave is independently verifiable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Change `p-2` to `p-0` on `#main-content` in `base.html` (line 44)
- Pages define their own padding on their wrapper, not via base.html
- Error pages (404, 500) naturally benefit from `p-0` — their fullscreen layout is correct as-is
- Required: manual visual spot-check of 5 key pages after base.html change
- Max-width scale:
  - Forms (create/edit): 900px — standardize (clients/create currently 800px → change to 900px)
  - Detail/view pages (clients/view, appointments/view, employees/view): 900px
  - Lists (clients, employees, services, sellers, invoices): 1400px
  - Calendars + dashboard: no max-width (full-width) — per SPAC-02
  - sellers/edit superadmin: special case — no changes (owns its own full-width layout)
- Max-width as local wrapper per-template (not new global CSS classes)
- Templates without any max-width that are forms/views → add 900px wrapper

### Claude's Discretion
- Order of changes: base.html first, then templates grouped per-feature
- Exact wrapper implementation (inline style vs Tailwind utility) per-template

### Deferred Ideas (OUT OF SCOPE)
- Global CSS classes (.page-wrapper-form, .page-wrapper-list) — considered but deferred; per-template wrapper is sufficient and less risky for this phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SPAC-01 | Remove `!important` padding override from 14+ templates — `base.html` must default to padding 0, pages define their own | Base.html `p-2→p-0` change eliminates the need for all `!important` overrides. 13 templates confirmed; each has `.refined-page` or equivalent providing padding. |
| SPAC-02 | Consistent max-width scale for page types (forms: 900px, lists: 1400px, calendars: full-width) | Complete template audit below maps every template to its current and target value. Calendar pages already use `.refined-page { max-width: 1400px/1600px }` which must change to no max-width per SPAC-02. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | Installed via `static/css/output.css` | Utility classes (`p-0`, `mx-auto`) | Already in project, `p-0` available |
| Flask/Jinja2 | Project-standard | `{% block extra_css %}` for per-template styles | All templates use this pattern |

### No external libraries needed
This phase touches only HTML template structure and inline CSS. No npm installs, no new dependencies.

## Architecture Patterns

### Recommended Project Structure
No file structure changes. All work is within existing `templates/` directory.

### Pattern 1: `.refined-page` CSS class (used by most templates)
**What:** Template defines `.refined-page` in `{% block extra_css %}` with max-width + margin + padding. Wrapper div in `{% block content %}` gets `class="refined-page"`.
**When to use:** All templates that already use `.refined-page` class — maintain pattern consistency.
**Example:**
```css
/* In {% block extra_css %} */
.refined-page { max-width: 900px; margin: 0 auto; padding: 2rem; }
```
```html
<!-- In {% block content %} -->
<div class="refined-page">
  ...page content...
</div>
```

### Pattern 2: Inline style on content wrapper (used by clients/*)
**What:** First div in `{% block content %}` carries inline style with max-width + margin + padding. No CSS class defined.
**When to use:** Templates already using this pattern (clients/list.html, clients/view.html, clients/create.html, clients/edit.html). Do not convert to `.refined-page` — maintain existing pattern.
**Example:**
```html
<div style="max-width: 1400px; margin: 0 auto; padding: 2rem;">
  ...page content...
</div>
```

### Pattern 3: Full-width viewport-filling (dashboard, list pages with sticky tables)
**What:** Template sets `display: flex; flex-direction: column; height: 100%; overflow: hidden` on `.refined-page` to fill the viewport and enable inner scroll. No `max-width`.
**When to use:** Dashboard, history/list, invoices/list, sellers/list — pages where content must fill the screen and inner scroll is intentional.
**Example:**
```css
.refined-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    /* NO max-width */
}
```
After removing `!important` from `#main-content`, the `padding: 1rem 1.5rem` moves to `.refined-page` itself:
```css
.refined-page {
    padding: 1rem 1.5rem;
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
}
```

### Pattern 4: `#main-content` background override (background-only, no padding)
**What:** Some templates set `background: var(--color-surface-warm)` on `#main-content` without touching padding. This is safe and stays as-is after `p-0` change.
**When to use:** Any template that needs a non-default background on the main area.
**Affected templates:** `auth/profile.html`, `auth/change_password.html`, `invoices/list_refined.html` (first block), all the `padding: 1rem 1.5rem !important` templates (background + padding combined).

### Anti-Patterns to Avoid
- **Padding on `#main-content` with `!important`:** The entire point of this phase is to eliminate these. After `p-0`, `!important` is unnecessary — remove the padding property entirely or move to wrapper.
- **Removing padding without restoring it on wrapper:** Templates that relied on `#main-content` padding (via `!important`) need equivalent padding on their own `.refined-page`. Most already have it; confirm before removing.
- **Global CSS classes for max-width:** Out of scope per user decision. Do not add `.page-wrapper-form` or similar to `input.css`.
- **Changing calendar max-width before confirming full-width intent:** Calendars currently have 1400px/1600px max-width on `.refined-page`. Per SPAC-02 these must go to no max-width. Verify visual result.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Padding normalization | Custom CSS reset or cascade layer | `p-0` Tailwind class on `#main-content` | One character change, already in Tailwind build |
| Max-width enforcement | JS-based layout enforcement | CSS in `{% block extra_css %}` | Server-rendered, no runtime needed |

**Key insight:** This is a CSS specificity problem, not a design system problem. The entire fix is removing the conflict source (`p-2`) and letting each template be authoritative over its own layout.

## Complete Template Audit

### Group A: base.html change only (1 file)
| File | Change |
|------|--------|
| `templates/base.html` line 44 | `p-2` → `p-0` |

### Group B: Remove `!important` padding — template already has its own padding on wrapper (no max-width change needed)
These templates have `#main-content { padding: X !important; }` and `.refined-page` already includes `padding` in its definition. Remove the entire `#main-content { ... padding ... }` rule or just the padding property.

| File | Current `#main-content` override | `.refined-page` padding | Action |
|------|-----------------------------------|------------------------|--------|
| `sellers/create.html` | `padding: 1rem 1.5rem !important` | No padding on `.refined-page` itself | Move `padding: 1rem 1.5rem` to `.refined-page` |
| `sellers/edit.html` | `padding: 1rem 1.5rem !important` | No padding on `.refined-page` itself | Move `padding: 1rem 1.5rem` to `.refined-page` |
| `settings/email.html` | `padding: 1rem 1.5rem !important` | No padding on `.refined-page` itself | Move `padding: 1rem 1.5rem` to `.refined-page` |
| `invoices/create.html` | `padding: 1rem 1.275rem !important` | No padding on `.refined-page` itself | Move `padding: 1rem 1.5rem` to `.refined-page` (normalize to standard) |
| `invoices/edit.html` | `padding: 1rem 1.5rem !important` | No padding on `.refined-page` itself | Move `padding: 1rem 1.5rem` to `.refined-page` |
| `invoices/upload.html` | `padding: 1rem 1.5rem !important`, `overflow-x: hidden !important` | `refined-page` has `max-width: 100%; overflow-x: hidden` | Remove padding from `#main-content`, add `padding: 1rem 1.5rem` to `.refined-page`; keep `overflow-x: hidden` on both |

### Group C: Remove `!important` padding — flex-column full-height layouts (move padding to `.refined-page`)
These are the "sticky scrollable list" templates. `#main-content` has `padding + display:flex + overflow:hidden !important`. After removing `!important`, the `display:flex` and `overflow:hidden` on `#main-content` become moot (base.html uses `flex-1 overflow-auto`). The padding must move to `.refined-page`.

| File | Action |
|------|--------|
| `dashboard/index.html` | Remove `padding: 1rem 1.5rem !important` from `#main-content`; add `padding: 1rem 1.5rem` to `.refined-page` |
| `history/list_refined.html` | Same — full-width list, no max-width needed |
| `invoices/list_refined.html` | Has TWO `#main-content` blocks (lines 19 and 618). Remove padding from the line-618 block; first block (background only) stays. Add `padding: 1rem 1.5rem` to `.refined-page` |
| `sellers/list_refined.html` | Remove padding `!important` from `#main-content`; add `padding: 1rem 1.5rem` to `.refined-page` |

### Group D: Error/special pages — no change to padding (correct after p-0)
| File | Current override | After p-0 |
|------|-----------------|-----------|
| `errors/404.html` | `padding: 0 !important` | Can remove `!important` since base is now `p-0` |
| `errors/500.html` | `padding: 0 !important` | Can remove `!important` since base is now `p-0` |
| `appointments/superadmin_edit.html` | `padding: 0 !important; overflow: hidden !important` | Can remove `!important` on padding (still explicit 0 for clarity OK, or remove entirely) |

### Group E: Max-width adjustments only (no `!important` to remove — these use `.refined-page` class in CSS)
| File | Current max-width | Target | Change |
|------|-------------------|--------|--------|
| `clients/create.html` | 800px | 900px | Update `.refined-page { max-width: 800px }` → 900px |
| `clients/edit.html` | 800px | 900px | Same |
| `clients/view.html` | 900px | 900px | No change |
| `clients/list.html` | 1400px | 1400px | No change |
| `appointments/create.html` | 900px | 900px | No change |
| `appointments/edit.html` | 1000px | 900px | Update to 900px (detail/view scale) |
| `appointments/view.html` | 1000px | 900px | Update to 900px |
| `appointments/list.html` | 1400px | 1400px | No change |
| `appointments/calendar.html` | 1400px | full-width | Remove max-width from `.refined-page` per SPAC-02 |
| `appointments/calendar_week.html` | 1600px | full-width | Remove max-width from `.refined-page` per SPAC-02 |
| `appointments/calendar_month.html` | 1600px | full-width | Remove max-width from `.refined-page` per SPAC-02 |
| `employees/create.html` | 800px | 900px | Update to 900px |
| `employees/edit.html` | 800px | 900px | Update to 900px |
| `employees/list.html` | 1400px | 1400px | No change |
| `employees/view.html` | 1000px | 900px | Update to 900px |
| `employees/formy_zatrudnienia/list.html` | 1100px | 1400px | Update to 1400px (list type) |
| `services/create.html` | 800px | 900px | Update to 900px |
| `services/edit.html` | 800px | 900px | Update to 900px |
| `services/list.html` | 1400px | 1400px | No change |
| `services/view.html` | 900px | 900px | No change |
| `income/dashboard.html` | 1400px | full-width | Remove max-width (dashboard type) |
| `roles/create.html` | 720px | 900px | Update to 900px (form type) |
| `roles/edit.html` | 720px | 900px | Update to 900px |
| `roles/list.html` | 1200px | 1400px | Update to 1400px |
| `users/create.html` | 720px | 900px | Update to 900px |
| `users/edit.html` | 720px | 900px | Update to 900px |
| `users/list.html` | 1400px | 1400px | No change |
| `sellers/create.html` | 600px (on `.refined-page`) | 900px | Update to 900px |
| `sellers/edit.html` | 900px (on `.refined-page`) | 900px | No change |
| `sellers/list_refined.html` | No max-width on `.refined-page` (full-width, flex-column) | full-width | No change |
| `auth/change_password.html` | 480px (on `.refined-page`) | 900px | Update — OR leave at 480px if considered a special auth form. Needs decision. |
| `settings/email.html` | 600px (on `.refined-page`) | 900px | Update to 900px |

### Group F: Templates with no max-width — need audit
| File | Type | Recommendation |
|------|------|---------------|
| `analytics/dashboard.html` | Dashboard — uses Tailwind classes directly, no `.refined-page`, no `#main-content` override | Full-width is correct per SPAC-02. No wrapper needed — the `p-2` from base will become `p-0`, so padding disappears. Need to add `padding: 1rem 1.5rem` on the first content div or via `{% block extra_css %}`. |
| `auth/profile.html` | Profile view — has `max-w-4xl mx-auto` Tailwind class on content div + `padding: 2rem` inline | `max-w-4xl` = 56rem = 896px ≈ 900px. Effectively already at target. Safe to leave as Tailwind utility. |
| `invoices/create.html` | Form — `.refined-page` has NO max-width in its CSS definition | Is a wide form (two-panel invoice editor). Evaluate whether max-width applies or full-width is intentional. |
| `invoices/edit.html` | Form — same — `.refined-page` has NO max-width | Same as create |

## Common Pitfalls

### Pitfall 1: flex-column height-100% pages losing scroll after removing `#main-content` padding
**What goes wrong:** Templates like `dashboard/index.html`, `history/list_refined.html`, `invoices/list_refined.html`, `sellers/list_refined.html` use `height: 100%; overflow: hidden` on `.refined-page` to create an inner-scrollable area. Their `#main-content` currently also sets `overflow: hidden !important`. After removing `overflow: hidden` from `#main-content`, the base.html `overflow-auto` takes over. The inner scroll mechanism in `.refined-page` should still work because `height: 100%` inherits from the `flex-1` container.
**Why it happens:** CSS flex/height inheritance depends on parent having explicit or flex-assigned height.
**How to avoid:** After change, visually verify these 4 pages still scroll correctly inside the content area.
**Warning signs:** The whole page scrolls instead of just the table, or content overflows without scroll.

### Pitfall 2: `invoices/list_refined.html` has two `#main-content` rule blocks
**What goes wrong:** Line 19 sets `background` only (no `!important`). Line 618 sets `padding: 1rem 1.5rem !important; display: flex; flex-direction: column; overflow: hidden !important;`. The second block is a late duplicate — must not forget it when auditing.
**How to avoid:** Remove only the padding from line 618 block. Keep background from line 19 block.

### Pitfall 3: Calendar templates need max-width removed, not just adjusted
**What goes wrong:** Calendars have `.refined-page { max-width: 1400px/1600px }`. Per SPAC-02 they must be full-width. Simply setting a very large number (e.g., 9999px) is wrong — remove the `max-width` property entirely.
**Warning signs:** Calendar shows a constrained centered layout on wide monitors.

### Pitfall 4: `analytics/dashboard.html` loses all padding after base change
**What goes wrong:** This template has no `#main-content` override and no `.refined-page` class. Currently it relies on `p-2` from base.html. After `p-0`, its content will be flush against the viewport edge.
**How to avoid:** Add padding to the first content div in `{% block content %}` before or in the same wave as the base.html change.

### Pitfall 5: `invoices/create.html` and `invoices/edit.html` — padding moves but there's no max-width
**What goes wrong:** These are wide two-panel forms. Removing `!important` from `#main-content` leaves `.refined-page` without padding and without max-width. The padding moves to `.refined-page`. The max-width question must be answered: do these use full-width intentionally?
**How to avoid:** Check the actual rendered layout. These invoice forms are wide editors — likely intentional full-width. If so: move padding to `.refined-page`, do not add max-width.

### Pitfall 6: `auth/change_password.html` and similar narrow forms
**What goes wrong:** `change_password.html` uses 480px max-width on `.refined-page`. Blanket-applying 900px would make it look too wide.
**How to avoid:** 480px for auth forms is a defensible design choice separate from the 900px form standard. This template only overrides `background` on `#main-content` (no padding `!important`). Since there is no padding `!important` to remove, it is out of scope for SPAC-01. Max-width normalization per SPAC-02 — apply 900px or leave at 480px as discretion.

## Code Examples

### Base.html change (the single most impactful edit)
```html
<!-- BEFORE (line 44 of base.html) -->
<main class="flex-1 overflow-auto p-2" id="main-content">

<!-- AFTER -->
<main class="flex-1 overflow-auto p-0" id="main-content">
```

### Standard form/view template — remove `!important`, ensure wrapper has padding
```css
/* BEFORE */
#main-content {
    background: var(--color-surface-warm);
    padding: 1rem 1.5rem !important;
}

.refined-page {
    font-family: var(--font-body);
    color: var(--color-ink);
    max-width: 600px;
    margin: 0 auto;
    /* no padding */
}

/* AFTER */
#main-content {
    background: var(--color-surface-warm);
    /* padding removed — base.html now p-0, wrapper provides it */
}

.refined-page {
    font-family: var(--font-body);
    color: var(--color-ink);
    max-width: 900px;
    margin: 0 auto;
    padding: 1rem 1.5rem;
}
```

### Full-width flex-column list template — remove `!important`, move padding to `.refined-page`
```css
/* BEFORE */
#main-content {
    background: var(--color-surface-warm);
    padding: 1rem 1.5rem !important;
    display: flex;
    flex-direction: column;
    overflow: hidden !important;
}

.refined-page {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
}

/* AFTER */
#main-content {
    background: var(--color-surface-warm);
    /* padding, display, overflow removed from here */
}

.refined-page {
    padding: 1rem 1.5rem;
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
}
```

### Calendar template — remove max-width for full-width per SPAC-02
```css
/* BEFORE */
.refined-page { max-width: 1400px; margin: 0 auto; padding: 2rem; }

/* AFTER */
.refined-page { padding: 2rem; }
/* margin: 0 auto removed along with max-width — centering only makes sense with a constrained width */
```

### clients/create.html — inline style pattern, bump 800px → 900px
```html
<!-- BEFORE -->
<div style="max-width: 800px; margin: 0 auto; padding: 2rem;">

<!-- AFTER -->
<div style="max-width: 900px; margin: 0 auto; padding: 2rem;">
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `#main-content { padding: X !important }` per-page fight | `p-0` on base + padding in wrapper | Eliminates CSS specificity war across 13+ files |
| Mixed max-width values (480/600/720/800/900/1000/1100/1200/1400/1600px) | Normalized 3-value scale (900/1400/none) | Predictable layout at a glance |

## Open Questions

1. **`invoices/create.html` and `invoices/edit.html` — intentional full-width?**
   - What we know: `.refined-page` has no `max-width`. These are two-panel invoice editors with a document preview on one side.
   - What's unclear: Is full-width the intended design, or did it just never get a max-width?
   - Recommendation: Treat as full-width (list-style, no max-width). They are wide editors, not narrow forms. Move padding to `.refined-page`, no max-width. Confirm with visual check.

2. **`analytics/dashboard.html` — padding restoration**
   - What we know: Uses raw Tailwind classes in content, no `#main-content` override. Will lose all padding after `p-0`.
   - Recommendation: Add `style="padding: 1rem 1.5rem"` to the outermost `<div>` in `{% block content %}` OR add a `{% block extra_css %}` block with a wrapper rule. Given dashboard is full-width, a simple padding wrapper is best.

3. **`auth/change_password.html` — 480px vs 900px**
   - Currently only overrides `background` on `#main-content` (no `!important` padding). Outside SPAC-01 scope.
   - For SPAC-02 max-width normalization: 480px for a narrow password form is reasonable. Apply Claude's discretion: leave at 480px as exception for auth flows.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual browser verification (no automated test suite detected for templates) |
| Config file | None — Flask templates, no Jest/Pytest for CSS/layout |
| Quick run command | `flask run` then visual check in browser |
| Full suite command | Manual spot-check of 5 key page types |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPAC-01 | No `!important` in computed styles for `#main-content` padding | Manual / CSS audit | `grep -rn "padding.*!important" templates/ --include="*.html"` (expect 0 hits on `#main-content`) | ❌ Wave 0 |
| SPAC-02 | Form pages ≤900px, list pages ≤1400px, calendars full-width | Manual visual check | No automated equivalent | Manual-only |

### Sampling Rate
- **Per task commit:** `grep -rn "padding.*!important" templates/ --include="*.html"` — confirm count decreasing
- **Per wave merge:** Visual check of one representative page from each category (form, list, calendar, dashboard)
- **Phase gate:** Zero `!important` padding hits on `#main-content` + visual regression check before `/gsd:verify-work`

### Wave 0 Gaps
- No automated test infrastructure needed — this is pure CSS/template work
- The grep command above serves as a machine-checkable proxy for SPAC-01
- SPAC-02 requires human eye — no machine check possible without browser automation

## Sources

### Primary (HIGH confidence)
- Direct codebase audit — `templates/` directory, all 52 `.html` files examined
- `base.html` line 44 — source of truth for the `p-2` problem
- `grep` output for `!important` padding — authoritative inventory of 13 affected files
- `grep` output for `max-width` — authoritative inventory of all current values

### No external research needed
This phase is entirely internal to the codebase. No library APIs, no framework versions, no community patterns required. All facts derived from direct file reads.

## Metadata

**Confidence breakdown:**
- Template inventory: HIGH — every file read directly
- `!important` count: HIGH — grep confirmed 13 matches (REQUIREMENTS.md says 14+ which includes the upcoming count)
- Max-width current values: HIGH — grep confirmed, values cross-checked against file reads
- Target max-width assignments: HIGH — all locked decisions in CONTEXT.md
- Edge cases (flex-column scroll, invoices full-width): MEDIUM — behavior inference, requires visual confirmation

**Research date:** 2026-03-19
**Valid until:** Until any template is added or modified — codebase is authoritative
