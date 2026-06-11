---
title: "Phase 03: Status-Toast Poller + Overlay Scroll-Lock"
description: "Pause the status poller in background tabs, make toasts dismissable, cap concurrent toasts (Issue 6), and lock body scroll behind modals (Suggestion 1)."
skill: "none"
status: done
group: "shared-behavior"
dependencies: [P01, P02]
tags: [phase, javascript, usability, performance]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 03: Status-Toast Poller + Overlay Scroll-Lock

**Context:** [[plan|Master Plan]] | **Dependencies:** P01, P02 | **Status:** Pending

---

## Overview

The global status-change poller in `base.html` (`setInterval(pollStatusEvents, 5000)`) runs forever — including in backgrounded tabs — and renders `.status-toast` elements with `pointer-events: none`, so they can't be dismissed and a burst stacks an undismissable pile over the bottom-right (covering content/primary actions on mobile). This phase makes the poller pause when the tab is hidden (Page Visibility API), makes toasts dismissable, caps how many show at once, and — reusing the P02 `.scroll-lock` — locks body scroll behind modals (Suggestion 1).

**Goal:** The poller idles in background tabs, toasts can be dismissed and never stack into a wall, and modal backdrops stop the page scrolling behind them.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** The inline `<script>`/`<style>` block in `templates/base.html` (lines ~269–329: `.status-toast` CSS + the poller IIFE). Also `static/js/modals.js` (open/close) + `static/css/input.css` `.modal-overlay` for the scroll-lock.
- **Server Layer:** Unchanged — the `/api/appointments/status-events` endpoint already exists; only client cadence/UX changes.
- **Database Layer:** None.
- **Integrations:** Reuses `.scroll-lock` from P02; defers to `window.showToast` when present (`notifications.js`).

### User Workflow

**Trigger:** Appointment statuses change elsewhere; the poller surfaces toasts. Separately, any modal opens.

**Steps:**
1. Tab focused → poller fetches every 5s; a status change shows a toast.
2. Toast is dismissable (close affordance / tap) and auto-dismisses; at most N visible — extras queue or replace oldest.
3. Tab backgrounded → poller pauses (no fetch, no battery drain); resumes on return.
4. A modal opens → body scroll locks; closes → unlocks.

**Success Outcome:** No undismissable toast pile; no background polling; no scroll-bleed behind dialogs.

### Problem Being Solved

**Pain Point:** Issue 6 (undismissable, background-running, stacking toasts) + Suggestion 1 (page scrolls behind modals).

**Alternative Approach:** Leaving it means mobile users get actions covered by toasts they can't clear.

### Integration Points

**Upstream Dependencies:** P02 (`.scroll-lock` utility).

**Downstream Consumers:** None.

**Data Flow:**
```
visibilitychange ─▶ hidden? clearInterval : start poll
pollStatusEvents ─▶ events ─▶ enqueue toast (cap N) ─▶ dismissable
Modals.show()/close() ─▶ body.classList toggle scroll-lock
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Toast cap policy:** Cap at **3** concurrent; beyond that, drop the oldest (replace) rather than queue indefinitely?
   - **Assumptions if unanswered:** Cap 3, replace-oldest.
   - **Impact:** A queue could delay relevant info; replace-oldest keeps the latest visible.

2. **Dismiss affordance:** Add a small `×` button AND keep tap-to-dismiss + auto-timeout?
   - **Assumptions if unanswered:** Yes — `×` + click-anywhere-on-toast + 6s auto.
   - **Impact:** Without an explicit affordance, discoverability is poor.

3. **showToast delegation:** When `window.showToast` exists (notifications.js), the status poller already delegates to it. Should the cap/dismiss logic live in the fallback `.status-toast` path only, or also harden `showToast`?
   - **Context:** Need to read `static/js/notifications.js` to see if `showToast` already caps/dismisses.
   - **Assumptions if unanswered:** Read `notifications.js`; if `showToast` already dismissable+capped, only fix the fallback path + add visibility-pause. If not, add a shared cap there.
   - **Impact:** Avoid double-implementing.

### Validation Checklist

- [ ] Read `static/js/notifications.js` `showToast` to learn existing capabilities BEFORE coding.
- [ ] P02 merged (`.scroll-lock` available).
- [ ] Cap policy confirmed (3, replace-oldest).

> [!CAUTION]
> The poller block is gated `{% if current_user.is_authenticated %}` — keep that guard; unauthenticated pages must not poll.

---

## Requirements

### Functional

- Poller stops fetching while `document.hidden`; resumes on visible.
- Status toasts are dismissable (× + tap) and auto-dismiss.
- Concurrent status toasts capped (3); oldest replaced beyond cap.
- `.status-toast` no longer has `pointer-events: none`.
- Body scroll locked while any modal is open; unlocked on close.

### Technical

- Edits in `templates/base.html` (poller `<script>` + `.status-toast` `<style>`), `static/js/modals.js` (open/close), and reuse `.scroll-lock` (P02).
- Preserve `prefers-reduced-motion` (already present for `.toast-*`; add for `.status-toast` if animating).
- Preserve delegation to `window.showToast`.

---

## Decision Log

### Replace-oldest cap of 3 (ADR-03-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Bursts stack toasts into an undismissable wall.

**Decision:** Track active status-toasts in an array; at >3, remove the oldest before adding.

**Consequences:** Bounded screen real estate; very old events drop silently (acceptable — they're transient notifications).

### Page Visibility pause (ADR-03-02)

**Date:** 2026-06-10
**Status:** Accepted

**Decision:** Replace the bare `setInterval` with start/stop controlled by `visibilitychange`; do an immediate catch-up poll on becoming visible.

**Consequences:** No background fetch/battery use; a short gap while hidden is fine (the endpoint takes `since=` and returns the delta).

---

## Implementation Steps

### Step 0: Define Verification (do first)

- [ ] Read `static/js/notifications.js` `showToast`; note whether it already dismisses/caps.
- [ ] Playwright/`/browse`: simulate `visibilitychange` (set `document.hidden`) → assert no `/api/appointments/status-events` request fires while hidden; on return → assert a catch-up request fires.
- [ ] Inject 5 fake status toasts → assert ≤3 in DOM; click `×` → assert removed.
- [ ] Open a modal (`Modals.confirm(...)`) → assert `body.scroll-lock`; close → assert removed.
- [ ] Confirm assertions FAIL before the fix.

### Step 1: Visibility-aware poller

- [ ] In `base.html`, replace `setInterval(pollStatusEvents, 5000);` with:
```js
var pollTimer = null;
function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(pollStatusEvents, 5000);
}
function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}
document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
        stopPolling();
    } else {
        pollStatusEvents();   // immediate catch-up
        startPolling();
    }
});
if (!document.hidden) startPolling();
```

### Step 2: Dismissable, capped status toasts

- [ ] In `.status-toast` CSS (base.html `<style>`), remove `pointer-events: none;` and add a cursor + close-button styles:
```css
.status-toast { /* …existing… (drop pointer-events:none) */ cursor: default; }
.status-toast .st-close {
    margin-left: 0.75rem; background: none; border: none; color: #cbd5e1;
    font-size: 1rem; line-height: 1; cursor: pointer; padding: 0;
}
.status-toast .st-close:hover { color: #fff; }
```
- [ ] In the fallback `showStatusToast` (used when `window.showToast` is absent), track active toasts and cap:
```js
var activeStatusToasts = [];
function removeStatusToast(el) {
    var i = activeStatusToasts.indexOf(el);
    if (i > -1) activeStatusToasts.splice(i, 1);
    if (el.parentNode) el.parentNode.removeChild(el);
}
// inside the fallback branch (after creating `el`, before appendChild):
el.style.bottom = (1.5 + activeStatusToasts.length * 3.5) + 'rem';
var close = document.createElement('button');
close.className = 'st-close'; close.setAttribute('aria-label', 'Zamknij'); close.textContent = '×';
close.addEventListener('click', function () { removeStatusToast(el); });
el.appendChild(close);
el.addEventListener('click', function () { removeStatusToast(el); });
activeStatusToasts.push(el);
while (activeStatusToasts.length > 3) { removeStatusToast(activeStatusToasts[0]); }
```
- [ ] Update the auto-remove timeout to call `removeStatusToast(el)` instead of manual `removeChild`.

> [!NOTE]
> If Step-0 finds `window.showToast` (notifications.js) is the actual path in practice AND already caps/dismisses, the fallback fix above still matters (it's the no-`showToast` path) — but confirm `showToast` itself isn't stacking; if it is, apply an equivalent cap there.

### Step 3: Modal body scroll-lock (Suggestion 1)

- [ ] In `static/js/modals.js`, in the show path add `document.body.classList.add('scroll-lock')`, and in the close path (after the closing animation completes / element removed) `document.body.classList.remove('scroll-lock')`.
- [ ] Guard against multiple stacked modals: only remove the lock when `#modal-container` is empty (`if (!document.getElementById('modal-container').children.length) body.classList.remove('scroll-lock')`).

### Step 4: Rebuild + verify

- [ ] `npm run build:css` (CSS in base.html `<style>` is inline, not built — but `.scroll-lock` from P01/P02 must be in `output.css`).
- [ ] Run Step-0 assertions — all PASS.

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] No status-events fetch while `document.hidden`; catch-up fetch on return.
- [ ] Status toasts dismissable via × and tap; auto-dismiss intact.
- [ ] ≤3 concurrent status toasts.
- [ ] Modal open locks body scroll; close (last modal) unlocks.

**Quality Gates:**
- [ ] `.status-toast` no longer `pointer-events:none`.
- [ ] No regression to `showToast`/`notifications.js` toasts.
- [ ] No console errors; poller cleanly start/stops.

**Integration:**
- [ ] Reuses `.scroll-lock` from P02 (no second lock class).

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Background pause:** Open the app, switch tabs for 30s, return — verify (Network panel) no requests fired while hidden.
  - Expected: silent while hidden; Actual: ___
- [ ] **Toast pile:** Trigger several status changes — at most 3 visible, each dismissable.
  - Expected: capped + dismissable; Actual: ___
- [ ] **Modal scroll:** Open a confirm modal on a long page, try scrolling — background fixed.
  - Expected: locked; Actual: ___

#### Automated Testing
```bash
# Playwright: visibility pause, toast cap/dismiss, modal scroll-lock
```

#### Performance Testing
- [ ] 0 network requests while backgrounded over 60s; Actual: ___

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` (files: `templates/base.html`, `static/js/modals.js`); 0 critical.
- [ ] **Code Quality:** Timers cleared; no leaked intervals; cap logic correct.
- [ ] **Error Handling:** `.catch()` on poll fetch preserved (silent network failures).
- [ ] **Security:** No change to endpoint/auth; CSRF shim untouched.
- [ ] **Documentation:** Comment the visibility-pause rationale.
- [ ] **Project Pattern Compliance:** Inline ES5 style matches file; `.scroll-lock` reused.

---

## Dependencies

### Upstream (Required Before Starting)
- P02 (`.scroll-lock`).

### Downstream (Will Use This Phase)
- None.

### External Services
- Existing `/api/appointments/status-events` (unchanged).

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Verification assertions pass
- [ ] Code review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `fix(toasts): pause poller in bg tabs, dismissable + capped toasts, modal scroll-lock (phase 03)`

---

## Notes

### Technical Considerations
- `pollStatusEvents` uses `lastPoll`/`since=`; a hidden gap is naturally caught up on the next call — no events lost.
- Keep delegation to `window.showToast` first; the fallback path is the hardened one.

### Known Limitations
- Replace-oldest can drop a status event from view if 4+ arrive in one poll; acceptable for transient notifications (the data still exists server-side).

### Future Enhancements
- Extract a generic `ToastManager` (cap + dismiss + stack offset) into `static/js/notifications.js` so all toast types share it.

---

**Previous:** [[phase-02-mobile-sidebar-a11y|Phase 02]]
**Next:** [[phase-04-mobile-header-title|Phase 04: Mobile header page-title]]
