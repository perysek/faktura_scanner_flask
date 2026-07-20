# StyleSeed — Design Lock
<!-- Selections persist here. This file cannot waive StyleSeed core invariants. -->
- App domain: internal business operations (salon management: invoicing, appointments, staff, analytics)
- Surface: web-app (server-rendered Flask + Jinja2, no SPA framework)
- Surface adapter: product-ui (renderer: project framework — this app's own templates, not the bundled React scaffold)
- Page type: mixed (dashboards, lists, forms) across the whole authenticated shell
- Output grammar: operations-console
- Grammar path: built-in:engine/RULESETS.md
- Grammar fallback: operations-console
- Reference confidence: n/a (grammar chosen from job fit, not compiled from a reference)
- Aesthetic profile: none
- Skin: custom (existing "System B / refined" design system, documented in this repo's CLAUDE.md)
- Primary action (functional): #2563eb — unchanged; kept constant across every theme by deliberate
  existing project convention (decorative brand accent and functional action/focus color are
  intentionally two different roles — see input.css comments at F-008)
- Font: Inter (unchanged)
- Radius: sharp/flat — 2px inputs/buttons/badges, 3px cards/modals (unchanged)
- Elevation: light=flat + hairline borders · dark-family=tonal ramp + hairline (no floating shadows)
- Density: comfortable to compact (unchanged)
- Motion: existing cubic-bezier easing curves (unchanged); reduced-motion respected
- Imagery/data role: categorical chart/status colors stay constant across every theme (stable data
  semantics per operations-console rule — a theme changes chrome, not what a color means)
- Signature move: one icon-button theme switcher in the sidebar footer, opening an accessible
  popover menu (role="menu") of 5 named themes
- Locked: 2026-07-20

## Theme system (this feature)

Five themes, switched at runtime via `<html data-theme="...">`, persisted client-side
(localStorage — device-level preference, no account sync). Applied via a no-FOUC inline
script in `templates/base.html <head>` (reads localStorage before first paint) plus
`static/js/theme.js` for the popover UI.

| Theme | `data-theme` value | Identity |
|---|---|---|
| Light (current default) | *(absent — `:root` default)* | Unchanged. Zero visual diff from today. |
| Dark | `dark` | Neutral warm-charcoal surfaces, brighter gold accent for legibility. |
| Light blue | `blue` | Cool light surfaces, steel-blue accent (deliberately distinct from the existing `--color-status-scheduled` blue so status badges keep their own meaning). |
| Light green | `green` | Warm-cool light surfaces, sage-green accent (deliberately distinct from `--color-success`). |
| Dimmed brown | `brown` | Muted dark sepia/walnut surfaces — dimmed, not near-black like `dark` — copper accent. |

Tokens that vary per theme: `--color-ink[-muted|-subtle]`, `--color-surface[-warm|-elevated]`,
`--color-border[-subtle]`, `--color-accent[-muted|-deep]`, `--color-on-accent`, all `--sidebar-*`.
Dark-family themes (`dark`, `brown`) additionally override the solid pale `*-bg` status/info/purple
tokens with the existing translucent `*-badge` values (already alpha-blended, so they read
correctly regardless of the underlying surface).

Tokens that stay constant across all 5 themes (by grammar rule — categorical data semantics
must not shift): `--color-success*`, `--color-warning`, `--color-error`, `--color-info*`,
`--color-status-*` (text/badge — only the solid `-bg` fallback tint changes for dark-family),
`--color-chart-*`, `--color-star-*`, `--color-focus-ring` (except a brighter dark-mode variant
on `dark`/`brown` only, needed to clear 3:1 against a near-black background — same hue family).

All five palettes were checked against WCAG AA (4.5:1 body text / 3:1 large text & UI) before
implementation; see the "Fix first" section of the shipped `/ss-score` run for anything
outstanding.

## Known scope boundary

This pass covers the shared design system (`static/css/input.css`), shared chrome
(`templates/base.html`, `templates/components/sidebar.html`), and — because `/ss-verify`
against a real dark-family theme immediately exposed the alternative — every page-scoped
`<style>` block across the app that hardcoded a literal color the theme system needed to
override (see "ss-verify findings" below). Public/marketing pages (`landing/index.html`,
`booking/index.html`, `auth/login.html`, `public/*`, `manual/index.html`) are standalone
templates that never extend `base.html`, so they never receive a `data-theme` attribute
and always render in the light palette regardless of a user's saved preference — verified,
not assumed.

## `/ss-score` (self-assessed, evidence-based)

```
Rule set: operations-console × internal-ops × mixed pages × none
Color discipline      15/16   one accent per theme, semantics kept stable, tokens not hex
Hierarchy/typography  16/16   untouched by this feature
Layout & rhythm        12/12   untouched by this feature
Cards & elevation       9/10   tonal ramp + hairline in dark-family; stat-tile/page contrast a touch subtle
States & a11y          17/18   all 5 palettes WCAG AA-checked pre-ship; -1 pre-existing avatar-monogram gap (below, left alone)
Motion & interaction     6/6   instant open/close, full keyboard nav, no added motion
Coherence              12/12   one accent, one radius/elevation language per theme
Distinctiveness          9/10   clean swatch-menu pattern, not overstyled
Total: 96/100 (A)
```

## `/ss-verify` findings (rendered via gstack `/browse`, real login session, 5 themes + 1 table page)

Two real cross-cutting bugs were caught by looking at pixels, not just reading code — both
fixed before shipping:

1. **Dashboard stat cards/chart panel stayed hardcoded white** under `dark`/`brown` — with
   `--color-ink` correctly flipping to near-white text for those themes, the numbers became
   near-invisible white-on-white. Root cause: 265 occurrences of literal `background: white`/
   `#fff` across 63 page-scoped `<style>` blocks (a much larger version of the same debt already
   fixed in `input.css`). Swept to `var(--color-surface-elevated)` app-wide; zero visual change
   on the (default) light theme, correct elevation on all four new ones.
2. **"Dark button/pill" idiom broke the same way** — `background: var(--color-ink)` paired with
   a hardcoded `color: white` is a widespread idiom (70 sites, 39 files) for primary
   buttons/active pills/toasts. Same root cause: ink flips light in dark-family themes, so the
   paired white text vanished. Added `--color-on-ink` (mirrors `--color-on-accent`) and fixed
   every paired site plus one `--color-ink-muted` hover-state variant found the same way.

**Pre-existing, left alone (not introduced by this feature, and fixing it would change the
locked "light = current default" look):** the sidebar avatar monogram (`13px white text on
`#c9a227` gold, ~2.4:1) was already below WCAG AA in production before this change. The new
themes' avatar text was designed to clear AA from the start (`--color-on-accent` — see palette
table above); light theme keeps its exact current pixels per the "light = unchanged" lock.
