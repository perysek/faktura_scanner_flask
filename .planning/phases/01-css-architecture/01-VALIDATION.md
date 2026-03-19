---
phase: 1
slug: css-architecture
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None — no pytest/jest/vitest detected; CSS validation via grep + build |
| **Config file** | none — Wave 0 not applicable for CSS-only phase |
| **Quick run command** | `npm run build:css` |
| **Full suite command** | `npm run build:css && grep -rn "\.page-title\s*{" templates/ --include="*.html"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `npm run build:css` — confirms CSS compiles without errors
- **After every plan wave:** Run full grep audit (see Per-Task map) + manual spot-check on 3 key pages
- **Before `/gsd:verify-work`:** All grep audits clean + visual parity confirmed
- **Max feedback latency:** 10 seconds (build only)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| global-add | 01 | 1 | TYPO-01 | build | `npm run build:css` | ✅ | ⬜ pending |
| calendar-fix | 01 | 1 | TYPO-02 | grep | `grep "font-size.*1\.375rem" templates/appointments/calendar_month.html templates/appointments/calendar_week.html` — should return empty | ✅ | ⬜ pending |
| stat-value-fix | 01 | 2 | TYPO-03 | grep | `grep -n "font-size.*1\.75rem\|font-size.*1\.5rem" templates/clients/list.html templates/employees/list.html templates/income/dashboard.html` — should return only non-stat-value occurrences | ✅ | ⬜ pending |
| template-strip | 01 | 2 | TYPO-01 | grep | `grep -rn "\.page-title\s*{" templates/ --include="*.html"` — should return 0 full redeclarations (only delta overrides acceptable) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

No Wave 0 required — no new test infrastructure needed. Existing `npm run build:css` and `grep` serve as validation tools.

*Existing infrastructure covers all automated verification for this phase.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `.page-title` visually same size on all pages including calendars | TYPO-02 | No CSS unit testing in project | Navigate: dashboard → calendar_month → clients/list — headline must look same size across all three |
| `.stat-value` visually consistent at 1.25rem across stat cards | TYPO-03 | No CSS unit testing in project | Compare: dashboard/index, clients/list, employees/list, income/dashboard — stat numbers must appear at same density/size |
| No visual regression on any page | TYPO-01 | Changes affect 29+ templates | Spot-check 5 pages: invoices/list, appointments/list, sellers/list_refined, dashboard/index, clients/list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
