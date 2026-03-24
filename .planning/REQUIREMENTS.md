# Requirements: MyWay Nails & Beauty — UI/UX Polish Milestone

**Defined:** 2026-03-19
**Core Value:** Recepcjonistka i stylistka muszą sprawnie zarządzać rezerwacjami i klientami
**Source:** UI audit 17/24 (2026-03-18) — `.planning/UI-REVIEW.md`

## v2.0 Requirements

Requirements dla milestonu UI/UX Polish. Każdy ma źródło w UI audicie.

### Typography (Pillar 4 — 2/4)

- [x] **TYPO-01**: Wspólny blok `:root` z deklaracjami CSS klas typograficznych (`.page-title`, `.page-subtitle`, `.stat-value`, `.stat-label`) przeniesiony do `static/css/input.css` — eliminuje 45 duplikatów
- [x] **TYPO-02**: Spójna skala `.page-title` — jeden rozmiar (1.75rem) na wszystkich stronach, w tym widokach kalendarza (teraz 1.375rem)
- [x] **TYPO-03**: Ujednolicona skala `.stat-value` — jeden rozmiar zamiast 1.25rem/1.5rem/1.75rem na różnych stronach

### Spacing (Pillar 5 — 3/4)

- [x] **SPAC-01**: Usunięcie `!important` padding override z 14+ szablonów — `base.html` musi domyślnie ustawiać padding 0, strony definiują swój własny
- [ ] **SPAC-02**: Spójna skala `max-width` dla typów stron (formularze: 900px, listy: 1400px, kalendarze: full-width)

### Color (Pillar 3 — 3/4)

- [x] **COL-01**: Eliminacja pozostałych ~80 hardcoded hex wartości z szablonów (auth, form, error templates)
- [x] **COL-02**: `brand-*` Tailwind tokeny używane w szablonach zamiast `--color-accent` i `#c9a227` inline

### Accessibility (Pillar 6 — 3/4)

- [x] **A11Y-01**: `aria-label` na wszystkich icon-only buttons (calendar navigation, modal close, flash dismiss)
- [x] **A11Y-02**: `aria-live` regions dla async content updates (appointment list, client list, stat cards)
- [x] **A11Y-03**: Skip-navigation link w `base.html`

### Experience Design (Pillar 6 — 3/4)

- [ ] **UX-01**: Retry action w stanach błędu async (calendar day view, client list, appointment list)
- [x] **UX-02**: 404 CTA routing do `main.dashboard` zamiast `main.invoices_list`
- [x] **UX-03**: Poprawka pozostałego brakującego znaku diakrytycznego (`sellers/edit.html` line 445: "Ladowanie..." → "Ładowanie...")

### Copywriting (Pillar 1 — 3/4)

- [x] **COPY-01**: "Idź na początek" → "Powrót na górę" w `analytics/dashboard.html`

## v3.0 Requirements

Odroczone — do następnego milestonu.

### Accessibility (zaawansowane)

- **A11Y-04**: Focus management w modal dialogs (trap focus w otwartym modalu)
- **A11Y-05**: Screen reader test — pełne przejście przez kluczowe flows

### Color System

- **COL-03**: Zapis superadmin "Power Panel" do osobnego CSS — dokumentacja że to celowa rozbieżność

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dark mode | Duży nakład pracy, brak wymagania użytkownika |
| Animacje przejść między stronami | Flask SSR — wymaga JS router |
| Redesign layoutu | Design jest spójny, tylko sprzątanie |
| Responsive/mobile layout | Web-first, desktop primary |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TYPO-01 | Phase 1 | Complete |
| TYPO-02 | Phase 1 | Complete |
| TYPO-03 | Phase 1 | Complete |
| SPAC-01 | Phase 2 | Complete |
| SPAC-02 | Phase 2 | Pending |
| COL-01 | Phase 3 | Complete |
| COL-02 | Phase 3 | Complete |
| A11Y-01 | Phase 4 | Complete |
| A11Y-02 | Phase 4 | Complete |
| A11Y-03 | Phase 4 | Complete |
| UX-01 | Phase 4 | Pending |
| UX-02 | Phase 4 | Complete |
| UX-03 | Phase 4 | Complete |
| COPY-01 | Phase 4 | Complete |

**Coverage:**
- v2.0 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-19*
*Source: UI audit `.planning/UI-REVIEW.md` (scored 17/24)*
