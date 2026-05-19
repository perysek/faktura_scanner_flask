---
title: "Phase 07: Session Management Endpoints"
description: "Build GET /api/import/session-status and POST /api/import/reconnect-session — the two endpoints that surface caldis.pl session health and let admins refresh the session file from within the UI."
skill: server-action-builder
status: pending
group: "http-layer"
dependencies: [phase-06-sse-progress-stream]
tags: [phase, implementation, flask, route, playwright, session]
created: 2026-05-20
updated: 2026-05-20
---

# Phase 07: Session Management Endpoints

**Context:** [[plan|Master Plan]] | **Dependencies:** Phase 06 | **Status:** Pending

---

## Overview

Add two routes to the existing `routes/import_routes.py` blueprint created in Phase 06:

1. **`GET /api/import/session-status`** — reads `assets/temp/caldis_session.json`, returns `{status: "active"|"expired"|"missing", age_days: N}`.
2. **`POST /api/import/reconnect-session`** — launches Playwright in headed mode on the server host so the admin can log in to caldis.pl manually; writes the storage state to the session file; returns `{status: "active"}` on success or 503 on headless servers.

**Goal:** The import UI can show an accurate session health badge on page load, and admins can refresh an expired session without touching the command line.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** Phase 09 uses `GET /api/import/session-status` on page load to set the badge colour. Phase 10 uses `POST /api/import/reconnect-session` when the admin clicks "Odnów sesję".
- **Server Layer:** Two new routes on the existing `import_bp`; no new files.
- **Database Layer:** None — session state is file-based.
- **Integrations:** Playwright (async, subprocess via `asyncio.run()` in a thread).

### User Workflow

**Session status check (automatic, on page load):**

1. Browser opens `/import` page
2. Page JS calls `GET /api/import/session-status`
3. Server reads `SESSION_FILE.stat().st_mtime` (or checks existence)
4. Returns `{status: "active", age_days: 3.2}` → badge renders green
5. If `age_days >= 30` → returns `{status: "expired"}` → badge renders yellow + reconnect button appears
6. If file missing → returns `{status: "missing"}` → badge renders red + reconnect button appears

**Reconnect flow (admin-triggered, only on GUI-accessible server):**

1. Admin clicks "Odnów sesję" button
2. JS calls `POST /api/import/reconnect-session`
3. Server checks headless flag (see ADR-07-01)
4. If headless → returns 503 with `{error: "Serwer nie ma interfejsu graficznego..."}` → frontend shows manual instructions
5. If GUI available → launches `asyncio.run(reconnect_playwright_session(headed=True))` in a thread → waits up to 120s for the admin to complete manual login
6. On session saved → returns `{status: "active"}`
7. Frontend updates badge to green, hides reconnect button

### Problem Being Solved

**Pain Point:** Without this endpoint, admins have to SSH/RDP into the server and run `python scripts/import_appointments_playwright.py --headed` — impossible for non-technical users and breaks the "do everything from the browser" goal.

### Integration Points

**Upstream Dependencies:**
- Phase 06 — `import_bp` exists in `routes/import_routes.py`
- `scripts/import_appointments_playwright.py` — `fetch_xlsx_playwright()` is reused in stripped-down form (login + session save only, no download)

**Downstream Consumers:**
- Phase 09 — page template reads session status on load
- Phase 10 — reconnect button POSTs to this endpoint

**Data Flow:**

```
Browser ──GET /api/import/session-status──► Flask
                                             │
                                             └─► os.path.exists(SESSION_FILE)
                                                 → stat().st_mtime → age calculation
                                                 → jsonify({status, age_days})

Browser ──POST /api/import/reconnect-session──► Flask
                                                 │
                                                 ├─► _is_headless_server() check
                                                 │     └─► True → 503
                                                 │
                                                 └─► thread: asyncio.run(_reconnect())
                                                       └─► playwright headed login
                                                       └─► ctx.storage_state(path=SESSION_FILE)
                                                       └─► jsonify({status: "active"})
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Session expiry window:** The plan assumed 30 days based on typical caldis.pl cookie lifetime. Is 30 days correct, or should the threshold be configurable via an env var?
   - **Assumptions if unanswered:** 30-day hard-coded threshold. No env var in this phase.
   - **Impact:** Admins with short-lived sessions may see "expired" incorrectly; easy to adjust later.

2. **Reconnect timeout:** Admin has up to 120s to complete manual login. Is that enough time for slow reCAPTCHA challenges?
   - **Assumptions if unanswered:** 120s — matches the reference script's `page.wait_for_url(..., timeout=120_000)`.
   - **Impact:** Longer timeout = better UX; shorter = faster failure detection.

3. **Headless detection:** On Windows, `DISPLAY` env var is not the right signal. See ADR-07-01 for the chosen approach.

### Validation Checklist

- [ ] Phase 06 merged — `import_bp` exists
- [ ] `assets/temp/` directory exists (created by `config/settings.py`)
- [ ] Playwright installed: `playwright install chromium` was run on the server
- [ ] `SESSION_FILE` path constant is consistent between this file and `scripts/import_appointments_playwright.py`

> [!CAUTION]
> The reconnect endpoint blocks the request thread for up to 120s while Playwright runs. Waitress (Windows) and Gunicorn have worker timeout settings — ensure the server timeout is >= 130s. Alternatively run the Playwright call in a background thread and let the endpoint poll with retries. See ADR-07-02.

---

## Requirements

### Functional

**Route: `GET /api/import/session-status`**
- Auth: `@login_required` + `@module_permission_required('data_import')`
- Logic:
  - `SESSION_FILE = PROJECT_ROOT / 'assets' / 'temp' / 'caldis_session.json'`
  - If not exists → `{"status": "missing", "age_days": null}`
  - If exists → `age_days = (time.time() - SESSION_FILE.stat().st_mtime) / 86400`
  - If `age_days < 30` → `{"status": "active", "age_days": round(age_days, 1)}`
  - Else → `{"status": "expired", "age_days": round(age_days, 1)}`
- No DB access.

**Route: `POST /api/import/reconnect-session`**
- Auth: `@login_required` + `@module_permission_required('data_import')`
- Body: none required (uses server-side credentials from env or session file)
- Logic:
  1. Call `_is_headless_server()` → if True: raise `AppError('Serwer nie ma interfejsu graficznego...', status_code=503)`
  2. Run `asyncio.run(_do_reconnect_playwright())` — this calls into a stripped-down version of `fetch_xlsx_playwright` that logs in and saves the session, then exits before the download step
  3. On success: return `{"status": "active"}`
  4. On `RuntimeError` from Playwright: reraise as `AppError` with the message

### Technical

```python
import asyncio
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = PROJECT_ROOT / 'assets' / 'temp' / 'caldis_session.json'
SESSION_MAX_AGE_DAYS = 30


def _is_headless_server() -> bool:
    """Return True when the host cannot open a visible browser window.

    On Linux: no DISPLAY env var → headless.
    On Windows: always has a display (even Remote Desktop counts).
    On macOS: always has a display.
    """
    if sys.platform.startswith('linux'):
        return not os.environ.get('DISPLAY')
    return False


async def _do_reconnect_playwright() -> None:
    """Launch a headed Playwright browser, wait for manual login, save session."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context(accept_downloads=False)
        page = await ctx.new_page()

        await page.goto('https://caldis.pl/logowanie', wait_until='networkidle')
        logger.info('Czekam na reczne logowanie admina (max 120s)...')

        await page.wait_for_url(
            lambda url: 'logowanie' not in url.lower(),
            timeout=120_000,
        )
        logger.info('Zalogowano pomyslnie — zapisuje sesje.')

        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        await ctx.storage_state(path=str(SESSION_FILE))
        logger.info('Sesja zapisana: %s', SESSION_FILE.name)
        await browser.close()
```

Add these routes to `routes/import_routes.py` (the file created in Phase 06):

```python
@import_bp.route('/import/session-status', methods=['GET'])
@login_required
@module_permission_required('data_import')
def get_session_status():
    """Return caldis.pl session file health."""
    if not SESSION_FILE.exists():
        return jsonify({'status': 'missing', 'age_days': None})
    age_days = (time.time() - SESSION_FILE.stat().st_mtime) / 86400
    status = 'active' if age_days < SESSION_MAX_AGE_DAYS else 'expired'
    return jsonify({'status': status, 'age_days': round(age_days, 1)})


@import_bp.route('/import/reconnect-session', methods=['POST'])
@login_required
@module_permission_required('data_import')
def reconnect_session():
    """Launch headed Playwright browser for manual caldis.pl re-login."""
    try:
        if _is_headless_server():
            raise AppError(
                'Serwer nie ma interfejsu graficznego. '
                'Uruchom recznie: python scripts/import_appointments_playwright.py --headed',
                status_code=503,
            )
        asyncio.run(_do_reconnect_playwright())
        return jsonify({'status': 'active'})
    except AppError:
        raise
    except RuntimeError as exc:
        logger.exception('Playwright reconnect failed')
        raise AppError(f'Blad polaczenia z caldis.pl: {exc}')
    except Exception:
        logger.exception('Unexpected error in reconnect_session')
        raise AppError('Wystapil blad serwera')
```

---

## Decision Log

### Headless Server Detection (ADR-07-01)

**Date:** 2026-05-20
**Status:** Accepted

**Context:** The reconnect endpoint must detect whether the server can open a visible browser window. On Linux without a display server (Vultr VPS), headed Playwright raises `Error: Target page, context or browser has been closed` or a similar exception because there's no X11/Wayland compositor. On Windows Server (the current production host), a display is always available — even when accessed via Remote Desktop.

**Decision:** Check `sys.platform.startswith('linux') and not os.environ.get('DISPLAY')`. Return 503 with clear manual instructions if headless.

**Consequences:**
- **Positive:** Works correctly on both Windows Server (current prod) and Vultr (headless). Clear error message guides admins.
- **Negative:** A Linux box WITH a display server (unlikely for a server) would incorrectly allow the reconnect. This is a non-issue for current deployment.
- **Neutral:** macOS (dev machines) always passes the check.

### Reconnect as Synchronous Request (ADR-07-02)

**Date:** 2026-05-20
**Status:** Accepted

**Context:** The reconnect waits up to 120s for the admin to complete the reCAPTCHA and login flow. Running this synchronously blocks the request worker for that duration.

**Decision:** Accept the synchronous block for now. Waitress on Windows Server handles concurrent requests via threads; the reconnect tie-up is one worker for up to 120s — acceptable because: (a) reconnect is rare (once per ~30 days), (b) only admins can trigger it, (c) the alternative (background thread + polling) adds complexity for a once-a-month operation.

**Consequences:**
- **Positive:** Simple code, no polling round-trips.
- **Negative:** If Waitress is configured with a low thread count, the reconnect could exhaust a worker. Mitigation: Waitress defaults to 4 threads — unlikely to be fully saturated by a single admin session.
- **Neutral:** If the server gains a worker timeout < 120s (e.g. nginx `proxy_read_timeout`), increase the timeout or switch to the background-thread approach.

---

## Implementation Steps

### Step 0: Test Definition (TDD)

Add to `tests/routes/test_import_routes.py`:

```python
class TestSessionStatus:

    def test_status_missing_when_no_file(self, client, login_admin, tmp_path, monkeypatch):
        monkeypatch.setattr('routes.import_routes.SESSION_FILE',
                            tmp_path / 'nonexistent.json')
        resp = client.get('/api/import/session-status')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'missing'

    def test_status_active_when_file_fresh(self, client, login_admin, tmp_path, monkeypatch):
        f = tmp_path / 'caldis_session.json'
        f.write_text('{}')
        monkeypatch.setattr('routes.import_routes.SESSION_FILE', f)
        resp = client.get('/api/import/session-status')
        data = resp.get_json()
        assert data['status'] == 'active'
        assert data['age_days'] < 1

    def test_status_expired_when_file_old(self, client, login_admin, tmp_path, monkeypatch):
        import os
        f = tmp_path / 'caldis_session.json'
        f.write_text('{}')
        # backdate mtime by 31 days
        old_mtime = time.time() - (31 * 86400)
        os.utime(f, (old_mtime, old_mtime))
        monkeypatch.setattr('routes.import_routes.SESSION_FILE', f)
        resp = client.get('/api/import/session-status')
        assert resp.get_json()['status'] == 'expired'


class TestReconnectSession:

    def test_reconnect_503_on_headless(self, client, login_admin, monkeypatch):
        monkeypatch.setattr('routes.import_routes._is_headless_server', lambda: True)
        resp = client.post('/api/import/reconnect-session')
        assert resp.status_code == 503

    def test_reconnect_calls_playwright_on_gui_server(self, client, login_admin, monkeypatch):
        monkeypatch.setattr('routes.import_routes._is_headless_server', lambda: False)
        async def fake_reconnect():
            pass
        monkeypatch.setattr('routes.import_routes._do_reconnect_playwright', fake_reconnect)
        resp = client.post('/api/import/reconnect-session')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'active'
```

- [ ] `pytest tests/routes/test_import_routes.py::TestSessionStatus -v` — all fail (routes don't exist yet)
- [ ] `pytest tests/routes/test_import_routes.py::TestReconnectSession -v` — all fail

### Step 1: Add Constants and Helpers

At the top of `routes/import_routes.py` (after existing imports), add:

```python
import asyncio
import os
import sys
import time as _time_module

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_FILE = PROJECT_ROOT / 'assets' / 'temp' / 'caldis_session.json'
SESSION_MAX_AGE_DAYS = 30
```

Add `_is_headless_server()` and `_do_reconnect_playwright()` helper functions (see Requirements section above).

### Step 2: Add Route Handlers

Append to `routes/import_routes.py`:
- `get_session_status()` — full implementation from Requirements
- `reconnect_session()` — full implementation from Requirements

### Step 3: Verify Tests

- [ ] `pytest tests/routes/test_import_routes.py -v` — all pass
- [ ] `pytest tests/` — no regressions

---

## Verifiable Acceptance Criteria

**Critical Path:**

- [ ] `GET /api/import/session-status` returns `{status: "missing"}` when `assets/temp/caldis_session.json` doesn't exist
- [ ] `GET /api/import/session-status` returns `{status: "active", age_days: N}` when file is < 30 days old
- [ ] `GET /api/import/session-status` returns `{status: "expired", age_days: N}` when file is >= 30 days old
- [ ] `POST /api/import/reconnect-session` returns 503 when `_is_headless_server()` is True
- [ ] `POST /api/import/reconnect-session` returns `{status: "active"}` on successful Playwright reconnect
- [ ] Both routes require `@login_required` + `@module_permission_required('data_import')`
- [ ] All new tests pass

**Security:**

- [ ] `SESSION_FILE` contents are never returned in any response
- [ ] `age_days` is the only metadata exposed — no file paths in the response

---

## Quality Assurance

### Test Plan

#### Manual Testing

- [ ] **Missing file:** Delete `assets/temp/caldis_session.json`, open `/import` → badge shows red "Brak sesji"
- [ ] **Expired simulation:** Set the file mtime to 35 days ago with `os.utime()` in a shell → badge shows yellow "Wygasła"
- [ ] **Reconnect on Windows dev box:** Click "Odnów sesję" → Chromium opens, log in manually → badge flips to green
- [ ] **Reconnect on Vultr (headless):** POST to reconnect → 503 with clear error message

#### Automated Testing

```bash
pytest tests/routes/test_import_routes.py -v
pytest tests/
```

### Review Checklist

- [ ] `SESSION_FILE` constant matches the path in `scripts/import_appointments_playwright.py`
- [ ] Both routes carry `@module_permission_required('data_import')`
- [ ] `_do_reconnect_playwright` logs at `logger.info` level (no `print()`)
- [ ] `asyncio.run()` is called at route level, not inside an existing event loop (Flask/Waitress don't run an event loop by default — this is safe)
- [ ] `AppError` with `status_code=503` is used for headless server rejection (not a raw `abort(503)`)

---

## Dependencies

### Upstream (Required Before Starting)

- **Phase 06** — `import_bp` and `routes/import_routes.py` exist

### Downstream (Will Use This Phase)

- **Phase 09** — page template calls session-status on load
- **Phase 10** — reconnect button calls reconnect-session

### External Services

- **caldis.pl** — Playwright connects to this during reconnect
- **Playwright/Chromium** — must be installed on server: `playwright install chromium`

---

## Completion Gate

### Sign-off

- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Manual session-status smoke on both file states confirmed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `feat(import): phase 07 — session management endpoints`

---

## Notes

### Technical Considerations

- `asyncio.run()` creates a fresh event loop each call — this is correct in a sync Flask route (Waitress and the dev server have no pre-existing event loop). Do NOT use `asyncio.get_event_loop().run_until_complete()` — it's deprecated in Python 3.10+.
- `_is_headless_server()` must be a standalone function (not a lambda) so it can be monkeypatched in tests.
- `time` is already imported as `_time` in Phase 06 for `_time.sleep()`. Add `import time as _time_module` if needed to avoid the naming collision.

### Known Limitations

- The reconnect endpoint blocks for up to 120s — see ADR-07-02.
- No way to cancel an in-progress reconnect from the browser (browser can close the tab, but the Playwright session on the server continues until timeout).

---

**Previous:** [[phase-06-sse-progress-stream|Phase 06: SSE Progress Stream + Status Endpoint]]
**Next:** [[phase-08-import-routes|Phase 08: Start Import + History Endpoints + Page Route]]
