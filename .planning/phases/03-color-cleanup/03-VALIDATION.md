---
phase: 03
slug: color-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | grep/ripgrep (static analysis — no runtime tests needed for CSS token replacement) |
| **Config file** | none — grep-based verification |
| **Quick run command** | `grep -rn "#c9a227\|#d97706" templates/ --include="*.html"` |
| **Full suite command** | `grep -rn "#[0-9a-fA-F]\{6\}" templates/ --include="*.html" \| grep -v superadmin_edit` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `grep -rn "#c9a227\|#d97706" templates/ --include="*.html"`
- **After every plan wave:** Run full hex audit grep
- **Before `/gsd:verify-work`:** Full suite must return zero matches for COL-01/COL-02 targets
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | COL-01 | grep | `grep -n "#333\|#c9a227\|#d97706" templates/auth/*.html` | N/A | ⬜ pending |
| 03-01-02 | 01 | 1 | COL-01 | grep | `grep -n "#333\|#c9a227\|#d97706" templates/errors/*.html` | N/A | ⬜ pending |
| 03-02-01 | 02 | 1 | COL-01 | grep | `grep -rn "#333" templates/ --include="*.html" \| grep -v superadmin` | N/A | ⬜ pending |
| 03-03-01 | 03 | 2 | COL-02 | grep | `grep -n "#c9a227" templates/users/list.html` | N/A | ⬜ pending |
| 03-03-02 | 03 | 2 | COL-02 | grep | `grep -n "#d97706" templates/appointments/calendar.html` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements — grep-based verification needs no setup.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual color consistency | COL-01 | CSS var replacement may have slight rendering delta | Open 3 representative pages, compare gold accent visually |
| Calendar coverage bar color | COL-02 | JS getComputedStyle timing on page load | Open calendar day view, verify orange coverage bars render correctly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
