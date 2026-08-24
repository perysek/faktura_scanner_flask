# DESIGN.md — GUI / UI / UX System Specification

> **Purpose of this document.** This is the single source of truth for the visual language,
> interaction rules, and structural conventions of this application's frontend. It is written to
> be **self-sufficient**: a fresh Claude/engineer session with zero prior context on this
> codebase should be able to read this file alone and build a new page, screen, or feature that
> is visually and behaviorally indistinguishable from the rest of the app.
>
> **Scope discipline.** This document deliberately does **not** name or describe the app's
> business-domain pages, modules, or content (what specific sections exist, what they're called,
> what data they show). That belongs in feature-level docs / the codebase itself. This file owns
> only the **design system**: tokens, components, chrome, auth, routing/access patterns, and the
> rules for extending them. Where a concrete example is needed (e.g. "how do I add a sidebar
> link"), it uses a generic placeholder module (`Resource A`, `/resource-a`) — copy the pattern,
> not the name.
>
> Follow this document exactly. If a new situation isn't covered, extend the document first,
> then build — don't improvise inline and leave the spec stale.

---

## 0. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend framework | React 18 + TypeScript | Function components + hooks only, no class components |
| Build tool | Vite 5 | Dev server on port 5173, proxies API calls to the backend |
| Routing | React Router 6 (`react-router-dom`) | Client-side SPA routing, `viewTransition` enabled on nav links |
| Styling | Tailwind CSS 3 (utility layer) + a hand-authored CSS token/component system | Tailwind handles layout utilities (`flex`, `gap-2`, `px-4`…); all **visual identity** (color, radius, shadow, motion) comes from CSS custom properties and named component classes, not Tailwind's default palette |
| Fonts | Geist Variable, self-hosted via `@fontsource-variable/geist` | No Google Fonts CDN dependency — fully offline-capable, no FOIT/FOUT network hop |
| Icons | Two parallel inline-SVG systems (see §11) | No icon font, no external icon library import at runtime |
| Backend | Flask (Python) + PostgreSQL | REST-ish JSON endpoints under a few distinct route prefixes (not one unified `/api`) |
| Auth | Flask-Login session-cookie auth (`HttpOnly`, `SameSite=Lax`) | Cookie-based, not JWT/localStorage tokens — see §17 |
| API transport | `fetch` with `credentials: 'include'` | A thin wrapper (`lib/api/client.ts`), not axios/react-query — see §18 |
| State management | React local state + Context (no Redux/Zustand/etc.) | `AuthContext`, `ToastProvider`, `ConfirmProvider` are the only global state; everything else is component-local or a small custom hook |

**Critical architectural fact:** there is no CSS-in-JS and no component library (no MUI/Chakra/shadcn
runtime). Every visual primitive (button, input, card, badge, modal) is a **named CSS class** backed
by a **design token**, imported once in `src/styles/index.css`:

```css
@import '@fontsource-variable/geist';
@import './tokens.css';      /* :root custom properties + [data-theme] overrides */
@import './base.css';        /* html/body reset, global transition rule, focus-visible, a11y utilities */
@import './components.css';  /* every named component class in the system */
@tailwind base;
@tailwind components;
@tailwind utilities;
```

Tailwind is loaded **after** the token/component layer, so Tailwind utilities can still override
spacing/layout on a case-by-case basis, but they must never be the source of a color, radius, or
shadow value — those always come from `var(--token-name)` or a `.class-name` defined in
`components.css`.

---

## 1. Design Philosophy

The aesthetic is **"refined minimal"** — a quiet, boutique/operations-console hybrid: flat surfaces,
sharp-but-not-harsh corners, low-weight body type, and a single decorative accent color used
sparingly at high-value touchpoints (primary brand CTA, active nav indicator, focus highlights on
selection). It reads as premium through restraint (whitespace, hairline borders, warm-tinted
shadows) rather than through heavy visual effects.

**Anti-patterns — do not do these:**
- Gradient-fill buttons on ordinary list/table/CRUD pages (gradients are reserved for the one
  "brand CTA" role — see §7)
- Large border-radius (`rounded-2xl` / 16px+) outside of modals and overlays
- Heavy drop shadows on inline content cards (use the token shadow ramp, which is deliberately
  subtle and warm-tinted, not pure black)
- More than one accent color competing for attention on a single screen
- Pure black shadows (`rgba(0,0,0,…)`) — this system uses a warm ink-brown tint
  (`rgba(26, 20, 12, …)`) for all elevation; it's a deliberate brand fingerprint, not an oversight

---

## 2. Design Tokens

All tokens live in `src/styles/tokens.css` under `:root` (the default/light theme), with
`[data-theme="…"]` blocks overriding a subset for alternate palettes (§4). **Never hardcode a hex
value in a component or a page-scoped style block** — always consume `var(--token-name)`. This is
the single most important rule in the whole system: it's what makes theming, future rebrand, and
consistent dark-mode-if-ever-added possible without touching component code.

### 2.1 Text / Ink

```css
--color-ink:        #1a1a1a   /* primary body text, headings */
--color-ink-muted:  #525252   /* secondary text, labels, hover states on dark fills */
--color-ink-subtle: #6b6b6b   /* placeholders, helper text, table headers, disabled-ish text */
```

### 2.2 Surfaces

```css
--color-surface:          #fafafa  /* panel backgrounds, table header row, hover backgrounds */
--color-surface-warm:     #f2f0ea  /* page body background (the "canvas" behind cards) */
--color-surface-elevated: #fdfcfa  /* cards, inputs, modals — anything that sits "above" the canvas */
```

### 2.3 Borders

```css
--color-border:         #e8e6e1  /* standard dividers, input borders, card borders */
--color-border-subtle:  #f0eeea  /* very light separators, table row dividers */
```

### 2.4 Radius

```css
--radius-sm: 2px   /* buttons, inputs, badges, table containers, most surfaces — the default */
--radius-md: 3px   /* cards, modals, dropdown panels — one notch softer than the default */
```

This is a **flat/minimal radius system** ("System A" in this project's history — a rounded
"System B" with `0.75rem`/`1rem` radii was explored and explicitly rejected for this app's
identity; do not reintroduce large radii outside modals).

### 2.5 Elevation (Shadows)

A dual-layer "contact + ambient" shadow ramp, warm ink-brown tinted (`rgba(26, 20, 12, …)`)
instead of pure black — this is what gives cards a soft, premium lift instead of a harsh
Material-style shadow:

```css
--shadow-xs:    0 1px 1px rgba(26, 20, 12, 0.04)
--shadow-sm:    0 1px 2px rgba(26, 20, 12, 0.05), 0 2px 4px rgba(26, 20, 12, 0.04)
--shadow-md:    0 2px 4px rgba(26, 20, 12, 0.06), 0 8px 16px rgba(26, 20, 12, 0.10)
--shadow-lg:    0 4px 8px rgba(26, 20, 12, 0.08), 0 12px 28px rgba(26, 20, 12, 0.14)
--shadow-xl:    0 6px 12px rgba(26, 20, 12, 0.10), 0 24px 48px rgba(26, 20, 12, 0.18)
--shadow-focus: 0 0 0 3px rgba(26, 20, 12, 0.05)
--shadow-sidebar: 4px 0 16px rgba(26, 20, 12, 0.14), 1px 0 2px rgba(26, 20, 12, 0.08)
```

Usage convention: `xs`→`sm` for resting cards/inputs, `md` for hover-lift states, `lg`/`xl` for
overlays (modal panels, dropdown menus), `focus` for the soft halo behind `:focus` on refined
inputs (not the same thing as the keyboard `:focus-visible` outline — see §13).

### 2.6 Accent / Brand (decorative)

```css
--color-accent:       #c9a227                    /* decorative gold — sidebar active pill, brand CTA */
--color-accent-muted: rgba(201, 162, 39, 0.12)    /* tinted background for active/selected states */
--color-accent-deep:  #a07d1a                     /* gradient dark stop, border on brand CTA */
--color-on-accent:    var(--color-ink)            /* text color when painted onto --color-accent */
--color-on-ink:       #ffffff                     /* text color when painted onto --color-ink (dark fills) */
```

**`--color-accent` is a decorative brand color, not a functional one.** It is used for: the
sidebar active-link pill/icon, the avatar gradient, the one "brand CTA" button variant, badges,
and theme-switcher swatches. It must **never** be relied upon for a semantic/functional signal
(success, error, focus) — those have their own dedicated tokens (§2.7). This separation is
deliberate and load-bearing: a future rebrand only needs to change `--color-accent`; it must never
need a hunt-and-replace of every place gold happens to be used for "this is clickable" or "this
is the current selection outline."

### 2.7 Functional Accent

```css
--color-focus-ring: #2563eb   /* :focus-visible outline, functional links, info-toned actions */
```

Kept **constant across every visual theme** (§4) — it's a functional signal (what does the
keyboard focus ring mean, what does "info" mean), not brand decoration, so a theme swap must never
change what it means.

### 2.8 Semantic (state colors)

```css
--color-success: #2d6a4f
--color-warning: #9a6700
--color-error:   #9b2c2c
--color-info:    #1e6091
--color-purple:  #7e22ce   /* + --color-purple-bg, --color-purple-badge */
--color-orange:  #c2410c   /* + --color-orange-bg */
--color-pink:    #be185d   /* + --color-pink-bg */
```

Plus a richer green pairing for destructive-action success feedback (undo toasts, etc.):
`--color-success-action: #10b981` / `--color-success-action-dark: #059669`.

### 2.9 Status / Categorical Data Colors

A dedicated palette for entity-state badges (e.g. "active/pending/cancelled"-style states), each
with a foreground + background pair:

```css
--color-status-scheduled / -bg / -badge     (blue family)
--color-status-confirmed / -dark / -bg / -badge  (green family)
--color-status-in-progress / -bg / -badge   (amber family)
--color-status-completed / -bg              (deep green)
--color-status-cancelled / -dark / -bg / -badge  (red family)
--color-status-no-show                      (neutral gray, no bg — rare/muted state)
```

**Rule: status/categorical colors are constant across every theme.** This is an
"operations-console" convention — a theme changes chrome (surfaces, borders, ink, the one accent),
it must never reassign what a color *means* in the data (e.g. red must always mean the same status
everywhere, in every theme, for every user). Do not add a per-theme override for any
`--color-status-*` or `--color-chart-*` token.

### 2.10 Chart Palette

A fixed 10-color categorical set for data visualization, also constant across themes:

```css
--color-chart-blue, -green, -orange, -red, -purple, -pink, -teal, -amber, -slate, -sky
```

### 2.11 Typography Tokens

```css
--font-display: 'Geist Variable', system-ui, sans-serif
--font-body:    'Geist Variable', system-ui, sans-serif
```

Both point to the same variable font family — the distinction exists so the token *names* can
diverge later (e.g. a display serif) without touching every call site.

### 2.12 Motion

```css
--ease-out-expo:  cubic-bezier(0.16, 1, 0.3, 1)   /* snappy deceleration — buttons, cards, sidebar pill */
--ease-out-quart: cubic-bezier(0.25, 1, 0.5, 1)    /* smoother deceleration — table rows, accordions */
```

### 2.13 Sidebar Tokens (theme-dependent block, see §4 for full value table)

```css
--sidebar-bg, --sidebar-bg-deep, --sidebar-text, --sidebar-text-hover, --sidebar-text-active,
--sidebar-heading, --sidebar-border, --sidebar-hover-bg, --sidebar-active-bg,
--sidebar-active-border, --sidebar-logo-filter
```

---

## 3. Typography

| Use | Font | Weight | Size | Class |
|---|---|---|---|---|
| Page title | Geist Variable | 600 | 1.75rem | `.page-title` |
| Auth screen title | Geist Variable | 600 | 2rem | `.refined-title` |
| Page/auth subtitle | Geist Variable | 300 | 0.8125rem | `.page-subtitle` / `.refined-subtitle` |
| Stat value | Geist Variable | 600 | 1.25rem | `.stat-value` |
| Stat label | Geist Variable | 500 | 0.6875rem, uppercase, 0.08em tracking | `.stat-label` |
| Body / paragraph | Geist Variable | 300–400 | 0.875rem | default |
| Table cell | Geist Variable | 400 | 0.8125rem | `.refined-table td` |
| Table header | Geist Variable | 500 | 0.6875rem, uppercase, 0.12em tracking | `.refined-table th` |
| Form label | Geist Variable | 500 | 0.8125rem | `.form-label` |
| Auth field label | Geist Variable | 500 | 0.75rem, uppercase, 0.06em tracking | `.refined-label` |
| Input text | Geist Variable | 300–400 | 0.8125rem (auth) / 0.875rem (forms) | `.refined-input` / `.form-input` |
| Button text | Geist Variable | 400–500 | 0.75–0.8125rem, 0.02em tracking | `.refined-btn-*` |

**Letter-spacing conventions:** table headers `0.12em`, stat labels `0.08em`, auth field labels
`0.06em`, button text `0.02em`, headings (`page-title`, `refined-title`) `-0.02em` (tight, not
wide — headings *tighten*, small-caps-style labels *widen*).

**Mobile input-zoom guard:** any `input`/`select`/`textarea`/`.refined-input` is forced to
`font-size: 16px !important` below 1024px viewport width. This is a deliberate iOS Safari
workaround — any focused control under 16px triggers an auto-zoom on focus that never zooms back
out. **Never remove this rule** when adding new form controls; extend the selector list in
`base.css` instead if you add a new input-like class.

---

## 4. Theming System

Four **light-family** themes, switched at runtime via `data-theme` on `<html>`:

| Theme | `data-theme` value | Character |
|---|---|---|
| Default (light) | *(attribute absent)* | Warm neutral surface + gold accent — the baseline identity |
| Blue | `blue` | Cool light surfaces, steel-blue accent |
| Green | `green` | Warm-cool light surfaces, sage-green accent |
| Graphite | `graphite` | Cool graphite-gray surfaces, muted plum accent — quieter/editorial |

**Rules for this system, binding for any future theme added:**

1. **All themes are light-family.** No dark theme currently exists in this system (a prior
   dark-family exploration was explicitly removed). If a dark theme is added later, every
   `--color-status-*`, `--color-chart-*`, `--color-focus-ring`, and `--color-on-ink`/
   `--color-on-accent` pairing must be re-verified for contrast — dark surfaces are exactly where
   a hardcoded `color: white` paired with `background: var(--color-ink)` breaks (ink flips light
   in a dark theme, and the paired white text becomes invisible). This is a real bug class that
   has already bitten this exact codebase once; see the historical fix in `STYLESEED.md`.
2. **Only these tokens vary per theme:** `--color-ink[-muted|-subtle]`,
   `--color-surface[-warm|-elevated]`, `--color-border[-subtle]`, `--color-accent[-muted|-deep]`,
   `--color-on-accent`, and every `--sidebar-*` token.
3. **These tokens never vary per theme:** `--color-success*`, `--color-warning`, `--color-error`,
   `--color-info*`, every `--color-status-*`, every `--color-chart-*`, every `--color-star-*`,
   `--color-focus-ring`. Categorical/semantic meaning must not shift under the user's feet when
   they switch a cosmetic preference.
4. **Persistence is device-local, not account-synced** — `localStorage.setItem('theme', value)`.
   There is deliberately no server round-trip for a theme preference.
5. **No-FOUC requirement.** Theme must be applied *before first paint*, via an inline `<script>`
   in `index.html`'s `<head>` that reads `localStorage` synchronously and sets the `data-theme`
   attribute before React ever mounts:
   ```html
   <script>
     (function () {
       try {
         var t = localStorage.getItem('theme');
         if (t) document.documentElement.setAttribute('data-theme', t);
       } catch (e) {}
     })();
   </script>
   ```
   Any new persisted visual preference (density mode, font-size scale, etc.) must follow this
   same synchronous-inline-script pattern — a `useEffect` in React is too late and causes a
   visible flash.
6. **UI for switching themes:** one icon-button in the sidebar footer opening an accessible
   popover (`role="menu"`, items are `role="menuitemradio"` with `aria-checked`). This is the
   system's one sanctioned "signature move" for a settings-style popover — reuse this exact
   pattern (trigger button + `role="menu"` popover + click-outside + Escape to close) for any
   future similar small-footprint settings control; do not invent a second popover idiom.

---

## 5. Spacing & Layout

- Base spacing unit follows Tailwind's default scale (0.25rem increments) — `gap-2`, `px-4`,
  `py-1.5`, etc. There is no custom spacing scale; Tailwind's defaults are used as-is for layout.
- Page-level content padding: `.refined-page` → `padding: 1rem 1.5rem`.
- Card padding: `.form-card` → `1rem 1.125rem`; auth cards → `2.5rem` (auth screens get generous
  breathing room since they're single-purpose, low-density screens).
- Form field grid: `.form-grid` uses `grid-template-columns: repeat(auto-fit, minmax(200px, 1fr))`
  — **`auto-fit`, deliberately not `auto-fill`.** This matters: `auto-fill` reserves empty grid
  tracks a row *could* hold even when nothing is placed in them, leaving visible dead space next
  to a short 2-field group. `auto-fit` collapses unused tracks so a short field group fills the
  row's full width instead of stranding itself in a corner. Always use `auto-fit` for form grids
  in this system, never `auto-fill`.
- `.form-field-full` (`grid-column: 1 / -1`) spans a field across the full grid width — use for
  long text/textarea fields inside an otherwise multi-column form.
- Responsive breakpoints follow Tailwind defaults (`sm` 640px, `md` 768px, `lg` 1024px,
  `xl` 1280px). The one structurally significant breakpoint is **`lg` (1024px)** — it's the
  sidebar desktop/mobile-drawer cutover point (see §15) and the input-zoom-guard cutover (§3).
- **Full-viewport-frame layout, not page-scroll layout.** The app shell's `<main class=
  "app-shell-content">` is `flex:1; overflow:auto` — it is a fixed-height viewport frame, not a
  page that scrolls as a whole; each routed page decides for itself which of two scroll models it
  needs (§20 has the full spec, this is the summary):
  - **Default — the whole page scrolls together** inside `<main>` (header, stats, filters, table,
    all one flow). This is what every page gets by default and is correct for anything that isn't
    built around one dominant table (forms, Detail pages, Dashboard).
  - **Opt-in — `.page-fills-viewport` on the page root** (desktop ≥1024px only). Header/stats/
    search stay pinned at their natural height; the page's `.table-container` stretches to fill the
    rest of `<main>` and scrolls internally with its own sticky `<thead>` — used by every list page
    built around one primary table (Klienci, Sprzedawcy, Usługi, Pracownicy, Kategorie usług, Formy
    zatrudnienia). Mobile always keeps the default whole-page scroll (nested scroll regions
    are a touch-UX papercut on phones) — see §20.
  Do not let both the page and an inner region scroll independently under the default model, and do
  not default to "let the whole document scroll" while `.page-fills-viewport` is active — that
  defeats the point of pinning the header/search chrome.

---

## 6. Buttons

Five variants, one canonical component (`components/ui/Button.tsx`) mapping a `variant` prop to a
CSS class. **Always use `<Button variant="…">` — never hand-roll button styling inline.**

| Variant | Class | Role |
|---|---|---|
| `primary` | `.refined-btn-primary` | Default call-to-action — dark ink fill |
| `secondary` | `.refined-btn-secondary` | Default choice for most buttons — bordered, low emphasis |
| `ghost` | `.refined-btn-ghost` | Lowest emphasis — icon-adjacent or tertiary actions |
| `danger` | `.refined-btn-danger` | Destructive actions outside of modals (delete, remove) |
| `brand` | `.refined-btn-brand` | **Reserved.** Gold gradient CTA — one specific high-value touchpoint per flow (e.g. the auth submit button), never a general "primary" replacement |

### State reference (per variant)

**Primary** (`.refined-btn-primary`):
```
Rest:     background var(--color-ink), color var(--color-on-ink), radius var(--radius-sm)
Hover:    background var(--color-ink-muted), translateY(-1px), shadow var(--shadow-md)
Active:   scale(0.97)  — via the shared .btn-press micro-interaction (below)
Disabled: opacity 0.6, pointer-events: none
Focus:    2px solid var(--color-focus-ring), 2px offset — keyboard-only (:focus-visible)
```

**Brand** (`.refined-btn-brand`) — the one gradient exception in the whole system:
```
Rest:  linear-gradient(135deg, #d9b23c 0%, var(--color-accent) 45%, var(--color-accent-deep) 100%),
       1px solid var(--color-accent-deep), inset top highlight + shadow-sm
Hover: gradient shifts lighter, translateY(-1px), shadow-md
Disabled: opacity 0.6, pointer-events: none
```

**Secondary** (`.refined-btn-secondary`):
```
Rest:   background var(--color-surface-elevated), border 1px var(--color-border)
Hover:  border-color var(--color-ink-muted), background var(--color-surface)
Active (toggle state, e.g. selected filter chip): .active class →
        background var(--color-ink), color var(--color-on-ink), border-color var(--color-ink)
Disabled: opacity 0.6, pointer-events: none
```

**Ghost** (`.refined-btn-ghost`):
```
Rest:  transparent, color var(--color-ink-muted), border 1px var(--color-border)
Hover: background var(--color-surface-warm), color var(--color-ink)
```

**Danger** (`.refined-btn-danger`):
```
Rest:  transparent, color var(--color-error), border 1px transparent
Hover: background rgba(155,44,44,0.06), border-color rgba(155,44,44,0.2)
```

**Universal micro-interaction — `.btn-press`:** every `<Button>` gets this automatically.
```css
.btn-press:active { transform: scale(0.97); transition: transform 100ms ease-out; }
.btn-press:disabled { transform: none; }
```
Any new pressable control (not just buttons — e.g. a permission-grid tile, see `components.css`
`.permission-tile:active`) should get an equivalent tactile scale-down on `:active` for
consistency, unless `prefers-reduced-motion` disables it.

**Sizing:** default padding `0.625rem 1rem`, font `0.8125rem`. A `small` prop (`.refined-btn-sm`)
tightens to `0.375rem 0.75rem` / `0.75rem` font — use for inline/table-adjacent actions, not for
primary page-level CTAs.

**Modal-footer buttons** use a parallel but distinct class set (`.btn-primary`/`.btn-secondary`/
`.btn-danger` under `.modal-footer`, and `.cm-btn-*` under the confirm dialog) — same visual
language (ink fill primary, bordered secondary, red danger) but scoped so overlay chrome doesn't
depend on the page-level `.refined-btn-*` classes changing shape. Keep these two families in sync
by hand if you change one's colors/radius — they are intentionally separate CSS, not a shared
mixin, because the confirm dialog is deployment-critical inline CSS (see the CSS delivery-strategy
note in `GUI-COMPONENTS-GOLDEN-BOOK.md` if this project reintroduces a build step where that
matters).

---

## 7. Forms

All form fields are built from typed React primitives in `components/ui/form.tsx` — **never
hand-roll a raw `<input>`/`<select>`/`<textarea>` on a page.** Available primitives:

| Component | Renders |
|---|---|
| `<TextField>` | `<input>` + label + optional required-marker/error/helper |
| `<SelectField>` | `<select>` + same wrapper contract, optional placeholder option |
| `<TextareaField>` | `<textarea>` + same wrapper contract |
| `<CheckboxField>` | checkbox + label + optional description line |
| `<FormCard>` | card shell (`.form-card`) — one or more fieldsets |
| `<FormFieldset>` | `<fieldset>`/`<legend>` pair + auto-fit grid of fields (real `<fieldset>`, not a styled `<div>` — screen readers announce the group name before each field) |
| `<FormSection>` | convenience: one `FormCard` wrapping one `FormFieldset`, for single-topic forms |
| `<FormActions>` | submit + optional cancel button row, submit shows a "Saving…"-style busy label when `isLoading` |

**Field wrapper contract (identical across every field type):**
- Label always above the input, `.form-label` styling
- Required fields get a red `*` marker (`aria-hidden`, since the `required` HTML attribute is the
  actual accessible signal)
- Error text (red, `var(--color-error)`) takes priority and suppresses helper text
- Helper text (muted, `var(--color-ink-subtle)`) only shows when there's no error
- `fullWidth` prop spans the field across the whole grid (`.form-field-full`)

**Multi-topic forms** (several distinct field groups on one page) compose `FormCard` +
multiple `FormFieldset`s directly, so the groups share one card's padding/border/shadow instead of
paying for a full card per topic — each fieldset after the first gets a top border + margin
instead of its own elevation. **Single-topic forms** use the `FormSection` convenience wrapper.
Pick based on whether the form has one logical group or several — don't default to one card per
field group; that was a rejected pattern in this system's history (documented in `components.css`
as the reason `.form-fieldset` exists separately from `.form-card`).

**Validation timing convention:** this system validates on submit (see §17's reset-password form:
length + match checks run in the submit handler, not on blur/change). Follow this unless a
specific UX reason calls for earlier validation — inline-as-you-type validation is not the
established pattern here and would be visually inconsistent with every other form in the app.

---

## 8. Feedback Systems

Three global providers, each mounted once near the app root and consumed via a hook — **never
instantiate a second toast stack or a second confirm dialog.**

### 8.1 Toasts (`ToastProvider` / `useToast()`)
- 4 types: `success`, `error`, `warning`, `info`
- Max 3 stacked; oldest is silently dropped when a 4th arrives
- Default duration 4000ms; pass `0` for persistent (must be dismissed manually)
- Positioned `fixed bottom-4 right-4`, `aria-live="polite"` on the container so screen readers
  announce new toasts without interrupting
- Each toast: icon (mapped per type) + message + explicit close button (`aria-label`)
- Slide-up entrance animation (`toast-slide-up`, 0.3s), respects `prefers-reduced-motion`

### 8.2 Confirm dialog (`ConfirmProvider` / `useConfirm()`)
- Promise-based: `const ok = await confirm({ title, message, type, confirmText?, cancelText? })`
- 3 types: `danger` (default), `warning`, `info` — each tints the leading icon badge and the
  confirm button color
- **Use this for every destructive/consequential action** (delete, irreversible state change).
  Never use the browser's native `confirm()`/`alert()` — it can't be styled, can't be tested
  reliably, and breaks the app's focus-management contract.
- Accessibility: `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing at the title,
  focus starts on **Cancel** (the safe default, not Confirm), full focus trap while open, closes
  on Escape or backdrop click, returns focus to the triggering element on close.

### 8.3 Generic modal
- `.modal-overlay` / `.modal-content` / `.modal-header` / `.modal-body` / `.modal-footer` classes
  exist in `components.css` for one-off overlay content (a form-in-a-dialog, a data preview) that
  isn't a simple confirm. Same backdrop blur + entrance-animation language as the confirm dialog.
  Reuse the confirm dialog's a11y contract (focus trap, Escape, `role="dialog"`) for any new modal
  built on these classes — it is not automatic just from using the CSS classes.

---

## 9. Icons

**Two parallel, non-interchangeable icon systems.** Mixing them (using a path from one inside the
other's component) renders off-canvas or invisible — they use different SVG coordinate spaces.

| System | Component | ViewBox | Style | Use for |
|---|---|---|---|---|
| Glyph icons | `<Icon name="…" />` (`lib/icons/Icon.tsx`) | `0 -960 960 960` | Filled, `fill="currentColor"` | Everything **except** sidebar nav rows — toasts, stat cards, empty states, confirm-dialog badges, theme-switcher swatVatch icon |
| Nav icons | `<NavIcon path="…" />` (`components/layout/NavIcon.tsx`) | `0 0 24 24` | Stroke, `stroke="currentColor"`, `strokeWidth 2` | Sidebar nav links only |

**Extending the glyph set:** add a `<path d="…"/>` string to `ICON_PATHS` in `lib/icons/Icon.tsx`'s
`paths.ts` — that is the **only** sanctioned way to add a new glyph. Never inline a raw `<svg>` at
a call site; an unknown `name` silently falls back to the `info` glyph rather than rendering
nothing, so a typo'd icon name is visually obvious (a wrong-looking icon) rather than a blank gap.

**Extending the nav icon set:** any 24×24 stroke path (Heroicons-style outline icons are the
established source) passed directly as the `iconPath` string in a nav link config — no shared
registry, since nav icons are page-specific and don't need reuse tracking the way content glyphs
do.

Both systems render `aria-hidden="true"` — icons are always decorative. The interactive element
that hosts an icon (a button, a link) is responsible for its own `aria-label` if it has no visible
text.

---

## 10. Animations & Transitions

### 10.1 Global rule

Every element transitions `background-color, border-color, color, fill, stroke, opacity,
box-shadow, transform` at `300ms cubic-bezier(0.4, 0, 0.2, 1)` by default (set once on the
universal selector in `base.css`). This is what makes a theme swap (§4) animate smoothly instead
of hard-cutting, and it means **most hover/focus states don't need their own `transition`
declaration** — only declare a custom transition when you need a different duration/easing than
the global default (e.g. the snappier `--ease-out-expo` buttons use).

### 10.2 Named animation classes (add the class, get the effect)

| Class | Effect | Typical use |
|---|---|---|
| `.animate-fade-up` | opacity 0→1 + translateY(10px→0), 0.4s | Page sections / cards on load |
| `.animate-fade-in` | opacity 0→1, 0.3s | Inline dynamic content, empty states |
| `.animate-scale-in` | scale(0.95→1) + opacity, 0.2s | Dropdowns, popovers |
| `.stagger-item` | `.animate-fade-up` with per-`nth-child` delay (up to 10) | Table row entrance |
| `.hover-lift` | translateY(-2px) + shadow-md on `:hover` | Cards, panels |
| `.skeleton` | Shimmer gradient sweep, 1.5s loop | Loading placeholders |
| `.btn-press` | scale(0.97) on `:active` | Any clickable control (§6) |

### 10.3 View Transitions (sidebar + route content)

The sidebar active-link pill and the `#main-content` region both use the browser View Transitions
API (`@view-transition { navigation: auto; }`, progressive enhancement) to cross-fade between
route changes instead of hard-cutting, with a CSS-keyframe fallback
(`sidebar-link-enter`/`pill-enter`) for browsers without View Transition support. If you add a new
persistent chrome element that should visually "glide" between navigations rather than
remount-flash, give it a stable `view-transition-name` the same way.

### 10.4 Reduced motion

**Every** animation in this system has a `@media (prefers-reduced-motion: reduce)` override that
either removes the animation entirely or drops it to an instant/near-instant state change. This is
non-negotiable for any new animation added to the system — write the reduced-motion override in
the same commit as the animation, not as a follow-up.

---

## 11. Accessibility Contract

This is a **must-follow baseline**, not a nice-to-have, for every new screen/component:

1. **Keyboard-only focus ring.** `:focus-visible { outline: 2px solid var(--color-focus-ring);
   outline-offset: 2px; }` — never fires for a mouse click, always fires for keyboard navigation.
   Never suppress this with `outline: none` without providing an equivalent visible replacement.
2. **Escape-key coordination — the single most important non-obvious pattern in this codebase.**
   Multiple dismissible layers (a popover, a modal, a mobile drawer, a page-level "back" binding)
   can be mounted simultaneously. Without coordination, opening a small popover while on a form
   and pressing Escape would close the popover **and** navigate away in the same keystroke. The
   fix is a tiny module-level depth counter (`lib/a11y/escapeScope.ts`):
   - Any dismissible layer with its own open/closed state calls `useEscapeClaim(isOpen)` —
     this reserves the Escape key while open (it does **not** itself close anything; the layer's
     own Escape handler still has to exist).
   - Any page-level "Escape = go back / cancel" binding uses `useEscapeAction(action, enabled,
     guardTyping = true)`, which checks `isEscapeClaimed()` first and silently no-ops if something
     more specific already owns the key. `guardTyping` (on by default) also no-ops while focus is
     inside an INPUT/TEXTAREA/SELECT, so Escape never discards an in-progress field — ported from
     the original app's create/edit inline Escape handlers, which had the same guard.
   - Two convenience wrappers around `useEscapeAction` cover the two recurring shapes: `useEscapeBack
     (href)` (`lib/a11y/useEscapeBack.ts`) for a fixed-target "go back" binding — every Detail page's
     "Powrót do listy" and `FormActions`' "Anuluj" use this pattern (`FormActions` centralizes it, so
     every form page gets Escape-to-cancel for free); `useEscapeClose(isOpen, onClose)` (`lib/a11y/
     useEscapeClose.ts`) for a layer that both claims the key AND closes itself unconditionally while
     open (no self-`isEscapeClaimed()` check — a layer never gates its own dismissal) — this is what
     `ConfirmProvider` uses internally, and what any inline dismissible section nested inside a page
     that already has a `useEscapeBack` binding must use too (e.g. EmployeeDetailPage's "Dodaj
     usługę" toggle-form claims Escape while open so the page's own "Powrót do listy" binding
     doesn't fire instead and yank the user away mid-edit).
   - **Rule: "one Escape closes one layer."** Any new popover, dropdown, or modal-like UI **must**
     call `useEscapeClaim` while open. Skipping this is a correctness bug, not a style nit — it
     will manifest as a popover and a page navigation firing on the same keystroke.
3. **Focus trap for overlay UI.** `useFocusTrap(active, containerRef, returnFocusRef?)` traps Tab
   navigation inside a container while active and returns focus to a specified element (or the
   element that opened the overlay) on close. Used by the confirm dialog and the mobile sidebar
   drawer. Any new full-overlay UI (modal, drawer) must use this — do not let Tab escape into the
   page behind an open overlay (WCAG 2.4.3).
4. **SPA route-change focus management.** A client-side navigation never fires a browser "page
   load" event, so screen readers get no signal anything happened unless focus visibly moves. The
   app shell moves focus to the `<main id="main-content" tabIndex={-1}>` landmark on every route
   change (skipping the very first mount). Any new top-level layout/shell must preserve this
   behavior.
5. **Dialogs:** `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing at the visible
   title. Destructive dialogs start focus on the safe/cancel option, not the confirm option.
6. **Icon-only interactive elements** always carry `aria-label` (and usually `title` too, for a
   mouse-hover tooltip).
7. **Sortable / toggle / expandable controls** are real focusable `<button>`s with the correct
   ARIA state (`aria-expanded`, `aria-sort`, `aria-checked`, `aria-current="page"` on the active
   nav link) — never a `<div onClick>`.
8. **Labels are always programmatically tied to inputs** via `htmlFor`/`id` — never a bare
   placeholder standing in for a label.
9. **Color contrast:** body ink on the default surface is ~18:1 (WCAG AAA); every theme palette
   (§4) must be checked against WCAG AA (4.5:1 body text, 3:1 large text/UI) before shipping —
   this has already been done once for all four current themes and must be repeated for any new
   theme or any token-value change to an existing one.

---

## 12. App Shell & Layout Structure

```
<div class="flex h-full">
  <Sidebar />                              <!-- fixed-width rail on desktop, off-canvas drawer on mobile -->
  <div class="flex-1 flex flex-col h-full overflow-hidden">
    <header>                               <!-- mobile menu toggle + condensed logo/title (lg:hidden) -->
    <main id="main-content" tabIndex={-1}> <!-- <Outlet /> — the routed page renders here -->
    <footer>                               <!-- persistent copyright/footer strip -->
  </div>
</div>
```

- `<main>` is `overflow-hidden` — a fixed-height frame; individual pages own their own scroll
  region (§5).
- The mobile header shows a condensed logo + the current page's title (looked up from a
  path-prefix table, e.g. `PAGE_TITLES: [prefix, title][]` matched via
  `pathname.startsWith(prefix)` in longest-prefix-first order) — desktop hides this header
  entirely and relies on the sidebar + page's own `<PageHeader>` (§ component conventions) instead.
- Footer is always visible, outside the scrolling content region.

---

## 13. Sidebar — Structure & Behavior (increased precision)

The sidebar is the most integration-heavy piece of chrome in the system. Read this section fully
before adding, removing, or reordering navigation.

### 13.1 Visual structure (top to bottom)

1. **Brand header** — logo image + small uppercase tagline caption, bottom border.
2. **Nav region** (`<nav aria-label="…">`, scrollable) — one or more **accordion sections**, each
   containing one or more **nav links**.
3. **Footer** (fixed, non-scrolling, slightly deeper background tint) — user avatar (initials on
   an accent-gradient circle) + name + role label, theme-switcher icon button (§4), logout icon
   button.

### 13.2 Section (accordion) behavior

- Sections are single-open accordions: opening one section closes any other open section. State
  (`openSectionId`) lives in the parent `<Sidebar>`, not in each section.
- **The section containing the currently-active route auto-opens** on navigation (derived from
  `location.pathname`, recomputed on every route change) — a user is never left with the active
  page hidden inside a collapsed section.
- Expand/collapse animates via a measured `scrollHeight` → `max-height` transition (0.3s
  ease-in-out), not `display: none`/`block` — this is what makes the accordion animate instead of
  snap. A debounced `resize` listener re-measures `scrollHeight` while a section is open, so a
  viewport resize (e.g. rotating a tablet) doesn't leave a stale collapsed/cut-off height cached.
- Section header is a real `<button>` with `aria-expanded` + `aria-controls` pointing at the
  content region (`role="region"`, `aria-label` = section title).
- **On mobile (< 1024px), the accordion visually flattens** — section headers are hidden and every
  section's content is force-expanded (`max-height: none`), so the mobile drawer shows one flat
  list instead of nested accordions (small-screen users get simpler navigation, not more
  interaction).

### 13.3 Active-link indicator

- A 3px rounded pill on the link's left edge, colored `--sidebar-active-border`, over a tinted
  `--sidebar-active-bg` background; the link's icon also recolors to the same accent.
- Cross-fades in via the View Transitions API (§10.3) with a keyframe fallback.
- `end` matching on the router `<NavLink>` (exact path match, not prefix) — a parent link does not
  stay visually "active" while a child route is open unless it's explicitly the exact current path.

### 13.4 Mobile drawer behavior

- The `<aside>` element **stays mounted at all times** — it's moved off-canvas via
  `transform: translateX(-100%)` plus a delayed `visibility: hidden`, not conditionally rendered.
  This is what allows the open/close transition to animate; conditional rendering would snap.
  `visibility` flips to `hidden` only *after* the slide-out transition finishes (a 0s-delay
  transition on `visibility`), so the drawer is removed from the tab order the instant it starts
  closing, but stays paintable while the slide animation is still visible.
- A semi-transparent backdrop (`.sidebar-backdrop`) fades in behind it; clicking the backdrop
  closes the drawer.
- While open: focus trap active (§11.3), body scroll locked (`.scroll-lock` on `<body>`), focus
  moves to the first link in the drawer, and Escape closes it (claiming the escape scope so a
  page-level Escape binding doesn't also fire — §11.2).
- At `lg` (1024px) and above, all of this collapses to a static, always-visible, non-drawer panel
  (the mobile-only inline styles/JS become no-ops via a `min-width: 1024px` media query override).

### 13.5 Adding a new nav link or section — routing/business-logic hints

The sidebar's content is entirely data-driven from one config file
(`components/layout/navConfig.ts`) — **you should never need to touch `Sidebar.tsx` or
`SidebarSection.tsx` to add a link.** The shape:

```ts
export interface NavLinkConfig {
  label: string;
  to: string;                                   // must match a route registered in the router
  iconPath: string;                             // a 24×24 stroke path — see §9
  mobileHide?: boolean;                         // true = desktop-rail-only, dropped from the flattened mobile list
  visible: (ctx: NavVisibilityCtx) => boolean;   // access-control predicate — see below
}

export interface NavSectionConfig {
  id: string;      // stable key — used for accordion open/close state and aria-controls
  title: string;
  links: NavLinkConfig[];
}
```

**To add a link to an existing section:** append a `NavLinkConfig` object to that section's
`links` array.

**To add a new section:** append a `NavSectionConfig` object to the top-level `NAV_SECTIONS`
array — it automatically gets accordion behavior, mobile flattening, etc. for free.

**The `visible` predicate is the load-bearing part — read this carefully:**

- The sidebar filters `NAV_SECTIONS` down to only the links (and, transitively, only the sections
  that end up non-empty) whose `visible(ctx)` returns `true` for the current user, **every
  render** — there is no separate "admin sidebar config" to keep in sync.
- `ctx` gives you: the current `user` object (including `.role`), `isSupervisor`,
  `hasLinkedEmployee`, and `hasModuleAccess(moduleName)`.
- **The frontend's visibility check must mirror the backend's actual access-control decision for
  that route — not loosely, exactly.** A link that's visible but 403s on load (or on its first API
  call) is a defect. Concretely:
  - If the route's backend guard is "has module X" → `visible: (ctx) => ctx.hasModuleAccess('x')`.
  - If the backend guard is a **literal role check** (not a module-based one) → check
    `ctx.user.role === 'specificRole'` directly, even if that role also happens to have some
    *other* module permission that would make `hasModuleAccess` return true for an unrelated
    reason. (This exact trap exists in the real codebase: a role can hold a broad
    "settings"-module grant that would make a naive `hasModuleAccess('settings')` check pass, while
    the actual backend endpoint gates strictly on `role === 'superuser'` — using the module check
    there would show the link to users who then get a wall of 403s. Always trace the *real* route
    guard, not the nearest-sounding permission flag.)
  - If the backend guard is an **OR of conditions** (e.g. "module access OR is a supervisor") →
    write that same OR directly in `visible`, don't approximate with a single flag.
  - If a page's true precondition is "the current user is linked to some other domain entity"
    (not a role/module check at all) — expose that as its own boolean on the auth context
    (`hasLinkedEmployee` is the existing example) and gate on it directly.
- `mobileHide: true` is a **density** decision, not a security one — never use it to hide a link
  from users who shouldn't see it; that's what `visible` is for. Use it only to trim a long desktop
  rail down to essentials on the space-constrained mobile flattened list, for a link a mobile user
  can still reach another way.
- Icon: pick or add a 24×24 stroke path per §9's nav-icon guidance. Don't reuse a glyph-icon path
  (§9's other system) here — wrong coordinate space, renders incorrectly.

**Route registration is separate and must be kept in lockstep.** Adding a `NavLinkConfig` does
**not** register a route — you must also add the corresponding `<Route>` in `router.tsx` (see
§14). The sidebar link and the route are two independent pieces of config that must agree on the
same `to`/`path` string; nothing enforces that agreement automatically, so a typo'd path silently
produces a dead nav link (or a route with no way to reach it via the sidebar).

**Page-title mapping:** if the new route should show a title in the mobile condensed header, add a
matching `[pathPrefix, title]` tuple to the shell's page-title lookup table (§12) — longest/most
specific prefix should be listed **before** shorter/parent prefixes, since the lookup uses
first-match-wins over `pathname.startsWith(prefix)`.

---

## 14. Routing & Access Control

### 14.1 Route tree shape

- Public routes (auth screens — §17) are declared **outside** any guard.
- Everything else nests inside one outer `<Route element={<ProtectedRoute />}>` (bare
  authentication gate — no `requireModule`/`guard` props) wrapping the app shell, so every
  authenticated-area route automatically gets the sidebar/header/footer chrome.
- Individual route groups needing **additional** access control nest a *second*,
  more specific `<ProtectedRoute .../>` layer inside that.

### 14.2 `ProtectedRoute` — the two gating modes

```tsx
<ProtectedRoute requireModule="someModule" />     // simple case: one module-access check
<ProtectedRoute guard={(ctx) => /* boolean expr */} />  // escape hatch: arbitrary OR/role logic
```

- `requireModule` is sugar for the common single-module case.
- `guard` wins if both are somehow given, and is the tool for anything that isn't a plain single
  module check — literal-role gates, OR-of-conditions gates, "linked entity" gates. `guard`
  receives the same `ctx` shape as the sidebar's `visible` predicate (`user`, `isSupervisor`,
  `hasLinkedEmployee`, `hasModuleAccess`) — **reuse the exact same boolean expression you used in
  that route's `navConfig.ts` `visible` check.** These two are meant to be kept identical; a route
  guard and its sidebar visibility predicate diverging is the exact bug class flagged in §13.5.
- **Unauthenticated** users are redirected to `/login` with `state: { next: location.pathname }` —
  the login page reads this and returns the user to where they were headed after a successful
  login (see §17.1).
- **Authenticated but disallowed** users are redirected to the app's default landing page (not
  shown a blank/broken screen, not bounced back to `/login`).
- Route guarding **waits out** the initial session-check (`isLoading` from `AuthContext`) before
  deciding anything — this prevents a hard page refresh on a protected route from flash-redirecting
  to `/login` before the real session state is even known yet.

### 14.3 Adding a new protected route group

1. Add the page component and its `<Route>` entries under the appropriate existing
   `<ProtectedRoute .../>` wrapper if it shares that group's access rule, **or**
2. Open a **new** `<ProtectedRoute requireModule="…" />` (or `guard={...}`) wrapper if it's a
   distinct access rule, and nest the new route(s) inside it.
3. Add the matching `NavLinkConfig` (§13.5) with an identical access predicate.
4. **Access control is enforced server-side, always.** The frontend guard exists to give the user
   a clean UX (don't show/don't route to something they can't use) — it is not itself a security
   boundary. Never treat a frontend-only `visible`/`guard` check as sufficient; the backend
   endpoint(s) the new page calls must independently enforce the same rule. If you can't point to
   the exact backend check the frontend gate is mirroring, that's a sign the backend check may be
   missing, not that the frontend check is enough on its own.

---

## 15. Authentication & Login Methodology

This section is intentionally precise — the auth flow is the one area where "close enough" causes
real security or UX regressions.

### 15.1 Session model

- **Cookie-based session auth**, not token-based. The backend issues an `HttpOnly`,
  `SameSite=Lax` session cookie on successful login; `Secure` is environment-configurable (must be
  `true` behind HTTPS in any real deployment — treat a `false`/unset value as a **dev-only**
  posture, never acceptable in production).
- The frontend never stores a session token in `localStorage`/`sessionStorage`/JS-readable state —
  the cookie is the only credential, and it's not accessible to JS by design (`HttpOnly`).
- Every API call goes through one shared `fetch` wrapper with `credentials: 'include'` so the
  cookie always rides along, plus a header (e.g. `X-Requested-With: XMLHttpRequest`) that signals
  "this is an API/SPA call" to the backend — this is what lets a shared backend endpoint return a
  clean JSON error/redirect-free response to the SPA instead of the flash-message+redirect
  behavior meant for a full-page HTML form submit. **Any new backend endpoint the SPA calls needs
  to honor this same signal** if it has both an HTML-form and a JSON-API caller.
- **"Remember me"** maps to a 30-day *sliding* session lifetime (the session is marked permanent
  server-side on login when the checkbox is checked); unchecking it yields the backend's normal
  (shorter/browser-session-scoped) default.
- **Session-check-on-load pattern:** the SPA has no server-rendered "who is logged in" context, so
  on every fresh load it calls a `/…/me`-style endpoint once, and holds `isLoading: true` until
  that resolves. Every piece of UI that depends on auth state (route guards, the sidebar, the
  header) must wait out this initial load rather than assume "no user yet" means "logged out" —
  those are different states and collapsing them causes a login-page flash on every hard refresh
  of a protected page.

### 15.2 Login flow

1. Submit email + password (+ optional "remember me") via the shared API client.
2. On success: fetch the session-check endpoint again to hydrate the full user/permissions/role
   context, then navigate to `state.next` (the path the user originally tried to reach, if any —
   see §14.2) or the default landing page.
3. On failure: show the error inline on the form (a dedicated error banner above the fields) —
   **never a native `alert()`**, never a silent failure.
4. If a user who is already authenticated lands on the login route, redirect them away immediately
   (respecting `state.next` if present) rather than showing the form again.
5. **Passwords are hashed with bcrypt** server-side (salted per-user); the frontend never sees, is
   sent, or should ever try to compute a password hash.

### 15.3 Forgot / Reset password — exact methodology

This system deliberately uses a **no-outbound-email, screen-shown reset link** methodology in its
current form. This is a real, working, secure token mechanism — but the "show the link on screen
instead of emailing it" delivery choice is a **development/demo convenience that must be replaced
before any real production deployment** (see §16's forbidden list). Document both halves distinctly:

**The token mechanism itself (production-appropriate, keep this part):**
1. User submits an email address to a "forgot password" endpoint.
2. Backend looks up the account. Whether or not it exists, **the HTTP response shape is
   identical from the client's point of view** — this prevents account enumeration via response
   timing/shape. A reset artifact is only actually generated when the account exists.
3. Any previously-issued, still-unused reset token for that user is invalidated (`used = TRUE`)
   before a new one is minted — a user can never have more than one live reset token at a time.
4. A new token is generated with a cryptographically secure random generator producing a 256-bit
   URL-safe string (`secrets.token_urlsafe(32)` server-side — never a predictable/sequential ID).
5. The token is stored server-side with a **1-hour expiry** and a `used` flag, tied to the
   specific user.
6. The reset-password endpoint validates the token against three conditions simultaneously: token
   exists, `used = FALSE`, and `expires_at > now()`. Any failure of any of the three is treated
   identically (generic "link is invalid or has expired" messaging) — the failure reason is never
   distinguished for the client, again to avoid leaking state.
7. On successful password change: the new password is hashed and stored, and the token is
   immediately marked `used = TRUE` (single-use, even if not yet expired) in the same transaction
   as the password update.
8. Both the request and the successful reset are audit-logged server-side.

**The delivery mechanism (dev-only, flag before shipping):**
- Instead of emailing the reset link, the backend returns the constructed reset URL directly in
  the API response / renders it directly on the "forgot password" confirmation screen, inside a
  clearly-labeled, monospace, select-on-click read-only field with a "valid for 1 hour" hint and a
  direct "go to the reset form" button.
- **This is only acceptable because there is currently no real email-delivery integration.** The
  moment this app has a real outbound-email capability, this screen's behavior must change to
  "we've sent a reset link to that address if an account exists" with **no link value returned to
  the client at all** — showing the actual token to whoever is sitting at the requesting browser
  defeats the entire point of a possession-based reset flow (verifying the requester controls the
  email address) the instant it's a real user's account rather than a dev seed account.

**Reset-password form validation (client-side, defense-in-depth — backend re-validates
identically):**
- New password minimum length: **8 characters** (matches the backend's own minimum — keep these
  in sync if either changes).
- Password + confirmation fields must match.
- On success: redirect to the login screen with a success message; the user must log in fresh with
  the new password (a password reset does not auto-log-in).

### 15.4 Change-password (authenticated user changing their own password)

- Requires the **current** password (re-authentication-in-place), plus new password +
  confirmation.
- Same 8-character minimum, same mismatch check, same bcrypt re-hash on success.
- This is a distinct flow from the forgot/reset flow above — it never touches the token table at
  all, since the user is already authenticated and proving continued possession of the old
  credential directly.

### 15.5 Visual/UX conventions specific to auth screens

- All three primary auth screens (login, forgot-password, reset-password) share one centered,
  single-column `AuthLayout` — full-height flex-centered column on the app's warm canvas
  background, independent of the authenticated app shell (no sidebar, no header/footer chrome).
- Card treatment: `.refined-card` (flat, hairline border, `--radius-sm`, `shadow-sm`), generous
  `2.5rem` internal padding.
- Errors render as an inline banner (`.flash-message.flash-error`) above the form fields, not a
  toast — auth errors are page-level state, not transient notifications, since the user needs the
  message to persist while they correct the field.
- The "neutral" forgot-password confirmation state uses a dedicated low-emphasis notice style
  (`.neutral-notice`) distinct from the error/success flash colors — it's neither good nor bad
  news (an enumeration-safe message must not visually read as either "success! we found you" or
  "error! not found").
- A single small "back" link (`.back-link`, muted, centered, no underline until hover) sits below
  the card on every non-login auth screen, always pointing one step back in the flow (reset →
  forgot, forgot → login).
- The login submit button is the one place `variant="brand"` (the gradient CTA, §6) is used —
  reinforcing it as the single highest-value action on the highest-traffic entry screen. Every
  other auth-screen submit button (forgot/reset) uses `variant="primary"` (plain ink fill), not
  brand — the brand gradient is not "the auth-screen button style," it's specifically the login
  button.

### 15.6 CSRF Protection

The backend applies Flask-WTF's `CSRFProtect` to every `POST`/`PUT`/`PATCH`/`DELETE` request by
default (`app.py`, `csrf = CSRFProtect(app)`); only three blueprints are exempted
(`public_bp`, `booking_bp`, `mobile_bp` — all token-authenticated with no ambient session for
CSRF to protect). `auth_bp` and every other session-authenticated blueprint the SPA talks to are
**not** exempt, which means every mutating call the frontend makes needs a valid CSRF token or
it is rejected before the route handler ever runs.

- **Token endpoint:** `GET /auth/csrf-token` — unauthenticated (a token must be obtainable
  *before* login, since the login `POST` itself needs one) and side-effect-free. Returns
  `{ success: true, csrf_token: '<token>' }` via Flask-WTF's `generate_csrf()`. `GET` requests
  never need a token — `CSRFProtect` only checks state-changing methods — so this endpoint itself
  requires none.
- **Client behavior:** `lib/api/client.ts` fetches this token lazily on the first non-`GET`
  request of the page load and caches it in module state for the lifetime of that load (one
  token per tab load, not per-request). Every subsequent non-`GET` request attaches it as an
  `X-CSRFToken` header automatically — this is transparent to page/component code, which never
  handles the token directly.
- **Bypassing the shared client loses this too.** Same rule as §18's credentials warning: any
  ad-hoc `fetch()` call that skips the `api` wrapper sends no CSRF header and will be rejected on
  any mutating method. There is no manual step to remember when using `api.post/put/del` — the
  token attachment is automatic — but a raw `fetch()` call must add it explicitly or go through
  the wrapper instead.
- **Failure mode to recognize:** a rejected CSRF request currently returns an **HTML** error page
  (400) for any path outside `/api/*` — including everything under `/auth/*` — because
  `app.py`'s `CSRFError` handler only serves JSON when `request.path.startswith('/api/')`. The
  client's response parsing checks `content-type` before attempting to parse JSON, so this
  surfaces as a normal status-coded `ApiError` rather than crashing on an unexpected response
  body — but the *message* a user sees for a CSRF rejection is still the generic "session
  expired" framing, not something CSRF-specific, since the SPA has no dedicated copy for this
  case today.

---

## 16. Rules — Must / Should / Avoid / Forbidden

### Must
- Consume design values through `var(--token-name)` or a named class from `components.css` —
  never a hardcoded hex/px value in a component or page.
- Use the shared `<Button>`, form-field primitives, `Icon`/`NavIcon`, `useToast`, `useConfirm` for
  every instance of those UI patterns — no bespoke reimplementations.
- Pair any new dismissible layer (popover/dropdown/modal) with `useEscapeClaim` (§11.2) and, if
  it's a full overlay, `useFocusTrap` (§11.3).
- Write the `prefers-reduced-motion` override in the same change as any new animation.
- Keep a route's `ProtectedRoute` guard and its sidebar `NavLinkConfig.visible` predicate
  expressing the *exact same* access rule (§13.5, §14.2).
- Treat every frontend access-control check as UX-only — verify the backend independently enforces
  the same rule for every endpoint the new page calls.
- Re-check WCAG AA contrast for any new or modified theme color.
- Keep the reset-password/change-password minimum password length constant between frontend and
  backend if either is changed.

### Should
- Default to `variant="secondary"` for buttons unless there's a clear reason for a stronger
  (`primary`) or weaker (`ghost`) emphasis; reserve `brand` for the one login CTA (§15.5).
- Validate forms on submit, matching the established pattern, unless a specific screen has a
  strong UX reason for earlier (blur/change-time) validation.
- Prefer `FormFieldset`-inside-shared-`FormCard` for multi-topic forms; `FormSection` only for
  genuinely single-topic forms.
- Use `mobileHide` for sidebar density trimming, never for access control.

### Avoid
- Large border-radius (16px+) outside modals/overlays.
- More than one accent color competing for attention on one screen.
- A second popover/dropdown interaction idiom that doesn't match the established
  trigger-button + `role="menu"`/`role="dialog"` + click-outside + Escape pattern.
- Page-level full-document scrolling when the app-shell's fixed-frame + region-owns-its-scroll
  model (§5, §12) already fits the content.

### Forbidden
- Native browser `alert()` / `confirm()` / `prompt()` for any in-app flow — always the
  `ConfirmProvider`/toast system.
- Storing any session credential in `localStorage`/`sessionStorage`/non-`HttpOnly` cookies.
- Returning a password-reset token/link value directly to a real (non-seed/non-dev) user in any
  API response or on-screen surface once real email delivery exists (§15.3).
- Treating a frontend route guard or sidebar `visible` check as a substitute for server-side
  authorization.
- Hardcoded `rgba(0,0,0,…)` shadows — this system's shadow ramp is warm-tinted
  (`rgba(26,20,12,…)`) by design; a pure-black shadow is a visible inconsistency, not a neutral
  default.
- Adding a new animation with no `prefers-reduced-motion` handling.
- A `<div onClick>` standing in for an interactive control that has a real semantic HTML
  equivalent (`<button>`, `<a>`).

---

## 17. Extending the System — Guidance for Future Features

- **New settings-style popover (beyond the theme switcher):** reuse the exact
  trigger-icon-button + `role="menu"` popover pattern from §4.6/ThemeSwitcher — same click-outside
  handling, same `useEscapeClaim` usage, same `.theme-menu`-style CSS shape (rename the class, keep
  the structure).
- **New status/categorical color needed:** add a new `--color-status-*` (foreground) +
  `-bg`/`-badge` (background) pair to `tokens.css`'s constant-across-themes block (§2.9) — do not
  reuse an existing status color for an unrelated meaning, and do not make the new pair
  theme-dependent.
- **New chart type:** pull colors from the existing 10-color `--color-chart-*` categorical set
  (§2.10) in order, rather than picking arbitrary new hues, so a legend stays visually consistent
  with any other chart in the app.
- **New form field type not covered by `form.tsx`'s primitives:** extend `form.tsx` with a new
  typed component following the existing `FieldWrapper` contract (label/required/error/helper) —
  don't build a one-off field inline on a page.
- **New dark theme (if ever required):** re-read §4 rule 1 in full before starting — this is the
  single highest-risk extension to this system given the codebase's own history with it.
- **New module/section of the app:** the three things that must move together are (1) the route(s)
  in `router.tsx` under the correct `ProtectedRoute` grouping (§14.3), (2) the `NavLinkConfig`
  entry/entries in `navConfig.ts` with a matching access predicate (§13.5), and (3) the backend's
  own authorization for every endpoint the new pages call. Treat these three as one atomic change
  — shipping one without the other two produces either a dead link, an inaccessible-but-visible
  link, or a client-trusts-itself security gap.
- **Density/compactness mode, font-size scale, or any other persisted visual preference:** follow
  the theme system's exact persistence pattern (§4 rules 4–5) — synchronous inline no-FOUC script
  in `index.html`, `localStorage`, device-local (not account-synced) unless there's a specific
  reason to promote it to server-synced.

---

## 18. Data Fetching & State Conventions

- No global data-fetching library (no React Query/SWR). The established pattern is a small shared
  hook, `useApiData<T>(fetcher, deps)`, returning `{ data, loading, error, reload }` — fetch-on-
  mount (and on `deps` change), with a `reload()` escape hatch for post-mutation refresh. New
  list/detail pages should use this hook rather than hand-rolling `useEffect` + three `useState`s.
- All network errors surface as a typed `ApiError` (status + message) from the shared `api` client
  (`lib/api/client.ts`); UI code should catch and branch on `err instanceof ApiError` to show the
  backend's real message, falling back to a generic "couldn't connect to the server" string
  otherwise (this exact fallback string is repeated verbatim across the auth screens — reuse the
  same phrasing for consistency rather than writing a new variant per screen).
- The API client is a thin `fetch` wrapper, not axios — `api.get/post/put/del`. It always sends
  `credentials: 'include'`, the API-call-signaling header (§15.1), and — on every non-`GET`
  request — a CSRF token (§15.6); any new direct `fetch()` call that bypasses this wrapper will
  silently lose all three and likely break auth on that call.
- Global state is intentionally minimal: `AuthContext` (current user/permissions/session status),
  `ToastProvider`, `ConfirmProvider`. Resist adding a new global store for page-local data — the
  `useApiData` + local `useState` pattern is the default, not an exception.

---

## 19. Pre-Ship Checklist for Any New Screen

- [ ] No hardcoded hex/px values — everything traces to a token or an existing named class
- [ ] Buttons use `<Button variant="…">`, not raw `<button className="...">`
- [ ] Form fields use `form.tsx` primitives
- [ ] Destructive actions go through `useConfirm()`, never native `confirm()`
- [ ] Any new popover/modal calls `useEscapeClaim` (+ `useFocusTrap` if it's a full overlay)
- [ ] New animations have a `prefers-reduced-motion` fallback
- [ ] Icon-only buttons have `aria-label`
- [ ] New route is registered in `router.tsx` under the correct access-control wrapper **and** has
      a matching `NavLinkConfig` entry with an identical `visible` predicate **and** the backend
      independently enforces that same rule
- [ ] New protected route waits out `isLoading` before redirect decisions
- [ ] Verified against at least the default theme + one alternate theme (contrast, layout) if any
      new color/surface is introduced
- [ ] Any new data table follows §20 (sticky header, custom scrollbar, clickable rows where a view/
      edit action exists) and, if it's the page's one primary table, `.page-fills-viewport`

---

## 20. Tabele przewijalne i klikalne wiersze

Every data table in the app — not just the big CRUD list pages — follows one shared contract.
Added after an audit found every table built through Fazy 1–2 had the browser's unstyled native
scrollbar, no sticky header, and no clickable rows, none of which matched this doc's original intent
(§5 already described the header-pinned/table-fills-viewport layout in outline; no page had actually
implemented it). Retrofitted across all ~16 existing tables at once — this section is both the spec
and the fix record.

### 20.1 Sticky header + custom scrollbar — every table, no exceptions

- `.refined-table th` (global, `styles/components.css`) is `position: sticky; top: 0; z-index: 1`
  with an opaque `background` matching the header row — required because a sticky element needs its
  own background or scrolled-past row content shows through the gaps between cells. A handful of
  tables predate `.refined-table` and use their own page-owned class (`.pref-table`, `.appt-table`,
  `.cat-modal-table`) — each got the identical `position: sticky` treatment added to its own `th`
  rule rather than being migrated onto `.refined-table` (would have changed padding/density that was
  a deliberate 1:1 port from the original template).
- `.table-container` (the shared card-chrome scroll wrapper) carries the custom scrollbar: thin
  track, `var(--color-border)` thumb, transparent track, theme-aware via tokens — both
  `scrollbar-width`/`scrollbar-color` (Firefox) and the `::-webkit-scrollbar*` pseudo-elements
  (Chrome/Edge/Safari). Never the browser's default chrome on a table scroll region.
- `.scroll-thin` is the same scrollbar treatment without the card chrome (border/bg/shadow), for a
  table already nested inside another card that already provides that chrome — e.g. EmployeeDetail
  Page's balance-adjustment history and assigned-services table, ClientDetailPage's appointment
  history. Both classes share one CSS rule set (`components.css`, "Tables" block) so the two never
  drift out of sync.
- **Bounded height is what makes the header actually stick.** `position: sticky` sticks relative to
  the nearest ancestor with a scrolling mechanism (any `overflow` other than `visible`) — if that
  ancestor's own height is unconstrained (`overflow: auto` with no `max-height`), it never scrolls
  itself and the sticky header does nothing. Every `.table-container`/`.scroll-thin` instance that
  isn't already `.page-fills-viewport`'s flex-filled region (§20.2) needs an explicit `max-height`
  (inline `style`, page-specific — e.g. `420px` for a Detail-page sub-table, `50vh`–`60vh` for
  something inside a `Modal`, which already bounds itself via `.modal-body`'s own scroll but needs
  its OWN nested scroll region for the sticky header to have something to stick against).

### 20.2 `.page-fills-viewport` — one primary table fills the remaining viewport

Opt-in on a page's root element (alongside `.refined-page`), desktop (`≥1024px`) only — see §5 for
the two-scroll-model summary. Two DOM shapes are supported by the same CSS block:

- `.table-container` as a **direct child** of the page root (Klienci, Sprzedawcy, Usługi,
  Pracownicy) — the container itself becomes `flex: 1; min-height: 0`.
- `.table-container` **nested inside a wrapping `.form-card`** alongside a section title (Kategorie
  usług, Formy zatrudnienia — both stack a create-form card above the table card) — the `.form-card`
  matched by `:has(> .table-container)` becomes the flex-filling region and turns into its own
  flex-column internally, so its child `.table-container` then fills *that*.

Mobile (`<1024px`) never applies this — the media query gates the whole ruleset, so mobile always
falls back to the page's default whole-page scroll (§5), which is what `.stack-cards` (the
responsive card-per-row table transform, DESIGN-TOKENS.md) already expects. `ScrollTopButton`
("mobile stack-cards pages only") needs zero changes for this — on desktop under
`.page-fills-viewport` nothing ever overflows `#main-content` far enough to cross its `threshold`,
so it naturally stays inert there and only appears on mobile as originally designed.

Shape 2's `.table-container` also gets a **non-media-gated** visual fix (`components.css`, right
after the block above): `.form-card`'s own padding applies to all its children, so without this the
table sat inset inside that padding with its own border/background/shadow drawn a second time
inside the outer card's — a "box inside a box" at every viewport width, not just desktop. Negative
margins (matching `.form-card`'s padding) bleed the table flush to the card's edges and it drops its
own now-redundant chrome, since the wrapping `.form-card` already supplies it — the section title
above keeps the card's normal padding. Both table pages also need `stack-cards-wrap` on their
`.table-container` (Kategorie usług/Formy zatrudnienia were missing it — Klienci/Pracownicy already
carry it) so the same "boxed twice" problem doesn't reappear on mobile's stacked-card view.

### 20.3 Clickable rows

A table row whose record has a "view" action mirrors that action on row-click; if there's no "view"
but there IS an "edit" action (including "enters inline row-edit mode," for the two tables that edit
in place — Kategorie usług, Formy zatrudnienia), row-click mirrors edit instead. A table with neither
(delete-only rows, pure read-only history, or — sync-results-style — two co-equal domain actions with
no natural single default) gets no row-click at all; don't force one.

- Add `row-clickable` to the `<tr>` (or a page-owned equivalent, e.g. `.appt-table tbody
  tr.row-clickable`) — that's what supplies `cursor: pointer`.
- Guard the `onClick` against the row's own action buttons/links with `.closest()` against their
  wrapping class (`.action-icons`, `.row-actions`, or the single interactive element's own tag —
  `a`/`button` — when there's no wrapper), so clicking "Edytuj"/"Usuń" doesn't *also* fire the row's
  navigation. This mirrors ClientsListPage's pre-existing mobile-only tap-anywhere-on-card pattern —
  extended to every viewport size and every table, not reinvented per page.
- When the target isn't an in-SPA route (e.g. ClientDetailPage's appointment-history rows link to
  `/appointment/:id`, still a Jinja page — Wizyty isn't ported yet), use `window.location.href`
  instead of `navigate()`; everything else uses React Router's `navigate()`.
