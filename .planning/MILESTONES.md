# Milestones: MyWay Nails & Beauty

### v3.0 — Functional-Improvements

**Shipped:** 2026-04-09
**Phases:** 5–9 (15 plans)
**Timeline:** 2026-03-31 → 2026-04-09 (10 days)
**Commits:** 66 | **Files changed:** 104 | **LOC:** +14,793 / -1,120

**What shipped:**
- Soft delete for invoices, clients, appointments, services — undo toast, restore endpoints, already-deleted detection
- Custom exception hierarchy — AppointmentConflictError, DatabaseConnectionError, specific catches replacing 140+ bare except blocks
- AppointmentStatus Python enum + PostgreSQL CHECK constraint replacing hardcoded strings
- SECRET_KEY startup guard + environment-based DEBUG logging control
- Database indexes on filtered columns, analytics query optimization, employee schedule JOIN batching
- ThreadedConnectionPool with configurable size/timeout/health-check, request-scoped connections
- managed_transaction() for atomic multi-step operations with safe_commit() suppression pattern
- Dependency audit — 6 packages updated, pip check clean

**Known gaps:**
- FIX-01, FIX-02: Audit DELETE logging — soft delete resolves FK conflict but audit log entries not verified end-to-end

**Deferred:**
- SPAC-02: max-width normalization (carried from v2.0)

---

## Completed Milestones

### v1.0 — Core Application

**Shipped:** Pre-2026
**Phases:** Pre-GSD (not tracked)

**What shipped:**
- OCR invoice scanning (PyMuPDF + Tesseract)
- Client management (CRUD, visit history)
- Employee and service management
- Appointments with day/week/month views
- Income dashboard and analytics
- Authentication + RBAC (5 roles)
- Design system (CSS custom properties)

### v2.0 — UI/UX Polish

**Shipped:** 2026-03-24
**Phases:** 1–4 (10 plans)
**Last phase:** Phase 4

**What shipped:**
- CSS architecture: unified typography in input.css (45 template dedup)
- Layout & spacing: base.html p-0 fix, !important elimination (13 templates)
- Color cleanup: hardcoded hex → CSS tokens/Tailwind brand-* (19+ files)
- Accessibility: aria-labels, aria-live, skip-nav, retry buttons
- UX fixes: 404 CTA routing, diacritic fix, copy improvements

**Deferred:**
- SPAC-02: max-width normalization (900px forms, 1400px lists, full-width calendars)

**Metrics:**
- UI audit score: 17/24 → improved across Typography, Spacing, Color, Accessibility pillars

---
*Last updated: 2026-03-31 after v2.0 completion*
