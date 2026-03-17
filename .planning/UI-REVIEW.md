# UI Review — MyWay Nails & Beauty (Retroactive Audit)

**Audited:** 2026-03-16
**Baseline:** Abstract 6-pillar standards (no UI-SPEC.md exists)
**Screenshots:** Not captured — Playwright unavailable; Flask dev server detected at localhost:5000

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | Pervasive missing Polish diacritics across 5+ templates; dashboard error strings unpolished |
| 2. Visuals | 3/4 | Strong calendar and dashboard layouts; sidebar "Admin Wizyty" link hardcodes appointment_id=1 |
| 3. Color | 2/4 | Split design system: Tailwind primary=blue, page CSS accent=gold (#c9a227); 689 hardcoded hex values across 45 files |
| 4. Typography | 2/4 | Content pages bypass Tailwind text scale entirely with custom rem values (0.6875rem, 0.8125rem, 1.25rem) |
| 5. Spacing | 3/4 | Sidebar uses Tailwind scale cleanly; content pages use custom CSS pixel-rem values, inconsistent with base layout |
| 6. Experience Design | 3/4 | Good state coverage (loading, empty, error); sidebar section headers not keyboard-accessible; near-zero aria usage |

**Overall: 15/24**

---

## Top 3 Priority Fixes

1. **Missing Polish diacritics in user-facing strings** — Users see "Odswiez", "Oplacone", "Blad ladowania", "zagleglosci", "Najczestsi dostawcy", "Nadchodzace platnosci" — looks unfinished and unprofessional — Fix: add missing characters in `templates/dashboard/index.html` lines 373, 385, 389, 460, 476, 517, 520, 576, 607 and `templates/settings/email.html` lines 416, 421, 457

2. **Hardcoded appointment_id=1 in sidebar "Admin Wizyty" link** — Superadmin navigates to the wrong visit on every click; link is broken by design — Fix: change `url_for('main.superadmin_edit_visit', appointment_id=1)` in `sidebar.html` line 186 to a dedicated admin landing route (e.g., redirect to appointments list or a dedicated superadmin dashboard route) that does not require a hardcoded entity ID

3. **Split color design system: Tailwind blue vs. page-level gold** — Components built at different times use two unrelated accent colors; `primary` in Tailwind config resolves to blue (#3b82f6) while dashboard/invoices/calendar pages define `--color-accent: #c9a227` (gold) and render charts, badges, and hover states in that color — Fix: either extend `tailwind.config.js` with a `gold` or `brand` key that maps to `#c9a227` and use it consistently, or replace page-level `--color-accent` references with the existing Tailwind primary scale

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)

**Missing diacritics — dashboard/index.html**

The dashboard template has multiple Polish strings with missing accented characters, likely from development shortcuts. These appear in DOM text visible to all users:

- Line 373: `"Odswiez"` should be `"Odśwież"`
- Line 374 (button label): `"Odswiez dane"` (title attr) → `"Odśwież dane"`
- Line 385: `"Oplacone"` → `"Opłacone"`
- Line 389: `"Nieoplacone"` → `"Nieopłacone"`
- Line 460: `"Nadchodzace platnosci"` → `"Nadchodzące płatności"`
- Line 476: `"Najczestsi dostawcy"` → `"Najczęstsi dostawcy"`
- Line 516–517: `"Odswiezono"` / `"Odswiez"` → `"Odświeżono"` / `"Odśwież"`
- Line 520: `"Blad"` → `"Błąd"`
- Lines 576, 611, 655, 689: `"Blad ladowania"` → `"Błąd ładowania"`
- Line 607: `"Brak zagleglosci"` → `"Brak zaległości"`, `"Wszystko oplacone na czas!"` → `"Wszystko opłacone na czas!"`

**Missing diacritics — settings/email.html**

- Lines 416, 421: `"Blad zapisywania..."` → `"Błąd zapisywania..."`
- Line 457: `"Blad testowania..."` → `"Błąd testowania..."`

**sellers/list_refined.html (multiple lines)**

"Blad ladowania sprzedawcow", "Blad usuwania", "Blad synchronizacji", "Blad odswiezania" — all missing diacritics

**Positive observations:**

- Empty states use meaningful messages: "Brak wizyt w wybranym zakresie", "Brak zaplanowanych wizyt", "Wszystko opłacone na czas!"
- Calendar status labels ("Zaplanowana", "Potwierdzona", "W trakcie") are clear and domain-appropriate
- Destructive actions use "Zmień dane" / "Zapisz mimo to" rather than generic "Cancel/OK"

---

### Pillar 2: Visuals (3/4)

**Sidebar — strong implementation, one critical bug**

The sidebar hover-expand pattern is well-executed. Active section stays open, inactive sections collapse on hover. Chevron rotation provides clear affordance. User avatar with gradient initials is a polished touch.

Critical bug: `sidebar.html` line 186 — the "Admin Wizyty" link is:
```
url_for('main.superadmin_edit_visit', appointment_id=1)
```
This hardcodes entity ID 1 and will navigate to a specific (possibly unrelated) appointment on every click. This link appears in the System section visible to superusers only, but the navigation target is wrong by design.

**Sidebar section headers suggest interactivity they don't offer**

Section headers (`sidebar-section-header`) show a chevron icon that animates on expand/collapse, but the header itself has `cursor-default select-none` — click does nothing. The hover behavior only triggers on `mouseenter` of the entire `.sidebar-section` div. Users who try to click the header label to toggle will be confused.

**Dashboard visual hierarchy — good**

The dashboard layout correctly uses a full-width chart at top, then a 2-column grid of panels. Stat cards provide scannable KPIs. Loading state text (`"Ladowanie..."`) appears immediately before data loads, which is appropriate.

**Calendar — strong**

The day-view calendar with employee columns, coverage stat card, and color-coded appointment blocks provides excellent at-a-glance information density. The appointment block status colors (blue/green/amber/dark-green/red) are visually distinct.

**Icon-only buttons without labels**

Calendar pagination arrows (`prevDayBtn`, `nextDayBtn`, `prevEmployeesBtn`, `nextEmployeesBtn`) have `title` attributes but no `aria-label`. Titles require hover and don't serve screen readers reliably.

---

### Pillar 3: Color (2/4)

**Two competing accent color systems**

The Tailwind config (`tailwind.config.js` lines 13–24) defines:
- `primary-500` = `#3b82f6` (blue)
- `accent-500` = `#10b981` (green)

The sidebar uses `primary-400/500/600/700` (blue) for active states and the user avatar gradient.

Meanwhile, `dashboard/index.html`, `invoices/list_refined.html`, and `appointments/calendar.html` each define in their own `<style>` blocks:
- `--color-accent: #c9a227` (gold/amber)

This gold accent is used for:
- Chart hover bars (`hoverBackgroundColor`)
- Invoice status badges (`status-unpaid`)
- Appointment add-on text color (`#d97706` orange-adjacent)
- Coverage bar color transitions

The result is that the primary navigation chrome (sidebar) is blue while the primary content areas are gold-toned. These two systems never meet and produce a visual discontinuity at the sidebar/content boundary.

**Hardcoded hex count: 689 occurrences across 45 files**

Notable patterns:
- `#2563eb`, `#059669`, `#d97706`, `#dc2626` — appointment status colors hardcoded in JS-generated HTML inside `calendar.html` (lines 80–84, 489–518) rather than referenced from CSS classes
- `#3b82f6`, `#10b981`, `#6366f1`, `#f59e0b`, `#94a3b8` — seller initial avatar colors hardcoded inline in `dashboard/index.html` line 664

These hardcoded colors cannot be theme-changed and create maintenance risk.

**What works well:** The semantic status color model (blue=scheduled, green=confirmed, amber=in-progress, dark-green=completed, red=cancelled) is consistent across the calendar, list, and view templates.

---

### Pillar 4: Typography (2/4)

**Content pages bypass Tailwind text scale entirely**

The sidebar, base layout, and component macros use Tailwind's text scale (`text-xs`, `text-sm`, `text-base`, etc.) consistently.

However, `dashboard/index.html`, `invoices/list_refined.html`, and `appointments/calendar.html` each declare a local `<style>` block with custom font sizes in `rem` units:

| Class | Value | Tailwind equivalent |
|-------|-------|---------------------|
| `.stat-value` | `1.25rem` | `text-xl` |
| `.page-title` (dashboard) | `1.5rem` | `text-2xl` |
| `.page-title` (calendar) | `1.75rem` | `text-[1.75rem]` (nonstandard) |
| `.list-item-title` | `0.8125rem` | between `text-xs` and `text-sm` |
| `.list-item-subtitle` | `0.6875rem` | between `text-xs` and `text-sm` |
| `.stat-label` | `0.6875rem` | same |
| `.appointment-status-badge` | `0.5625rem` | smaller than `text-xs` |

The `0.6875rem` and `0.5625rem` values fall between Tailwind's named steps and will produce inconsistent rendering compared to components that use the standard scale.

**Font weights across audited files:** `font-medium` (500), `font-semibold` (600), `font-bold` (700), `font-light` (300) — 4 weights in use, which is acceptable, but mixing CSS `font-weight: 600` declarations with Tailwind `font-semibold` means identical weight values come from two different systems.

**What works well:** The type hierarchy within each individual page is internally consistent. Headings are large and weighted, labels are small and muted, data values are medium-sized and bold.

---

### Pillar 5: Spacing (3/4)

**Sidebar — clean Tailwind spacing**

The sidebar uses Tailwind spacing classes throughout: `px-4 py-2`, `px-4 py-3`, `px-2 mb-1`, `py-1`, `gap-1`, `gap-2`, `p-2`. No arbitrary values. Spacing is consistent between all nav items (`px-4 py-2`).

Minor inconsistency: the user info panel bottom div uses `p-2` while the top logo/header uses `px-4 py-2` — the logout button ends up with less horizontal padding than nav items. This creates a slight misalignment at the bottom of the sidebar.

**Content pages — custom CSS spacing**

Dashboard and invoices list bypass Tailwind for layout spacing:
- `padding: 1rem 1.5rem`
- `gap: 0.75rem`
- `margin-bottom: 1rem`
- `padding: 0.75rem 1rem`

This is not inherently wrong (content pages have design freedom) but means the `p-2` override in `base.html` line 44 (`<main class="flex-1 overflow-auto p-2">`) and the page's own `#main-content { padding: 1rem 1.5rem !important; }` override fight each other. The `!important` on line 38 of `dashboard/index.html` is a maintenance risk.

**Arbitrary value usage**

No Tailwind arbitrary values (e.g., `[13px]`) were found in the sidebar or audited content templates. The custom CSS approach avoids that pattern but creates equivalent fragmentation.

**Positive:** The `space-y-0.5` on `.sidebar-section-items` achieves tight but readable nav item stacking — a well-chosen scale value.

---

### Pillar 6: Experience Design (3/4)

**Loading states — well implemented**

- Dashboard: panels show "Ladowanie..." text before async data arrives; refresh button shows spinner animation (`.loading svg` animation)
- Calendar: `loadingOverlay` with spinner covers the timeline grid during fetch
- Calendar employee pagination label shows "Ładowanie..." during initial load

**Error states — functional but unpolished**

Error handling is consistent across the codebase (try/catch in all async functions), but error messages lack diacritics (see Pillar 1). The dashboard error state renders just `<div class="empty-title">Blad ladowania</div>` with no recovery action or retry button.

**Empty states — good**

- Dashboard panels show icon + title for empty data
- Calendar shows a centered empty state with icon, "Brak wizyt", and description text
- The overdue-payments empty state correctly shows a positive message: "Brak zaległości — Wszystko opłacone na czas!" (though with missing diacritics)

**Missing: Accessibility / keyboard interaction**

Aria usage is nearly absent across the template suite — only 3 `aria-label` attributes were found across all 50+ templates. Specific gaps:

- Sidebar section headers: click-to-toggle is not wired (hover only), no keyboard equivalent
- Calendar pagination arrow buttons (`prevDayBtn`, etc.): have `title` attributes but no `aria-label`
- Employee stat dots in calendar headers are purely decorative SVG/spans with no text alternative
- The sidebar `sidebar-section-header` elements use `cursor-default` which overrides UA pointer and makes the chevron icon misleading on mouse and invisible on keyboard

**Destructive action confirmations — present**

`components/confirm_modal.html` is included in base.html and used across 34 templates. Confirmation dialogs are present for deletes. This is well-handled.

**Role display in sidebar footer**

`<p class="text-xs text-slate-400 capitalize">{{ current_user.role }}</p>` displays raw role strings like "superuser", "receptionist". `capitalize` only uppercases the first letter — "Superuser" is acceptable but "Receptionist" is shown where a human-readable label like "Recepcjonistka" would be more appropriate for a Polish-language app.

---

## Files Audited

- `templates/components/sidebar.html` — primary focus, hover-expand nav
- `templates/base.html` — layout shell
- `templates/dashboard/index.html` — dashboard with Chart.js, async panels
- `templates/invoices/list_refined.html` — invoice list with filters and table
- `templates/appointments/calendar.html` — day-view timeline calendar
- `templates/components/scrollable_table.html` — reusable table macro
- `templates/components/form_fields.html` — reusable form macro
- `templates/components/confirm_modal.html` — destructive action modal
- `tailwind.config.js` — color token definitions
- `static/css/input.css` — global Tailwind component classes
- `.planning/codebase/ARCHITECTURE.md` — project context
