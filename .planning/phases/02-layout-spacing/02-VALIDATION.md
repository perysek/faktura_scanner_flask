---
phase: 2
slug: layout-spacing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None — pure CSS/template work; grep audit serves as proxy |
| **Config file** | none — Wave 0 not applicable |
| **Quick run command** | `grep -rn "padding.*!important" templates/ --include="*.html" \| grep "main-content"` |
| **Full suite command** | `grep -rn "padding.*!important" templates/ --include="*.html"` (expect 0 hits on #main-content) |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick grep — confirm `!important` count decreasing
- **After every plan wave:** Full grep + visual spot-check of one representative page per category
- **Before `/gsd:verify-work`:** Zero `!important` padding hits on `#main-content` + visual regression on 5 key pages
- **Max feedback latency:** 5 seconds (grep only)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| base-html-change | 02-01 | 1 | SPAC-01 | grep | `grep -n "p-2\|p-0" templates/base.html` — should show `p-0` | ✅ | ⬜ pending |
| important-strip | 02-01 | 2 | SPAC-01 | grep | `grep -rn "#main-content.*!important\|padding.*!important" templates/ --include="*.html"` — should return 0 for #main-content context | ✅ | ⬜ pending |
| max-width-forms | 02-02 | 2 | SPAC-02 | grep | `grep -n "max-width" templates/clients/create.html templates/clients/edit.html` — should show 900px | ✅ | ⬜ pending |
| max-width-lists | 02-02 | 2 | SPAC-02 | grep | `grep -n "max-width" templates/employees/list.html templates/services/list.html` — should show 1400px | ✅ | ⬜ pending |
| max-width-calendars | 02-02 | 2 | SPAC-02 | grep | `grep -n "max-width" templates/appointments/calendar.html templates/appointments/calendar_week.html` — should return empty or only @media queries | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

No Wave 0 required — no new test infrastructure needed for this CSS-only phase.

*Existing grep commands serve as machine-checkable proxies for SPAC-01.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Form pages visually contained at 900px | SPAC-02 | No browser automation | Open clients/create, employees/create, services/create — content should not span full browser width |
| List pages use full 1400px area | SPAC-02 | No browser automation | Open clients/list, employees/list — table should fill most of viewport at 1400px+ screen |
| Calendar pages are truly full-width | SPAC-02 | No browser automation | Open calendar — grid should extend edge to edge with no visible margin |
| No visual regression on key pages | SPAC-01 | Changes affect all pages via base.html | Spot-check: dashboard, invoices/list, sellers/list_refined, clients/list, appointments/list |
| analytics/dashboard.html not flush to edge | SPAC-01 | New padding addition | Verify content has appropriate padding after base.html p-0 change |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
