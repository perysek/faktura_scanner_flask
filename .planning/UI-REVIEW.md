# UI Review — MyWay Nails & Beauty (Re-Audit)

**Audited:** 2026-03-18
**Previous audit:** 2026-03-16 — scored 15/24
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md exists)
**Screenshots:** Not captured — no dev server running on localhost:3000/5000/5173/8080
**Scope:** 52 HTML templates, tailwind.config.js, static/css/input.css

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 3/4 | All major diacritic regressions fixed; one instance remains in sellers/edit.html |
| 2. Visuals | 3/4 | Hardcoded appointment_id=1 fixed; sidebar click-to-toggle wired; icon-only buttons still lack aria-label |
| 3. Color | 3/4 | brand-500 gold token added to tailwind.config.js; 689 hardcoded hex values remain; brand tokens unused in templates |
| 4. Typography | 2/4 | 45 of 52 templates re-declare :root font sizes; page-title varies 1.375–1.75rem across calendar/content pages; custom sub-px sizes persist |
| 5. Spacing | 3/4 | !important overrides on #main-content padding found in 14+ templates; inconsistent max-width between pages (800–1600px) |
| 6. Experience Design | 3/4 | Keyboard shortcuts (Ctrl+S, Esc) added to forms; sidebar click-to-toggle added; aria coverage still near-zero; 404 CTA routes to invoices_list not dashboard |

**Overall: 17/24** (up from 15/24)

---

## Changes Since Previous Audit

### Improvements
- **Critical bug fixed:** `sidebar.html` line 186 now uses `url_for('main.superadmin_edit_latest')` instead of the hardcoded `appointment_id=1` route. Active state detection also includes the new route endpoint.
- **Sidebar click-to-toggle added:** `sidebar.html` lines 295–310 wire a `click` event listener on each `.sidebar-section-header` with proper expand/collapse and `section.dataset.active` state tracking. The previous audit flagged this as non-functional.
- **Sidebar role labels humanized:** `sidebar.html` line 226 now renders a dict mapping (`'superuser': 'Superadmin'`, `'accountant': 'Księgowa'`, `'receptionist': 'Recepcjonistka'`, `'stylist': 'Stylistka'`) instead of the raw `current_user.role | capitalize`.
- **Missing diacritics substantially fixed:** The previous audit found 12+ instances across `dashboard/index.html` and `settings/email.html`. Current grep across all 52 templates finds only one remaining instance (`sellers/edit.html` line 445: `"Ladowanie..."`).
- **Gold brand token added to Tailwind:** `tailwind.config.js` lines 30–41 add a `brand` color scale with `brand-500: '#c9a227'`. The comment explicitly notes it matches `--color-accent` in content pages.
- **`appointments/list.html` date parsing fixed:** `getDateFromInput()` uses `new Date(dateStr + 'T12:00:00')` to avoid UTC timezone offset — consistent with the project's date handling guidance.

### Regressions / Unchanged Problems
- The 689 hardcoded hex color occurrences remain unchanged — the `brand-*` tokens were added to the config but are not used in any template yet.
- The 45-of-52 templates pattern of per-template `:root` CSS variable blocks is unchanged.
- Accessibility (aria coverage) remains near-zero across content pages.

---

## Top 3 Priority Fixes

1. **Adopt the brand-* Tailwind tokens in templates** — The gold `brand-500` (#c9a227) token exists in `tailwind.config.js` but zero templates use it. Every content page that references `var(--color-accent)` in JavaScript-generated DOM or inline color strings (`#c9a227`, `#d97706`) should be updated to use `brand-*` utilities. This reduces the hardcoded hex count from 689, makes the gold accent theme-changeable in one place, and resolves the two-system color inconsistency. Start with `invoices/list_refined.html`, `dashboard/index.html`, and `sellers/list_refined.html`.

2. **Extract the shared :root CSS block into static/css/input.css** — 45 of 52 templates declare an identical or near-identical `:root { --color-ink: ... }` block. Any future brand-color change requires editing ~45 files. Move the shared custom properties into `input.css` under `@layer base { :root { ... } }`. Templates that need page-specific overrides can still declare them locally. This also eliminates the `!important` fights between `base.html`'s `<main class="p-2">` and each page's `#main-content { padding: 1rem 1.5rem !important }`.

3. **Add aria-label to all icon-only buttons** — Calendar pagination buttons (`prevDayBtn`, `nextDayBtn`, `prevEmployeesBtn`, `nextEmployeesBtn` in `calendar.html` lines 209–238) use `title` attributes which are tooltip-only and do not serve screen readers. The analytics dashboard period navigation buttons (`prevPeriod`, `nextPeriod` in `analytics/dashboard.html` lines 17–29) have `title` but no `aria-label`. Fix: add `aria-label="Poprzedni dzień"` (etc.) to each button alongside the existing `title`. Also add `aria-label` to the confirm modal close `×` button (`confirm_modal.html` line 27) and the flash message dismiss button (`flash_messages.html` line 31).

---

## Detailed Findings

### Pillar 1: Copywriting (3/4)

**Improvement since last audit:** The 12+ missing-diacritic strings in `dashboard/index.html` and `settings/email.html` have been corrected. The `sellers/list_refined.html` errors cited in the previous audit (`Blad ladowania sprzedawcow`, `Blad usuwania`, etc.) are also fixed.

**One remaining instance:**

- `templates/sellers/edit.html` line 445: `"Ladowanie..."` should be `"Ładowanie..."` — this is the only remaining missing-diacritic issue found across all 52 templates.

**Strong copy patterns found across the full template set:**

- Appointment form `create.html` uses `"Zarezerwuj wizytę"` (not generic "Submit") and `"Zapisywanie..."` feedback during save
- Error recovery messages are specific: "Nie udało się połączyć z serwerem. Spróbuj ponownie." (`appointments/create.html` line 259)
- Empty states are contextual: `"Brak wizyt w wybranym zakresie"`, `"Nie znaleziono klientów"`, `"Ładowanie klientów..."` (clients/list.html)
- The `forgot_password.html` copy is careful — it uses a neutral notice to avoid email enumeration: "Jeśli konto z podanym adresem istnieje, poniżej znajdziesz link..." (line 219)
- Status labels are consistent across all calendar/list/view pages: `STATUS_LABELS` object is defined locally in each template with identical Polish values

**Minor observations:**

- `404.html` "Powrót do strony głównej" button routes to `main.invoices_list`, not an actual home/dashboard. For non-accountant roles (receptionists, stylists) who have no access to invoices, this button will result in a redirect or permission error. A more universal CTA would route to `main.dashboard`.
- `analytics/dashboard.html` "Idź na początek" back-to-top button label is functional but slightly informal; "Powrót na górę" is more consistent with the app's formal-register copy.

---

### Pillar 2: Visuals (3/4)

**Improvements since last audit:**

- The hardcoded `appointment_id=1` bug in the sidebar "Admin Wizyty" link is fixed.
- Sidebar section headers now have JavaScript-driven click-to-toggle (`sidebar.html` lines 295–310). `header.style.cursor = 'pointer'` is set programmatically, overriding the template's `cursor-default`.

**Remaining issues:**

**Calendar icon-only buttons lack aria-label**

`appointments/calendar.html` lines 209–238: four navigation buttons (`prevEmployeesBtn`, `nextEmployeesBtn`, `prevDayBtn`, `nextDayBtn`) have only `title` attributes. Titles are hover-tooltip only and not announced by screen readers. Same pattern in `analytics/dashboard.html` lines 17, 25 (`prevPeriod`, `nextPeriod`).

**Confirm modal close button has no accessible label**

`components/confirm_modal.html` line 27: the close `×` button (`<button type="button" onclick="closeConfirmModal()">`) has no `aria-label` or visible text. The SVG path is purely decorative without a label.

**Flash messages dismiss button lacks accessible label**

`components/flash_messages.html` line 31: the `×` dismiss button (`<button onclick="this.parentElement.remove()">`) has no `aria-label`.

**Superadmin edit page has its own visual language**

`appointments/superadmin_edit.html` defines a distinct "Power Panel" theme (dark `#0f0f0f` background, blue accent `--pp-blue`, compact typography) that intentionally differs from the app's "Refined Minimal" aesthetic. This is a conscious design choice for a superuser-only tool and is not a defect, but it means the superadmin experience is visually discontinuous with the rest of the app.

**Visual hierarchy is strong overall**

The shared pattern of `page-title` (1.75rem, weight 600) + `page-subtitle` (0.8125rem, weight 300) + stat cards + table/calendar is consistent across clients, employees, services, and appointment list pages. The `client-avatar` blue gradient is repeated across `clients/list.html` and `clients/view.html` consistently.

---

### Pillar 3: Color (3/4)

**Improvement since last audit:**

`tailwind.config.js` lines 30–41 add the `brand` color scale:
```
brand-500: '#c9a227'   // Gold accent — matches --color-accent in content pages
```
The config comment explicitly calls out the mapping. This is the correct structural fix.

**Not yet applied:**

Despite the token existing in the config, zero templates reference `brand-*` utilities. All gold usages are still hardcoded:
- `--color-accent: #c9a227` in `:root` blocks across `invoices/list_refined.html`, `sellers/list_refined.html`, `history/list_refined.html`, `dashboard/index.html`, `auth/login.html`, `auth/profile.html`, `auth/forgot_password.html`, `auth/reset_password.html`, `users/list.html`
- `#c9a227` and `#d97706` inline in JS-generated appointment block HTML (`calendar.html` lines 97, 633)

**Hardcoded hex count:** 689 occurrences across all templates (unchanged from previous audit).

**The two color systems are structurally still present:**

| System | Used by | Accent color |
|--------|---------|-------------|
| Tailwind `primary-*` | `sidebar.html`, `flash_messages.html`, `confirm_modal.html` | Blue (#3b82f6) |
| CSS `--color-accent` | All 9 content-page templates that set it | Gold (#c9a227) |

The `brand-*` token in `tailwind.config.js` bridges the gap structurally, but the bridge is not yet used in HTML.

**What works well:**

The semantic appointment status color model (blue=scheduled, green=confirmed, amber=in-progress, dark-green=completed, red=cancelled) is consistent across `calendar.html`, `list.html`, `view.html`, and `edit.html`. Both the CSS class-based `.status-badge` and the JavaScript-generated `appointment-block` colors use the same values.

---

### Pillar 4: Typography (2/4)

**Score unchanged from previous audit.**

**Per-template :root blocks create a fragmented type scale:**

45 of 52 templates define their own `:root { ... }` block. Most include font-size declarations for classes like `.page-title`, `.page-subtitle`, `.stat-value`. These are not shared via a stylesheet; they are copied into each template. The practical effect is:

| Class | Declared sizes found |
|-------|---------------------|
| `.page-title` | `1.375rem` (week/month calendars), `1.5rem` (dashboard, invoices, history, create), `1.75rem` (list pages, forms) |
| `.page-subtitle` | `0.8125rem` (most pages), `0.75rem` (week/month calendars) |
| `.stat-value` | `1.25rem` (dashboard), `1.5rem` (income), `1.75rem` (clients, employees, services) |
| `.stat-label` | `0.6875rem` (most pages), `0.75rem` (clients) |

Three pages (week calendar, month calendar) use `page-title: 1.375rem` while all other pages use `1.75rem` — creating a perceivable headline inconsistency when navigating between Wizyty views.

**Sub-Tailwind font sizes persist:**

The following sizes are below the Tailwind `text-xs` (0.75rem) threshold:
- `0.6875rem` — table header cells, stat labels (appears in ~15 templates)
- `0.625rem` — calendar appointment details, employee stat dots
- `0.5625rem` — appointment status badges in calendar blocks

These do not break readability but cannot be managed through the Tailwind scale without arbitrary values.

**Tailwind font classes found in templates:**

| Class | Count |
|-------|-------|
| `text-sm` | 70 |
| `text-xs` | 29 |
| `text-lg` | 27 |
| `text-2xl` | 11 |
| `text-xl` | 2 |
| `text-base` | 1 |
| `text-3xl` | 1 |

The `text-lg` count (27) is driven largely by the analytics dashboard which uses Tailwind directly rather than custom CSS. The analytics page is the only content page that uses Tailwind classes for typography — all other content pages use custom CSS `font-size` declarations.

**Font weights:**

| Class | Count |
|-------|-------|
| `font-medium` | 52 |
| `font-semibold` | 23 |
| `font-bold` | 1 |

Three weights in the Tailwind-class system. However, per-page CSS also declares `font-weight: 600` (semibold) and `font-weight: 300` (light) via custom properties, meaning there are effectively 4 weights in use across the system, mixed between two authoring approaches.

---

### Pillar 5: Spacing (3/4)

**Score unchanged from previous audit.**

**!important padding overrides in 14+ templates:**

The layout `base.html` line 44 sets `<main class="flex-1 overflow-auto p-2" id="main-content">`. Pages that need different padding override this with:
```css
#main-content { padding: 1rem 1.5rem !important; overflow: hidden !important; }
```
This pattern appears in: `dashboard/index.html`, `invoices/list_refined.html`, `invoices/create.html`, `invoices/edit.html`, `sellers/list_refined.html`, `history/list_refined.html`, `auth/profile.html`, `auth/change_password.html`, `appointments/superadmin_edit.html`, `errors/404.html`, `errors/500.html`, and others (14+ total). The `!important` indicates a structural mismatch — the base layout's `p-2` serves as a fallback that most pages have to fight.

**max-width inconsistency across page types:**

| Template | max-width |
|----------|-----------|
| `clients/create.html` | 800px |
| `appointments/create.html`, `view.html`, `edit.html` | 900–1000px |
| `clients/list.html`, `employees/list.html`, `services/list.html` | 1400px |
| `appointments/calendar_week.html`, `calendar_month.html` | 1600px |
| `appointments/calendar.html`, `invoices/list_refined.html` | No max-width (full-width) |
| `roles/list.html` | 1200px |

There is no consistent content-width scale. Six different values across comparable pages.

**Inline `style="display: ..."` for visibility state:** 144 occurrences of inline `display` style attributes vs. class-based visibility toggling. This mixes layout decisions into JavaScript and makes CSS-only responsive overrides harder.

**Positive: appointment creation form spacing**

The `appointments/create.html` form-card system (`padding: 2rem`, `gap: 1rem` grid, `margin-bottom: 1.5rem` cards) produces comfortable vertical rhythm. The summary-box `padding: 1rem` inside cards maintains visual separation without being wasteful.

---

### Pillar 6: Experience Design (3/4)

**Improvements since last audit:**

- **Keyboard shortcuts added:** `appointments/create.html` (lines 315–329), `clients/create.html` (lines 385–399), and other form templates implement `Ctrl+S` = save and `Esc` = cancel with proper guards (does not fire when modal is open, does not fire from input/textarea focus).
- **Sidebar click-to-toggle:** Section headers now fire a `click` event to expand/collapse sections, with restore-on-leave behavior. Previously headers were hover-only.
- **`appointments/list.html` timezone-safe date parsing:** `getDateFromInput()` appends `T12:00:00` to avoid UTC midnight off-by-one bugs.

**Loading states — comprehensive coverage:**

- `appointments/list.html` initial tbody: `"Ładowanie wizyt..."` Material Icons placeholder
- `clients/list.html` initial tbody: `"Ładowanie klientów..."`
- `roles/list.html`: dedicated `#loading-state` div with `"Ładowanie..."`
- `superadmin_edit.html`: full-page `pp-loading-overlay` with spinner
- Calendar templates: `loadingOverlay` shown during API fetches

**Error states — good coverage, one UX gap:**

- All async functions in all audited templates use `try/catch` with user-facing error messages
- Error messages are now properly diacriticked: `"Błąd połączenia z serwerem"`, `"Błąd rezerwacji"`
- Gap: none of the async error states offer a retry action. The calendar day view shows `"Błąd ładowania wizyt"` but no retry button. Pattern from `dashboard/index.html` (which has a manual refresh button) is not replicated in calendar or client list pages.

**Accessibility — near-zero aria coverage (unchanged):**

The entire template suite has approximately 4 `aria-*` attributes:
- `flash_messages.html` line 9: `role="alert"` on flash notifications
- `confirm_modal.html` line 2: `aria-labelledby`, `role="dialog"`, `aria-modal="true"`

No `aria-label` on any icon-only button across the 50 content templates. No `aria-live` regions for async content updates (appointment list, client list, stat cards load silently). No skip-navigation link.

**Destructive action confirmations — well implemented:**

`confirm_modal.html` supports `danger`, `warning`, and `info` types with appropriate icon/color. Escape key closes the modal. Focus is sent to the cancel button on open (`setTimeout` focus, line 127–130). The `confirmDelete()` helper provides a consistent string "Ta operacja jest nieodwracalna." across all delete operations.

**Role-based empty states:**

`appointments/create.html` lines 166–168: when no employee is selected, the services container shows "Wybierz pracownika, aby zobaczyć dostępne usługi" rather than an empty box. When an employee with no services is selected, it shows "Brak przypisanych usług dla tego pracownika" (line 186). Both are informative.

---

## Registry Audit

Not applicable — no `components.json` found (shadcn not initialized).

---

## Files Audited

**Core layout:**
- `templates/base.html`
- `templates/components/sidebar.html`
- `templates/components/confirm_modal.html`
- `templates/components/flash_messages.html`
- `templates/components/form_fields.html`
- `templates/components/scrollable_table.html`

**Dashboard & analytics:**
- `templates/dashboard/index.html`
- `templates/analytics/dashboard.html`
- `templates/income/dashboard.html`

**Appointments (all 7):**
- `templates/appointments/calendar.html`
- `templates/appointments/calendar_week.html`
- `templates/appointments/calendar_month.html`
- `templates/appointments/list.html`
- `templates/appointments/create.html`
- `templates/appointments/edit.html`
- `templates/appointments/view.html`
- `templates/appointments/superadmin_edit.html`

**Invoices:**
- `templates/invoices/list_refined.html`
- `templates/invoices/create.html`
- `templates/invoices/edit.html`
- `templates/invoices/upload.html`

**Clients:**
- `templates/clients/list.html`
- `templates/clients/create.html`
- `templates/clients/edit.html`
- `templates/clients/view.html`

**Employees:**
- `templates/employees/list.html`

**Services:**
- `templates/services/list.html`

**Sellers:**
- `templates/sellers/list_refined.html`
- `templates/sellers/edit.html`

**Users & roles:**
- `templates/users/list.html`
- `templates/roles/list.html`

**Auth:**
- `templates/auth/login.html`
- `templates/auth/profile.html`
- `templates/auth/forgot_password.html`

**Errors:**
- `templates/errors/404.html`

**History:**
- `templates/history/list_refined.html`

**Config:**
- `tailwind.config.js`
- `static/css/input.css`
