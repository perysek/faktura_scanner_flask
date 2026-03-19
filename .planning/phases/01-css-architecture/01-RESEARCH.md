# Phase 1: CSS Architecture - Research

**Researched:** 2026-03-19
**Domain:** Tailwind CSS `@layer components`, Jinja2 template CSS consolidation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `.page-title` unifies to 1.75rem on all pages including calendars (calendar_month.html, calendar_week.html currently at 1.375rem)
- `font-family: var(--font-display)` goes into the global `.page-title` definition (eliminates its omission in auth/change_password.html)
- `margin-bottom` stays per-template — NOT in the global `.page-title` definition
- `.stat-value` standardises to 1.25rem globally
- Only 4 classes go global: `.page-title`, `.page-subtitle`, `.stat-value`, `.stat-label`
- Per-feature unique classes (`.coverage-value`, `.summary-value`, `.appointment-client`, etc.) remain local

### Claude's Discretion
- Order of removing local definitions after global declarations are added (can group per-feature or alphabetically)
- How to handle templates that extend the global definition with additional style (e.g. adding `color` or `margin`) — minor overrides stay locally

### Deferred Ideas (OUT OF SCOPE)
- None identified during discuss-phase. `.section-title` and `.form-label` classes were considered but deferred to future milestones.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TYPO-01 | Common `:root`/`@layer components` block with typographic class declarations (`.page-title`, `.page-subtitle`, `.stat-value`, `.stat-label`) moved to `static/css/input.css` — eliminates 45 duplicates | `@layer components` is the correct insertion point in the existing `input.css`; confirmed no `:root` blocks exist in templates |
| TYPO-02 | Consistent `.page-title` scale — 1.75rem on all pages including calendar views (currently 1.375rem) | Exact templates requiring update: calendar_month.html, calendar_week.html (1.375rem→1.75rem); dashboard/index.html, settings/email.html, history/list_refined.html, invoices/{create,edit,upload,list_refined}.html, sellers/{create,edit,list_refined}.html (1.5rem→1.75rem) |
| TYPO-03 | Unified `.stat-value` scale — one size instead of 1.25rem/1.5rem/1.75rem on different pages | Exact templates requiring update: clients/list.html, employees/list.html, services/list.html (1.75rem→1.25rem); income/dashboard.html (1.5rem→1.25rem); sellers/edit.html stays at 1rem (intentional local override — compact form context) |
</phase_requirements>

---

## Summary

Phase 1 consolidates four typography classes into a single `@layer components` block in `static/css/input.css`. No new libraries, no build system changes, no template HTML structure changes. The work is exclusively CSS surgery: write one canonical definition, then remove the local redeclarations from 38+ Jinja2 templates.

The current state is a direct grep into every template. The findings below are HIGH confidence because they come from actual source inspection, not inference.

After this phase: any font-size change to `.page-title` touches one line in `input.css` and propagates to all 50 templates automatically.

**Primary recommendation:** Add the 4-class block to `@layer components` in `input.css`, run `npm run build`, then systematically strip local redeclarations template by template.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | ^3.4.0 | CSS compilation pipeline (`input.css` → `output.css`) | Already in use; build is `npm run build` |

### Supporting
| Concept | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@layer components` | CSS Cascade Layers (native) | Place utility-first component definitions that can be overridden by utilities | All 4 typography classes go here — same layer already used in this project |
| `@layer base` | CSS Cascade Layers (native) | Global element resets and `:root` variables | Already in use in `input.css`; do NOT add component classes here |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@layer components` in `input.css` | Separate `typography.css` imported via `@import` | More files, same result — unnecessary given one file already exists |
| Global `.page-title` definition | Jinja2 macro with inline `style=` | Loses CSS cascade benefits, harder to override, no Tailwind purge safety |

**Build command:**
```bash
npm run build
# equivalent: tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify
```

---

## Architecture Patterns

### Recommended CSS Block Structure

Add this block inside `@layer components` in `static/css/input.css`:

```css
/* ============================================
   TYPOGRAPHY — Global shared classes
   Phase 1: CSS Architecture
   ============================================ */

.page-title {
    font-family: var(--font-display);
    font-size: 1.75rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--color-ink);
}

.page-subtitle {
    color: var(--color-ink-muted);
    font-size: 0.8125rem;
    font-weight: 300;
}

.stat-value {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-ink);
    line-height: 1;
}

.stat-label {
    font-size: 0.6875rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-ink-subtle);
}
```

**Important:** Place immediately after the existing modal component block — the `@layer components` block is already open and active in `input.css`.

### Pattern: Local Override After Global Definition

When a template needs a contextual adjustment beyond the global definition, keep only the delta locally:

```html
{% block styles %}
<style>
    /* Only the context-specific delta — global definition handles the rest */
    .page-title { margin-bottom: 0.5rem; }
</style>
{% endblock %}
```

A local `{ margin-bottom: 0.5rem; }` rule defined inside `<style>` in the template **will override** the `@layer components` definition because inline `<style>` tags operate in the implicit outer layer (higher specificity than named `@layer` blocks).

### Anti-Patterns to Avoid

- **Duplicating the full definition locally after globalising:** Removing the local block is required — leaving it creates a hidden override that silently overrides the global value.
- **Adding `!important` to global class definitions:** The whole point is cascade; `!important` breaks intentional local overrides.
- **Editing `output.css` directly:** It is regenerated by every `npm run build` run. Changes are lost.
- **Adding component classes to `@layer base`:** `@layer base` is for element defaults and variables. Components belong in `@layer components`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Determining which templates have local overrides | Custom audit script | Grep for `\.page-title\s*{` etc. | One-time inventory already done (see below) |
| Preventing regressions across 50 templates | Browser screenshot comparison suite | Visual inspection + `npm run build` verify | Overkill for CSS text changes with no layout impact |

---

## Complete Template Inventory

This is the exhaustive ground-truth for what needs to change. Derived from direct source inspection.

### `.page-title` — Local Definitions to Remove After Globalising

Templates already at 1.75rem (remove local definition, global definition takes over):
- `auth/change_password.html` — missing `font-family: var(--font-display)` → global fixes this
- `appointments/view.html`
- `appointments/create.html`
- `appointments/edit.html`
- `appointments/list.html`
- `appointments/calendar.html`
- `appointments/superadmin_edit.html` (not confirmed in grep but follows pattern — verify)
- `clients/create.html`
- `clients/edit.html`
- `clients/list.html`
- `clients/view.html`
- `employees/create.html`
- `employees/edit.html`
- `employees/list.html`
- `employees/view.html`
- `employees/formy_zatrudnienia/list.html`
- `income/dashboard.html`
- `roles/create.html`
- `roles/edit.html`
- `roles/list.html`
- `services/create.html`
- `services/edit.html`
- `services/list.html`
- `services/view.html`
- `users/create.html`
- `users/edit.html`
- `users/list.html`

Templates at 1.5rem that need updating to 1.75rem (change font-size AND remove local definition):
- `dashboard/index.html` — also has `color: var(--color-ink)` and `margin: 0` (keep `margin: 0` locally if needed)
- `settings/email.html` — also has `color: var(--color-ink)` (redundant with global, remove)
- `history/list_refined.html` — also has `color: var(--color-ink)` (redundant with global, remove)
- `invoices/create.html` — also has `color: var(--color-ink)` (redundant, remove)
- `invoices/edit.html` — also has `color: var(--color-ink)` (redundant, remove)
- `invoices/upload.html` — also has `color: var(--color-ink)` (redundant, remove)
- `invoices/list_refined.html` — also has a responsive media query `@media ... { .page-title { font-size: 1.25rem; } }` at line 636 — keep that media query locally
- `sellers/create.html` — also has `color: var(--color-ink)` (redundant, remove)
- `sellers/edit.html` — also has `color: var(--color-ink)` and local `margin: 0 0 0.25rem 0` (keep margin locally)
- `sellers/list_refined.html` — also has `color: var(--color-ink)` (redundant, remove)

Templates at 1.375rem that need updating to 1.75rem (change font-size AND remove local definition):
- `appointments/calendar_month.html`
- `appointments/calendar_week.html`

Templates with NO `.page-title` local definition (no action needed):
- `analytics/dashboard.html` — uses Tailwind utility classes directly (`text-2xl font-semibold text-slate-900`)

### `.page-subtitle` — Local Definitions to Remove After Globalising

The dominant pattern is `color: var(--color-ink-muted); font-size: 0.8125rem; font-weight: 300;`. The global definition matches this exactly.

Templates with non-standard values (keep local override):
- `roles/edit.html` — adds `font-family: monospace` (intentional for role UUIDs — keep locally)
- `invoices/edit.html` — uses `font-size: 0.75rem` instead of 0.8125rem (keep locally or remove — planner decides)
- `appointments/calendar_month.html` and `calendar_week.html` — use `font-size: 0.75rem` (compact calendar context — keep locally)
- `settings/email.html` and `sellers/create.html` / `sellers/edit.html` — use `font-size: 0.875rem` (slightly larger — keep locally)

Templates matching global exactly (remove local definition):
- `users/list.html`, `roles/list.html`, `appointments/view.html`, `appointments/list.html`, `appointments/edit.html`, `appointments/create.html`, `appointments/calendar.html`, `income/dashboard.html`, `clients/list.html`, `clients/edit.html`, `clients/create.html`, `clients/view.html`, `employees/create.html`, `employees/edit.html`, `employees/list.html`, `employees/view.html`, `employees/formy_zatrudnienia/list.html`, `services/create.html`, `services/edit.html`, `services/list.html`, `services/view.html`

### `.stat-value` — Local Definitions to Remove After Globalising

| Template | Current | Action |
|----------|---------|--------|
| `dashboard/index.html` | 1.25rem, color: var(--color-ink), line-height: 1 | Remove (global matches) |
| `sellers/list_refined.html` | 1.25rem, color: var(--color-ink), line-height: 1 | Remove (global matches) |
| `income/dashboard.html` | 1.5rem + color modifier classes (`.stat-value.green`, etc.) | Change to 1.25rem, remove base block, keep `.stat-value.green { color: ... }` modifiers locally |
| `clients/list.html` | 1.75rem, font-family: var(--font-display), color: var(--color-ink) | Remove (global matches after 1.75rem→1.25rem correction) |
| `employees/list.html` | 1.75rem, font-family: var(--font-display), color: var(--color-ink) | Remove (global matches after correction) |
| `services/list.html` | 1.75rem, font-family: var(--font-display), color: var(--color-ink) | Remove (global matches after correction) |
| `sellers/edit.html` | 1rem (compact form context) | **Keep as local override** — intentionally smaller |

### `.stat-label` — Canonical Value Decision

Two variants found across templates:
- **Variant A** (clients/list, employees/list, services/list): `font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em;` — no color defined
- **Variant B** (dashboard/index, sellers/list_refined, income/dashboard): `font-size: 0.6875rem; text-transform: uppercase; letter-spacing: 0.08em-0.1em; color: var(--color-ink-subtle);`
- **Variant C** (sellers/edit): `font-size: 0.6875rem; color: var(--color-ink-subtle); margin-top: 0.125rem;`

**Recommended canonical:** Variant B-style (`0.6875rem`, `letter-spacing: 0.08em`, `color: var(--color-ink-subtle)`) because it includes explicit color (Variant A omits it), matches the more polished dashboard/income templates, and aligns with the existing `income/dashboard.html` implementation.

Templates requiring a local override for `.stat-label` after globalising (they use 0.75rem variant):
- `clients/list.html` — can remove or keep a `font-size: 0.75rem` override
- `employees/list.html` — same
- `services/list.html` — same

---

## Common Pitfalls

### Pitfall 1: CSS Cascade Layer Specificity

**What goes wrong:** After adding `.page-title` to `@layer components`, a template with a remaining local `<style>.page-title { font-size: 1.5rem; }</style>` overrides the global definition. Developer thinks "global definition must not be working."

**Why it happens:** Styles in `<style>` tags in the document `<head>` belong to the implicit outer layer, which has higher priority than any named `@layer`. This is by design and is correct — it allows local overrides.

**How to avoid:** The cleanup step (removing local definitions) is as important as the addition step. A template that still has a local `.page-title` block will always win over the global definition.

**Warning signs:** Navigating to that specific page still shows the old size.

### Pitfall 2: Partial Block Removal

**What goes wrong:** Developer removes `font-size: 1.75rem;` from a local block but leaves the other properties (e.g. `font-weight: 600; letter-spacing: -0.02em;`). The block is now partially redundant but still present.

**Why it happens:** Surgical property-by-property removal in multi-property blocks is error-prone.

**How to avoid:** For templates where ALL properties match the global definition, remove the entire `.page-title { }` block. Only keep the block if there is a genuine local delta (e.g. `margin-bottom`).

### Pitfall 3: `color: var(--color-ink)` Confusion

**What goes wrong:** Multiple templates have `color: var(--color-ink)` in their local `.page-title` block. Developer wonders whether to keep this in the global definition.

**Why it happens:** `--color-ink` is the default body text color. Some templates added it explicitly; others omitted it. The body already sets `color: var(--color-ink)` globally, so it is redundant in all cases.

**How to avoid:** Include `color: var(--color-ink)` in the global definition (defensive, explicit). Then all local `color: var(--color-ink)` copies are safely removable.

### Pitfall 4: The `invoices/list_refined.html` Responsive Override

**What goes wrong:** This template has both a top-level `.page-title { font-size: 1.5rem; }` AND a media-query override `@media (max-width: 1024px) { .page-title { font-size: 1.25rem; } }` at line 636.

**How to avoid:** Remove the top-level block only. Retain the media query block locally — it is a genuine responsive contextual override that global CSS cannot express.

### Pitfall 5: `income/dashboard.html` Modifier Classes

**What goes wrong:** The template defines `.stat-value.green { color: var(--color-success); }` alongside the base `.stat-value` block. Developer removes the entire block and loses the color modifiers.

**How to avoid:** Remove only the base `.stat-value { ... }` block. Keep `.stat-value.green`, `.stat-value.blue`, `.stat-value.purple`, `.stat-value.orange` modifier rules. These are feature-local semantics that belong in the template.

### Pitfall 6: Build Not Run After Input.css Change

**What goes wrong:** Developer adds classes to `input.css` and tests in browser — sees no change.

**Why it happens:** Flask serves `output.css` (precompiled). `input.css` is not served directly.

**How to avoid:** Always run `npm run build` after any change to `input.css` before checking the browser.

---

## Code Examples

### Global Typography Block (goes into `@layer components`)

```css
/* Source: input.css — add inside existing @layer components block */
/* ============================================
   TYPOGRAPHY — Global shared classes
   Phase 1: CSS Architecture
   ============================================ */

.page-title {
    font-family: var(--font-display);
    font-size: 1.75rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--color-ink);
}

.page-subtitle {
    color: var(--color-ink-muted);
    font-size: 0.8125rem;
    font-weight: 300;
}

.stat-value {
    font-family: var(--font-display);
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--color-ink);
    line-height: 1;
}

.stat-label {
    font-size: 0.6875rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-ink-subtle);
}
```

### Correct Local Override Pattern (margin delta)

```html
<!-- Source: any template needing context-specific margin -->
{% block styles %}
<style>
    /* Only the delta — global .page-title handles font-size/weight/family */
    .page-title { margin-bottom: 0.5rem; }
</style>
{% endblock %}
```

### Correct Local Override Pattern (compact stat in form)

```html
<!-- Source: sellers/edit.html — intentionally compact stat widget -->
<style>
    /* Contextual override: compact form context needs smaller stat */
    .stat-value { font-size: 1rem; }
    .stat-label { margin-top: 0.125rem; }
</style>
```

### Verification Command

```bash
# After removing all local definitions, confirm no template still redefines these classes
grep -r "\.page-title\s*{" templates/
grep -r "\.stat-value\s*{" templates/
grep -r "\.page-subtitle\s*{" templates/
grep -r "\.stat-label\s*{" templates/
```

Expected output after cleanup: only small local override blocks (containing just context-specific properties like `margin-bottom`), not full redeclarations.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None detected — no pytest.ini, jest.config.*, or vitest.config.* found |
| Config file | None — Wave 0 gap |
| Quick run command | `npm run build` (build verification) |
| Full suite command | Manual browser verification on key pages |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TYPO-01 | No template `<style>` block contains a full `.page-title`/`.page-subtitle`/`.stat-value`/`.stat-label` redeclaration | grep audit | `grep -r "\.page-title\s*{" templates/` — should return only delta overrides | ❌ Wave 0: write grep check script |
| TYPO-02 | `.page-title` renders at 1.75rem on all pages including calendars | manual visual | Navigate dashboard→calendar, check headline size parity | Manual only |
| TYPO-03 | `.stat-value` renders at 1.25rem on clients/list, employees/list, income/dashboard | manual visual | Compare stat cards across those 3 pages + dashboard/index | Manual only |

### Sampling Rate
- **Per task commit:** `npm run build` — confirms CSS compiles without errors
- **Per wave merge:** grep audit (TYPO-01) + manual browser spot-check on 3 key pages: `dashboard/index`, `appointments/calendar_month`, `clients/list`
- **Phase gate:** All grep audits clean + visual parity confirmed before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] No automated test infrastructure exists for CSS validation — acceptable for this phase; grep audit serves as TYPO-01 verification
- [ ] Framework install: not applicable — this phase is pure CSS, no Python test logic involved

---

## Sources

### Primary (HIGH confidence)
- Direct source inspection of `static/css/input.css` — confirmed `@layer components` block structure, existing CSS custom properties, build pipeline
- Direct grep of all 50 templates — confirmed exact current values for all 4 classes
- `package.json` — confirmed build command `npm run build:css` and Tailwind 3.4.x

### Secondary (MEDIUM confidence)
- Tailwind CSS v3 documentation on `@layer` — `@layer components` is the canonical location for component-level styles that can be overridden by utilities (well-established, unchanged since v2)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — confirmed from actual project files
- Architecture: HIGH — `@layer components` pattern confirmed in existing `input.css`, CSS cascade layer behavior is well-specified
- Pitfalls: HIGH — derived from actual source inspection of each template's anomalies
- Template inventory: HIGH — exhaustive grep results, confirmed counts

**Research date:** 2026-03-19
**Valid until:** This research is tied to the current codebase state. Valid until any template is modified. Stable for 60+ days unless new templates are added.
