# MyWay Nails & Beauty — Aplikacja Salonowa

## What This Is

Kompleksowa aplikacja webowa dla salonu kosmetycznego (MyWay Nails & Beauty). Obsługuje skanowanie faktur przez OCR, zarządzanie klientami, pracownikami, usługami, rezerwacjami i raportowanie dochodów. Dostęp oparty na rolach (superuser, admin, accountant, receptionist, stylist). Codebase obejmuje soft delete, custom exceptions, transactional integrity i connection pooling. Stack: Flask 3.0, PostgreSQL, Tailwind CSS, Jinja2.

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
- ✓ Soft delete for invoices, clients, appointments, services — v3.0
- ✓ Custom exception hierarchy (AppointmentConflictError, DatabaseConnectionError) — v3.0
- ✓ AppointmentStatus enum + PostgreSQL CHECK constraint — v3.0
- ✓ SELECT * replaced with explicit column lists in critical repos — v3.0
- ✓ EmailService specific IMAP exception handling — v3.0
- ✓ SECRET_KEY startup validation + environment-based DEBUG logging — v3.0
- ✓ Database indexes on filtered columns + analytics optimization — v3.0
- ✓ ThreadedConnectionPool with configurable health checks — v3.0
- ✓ managed_transaction() for atomic multi-step operations — v3.0
- ✓ Dependency audit — 6 packages updated — v3.0

### Active

(No active requirements — next milestone not yet planned)

### Out of Scope

- Aplikacja mobilna — web-first
- Real-time WebSocket — polling jest wystarczający
- Multi-tenant (wiele salonów) — single-tenant design
- SQLAlchemy ORM migration — psycopg2 improvements sufficient for now
- Async PDF/OCR processing (Celery) — not blocking current usage
- Dark mode — no user demand

## Context

v3.0 Functional-Improvements milestone completed (2026-04-09). Addressed codebase concerns from audit: soft deletes, exception hierarchy, database indexes, connection pooling, transactional integrity, security hardening. 15/17 requirements implemented (FIX-01/FIX-02 audit DELETE logging deferred).

Stack: Python 3.11, Flask 3.1.3, PostgreSQL, Tailwind CSS 3.4, Jinja2, Alembic 1.18.4, Docker.

## Constraints

- **Tech stack**: Flask + Jinja2 + Tailwind — nie dodajemy React/Vue
- **Backwards compatibility**: zmiany CSS muszą być wizualnie neutralne lub lepsze
- **Brak bundlera JS**: vanilla JS, żadnych npm build steps dla logiki (tylko Tailwind CSS build)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CSS custom properties zamiast Tailwind do kolorów statusów | Status colors są semantyczne | ✓ Good |
| base.html p-0 zamiast p-2 | Root cause fix for !important fights | ✓ Good |
| Soft delete inline in repos, not BaseRepository refactor | Pragmatic — fewer entities, simpler | ✓ Good |
| ServiceRepository.delete() does real soft-delete (is_deleted) not deactivation (is_active) | Consistent semantics across entities | ✓ Good |
| Log type(e).__name__ not str(e) in connect() | IMAP errors can echo credentials | ✓ Good |
| RuntimeError for SECRET_KEY guard, not ValueError | Startup misconfiguration is runtime problem | ✓ Good |
| ThreadedConnectionPool with SELECT 1 health check | Dead connections discarded before use | ✓ Good |
| safe_commit() + managed_transaction() pattern | Ambient transaction — repos don't need to know about tx scope | ✓ Good |
| bcrypt major update deferred | Breaking API changes, needs separate investigation | — Pending |

---
*Last updated: 2026-04-09 after v3.0 Functional-Improvements milestone*
