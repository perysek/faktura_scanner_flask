---
phase: 06
slug: code-robustness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | none — runs with `pytest tests/` from project root |
| **Quick run command** | `python -m pytest tests/services/test_email_service.py tests/repositories/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/services/test_email_service.py tests/repositories/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | IMPR-03 | unit | `pytest tests/services/test_appointment_service.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | IMPR-03 | unit | `pytest tests/repositories/test_base_repository.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | IMPR-03 | unit | `pytest tests/routes/test_api_routes.py -x -q` | ✅ partial | ⬜ pending |
| 06-02-01 | 02 | 2 | IMPR-04 | unit | `pytest tests/repositories/test_appointment_repository.py -x -q` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | IMPR-04 | unit | `pytest tests/routes/test_appointment_routes.py -x -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 3 | IMPR-05 | unit | `pytest tests/repositories/test_client_repository.py -x -q` | ❌ W0 | ⬜ pending |
| 06-04-01 | 04 | 4 | FIX-03 | unit | `pytest tests/services/test_email_service.py -x -q` | ✅ partial | ⬜ pending |
| 06-04-02 | 04 | 4 | IMPR-06 | unit | `pytest tests/services/test_email_service.py::TestEmailServiceConnect -x -q` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/services/test_appointment_service.py` — stubs for IMPR-03 exception reparenting
- [ ] `tests/repositories/test_base_repository.py` — stubs for IMPR-03 DatabaseConnectionError
- [ ] `tests/repositories/test_appointment_repository.py` — stubs for IMPR-04 enum usage
- [ ] `tests/routes/test_appointment_routes.py` — stubs for IMPR-04 route status validation
- [ ] `tests/repositories/test_client_repository.py` — stubs for IMPR-05 column projection
- [ ] `tests/services/test_email_service.py` — extend with credential masking tests (file exists)

**Baseline:** 249 tests collected, 248 passing, 1 failing (pre-existing `test_iban_inny_kraj_nie_pl` — unrelated).

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
