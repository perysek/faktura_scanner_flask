# MyWay Nails & Beauty — Aplikacja Salonowa

## What This Is

Kompleksowa aplikacja webowa dla salonu kosmetycznego (MyWay Nails & Beauty). Obsługuje skanowanie faktur przez OCR, zarządzanie klientami, pracownikami, usługami, rezerwacjami i raportowanie dochodów. Dostęp oparty na rolach (superuser, admin, accountant, receptionist, stylist). Stack: Flask 3.0, PostgreSQL, Tailwind CSS, Jinja2.

## Core Value

Recepcjonistka i stylistka muszą sprawnie zarządzać rezerwacjami i klientami — to jest krwiobieg salonu.

## Requirements

### Validated

- ✓ Skanowanie faktur PDF przez OCR (PyMuPDF + Tesseract) — v1.0
- ✓ Zarządzanie klientami (CRUD, historia wizyt) — v1.0
- ✓ Zarządzanie pracownikami i usługami — v1.0
- ✓ Rezerwacje z widokiem dziennym/tygodniowym/miesięcznym — v1.0
- ✓ Panel dochodów i analityki — v1.0
- ✓ Autentykacja + RBAC (5 ról) — v1.0
- ✓ Spójny design system (CSS custom properties) — v1.0
- ✓ CSS architecture: unified typography in input.css — v2.0
- ✓ Layout & spacing: !important elimination, base.html p-0 — v2.0
- ✓ Color cleanup: hardcoded hex → CSS tokens/brand-* — v2.0
- ✓ Accessibility: aria-labels, aria-live, skip-nav, retry buttons — v2.0

## Current Milestone: v3.0 Functional-Improvements

**Goal:** Fix known bugs, implement missing critical features, optimize performance, and harden the codebase based on concerns audit findings.

**Target features:**
- Bug fixes (audit logging, exception handling)
- Missing critical features (soft deletes, transactional integrity)
- Performance optimization (database indexes, query optimization)
- Security hardening (secret key validation, explicit column selection)
- Code robustness (custom exceptions, status enums, connection management)

### Active

(Defined in REQUIREMENTS.md — v3.0 requirements)

### Out of Scope

- Aplikacja mobilna — web-first
- Real-time WebSocket — polling jest wystarczający
- Multi-tenant (wiele salonów) — single-tenant design

## Context

v2.0 UI/UX Polish milestone completed (2026-03-24). UI audit improved from 17/24.

Current concerns (see `.planning/codebase/CONCERNS.md`):
- Audit logging FK constraint blocks DELETE tracking
- Broad exception handling masks real errors across routes/services
- Missing database indexes on frequently filtered columns
- PDF/OCR processing untested and single-threaded
- No soft delete — hard deletes lose data permanently
- No transactional integrity for multi-step operations (appointments)

Stack: Python 3.11, Flask 3.0, PostgreSQL, Tailwind CSS 3.4, Jinja2, Alembic, Docker.

## Constraints

- **Tech stack**: Flask + Jinja2 + Tailwind — nie dodajemy React/Vue
- **Backwards compatibility**: zmiany CSS muszą być wizualnie neutralne lub lepsze
- **Brak bundlera JS**: vanilla JS, żadnych npm build steps dla logiki (tylko Tailwind CSS build)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CSS custom properties zamiast Tailwind do kolorów statusów | Status colors są semantyczne, Tailwind classes są zbyt utility-focused | ✓ Good |
| Osobna gałąź do refaktoru hex kolorów | Izolacja zmiany, łatwy review | ✓ Good |
| `--color-ink-muted` = #525252 zamiast #333 | Spójność z design system | ✓ Good |

---
*Last updated: 2026-03-31 after v2.0 completion, starting milestone v3.0 Functional-Improvements*
