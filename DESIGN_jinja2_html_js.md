# DESIGN.md — System projektowy aplikacji (stan faktyczny)

> **Status:** ten dokument opisuje **rzeczywisty, aktualny stan** systemu projektowego —
> zweryfikowany bezpośrednio w `static/css/input.css`, `templates/`, `static/js/` i
> `.github/workflows/ci.yml` (audyt: 2026-08-14), nie na podstawie starszych notatek.
> **Źródło prawdy dla tokenów:** `static/css/input.css :root` (edytuj tam, uruchom
> `npm run build:css`, **nigdy** nie edytuj ręcznie `output.css` — jest generowany i
> nadpisywany przy każdym buildzie/deployu).
>
> **Relacja do innych dokumentów w repo** — w projekcie jest kilka starszych plików
> (`GUI-GOLDEN-BOOK.md`, `GUI-COMPONENTS-GOLDEN-BOOK.md`, `STYLESEED.md`,
> `plans/260610-ui-usability-fixes/DESIGN-TOKENS.md`). Zawierają wartościowy opis
> zachowań JS (Modals/Notifications/SearchableSelect) i strukturę komponentów, ale
> **`GUI-GOLDEN-BOOK.md` jest w części nieaktualny** — opisuje m.in. Material Icons
> jako aktywny system ikon, gradientowe przyciski `rounded-xl`/`rounded-2xl` jako
> "System B" oraz `table-utils.js`. Żadne z tych trzech nie istnieje już w kodzie
> (patrz [§12 Rozbieżności](#12-rozbieżności-wobec-starszych-dokumentów-w-repo)).
> Ten plik jest odtąd punktem odniesienia dla pytań "jak to jest *teraz*".

---

## Spis treści

1. [Stack i filozofia](#1-stack-i-filozofia)
2. [Tokeny projektowe](#2-tokeny-projektowe)
3. [System motywów (jasny/niebieski/zielony/grafitowy)](#3-system-motywów)
4. [Typografia](#4-typografia)
5. [Komponenty — przyciski, formularze, karty](#5-komponenty--przyciski-formularze-karty)
6. [Tabele — sortowanie i widok mobilny (stack-cards)](#6-tabele)
7. [Modale, powiadomienia, toasty](#7-modale-powiadomienia-toasty)
8. [System ikon (inline SVG)](#8-system-ikon)
9. [Sidebar i nawigacja](#9-sidebar-i-nawigacja)
10. [Ruch, przejścia stron (View Transitions)](#10-ruch-i-przejścia-stron)
11. [Dostępność (a11y) i mobile](#11-dostępność-i-mobile)
12. [Rozbieżności wobec starszych dokumentów w repo](#12-rozbieżności-wobec-starszych-dokumentów-w-repo)
13. [Build, CI guard, mapa plików](#13-build-ci-guard-mapa-plików)

---

## 1. Stack i filozofia

| Warstwa | Technologia |
|---|---|
| CSS | Tailwind CSS 3 (CLI), `static/css/input.css` → `static/css/output.css` (minified, gitignored) |
| Font | **Inter** (jedyny font, `--font-display` = `--font-body`) |
| Ikony | **Wyłącznie inline SVG** — brak fontu ikon (usunięty w całości) |
| Szablony | Jinja2, dziedziczenie z `templates/base.html` |
| JS | Vanilla ES6, moduły ładowane globalnie przez `base.html`, bez frameworka/bundlera |

**Nazwa i status systemu:** w starszej dokumentacji funkcjonuje jako *"System B / refined"*
(ADR-G-01). Od migracji Faz 01–11 (2026-06-11) i domknięcia planu
`260613-deferred-design-tickets` (2026-06-14) jest to **jedyny** język wizualny
uwierzytelnionej aplikacji — nie ma już wyboru "System A vs System B".

**Charakterystyka:** płaskie wypełnienia (brak gradientów), promienie 2–3px, kolory
wyłącznie przez zmienne CSS, `Inter` jako jedyny font, glify tekstowe/SVG zamiast
fontu ikon. Złoty akcent (`--color-accent`, `#c9a227`) jest **wyłącznie dekoracyjny**
(logo, hover na sidebarze) — nigdy jako kolor głównej akcji. Funkcjonalny akcent
(focus ring, linki) to `--color-focus-ring` (`#2563eb`, niebieski).

**Zakazane wzorce w uwierzytelnionych szablonach** (egzekwowane przez CI, patrz §13):
`rounded-xl`, `rounded-2xl`, `bg-gradient-to-*` / `from-primary-*` / `to-primary-*`,
surowe klasy `slate-*` na przyciskach, font Material Icons.

`★ Insight ─────────────────────────────────────`
Ciekawa decyzja architektoniczna: token-owe klasy komponentowe (`.refined-btn-primary`
itd.) żyją w `input.css @layer components`, ale strony wciąż mają dużo lokalnych,
**nie-warstwowanych** bloków `<style>`. W kaskadzie CSS `@layer` ma zawsze niższy
priorytet niż zwykłe (nie-warstwowane) reguły, niezależnie od specyficzności selektora
— więc lokalny `<style>` strony *zawsze* wygrywa z klasą globalną o tej samej
specyficzności. To celowe: migrację strony na globalny komponent robi się bezpiecznie
("usuń lokalną kopię, spadnij na globalną"), ale zostawia pułapkę — reguła `!important`
w globalnych regułach mobilnych (np. wymuszenie 16px na inputach) jest *konieczna*,
bo inaczej przegrałaby z jakimkolwiek lokalnym stylem strony.
`─────────────────────────────────────────────────`

---

## 2. Tokeny projektowe

Wszystkie w `input.css`, blok `@layer base { :root { ... } }`. Motyw jasny (bez
`data-theme`) jest wartością domyślną — pozostałe motywy nadpisują te same nazwy
zmiennych pod `[data-theme="…"]` (§3).

### Tekst (hierarchia 3-poziomowa)
| Token | Wartość | Zastosowanie |
|---|---|---|
| `--color-ink` | `#1a1a1a` | Tekst główny; kanoniczne wypełnienie płaskiego primary-buttona |
| `--color-ink-muted` | `#525252` | Tekst drugorzędny; kolor hover primary-buttona |
| `--color-ink-subtle` | `#6b6b6b` | Tekst pomocniczy, placeholdery, etykiety th (WCAG AA ≥4.5:1) |

### Powierzchnie
| Token | Wartość | Zastosowanie |
|---|---|---|
| `--color-surface` | `#fafafa` | Hover wiersza, subtelne panele |
| `--color-surface-warm` | `#f7f6f3` | Tło strony |
| `--color-surface-elevated` | `#ffffff` | Karty, inputy, modale (zamiast twardego `white`) |

### Obramowania
| Token | Wartość |
|---|---|
| `--color-border` | `#e8e6e1` |
| `--color-border-subtle` | `#f0eeea` |

### Promienie
| Token | Wartość | Zastosowanie |
|---|---|---|
| `--radius-sm` | `2px` | Inputy, przyciski, badge'e |
| `--radius-md` | `3px` | Karty, modale |

Wszędzie przez `var()` — literały `2px`/`3px` istnieją tylko w definicjach samych
tokenów.

### Marka / akcent
`--color-accent` (`#c9a227`, dekoracyjny złoty), `--color-accent-muted`
(`rgba(201,162,39,.12)`), `--color-accent-deep` (`#a07d1a`, drugi stop gradientu
avatara w sidebarze), `--color-on-accent`/`--color-on-ink` (`#ffffff`, kolor tekstu
na wypełnieniach), `--color-focus-ring` (`#2563eb`, **funkcjonalny** akcent).

### Semantyczne
`--color-success` (`#2d6a4f`, leśna zieleń — tekst/badge/"opłacone"),
`--color-success-action` + `-dark` (`#10b981`/`#059669`, szmaragd — potwierdź/zapisz),
`--color-warning` (`#9a6700`), `--color-error` (`#9b2c2c`), `--color-info`
(`#1e6091`), rodzina `--color-purple*`. **Dwie zielenie są celowe** (nie łączyć) —
leśna do statusu/tekstu, szmaragdowa do wypełnień akcji.

### Status wizyty (cykl życia)
`--color-status-{scheduled|confirmed|in-progress|completed|cancelled|no-show}`,
każdy z wariantem `-bg`/`-badge` (część też `-dark`) — do badge'y i chipów w
kalendarzu.

### Panel informacyjny
`--color-info-bg`/`-border`/`-text`/`-text-dark` (tony niebieskie).

### Paleta wykresów
`--color-chart-{blue|green|orange|red|purple|pink|teal|amber|slate|sky}` +
`--color-chart-blue-dark`.

### Gwiazdki ocen
`--color-star-filled` (`#f59e0b`), `--color-star-empty` (`#d1d5db`).

### Easing
`--ease-out-expo: cubic-bezier(0.16,1,0.3,1)` (żwawe wyhamowanie — mikrointerakcje),
`--ease-out-quart: cubic-bezier(0.25,1,0.5,1)` (łagodne wyhamowanie).

### Sidebar
`--sidebar-bg`/`-bg-deep`/`-text`/`-text-hover`/`-text-active`/`-heading`/`-border`/
`-hover-bg`/`-active-bg`/`-active-border` — patrz §9 dla wartości per motyw.

---

## 3. System motywów

**To jest część systemu nieobecna w żadnym starszym dokumencie w repo** — dodana po
ostatniej aktualizacji `DESIGN-TOKENS.md`. Cztery motywy, przełączane atrybutem
`data-theme` na `<html>`:

| Motyw | Selektor | Charakter |
|---|---|---|
| **Jasny** (domyślny) | *(brak atrybutu)* — `:root` | Ciepły beż/écru, złoty akcent |
| **Niebieski** | `[data-theme="blue"]` | Chłodny granat/stal, niebieski akcent |
| **Zielony** | `[data-theme="green"]` | Głęboka zieleń, zielony akcent |
| **Grafitowy** | `[data-theme="graphite"]` | Neutralny szary, śliwkowy akcent |

Każdy motyw nadpisuje **ten sam zestaw nazw zmiennych**: `--color-ink*`,
`--color-surface*`, `--color-border*`, `--color-accent*`, `--sidebar-*`. Zmienne
semantyczne (`--color-success*`, `--color-warning`, `--color-error`, `--color-info*`,
`--color-status-*`, `--color-chart-*`, `--color-star-*`, `--color-focus-ring`)
**pozostają stałe we wszystkich motywach** — nie są przedefiniowywane.

**Mechanizm przełączania** (`static/js/theme.js` + inline skrypt w `base.html`):
1. **Bez FOUC** — `base.html` w `<head>`, *przed* pierwszym malowaniem, synchronicznie
   czyta `localStorage['theme']` i ustawia `data-theme` na `<html>`.
2. `theme.js` obsługuje wyłącznie popover w stopce sidebara (przycisk
   `#theme-toggle-btn` + menu `#theme-menu`, `role` menu z nawigacją strzałkami/
   Home/End/Escape, `aria-checked` na aktywnej pozycji) i persystuje wybór do
   `localStorage`.

`★ Insight ─────────────────────────────────────`
Rozdzielenie "co pomalować" (inline skrypt w `<head>`) od "jak obsłużyć UI" (`theme.js`
ładowany na końcu `<body>`) to klasyczny wzorzec przeciw FOUC (Flash Of Unstyled
Content). Gdyby ustawienie `data-theme` czekało na załadowanie `theme.js` na dole
strony, użytkownik z zapisanym motywem "niebieskim" zobaczyłby przez ułamek sekundy
motyw jasny, a potem "mignięcie" na niebieski. Inline skrypt w head jest brzydszy
architektonicznie (kod poza plikami JS), ale to jedyny sposób, by zdążyć przed
pierwszym renderem.
`─────────────────────────────────────────────────`

**Historia:** motyw miał wcześniej też warianty `dark` i `brown` — zostały usunięte
na rzecz `graphite` (patrz commit `bddb4a5`). Jeśli natrafisz na `data-theme="dark"`
lub `data-theme="brown"` w starym kodzie/screenshotach — to relikt, nie aktywny motyw.

---

## 4. Typografia

Jedyny font: `--font-display` = `--font-body` = `'Inter', system-ui, sans-serif`.

| Zastosowanie | Waga | Rozmiar | Klasa/uwaga |
|---|---|---|---|
| Tytuł strony | 600 | zmienny | `.page-title` |
| Podtytuł strony | 300 | — | `.page-subtitle` |
| Wartość statystyki | 600 | 1.25rem | `.stat-value` |
| Etykieta statystyki | 500 | 0.6875rem, uppercase | `.stat-label` |
| Komórka tabeli | 400 | 0.8125rem | `.refined-table td` |
| Nagłówek tabeli (th) | 500 | 0.6875rem, uppercase, tracking 0.12em | `.refined-table th` |
| Etykieta formularza | 500 | 0.8125rem | `.form-label` |
| Input formularza | 400 | 0.875rem | `.form-input` |
| Tekst przycisku | 500 | 0.8125rem, tracking 0.02em | `.refined-btn-primary` |

---

## 5. Komponenty — przyciski, formularze, karty

### Przyciski globalne (`input.css @layer components`)

| Klasa | Rola | Wypełnienie |
|---|---|---|
| `.refined-btn-primary` | Główna akcja | Płaskie `--color-ink`, hover `--color-ink-muted` + unoszenie 1px + cień |
| `.refined-btn-secondary` | Akcja drugorzędna | Białe tło, obramowanie tokenowe |
| `.refined-btn-ghost` | Niska ranga / ikonowe | Przezroczyste, obramowanie tokenowe |
| `.refined-btn-danger` | Destrukcyjna (usuń) | Przezroczyste, tekst `--color-error`, hover czerwony tint |
| `.refined-btn-sm` | Modyfikator rozmiaru | Dodaj obok wariantu koloru |

Formularze mają **osobny, równoległy** zestaw (`templates/components/form_fields.html`
+ `input.css`): `.form-btn-primary` / `.form-btn-secondary` — identyczna logika
kolorów co `.refined-btn-*`, ale inne paddingi/font-size (dopasowane do gęstości
formularza, nie listy). **Cancel w formularzach renderuje się jako `<a href>`** z
klasą `.form-btn-secondary`, nie jako `<button>`.

Wszystkie warianty mają stan `:disabled` (`opacity: 0.6`, `pointer-events: none`) —
nigdy nie ukrywaj przycisku warunkowo, gdy można go zdisejblować.

### Formularze
`.form-label`, `.form-input`/`.form-select`/`.form-textarea` (border tokenowy,
`--radius-sm`, focus ring `0 0 0 3px rgba(26,26,26,.04)`), `.form-card`
(`--radius-md`, sekcja pól), `.form-paste-btn` (przycisk wklejania z OCR).

Makra w `templates/components/form_fields.html`: `text_input`, `number_input`,
`date_input`, `select_input`, `textarea_input`, `checkbox_input`, `currency_input`,
`form_actions`, `field_error`, `field_helper`, `readonly_field`, `form_section`.
**Nie twórz ręcznie `<input>`** — użyj makra.

**Zasada mobilna (globalna, `@layer base`):** przy `max-width: 1023px` każdy
`input`/`select`/`textarea`/`.ss-trigger`/`.ss-search`/`.refined-input` ma wymuszony
`font-size: 16px !important`. To dokładny próg, poniżej którego Safari na iOS
automatycznie zooomuje przy fokusie pola — **nigdy nie schodź poniżej 16px** dla
kontrolek formularza na mobile. `!important` jest tu konieczny (patrz insight w §1).

### SearchableSelect (własny dropdown)
Każdy `<select>` z >~5 opcjami powinien być wzbogacony:
```js
SearchableSelect.enhance('#client-select');   // raz, przy renderowanych opcjach Jinja
SearchableSelect.sync('client-select');        // po dynamicznym dociągnięciu opcji (fetch)
SearchableSelect.setValue(el, val);             // ustawienie wartości programowo
```
CSS mieszka w **inline `<style>` w `base.html`**, nie w `input.css` — celowo, bo
`output.css` jest gitignored i nie musi być zbudowany, żeby te style dotarły na
serwer wdrożeniowy.

### Karty / statystyki
`.stat-card`, `.stat-icon` (warianty `.blue`/`.green`/`.purple`/`.orange`),
`.search-card` (panel wyszukiwania/filtrów), `.table-container` (otoczka scrolla
tabeli), `.empty-state`/`.empty-icon`/`.empty-text` (pusty stan listy).

---

## 6. Tabele

### Bazowa `.refined-table`
Token-owa: `th` — `0.6875rem`/500/uppercase/tracking `0.12em`/kolor
`--color-ink-subtle`; `td` — `0.8125rem`/`--color-ink`; hover wiersza
`background: var(--color-surface)`. Strony ze stronicowanym własnym `<style>`
(niewarstwowanym) mogą nadpisywać dowolną właściwość per-stronę — to zamierzone.

### Sortowanie — wzorzec dostępny (S3, Faza 06)
```html
<th class="th-sortable" aria-sort="none|ascending|descending">
  <button type="button" class="th-sort-btn">
    Etykieta <span class="th-sort-icon" aria-hidden="true">▲</span>
  </button>
</th>
```
Glify tekstowe (nie SVG, nie font ikon): `▲` rosnąco, `▼` malejąco, przygaszone `▲`
gdy nieaktywne. Klawiatura działa natywnie (to `<button>`), `:focus-visible` ma
własny ring. **Każda strona z sortowaniem po stronie klienta ma własny sorter JS** —
`table-utils.js` **został usunięty** (zero żywych konsumentów, każda lista miała
już swój sorter z synchronizacją `aria-sort`; patrz §12).

### Widok mobilny — `.stack-cards` (wzorzec ADR-D-01, Faza 260613)
Współdzielony komponent w `input.css @layer components`, opt-in per tabela:
```html
<table class="refined-table stack-cards">
  <tr>
    <td data-label="Kolumna">wartość</td>
    <td class="cell-name" data-label="">Jan Kowalski</td>   <!-- nagłówek karty -->
    <td class="cell-actions">…</td>                          <!-- stopka "Akcje" -->
    <td class="cell-hide-sm">…</td>                          <!-- ukryte na kartach -->
    <td class="cell-empty" colspan="…">Brak wyników</td>      <!-- pełna szerokość -->
  </tr>
</table>
```
Przy `≤640px`: `thead` znika, każdy `<td>` staje się wierszem flex z
`::before { content: attr(data-label) }`. Jeden DOM, czysto CSS-owe — desktop
nietknięty (atrybut `data-label` jest bez efektu >640px). Wdrożony na **13 tabelach**
(faktury, wizyty, sprzedawcy, pracownicy, użytkownicy, role, nieobecności — wnioski/
kategorie/bilanse, moje-nieobecności, przypisane usługi pracownika, kategorie usług,
formy zatrudnienia). Dla tabel z osobną przewijaną główką (faktury, sprzedawcy) —
`stack-cards` idzie na tabelę **body**, z lokalnym blokiem `≤640px` ukrywającym
sticky header.

---

## 7. Modale, powiadomienia, toasty

### Modal — dwie ścieżki wywołania
```js
// Potwierdzenie destrukcyjnej akcji
Modals.confirm({
  title: 'Potwierdź usunięcie', message: 'Czy na pewno?',
  confirmText: 'Usuń', onConfirm: () => { /* akcja */ }
});

// Modal generyczny (formularz/panel danych)
const overlay = Modals.show({
  title: 'Tytuł', content: '<p>…</p>', size: 'medium', // small|medium|large
  buttons: [
    { text: 'Anuluj', type: 'secondary', onClick: (e, o) => Modals.close(o) },
    { text: 'Zapisz', type: 'primary', onClick: (e, o) => { /* akcja */ } }
  ]
});

Modals.alert({ title, message, type: 'info' });
Modals.loading('Przetwarzanie…');
Modals.closeAll();
```
**Wygląd (aktualny, płaski — nie gradientowy)**: `.modal-overlay` (backdrop-blur 4px,
`z-index: 9999`), `.modal-content` (`--color-surface-elevated`, `--radius-md`, cień
`0 8px 32px rgba(0,0,0,.18)`), przyciski stopki `.btn-primary`/`.btn-secondary`/
`.btn-danger`/`.btn-success` — te same płaskie tokeny co `.refined-btn-*`, **bez
gradientów**, `--radius-sm`. Animacja wejścia/wyjścia przez klasę `.is-closing`
(fade + scale 0.98).

### Toasty (runtime)
```js
Notifications.success('Zapisano'); Notifications.error('Błąd połączenia');
Notifications.warning('Sprawdź dane'); Notifications.info('Ładowanie…');
Notifications.show('Wiadomość', 'success', 8000);  // 0 = trwały
Notifications.clear();
```
Kontener `fixed bottom-4 right-4`, maks. 3 sztaple — najstarszy usuwany
automatycznie.

### Flash messages (server-side)
Renderowane **raz** przez `base.html` via `components/flash_messages.html`. **Nigdy**
nie wywołuj `get_flashed_messages()` w szablonie potomnym — kolejka Flaska jest
jednorazowego odczytu.
```python
flash('Zapisano pomyślnie', 'success')  # kategorie: success|error|warning|info
```

### Undo toast (miękkie usuwanie)
```js
showUndoToast('Rekord usunięty', '/api/records/123/restore', 8000);
```

---

## 8. System ikon

**Wyłącznie inline SVG — font ikon (Material Icons) został w całości usunięty**
(Faza 260613, plan `phase-06-material-icons-sweep-font-removal.md`). Źródło
prawdy ścieżek: `templates/components/icons.html` (Jinja) + odpowiednik JS
`static/js/icons.js` — **muszą być trzymane w synchronizacji ręcznie**.

```jinja
{% from 'components/icons.html' import icon %}
{{ icon('save', class='w-4 h-4') }}
```
```js
Icons.svg('save', 'w-4 h-4')
```

Ścieżki pochodzą z Google Material Symbols (`viewBox 0 -960 960 960`), nigdy pisane
ręcznie. `.icon` (baza w `input.css`) skaluje się przez `font-size` (`1em`), więc
klasy `text-sm`/`text-xl` nadal działają, a kolor dziedziczy przez `currentColor`.
Nieznana nazwa ikony spada na `info` (fallback), nie wywala błędu.

Aby dodać nowy glif: znajdź go w Material Symbols (outlined), wklej `<path>` do
**obu** plików (`icons.html` i `icons.js`) pod tym samym kluczem.

---

## 9. Sidebar i nawigacja

Struktura: sekcje akordeonowe (JS steruje `maxHeight`, tylko jedna sekcja rozwinięta
naraz), makra `sidebar_link`/`sidebar_section_start`/`sidebar_section_end` z
`templates/macros/sidebar_macros.html`.

**Aktywny link:** złoty pasek 3px (`--sidebar-active-border` = `--color-accent`) na
tle `--sidebar-active-bg` (tint akcentu), aktywna ikona też złota. Tekst aktywny
pozostaje `ink` (nie złoty) — złoto zarezerwowane dla paska/ikony.

**Stopka:** awatar z gradientem `linear-gradient(135deg, --color-accent, --color-accent-deep)`,
pełne imię i nazwisko, polska etykieta roli. Link wylogowania czerwienieje na hover
przez inline `onmouseenter`/`onmouseleave` (celowo nie Tailwind — działa niezależnie
od tego, czy dokładnie te klasy przetrwały purge).

**Tokeny sidebaru per motyw** (§3) — jasny: `#dedad3`/`#d2cec6` (ciepły beż);
niebieski: `#dde7f4`/`#cddaed`; zielony: `#dbe9d6`/`#cbdec4`; grafitowy:
`#e2e2e6`/`#d5d5da`. Każdy motyw ma spójny komplet `-text`/`-text-hover`/
`-text-active`/`-heading`/`-border`/`-hover-bg`, a `-active-bg`/`-active-border`
zawsze wskazują na `--color-accent-muted`/`--color-accent` tego motywu (więc pasek
aktywnego linku zmienia kolor razem z motywem — nie jest już zawsze złoty poza
motywem jasnym).

**Mobile:** sidebar `hidden lg:flex`, przełącznik `#sidebar-toggle` w headerze
(`lg:hidden`), ciemny overlay `#sidebar-overlay` za otwartym sidebarem mobilnym.

---

## 10. Ruch i przejścia stron

### View Transitions API (progresywne wzbogacenie, commit `0ded5a7`)
```css
@view-transition { navigation: auto; }   /* włącza cross-document transitions dla MPA */
```
Dwa niezależne cele przejścia:
1. **`sidebar-active-link`** — wszystkie linki sidebara dzielą jedną nazwę
   transition, więc przeglądarka morfuje złoty pasek między starą a nową stroną
   zamiast go "przeskakiwać".
2. **`main-page-content`** (na `#main-content`, **nie** na `:root`) — treść
   routowana fade'uje + lekko przesuwa się w górę (`translateY(10px)→0`, 340ms)
   przy wejściu, a stara treść fade'uje + przesuwa w górę wychodząc (320ms).
   Nazwa transition jest celowo na `#main-content`, nie na całym dokumencie — dzięki
   temu **stały chrome (sidebar/header) nigdy się nie rusza**, tylko routowana treść.

Oba respektują `@media (prefers-reduced-motion: reduce)` (animacje wyłączone
całkowicie).

### Inne mikrointerakcje (`@layer components`, dodaj klasę do elementu)
| Klasa | Efekt | Użycie |
|---|---|---|
| `.btn-press` | `scale(0.97)` na `:active` | Wszystkie klikalne przyciski |
| `.hover-lift` | `translateY(-2px)` + cień | Karty, panele |
| `.animate-fade-up` | opacity + translateY(10px) → normalny | Sekcje strony przy ładowaniu |
| `.stagger-item` | opóźnienie `nth-child` na `.animate-fade-up` | Wiersze tabeli |
| `.skeleton` | shimmer | Placeholder ładowania |
| `.success-pulse` / `.error-shake` | zielony pulse / poziomy trzęs | Po zapisie / błąd walidacji |

---

## 11. Dostępność i mobile

1. **Skip link** do `#main-content` (z `base.html`).
2. Przyciski ikonowe → `aria-label`.
3. Aktywny link nawigacji → `aria-current="page"`.
4. Modale → `role="dialog"`, `aria-modal="true"`, `aria-labelledby`.
5. Pola formularzy → `<label for>` powiązany z `id` inputu.
6. `.sr-only` dla tekstu tylko dla czytników ekranu.
7. Nagłówki sortowalne → `aria-sort` synchronizowane po każdym sortowaniu
   (`ascending`/`descending`/`none` na sąsiadach).
8. Kontrast: `ink` `#1a1a1a` na `#ffffff` = 18.1:1 (znacznie powyżej WCAG AA).

**Nagłówek mobilny (page_title):** każda routowana strona (`<lg`) dostaje tytuł z
`config/page_titles.py` — mapa `request.endpoint → polska etykieta`, wystawiana
przez `inject_globals` jako `page_title`. `base.html`'s
`{% block mobile_title %}{{ page_title or '' }}{% endblock %}` domyślnie z niej
korzysta; strona może nadpisać blokiem jawnie. **Dodając nowy endpoint z własnym
tytułem mobilnym — dopisz go do `PAGE_TITLES` w `config/page_titles.py`.**

**Guard zoomu iOS:** patrz §5 (16px na kontrolkach formularza ≤1023px, `!important`
obowiązkowy).

---

## 12. Rozbieżności wobec starszych dokumentów w repo

Podczas audytu potwierdziłem, że **`GUI-GOLDEN-BOOK.md` (ostatnia aktualizacja
2026-06-30) jest w kilku miejscach nieaktualny** względem obecnego stanu kodu:

| Twierdzenie w `GUI-GOLDEN-BOOK.md` | Stan faktyczny w kodzie |
|---|---|
| "Ikony: Material Icons (Google CDN) + inline SVG heroicons" | Material Icons **usunięty całkowicie** — wyłącznie inline SVG (§8) |
| "Dwa systemy promieni — wybierz jeden per projekt" (System A 2px vs System B rounded-xl/2xl) | **Jeden** system — płaski, `--radius-sm`/`--radius-md` (2px/3px). `rounded-xl`/`2xl` zablokowane przez CI (§13) |
| Przyciski rounded: `bg-gradient-to-r from-primary-500 to-primary-600 rounded-xl` | `.refined-btn-primary` to płaskie `--color-ink`, `--radius-sm`, **bez gradientu** |
| Modal: `border-radius: 1rem`, gradientowe przyciski stopki | `.modal-content` = `--radius-md` (3px), przyciski stopki płaskie tokenowe (§7) |
| `--color-ink-subtle: #8a8a8a` | Aktualnie `#6b6b6b` w `input.css` |
| `table-utils.js` (`sortTable`, `applyAllFilters`, `exportToCSV`) jako globalny skrypt | **Usunięty** (zero konsumentów) — każda lista ma własny sorter (§6) |
| Brak wzmianki o motywach, View Transitions, `.stack-cards`, `page_title` | Wszystkie są aktywną częścią systemu (§3, §6, §10, §11) |

**Co w starszych dokumentach nadal jest wiarygodne** i warto po nie sięgać po
głębsze detale: API `Modals.*`/`Notifications.*`/`SearchableSelect.*` (zweryfikowane
zgodne z `static/js/modals.js`, `notifications.js`, `searchable-select.js`),
struktura makr `form_fields.html`, ogólna zasada "nie hand-rolluj komponentu, gdy
istnieje udokumentowany" z `GUI-COMPONENTS-GOLDEN-BOOK.md`.

**Rekomendacja:** przy kolejnej okazji warto zaktualizować lub zarchiwizować
`GUI-GOLDEN-BOOK.md`, żeby nie wprowadzać w błąd (np. dopiskiem na górze
wskazującym na ten plik jako aktualny). Nie zrobiłem tego teraz, bo nie było to
częścią prośby — daj znać, jeśli mam to też posprzątać.

---

## 13. Build, CI guard, mapa plików

### Pipeline
```
static/css/input.css  ──npm run build:css──▶  static/css/output.css (zminifikowany)
                                                  └─ asset_url() cache-bustuje przez hash treści
```
- `npm run watch:css` podczas developmentu.
- `output.css` jest **generowany i gitignored** — build dzieje się na serwerze przy
  deployu. Wszystko, co musi dotrzeć na serwer bez builda (np. CSS SearchableSelect),
  musi siedzieć w inline `<style>` w `base.html`, nie w `input.css`.

### CI design guard (`.github/workflows/ci.yml`, job `design-guard`)
Buduje build na `grep -rnE 'rounded-xl|rounded-2xl|from-primary-|to-primary-'` po
`templates/**/*.html`, z wyjątkiem trzech samodzielnych stron auth
(`login.html`, `forgot_password.html`, `reset_password.html` — nie ładują
`output.css`, więc migracja ich nie dotyczy). Każde trafienie **failuje build**.

### Mapa plików (design-relevant)
| Co | Gdzie |
|---|---|
| Tokeny + wszystkie klasy komponentowe | `static/css/input.css` |
| Ikony (Jinja) | `templates/components/icons.html` |
| Ikony (JS) | `static/js/icons.js` |
| Przełącznik motywu | `static/js/theme.js` + inline skrypt w `templates/base.html` `<head>` |
| Modale / Toasty / SearchableSelect | `static/js/modals.js` / `notifications.js` / `searchable-select.js` |
| Makra formularzy | `templates/components/form_fields.html` |
| Makra sidebaru | `templates/macros/sidebar_macros.html` |
| Mapa tytułów mobilnych | `config/page_titles.py` |
| CI design guard | `.github/workflows/ci.yml` (job `design-guard`) |
| Historia decyzji projektowych | `plans/260610-ui-usability-fixes/`, `plans/260613-deferred-design-tickets/` |

---

*Dokument wygenerowany na podstawie bezpośredniego audytu kodu, nie na podstawie
wcześniejszych dokumentów w repo. Jeśli coś tu opisane straci aktualność po kolejnej
zmianie w `input.css`/`base.html` — ten plik trzeba zaktualizować ręcznie, nie ma
automatycznej synchronizacji.*
