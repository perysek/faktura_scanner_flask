---
phase: 04
slug: accessibility-ux-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | grep + DOM attribute checks (static analysis for HTML attributes) |
| **Config file** | none — grep-based verification |
| **Quick run command** | `grep -rn "aria-label\|aria-live\|skip-nav" templates/ --include="*.html" \| wc -l` |
| **Full suite command** | `grep -rn "aria-label" templates/ --include="*.html" && grep -rn "aria-live" templates/ --include="*.html" && grep "skip-nav\|sr-only" templates/base.html` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick aria attribute count
- **After every plan wave:** Run full grep suite
- **Before `/gsd:verify-work`:** Full suite must confirm all targets
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | A11Y-03 | grep | `grep "skip-nav\|sr-only" templates/base.html` | N/A | ⬜ pending |
| 04-01-02 | 01 | 1 | A11Y-01 | grep | `grep -rn "aria-label" templates/appointments/calendar*.html` | N/A | ⬜ pending |
| 04-01-03 | 01 | 1 | A11Y-02 | grep | `grep -rn "aria-live" templates/appointments/calendar.html templates/clients/list.html` | N/A | ⬜ pending |
| 04-02-01 | 02 | 1 | UX-01 | grep | `grep -n "Spróbuj ponownie\|retry" templates/appointments/calendar.html templates/clients/list.html` | N/A | ⬜ pending |
| 04-02-02 | 02 | 1 | UX-02 | grep | `grep -n "main.dashboard" templates/errors/404.html templates/errors/500.html` | N/A | ⬜ pending |
| 04-02-03 | 02 | 1 | COPY-01, UX-03 | grep | `grep -n "Powrót na górę" templates/analytics/dashboard.html && grep -n "Ładowanie" templates/sellers/edit.html` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements — grep-based verification needs no setup.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Screen reader announces content updates | A11Y-02 | Requires screen reader runtime | Enable NVDA/VoiceOver, navigate calendar, verify announcements |
| Keyboard skip-nav works | A11Y-03 | Requires Tab key interaction | Press Tab on page load, verify skip link appears, press Enter, verify focus moves to #main-content |
| Retry button reloads content | UX-01 | Requires triggering error state | Disconnect network, load calendar/client list, verify retry button appears and works |
| 404 CTA routes correctly per role | UX-02 | Requires login as different roles | Login as receptionist → trigger 404 → verify CTA goes to dashboard |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
