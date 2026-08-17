# Faza 0 — Fundamenty

Musi być zamknięta przed jakąkolwiek stroną modułową (Faza 1+). Nic w tej fazie nie zależy od
konkretnego modułu biznesowego — to czysty szkielet aplikacji + auth + chrome.

## 0.1 Scaffold

```
frontend/                          # nowy katalog, root repo zostaje wspólny (monorepo, nie osobne repo)
├── index.html                     # inline no-FOUC theme script w <head> (DESIGN.md §4 rule 5)
├── vite.config.ts                 # dev server :5173, proxy /api → backend Flask (:5000/whatever)
├── src/
│   ├── main.tsx
│   ├── router.tsx                 # DESIGN.md §14
│   ├── styles/
│   │   ├── index.css              # @import kolejność z DESIGN.md §0
│   │   ├── tokens.css             # :root + [data-theme] — patrz §0.2 niżej
│   │   ├── base.css
│   │   └── components.css
│   ├── lib/
│   │   ├── api/client.ts          # fetch wrapper, credentials:'include' (DESIGN.md §18)
│   │   ├── icons/Icon.tsx + paths.ts
│   │   └── a11y/escapeScope.ts    # useEscapeClaim/useEscapeAction (DESIGN.md §11.2)
│   ├── contexts/AuthContext.tsx
│   ├── components/
│   │   ├── ui/Button.tsx, form.tsx
│   │   ├── layout/Sidebar.tsx, SidebarSection.tsx, NavIcon.tsx, navConfig.ts
│   │   └── feedback/ToastProvider.tsx, ConfirmProvider.tsx
│   └── pages/auth/{Login,ForgotPassword,ResetPassword}.tsx
```

**Build/dev integracja z Flaskiem:** w developmencie Vite serwuje `:5173` i proxy'uje `/api/*` do
backendu Flask. Do potwierdzenia przed startem: czy produkcyjny build Vite (statyczne pliki) będzie
serwowany *przez* Flask (jeden origin, prościej dla cookies `SameSite=Lax`) czy z osobnego hostingu
(wtedy `SameSite=Lax` + `credentials:'include'` może wymagać `SameSite=None; Secure` i CORS —
realna różnica w konfiguracji auth, nie kosmetyka). **To pytanie architektoniczne do rozstrzygnięcia
na starcie Fazy 0**, bo determinuje ustawienia cookie sesji backendu.

## 0.2 Port tokenów (`input.css :root` → `tokens.css`)

Mechaniczny port **z wyjątkami z `plan.md` §0.1** (font, cienie, orange/pink, 4 różniące się
wartości surface). Checklist:

- [ ] Skopiuj 1:1: `--color-ink*`, `--color-border*`, `--radius-sm/md`, `--color-accent*`,
      `--color-focus-ring`, `--color-success*`, `--color-warning`, `--color-error`, `--color-info*`,
      `--color-purple*`, wszystkie `--color-status-*`, wszystkie `--color-chart-*`,
      `--color-star-*`, `--ease-out-*`.
- [ ] Zamień `--font-display`/`--font-body` na `'Geist Variable', system-ui, sans-serif` (**decyzja
      świadoma, nie automatyczna** — potwierdź przed commitem, patrz `plan.md` §0.1 pkt 1).
- [ ] Dodaj `@fontsource-variable/geist` jako zależność npm; usuń ewentualny Google-Fonts `<link>`
      (obecny `input.css`/`base.html` już nie ładuje Google Fonts dla Inter — sprawdzić czy jest
      gdzieś w `base.html` `<head>` mimo wszystko, bo `GUI-GOLDEN-BOOK.md` o tym wspominał jako
      historyczny fakt).
- [ ] Dopisz **nowy** ramp cieni z `DESIGN.md` §2.5 (`--shadow-xs…xl`, `--shadow-focus`,
      `--shadow-sidebar`) — nie istnieje dziś, więc nie ma czego "portować", tylko dodać.
- [ ] `--color-surface-warm`/`--color-surface-elevated`: użyj wartości z `DESIGN.md`
      (`#f2f0ea`/`#fdfcfa`), nie z `input.css` (`#f7f6f3`/`#ffffff`) — **ale wklej oba obok siebie w
      PR-opisie do jednorazowego review wzrokowego** (patrz `plan.md` §0.1 pkt 5).
- [ ] Dodaj `--color-orange`/`--color-pink` jako nowe nazwane tokeny; przejrzyj każde miejsce w
      `input.css` używające `#c2410c` (m.in. `.stat-icon.orange`, `.stat-value.orange`,
      `.status-badge.on-leave`) i zdecyduj: `var(--color-orange)` czy to jednak coś innego.
- [ ] Sidebar: port 4 bloków `[data-theme]` z `input.css` (linie ok. 111–238) 1:1 — te wartości
      DESIGN.md nie kwestionuje.
- [ ] Dodaj `--sidebar-logo-filter` (token wymieniony w DESIGN.md §2.13, nie istnieje w obecnym
      `input.css`) — prawdopodobnie CSS `filter` do przebarwienia logo per motyw; do zaprojektowania
      od zera, bo dzisiejsze logo/motywy nie mają takiego mechanizmu.

## 0.3 Auth — jedyna prawdziwa luka backendowa

**Cel:** React musi móc się zalogować, wylogować, sprawdzić sesję (`/me`), zresetować hasło —
wszystko przez JSON, bez psucia dzisiejszego `request.form` + redirect flow używanego przez
ewentualne pozostające strony Jinja w okresie przejściowym.

### Backend (`routes/auth/routes.py`, dziś 224 linie — rozszerzenie, nie przepisanie)

Wzorzec: każdy istniejący handler (`login`, `logout`, `forgot_password`, `reset_password`,
`change_password`) dostaje na początku rozgałęzienie:

```python
wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
```

- Gdy `wants_json` i sukces → `jsonify({'success': True, ...})` zamiast `redirect(...)`.
- Gdy `wants_json` i błąd walidacji/auth → `jsonify({'success': False, 'error': '...'}), 4xx`
  zamiast `flash(...) + render_template(...)`.
- Brak `wants_json` → **dzisiejsze zachowanie bez zmian** (bezpieczne dla stron Jinja, które żyją
  równolegle przez cały big-bang).
- Dodać endpoint `GET /auth/me` (dziś nie istnieje w tej formie — sprawdzić, czy coś podobnego jest
  w `api_routes.py`, bo plik ma 4589 linii i mogło umknąć w audycie) zwracający obecnego
  `current_user` + `role` + `permissions` albo `401` gdy brak sesji — to jest backbone
  `AuthContext`'owego "session-check-on-load" z DESIGN.md §15.1.
- `remember`/`session.permanent` (linia 44 dziś) — logika zostaje identyczna, tylko odczyt pola z
  `request.form.get('remember')` **albo** z JSON body w zależności od `Content-Type`.
- **Reset hasła — dokładnie sprawdzić, czy dzisiejszy `forgot_password()` (linia 133+) już zwraca
  link na ekranie czy wysyła mailem**, zanim napiszemy JSON wariant — `DESIGN.md` §15.3 zakłada
  konkretnie wariant "link pokazany na ekranie, bo brak realnego e-maila" jako świadomy stan
  dev/demo. Kod backendu (`token = secrets.token_urlsafe(32)`, linia 156) potwierdza mechanizm
  tokenu, ale **nie sprawdziłem jeszcze, co dokładnie dzieje się z tym tokenem dalej** (czy leci
  mailem czy na ekran) — **to jest dokładnie kandydat na "poproś o przykład kodu"**:

> **Gotowy prompt do innej sesji/agenta na tym repo**, jeśli chcesz mieć to potwierdzone przed
> pisaniem JSON auth:
> *"W `routes/auth/routes.py`, funkcja `forgot_password()` (linia ~133–178) i `services/auth/auth_service.py` —
> pokaż mi dokładnie, co się dzieje po wygenerowaniu tokenu resetu hasła: czy wysyłany jest e-mail,
> czy URL resetu trafia do kontekstu szablonu/response, i jaki dokładnie jest kształt tego, co widzi
> użytkownik na ekranie 'zapomniałem hasła'. Pokaż też pełną treść `reset_password()` (linia
> 178–224) i sprawdź, czy istnieje już jakikolwiek endpoint zwracający JSON zamiast
> redirect/render_template w całym `routes/auth/` — jeśli tak, wklej go w całości."*

### Frontend

- `AuthContext` — `user`, `isLoading`, `login()`, `logout()`, hydratacja przez `GET /auth/me` na
  starcie (DESIGN.md §15.1).
- `ProtectedRoute` — dwa tryby (`requireModule` / `guard`), czeka na `isLoading` (DESIGN.md §14.2).
- Trzy ekrany: `Login`, `ForgotPassword`, `ResetPassword` — `AuthLayout` wspólny, walidacja on-submit
  (DESIGN.md §15.5). Login → jedyne miejsce z `variant="brand"` na przycisku.
- **Hasła: min. 8 znaków — potwierdzić że to nadal aktualna wartość w `auth_service.py`/backendzie
  zanim się to zahardkoduje po stronie frontu** (DESIGN.md §15.3 zakłada 8, ale to backend jest
  źródłem prawdy — jeden grep przed napisaniem walidacji frontowej).

## 0.4 Shell, sidebar, routing

- `navConfig.ts` — port z `templates/macros/sidebar_macros.html` + dzisiejszej struktury sekcji.
  **Nie mam jeszcze dokładnej listy sekcji/linków z prawdziwego kodu sidebaru** (widziałem tylko
  makra, nie wywołania per-sekcja) — do zrobienia jako pierwszy krok tej podfazy, bezpośrednim
  czytaniem `templates/components/sidebar.html`.
- Dla każdego `NavLinkConfig.visible`: sparować z dokładnym `@module_permission_required(...)` /
  sprawdzeniem roli z odpowiadającej trasy Flask — **to jest dokładnie pułapka opisana w
  DESIGN.md §13.5** (moduł "settings" dający fałszywy dostęp do czegoś faktycznie zgated na
  `role === 'superuser'`). Zrobić to per-moduł w Fazie 2, nie zgadywać teraz zbiorczo.
- Route tree (`router.tsx`) — jeden zewnętrzny `<ProtectedRoute>` (bare auth gate) + zagnieżdżone
  bardziej specyficzne tam, gdzie backend faktycznie ma dodatkowy gate (RBAC, superadmin).
- Mobile page-title lookup (DESIGN.md §12) — 1:1 port `config/page_titles.py`'s `PAGE_TITLES`
  dict → `[pathPrefix, title][]`, zachowując polskie etykiety. Uwaga: obecny mechanizm jest
  `request.endpoint` (exact match dict), docelowy — `pathname.startsWith(prefix)` (prefix match,
  longest-first) — to zmiana strategii dopasowania, nie 1:1 kopiowanie kluczy; przy porcie każdy
  endpoint trzeba przekonwertować na URL prefix i sprawdzić kolizje (np. `/klienci` vs
  `/klienci/nowy` — kolejność ma znaczenie).

## 0.5 Theming

- Inline no-FOUC script (DESIGN.md §4 rule 5) → `frontend/index.html` `<head>`, 1:1 z dzisiejszym
  odpowiednikiem w `base.html`.
- `ThemeSwitcher` komponent — port `static/js/theme.js` (popover, `role="menu"`, `menuitemradio`,
  strzałki/Home/End/Escape) na React + hook `useEscapeClaim`.
- 4 motywy (`light`/`blue`/`green`/`graphite`) — wartości z §0.2. **Bez `dark`/`brown`** — te zostały
  świadomie usunięte z produktu (commit `bddb4a5`), nie odtwarzać.

## 0.6 Ikony — dwa systemy do zbudowania

- **Glify** (`Icon.tsx`, `0 -960 960 960`, filled) — port bezpośredni z `templates/components/icons.html`
  (mapa `_ICON_PATHS`, ~70 wpisów) → `paths.ts`. Mechaniczne kopiowanie stringów `<path d="...">`.
- **NavIcon** (`0 0 24 24`, stroke) — **nowy system, nie istnieje dziś.** Sidebar dziś dostaje
  surowy `svg_path_d` per link (prawdopodobnie też w `0 -960 960 960`, do potwierdzenia przy
  czytaniu `sidebar.html`) — trzeba dobrać 24×24 stroke-odpowiedniki (Heroicons outline, jak
  sugeruje DESIGN.md §9) dla każdej dzisiejszej ikony nawigacji, nie automatyczna konwersja
  coordinate-space.

## 0.7 Feedback systems

| Dzisiaj (vanilla JS) | Docelowo (React) | Mapowanie API |
|---|---|---|
| `Notifications.success/error/warning/info/show/clear` | `useToast()` | 1:1 nazwy metod, ta sama semantyka (max 3, domyślne 4000ms u DESIGN.md vs dzisiejsze — **sprawdzić dokładną domyślną wartość w `notifications.js`** przed przyjęciem 4000 na sztywno) |
| `Modals.confirm({title,message,confirmText,onConfirm})` | `useConfirm()` — **zmiana z callbacku na Promise** (`const ok = await confirm(...)`) | Sama treść configu 1:1, ale wołający kod zmienia kształt (callback → await) — to dotyka **każdego miejsca w każdym module**, gdzie dziś wywoływane jest `Modals.confirm`/`confirmDelete` — policzyć realną liczbę wystąpień przed Fazą 2 (`grep -rn "Modals.confirm\|confirmDelete" static/js templates` — nie zrobione jeszcze w tym audycie) |
| `Modals.show/alert/loading/closeAll` | Generic `.modal-*` classes + własny hook per przypadek (DESIGN.md §8.3) | Nie ma gotowego 1:1 komponentu — każde użycie `Modals.show()` trzeba ocenić indywidualnie: czy to faktycznie confirm (→ `useConfirm`) czy prawdziwy custom modal (→ nowy React komponent na `.modal-*`) |

## 0.8 Definicja ukończenia Fazy 0

- [ ] `npm create vite` scaffold działa, `npm run dev` serwuje pustą stronę z działającym
      no-FOUC theme switchem (4 motywy przełączalne, bez migotania).
- [ ] Logowanie działa end-to-end przez nowy JSON auth (prawdziwa baza, prawdziwy użytkownik
      testowy) — sesja cookie ustawiona, `GET /auth/me` zwraca użytkownika po odświeżeniu strony.
- [ ] Sidebar renderuje się z `navConfig.ts` (może być z placeholderowymi linkami do stron, które
      jeszcze nie istnieją w Fazie 1) z poprawnym accordion/mobile-drawer/View-Transitions
      zachowaniem.
- [ ] Diff tokenów (§0.2) zaakceptowany wzrokowo przez kogoś, kto patrzy na oba zrzuty ekranu obok
      siebie — nie tylko na kod.
- [ ] `useToast`/`useConfirm` zamontowane raz w roocie, przetestowane manualnie (jeden przykładowy
      toast + jeden przykładowy confirm dialog na tymczasowej stronie).
