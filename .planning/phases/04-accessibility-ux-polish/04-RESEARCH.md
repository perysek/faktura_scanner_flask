# Phase 4: Accessibility & UX Polish - Research

**Researched:** 2026-03-24
**Domain:** HTML accessibility attributes, Jinja2 conditional rendering, JavaScript async error handling
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- All icon-only buttons (calendar navigation prev/next, modal close, flash dismiss) get `aria-label` matching visible tooltip text
- Skip-navigation link: hidden link at the top of `base.html` with `class="sr-only focus:not-sr-only"` — standard Tailwind a11y pattern, linking to `#main-content`
- `aria-live="polite"` regions on async content containers: calendar day view, client list, appointment list
- `login.html` (standalone, no sidebar) does NOT get skip-nav — not needed
- Retry button "Spróbuj ponownie" visible in error state, calls `location.reload()` or re-fetch endpoint
- Retry added to: calendar day view, client list, appointment list — per UX-01
- 404 CTA: conditional per role — accountant → `main.invoices_list`, rest → `main.dashboard` (Jinja if on `current_user.role`)
- 500 CTA: same conditional logic as 404
- `analytics/dashboard.html`: "Idź na początek" → "Powrót na górę" — per COPY-01
- `sellers/edit.html` line 416: "Ladowanie..." → "Ładowanie..." (fix missing diacritic ą) — per UX-03
- Do not scan wider for diacritics — UX-03 points specifically to these 2 files

### Claude's Discretion

- Exact implementation of retry logic (reload vs re-fetch) per-component
- Visual style of retry button (should match existing design system)
- Exact list of icon-only buttons to audit (planner identifies from codebase scout)

### Deferred Ideas (OUT OF SCOPE)

- A11Y-04 (v3.0): Focus trap in modal dialogs
- A11Y-05 (v3.0): Full screen reader test
- Retry on ALL async components (only the 3 from UX-01)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| A11Y-01 | `aria-label` on all icon-only buttons (calendar navigation, modal close, flash dismiss) | Audit findings show calendar.html already has aria-labels on day/employee nav; calendar_week.html and calendar_month.html also have them; `analytics/dashboard.html` has them on prevPeriod/nextPeriod; flash_messages.html dismiss button already has `aria-label="Zamknij powiadomienie"`; confirm_modal.html close button already has `aria-label="Zamknij okno dialogowe"` — full audit required to find gaps |
| A11Y-02 | `aria-live` regions for async content updates (appointment list, client list, stat cards) | `appointments/list.html` tbody has id `appointments-tbody`, `clients/list.html` has id `clients-tbody` — add `aria-live="polite"` to container divs wrapping these tbodies; calendar day view timeline-container needs `aria-live="polite"` |
| A11Y-03 | Skip-navigation link in `base.html` | `base.html` already has `id="main-content"` on `<main>`; skip-nav link needs to be first child of `<body>`; `sr-only` and `focus:not-sr-only` classes are NOT in compiled output.css — requires either CSS addition or safelist entry |
| UX-01 | Retry action in async error states (calendar day view, client list, appointment list) | `calendar.html` error shows `Modals.alert()` with no retry; `clients/list.html` error renders plain text in tbody; `appointments/list.html` error renders plain text in tbody — all need retry button injected into error HTML |
| UX-02 | 404 CTA routing to `main.dashboard` instead of `main.invoices_list` | Both `errors/404.html` line 103 and `errors/500.html` line 103 hardcode `main.invoices_list`; need Jinja conditional on `current_user.role` |
| UX-03 | Fix missing diacritic (`sellers/edit.html` line 416: "Ladowanie..." → "Ładowanie...") | Confirmed at `sellers/edit.html:416` — single character fix |
| COPY-01 | "Idź na początek" → "Powrót na górę" in `analytics/dashboard.html` | Confirmed at `analytics/dashboard.html:84` — single text node change |
</phase_requirements>

---

## Summary

Phase 4 is a targeted polish pass: adding ARIA attributes, one skip-nav link, retry buttons in error states, fixing two error page CTAs, and two copywriting fixes. The codebase already has 63 aria attribute occurrences across 18 files — this phase closes the remaining gaps rather than starting from scratch.

The most architecturally significant change is the skip-navigation link in `base.html`: Tailwind's `sr-only` and `focus:not-sr-only` utilities are **not** present in the compiled `output.css` (zero matches confirmed). These classes must be added either via a CSS snippet in `input.css` or by adding them to the Tailwind safelist. The safelist approach is preferred — it forces Tailwind to include these utilities without coupling them to a specific template.

The retry button pattern is the most varied: `calendar.html` routes errors through `Modals.alert()` (a modal overlay), while `clients/list.html` and `appointments/list.html` inject HTML directly into a `<tbody>`. The retry implementation must match the existing error rendering approach in each file rather than forcing a uniform pattern.

**Primary recommendation:** Address requirements in this order — (1) copywriting fixes (zero risk), (2) error page CTA routing (low risk, Jinja-only), (3) aria-labels on icon-only buttons (additive, no behavior change), (4) skip-nav + sr-only CSS (requires CSS rebuild), (5) aria-live regions (additive attribute), (6) retry buttons (requires JS changes in 3 files).

---

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | Existing (compiled) | `sr-only` / `focus:not-sr-only` utility classes | Already in project; these utilities are part of Tailwind core |
| Jinja2 | Existing Flask | Conditional CTA rendering in error templates | Project's template engine |
| Vanilla JS | Existing | Retry button event handlers | Project uses no JS framework — all existing async is plain fetch |

### No New Dependencies Required
All seven requirements are satisfied with HTML attributes, Jinja2 conditionals, and plain JavaScript. No new packages needed.

---

## Architecture Patterns

### Pattern 1: Skip Navigation Link (A11Y-03)

**What:** A visually hidden anchor that appears on focus, allowing keyboard users to bypass the sidebar navigation.

**Placement:** Must be the **first child** of `<body>` in `base.html`, before the `{% if current_user.is_authenticated %}` block. This ensures it is always first in tab order regardless of auth state.

**The `sr-only` problem:** Tailwind's `sr-only` and `focus:not-sr-only` classes are PurgeCSS'd out because they appear in no template. Two options:

Option A — Safelist in `tailwind.config.js`:
```javascript
// tailwind.config.js
module.exports = {
  safelist: ['sr-only', 'focus:not-sr-only'],
  // ... rest of config
}
```

Option B — Raw CSS in `input.css` (no Tailwind dependency):
```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
.focus\:not-sr-only:focus {
  position: static;
  width: auto;
  height: auto;
  padding: 0;
  margin: 0;
  overflow: visible;
  clip: auto;
  white-space: normal;
}
```

**Recommended:** Option B (raw CSS in `input.css`) — explicit, no reliance on Tailwind's safelist mechanics, survives future Tailwind upgrades.

**HTML in `base.html`:**
```html
<body class="h-full antialiased">
    <a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:top-2 focus:left-2 focus:px-4 focus:py-2 focus:bg-white focus:text-slate-900 focus:rounded focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-brand-500">
        Przejdź do treści
    </a>
    {% if current_user.is_authenticated %}
    ...
```

Note: The `focus:absolute`, `focus:z-50`, etc. classes depend on whether those Tailwind variants are in `output.css`. A simpler approach is inline styles on the focused state, or just define everything in the `.sr-only` / `.focus:not-sr-only` raw CSS block.

### Pattern 2: aria-live Regions (A11Y-02)

**What:** An `aria-live="polite"` attribute on the container of dynamically updated content announces changes to screen readers.

**Rule:** Apply the attribute to the container element, not to individual items inside it. The container must exist in the DOM at page load — dynamically injected containers are not detected by screen readers.

**For `clients/list.html`:**
```html
<!-- Clients Table -->
<div class="table-container" aria-live="polite" aria-label="Lista klientów">
    <table class="refined-table">
        ...
        <tbody id="clients-tbody">
```

**For `appointments/list.html`:**
```html
<div class="table-container" aria-live="polite" aria-label="Lista wizyt">
    <table class="refined-table">
        ...
        <tbody id="appointments-tbody">
```

**For calendar day view (`calendar.html`):**
The existing `#emptyState` and the `timeline-container` hold the dynamic content. Wrap or annotate the `timeline-container`:
```html
<div class="timeline-container" aria-live="polite" aria-label="Harmonogram dnia">
```

### Pattern 3: Retry Button in Error States (UX-01)

**Three different error rendering approaches in scope:**

**calendar.html** — errors currently route through `Modals.alert()`:
```javascript
// Current (no retry)
function showError(message) {
    Modals.alert({ title: 'Błąd', message: message, type: 'error' });
}
```
Change to render an inline error state in `#emptyState` instead of a modal — this is more consistent with the aria-live pattern (modal popups are not announced by the aria-live region):
```javascript
function showError(message) {
    emptyState.style.display = 'block';
    emptyState.innerHTML = `
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <h3 style="color: var(--color-error);">Błąd ładowania</h3>
        <p>${escapeHtml(message)}</p>
        <button onclick="loadSchedule()" class="refined-btn-secondary" style="margin-top:1rem;">Spróbuj ponownie</button>
    `;
}
```

**clients/list.html** — errors currently inject HTML into `<tbody>`:
```javascript
// In catch block — add retry button to the error row
tbody.innerHTML = `
    <tr>
        <td colspan="6" class="empty-state">
            <p class="empty-text" style="color:var(--color-error);">Błąd połączenia z serwerem</p>
            <button onclick="loadClients()" class="refined-btn-secondary" style="margin-top:0.75rem;">Spróbuj ponownie</button>
        </td>
    </tr>
`;
```

**appointments/list.html** — same pattern:
```javascript
// In catch block — add retry button to the error row
tbody.innerHTML = `<tr><td colspan="9" class="empty-state">
    <p class="empty-text" style="color:var(--color-error);">Błąd połączenia z serwerem</p>
    <button onclick="loadAppointments()" class="refined-btn-secondary" style="margin-top:0.75rem;">Spróbuj ponownie</button>
</td></tr>`;
```

### Pattern 4: Conditional CTA in Error Pages (UX-02)

Both `errors/404.html` and `errors/500.html` currently hardcode `main.invoices_list` at line 103.

**404.html and 500.html replacement:**
```html
<a href="{{ url_for('main.invoices_list' if current_user.is_authenticated and current_user.role == 'accountant' else 'main.dashboard') }}" class="btn-refined">
    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
    </svg>
    Powrót do strony głównej
</a>
```

This uses Jinja2 inline conditional — no `{% if %}` block needed. `current_user` is available on error pages because both templates extend `base.html` and Flask-Login injects `current_user` into the Jinja context globally.

**Verification needed:** Confirm that `current_user` is accessible in error handler templates. Flask error handlers registered with `@app.errorhandler` may not have the full request context in all configurations — test this. If `current_user` is unavailable, use:
```html
{% if current_user.is_authenticated %}
    {% if current_user.role == 'accountant' %}
        {% set cta_url = url_for('main.invoices_list') %}
    {% else %}
        {% set cta_url = url_for('main.dashboard') %}
    {% endif %}
{% else %}
    {% set cta_url = url_for('auth.login') %}
{% endif %}
<a href="{{ cta_url }}" class="btn-refined">...</a>
```

### Recommended Edit Sequence

```
Wave 1 (zero-risk text changes):
  sellers/edit.html line 416: "Ladowanie..." → "Ładowanie..."
  analytics/dashboard.html line 84: "Idź na początek" → "Powrót na górę"

Wave 2 (Jinja-only changes):
  errors/404.html line 103: conditional CTA
  errors/500.html line 103: conditional CTA

Wave 3 (HTML attribute additions):
  input.css: add .sr-only and .focus:not-sr-only CSS
  base.html: insert skip-nav link as first child of <body>
  Audit + add aria-label to any icon-only buttons missing it
  Add aria-live="polite" to clients/list.html, appointments/list.html, calendar.html containers

Wave 4 (JavaScript changes):
  calendar.html: replace Modals.alert() with inline error + retry button
  clients/list.html: add retry button to catch block error HTML
  appointments/list.html: add retry button to catch block error HTML
```

### Anti-Patterns to Avoid

- **aria-live on `<body>`:** Too broad — announces every DOM change on the page. Apply only to the specific async container.
- **aria-live="assertive":** Interrupts the screen reader mid-sentence. Use `polite` for data updates.
- **Skip-nav after sidebar HTML:** If the skip link is not the first focusable element, keyboard users still tab through the entire sidebar before reaching it.
- **`sr-only` without defining it:** Tailwind PurgeCSS removes unused utilities — the class must be defined in CSS or safelisted.
- **Retry button inside `<thead>`:** Buttons inside table headers cause invalid HTML. Retry buttons belong in `<td>` cells or in a container outside the `<table>`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Screen reader announcements | Custom JS announcement system | Native `aria-live` HTML attribute | Browser AT integration; JS solutions are unreliable across AT/browser combos |
| Skip navigation styling | Custom CSS from scratch | Tailwind sr-only pattern (or verbatim CSS above) | Well-tested, matches browser AT expectations |
| Focus management | Custom tabIndex manipulation | Standard link/button focus flow | Native focus order is more reliable than JS-managed focus |

**Key insight:** All a11y requirements in this phase are satisfied with standard HTML attributes and CSS patterns. No JS library is needed.

---

## Common Pitfalls

### Pitfall 1: sr-only Not Applied (A11Y-03)
**What goes wrong:** Skip-nav link renders visually at all times (no `sr-only` defined) or `focus:not-sr-only` has no effect.
**Why it happens:** Tailwind PurgeCSS removes `sr-only` from output.css because no template uses it at build time.
**How to avoid:** Add the raw CSS to `input.css` before using the class in any template. Run `npm run build` (or equivalent) to regenerate `output.css`.
**Warning signs:** Skip link is visible on page or doesn't appear on keyboard focus.

### Pitfall 2: aria-live on Dynamically Injected Container
**What goes wrong:** `aria-live` attribute is added to a container that is itself injected by JavaScript — screen readers do not observe it.
**Why it happens:** AT registers `aria-live` regions at page load. Elements added after load are not monitored.
**How to avoid:** The container (`table-container`, `timeline-container`) must exist in the initial HTML. Only the content inside it changes — confirmed in this codebase.

### Pitfall 3: current_user in Flask Error Handlers
**What goes wrong:** `current_user` is undefined in the 404/500 Jinja context, causing a template rendering error.
**Why it happens:** Flask error handlers may bypass Flask-Login's before_request hooks depending on configuration.
**How to avoid:** Test the rendered 404 page as both authenticated and unauthenticated user before committing. If `current_user` raises an error, use `current_user.is_authenticated` check (Flask-Login always provides the proxy, even if the user is anonymous).

### Pitfall 4: Retry Button in tbody Breaks Validator
**What goes wrong:** HTML validator reports error; some browsers reorder table content.
**Why it happens:** `<button>` inside `<td>` is valid HTML5, but `<button>` inside `<tbody>` directly (outside `<td>`) is invalid.
**How to avoid:** Retry button must be inside `<td>`, which it is in all three patterns above. Confirmed correct.

### Pitfall 5: aria-label Text Mismatch with Tooltip
**What goes wrong:** Screen reader announces different text than sighted users see in tooltip.
**Why it happens:** `title` and `aria-label` are set independently and get out of sync.
**How to avoid:** A11Y-01 requires exact match — when `title="Poprzedni miesiąc"`, set `aria-label="Poprzedni miesiąc"`. Audit must check both attributes together.

---

## Code Examples

### Skip Navigation (verified standard pattern)
```html
<!-- First child of <body> in base.html -->
<a href="#main-content" class="sr-only focus:not-sr-only">
    Przejdź do treści
</a>
```

```css
/* In static/css/input.css — add after @tailwind utilities; */
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border-width: 0;
}
.focus\:not-sr-only:focus {
    position: static;
    width: auto;
    height: auto;
    padding: 0;
    margin: 0;
    overflow: visible;
    clip: auto;
    white-space: normal;
}
```

### aria-live Region (verified standard pattern)
```html
<!-- Wrap the async container -->
<div class="table-container" aria-live="polite" aria-label="Lista klientów">
    <table class="refined-table">
        <tbody id="clients-tbody">
            <!-- JS injects here -->
        </tbody>
    </table>
</div>
```

### Existing Icon Button (already correct — reference pattern)
```html
<!-- From calendar.html line 215 — model for all icon-only buttons -->
<button id="prevDayBtn" class="refined-btn-secondary"
        title="Poprzedni dzień"
        aria-label="Poprzedni dzień"
        style="flex-shrink: 0;">
    <svg ...>...</svg>
</button>
```

---

## Existing ARIA Audit Findings

Current state from codebase scan:

| Template | Already Has aria-label | Gaps Found |
|----------|----------------------|------------|
| `flash_messages.html` | Dismiss button: `aria-label="Zamknij powiadomienie"` | None |
| `confirm_modal.html` | Close button: `aria-label="Zamknij okno dialogowe"` | None |
| `calendar.html` | prevDayBtn, nextDayBtn, prevEmployeesBtn, nextEmployeesBtn | No aria-live on timeline |
| `calendar_week.html` | prevWeekBtn, nextWeekBtn, prevEmployeeBtn, nextEmployeeBtn | No aria-live |
| `calendar_month.html` | prevMonthBtn, nextMonthBtn, prevEmployeeBtn, nextEmployeeBtn | No aria-live |
| `analytics/dashboard.html` | prevPeriod, nextPeriod (lines 29, 37) | No aria-live on KPI sections |
| `clients/list.html` | None found | No aria-live on table container |
| `appointments/list.html` | 2 occurrences (need audit) | No aria-live on table container |

**Net finding for A11Y-01:** `flash_messages.html` and `confirm_modal.html` already comply. Calendar templates already have icon button aria-labels. The planner should audit remaining templates for any icon-only buttons without aria-label.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `role="button"` on `<div>` | Native `<button>` element | Project already uses native buttons — no change needed |
| `tabindex="0"` on non-interactive elements | Semantic HTML | Not in scope for this phase |
| Skip nav via `display:none` | `sr-only` pattern | `display:none` is not focusable — must use clip/position trick |

---

## Open Questions

1. **`current_user` availability in error handler templates**
   - What we know: Both 404.html and 500.html extend `base.html` and use `current_user` (base.html has `{% if current_user.is_authenticated %}`), so it must be available — the pages already render correctly with this construct
   - What's unclear: Whether Flask-Login's proxy behaves identically in error handlers as in normal routes
   - Recommendation: Test by navigating to a 404 as both authenticated and unauthenticated — if base.html renders without error today, the Jinja conditional will work

2. **CSS rebuild requirement for sr-only**
   - What we know: `sr-only` is not in `output.css`; the project uses Tailwind with a `content` array pointing at templates and JS files
   - What's unclear: Whether there is a watch/build script available (`npm run build` or similar)
   - Recommendation: Planner should include a "rebuild CSS" step after adding `sr-only` to `input.css`, with the command `npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify` or equivalent from package.json scripts

3. **calendar.html retry UX — modal vs inline**
   - What we know: Current error uses `Modals.alert()` modal; proposed change replaces it with inline error in `#emptyState`
   - What's unclear: Whether `Modals.alert()` behavior is intentional (e.g., forces acknowledgment) or incidental
   - Recommendation: Use inline error state — it is more accessible (aria-live region announces it), dismissable by just loading new data, and consistent with the other two retry patterns

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None detected — no pytest.ini, jest.config, or test directories found |
| Config file | None — Wave 0 gap |
| Quick run command | Manual browser test |
| Full suite command | Manual browser test |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| A11Y-01 | Icon-only buttons have matching aria-label and title | manual | View source, check attributes | N/A |
| A11Y-02 | Async content containers have aria-live="polite" | manual | View source, verify attribute on container | N/A |
| A11Y-03 | Skip-nav link is first in DOM and focusable with keyboard | manual | Tab from address bar, first focus should be skip link | N/A |
| UX-01 | "Spróbuj ponownie" button appears in error state; clicking it re-fetches | manual | Simulate network error (DevTools → Offline), verify retry button appears and works | N/A |
| UX-02 | Non-accountant 404 CTA links to dashboard; accountant CTA links to invoices_list | manual | Login as non-accountant, visit /nonexistent, verify CTA URL | N/A |
| UX-03 | sellers/edit.html shows "Ładowanie..." (with ą) | manual | View source or DOM inspection | N/A |
| COPY-01 | analytics/dashboard.html back-to-top button reads "Powrót na górę" | manual | View page, scroll down, verify button text | N/A |

### Wave 0 Gaps
- [ ] No automated test infrastructure — all validation is manual browser-based
- [ ] No existing test files for any of these requirements
- [ ] "None — existing test infrastructure covers all phase requirements" does NOT apply

*(Note: For a phase of this scope — HTML attributes and text changes — manual verification is appropriate and sufficient. No test framework setup is warranted.)*

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `templates/base.html`, `templates/errors/404.html`, `templates/errors/500.html`, `templates/components/flash_messages.html`, `templates/components/confirm_modal.html`, `templates/analytics/dashboard.html`, `templates/appointments/calendar.html`, `templates/appointments/calendar_week.html`, `templates/appointments/calendar_month.html`, `templates/clients/list.html`, `templates/appointments/list.html`, `templates/sellers/edit.html`
- Tailwind CSS `sr-only` utility — built-in, documented at tailwindcss.com/docs/screen-readers
- WAI-ARIA 1.2 `aria-live` specification — live region best practices
- HTML5 spec — `aria-label` on interactive elements

### Secondary (MEDIUM confidence)
- Tailwind PurgeCSS behavior — confirmed by grep of `output.css` (zero matches for `sr-only`)
- Flask-Login `current_user` proxy availability in error handlers — inferred from existing working base.html usage

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all changes are HTML/CSS/Jinja2/vanilla JS
- Architecture: HIGH — patterns verified against actual codebase code
- Pitfalls: HIGH — confirmed by direct inspection (sr-only not in output.css, error states lack retry, etc.)

**Research date:** 2026-03-24
**Valid until:** 2026-06-24 (stable HTML/ARIA patterns; no time-sensitive dependencies)
