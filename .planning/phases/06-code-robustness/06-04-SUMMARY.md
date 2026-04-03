---
phase: 06-code-robustness
plan: "04"
subsystem: email-service
tags: [exception-handling, logging, credential-masking, email, export]
dependency_graph:
  requires: ["06-01"]
  provides: ["FIX-03", "IMPR-06"]
  affects: ["services/email_service.py", "services/export_service.py"]
tech_stack:
  added: []
  patterns:
    - "specific exception catch: imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError"
    - "credential-safe logging: log type(e).__name__ not str(e)"
    - "TDD: RED-GREEN cycle with file-scan tests"
key_files:
  created: []
  modified:
    - services/email_service.py
    - services/export_service.py
    - tests/services/test_email_service.py
decisions:
  - "Log type(e).__name__ instead of str(e) in connect() — IMAP servers sometimes echo credentials in error messages"
  - "Update existing tests that used bare Exception to use OSError — connection refused is an OS-level error"
  - "Pre-existing IBAN validator test failure deferred (out of scope)"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-03"
  tasks_completed: 2
  files_modified: 3
---

# Phase 06 Plan 04: EmailService Error Handling — Specific Exceptions, Logging, Credential Masking Summary

**One-liner:** EmailService bare except blocks replaced with specific IMAP/OS exceptions and print() replaced with credential-safe logging using type(e).__name__ pattern.

## What Was Built

Fixed all EmailService error handling and export_service.py bare except as a bonus:

**EmailService (services/email_service.py):**
- Replaced 3 bare `except:` blocks in `_extract_email_body_text()` with `except (UnicodeDecodeError, LookupError)` and `except AttributeError`
- Replaced `except Exception` in `connect()` with specific `imaplib.IMAP4.error` and `OSError` handlers
- Replaced `except Exception` in `fetch_pdf_attachments()` per-folder with `imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError`
- Replaced `except Exception` in `_process_email()` with `imaplib.IMAP4.error, imaplib.IMAP4.abort, OSError, ValueError, KeyError`
- Replaced `except Exception` in `_save_attachment()` with `OSError, IOError`
- Replaced `except Exception` in `test_connection()` static method with specific IMAP/OS exceptions
- Replaced all `print()` calls (6 total) with appropriate `logging.info/error/warning/debug`
- Credential masking: `connect()` logs `type(e).__name__` not `str(e)` — IMAP error messages can echo the password
- `disconnect()` already correct; `print()` there also replaced with `logging.info`

**export_service.py:**
- Replaced bare `except:` with `except TypeError`
- Fixed column width bug: comparison used `len(str(cell.value))` but assignment used `len(cell.value)` — now both use `str()`
- Added `cell.value is not None` guard

## Tests Added (TDD)

New test classes in `tests/services/test_email_service.py`:

- `TestEmailServiceCredentialMasking.test_connect_failure_does_not_log_password` — uses `caplog` to assert password absent from log output
- `TestEmailServiceCredentialMasking.test_connect_imap_error_returns_false` — verifies IMAP4.error caught specifically
- `TestEmailServiceCredentialMasking.test_connect_os_error_returns_false` — verifies OSError caught specifically
- `TestEmailServiceSpecificExceptions.test_extract_email_body_text_catches_unicode_decode_error` — smoke test
- `TestEmailServiceSpecificExceptions.test_extract_email_body_text_returns_empty_on_attribute_error` — None input returns ''
- `TestEmailServiceSpecificExceptions.test_fetch_pdf_attachments_catches_imap_error_per_folder` — continues after IMAP error
- `TestEmailServiceSpecificExceptions.test_no_bare_except_blocks` — file-scan test (0 bare excepts)
- `TestEmailServiceSpecificExceptions.test_no_print_calls` — file-scan test (0 print() calls)

Total: 19 email service tests pass (was 11 before).

## Verification Results

| Check | Result |
|-------|--------|
| `grep -c "except:" services/email_service.py` | 0 |
| `grep -c "print(" services/email_service.py` | 0 |
| `grep -c "logging.*" services/email_service.py` | 15 |
| `grep -c "imaplib.IMAP4.error" services/email_service.py` | 7 |
| `grep -c "type(e).__name__" services/email_service.py` | 16 |
| password in logging lines | none |
| `grep -c "except:" services/export_service.py` | 0 |
| `grep -c "except TypeError" services/export_service.py` | 1 |
| Email service tests | 19/19 |
| Full suite | 274/275 (1 pre-existing IBAN failure) |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| RED | 2141da6 | test(06-04): add failing tests for credential masking and specific exceptions |
| GREEN | 6c1b679 | feat(06-04): fix EmailService error handling |
| Task 2 | 9f86ec6 | fix(06-04): replace bare except in export_service.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing tests to use OSError instead of bare Exception**
- **Found during:** GREEN phase of Task 1
- **Issue:** Two existing tests (`test_connect_failure_sets_connected_false`, `test_connection_failure`) used `Exception("Connection refused")` as mock side effect. Once `connect()` was narrowed to only catch `imaplib.IMAP4.error` and `OSError`, these tests started failing.
- **Fix:** Changed `Exception("Connection refused")` to `OSError("Connection refused")` — semantically correct since "connection refused" is an OS-level network error.
- **Files modified:** `tests/services/test_email_service.py`

### Deferred Issues

**Pre-existing failure:** `tests/utils/test_validators.py::TestIBANValidator::test_iban_inny_kraj_nie_pl` — IBANValidator accepts foreign IBANs when it should reject them. Confirmed pre-existing (fails on baseline without my changes). Added to `deferred-items.md`.

## Self-Check: PASSED
