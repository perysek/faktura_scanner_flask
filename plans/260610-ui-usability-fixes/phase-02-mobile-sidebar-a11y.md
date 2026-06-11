---
title: "Phase 02: Mobile Sidebar A11y + Accordion Resize"
description: "Make the off-canvas mobile sidebar accessible — live aria-expanded, focus trap, body scroll-lock — and make the accordion resize-safe (Issue 3 + Suggestion 2)."
skill: "none"
status: done
group: "shared-behavior"
dependencies: [P01]
tags: [phase, accessibility, javascript, mobile]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 02: Mobile Sidebar A11y + Accordion Resize

**Context:** [[plan|Master Plan]] | **Dependencies:** P01 | **Status:** Pending

---

## Overview

The off-canvas mobile sidebar opens but lies to assistive tech: the hamburger button is hard-coded `aria-expanded="false"`, focus is never trapped inside the drawer (Tab escapes to hidden content behind the overlay), and the body keeps scrolling underneath. This phase fixes all three in the existing `openMobileSidebar`/`closeMobileSidebar` functions and adds a resize handler so the accordion's fixed `max-height` doesn't clip after a viewport/font reflow (Suggestion 2).

**Goal:** Opening the mobile drawer reports the correct ARIA state, traps focus, locks background scroll, and the accordion never clips when the viewport resizes.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** `templates/components/sidebar.html` inline `<script>` (`openMobileSidebar`/`closeMobileSidebar`, accordion `expand`) and the toggle button in `templates/base.html` (`#sidebar-toggle`, currently hard-coded `aria-expanded="false"`).
- **Server Layer:** None.
- **Database Layer:** None.
- **Integrations:** Uses a body scroll-lock utility shared with the modal lock in P03 (define once).

### User Workflow

**Trigger:** Mobile user taps the hamburger (`#sidebar-toggle`, visible `lg:hidden`).

**Steps:**
1. Drawer slides in; `#sidebar-toggle` flips to `aria-expanded="true"`; SR announces "expanded".
2. Focus moves into the drawer; Tab cycles **within** the drawer (first ↔ last focusable), never reaching content behind the overlay.
3. Background `body` does not scroll.
4. Esc or overlay-click closes: `aria-expanded="false"`, focus returns to the toggle, body scroll restored.

**Success Outcome:** Screen-reader and keyboard users get a correct, trapped, scroll-locked drawer matching what sighted users see.

### Problem Being Solved

**Pain Point:** Issue 3 — wrong/confusing menu state for AT users; keyboard users lose their place behind the backdrop; touch users scroll the page under the open drawer. Plus Suggestion 2 — accordion sections set `max-height` to a fixed `scrollHeight` px and can clip on reflow.

**Alternative Approach:** Without this, mobile nav is effectively broken for keyboard/SR users.

### Integration Points

**Upstream Dependencies:** P01 (foundation; the scroll-lock utility class is introduced here and reused by P03).

**Downstream Consumers:** P03 reuses the same body scroll-lock for modals.

**Data Flow:**
```
#sidebar-toggle click ─▶ openMobileSidebar()
   ├─ sidebar.classList show + aria-expanded=true
   ├─ body scroll-lock ON
   ├─ move focus into drawer + install keydown Tab-trap
   └─ Esc / overlay-click / resize≥lg ─▶ closeMobileSidebar() (reverse)
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Scroll-lock mechanism:** Use a dedicated CSS class `.scroll-lock { overflow: hidden; }` in `input.css` (safe against Tailwind purge) rather than toggling the Tailwind `overflow-hidden` utility?
   - **Context:** A JS-toggled `overflow-hidden` string in an inline `<script>` is technically JIT-detected, but a dedicated author class is collision-proof and shared with P03.
   - **Assumptions if unanswered:** Yes — add `.scroll-lock` to `input.css`.
   - **Impact:** Using the Tailwind utility risks a missing class if scan context changes.

2. **Focus trap scope:** Trap among all focusable elements inside `#sidebar` (links + logout)?
   - **Assumptions if unanswered:** Yes — query `a[href], button` inside `#sidebar`.

### Validation Checklist

- [ ] Scroll-lock approach confirmed (`.scroll-lock` class).
- [ ] P01 merged (so `input.css` is the active edit target and rebuild flow is known).
- [ ] Tested at <1024px (drawer only exists there).

> [!CAUTION]
> `closeMobileSidebar` already guards `window.innerWidth >= 1024`. Keep that guard so a desktop resize doesn't fight the `lg:flex` static sidebar.

---

## Requirements

### Functional

- `#sidebar-toggle` `aria-expanded` reflects real open/closed state.
- Focus moves into the drawer on open and is trapped (Tab/Shift+Tab cycle first↔last).
- `body` scroll is locked while the drawer is open and restored on close.
- Focus returns to `#sidebar-toggle` on close.
- Accordion expanded section recomputes `max-height` on `resize` (no clipping).

### Technical

- Edits in `templates/components/sidebar.html` (inline script) + `templates/base.html` (toggle button is fine as-is; JS updates its attribute) + `static/css/input.css` (`.scroll-lock`).
- Preserve existing Esc-to-close and overlay-click-to-close.
- Respect `prefers-reduced-motion` (no new animation added).

---

## Decision Log

### Dedicated `.scroll-lock` utility (ADR-02-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Both the sidebar (here) and modals (P03) need to lock body scroll.

**Decision:** Add `.scroll-lock { overflow: hidden; }` to `input.css @layer utilities`; toggle it via `document.body.classList`. Shared by P03.

**Consequences:** One source of truth, purge-proof. Rebuild required (P01 flow).

### In-place focus trap, no library (ADR-02-02)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** No JS deps beyond Tailwind; adding a focus-trap library is overkill.

**Decision:** Hand-roll a `keydown` Tab handler that cycles first/last focusable inside `#sidebar`, installed on open, removed on close.

**Consequences:** ~20 lines; no new dependency.

---

## Implementation Steps

### Step 0: Define Verification (do first)

- [ ] Playwright/`/browse` at 390px: open drawer → assert `#sidebar-toggle[aria-expanded="true"]`; assert `document.body` has `scroll-lock` (overflow hidden); Tab repeatedly and assert `document.activeElement` stays within `#sidebar`; Esc → assert `aria-expanded="false"` and `activeElement === #sidebar-toggle`.
- [ ] Manual: open drawer, try to scroll background — must not move.
- [ ] Manual: expand an accordion section, resize the window narrower/taller — expanded items must not clip.
- [ ] Confirm assertions FAIL before the fix.

### Step 1: Add the shared scroll-lock utility

- [ ] In `static/css/input.css` `@layer utilities`, add:
```css
/* Body scroll-lock behind overlays (sidebar drawer P02, modals P03) */
.scroll-lock { overflow: hidden; }
```
- [ ] `npm run build:css`.

### Step 2: Make open/close ARIA + scroll-lock + focus-trap aware

Edit the inline script in `templates/components/sidebar.html` (`openMobileSidebar`/`closeMobileSidebar`, lines ~283–303).

#### 2.1: Track focusable + trap handler

- [ ] Add, near the toggle wiring:
```js
function getFocusable() {
    return Array.prototype.slice.call(
        sidebar.querySelectorAll('a[href], button:not([disabled])')
    ).filter(function (el) { return el.offsetParent !== null; });
}

function trapTab(e) {
    if (e.key !== 'Tab') return;
    var f = getFocusable();
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
    }
}
```

#### 2.2: Update `openMobileSidebar`

- [ ] Add inside `openMobileSidebar` (after it un-hides the sidebar):
```js
if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'true');
document.body.classList.add('scroll-lock');
document.addEventListener('keydown', trapTab);
var firstLink = sidebar.querySelector('a[href]');
if (firstLink) firstLink.focus();
```
(Replace the existing focus-first-link block; do not duplicate it.)

#### 2.3: Update `closeMobileSidebar`

- [ ] Add inside `closeMobileSidebar` (keep the `innerWidth >= 1024` early-return guard):
```js
if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
document.body.classList.remove('scroll-lock');
document.removeEventListener('keydown', trapTab);
```
(The existing `toggleBtn.focus()` already returns focus — keep it.)

### Step 3: Accordion resize-safety (Suggestion 2)

- [ ] In the same script, after the accordion init, add a debounced resize handler that recomputes `max-height` for the currently-expanded section(s):
```js
var resizeTimer;
window.addEventListener('resize', function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
        sections.forEach(function (section) {
            var items = getItems(section);
            if (items && items.style.maxHeight && items.style.maxHeight !== '0px') {
                items.style.maxHeight = items.scrollHeight + 'px';
            }
        });
    }, 120);
});
```

### Step 4: Rebuild + verify

- [ ] `npm run build:css` (for `.scroll-lock`).
- [ ] Run Step-0 assertions — all must PASS.

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] `#sidebar-toggle aria-expanded` toggles `true`/`false` with drawer state.
- [ ] Tab/Shift+Tab cycle stays inside `#sidebar` while open.
- [ ] `body` cannot scroll while drawer open; scroll restored on close.
- [ ] Focus returns to toggle on close.

**Quality Gates:**
- [ ] Accordion expanded section does not clip after resize.
- [ ] Esc + overlay-click still close (no regression).
- [ ] axe: 0 new violations on a page with the drawer open.

**Integration:**
- [ ] `.scroll-lock` present in `output.css` and consumed by P03 later.

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Keyboard-only:** Open drawer via Enter on toggle, Tab through, confirm trap, Esc to close, focus on toggle.
  - Expected: trapped + returned; Actual: ___
- [ ] **Background scroll:** Drawer open, attempt scroll — page fixed.
  - Expected: no scroll; Actual: ___

#### Automated Testing
```bash
npm run build:css
# Playwright: aria-expanded toggling, focus containment, body.scroll-lock present
```

#### Performance Testing
- [ ] Resize handler debounced (no thrash); Actual: ___

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` (files: `templates/components/sidebar.html`, `templates/base.html`, `static/css/input.css`, `static/css/output.css`); 0 critical.
- [ ] **Code Quality:** No global leaks; listeners removed on close.
- [ ] **Error Handling:** Null-guards on `sidebar`/`overlay`/`toggleBtn` preserved.
- [ ] **Security:** N/A.
- [ ] **Documentation:** Inline comment explaining the trap.
- [ ] **Project Pattern Compliance:** ES5-style inline script matches existing file; `.scroll-lock` token-built.

---

## Dependencies

### Upstream (Required Before Starting)
- P01 (rebuild flow + `input.css` ownership).

### Downstream (Will Use This Phase)
- P03 reuses `.scroll-lock`.

### External Services
- None.

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Verification assertions pass
- [ ] Code review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `fix(sidebar): accessible mobile drawer — aria, focus-trap, scroll-lock (phase 02)`

---

## Notes

### Technical Considerations
- The static desktop sidebar (`lg:flex`) shares `#sidebar`; the `innerWidth >= 1024` guard in `closeMobileSidebar` prevents the trap/lock from affecting desktop. Do not remove it.
- `getFocusable` filters `offsetParent !== null` to skip hidden links (e.g. permission-gated nav items not rendered).

### Known Limitations
- Focus trap assumes the drawer's focusable order is DOM order (it is). If a future sticky "close" button is added, include it in the query.

### Future Enhancements
- A reusable `trapFocus(container)` helper could be extracted to `static/js/utils.js` and shared with modals (P03/Suggestion 1).

---

**Previous:** [[phase-01-design-tokens-foundation|Phase 01]]
**Next:** [[phase-03-status-toast-scroll-lock|Phase 03: Status-toast poller + overlay scroll-lock]]
