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

### Active

- [ ] Zunifikowany system typografii (jeden :root w input.css, nie w każdym szablonie)
- [ ] Spójna skala max-width dla stron
- [ ] Eliminacja !important padding overrides
- [ ] Pełna dostępność (aria-label dla ikon, aria-live dla async content)
- [ ] Retry actions w stanach błędu (calendar, client list)
- [ ] Poprawka 404 CTA (routing do dashboard zamiast invoices_list)

### Out of Scope

- Aplikacja mobilna — web-first
- Real-time WebSocket — polling jest wystarczający
- Multi-tenant (wiele salonów) — single-tenant design

## Context

Aktualny stan UI audit: **17/24** (up from 15/24). Najsłabszy pillar: Typography 2/4.

Główne problemy techniczne:
- 45/52 szablonów ma własny blok `:root` z deklaracjami CSS — refaktor wymaga centralnego `input.css`
- ~80 pozostałych hardcoded hex kolorów (po refaktorze gałęzi hex-colors)
- 14+ szablonów używa `!important` żeby nadpisać padding z `base.html`
- Accessibility near-zero (tylko 4 atrybuty `aria-*` w całej aplikacji)
- Brak retry w stanach błędu async

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
*Last updated: 2026-03-19 after UI audit analysis, starting milestone v2.0*
