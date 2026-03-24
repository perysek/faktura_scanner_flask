# Phase 3: Color Cleanup - Research

**Researched:** 2026-03-24
**Domain:** CSS custom properties, Tailwind token utilities, JS runtime color access
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `var(--color-accent)` CSS custom property is the primary token for brand gold (#c9a227) — consistent with Phase 1 decision (CSS custom properties over Tailwind)
- `#d97706` (amber/warning) is a separate status token `var(--color-status-in-progress)`, not a brand color — replace with existing CSS var
- Tailwind `brand-500 = #c9a227` in `tailwind.config.js` stays as compile-time duplicate — Tailwind config cannot reference CSS vars
- Inline SVG `stroke="#c9a227"` (users/list.html) must become `stroke="currentColor"` + parent `class="text-brand-500"` — standard Tailwind pattern
- `superadmin_edit.html` and `superadmin_edit_table.html` are EXCLUDED from scope — per COL-03 (v3.0): "Power Panel do osobnego CSS, celowa rozbieżność"
- Auth templates (login, profile, forgot_password, reset_password) require separate attention — login.html does not inherit from base.html, standalone CSS
- JS files in `static/js/` are in scope — `calendar.html` JS has `#d97706` to replace
- `output.css` (compiled Tailwind) — ignore, generated automatically
- Inline style hex → `style="color: var(--color-accent)"` — minimal change, consistent with existing pattern
- `<style>` block hex → `color: var(--color-accent)` — CSS custom properties
- JS hex strings (calendar.html coverage bar) → `getComputedStyle(document.documentElement).getPropertyValue('--color-status-in-progress')`
- `npm run build` after changes if Tailwind classes in templates change

### Claude's Discretion
- Order of changes per-template (grouping per-feature or per-template)
- Handling edge cases with colors not covered by existing tokens

### Deferred Ideas (OUT OF SCOPE)
- COL-03 (v3.0): Superadmin "Power Panel" to separate CSS — documentation of intentional divergence
- Eventual consolidation of `--color-accent` and `brand-500` into one source of truth (requires Tailwind v4 or CSS-in-JS)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| COL-01 | Eliminate remaining ~80 hardcoded hex values from templates (auth, form, error templates) | Full audit complete — see "Actual Scope" section; 132 grep hits total, minus superadmin exclusions and HTML-entity false positives |
| COL-02 | `brand-*` Tailwind tokens or `var(--color-accent)` used in templates instead of `#c9a227` inline | Two specific occurrences confirmed: users/list.html SVG stroke, calendar.html JS coverage bar |
</phase_requirements>

---

## Summary

Phase 3 is a surgical color cleanup: eliminate every hardcoded `#c9a227` and `#d97706` occurrence (the two primary targets of COL-02), and reduce the wider set of in-template hex values by replacing them with existing CSS custom properties from `input.css` (COL-01).

The CSS token infrastructure is already complete from Phase 1. `static/css/input.css` defines `--color-accent: #c9a227`, `--color-status-in-progress: #d97706`, a full status color palette, semantic utility colors, and a chart palette. No new tokens need to be created for the primary targets. The Tailwind `brand-500` utility class is available for Tailwind-class contexts (SVG stroke via `currentColor`).

The two hardcoded brand/status hex occurrences outside the superadmin exclusion zone are confirmed: `users/list.html:86` (SVG `stroke="#c9a227"`) and `appointments/calendar.html:737` (JS `#d97706`). The "~80" figure for COL-01 refers to the broader set of non-brand hex values across all in-scope templates. A full grep audit shows 132 total occurrences across 41 files, but approximately 47 are in the two excluded superadmin templates, and a further ~10 are HTML-entity escape character maps (not colors). The true in-scope target is approximately 75-80 replaceable hex values.

**Primary recommendation:** Replace hex values file-by-file, starting with the two explicit COL-02 targets (users/list.html, calendar.html), then batch-replace the `#333` hover pattern (17 files), then address per-file semantic hex using existing tokens.

---

## Actual Scope Audit

### Excluded from scope (superadmin)
- `templates/appointments/superadmin_edit.html` — 17 occurrences (all OUT OF SCOPE)
- `templates/appointments/superadmin_edit_table.html` — 30 occurrences (all OUT OF SCOPE)

Total excluded: ~47 occurrences

### False positives (HTML entity escape maps in JS)
These grep matches contain `&#039;` and similar entities, not color hex values:
- `employees/view.html:767`, `income/dashboard.html:106`, `appointments/view.html:189`,
  `appointments/edit.html:169`, `appointments/list.html:165`, `services/list.html:407`,
  `clients/view.html:619`, `clients/list.html:450`

Approx 8-10 false positive matches.

### True in-scope target: ~75 occurrences

| Category | Count | Example | Replacement |
|----------|-------|---------|-------------|
| Brand gold `#c9a227` | 1 | `users/list.html` SVG stroke | `stroke="currentColor"` + `class="text-brand-500"` |
| Status amber `#d97706` | 1 | `calendar.html` JS | `getComputedStyle(document.documentElement).getPropertyValue('--color-status-in-progress')` |
| Button hover dark `#333` | 17 | auth, errors, form templates | `var(--color-ink)` |
| Alert/feedback hex (`#fef2f2`, `#fecaca`, `#dcfce7`, `#86efac`, `#fef3c7`) | ~15 | `change_password.html`, `roles/*.html` | `var(--color-status-cancelled-bg)`, `var(--color-status-in-progress-bg)` etc. |
| Status semantic without token (`#c2410c` orange-red, `#be185d` pink, `#2563eb` blue-link) | ~12 | `employees/list.html`, `clients/list.html` | `var(--color-chart-orange)`, `var(--color-chart-pink)`, `var(--color-status-scheduled)` |
| Misc one-offs (gradients, chart data, `#333` dark bg) | ~20 | `dashboard/index.html` chart colors | Closest CSS var or leave if no token exists |

---

## Standard Stack

### Core (already in place)
| Asset | Location | Purpose | Status |
|-------|----------|---------|--------|
| CSS custom properties | `static/css/input.css` `:root` block | All token definitions | Complete — no additions needed |
| Tailwind brand scale | `tailwind.config.js` `brand` key | Compile-time gold utilities | Complete |
| Tailwind build | `npm run build` | Regenerates `output.css` | Required after any new Tailwind class additions |

### Available tokens for replacement

| Hex Being Replaced | CSS Var Token | Tailwind Class |
|-------------------|--------------|----------------|
| `#c9a227` | `var(--color-accent)` | `text-brand-500` / `bg-brand-500` / `stroke="currentColor"` + `text-brand-500` |
| `#d97706` | `var(--color-status-in-progress)` | n/a (status = CSS vars per Phase 1 decision) |
| `#333` (button hover) | `var(--color-ink)` (#1a1a1a ≈ #333) | `text-ink` (not defined) — use CSS var |
| `#fef2f2` / `#fecaca` | `var(--color-status-cancelled-bg)` / no border token | keep hex or add token |
| `#dcfce7` / `#86efac` | `var(--color-status-confirmed-bg)` / no border token | keep hex or add token |
| `#fef3c7` / `#92400e` | `var(--color-status-in-progress-bg)` / `var(--color-warning)` | use CSS vars |
| `#2563eb` (link/chip) | `var(--color-status-scheduled)` / `var(--color-chart-blue)` | `text-primary-600` |
| `#c2410c` (orange-red) | `var(--color-chart-orange)` (#ea580c ≈ close) | `text-orange-700` (Tailwind default) |
| `#be185d` (pink) | `var(--color-chart-pink)` (#db2777 ≈ close) | `text-pink-700` (Tailwind default) |
| `#2d6a4f` (green) | `var(--color-success)` / `var(--color-status-completed)` | n/a |
| `#dc2626` (red) | `var(--color-status-cancelled)` | n/a |
| `#166534` (dark green text) | `var(--color-success)` (slightly different shade) | `text-green-800` |
| `#6a1b9a` / `#4a148c` (purple) | `var(--color-purple)` (#7e22ce ≈ close) | n/a |
| `#8a8a8a` (muted) | `var(--color-ink-subtle)` | n/a |

**Tokens that do NOT exist and should be evaluated per Claude's Discretion:**
- Border-only hex for alerts (`#fecaca`, `#86efac`, `#bbf7d0`) — no `--color-*-border` tokens in input.css
- History entity colors (`#6a1b9a`, `#00796b`, `#e65100`, `#1565c0`, `#4a148c`, `#424242`) — no token for these
- `#1f5a3a` (invoices/upload.html dark green button) — no token
- `#7d5500` (sellers/edit.html amber-dark) — no token

---

## Architecture Patterns

### Pattern 1: CSS Custom Property Replacement (inline style)
**What:** Replacing inline `style="color: #c9a227"` with CSS var equivalent.
**When to use:** All `style=""` attribute hex replacements.
**Example:**
```html
<!-- Before -->
<span style="color: #c9a227; font-weight: 600;">Gold text</span>

<!-- After -->
<span style="color: var(--color-accent); font-weight: 600;">Gold text</span>
```

### Pattern 2: CSS Block Replacement
**What:** Replacing hex inside `<style>` block declarations.
**When to use:** Any `#[hex]` inside `{% block styles %}` `<style>` tags.
**Example:**
```css
/* Before */
.refined-btn-primary:hover { background: #333; }

/* After */
.refined-btn-primary:hover { background: var(--color-ink); }
```

### Pattern 3: SVG Inline Stroke with Tailwind
**What:** Replacing hardcoded SVG attribute with `currentColor` + parent class.
**When to use:** `users/list.html:86` and any other `stroke="#c9a227"` or `fill="#c9a227"` patterns.
**Example:**
```html
<!-- Before -->
<div style="background: #fdf6e3;">
  <svg stroke="#c9a227" ...>

<!-- After -->
<div class="text-brand-500" style="background: var(--color-accent-muted);">
  <svg stroke="currentColor" ...>
```
**Note:** The parent container that receives `text-brand-500` must be the direct ancestor of the SVG, or `currentColor` will inherit from further up. `#fdf6e3` on the container background has no existing token — use `var(--color-accent-muted)` (`rgba(201,162,39,0.12)`) as the closest semantic match, or keep `#fdf6e3` if visual fidelity matters.

### Pattern 4: JS Runtime CSS Var Read
**What:** Replacing hardcoded hex strings in JavaScript with runtime CSS var reads.
**When to use:** `calendar.html:737` coverage bar color logic.
**Example:**
```javascript
// Before
coverageFill.style.background = '#d97706'; // Orange

// After — read from CSS var at call time
const inProgressColor = getComputedStyle(document.documentElement)
  .getPropertyValue('--color-status-in-progress').trim();
coverageFill.style.background = inProgressColor;
```
**Critical:** Must call `getComputedStyle` inside the function that uses it (not at module load), so that the value is read after DOM + stylesheets are fully loaded. The full `updateCoverage` function has three branches (`#2d6a4f`, `#d97706`, `#dc2626`) — all three should be replaced to keep the pattern consistent even though only `#d97706` is the explicit COL-02 target.

### Anti-Patterns to Avoid
- **Adding new CSS vars for one-off colors:** If a color appears only in one place and has no semantic meaning across the codebase (e.g., history entity label colors), do not create `--color-history-appointment`. Consolidate to the closest existing token or leave the hex with a `/* intentional */` comment.
- **Replacing HTML entity false positives:** `&#039;` in JS escape maps is not a color. Do not touch those lines.
- **Changing superadmin files:** `superadmin_edit.html` and `superadmin_edit_table.html` are explicitly out of scope.
- **Breaking Tailwind purge:** If adding a new `text-brand-500` class to a template, Tailwind's content scan covers `./templates/**/*.html`, so any new class will be included in the next `npm run build`. No additional config needed.
- **Mixing CSS vars and Tailwind in ambiguous contexts:** SVG `stroke` only works with `currentColor` via Tailwind's `text-*` parent. Never use `stroke="var(--color-accent)"` — SVG attributes do not resolve CSS vars.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Brand gold in JS | A hardcoded hex constant | `getComputedStyle(document.documentElement).getPropertyValue('--color-accent')` | Keeps JS in sync with CSS; no duplication |
| SVG colored icons | `fill="#c9a227"` attribute | `currentColor` + parent `class="text-brand-500"` | SVG presentation attrs cannot use CSS vars; `currentColor` bridges the gap |
| Alert box colors | New CSS classes with hex | Existing `var(--color-status-*-bg)` tokens | All status background/border/text triples already defined in input.css |

---

## Common Pitfalls

### Pitfall 1: SVG Stroke Attribute Cannot Use CSS Vars
**What goes wrong:** Setting `stroke="var(--color-accent)"` — the browser treats this as a literal string, not a CSS var, so the stroke renders as an invalid color (often black or none).
**Why it happens:** SVG presentation attributes (like `stroke=""`) are not CSS properties — they do not participate in the cascade and cannot resolve `var()` syntax.
**How to avoid:** Always use `stroke="currentColor"` and control the color via the `color` CSS property on the SVG element or a parent, e.g., `class="text-brand-500"`.
**Warning signs:** SVG icon appears black or invisible after "replacement."

### Pitfall 2: `getComputedStyle` Called Before DOM/Styles Load
**What goes wrong:** Reading `--color-status-in-progress` at the top of a `<script>` block returns an empty string because the stylesheet hasn't been applied yet.
**Why it happens:** `<script>` in `<head>` or at the start of `<body>` runs before stylesheets finish loading.
**How to avoid:** Read CSS vars inside the function that needs them (lazy read), or inside a `DOMContentLoaded` listener. The `updateCoverage` function in calendar.html is called at runtime, so reading inside the function body is safe.
**Warning signs:** Coverage bar shows no color after replacement.

### Pitfall 3: `#333` vs `var(--color-ink)` Visual Delta
**What goes wrong:** `--color-ink: #1a1a1a` is darker than `#333333`. Replacing button hover backgrounds changes the visual shade slightly.
**Why it happens:** `#333` (51,51,51) is perceptibly lighter than `#1a1a1a` (26,26,26).
**How to avoid:** This is acceptable — the delta is small and the button hover is a non-primary visual state. Accept the minor shift as part of the cleanup. If visual fidelity is critical for a specific template, add a comment explaining the decision.
**Warning signs:** Code review comment about button hover shade — document the decision.

### Pitfall 4: Alert Border Colors Have No Token
**What goes wrong:** `#fecaca` (red border), `#86efac` (green border), `#bbf7d0` (light green border) appear in alert boxes but no `--color-*-border` tokens exist.
**Why it happens:** `input.css` defines `-bg` and `-badge` variants but not `-border` variants for status colors.
**How to avoid:** Per Claude's Discretion, either (a) add missing border tokens to `input.css` (clean but Phase 1-style work), or (b) keep the handful of border hex values with a `/* no token */` comment. Option (b) is lower risk for this phase. Document the decision in PLAN.md.
**Warning signs:** Large number of hex values remaining after cleanup — check if they are all border colors.

### Pitfall 5: History Entity Colors Have No Matching Tokens
**What goes wrong:** `history/list_refined.html` has 9 hex occurrences for entity type badges (`#6a1b9a`, `#00796b`, `#e65100`, `#1565c0`, `#4a148c`, `#424242`). None of these map to existing tokens.
**Why it happens:** Entity-type badge colors are a bespoke local palette not part of the global system.
**How to avoid:** Per Claude's Discretion, these are intentional local semantic colors. Document as `/* intentional: entity-type badge palette */` and exclude from replacement. The COL-01 requirement targets auth/form/error templates — history/list_refined is not in the primary COL-01 scope.
**Warning signs:** Success criteria check "Searching templates for `#c9a227` and `#d97706` returns zero results" — history/list_refined.html contains neither, so it does not affect the success criteria even if its other hex values remain.

---

## Code Examples

### getComputedStyle CSS Var Read (calendar.html)
```javascript
// Source: MDN Web Docs — CSS custom properties
function updateCoverage(percent) {
    const coverageValue = document.getElementById('coverageValue');
    const coverageFill = document.getElementById('coverageFill');

    if (coverageValue && coverageFill) {
        coverageValue.textContent = Math.round(percent) + '%';
        coverageFill.style.width = percent + '%';

        // Read from CSS vars — stays in sync with design tokens
        const root = document.documentElement;
        const style = getComputedStyle(root);
        const colorGreen   = style.getPropertyValue('--color-status-completed').trim();
        const colorOrange  = style.getPropertyValue('--color-status-in-progress').trim();
        const colorRed     = style.getPropertyValue('--color-status-cancelled').trim();

        if (percent >= 80) {
            coverageFill.style.background = colorGreen;
        } else if (percent >= 50) {
            coverageFill.style.background = colorOrange;
        } else {
            coverageFill.style.background = colorRed;
        }
    }
}
```

### SVG stroke via currentColor (users/list.html)
```html
<!-- Source: Tailwind CSS docs — SVG fills/strokes via currentColor -->
<div class="flex items-center justify-center flex-shrink-0 text-brand-500"
     style="width: 2.5rem; height: 2.5rem; border-radius: 2px; background: var(--color-accent-muted);">
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24"
         stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/>
    </svg>
</div>
```

### Alert box using existing status tokens
```html
<!-- auth/change_password.html pattern — before -->
<style>
    .alert-error { background: #fef2f2; border: 1px solid #fecaca; color: var(--color-error); }
    .alert-success { background: #dcfce7; border: 1px solid #86efac; color: var(--color-success); }
</style>

<!-- After — using available tokens for backgrounds; border hex kept (no token) -->
<style>
    .alert-error { background: var(--color-status-cancelled-bg); border: 1px solid #fecaca; /* no border token */ color: var(--color-error); }
    .alert-success { background: var(--color-status-confirmed-bg); border: 1px solid #86efac; /* no border token */ color: var(--color-success); }
</style>
```

### Button hover dark using CSS var
```css
/* Before — 17 files use this pattern */
.refined-btn-primary:hover { background: #333; }

/* After */
.refined-btn-primary:hover { background: var(--color-ink); }
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected — this phase has no automated tests |
| Config file | none — grep-based verification |
| Quick run command | `grep -r "#c9a227\|#d97706" templates/ --include="*.html" \| grep -v superadmin_edit` |
| Full suite command | `grep -r "#[0-9a-fA-F]\{6\}\|#[0-9a-fA-F]\{3\}\b" templates/ --include="*.html" \| grep -v superadmin_edit \| wc -l` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COL-01 | No `#c9a227` or `#d97706` in in-scope templates | smoke grep | `grep -rn "#c9a227\|#d97706" templates/ --include="*.html" \| grep -v superadmin_edit` — must return empty | N/A — grep is the test |
| COL-02 | `brand-*` Tailwind utilities or `var(--color-accent)` replace `#c9a227` inline | smoke grep | Same as COL-01 | N/A |

### Sampling Rate
- **Per task commit:** Run the COL-01 grep command above — must return zero results for changed files
- **Per wave merge:** Full hex count grep on entire `templates/` directory
- **Phase gate:** Both COL-01 and COL-02 grep commands return zero before `/gsd:verify-work`

### Wave 0 Gaps
None — no test framework setup required; verification is grep-based by nature of the task.

---

## Open Questions

1. **Alert border hex (`#fecaca`, `#86efac`, `#bbf7d0`) — replace or leave?**
   - What we know: No `--color-*-border` tokens exist in `input.css`
   - What's unclear: Whether adding border tokens is in scope (Phase 1-style work) or out of scope for this phase
   - Recommendation: Leave with `/* no border token */` comment. Adds zero new tokens, zero risk. Document as edge case in PLAN.md.

2. **`history/list_refined.html` entity badge hex — in or out of COL-01 scope?**
   - What we know: 9 occurrences of entity-type-specific hex; none are `#c9a227` or `#d97706`; no matching tokens exist
   - What's unclear: The COL-01 requirement says "auth, form, error templates" — history is arguably not in this list
   - Recommendation: Out of scope for Phase 3. Document as intentional local palette.

3. **`invoices/upload.html:254` `#1f5a3a` and `sellers/edit.html:195` `#7d5500` — no matching tokens**
   - What we know: These are one-off colors in specific UI contexts
   - What's unclear: Whether they should be consolidated or left as-is
   - Recommendation: Per Claude's Discretion, add `/* no token — intentional */` comment and leave. COL-01 success criteria only checks for `#c9a227` and `#d97706`.

---

## Sources

### Primary (HIGH confidence)
- Direct grep of `templates/` directory — confirmed all hex occurrences and locations
- `static/css/input.css` — authoritative token list, all `--color-*` vars verified
- `tailwind.config.js` — `brand-500: '#c9a227'` confirmed
- `03-CONTEXT.md` — locked decisions confirmed

### Secondary (MEDIUM confidence)
- MDN Web Docs pattern for `getComputedStyle` CSS var reads — standard API, widely documented
- Tailwind CSS `currentColor` SVG pattern — official Tailwind docs pattern

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tokens verified by direct file read of input.css and tailwind.config.js
- Architecture: HIGH — patterns confirmed by existing usage in `invoices/list_refined.html` reference template
- Pitfalls: HIGH — all pitfalls derived from concrete evidence in the codebase (SVG attr limitation, getComputedStyle timing)

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (stable CSS domain, no expected churn)
