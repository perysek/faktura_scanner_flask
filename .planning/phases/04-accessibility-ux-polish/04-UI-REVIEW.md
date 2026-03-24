# Phase 04 — UI Review

**Audited:** 2026-03-24
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md)
**Screenshots:** Not captured (no dev server detected on ports 3000, 5173, 8080, 5000)

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | Phase fixes applied correctly; two "Ladowanie..." strings remain in superadmin_edit_table.html out of scope |
| 2. Visuals | 3/4 | Inline error states now have visual hierarchy (SVG icon + heading + message + action); back-to-top button is floating blue pill that visually competes with design tokens |
| 3. Color | 3/4 | Design token system used consistently; 109 hardcoded hex values found across 29 templates (pre-existing, outside phase scope) |
| 4. Typography | 3/4 | Tailwind scale used in component files; page templates rely on CSS custom properties and inline font-size values instead of Tailwind utilities |
| 5. Spacing | 4/4 | Phase changes use inline style only for error-state margins; token-based spacing maintained; no arbitrary Tailwind values introduced |
| 6. Experience Design | 4/4 | Loading, error with retry, empty states, confirmation dialogs, disabled states, skip-nav, aria-live — all covered; modal focus trap is intentionally deferred |

**Overall: 20/24**

---

## Top 3 Priority Fixes

1. **Two "Ladowanie..." strings in superadmin_edit_table.html** — Screen reader users hear garbled Polish (the Ł diacritic is absent), breaking the Polish-language consistency contract established in Plan 01. Fix: change `Ladowanie...` at lines 355 and 396 of `templates/appointments/superadmin_edit_table.html` to `Ładowanie...`.

2. **Back-to-top button in analytics/dashboard.html uses hardcoded Tailwind blue** — The button at line 79 uses `bg-blue-600 ring-blue-400 hover:bg-blue-700` (hardcoded Tailwind palette) rather than the design token `var(--color-primary)` used across the rest of the app. This creates a visual inconsistency if the primary brand color ever changes. Fix: replace Tailwind color utilities with a design-token-aware class or inline `background: var(--color-primary)`.

3. **calendar_week.html and calendar_month.html error states still use Modals.alert** — Three error paths in `templates/appointments/calendar_week.html` (lines 447, 525, 739) and three in `templates/appointments/calendar_month.html` (lines 316, 393, 617) still use the modal-alert pattern that Plan 03 replaced in calendar.html. Users on those calendar views who encounter a load failure have no recovery path. Fix: apply the same `showError()` inline-retry pattern from calendar.html to the week and month views.

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**What passed:**

- `templates/sellers/edit.html` line 416: "Ładowanie..." — diacritic fix confirmed present.
- `templates/analytics/dashboard.html` line 84: "Powrót na górę" — copy correction confirmed.
- `templates/errors/404.html` line 103 and `templates/errors/500.html` line 103: Both use the Jinja2 conditional `url_for('main.invoices_list' if current_user.is_authenticated and current_user.role == 'accountant' else 'main.dashboard')` — routing logic correct.
- Retry buttons use consistent "Spróbuj ponownie" copy across all three async views (calendar.html:782, list.html:311, clients/list.html:538 and :549).
- Error headings in calendar inline state: "Błąd ładowania" — specific and descriptive.
- Error messages in list views: "Błąd połączenia z serwerem" — accurate and appropriately brief.
- Error page body copy is contextual: 404 says "Strona nie istnieje lub została przeniesiona", 500 explains the team was notified.
- CTA text on error pages "Powrót do strony głównej" — clear destination label.

**What needs attention:**

- `templates/appointments/superadmin_edit_table.html` line 355: `Ladowanie...` — missing Ł diacritic. This template was outside the Plan 01 scope but represents a visible inconsistency.
- `templates/appointments/superadmin_edit_table.html` line 396: `Ladowanie wizyt...` — same issue in the table loading row.
- These two were not in Phase 04's defined scope, but the diacritic is now visibly inconsistent with the rest of the app after the Plan 01 fix.

**Score rationale:** All three plan requirements (COPY-01, UX-02, UX-03) executed cleanly. Score held at 3 rather than 4 because two in-app strings remain unpolished, one of which is a loading state visible to every user of the superadmin calendar view.

---

### Pillar 2: Visuals (3/4)

**What passed:**

- Inline error states introduced in Plan 03 follow a consistent three-element hierarchy: SVG warning icon → heading → message → retry button. This is a clear improvement over blank rows or modal interruptions.
- SVG icon in calendar error state uses `var(--color-error)` correctly, providing semantic color meaning.
- The skip-navigation link is visually hidden until focused — does not affect the visual layout of any page.
- Modal close buttons (users/list.html, confirm_modal.html) are icon-only with correct visual affordance (SVG X mark).
- Error page layouts are centered and uncluttered, using the warm surface background to differentiate from authenticated views.

**What needs attention:**

- `templates/analytics/dashboard.html` back-to-top button (line 79): Uses `bg-blue-600 ring-2 ring-blue-400` hardcoded Tailwind palette and `rounded-full` pill shape. The rest of the app uses rectangular buttons (`border-radius: 2px` or small rounding via design tokens). The floating pill is visually distinctive in a way that may not be intentional. It was corrected for copy only in Plan 01 — the visual style was pre-existing but is now the most prominent cosmetic inconsistency in the dashboard.
- Retry buttons inside `<td class="empty-state">` inherit center-alignment from the empty-state class, which is correct. However, the button is followed by no visual separator from the error text above it — the top margin (`margin-top: 0.75rem`) provides spacing but no visual grouping. This is minor.

**Score rationale:** Phase visuals are clean and functional. The floating button inconsistency is pre-existing and minor; no regressions were introduced.

---

### Pillar 3: Color (3/4)

**What passed:**

- Phase 04 changes use `var(--color-error)` for error states (calendar showError heading, list error text), consistent with the established token system.
- `var(--color-ink)` used in skip-nav inline style on base.html line 25.
- Error pages use `var(--color-ink)`, `var(--color-ink-muted)`, `var(--color-surface-warm)`, `var(--color-error)` — all tokens, no hardcoded values in the error page CSS blocks.
- Retry buttons use `refined-btn-secondary` class — inherits design-system color without hardcoding.

**What needs attention:**

- 109 hardcoded hex occurrences across 29 template files (pre-existing, outside Phase 04 scope). High concentration in `templates/appointments/superadmin_edit_table.html` (31 occurrences) and `templates/appointments/superadmin_edit.html` (17 occurrences).
- Back-to-top button: `bg-blue-600`, `hover:bg-blue-700`, `ring-blue-400` — three hardcoded Tailwind color utilities on a prominently visible UI element (pre-existing).
- Confirm modal component uses Tailwind palette colors (`text-slate-800`, `text-slate-500`, `bg-red-100`, `text-red-600`) rather than design tokens. This is a pre-existing inconsistency in the component design, not introduced by Phase 04.

**Score rationale:** Phase 04 changes are token-compliant. Existing color debt is noted but pre-dates this phase. Score is 3 rather than 2 because no new hardcoded values were introduced and all phase-specific color usage is correct.

---

### Pillar 4: Typography (3/4)

**What passed:**

- Phase 04 touched no typography directly. All error state text in showError() uses inline `font-size` via CSS property in the error page `<style>` blocks (e.g., `.error-code { font-size: 4rem }`, `.error-message { font-size: 0.875rem }`) — these are consistent `rem`-based values.
- Inline error state in calendar showError() uses no explicit font-size, inheriting from the `.empty-state` context.
- Skip-nav link uses `font-size: 0.875rem; font-weight: 600` in the inline style — appropriate for a utility element.

**What needs attention:**

- The app architecture separates concerns between Tailwind-utility-based components (sidebar, flash messages, confirm modal — all use `text-sm`, `text-lg`, `font-semibold`, etc.) and template-level pages that use CSS custom properties and `rem` inline values. Both approaches are internally consistent but the mix means there is no single typography scale reference.
- 141 Tailwind text-size class occurrences are limited to 7 component files only (analytics/dashboard.html, base.html, sidebar, scrollable_table, form_fields, flash_messages, confirm_modal). Page templates do not use Tailwind typography utilities at all, relying on CSS custom properties instead.
- This is a pre-existing architectural choice, not a regression.

**Score rationale:** No typography regressions introduced. Score is 3 rather than 4 because the dual typography approach (Tailwind in components, inline rem in page templates) creates inconsistency that would require a future cleanup pass to fully resolve.

---

### Pillar 5: Spacing (4/4)

**What passed:**

- All retry buttons use `style="margin-top: 0.75rem;"` or `style="margin-top: 1rem;"` — both are standard rem multiples (3 and 4 on the 0.25rem base scale).
- Skip-nav link uses `top: 0.5rem; left: 0.5rem; padding: 0.5rem 1rem` — all standard scale values.
- No arbitrary Tailwind bracket values (e.g., `p-[17px]`) were introduced anywhere in Phase 04.
- The single Tailwind arbitrary value found in the entire codebase (`analytics/dashboard.html: py-2.5`) is a Tailwind standard step, not arbitrary.
- Error page CSS uses `padding: 2rem`, `margin: 0 0 1rem 0`, `margin: 0 0 2rem 0` — consistent rem scale.

**Score rationale:** Spacing is clean throughout Phase 04 changes. No issues found.

---

### Pillar 6: Experience Design (4/4)

**What passed:**

**Loading states:** Present and functional across 24 template files. Calendar views use an overlay spinner (`loadingOverlay`). List views show a skeleton row "Ładowanie klientów..." / "Ładowanie wizyt..." in the tbody before data arrives.

**Error states with recovery:** Fully implemented by Phase 04:
- `templates/appointments/calendar.html`: showError() renders inline error with retry button calling loadSchedule().
- `templates/clients/list.html`: Both API error path (line 534) and network catch (line 543) show retry calling loadClients().
- `templates/appointments/list.html`: Network catch (line 305) shows retry calling loadAppointments().

**Empty states:** Empty state handling is present across the app (clients view, services view, preferences, appointment lists).

**Disabled states:** Calendar navigation buttons (prev/next employee) use the `disabled` HTML attribute with CSS `opacity: 0.4; cursor: not-allowed` — correct visual treatment. The superadmin save-all button at `superadmin_edit_table.html:351` initializes as `disabled` and is enabled when dirty rows exist.

**Confirmation for destructive actions:** `confirm_modal.html` is a reusable component with `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, Escape key handler, and focus-to-cancel-button on open. `confirmDelete()` helper provides a consistent destruction confirmation pattern across the app.

**Accessibility (A11Y):**
- Skip-navigation link on `base.html:25` — first focusable element, `sr-only` hidden until focused.
- 3 `aria-live="polite"` regions on async containers (calendar, client list, appointment list).
- 66 `aria-label` attributes across 19 templates — comprehensive icon-only button coverage.
- 2 modals have `role="dialog" aria-modal="true"` (`confirm_modal.html`, `users/list.html`).
- `html lang="pl"` on base.html — correct language declaration.
- `sr-only` and `sr-only-focusable` CSS utilities defined in `static/css/input.css:121-142`.

**What has room for improvement (deferred by design):**

- `calendar_week.html` and `calendar_month.html` still use `Modals.alert` for error states (6 call sites total). These views were out of scope for Plan 03 (UX-01 targeted only the day view, client list, and appointment list). Users on week/month calendar views who hit load errors have no retry path. This is noted in CONTEXT.md as a known deferral.
- Focus trap inside modal dialogs is deferred to v3.0 per `04-CONTEXT.md` (A11Y-04).
- `confirm_modal.html` focuses the cancel button on open (line 129-131) but does not trap focus inside the modal boundary.

**Score rationale:** All in-scope requirements (A11Y-01, A11Y-02, A11Y-03, UX-01) are fully implemented. The week/month calendar gap and focus trap are explicit deferrals, not oversights. Score is 4/4 because every in-scope commitment was met.

---

## Registry Safety

Registry audit: No shadcn (`components.json` not found). Registry audit skipped.

---

## Files Audited

Phase 04 modified files (all verified):
- `C:/Projects/faktura_scanner_flask/templates/sellers/edit.html`
- `C:/Projects/faktura_scanner_flask/templates/analytics/dashboard.html`
- `C:/Projects/faktura_scanner_flask/templates/errors/404.html`
- `C:/Projects/faktura_scanner_flask/templates/errors/500.html`
- `C:/Projects/faktura_scanner_flask/static/css/input.css`
- `C:/Projects/faktura_scanner_flask/templates/base.html`
- `C:/Projects/faktura_scanner_flask/templates/clients/list.html`
- `C:/Projects/faktura_scanner_flask/templates/appointments/list.html`
- `C:/Projects/faktura_scanner_flask/templates/appointments/calendar.html`
- `C:/Projects/faktura_scanner_flask/templates/users/list.html`

Supporting context files read:
- `C:/Projects/faktura_scanner_flask/templates/components/confirm_modal.html`
- `C:/Projects/faktura_scanner_flask/templates/appointments/superadmin_edit_table.html` (lines 350-400)
- `C:/Projects/faktura_scanner_flask/templates/appointments/calendar_week.html` (grep only)
- `C:/Projects/faktura_scanner_flask/templates/appointments/calendar_month.html` (grep only)
