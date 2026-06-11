---
title: "Phase 10: Accessible Read-Only Star Rating"
description: "Give the already-rated star display an accessible value on appointment_rate.html and add radiogroup/arrow-key semantics to the interactive stars (Issue 10)."
skill: "none"
status: pending
group: "public-a11y"
dependencies: []
tags: [phase, accessibility, public]
created: 2026-06-10
updated: 2026-06-10
---

# Phase 10: Accessible Read-Only Star Rating

**Context:** [[plan|Master Plan]] | **Dependencies:** None | **Status:** Pending

---

## Overview

`templates/public/appointment_rate.html` is a standalone public page (no `base.html`, its own inline `<style>`, does not load `output.css`). When a visit is already rated, it renders five `<span class="star">★</span>` elements distinguished only by active/inactive color — a screen reader reads "star star star star star" with no score (Issue 10). The interactive stars are buttons with `aria-label` (good) but lack radio-group semantics / arrow-key support. This phase makes the read-only display expose its value (`role="img"` + `aria-label`) and upgrades the interactive stars to a keyboard-operable `radiogroup`.

**Goal:** Both the read-only and interactive ratings are fully understandable and operable by assistive tech.

---

## Context & Workflow

### How This Phase Fits Into the Project

- **UI Layer:** `templates/public/appointment_rate.html` — read-only block (lines ~93–99) + interactive stars block (lines ~136–184) + its inline `<style>`.
- **Server Layer:** None — the `/rate/{token}` POST is unchanged.
- **Database Layer:** None.

### User Workflow

**Trigger:** A customer opens the SMS rating link; either already rated (read-only) or rating now (interactive).

**Steps:**
1. **Read-only:** SR announces "Twoja ocena: 4 z 5 gwiazdek" instead of five undifferentiated stars.
2. **Interactive:** Stars form a radio group; arrow keys move selection; Enter/Space selects; SR announces the chosen score.

**Success Outcome:** Blind/low-vision customers can read their submitted score and submit a new one by keyboard.

### Problem Being Solved

**Pain Point:** Issue 10 — read-only stars have no accessible value; interactive stars lack radiogroup semantics.

**Alternative Approach:** Without this, SR users can't tell what they rated or easily rate by keyboard.

### Integration Points

**Upstream Dependencies:** None (standalone page).

**Downstream Consumers:** None.

**Data Flow:**
```
already_rated + current_score ─▶ role="img" aria-label="Twoja ocena: X z 5"
interactive ─▶ role="radiogroup"; each star role="radio" aria-checked; arrow-key handler
```

---

## Prerequisites & Clarifications

### Questions for User

1. **Read-only exposure:** Use `role="img"` + `aria-label="Twoja ocena: {{ current_score }} z 5"` on the stars row (simplest, one announcement) vs. a visually-hidden sentence?
   - **Assumptions if unanswered:** `role="img"` + `aria-label` (one clean announcement; no extra DOM).
   - **Impact:** Visually-hidden text needs a local `.sr-only` style (page doesn't load `output.css`).

2. **Interactive radiogroup depth:** Full `radiogroup` + `role="radio"` + `aria-checked` + Left/Right arrow navigation + roving `tabindex`?
   - **Assumptions if unanswered:** Yes — full pattern (it's the accessible standard for a rating).
   - **Impact:** Partial (just labels) leaves keyboard navigation clunky.

### Validation Checklist

- [ ] Read-only approach confirmed (`role="img"`).
- [ ] Interactive radiogroup depth confirmed.
- [ ] Polish wording confirmed ("Twoja ocena: X z 5").

> [!CAUTION]
> This page is standalone and has NO access to global `.sr-only`/tokens. Any visually-hidden helper or color must be defined in this file's `<style>`.

---

## Requirements

### Functional

- Read-only stars expose the numeric score to SR (e.g. "Twoja ocena: 4 z 5").
- Interactive stars are a `radiogroup`; each star is a `radio` with `aria-checked`; Left/Right (and Up/Down) arrows move selection; Enter/Space/click selects; selection updates the hidden `score` input.
- Existing visual behavior (fill on select, submit reveal, skip) preserved.

### Technical

- Edits confined to `templates/public/appointment_rate.html`.
- Add any visually-hidden style locally if used.
- Keep the existing IIFE; extend it for keyboard + ARIA state.

---

## Decision Log

### role="img" for read-only (ADR-10-01)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Five identical stars announce nothing.

**Decision:** Put `role="img"` + `aria-label="Twoja ocena: {{ current_score }} z 5"` on the `.stars-row.stars-readonly`; mark the individual `★` `aria-hidden`.

**Consequences:** One concise announcement; minimal markup.

### Full radiogroup for interactive (ADR-10-02)

**Date:** 2026-06-10
**Status:** Accepted

**Context:** Buttons-with-labels work but aren't an idiomatic rating control.

**Decision:** `role="radiogroup"` on `#stars`; each star `role="radio"`, `aria-checked`, roving `tabindex`; arrow-key handler.

**Consequences:** Keyboard-idiomatic; SR announces "wybrane/Ocena X z 5".

---

## Implementation Steps

### Step 0: Define Verification (do first)

- [ ] `/browse` a11y tree on an already-rated URL: assert the stars row exposes name "Twoja ocena: N z 5".
- [ ] On a not-yet-rated URL: assert `#stars` is `role="radiogroup"`; arrow keys move `aria-checked`; Enter selects; the hidden `#score-input` updates.
- [ ] Confirm assertions FAIL before the change.

### Step 1: Read-only accessible value

- [ ] Update the read-only block:
```html
{% if current_score %}
<div class="stars-row stars-readonly" style="margin-top:1.25rem;"
     role="img" aria-label="Twoja ocena: {{ current_score }} z 5 gwiazdek">
    {% for i in range(1, 6) %}
    <span class="star {% if i <= current_score %}active{% endif %}" aria-hidden="true">★</span>
    {% endfor %}
</div>
{% endif %}
```

### Step 2: Interactive radiogroup + keyboard

- [ ] Update the interactive stars markup:
```html
<div class="stars-row" id="stars" role="radiogroup" aria-label="Oceń wizytę od 1 do 5 gwiazdek">
    {% for i in range(1, 6) %}
    <button class="star" data-score="{{ i }}" type="button"
            role="radio" aria-checked="false" aria-label="Ocena {{ i }} z 5"
            tabindex="{{ '0' if i == 1 else '-1' }}">★</button>
    {% endfor %}
</div>
```
- [ ] Extend the IIFE: on select (click or key), set `aria-checked` on the chosen star (others false), move roving `tabindex` (selected = 0, rest = -1), fill stars, update `#score-input`, reveal submit. Add a `keydown` handler on `#stars`:
```js
stars.forEach(function (star, idx) {
    star.addEventListener('keydown', function (e) {
        var next = null;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = stars[Math.min(idx + 1, stars.length - 1)];
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = stars[Math.max(idx - 1, 0)];
        if (next) { e.preventDefault(); next.focus(); select(parseInt(next.dataset.score, 10)); }
    });
});
```
where `select(score)` centralizes the existing click logic + ARIA/tabindex updates.

### Step 3: Verify

- [ ] Run Step-0 assertions — all PASS.
- [ ] Manual: NVDA/VoiceOver (or `/browse` a11y tree) announces score read-only + selection interactive.

---

## Verifiable Acceptance Criteria

**Critical Path:**
- [ ] Read-only stars announce "Twoja ocena: X z 5".
- [ ] Interactive stars are a keyboard-operable radiogroup; selection updates `#score-input`.
- [ ] Submit/skip flow unchanged.

**Quality Gates:**
- [ ] axe 0 critical/serious on the page (both states).
- [ ] Mobile tap targets preserved (stars already large).

**Integration:**
- [ ] POST `/rate/{token}` still receives the selected score.

---

## Quality Assurance

### Test Plan

#### Manual Testing
- [ ] **Read-only SR:** Open an already-rated link with a screen reader → hears the score.
  - Expected: "Twoja ocena: N z 5"; Actual: ___
- [ ] **Keyboard rate:** Tab to stars, arrow to 4, Enter → submit appears, score=4.
  - Expected: works; Actual: ___

#### Automated Testing
```bash
# /browse: a11y tree assertions for both states
```

### Review Checklist

- [ ] **Code Review Gate:** `/code-review` (file: `templates/public/appointment_rate.html`); 0 critical.
- [ ] **Code Quality:** `select()` centralizes logic; no duplication.
- [ ] **Security:** `current_score` is an int from the server; rendered in an attribute safely.
- [ ] **Documentation:** N/A (standalone page).
- [ ] **Project Pattern Compliance:** Standalone page conventions kept (no base.html dependency added).

---

## Dependencies

### Upstream (Required Before Starting)
- None.

### Downstream (Will Use This Phase)
- None.

### External Services
- Existing `/rate/{token}` POST (unchanged).

---

## Completion Gate

### Sign-off
- [ ] All acceptance criteria met
- [ ] Verification passes
- [ ] Code review passed
- [ ] Phase marked DONE in plan.md
- [ ] Committed: `fix(rating): accessible read-only value + radiogroup stars (phase 10)`

---

## Notes

### Technical Considerations
- The page does not load `output.css`; do not reference global tokens/`.sr-only` — keep everything inline/local.
- Keep `aria-hidden="true"` on the decorative `★` glyphs so the group label is the single announcement.

### Known Limitations
- Visual star fill on keyboard hover-equivalent (focus) is optional; selection fill is the key state.

### Future Enhancements
- Reuse this radiogroup pattern if star ratings appear elsewhere (e.g. an internal review surface).

---

**Previous:** [[phase-09-clients-mobile-cards|Phase 09]]
**Next:** [[phase-11-verification-docs|Phase 11: App-wide a11y/responsive verification + docs]]
