---
phase: 5
slug: data-integrity
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.4 |
| **Config file** | `pytest.ini` (testpaths = tests) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | IMPR-01 | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | IMPR-01 | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete::test_get_all_excludes_deleted -x` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | IMPR-01 | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete::test_search_excludes_deleted -x` | ❌ W0 | ⬜ pending |
| 05-01-04 | 01 | 1 | IMPR-01 | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete::test_statistics_excludes_deleted -x` | ❌ W0 | ⬜ pending |
| 05-01-05 | 01 | 1 | IMPR-01 | unit | `pytest tests/repositories/test_invoice_repository.py::TestPartialUniqueConstraint -x` | ❌ W0 | ⬜ pending |
| 05-01-06 | 01 | 1 | IMPR-01 | unit | `pytest tests/repositories/test_invoice_repository.py::TestSoftDelete::test_find_by_number_excludes_deleted -x` | ❌ W0 | ⬜ pending |
| 05-01-07 | 01 | 1 | FIX-01 | unit | `pytest tests/routes/test_api_routes.py::TestDeleteInvoice -x` | ✅ (partial) | ⬜ pending |
| 05-01-08 | 01 | 1 | FIX-02 | unit | `pytest tests/repositories/test_invoice_repository.py::TestAuditAfterDelete -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/repositories/test_invoice_repository.py` — stubs for IMPR-01 soft delete behavior, FIX-02 audit FK
- [ ] `tests/repositories/__init__.py` — may already exist (directory has `__init__.py`)

*Existing: `tests/routes/test_api_routes.py::TestDeleteInvoice::test_audit_log_event_delete_signature` covers FIX-01 partially — it tests the `log_event` call signature but not the full HTTP DELETE flow.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Soft-deleted invoice disappears from UI list | IMPR-01 | Visual UI confirmation | 1. Delete an invoice via UI 2. Verify it's gone from the list 3. Check DB that `is_deleted=TRUE` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
