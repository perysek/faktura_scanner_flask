---
phase: 01-css-architecture
plan: 02
subsystem: ui
tags: [css, typography, jinja2, tailwind, templates]

requires:
  - phase: 01-01
    provides: Global .page-title and .page-subtitle definitions added to output.css via @layer components

provides:
  - All 38 templates stripped of full .page-title / .page-subtitle CSS redeclarations
  - Every remaining local block is delta-only (margin, line-height, or intentional non-global override)
  - calendar_month.html and calendar_week.html now use global 1.75rem instead of 1.375rem

affects:
  - 01-03 (spacing normalization — may reference template CSS state)
  - 01-04 (stat value normalization — same templates)

tech-stack:
  added: []
  patterns:
    - "Delta-only local blocks: templates may only override .page-title/.page-subtitle for spacing (margin/line-height), never for font-size/font-weight/font-family/letter-spacing/color"
    - "Non-standard subtitle overrides preserved: 0.75rem for compact calendar views, 0.875rem for form context subtitles, monospace for UUID display"

key-files:
  created: []
  modified:
    - "templates/appointments/calendar_month.html — removed 1.375rem override, kept margin-bottom: 0.25rem delta"
    - "templates/appointments/calendar_week.html — same as calendar_month"
    - "templates/dashboard/index.html — reduced to .page-title { margin: 0; }"
    - "templates/invoices/list_refined.html — reduced to margin: 0; line-height: 1.2; kept media query"
    - "templates/roles/list.html — .page-title block deleted entirely (no delta)"
    - "templates/users/list.html — .page-title block deleted entirely (no delta)"
    - "All other 32 templates — reduced to margin-only delta or block deleted"

key-decisions:
  - "services/view.html .page-subtitle kept as-is: contains display:flex/align-items/gap/flex-wrap which are genuine non-global layout deltas"
  - "roles/list.html and users/list.html .page-title blocks deleted entirely: had only font-size/font-weight/letter-spacing, zero local delta"
  - "invoices/list_refined.html responsive media query at line ~628 preserved: legitimate 1.25rem breakpoint override at max-width:1024px"

patterns-established:
  - "Template .page-title rule: keep ONLY if block contains margin-bottom, margin shorthand, or line-height; delete if only global-matching properties"
  - "Template .page-subtitle rule: keep ONLY if font-size differs from 0.8125rem, has font-family, or has margin-bottom; delete exact-global matches"

requirements-completed: [TYPO-01, TYPO-02]

duration: 9min
completed: 2026-03-19
---

# Phase 1 Plan 02: Strip Local Typography Redeclarations Summary

**Removed 253 lines of dead CSS across 38 templates — all .page-title and .page-subtitle full redeclarations replaced with delta-only blocks or deleted, fixing 1.375rem calendar override (TYPO-02) and eliminating global duplicates (TYPO-01)**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-19T04:22:20Z
- **Completed:** 2026-03-19T04:31:39Z
- **Tasks:** 3
- **Files modified:** 38

## Accomplishments
- Stripped 253 lines of redundant CSS from 38 Jinja2 templates in a single atomic commit
- Fixed critical TYPO-02 regression: `calendar_month.html` and `calendar_week.html` no longer override `.page-title` font-size with `1.375rem` — both now inherit the global `1.75rem`
- Closed TYPO-01: zero templates now contain an exact-duplicate `.page-subtitle` block matching `color: var(--color-ink-muted); font-size: 0.8125rem; font-weight: 300`
- Preserved all 7 intentional non-standard overrides (0.75rem compact subtitles, 0.875rem form subtitles, monospace UUID display, flex-layout subtitle, responsive media query)

## Task Commits

1. **Tasks 1+2+3: Strip .page-title and .page-subtitle blocks + build verify** - `66bf6bb` (refactor)

**Plan metadata:** _(docs commit to follow)_

## Files Created/Modified

- `templates/appointments/calendar_month.html` - `.page-title { margin-bottom: 0.25rem; }` (was 1.375rem override)
- `templates/appointments/calendar_week.html` - Same as calendar_month
- `templates/dashboard/index.html` - `.page-title { margin: 0; }` (was 1.5rem full block)
- `templates/invoices/list_refined.html` - `.page-title { margin: 0; line-height: 1.2; }` (was 1.5rem full block, media query preserved)
- `templates/invoices/create.html` - `.page-title { margin: 0; }` (was 1.5rem full block)
- `templates/invoices/edit.html` - `.page-title { margin: 0 0 0.25rem 0; }` (was 1.5rem full block)
- `templates/invoices/upload.html` - `.page-title { margin: 0; }` (was 1.5rem full block)
- `templates/sellers/create.html` - `.page-title { margin: 0 0 0.25rem 0; }` (was 1.5rem full block)
- `templates/sellers/edit.html` - `.page-title { margin: 0 0 0.25rem 0; }` (was 1.5rem full block)
- `templates/sellers/list_refined.html` - `.page-title { margin: 0; }` (was 1.5rem full block)
- `templates/history/list_refined.html` - `.page-title { margin: 0; }` (was 1.5rem full block)
- `templates/settings/email.html` - `.page-title { margin: 0 0 0.25rem 0; }` (was 1.5rem full block)
- `templates/roles/list.html` - `.page-title` block deleted entirely (no local delta)
- `templates/users/list.html` - `.page-title` block deleted entirely (no local delta)
- `templates/auth/change_password.html` - `.page-title { margin-bottom: 2rem; }`
- `templates/roles/create.html` - `.page-title { margin-bottom: 2rem; }`
- `templates/users/create.html` + `users/edit.html` - `.page-title { margin-bottom: 2rem; }`
- All remaining 20 templates - reduced to `margin-bottom: 0.25rem` or `margin-bottom: 0.5rem` delta
- All exact-global `.page-subtitle` blocks deleted from 20+ templates (appointments, clients, employees, income, services, roles/list, users/list)

## Decisions Made

- `services/view.html` `.page-subtitle` kept as-is: its `display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap` are genuine layout deltas not in the global definition
- `roles/list.html` and `users/list.html` `.page-title` blocks deleted entirely since their only content was global-matching properties with no local delta
- The responsive media query in `invoices/list_refined.html` (`@media (max-width: 1024px) { .page-title { font-size: 1.25rem; } }`) was explicitly preserved as a legitimate responsive override

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — all file re-reads on linter modification were handled transparently.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- TYPO-01 and TYPO-02 requirements closed — typography is now globally uniform
- All templates defer to `output.css` `@layer components` for base typography
- Phase 01-03 can safely rely on `.page-title` and `.page-subtitle` being globally defined without local interference
- Phase 01-04 same

---
*Phase: 01-css-architecture*
*Completed: 2026-03-19*
