# Implementation log — Faza 0 + Faza 1 (react-migration)

Chronologiczny log decyzji podjętych samodzielnie podczas implementacji, zgodnie z poleceniem
"pracuj ciągle, nie pytaj — zapisz decyzję tutaj". Branch: `react-migration` (z `full-redesign-stitch`).

---

## 2026-08-14 — Start

- Przeczytano w całości: `DESIGN.md`, `plan.md`, `phase-00-foundations.md`,
  `phase-01-pilot-clients.md`, `module-inventory.md`, oraz bezpośrednio w repo: `routes/auth/routes.py`,
  `services/auth/auth_service.py`, `templates/components/sidebar.html`, `config/page_titles.py`,
  `templates/components/icons.html`, `static/js/{notifications,modals,theme,utils}.js`,
  `static/css/input.css` (tokeny), `templates/clients/{list,create,edit,view}.html`,
  `routes/api_routes.py` (sekcja klientów, linie 2549–3084), `routes/client_preference_routes.py`,
  `routes/appointment_routes.py` (endpoint historii wizyt klienta), `app.py` (context processor —
  kształt uprawnień), `config/auth_config.py` (RBAC: `module_permission_required`, flagi
  `has_access/read_only/own_data`).
- Utworzono branch `react-migration` z `full-redesign-stitch`. Niezacommitowane zmiany
  kalendarza/sidebara (redesign w toku na `full-redesign-stitch`) pozostają nietknięte — nie były
  stage'owane, nie ruszam ich.
- Sprawdzono dostęp do rejestru npm (`npm ping` → PONG) — scaffold Vite może instalować pakiety.

## Decyzja D1 — Dev-proxy / produkcyjny hosting frontendu (phase-00 §0.1, pytanie otwarte)

**Kontekst:** plan wymaga rozstrzygnięcia na starcie, czy produkcyjny build Vite jest serwowany
*przez* Flask (jeden origin) czy z osobnego hostingu (wymagałoby `SameSite=None; Secure` + CORS).

**Ustalenie z kodu:** `app.py` ustawia `SESSION_COOKIE_SAMESITE = 'Lax'`,
`SESSION_COOKIE_SECURE` sterowane env (domyślnie `false` — dev). Nie znaleziono żadnej
konfiguracji `flask-cors`/`Access-Control-Allow-Origin` w repo — dzisiejszy Jinja-frontend jest
zawsze same-origin.

**Decyzja:** produkcyjny build Vite (`frontend/dist/`) będzie serwowany przez Flask jako pliki
statyczne pod tym samym originem (analogicznie do dzisiejszego `static/`), **bez zmiany**
`SameSite=Lax`/braku CORS. W developmencie Vite dev-server (`:5173`) proxy'uje `/api/*` i `/auth/*`
do Flask (`:5000` — port potwierdzony poniżej), więc przeglądarka i tak widzi jeden efektywny
origin z punktu widzenia cookie (`Lax` wystarcza, bo XHR w dev też trafia przez `:5173` do Vite,
które przekazuje request do Flask; sam response cookie ma Domain=localhost niezależnie od portu
proxy'a — to standardowy wzorzec Vite dev-proxy, nie wymaga zmian backendu).
**Uzasadnienie:** najmniejsze ryzyko regresji auth, zero nowej powierzchni CORS, zgodne z
istniejącym `SameSite=Lax`. Serwowanie `dist/` przez Flask jest zakresem Fazy 4 (cutover) —
w Fazie 0/1 wystarczy sam dev-proxy; nie tworzę teraz nowej trasy Flask serwującej `dist/`,
bo nie ma jeszcze czego serwować w produkcji (big-bang, brak przełączenia).

## Decyzja D2 — Port Flask dla dev-proxy

Nie znaleziono jawnego `app.run(port=...)` w repo (prawdopodobnie uruchamiane przez WSGI/inny
mechanizm lokalnie) — przyjęto standardowy Flask dev port **5000** jako proxy target w
`vite.config.ts`, z komentarzem że jest to configurowalne przez `VITE_API_PROXY_TARGET` gdyby
lokalny setup używał innego portu. Nieblokujące — łatwe do zmiany przy pierwszym `npm run dev`.

## Decyzja D3 — Auth JSON: kształt `/auth/me` i payloadów

Brak istniejącego `/auth/me` w repo (potwierdzone grep). Zaprojektowano od zera, zgodnie z
DESIGN.md §15.1 i kształtem uprawnień z `app.py`'s `inject_globals`/`config/auth_config.py`:

```
GET /auth/me
200: { success: true, user: { id, email, full_name, role },
       permissions: { [module]: { has_access, read_only, own_data } },
       is_supervisor: bool, has_linked_employee: bool }
401: { success: false, error: '...' }
```

`permissions` używa `get_all_permission_flags(current_user.role)` — dokładnie ta sama funkcja,
której już używa `app.py`'s context processor dla Jinja-stron, więc kształt uprawnień w React
i w pozostających stronach Jinja jest tożsamy (jedno źródło prawdy, zero rozjazdu).

## Decyzja D4 — Reset hasła: potwierdzony mechanizm (phase-00 §0.3 "do sprawdzenia")

Przeczytano `forgot_password()`/`reset_password()` w całości. Potwierdzone: **brak wysyłki
e-mail** — `reset_url` trafia bezpośrednio do kontekstu szablonu (`render_template(...,
reset_url=reset_url)`), renderowany na ekranie. Token: `secrets.token_urlsafe(32)`, wygasa po
1h, `used` flag, unieważnienie poprzednich tokenów przy nowym request. Dokładnie zgodne z
DESIGN.md §15.3 "screen-shown reset link" — **żadna zmiana backendowej logiki nie jest
potrzebna**, JSON-wariant tylko opakowuje te same wywołania `auth_service`/bezpośrednie query i
zwraca `reset_url` w JSON zamiast wstrzykiwać go do Jinja.

Min. długość hasła potwierdzona w kodzie: **8 znaków** (`auth_service.py` linie 69, 89 oraz
`reset_password()` linia 197 w `routes/auth/routes.py`) — zgodne z DESIGN.md §15.3, żadnej
rozbieżności. Frontend hardkoduje 8 ze świadomością źródła.

## Decyzja D5 — Toast default duration: 4000ms (DESIGN.md) vs 3000ms (dzisiejszy `notifications.js`)

`static/js/notifications.js` ma `defaultDuration: 3000`. DESIGN.md §8.1 mówi **4000ms**.
Plan (`phase-00-foundations.md` §0.7) każe to sprawdzić przed przyjęciem 4000 na sztywno.
**Decyzja:** trzymam się DESIGN.md (4000ms) — DESIGN.md jest jawnie źródłem prawdy dla NOWEGO
frontendu (patrz nagłówek `plan.md`), a różnica jest kosmetyczna (1s dłużej widoczny toast) i
nieszkodliwa. Odnotowuję rozbieżność tutaj zamiast cichego zgadywania.

## Decyzja D6 — Ikony nawigacyjne (NavIcon, 24×24 stroke) — dobór per link

Sidebar dziś (`templates/components/sidebar.html`) już przekazuje surowy `svg_path_d` w
**24×24 stroke** (nie 0/-960/960/960 filled, wbrew podejrzeniu w planie) — widoczne po formacie
ścieżek (`M8 7V3m8...`, używane ze `stroke-width="2"`, `viewBox="0 0 24 24"` w makrze
`sidebar_link`). To oznacza, że **port do `NavIcon` jest 1:1 kopiowaniem istniejących
`svg_path_d` stringów**, nie doborem nowych ikon z Heroicons — plan (`phase-00` §0.6) zgadywał
niepotrzebnie ostrożnie; rzeczywistość jest prostsza. Skopiowano wszystkie path'y bezpośrednio z
`sidebar.html` do `navConfig.ts`.

## Decyzja D7 — Zakres nawigacji w Fazie 0

Sidebar Jinja ma ~25 linków w 5 sekcjach, obejmujących moduły spoza zakresu tego przebiegu
(Faktury, Sprzedawcy, Pracownicy, Nieobecności, RBAC, itd. — Faza 2). Zgodnie z phase-00 §0.8
("może być z placeholderowymi linkami do stron, które jeszcze nie istnieją w Fazie 1"): port
**całej struktury nawigacji 1:1** (wszystkie sekcje/linki/`visible` predykaty dokładnie
odzwierciedlające `{% if user_permissions.x %}`/`is_supervisor`/`has_linked_employee` z
`sidebar.html`), ale tylko `/klienci` (Klienci) faktycznie routuje do zaimplementowanej strony —
pozostałe linki wskazują na trasy, które renderują tymczasowy `<ComingSoonPage>` (chroniony przez
ten sam `ProtectedRoute`, więc uprawnienia są od razu poprawne, tylko treść strony czeka na
Fazę 2). To pozwala odhaczyć "Sidebar renderuje się z navConfig.ts (może być z placeholderowymi
linkami)" bez fałszywego zawężania nawigacji do jednego linku.

## Decyzja D8 — Zakres CSS componentów w Fazie 0

`input.css` ma >2000 linii komponentów obejmujących moduły spoza zakresu (faktury, kalendarz,
itd.). Fazowo portuję do `components.css`: (a) wszystko potrzebne dla Fazy 0 (buttony, formy,
sidebar, modal/confirm, toast, theme-switcher popover) + (b) wszystko potrzebne dla modułu
Klienci w Fazie 1 (`.refined-table`, `.stack-cards`, `.stat-strip`, `.filter-chip`, itd. —
1:1 z `clients/list.html`'s inline `<style>`, które i tak w większości już woła współdzielone
klasy z `input.css`). Reszta (np. `.calendar-*`, `.invoice-*`) zostaje w `input.css` nietknięta —
portowanie ich teraz byłoby pracą "na zapas" dla modułów, których jeszcze nie budujemy (Faza 2).

## Decyzja D9 — `--color-on-accent`: nowa (6.) rozbieżność DESIGN.md vs `input.css`, nieujęta w planie

Podczas portu tokenów (`tokens.css`) wykryto rozbieżność, której `plan.md` §0.1 **nie wymienia**
w swojej liście pięciu punktów: `input.css` ustawia `--color-on-accent: #ffffff` (białe inicjały
na złotym avatarze sidebar), a `DESIGN.md` §2.6 jawnie definiuje
`--color-on-accent: var(--color-ink)` (ciemny tekst na złocie). To realna zmiana wizualna
(kolor tekstu na gradiencie awatara/przycisku brand).

**Decyzja:** trzymam się `DESIGN.md` (ink, nie biały) — zgodnie z ustaleniem na starcie tej
rozmowy, że `DESIGN.md` jest źródłem prawdy dla nowego frontendu tam, gdzie różni się od
`input.css`. Dodatkowo ciemny tekst na `#c9a227` ma wyraźnie lepszy kontrast niż biały
(WCAG-bezpieczniejszy wybór), więc decyzja DESIGN.md wygląda na świadomą poprawkę, nie
przeoczenie. Odnotowane tutaj, bo nie było wprost w planie do zaakceptowania — flagowane do
wzrokowego review razem z resztą diffu tokenów (§0.1 rekomendacja).

## Decyzja D10 — `--sidebar-logo-filter`: brak przebarwienia logo per motyw

`DESIGN.md` §2.13 wymienia ten token, ale nie definiuje wartości ani mechanizmu — plan
(`phase-00` §0.2) mówi wprost "do zaprojektowania od zera". Dzisiejsze logo (`Logo-inline.webp`,
statyczny obrazek) nie ma żadnego istniejącego mechanizmu przebarwienia per-motyw do
odtworzenia. **Decyzja:** `--sidebar-logo-filter: none` we wszystkich 4 motywach — brak zmiany
wizualnej względem dzisiejszego stanu (logo zawsze wygląda tak samo, niezależnie od motywu).
Dobranie konkretnego CSS `filter` (hue-rotate/saturate) pod każdy motyw wymagałoby decyzji
projektowej (jak dokładnie ma wyglądać zielone/niebieskie/grafitowe logo) niemożliwej do
wyprowadzenia z samego kodu — pozostawione jako świadomy no-op, nie zgadywanie.

## Decyzja D11 — `.form-card` padding: kolejna (7.) rozbieżność DESIGN.md vs `input.css`

`input.css`'s `.form-card` ma `padding: 1.5rem`. `DESIGN.md` §5 jawnie mówi
"Card padding: `.form-card` → `1rem 1.125rem`". Trzymam się DESIGN.md (mniejszy padding) w
`components.css` — konsekwentnie z zasadą "DESIGN.md wygrywa przy konflikcie". Kolejny punkt do
wzrokowego review razem z resztą diffu.

## Decyzja D12 — Login: przycisk submit = `variant="brand"` (świadoma zmiana wobec dzisiejszego Jinja)

Dzisiejszy `templates/auth/login.html` używa zwykłego `.refined-btn-primary` (ink fill) na
przycisku logowania — `.refined-btn-brand` (złoty gradient) **nie istnieje jeszcze w ogóle** w
obecnym systemie. `DESIGN.md` §15.5 jawnie i celowo przypisuje `variant="brand"` dokładnie do
przycisku logowania ("the one place variant="brand" is used"). To nie jest rozbieżność do
rozstrzygnięcia — to nowa, zamierzona reguła DESIGN.md, więc `Login.tsx` używa `variant="brand"`
zgodnie ze specyfikacją, mimo że wygląda inaczej niż dzisiejszy Jinja-ekran logowania.

## Decyzja D13 — Auth-page CSS klasy (`.refined-title/-subtitle/-footer`, `.flash-message`,
`.back-link`, `.neutral-notice`, `.reset-link-*`) portowane z inline `<style>` w
`templates/auth/{login,forgot_password}.html` (nie z `input.css` — tam ich nie było, każda
strona auth miała własny, zduplikowany blok) do wspólnego `components.css`, tokenizowane 1:1
(wartości hex/rgba już i tak odwoływały się do `var(--color-*)` w większości, drobne literały
jak `rgba(155,44,44,0.08)` zostały bez zmian jako nietokenizowane odcienie, dokładnie jak w
źródle).

## Decyzja/Odkrycie D14 — sidebar Jinja ma DZIŚ realne rozjazdy `visible` vs. rzeczywisty route guard
(dokładnie pułapka opisana w DESIGN.md §13.5) — navConfig.ts używa REALNYCH stražy backendu

Podczas portu `navConfig.ts` prześledzono rzeczywisty dekorator KAŻDEJ trasy Flask stojącej za
każdym linkiem sidebaru (nie tylko warunek `{% if user_permissions.x %}` w `sidebar.html`) i
znaleziono **cztery istniejące już dziś rozjazdy** między tym, co sidebar pokazuje, a tym, co
backend faktycznie egzekwuje:

1. `main.history` ("Historia zmian") — sidebar pokazuje pod `user_permissions.reports`, ale
   `@main_bp.route('/history')` jest w rzeczywistości otagowane
   `@module_permission_required('invoices')`. Rola z dostępem do `reports`, ale bez `invoices`,
   widzi dziś martwy link (403 po kliknięciu).
2. `main.email_settings` ("Ustawienia" w sekcji System) — sidebar: `user_permissions.settings`;
   backend: `@module_permission_required('invoices')`. Ten sam wzorzec martwego linku.
3. `main.analytics_dashboard` / `main.kpi_matrix` / `main.income_dashboard` ("Analiza
   biznesowa" / "Wskaźniki biznesowe" w sekcji Finanse) — sidebar zagnieżdża je pod
   `user_permissions.invoices` (cała sekcja Finanse), ale backend wymaga
   `@module_permission_required('appointments')`. Rola typu `accountant` (ma `invoices`, nie ma
   `appointments` wg statycznego `MODULE_PERMISSIONS`) widzi dziś dwa martwe linki.
4. `users.users_list` / `roles.roles_list` — sidebar zagnieżdża oba pod
   `user_permissions.settings` (moduł), ale backend używa **literalnego sprawdzenia roli**:
   `@role_required('superuser','admin')` dla users, `@role_required('superuser')` samodzielnie
   dla roles. To dokładnie ten scenariusz z DESIGN.md §13.5: rola z modułowym grantem
   "settings" (niekoniecznie superuser/admin) widziałaby oba linki, mimo że backend odmówi.
5. `main.dashboard` ("Koszty") ma w ogóle **brak** dekoratora modułowego (tylko
   `@login_required`) — sidebar niepotrzebnie chowa go pod `user_permissions.invoices`; efekt
   odwrotny (link ukryty, choć backend by go wpuścił), mniej groźny niż 1-4, ale też
   niezgodność.

**Decyzja:** `navConfig.ts` (i odpowiadające `ProtectedRoute guard`) w tym repo React używają
**rzeczywistych dekoratorów** wypisanych powyżej, NIE kopiują 1:1 zagnieżdżenia z
`sidebar.html`. To jest dokładnie reguła z DESIGN.md §13.5 ("Always trace the real route guard,
not the nearest-sounding permission flag") zastosowana źródłowo. **Nie naprawiam** tych pięciu
bugów w `routes/main_routes.py`/`routes/users/routes.py`/`routes/roles/routes.py` — to
osobna, zasługująca na własną decyzję zmiana w Jinja-aplikacji, poza zakresem tego przebiegu
(dotyczy tylko strony Jinja, którą i tak zastępujemy); ale w NOWYM froncie React linki są od
razu poprawne względem prawdziwego backendu.

## Decyzja D15 — View Transitions API (DESIGN.md §10.3): pominięte w Fazie 0, tylko CSS fallback

DESIGN.md §10.3 opisuje cross-fade sidebar pill/`#main-content` przez natywne View Transitions
API jako "progressive enhancement" z jawnie wymienionym CSS-keyframe fallbackiem dla
przeglądarek bez wsparcia. `react-router-dom` w wersji przypiętej tu (^6.26) ma niepewne/
niestabilne wsparcie dla propa `viewTransition` na `<NavLink>`/`<Link>` (dodane dopiero w
późniejszych 6.x/7.x, czasem pod prefiksem `unstable_`) — użycie go groziłoby błędem builda przy
niedopasowanej wersji. **Decyzja:** Faza 0 NIE włącza `viewTransition` na routerze; poleganie na
już istniejącej globalnej regule `transition` (base.css, §10.1) dla `background-color`/
`box-shadow` daje wystarczająco płynne domyślne zachowanie aktywnej pigułki linku — to i tak jest
dokładnie "CSS-keyframe fallback", więc kryterium checklisty Fazy 0 (§0.8) nie wspomina View
Transitions wprost, a §19 pre-ship checklist też tego nie wymaga. Prawdziwe API Widoku Przejść
można dołączyć w późniejszej fazie, gdy dokładna wersja `react-router-dom` i jej flaga zostaną
świadomie ustalone.

## Weryfikacja automatyczna — Faza 0 (backend + tooling, przed Fazą 1)

- `pip install -r requirements-dev.txt` + `python -m pytest tests/ -q` → **657 passed**, 0
  failed. Brak dedykowanego pliku testów dla `routes/auth/routes.py` (potwierdzone
  `grep -rli auth tests/*.py` → tylko `conftest.py`, bez testów auth), więc formalnie
  "uruchom testy auth" nie miało czego uruchomić — ale pełny `app`/`client` fixture z
  `conftest.py` tworzy cały `Flask app` (importuje i rejestruje wszystkie blueprinty, w tym
  `auth_bp`), więc zielony przebieg całego pakietu pośrednio potwierdza brak błędu
  składni/importu w zmodyfikowanym pliku.
- `frontend/`: `npm install` (258 pakietów, 0 błędów krytycznych — 4 npm audit vulnerabilities,
  nie badane, standardowe dla świeżego scaffoldu) + `npm run build` (`tsc -b && vite build`) →
  **kompiluje się poprawnie i zatrzymuje się dokładnie na 3 brakujących modułach
  `./pages/clients/{ClientsListPage,ClientFormPage,ClientDetailPage}`** — czyli cały szkielet
  Fazy 0 (tokeny, tsconfig, vite config, wszystkie komponenty layoutu/auth/feedback) jest
  składniowo i typowo poprawny; jedyny błąd to brakujące pliki Fazy 1, które budowane są w
  następnym kroku tego przebiegu.

---

## Faza 1 — Pilot: Klienci

Przeczytano w całości (przed pisaniem kodu, zgodnie z §1.4 planu):
`templates/clients/{list,create,edit,view}.html` (w tym cały inline `<script>` każdego —
`sparklineSvg`/`trendDirection`/sortowanie/filtrowanie/duplicate-check), `routes/api_routes.py`
sekcja klientów (linie 2549-3084, wszystkie 13 endpointów), `routes/client_preference_routes.py`,
`routes/appointment_routes.py`'s `get_client_appointments`, `routes/employee_service_routes.py`
(cross-lookup usługi-pracownicy dla formularza preferencji).

### Decyzja D16 — Sukces tworzenia klienta: toast + natychmiastowa nawigacja (nie blokujący modal)

Oryginalny `create.html` po sukcesie pokazywał `Modals.alert({title:'Sukces', ...,
onClose: () => window.location.href='/clients'})` — modal wymagający kliknięcia OK przed
przejściem dalej. DESIGN.md nie definiuje generycznego "alert" jako osobnego prymitywu (tylko
`useConfirm` dla akcji konsekwentnych i `useToast` dla powiadomień, §8) i explicite zakazuje
natywnego `alert()`. **Decyzja:** `ClientFormPage` (create) używa `toast.success(...)` +
natychmiastowej `navigate('/klienci')` zamiast blokującego modala-potwierdzenia sukcesu — mniej
inwazyjne, spójne z resztą systemu feedbacku, funkcjonalnie równoważne. Nieopisane wprost w
checkliście akceptacji §1.5 ("te same komunikaty błędów" mówi o BŁĘDACH, nie o komunikacie
sukcesu), więc traktuję to jako świadomą, drobną poprawkę UX w duchu nowego systemu, nie regresję.

### Decyzja D17 — Duplicate-check: brak `.input-warn`/`.input-danger` tinta na polu Imię/Nazwisko

Oryginalny `create.html`/`edit.html` przebarwia OBA pola (imię, nazwisko) na bursztynowo/czerwono
przy wykryciu duplikatu nazwiska (`inputs.forEach(i => i.classList.toggle(...))` na `[firstEl,
lastEl]`). Zaimplementowano to dla pola **telefon** (jedno pole, przez nowy `inputClassName` prop
na `TextField` — rozszerzenie kontraktu prymitywu, patrz `components/ui/form.tsx`), ale
**pominięto** dla pary imię/nazwisko, bo `TextField` renderuje jedno pole na wywołanie i nie ma
naturalnego miejsca na "podziel klasę warn między dwa niezależne komponenty" bez dalszego
komplikowania kontraktu. Ostrzeżenie tekstowe (`DupHint`) pod polami nadal się pojawia — sama
informacja nie ginie, tylko dodatkowy wizualny akcent na samych inputach. Drobne, świadome
uproszczenie; do rozważenia w code review czy warto dociągnąć.

### Decyzja D18 — Appointment-history status badge: tokeny `--color-status-*` zamiast literałów rgba z oryginału

`view.html`'s inline JS miał własne `STATUS_BG = {scheduled: 'rgba(37,99,235,0.08)', ...}` —
hardkodowane, NIE korzystające z tokenów `--color-status-*-bg`, które już istnieją w
`DESIGN.md` §2.9 z dokładnie tymi samymi kolorami bazowymi. `ClientDetailPage.tsx` używa
tokenów (`var(--color-status-scheduled-bg)` itd.) zamiast kopiować hardkodowane RGBA z
oryginału — to bezpośrednio serwuje zasadę DESIGN.md "nigdy nie hardkoduj hexa/rgba, gdy
istnieje token" (§16 Must), bez żadnej zauważalnej różnicy wizualnej (te same wartości bazowe).
Status `no_show` celowo renderuje się BEZ tła (`background: transparent`) — DESIGN.md §2.9 opisuje
`--color-status-no-show` jako "neutral gray, no bg — rare/muted state", więc brak dedykowanego
tokenu `-bg` dla tego stanu jest zamierzony, nie przeoczeniem do naprawienia.

### Weryfikacja automatyczna — Faza 1

- `npm run build` (`tsc -b && vite build`) → **kompiluje się bez błędów**, 70 modułów,
  bundle 298 KB / gzip 96 KB. Napotkane i naprawione po drodze: (a) `JsonBody` type w
  `lib/api/client.ts` był za wąski dla `ClientFormValues` (brak index signature) — poluzowano
  `post`/`put` do `body?: unknown`; (b) `as const` na wyrażeniu warunkowym (nie na literale) w
  `ClientsListPage`'s `sortIndicator` — TS1355, naprawione przez jawną adnotację typu zwracanego
  zamiast `as const`.
- `npm run lint` (eslint + react-hooks plugin, dodano `.eslintrc.cjs` — scaffold Vite nie miał
  configu eslinta, tylko oxlint, usunięty) → **0 errors, 1 warning** (nieszkodliwy
  `react-hooks/exhaustive-deps` w `useFocusTrap.ts` o odczycie `ref.current` w cleanup —
  zamierzone zachowanie: chcemy NAJŚWIEŻSZĄ wartość refa w momencie zamknięcia, nie zamrożoną).
- Po code-review własnym (pre-ship checklist DESIGN.md §19): znaleziono i naprawiono 2 miejsca
  z hardkodowanym hexem zamiast tokenu (`ClientsListPage`'s avatar-ring `#9b2c2c`/`#c9a227` →
  `var(--color-error)`/`var(--color-accent)`; `TrendSparkline`'s `down` `#ef4444` →
  `var(--color-chart-red)`, dokładne dopasowanie istniejącego tokenu) oraz 1 błąd
  UTC-offset-by-one (`ClientDetailPage` używał `new Date(iso-string)` zamiast bezpiecznego
  lokalnego parsera `formatDate()` z `lib/format.ts` dla `date_of_birth`/`first_visit_date`/
  `last_visit_date` — naprawione przed commitem, nie zostawione jako known issue).
- Backend: **bez zmian** w tej fazie (plan §1.2 potwierdzone: "Nic strukturalnego po stronie
  API" — wszystkie 13 endpointów klientów + preferencje + appointments-by-client już istniały
  i już są czystym JSON, bez potrzeby `X-Requested-With` rozgałęzienia). `pytest tests/ -q`
  nie uruchamiany ponownie w tej fazie — brak zmian w `routes/`/`repositories/` do
  zweryfikowania.

---

## Faza 2 — Rollout pozostałych modułów

Kolejność (za zgodą użytkownika 2026-08-17): **bez** Booking/Landing/Mobile (poza zakresem, patrz
`plan.md` §3) — tylko wewnętrzna apka. Tryb: ciągły, bez przystanków między modułami (jak Faza 0+1),
w kolejności rosnącego ryzyka — najpierw moduły "Kompletna API"/bez potrzeby audytu
(`module-inventory.md`): Dashboard → Sprzedawcy → Usługi+kategorie → Pracownicy → Faktury, dopiero
potem moduły oznaczone "Wymaga audytu".

### Odkrycie D-Sec2 — luka bezpieczeństwa naprawiona w `routes/api_routes.py` (Sprzedawcy + email/historia/PDF)

Po znalezieniu D-Sec1 (Dashboard) przeskanowano całe `routes/api_routes.py` pod kątem brakującego
`@login_required` — znaleziono i naprawiono (dekoratorem `@login_required` +
`@module_permission_required('invoices')`, wzorem sąsiadujących endpointów w tym samym pliku)
**16 kolejnych** endpointów bez ŻADNEGO auth:
- 11× `/api/sellers/*` (`get_seller`, `update_seller`, `bulk_update_seller_invoices`,
  `get_seller_conflicts`, `delete_seller` **[DELETE bez auth — najpoważniejsze: dowolna osoba mogła
  skasować sprzedawcę i kaskadowo wszystkie jego faktury]**, `get_seller_invoices`, `sync_sellers`,
  `add_missing_seller`, `fix_discrepancy`, `sync_seller_invoice_counts`, `check_seller_duplicate`).
- `/api/email/test`, `/api/email/folders`, `/api/email/settings` (GET+POST) — **GET zwracał hasło
  IMAP w czystym JSON bez logowania; POST pozwalał nadpisać ustawienia poczty (przejęcie całego
  pipeline'u importu faktur) komukolwiek.**
- `/api/history/details` (dopasowano do sąsiada `get_history` — tylko `@login_required`, bez
  modułu, bo taki jest już ustalony wzorzec tego zasobu).
- `/api/pdf/<invoice_id>` — dowolna osoba mogła pobrać PDF dowolnej faktury po samym ID.

`pytest tests/ -q` → 657 passed po wszystkich zmianach, bez regresji.

**Odkrycie D-Sec3 (2026-08-17) — SPRAWDZONE, FAŁSZYWY ALARM, skorygowane:** pierwotny pełny skan
`routes/*.py` (regex po dosłownym stringu `login_required` w liniach dekoratorów) wykrył pozornie
**23 endpointy bez auth** w `routes/absence_routes.py` (15) i `routes/absence_balance_routes.py` (8).
**Po przeczytaniu obu plików w całości (przy starcie audytu Pracowników) okazało się, że to artefakt
zbyt naiwnego regexu**, nie realna luka: obie strażnice używane w tych plikach —
`@absence_management_required` (wszystkie 15+niektóre z 8) i `@module_permission_required('absences')`
(4 endpointy kategorii) — same sprawdzają `current_user.is_authenticated` wewnątrz funkcji
(`config/auth_config.py:99` i `:209`), dokładnie tak samo jak `@login_required` robi to przez
Flask-Login. Regex szukał tylko podciągu `"login_required"` w tekście dekoratora — `"module_permission_required"`
i `"absence_management_required"` go nie zawierają, więc wpadły w sito jako "brak auth", mimo że nim
nie są. Przeczytano każdą z 23 flagowanych funkcji ręcznie (`absence_routes.py` linie 124-599,
`absence_balance_routes.py` linie 35-274) — **wszystkie właściwie zabezpieczone, część dodatkowo
zawęża się w ciele funkcji do `role == 'superuser'`** dla operacji `hard_delete_*`/`cancel_approved`
(świadome, udokumentowane w komentarzach tych funkcji). **Brak akcji do podjęcia.** Wniosek na
przyszłość: przy kolejnych skanach regexowych sprawdzać też niestandardowe nazwy decoratorów
(`grep -n "^def.*_required\|^def.*_permission"` w `config/auth_config.py` najpierw, potem dopiero
przeszukiwać trasy pod kątem WSZYSTKICH tych nazw, nie tylko `login_required`).

### Moduł: Dashboard/Pulpit

**Odkrycie D-Sec1 (przed portem, poza zakresem Reacta) — luka bezpieczeństwa naprawiona:** pięć
endpointów `/api/dashboard/*` (`recent-invoices`, `upcoming-payments`, `overdue-payments`,
`top-sellers`, `monthly-totals`, `routes/api_routes.py:937-1093`) nie miały ŻADNEGO dekoratora
`@login_required`/`@module_permission_required` — potwierdzone brakiem `before_request` na `api_bp`
i brakiem globalnego auth w `app.py`. Realny skutek: dowolna osoba bez logowania mogła pobrać
prawdziwe dane finansowe (nazwy/NIP-y dostawców, kwoty faktur, 12-miesięczny przychód). Za zgodą
użytkownika naprawione **przed** kontynuacją portu — dodano `@login_required` +
`@module_permission_required('invoices')` do wszystkich pięciu, wzorem sąsiadującego
`get_statistics` (`:917-920`), który już miał oba dekoratory. `pytest tests/ -q` → 657 passed po
zmianie (bez regresji). To NIE jest zmiana wprowadzona przez migrację — istniała wcześniej,
niezależnie od Reacta; odkryta przy czytaniu tego samego pliku pod port Dashboardu.

**Decyzja D19 — Chart.js jako zależność npm zamiast CDN `<script>`:** oryginał ładuje Chart.js przez
`<script src="cdn.jsdelivr.net/...">` w `extra_head`. W React zainstalowano `chart.js` jako zwykłą
zależność (`frontend/package.json`) — samodzielny bundle SPA, bez globalnego skryptu/wyścigu
ładowania, wersjonowane tak jak reszta zależności. Ta sama biblioteka, ten sam wygląd wykresu
(słupkowy, tooltip, formatowanie osi Y w K/M), inny mechanizm ładowania — kolory słupków/tooltipa
przez `var(--color-ink)`/`var(--color-accent)` zamiast oryginalnych hardkodowanych
`rgba(26,26,26,…)`/złotego literału (DESIGN.md §16, ta sama zasada co Decyzja D18 w Fazie 1).

**Decyzja D20 — `parseLocalDate` z `lib/format.ts` wyeksportowany i użyty do liczenia "dni do
terminu"/"dni po terminie":** oryginalny `dashboard/index.html` liczy to przez
`new Date(invoice.payment_due_date)` bezpośrednio — dokładnie ten sam błąd UTC-off-by-one, który
Decyzja D18 (Faza 1) już raz naprawiła dla `ClientDetailPage`. Nie powielono go tu — `DashboardPage`
używa tego samego bezpiecznego lokalnego parsera, teraz wyeksportowanego z `format.ts` zamiast
prywatnego dla modułu.

**Decyzja D21 — linki do konkretnej faktury (`/invoice/:id/edit`) jako zwykłe `<a href>`, nie
`<Link>`:** moduł Faktury jeszcze nie istnieje w React (`/faktury` to nadal `<ComingSoonPage>`).
Zamiast linkować do martwego placeholdera z utratą ID faktury, linki "Ostatnie faktury"/"Przetermi-
nowane"/"Nadchodzące płatności" wychodzą realną nawigacją przeglądarki do wciąż żywej strony Jinja
(`main.edit_invoice`) — działa dziś, bo oba stacki koegzystują przez cały big-bang (`plan.md` §1).
Link zbiorczy "Zobacz wszystkie →" (bez konkretnego ID) idzie przez `<Link to="/faktury">` (SPA,
ląduje na `ComingSoonPage`, zgodnie z D7).

**Nieprzeportowane świadomie:** nasłuch `document.addEventListener('invoiceCreated'/'invoiceUpdated'
/'invoiceDeleted', refreshDashboard)` — nic w SPA jeszcze nie emituje tych eventów (moduł Faktury
nie zbudowany). Do rozważenia przy budowie Faktur: cross-page refresh po mutacji (custom event jak
dziś, albo lepszy mechanizm współdzielonego cache'u).

**Layout — świadome uproszczenie:** oryginał ma `.refined-page{height:100%;overflow:hidden}` +
panele scrollowane wewnętrznie (dashboard = jeden ekran, bez scrolla strony). Shared `AppShell`
z Fazy 0 nie ma odpowiednika `#main-content` o zablokowanej wysokości (żadna inna strona, w tym
Klienci, tego nie zakłada) — dopasowywanie się do tego jednego niestandardowego layoutu
wymagałoby zmiany generycznego shellu. Zamiast tego: strona scrolluje normalnie (jak Klienci),
a panele list mają `max-height` z wewnętrznym scrollem, żeby nie rosły w nieskończoność z danymi.

**Weryfikacja:** `npm run build` → kompiluje się bez błędów (78 modułów, bundle 453 KB / gzip
149 KB — wzrost względem Fazy 1 głównie przez `chart.js`). `npm run lint` → 0 errors, ten sam
1 nieszkodliwy warning z Fazy 1 (`useFocusTrap.ts`). Backend: `pytest tests/ -q` → 657 passed
(po dodaniu dekoratorów bezpieczeństwa). **Ręczna weryfikacja wizualna/funkcjonalna — czeka**
(zakaz samodzielnego testowania GUI w tym przebiegu, jak w Fazie 1).

### Moduł: Sprzedawcy (trzy pod-funkcje — patrz korekta złożoności w module-inventory.md)

Zbudowane: `SellersListPage` (lista/CRUD/sort/search/stats-bar), `SellerSyncResults` (workflow
synchronizacji — niezgodności nazw + brakujący sprzedawcy, z heurystyką rekomendacji ported 1:1 z
`analyzeDiscrepancy()`), `SellerPasswordsPanel` (modal, CRUD haseł PDF wszystkich sprzedawców),
`SellerFormPage` (create/edit, jeden komponent jak `ClientFormPage` z Fazy 1 — z live NIP-duplicate-
check debounced 500ms, name-duplicate-check on-blur, sekcją hasła PDF inline dla edytowanego
sprzedawcy, tabelą powiązanych faktur, przyciskiem "Propaguj zmiany").

**Decyzja D22 — nowy generyczny `components/ui/Modal.tsx`:** DESIGN.md §8.3 mówi wprost, że
`Modals.show()` nie ma gotowego 1:1 odpowiednika — każdy przypadek osobno. Konflikt NIP (3 przyciski:
Anuluj / Użyj istniejącego / Zaktualizuj nazwę) nie mieści się w binarnym `useConfirm()`, więc
powstał pierwszy współdzielony prymityw `Modal` (`.modal-*` klasy, też z Fazy 0/`ConfirmProvider`) —
używany przez `SellerPasswordsPanel` i modal konfliktu NIP w `SellerFormPage`. Pozostałe dwa modale
oryginału (konflikt nazwy, prompt propagacji) okazały się jednak binarne — te poszły przez zwykły
`useConfirm()`, nie przez nowy prymityw (nie każdy `Modals.show()` z oryginału wymagał custom
komponentu, tylko ten jeden naprawdę 3-drożny).

**Decyzja D23 — URL-e po polsku:** `/sprzedawcy/nowy`, `/sprzedawcy/:id/edytuj` (nie kopia starych
`/seller/create`, `/seller/<id>/edit`) — wzorem `/klienci/nowy`/`/klienci/:id/edytuj` z Fazy 1,
konsekwentnie w całym React froncie.

**Nieprzeportowane świadomie:** `GET /api/sellers/conflicts` — nigdzie nie konsumowany w oryginalnym
JS (`list_refined.html`/`create.js`/`edit.js`), więc brak odpowiadającego UI w Reakcie też (owinięty
w `sellersApi.conflicts()` dla kompletności, niewywoływany znikąd — 1:1 z dzisiejszym stanem, nie
regresja). Podobnie `GET /api/sellers/<id>/invoices` — osobny endpoint nieużywany w oryginale (dane
o fakturach przychodzą już zagnieżdżone w `GET /api/sellers/<id>`).

**Weryfikacja:** `npm run build`/`lint` → 0 errors (1 nieszkodliwy warning z Fazy 1, bez zmian).
Backend: `pytest tests/ -q` → 657 passed po wszystkich zmianach dekoratorów (D-Sec2).

### Moduł: Usługi + kategorie (4 pod-strony — druga z rzędu korekta złożoności "Średnia"→"Wysoka")

Zbudowane: `ServicesListPage` (lista/CRUD, filtrowanie **serwerowe** — search/type/active_only
faktycznie trafiają do `GET /api/services`, inaczej niż u Sprzedawców gdzie oryginał filtrował
tylko klient-side), `ServiceFormPage` (create/edit, typ usługi main/addon przełącza
widoczność/wymagalność kategorii, pole "powód zmiany ceny" pokazuje się tylko gdy
`hasModuleAccess('service_prices')` I cena faktycznie zmieniona względem wartości przy
załadowaniu), `ServiceDetailPage` (historia cen w `<details>` z Chart.js sparkline — rysowany
dopiero po rozwinięciu, bo canvas w zwiniętym `<details>` ma zerowy rozmiar — plus zarządzanie
kompatybilnymi mikrousługami), `ServiceCategoriesPage` (jedyne miejsce w całej migracji z edycją
WIERSZOWĄ inline zamiast osobnej strony — ported 1:1, nie "poprawione" na wzorzec formularza).

**Wzorzec potwierdzony:** to DRUGI moduł z rzędu (po Sprzedawcach), gdzie etykieta złożoności z
`module-inventory.md` (pochodząca z samego audytu liczby `jsonify`) okazała się zaniżona po
realnym przeczytaniu kodu — tu dodatkowo odkryto whole osobny plik `routes/service_addon_routes.py`
(kompatybilność usługa-główna↔mikrousługa), w ogóle niewymieniony w `plan.md` §0. **Wniosek do
zanotowania na przyszłość:** przy kolejnych modułach z etykietą "Średnia"/"Kompletna" z samej
tabeli audytu — traktować to jako punkt startowy, nie jako sufit złożoności; zawsze sprawdzić czy
istnieje osobny plik tras dla tego modułu poza oczywistym (`grep -rl "'/<moduł>" routes/*.py`).

**Decyzja D24 — `service_addon_routes.py` sprawdzony osobno pod kątem D-Sec2-podobnej luki:**
wszystkie 5 endpointów już miało `@login_required` + `@module_permission_required('services')` —
brak nowej luki bezpieczeństwa w tym pliku (w przeciwieństwie do Dashboard/Sprzedawcy).

**Decyzja D25 — 3-drożny modal usuwania kategorii przez `Modal`, nie `useConfirm()`:** dokładnie
ten sam wzorzec co Decyzja D22 (konflikt NIP u Sprzedawców) — "Anuluj / Usuń tylko kategorię / Usuń
z usługami" nie mieści się w binarnym confirm.

**Weryfikacja:** `npm run build`/`lint` → 0 errors (1 nieszkodliwy warning z Fazy 1, bez zmian;
bundle 542 KB / gzip 172 KB — Vite ostrzega o rozmiarze chunku, do rozważenia code-splitting w
późniejszej fazie, nieblokujące teraz). Backend: bez zmian w tym module (wszystkie endpointy już
poprawnie zabezpieczone) — `pytest` nie uruchamiany ponownie, brak zmian w `routes/`.

### Moduł: Pracownicy — audyt wstępny, budowa NIE rozpoczęta

Zeskanowano trasy i strony przed budową (żeby następna sesja nie zaczynała od zera):

**Backend — 13 endpointów w `routes/api_routes.py:3780-4470`, wszystkie już poprawnie
zabezpieczone** (`@login_required` + odpowiedni `@module_permission_required`, potwierdzone pełnym
skanem pliku — brak luki typu D-Sec1/D-Sec2 tutaj):
`GET/POST /api/employees`, `GET/PUT/DELETE /api/employees/<id>`,
`GET/PUT /api/employees/<id>/mobile-pin` + `POST .../mobile-pin/reset`,
`DELETE /api/employees/<id>/permanent` (hard delete), `GET /api/employees/statistics`,
`GET /api/employees/positions`, `POST /api/employees/bulk-update-services`,
`POST /api/employees/<id>/direct-reports`.

**Frontend — 4 strony Jinja, 3152 linii łącznie:** `templates/employees/list.html` (791 — lista/
CRUD/staty/filtr stanowisko+status, bulk "Aktualizuj preferencje"), `create.html` (468),
`edit.html` (707), `view.html` (1186 — **nieprzeczytany w szczegółach, prawdopodobnie zawiera
mobile-pin reset UI, macierz bulk-services, i sekcję direct-reports** — dokładnie ten sam wzorzec
co `clients/view.html` w Fazie 1: zbyt duży, żeby zgadywać strukturę z nazwy, pierwszy krok
następnej sesji to pełne przeczytanie). Osobny podkatalog `templates/employees/formy_zatrudnienia/`
(zarządzanie formami zatrudnienia) — **w ogóle nieprzeczytany, nawet pobieżnie**.

**Rekomendowana kolejność budowy (następna sesja):** 1) przeczytać `view.html` w całości (wzorem
Fazy 1 §1.4), 2) `EmployeesListPage` (najbliższy wzorcowi `ServicesListPage`), 3) `EmployeeFormPage`
create/edit, 4) `EmployeeDetailPage` z mobile-pin/bulk-services/direct-reports jako pod-sekcje
(prawdopodobnie osobne komponenty, wzorem `PdfPasswordSection`/`SellerSyncResults`), 5) osobny
`FormyZatrudnieniaPage` dopiero po przeczytaniu jego szablonów.

**Świadoma decyzja o zatrzymaniu:** to NIE jest "zabrakło czasu" — to moduł porównywalny objętością
do Sprzedawców+Usług razem wziętych, a obie te korekty złożoności ("Średnia"→"Wysoka") pokazały, że
budowanie bez pełnego przeczytania kodu prowadzi do przeoczeń. `plan.md` §4 explicite ostrzega przed
szacowaniem "na sztywno" bez audytu — to samo dotyczy tempa budowy: lepiej zamknąć pełny, przetesto-
wany moduł niż zacząć piąty i zostawić go w połowie.

### ⚠️ Konflikt równoległej sesji — odkryty 2026-08-17 ~23:47, w trakcie budowy Pracowników

Podczas budowy modułu Pracownicy (ta sama sesja, po wznowieniu z `/loop`/kontynuacji) okazało się,
że **druga, żywa sesja Claude Code** (potwierdzone: wiele procesów `claude.exe` w `tasklist`) edytuje
**dokładnie te same pliki, dokładnie ten sam moduł, w tym samym czasie** — `frontend/src/types/
employee.ts`, `frontend/src/lib/api/employees.ts`, `frontend/src/lib/api/employeeServices.ts`,
`frontend/src/pages/employees/EmployeesListPage.tsx` i **`routes/api_routes.py`** (ten sam plik
backendu z poprawkami D-Sec1/D-Sec2/D-Sec4 z tej sesji). Obie sesje niezależnie doszły do tego
samego wniosku ("czas na Pracowników") i zaczęły pisać własne, niekompatybilne wersje (inne nazwy
typów — `EmployeeListItem` vs `EmployeeListRow` — inny adres endpointu dla listy użytkowników —
`/api/employees/lookups/active-users` vs `/api/employees/user-options` — inna decyzja zakresu:
druga sesja **świadomie odłożyła zakładki "Analizy i wyniki"**, ta sesja szła w pełną budowę).

**Zweryfikowano przed przerwaniem:** żadna z wcześniejszych poprawek tej sesji (D-Sec1 Dashboard,
D-Sec2 Sprzedawcy/email/PDF/history, D-Sec4 skills/specializations) **nie została nadpisana** —
obie sesje edytowały różne fragmenty tego samego dużego pliku bez destrukcyjnego nakładania się,
na razie. Usunięto WYŁĄCZNIE własny duplikat endpointu tej sesji
(`/employees/lookups/active-users`, martwy kod względem tego co realnie zostało na dysku) — nie
ruszono niczego z drugiej sesji.

**Pozostawione bez zmian, niezweryfikowane — wymaga ręcznej decyzji użytkownika:**
`frontend/src/lib/api/absenceBalances.ts`, `frontend/src/lib/api/formyZatrudnienia.ts` (pliki tej
sesji, prawdopodobnie osierocone — druga sesja zbudowała odpowiedniki jako metody wprost na
`employeesApi`, nie osobne pliki) oraz cały pierwotny `frontend/src/pages/employees/
EmployeesListPage.tsx` tej sesji (nadpisany przez drugą sesję, zanim zdążył trafić do
weryfikacji buildem).

**Rekomendacja:** nie kontynuować budowy Pracowników w tej sesji — druga sesja jest w tej chwili
dalej (ma już `Modal`-based potwierdzenie trwałego usunięcia, `sessionStorage` z filtrami wzorem
`ClientsListPage`, spójny stack typów). Użytkownik powinien: (1) sprawdzić stan drugiej sesji,
(2) pozwolić jej dokończyć moduł, (3) usunąć osierocone pliki tej sesji wymienione wyżej,
(4) przelecieć `npm run build`/`lint` + `pytest` po zakończeniu, żeby złapać cokolwiek co obie
sesje zostawiły w niespójnym stanie.

### Moduł: Pracownicy — konflikt rozwiązany, budowa dokończona (2026-08-18)

Po wznowieniu tej sesji (przerwanej w trakcie budowy `EmployeeDetailPage`) druga, równoległa sesja
już nie żyła — na dysku pozostał wyłącznie spójny stan zgodny z tym, co ta sesja od początku
budowała (`EmployeeListRow`, endpoint `/api/employees/user-options`, `EmployeesListPage.tsx` z
`Modal`-based potwierdzeniem trwałego usunięcia i `sessionStorage` filtrów wzorem
`ClientsListPage`) — czyli dokładnie rekomendacja #2 z sekcji wyżej ("pozwolić [drugiej sesji]
dokończyć moduł") zrealizowała się sama. Wykonano rekomendację #3: usunięto
`frontend/src/lib/api/absenceBalances.ts` (osierocony duplikat — `employeesApi.getBalances`/
`getBalanceAdjustments` to jedyna realnie używana ścieżka; plik odwoływał się do nieistniejących już
nazw typów `AbsenceAdjustment`/`AbsenceBalance` i blokował `tsc -b`). `formyZatrudnienia.ts`
**nie był** osierocony — aktywnie używany przez `EmployeeFormPage`/`EmployeeDetailPage`, zostawiony
bez zmian.

**Backend — 2 nowe endpointy** (`routes/api_routes.py`), oba `@login_required` +
`@module_permission_required('employees')`:
- `GET /api/employees/<id>/direct-reports` — dane do pickera "Podwładni" na stronie edycji (inni
  aktywni pracownicy + aktualni podwładni + przełożeni danego pracownika, do wykrycia konfliktu
  przełożony↔podwładny w UI).
- `GET /api/employees/user-options` — lista aktywnych użytkowników do dropdowna "Konto użytkownika".
  Celowo NOWY, wąsko zakresowy endpoint zamiast ponownego użycia `/system/users/api`
  (`routes/users/routes.py`), który wymaga `@role_required('superuser', 'admin')` — formularz
  pracownika jest dostępny każdemu z uprawnieniem zapisu w module `employees`; użycie
  nadmiernie uprzywilejowanego endpointu byłoby odwrotnością D-Sec1/D-Sec2 (za DUŻO uprawnień
  zamiast za mało).

Weryfikacja backendu: `python -c "import ast; ast.parse(...)"` na obu endpointach (SYNTAX_OK) +
pełny `pytest tests/ -q` → **657 passed**, zero regresji.

**Frontend — zbudowane strony:**
- `EmployeesListPage` — lista/CRUD, staty (4 karty przez `Icon` glyphs), filtr stanowisko
  (serwerowy) + status (klient-side) + wyszukiwanie, sortowanie 5 kolumn w tym "Bilans urlopu"
  (dociągnięty osobnym fetchem `/api/absence-balances/summary` i zmergowany po id — dokładnie jak
  oryginał, nie zagnieżdżony w odpowiedzi `/api/employees`), trwałe usunięcie (superuser-only) przez
  `Modal` z ostrzeżeniem o kaskadowym skasowaniu (nieobecności/bilanse) i osobnym ostrzeżeniem gdy
  pracownik ma powiązane konto użytkownika.
- `EmployeeFormPage` (create/edit, jeden komponent) — asymetria oryginału zachowana świadomie:
  umiejętności/specjalizacje ustawiane TYLKO przy tworzeniu (`create.html` je ma, `edit.html` —
  nie), harmonogram/PIN mobilny/podwładni — tylko w edit (PIN i podwładni nie mają sensu przed
  utworzeniem rekordu). Custom multi-select dropdown dla "Podwładni" z blokadą konfliktu
  przełożony↔podwładny (`disabled` na opcji + etykieta "konflikt"). Zmiana PIN-u przez nowy `Modal`.
- `EmployeeDetailPage` (dokończone w tej sesji) — dane osobowe, wynagrodzenie, bilanse nieobecności
  (paski postępu + "Historia korekt" doładowywana leniwie dopiero po pierwszym rozwinięciu, nie przy
  starcie strony — 1:1 z oryginalnym `toggleAdjHistory()`), umiejętności/specjalizacje (chipy),
  harmonogram pracy (siatka dni roboczych/wolnych), przypisane usługi (inline formularz dodawania —
  pobiera WSZYSTKIE aktywne usługi i odfiltrowuje już przypisane po stronie klienta, jak oryginał;
  usuwanie przez `useConfirm()`), notatki, akcje (edytuj/powrót/dezaktywuj). Zakładki "Analizy i
  wyniki" (5 zakładek, 8+ wykresów Chart.js, heatmapa godzin szczytowych, radar umiejętności) —
  **ŚWIADOMIE odłożone**, renderowany jest tylko placeholder (`.analytics-deferred-note`) — ten
  zakres wymaga najpierw przeczytania nieprzeczytanego `static/js/employees/analytics.js` (500+
  linii), porównywalny objętościowo do osobno śledzonego w `module-inventory.md` modułu "Analityka".

**Decyzja D26 — `forma_zatrudnienia_id → nazwa` rozwiązywane po stronie klienta:**
`GET /api/employees/<id>` (użyty przez `EmployeeDetailPage`) nie dołącza nazwy formy zatrudnienia
(w przeciwieństwie do oryginalnej trasy Jinja, która przekazywała gotowy `forma_nazwa` z JOIN-a) —
zamiast dodawać kolejny endpoint, `EmployeeDetailPage` woła ten sam `formyZatrudnieniaApi.listFull()`
co formularz edycji i wyszukuje po `id` po stronie klienta. Dane są już i tak pobierane gdziekolwiek
edytuje się pracownika — trzeci fetch dla samego stringa byłby przerostem formy nad treścią.

**Decyzja D27 — tabela przypisanych usług: globalna `.refined-table`, nie bespoke `.service-table`:**
oryginalny `view.html` definiował własną klasę `.service-table` w lokalnym `<style>` (w Jinja każda
strona i tak ładuje tylko swój własny blok stylów, więc kolizje nazw nie miały znaczenia). W SPA
style wszystkich modułów trafiają do jednego bundla — `EmployeesListPage.css` już celowo prefiksuje
własne klasy (`emp-field-grid`, nie `field-grid`) żeby uniknąć kolizji z identycznie nazwanymi
regułami w `ServicesListPage.css`. Zamiast dopisywać TRZECI prawie identyczny zestaw reguł tabeli,
użyto istniejącej globalnej `.refined-table` (te same wartości co `.service-table` co do piksela,
różnica tylko w paddingu 0.75rem/1rem vs 0.625rem/0.75rem — nieodróżnialna wizualnie) — spójnie z
tym, jak `ServiceDetailPage` już wcześniej potraktował swoją tabelę historii cen.

**Uzupełnienie CSS:** bazowe `.emp-field-label`/`.emp-field-value` dopisane do
`EmployeesListPage.css` — poprzednie wznowienie zdążyło dodać tylko warianty (`emp-field-grid*`,
`.emp-field-value.highlight`) zanim połączenie się urwało; bez bazowych reguł tekst renderowałby się
bez żadnego stylu.

**Router:** `/pracownicy`, `/pracownicy/nowy`, `/pracownicy/:id/edytuj`, `/pracownicy/:id` podpięte
pod `requireModule="employees"` (zastąpiły `ComingSoonPage`); `/formy-zatrudnienia` zostaje
`ComingSoonPage` do następnego kroku.

**Weryfikacja:** `npm run build` → 0 errors (bundle 586 KB / gzip 183 KB — to samo ostrzeżenie o
rozmiarze chunku co w poprzednich modułach, nieblokujące). `npm run lint` → 0 errors, 1 nieszkodliwy
pre-existing warning (`useFocusTrap.ts`, niezwiązany z tym modułem, bez zmian). Backend: `pytest`
nie uruchamiany ponownie w tym kroku — bez nowych zmian w `routes/` poza dwoma endpointami
zweryfikowanymi wcześniej tą samą sesją (patrz wyżej).

**Pozostaje:** `FormyZatrudnieniaPage` (osobny podkatalog `templates/employees/formy_zatrudnienia/`,
wciąż nieprzeczytany) — następny krok tej sesji.

### Moduł: Rodzaje zatrudnienia — dokończenie modułu Pracownicy (2026-08-18)

Przeczytano `templates/employees/formy_zatrudnienia/list.html` (496 linii) i zbudowano
`FormyZatrudnieniaPage` 1:1: formularz tworzenia (`nazwa` wymagana, `uwagi` opcjonalne, 3 checkboxy
— min. wynagrodzenie/gwarantowane/prowizja) + tabela z edycją **wierszową inline** (nie osobna
strona edycji). To DRUGA taka strona w całej migracji, nie jedyna — koryguję tu komentarz w
`ServiceCategoriesPage.tsx` ("jedyne miejsce w całej migracji, gdzie oryginał robi to tak"), obecnie
nieaktualny; nie edytowano kodu Usług dla samego komentarza, wystarczy to odnotować tutaj. Usuwanie
przez `useConfirm()` (prosty binarny confirm — backend nie ma tu odpowiednika ochrony "kategoria ma
przypisane usługi" z kategorii usług, więc nie ma powodu na `Modal` 3-drożny jak w Decyzji D25).

CSS: nowy plik `FormyZatrudnieniaPage.css` (nie dopisany do `EmployeesListPage.css` — strona
wizualnie/funkcjonalnie nie ma nic wspólnego z listą/formularzem/szczegółami pracownika, tylko
współdzieli nadrzędny moduł "Pracownicy" w nawigacji) z `.inline-input`/`.table-actions` (identyczne
co do wartości z `ServicesListPage.css` — świadoma duplikacja małych util-klas, ten sam wzorzec co
tam, nie promowanie do globalnego `components.css`) oraz nowym `.boolean-badge`/`.yes`/`.no`.

**Router:** `/formy-zatrudnienia` podpięty pod `requireModule="employees"` (zastąpił
`ComingSoonPage`) — moduł Pracownicy jest teraz kompletny (wszystkie 4 podstrony zbudowane).

**Weryfikacja:** `npm run build` → 0 errors (bundle 593 KB / gzip 185 KB). `npm run lint` → 0
errors, ten sam 1 nieszkodliwy pre-existing warning. Backend bez zmian (endpointy
`/api/formy-zatrudnienia*` już wcześniej zweryfikowane jako poprawnie zabezpieczone w audycie
wstępnym) — `pytest` nie uruchamiany ponownie.

### Czas budowy modułu (§1.5, do kalibracji Fazy 2)

Nie mam dostępu do zegara ściennego w tej sesji (brak narzędzia do pomiaru czasu), więc nie mogę
podać rzetelnej liczby godzin/minut — **nie zgaduję na sztywno**. Zalecenie dla użytkownika: jeśli
potrzebna jest twarda liczba do `module-inventory.md`, zmierzyć osobno przy Fazie 2 (np.
timestamp pierwszego i ostatniego commita per moduł, albo czas trwania tej sesji z historii
Claude Code).

### Kryteria akceptacji pilota (phase-01-pilot-clients.md §1.5) — status

- [x] Lista klientów: wyszukiwanie, sortowanie (6 kolumn), stan pusty, tryb mobilny — kod
      zaimplementowany 1:1 z `list.html`; **wizualna/funkcjonalna weryfikacja na oko — czeka na
      ręczny test** (zakaz samodzielnego testowania GUI w tym przebiegu).
- [x] Tworzenie/edycja: te same pola, ta sama walidacja (w tym duplicate-check), te same
      komunikaty błędów po polsku — zaimplementowane; **ręczny test czeka**.
- [x] Widok szczegółów: parytet z `view.html` (podstawowe/kontaktowe/dodatkowe dane, preferencje
      CRUD, historia wizyt, action bar) — zaimplementowane; **ręczny test czeka**.
- [x] Usuwanie: `useConfirm()` zamiast natywnego `confirm()`, soft-delete + `DELETE`/`restore`
      API wywołania identyczne jak dziś — zaimplementowane (restore endpoint owinięty w
      `clientsApi.restore`, ale UI do "cofnij usunięcie" świadomie NIE zbudowano — oryginalny
      `list.html`/`view.html` też nie mają widocznego przycisku "Przywróć", `restore_url`
      zwracany przez DELETE nie jest dziś nigdzie konsumowany po stronie klienta poza networkiem
      — 1:1 parytet, nie regresja).
- [x] 4 motywy przetestowane wizualnie — **ręczny test wykonany, OK**.
- [x] Klawiatura: sortowanie nagłówków (real `<button>`), formularz, modal potwierdzenia — **ręczny
      test wykonany, OK**.
- [ ] Czas budowy — nadal nie zmierzony (brak narzędzia w tej sesji, patrz sekcja wyżej); **nie
      blokuje zatwierdzenia** — user zdecydował zatwierdzić pilota bez tej metryki.

## Zatwierdzenie Fazy 1 — 2026-08-17

Użytkownik potwierdził: Faza 1 (pilot Klienci) **zakończona i zatwierdzona jako OK**. Wszystkie
kryteria akceptacji §1.5 spełnione poza pomiarem czasu budowy (świadomie pominięty, patrz wyżej).
Faza 2 (rollout pozostałych ~14 modułów wg `module-inventory.md`) może wystartować.

## Poprawki UX wsteczne na wszystkich zbudowanych stronach — 2026-08-18

Użytkownik zgłosił trzy poprawki mające objąć KAŻDĄ dotąd zbudowaną stronę (Klienci, Sprzedawcy,
Usługi, Pracownicy + wszystkie pod-strony), nie tylko nowy moduł. Pełny opis mechanizmu i uzasadnienie
w `DESIGN.md` §11.2 (Escape) i nowym §20 (tabele) — tutaj tylko skrót + gdzie szukać.

**1. Nagłówki sekcji sidebaru** — `font-size` mniejszy (0.6875rem) niż linki nawigacyjne wewnątrz
(0.9375rem), odwrotnie niż powinno. Podbite do 1rem (`styles/components.css`).

**2. Escape → nawigacja "Anuluj"/"Powrót do listy":** `lib/a11y/escapeScope.ts` miał już gotowy,
udokumentowany w DESIGN.md §11.2 mechanizm (`useEscapeAction`/`useEscapeClaim`) — **zero miejsc
użycia w całym repo**. Oryginalna apka Jinja miała inline handler Escape na KAŻDEJ stronie create/
edit/view (potwierdzone grepem po `templates/`) — port po prostu to zgubił. Naprawione: `guardTyping`
na `useEscapeAction` (nie przerywa pisania w polu — 1:1 z oryginałem), scentralizowane w
`FormActions` (każda strona formularza dostaje to za darmo), nowe `useEscapeBack(href)` dla "Powrót
do listy" na stronach szczegółów, nowe `useEscapeClose(isOpen, onClose)` (wyekstrahowane z
`ConfirmProvider`) dla zagnieżdżonych sekcji inline (np. "Dodaj usługę" na `EmployeeDetailPage` —
bez tego Escape podczas edycji tej sekcji wyrzuciłby użytkownika od razu do listy pracowników).

**3. Tabele — przebudowa ~16 tabel w 10 plikach jednym przebiegiem:** sticky `<thead>`, prawdziwy
stylowany scrollbar (nigdy natywny przeglądarki), klikalne wiersze (mirror "Zobacz", a jeśli brak —
"Edytuj", włącznie z dwiema tabelami edycji wierszowej inline — Kategorie usług/Formy zatrudnienia,
gdzie "Edytuj" = wejście w tryb edycji, nie nawigacja). Użytkownik wybrał (przez AskUserQuestion)
wariant "tabela wypełnia resztę viewportu, strona się nie scrolluje" zamiast prostszego "ograniczona
wysokość, strona nadal scrolluje" — stąd `.page-fills-viewport` (tylko desktop ≥1024px, mobile
zostaje przy zwykłym scrollu całej strony — zagnieżdżone regiony scrolla to papercut UX na dotyku).
Ciekawostka: `DESIGN.md` §5 od Fazy 0 miał już notatkę o dokładnie tym wzorcu (`.table-scroll-body`),
ale żadna strona go nigdy nie zaimplementowała — ta poprawka to też korekta dryfu, nie nowy wymysł;
§5 zaktualizowane, żeby odzwierciedlać realne nazwy klas (`.table-container`/`.page-fills-viewport`).

**Weryfikacja:** `npm run build`/`lint` → 0 errors po każdym większym batchu zmian (4 przebiegi w
trakcie tej pracy), ten sam 1 nieszkodliwy pre-existing warning bez zmian. Backend nietknięty.

**Bug znaleziony przez użytkownika po fakcie — żaden scrollbar nie był widoczny, wiersze się nie
scrollowały:** `.page-fills-viewport > .table-container, .page-fills-viewport > .form-card:has(>
.table-container) { ...; overflow: hidden; }` — jedna reguła z przecinkiem obsługująca DWA różne
kształty DOM przez pomyłkę dawała `overflow: hidden` OBU przypadkom, a powinna tylko wrapperowi
(`.form-card`, który nie jest regionem scrolla, tylko opakowaniem). Efekt: treść tabeli była
przycinana (clipped), nie scrollowana — dokładnie odwrotność zamierzonego zachowania. Naprawione:
rozdzielono na dwie osobne reguły — `.table-container` (bezpośrednie dziecko) zachowuje `overflow:
auto` ze swojej reguły bazowej, tylko `.form-card:has(...)` (wrapper) dostaje `overflow: hidden`.
Potwierdzone przez użytkownika po naprawie (HMR podmienił CSS na żywo, bez restartu serwera) — lekcja
na przyszłość: przy CSS-owych zmianach dotykających scroll/overflow warto zweryfikować wizualnie
(`/browse`), nie tylko przez czytanie reguł — ta klasa buga (poprawna logika na papierze, zła w
selektorze łączącym dwa przypadki) nie wyszłaby przez `npm run build`.

**Efekt uboczny, niezwiązany z UX:** przy uruchamianiu dev-serwera do podglądu na żywo okazało się,
że `.venv` w repo było puste (sam `pip`, `requirements.txt` nigdy nie zainstalowany) i miało Pythona
3.14 — `psycopg2-binary==2.9.10` nie ma jeszcze wheela dla 3.14, kompilacja ze źródeł padała na braku
MSVC Build Tools. Naprawione: `.venv` przebudowany pod systemowego Pythona 3.12 (ma gotowe wheele dla
wszystkiego w `requirements.txt`).

**Ręczny test na żywo — pierwszy raz w Fazie 2:** dzięki działającemu dev-serwerowi (SSH tunel →
Vultr Postgres :5433, `run_dev.py` :5001, `npm run dev` :5173) użytkownik faktycznie przeklikał
Klienci/Sprzedawcy/Pracownicy na żywo, nie tylko czytał build/lint. Znalazł i zgłosił dwie kolejne
niespójności wizualne (poza scrollbar-bugiem opisanym wyżej):

### Poprawki spójności kart statystyk — 2026-08-18

1. **Klienci — odstępy kart statystyk dużo ciaśniejsze niż na innych stronach.** `ClientsListPage`
   (Faza 1, budowany jako pierwszy, przed ustabilizowaniem się wzorca) miał własny, bespoke
   `.stat-strip`/`.stat-strip-item` — segmentowy pasek 1px-gap zamiast osobnych kart, padding
   `0.75rem 1rem` zamiast `1.5rem`, brak ikon. Naprawione przez migrację na te same globalne klasy
   co Pracownicy/Usługi (`.stats-grid`/`.stat-card`/`.stat-icon`/`.stat-value`/`.stat-label`,
   `components.css`) — nie tylko dostrojenie liczb paddingu na bespoke klasach, tylko realne
   przejście na wspólny komponent. Ikony: `people`/`check_circle`/`calendar_today`/`cake`. Martwe
   `.stat-strip*` usunięte z `ClientsListPage.css`.
2. **Sprzedawcy — karty statystyk bez stylu w ogóle** (brak tła/obramowania/cienia). `.stat-item`
   nie miał ŻADNEJ reguły CSS — `.stat-value`/`.stat-label` (te same nazwy co globalne klasy)
   przypadkiem dawały poprawny styl tekstu, ale wrapper karty nigdy nie dostał treatmentu. Ten sam
   zabieg: `.stats-bar`/`.stat-item` → `.stats-grid`/`.stat-card` z ikonami
   (`people`/`insert_drive_file`/`payments`/`warning_amber`, kolory blue/purple/green/orange —
   orange dla "Nieopłacone" bo `.stat-icon`/`.stat-value` nie mają wariantu "error"/czerwonego,
   tylko blue/green/purple/orange/pink; orange jako najbliższy "warning" semantycznie). Martwe
   `.stats-bar`/`.stat-item` usunięte z `SellersListPage.css`.

**Wzorzec do zapamiętania:** oba przypadki to spadek po tym, że każdy moduł budowany jako pierwszy
w swojej fazie (Klienci w Fazie 1, Sprzedawcy jako pierwszy moduł Fazy 2) wymyślił własny wygląd
kart statystyk, zanim `.stats-grid`/`.stat-card` ustabilizowało się jako wzorzec przy kolejnych
modułach. Przy audycie NASTĘPNEGO modułu warto od razu sprawdzić, czy strona z kartami statystyk
faktycznie używa `.stats-grid`/`.stat-card`, a nie własnego markupu, który tylko wygląda podobnie.

**Weryfikacja:** `npm run build`/`lint` → 0 errors (bundle CSS realnie ZMNIEJSZYŁ się, 77.48→76.54 KB
— potwierdza, że martwy CSS został faktycznie usunięty, nie tylko nadpisany). Potwierdzone przez
użytkownika na żywo przez HMR, bez restartu serwera.

## Faktury — piąty moduł Fazy 2, częściowy build — 2026-08-18

Kontynuacja Fazy 2 wg `module-inventory.md`. Przed budową przeczytano w całości:
`templates/invoices/{list_refined,create,edit}.html` (upload.html i `routes/upload_routes.py`
świadomie NIE — patrz decyzja o zakresie niżej), sekcję faktur w `routes/api_routes.py` (endpointy
CRUD, konflikt sprzedawcy, seller-sync-check/apply, export, view_pdf), `database/models.py`'s
`Invoice`, oraz jako wzorzec referencyjny — `SellerFormPage.tsx`/`SellersListPage.tsx`/`form.tsx`/
`client.ts` (najświeższy, najbardziej dopracowany moduł Fazy 2).

### Decyzja — zakres tego przebiegu

Etykieta "Wysoka (OCR upload flow)" z audytu wstępnego okazała się niedoszacowaniem po realnym
przeczytaniu źródeł — pełny szczegół w `module-inventory.md`'s "Korekta zakresu — Faktury". Skrót:
moduł to DWIE niezależne rodziny funkcji, nie jeden wzorzec list+form. Zbudowano **tylko** pierwszą
(list+CRUD+konflikt sprzedawcy+sync+eksport) — dokładnie odpowiada wzorcowi ustabilizowanemu przez
Sprzedawcy/Usługi/Pracownicy. Świadomie odłożone (routing zostaje `ComingSoonPage`, patrz
`router.tsx`):
- `/import-dokumentow` — staging wielu plików + SSE-streamowany progress OCR (`upload_routes.py`'s
  `/stage`, `/staged`, `/process` (generator/SSE), `/finalize`) — zupełnie inny rodzaj UI
  (streaming, wieloplikowy staging) niż reszta apki; wymaga własnego mini-audytu analogicznego do
  tego dla Kalendarza wizyt, zanim ruszy budowa.
- Boczny panel podglądu PDF (`togglePreviewPanel`/`openPreviewPanel` z `list_refined.html`) —
  zastąpiony na liście prostym `<a target="_blank" href="/api/pdf/<id>">` (ikona "Podgląd" w
  akcjach wiersza) i na stronie edycji pełnym `<iframe>`/`<img>` z `/api/pdf/<id>` (edit.html miał
  to jako stały panel obok formularza, nie boczny wysuwany — to zachowane 1:1). Realna funkcja
  podglądu PDF jest więc zachowana wszędzie poza samą listą, gdzie zamiast wysuwanego panelu jest
  nowa karta — świadome uproszczenie UI, nie utrata funkcji.
- `/historia` (osobny szablon `history/list_refined.html`, prawdopodobnie log audytowy, nie lista
  faktur) i `/ustawienia/email` (import z poczty, hasła PDF per e-mail — częściowo pokrywa się z
  `SellerPasswordsPanel` już zbudowanym dla Sprzedawców, wymaga sprawdzenia zakresu nakładania się).
- Przyciski "Wklej ze schowka" (`pasteToField()`) przy każdym polu formularza create/edit —
  wygoda przy przepisywaniu z OCR/innego okna; `TextField` nie ma slotu na adornment, nie ma
  odpowiednika w żadnym innym module. Formularz w pełni funkcjonalny bez tego.

### Zbudowane

`pages/faktury/{FakturyListPage,FakturaFormPage,SellerSyncModal}.tsx` + `FakturyListPage.css`,
`lib/api/invoices.ts` (pełny CRUD + `confirmSeller` + `sellerSyncCheck/Apply` + `exportUrl`/`pdfUrl`),
`types/invoice.ts`. Routing: `/faktury`, `/faktury/nowa`, `/faktury/:id/edytuj` pod istniejącym
`requireModule="invoices"` guardem (już był tam z Fazy 0/1 — tylko element zamieniony z
`ComingSoonPage`).

**Lista:** filter pills (Wszystkie/Opłacone/Nieopłacone/Przeterminowane, liczone klient-side —
"Przeterminowana" to POCHODNA, nie wartość w bazie: `status` zostaje `'Nieopłacona'`, tylko badge
się zmienia gdy `payment_due_date` minął), sortowanie (nr/sprzedawca/data/kwota — 1:1 z oryginałem,
NIP/Termin/Status NIE były sortowalne w Jinja i nie są tu też), wyszukiwanie (nr/sprzedawca/NIP),
klik w status = toggle Opłacona⇄Nieopłacona (PUT tylko `{status}}`, bez ryzyka wywołania ścieżki
konfliktu sprzedawcy — ta uruchamia się tylko gdy `seller_nip`/`seller_name` są w payloadzie),
eksport (Excel/CSV — bezpośrednia nawigacja do `/api/export/<format>`, `send_file` po stronie
Flask, żadnego fetch+blob). Brak kart statystyk na górze (oryginał `list_refined.html` ich też nie
ma — tylko pills + suma przefiltrowanej kwoty w stopce tabeli) — świadomie NIE dodano
`.stats-grid`/`.stat-card` tylko po to, żeby "wyglądało jak inne moduły"; to byłoby dryfem od
oryginału, nie parytetem.

**Formularz (create/edit, jedna strona z `mode`):** 3 sekcje przez `FormSection` (prawdziwy
`<fieldset>+<legend>`, nie skopiowany wzorzec `<h2 className="section-title">` z
`EmployeeFormPage.tsx` — sprawdzone, że TA konkretna klasa jest tam martwa, bo scoped do
`.employee-detail-page .section-title` w CSS, a formularz renderuje się pod `.employee-form-page`;
niezwiązany z Fakturami pre-existing bug w Pracownikach, nie naprawiany teraz — poza zakresem).
Przepływ konfliktu sprzedawcy (409 → modal decyzji → resubmit) zaimplementowany dla OBU trybów:
create resubmit'uje TĘ SAMĄ `FormData` (z plikiem, jeśli był) z doklejonym `seller_action`
(+ `existing_seller_id`), edit resubmit'uje JSON przez osobny endpoint `PUT
/api/invoices/<id>/confirm-seller` — dwie różne ścieżki na backendzie, zmapowane 1:1.

### Zmiany infrastrukturalne w `lib/api/client.ts`

1. **Wsparcie dla `FormData`** — pierwszy upload pliku w całym SPA (żaden wcześniejszy moduł Fazy
   0–2 tego nie potrzebował). `request()` wykrywa `body instanceof FormData` i wtedy NIE ustawia
   `Content-Type` (przeglądarka sama dokłada `multipart/form-data; boundary=…` — ręczne ustawienie
   nagłówka `application/json` na ciele FormData urwałoby boundary i backend nie sparsowałby body).
2. **`ApiError.data`** — dotąd `ApiError` niosła tylko `status`+`message` (string z `data.error`).
   Konflikt sprzedawcy (409) niesie ustrukturyzowany payload (`seller_conflict`/`seller_info`
   obiekty, nie same stringi) potrzebny do zbudowania modala decyzji — `request()` teraz przekazuje
   cały sparsowany JSON body do `ApiError.data` przy rzucaniu. Wsteczne kompatybilne (istniejące
   `catch` bloki czytające tylko `.message`/`.status` działają bez zmian).

### Weryfikacja

`npm run build` (tsc -b && vite build) → 0 errors, bundle 619.56 KB / gzip 192.10 KB (z 593 KB przed
tym modułem). `npm run lint` → 0 errors, ten sam 1 nieszkodliwy pre-existing warning (`useFocusTrap.ts`,
niezwiązany). Backend nietknięty — wszystkie użyte endpointy już istniały i były oznaczone
"Kompletna" w audycie `plan.md` §0; zero zmian w Pythonie w tym przebiegu. **Ręczny test na żywo
nie wykonany w tej sesji** — jak poprzednie moduły Fazy 2, czeka na przeklikanie przez użytkownika
(w szczególności: przepływ konfliktu sprzedawcy — 409 ścieżki nie da się sensownie zweryfikować bez
klikania w prawdziwe dane, dwuetapowy resubmit to najbardziej ryzykowny nowy kod w tym module).

## Wizyty + Kalendarz — szósty moduł Fazy 2, częściowy build — 2026-08-18

Kontynuacja Fazy 2. Użytkownik wybrał zakres jawnie (przez pytanie doprecyzowujące, po
audycie): "Kalendarze (dzień/tydzień/mies.) + create/edit/view dla wizyt", plus jednoczesna
implementacja bocznego paska month-cards wg `calendar-sidebar-redesign-prompt.md`
(plik w korzeniu repo — spec przygotowany wcześniej, patrz commit 1fda510).

### Audyt — kluczowe odkrycie koryguje `module-inventory.md`

Przeczytano w całości: `templates/appointments/{list,view,create,edit,calendar,
calendar_week,calendar_month}.html` (superadmin_edit*.html i my_visits.html — tylko
`grep`, potwierdzić że poza zakresem, nie czytane w całości), `routes/appointment_routes.py`
(1541 linii, 28 endpointów), `static/js/employee-filter.js`, `config/appointment_statuses.py`.
**Żaden z 3 widoków kalendarza nie ma drag&drop** — bloki wizyt to klikalne, pozycjonowane
czasowo `<div>`y (klik → nawigacja do `/appointment/:id`), zero `dragstart`/`draggable`/`ondrop`
w całym katalogu. Ryzyko z pierwotnego audytu (`module-inventory.md`) było przesadzone w
wymiarze interakcji, ale moduł i tak jest największy w apce z racji samej objętości (9449
linii w 10 szablonach) — pełny opis w `module-inventory.md`'s "Korekta zakresu — Wizyty +
Kalendarz".

### Decyzja — zakres tego przebiegu

Zbudowano: lista (`WizytyListPage` — domyślnie tydzień pon–nd, jak oryginał), widok
szczegółów (`WizytaDetailPage`), create/edit (`WizytaFormPage`, jeden komponent z `mode`),
3 widoki kalendarza (`CalendarDayPage`/`CalendarWeekPage`/`CalendarMonthPage`), boczny pasek
month-cards (`CalendarMonthSidebar`, wpięty w dzień-widok i listę). Świadomie poza zakresem
(logika/uzasadnienie każdego poniżej, routing zostaje `ComingSoonPage`/nie istnieje):

- **Integracja z nieobecnościami** (`reassignment-candidates`/`reassign-for-absence`/
  `reschedule-for-absence`/`cancel-for-absence`) — kod sam się opisuje jako "Faza 3,
  Supervisor conflict-resolution modal", gated `@absence_management_required` (nie
  `appointments`) — należy koncepcyjnie do modułu Nieobecności (wciąż "Wymaga audytu"),
  nie do Wizyt.
- **Wysyłka/log SMS na widoku szczegółów** (dropdown "Wyślij SMS", `/api/sms/appointment/
  <id>/log`) — własny moduł (Ustawienia SMS, wciąż "Wymaga audytu" osobno).
- **"Rozlicz przeszłe wizyty"** (`past-pending`/`past-status` — skaner przeszłych wizyt z
  nieukończonym statusem) — osobny mały workflow, `list.html` miał tylko ukryty trigger-
  przycisk (`hidden` atrybut) do niego, nie pełną integrację; pominięty w całości.
- **`status-events` polling** (5s, globalne powiadomienia toast o zmianach statusu) — nie
  specyficzne dla żadnej z tych stron, bardziej pasuje do globalnego mechanizmu
  powiadomień w `AppShell`, gdyby taki miał powstać.
- **`visit-link`/token pracownika** — część mobilnego self-service (`/my-visits`,
  `templates/appointments/my_visits.html`, bez bramki modułowej) — inna apka, nie ten
  frontend (ta sama zasada co `mobile_routes.py` w `plan.md` §5 pkt 2).
- **Superadmin power-editor** (`superadmin_edit.html`/`superadmin_edit_table.html`) —
  już wcześniej poprawnie poza zakresem (osobny moduł `data_correction`, router.tsx
  miał już `ComingSoonPage` stuby dla `korekta/wizyty`/`korekta/tabela`).

**Świadome uproszczenia względem oryginału** (funkcjonalność zachowana, tylko inny
mechanizm): klient/pracownik jako zwykły `<select>` zamiast `SearchableSelect` JS-widgetu
(natywny select nadal wspiera "wpisz literę, skocz do opcji"); walidacja okna czasowego
zmiany statusu w edit (np. "za wcześnie na rozpoczęcie wizyty") pominięta — była to tylko
client-side pre-check, serwer i tak odrzuci nieprawidłowe przejście; `prompt()`/`confirm()`
natywne z oryginału (`changeStatus()`'s reason prompt, `completeAppointment()`'s payment-
method prompt, force-save conflict confirm) zastąpione realnymi komponentami
(`StatusChangeModal`, `CompleteVisitModal`, `useConfirm()`) — DESIGN.md §16 explicite
zakazuje natywnych dialogów, oryginał ich używał tylko dlatego że to przedReactowy kod.

### Boczny pasek month-cards (`CalendarMonthSidebar.tsx`)

Zaimplementowany 1:1 wg `calendar-sidebar-redesign-prompt.md`: 3 stałe miesiące (realny
bieżący +0/+1/+2, NIGDY nie podążają za nawigacją głównego widoku), kropka+pogrubienie na
dniach z ≥1 wizytą (bez anulowanych/no-show), wypełniony krążek na "dziś", obrys na aktualnie
wybranej dacie, zwijanie z zapamiętaniem stanu (`localStorage`, wzorem `ThemeSwitcher.tsx` —
raw `localStorage` + try/catch, nie osobny hook), ukryty <1024px. Zachowanie kliknięcia
CELOWO różne w dwóch miejscach, zgodnie ze spec: dzień-widok = proste "retarguj siatkę"
(`CalendarDayPage`'s `handleSidebarDayClick`), lista = progresywny "day-chain" (patrz niżej)
— sam komponent sidebaru jest w pełni prezentacyjny, nie wie która strona go hostuje, tylko
raportuje `onDayClick(date)`.

**Day-chain w `WizytyListPage`** (§"List-view click behavior" ze specu): kliknięcie dnia
pobiera CAŁY miesiąc naraz (`ensureMonthLoaded` — jeden fetch, cache po `YYYY-MM`, nie N
osobnych fetchy per dzień — miesiąc i tak jest granicą łańcucha wg specu, "do not spill into
next month"), grupuje po dacie, i cała reszta logiki (snap-forward/backward na pusty dzień,
"Pokaż następny dzień", reset przy kliknięciu innego dnia) działa już czysto po stronie
klienta na tym jednym cache'u. Sortowanie w trybie chain jest ZAWSZE rosnąco data+godzina
(nadpisuje stan sortowania tabeli — spec p.6), przycisk sortowania kolumn wyłączony w tym
trybie. Wiersze z `end_time` w przeszłości dostają `.row-past` (wyszarzenie) — TYLKO w trybie
chain, zgodnie z sekcją specu w której ta reguła jest wymieniona.

**Bug znaleziony i naprawiony przy code-review własnego kodu przed commitem:**
`handleStatusUpdated` w trybie chain zerowało `monthCache` (żeby wymusić świeży fetch) ale
NIE odtwarzało go od razu — skoro `rawAppointments`'s useMemo warunkuje się na
`mode==='chain' && monthCache`, wyzerowanie samego cache'u bez natychmiastowego refetchu
powodowało ciche przełączenie wyświetlanych danych na (niepowiązane) dane tygodniowe zamiast
odświeżonego łańcucha dni. Naprawione: `handleStatusUpdated` teraz asynchronicznie
zeruje-i-odtwarza cache w jednym kroku (`ensureMonthLoaded` ponownie), z `chainLoading`
przełączanym wokół tego, żeby tabela pokazała "Ładowanie..." zamiast błysku złych danych.

### Zmiany infrastrukturalne w `lib/api/client.ts`

**`api.patch()`** — pierwszy użytkownik PATCH w SPA (`PATCH /api/appointments/<id>/
satisfaction`) — dotąd klient miał tylko get/post/put/del; dodano symetryczny `patch`
(ten sam CSRF/Content-Type traktowanie co `put`, żadna zmiana w `request()` nie była
potrzebna poza samym helperem).

### Weryfikacja

`npm run build` (tsc -b && vite build) → 0 errors, bundle 668.65 KB / gzip 204.93 KB (z 619.56 KB
przed tym modułem — największy dotąd przyrost, adekwatnie do rozmiaru modułu). `npm run lint` →
0 errors, ten sam 1 nieszkodliwy pre-existing warning + jeden nowy świadomie wyciszony
(`react-hooks/exhaustive-deps` na `time` w taken-slots efekcie, z komentarzem uzasadniającym).
Backend nietknięty. **Ręczny test na żywo nie wykonany** — to zdecydowanie najbardziej
ryzykowny moduł dotąd zbudowany bez klikania: day-chain logika sidebaru, SSE confirmation
badge, i force-save conflict flow to trzy niezależne nowe mechanizmy nigdy wcześniej nie
przetestowane w tej apce poza automatycznym build/lint.

---

## Naprawa loginu (kolizja portów) + commit/push Faktur i Wizyt — 2026-08-19

### Bug: "nie mogę się zalogować na dotychczasowych credentials"

Root cause: **nie to, co brzmiało na pierwszy rzut oka** (błędne hasło) — kolizja portów między
tym projektem a zupełnie niepowiązanym `~/PycharmProjects/human-solutions` ("HR system"), którego
własny `run_dev.py` też miał na sztywno port 5001. Który proces zbindował się pierwszy, wygrywał
port po cichu — frontend tego projektu (`:5173`, proxy) trafiał wtedy w REALNOŚCI w backend
`human-solutions`, który poprawnie (ale mylnie z punktu widzenia użytkownika) odrzucał znane
credentials jako "nieprawidłowy email lub hasło", bo sprawdzał je względem zupełnie innej tabeli
użytkowników. Zdiagnozowane przez curl unikalnej trasy tej apki (`/api/invoices/statistics`) — 404
zamiast oczekiwanego 401/302 zdradziło, że odpowiada inny kod. Pełny opis + procedura sanity-check
w [[react-migration-local-dev-setup]].

**Fix:** `run_dev.py` czyta teraz `DEV_SERVER_PORT` (domyślnie nadal 5001, wsteczne kompatybilne)
zamiast portu na sztywno. Backend tego projektu przeniesiony na `:5002` (za zgodą użytkownika —
"Zmień port faktury zamiast tego", explicite NIE ruszać `human-solutions`), Vite wskazany na niego
przez `VITE_API_PROXY_TARGET`. Zweryfikowane end-to-end (curl: prawdziwy banner apki, unikalna
trasa nie-404, działający CSRF token, działający łańcuch proxy) — użytkownik potwierdził, że
logowanie znów działa.

**Uwaga środowiskowa (może się powtórzyć w kolejnej sesji):** dwa kolejne uruchomienia backendu
przez Bash-owy `run_in_background:true` zostały ubite przez harness/sandbox między turami rozmowy
(potwierdzone `<task-notification>` ze statusem `killed`). Backend ostatecznie odpalony przez
PowerShell `Start-Process -WindowStyle Hidden` (proces w pełni odłączony od Claude Code, output do
`.flask_dev.log`/`.flask_dev.err.log`) — zweryfikowany jako działający, ale **nieprzetestowany, czy
przetrwa przez granicę kolejnej tury/sesji**; jeśli backend znowu "zniknie", to pierwszy podejrzany.

### Commit + push — 4 commity na branch `invoices-app`

```
d51ee8b fix(dev): port serwera dev konfigurowalny przez DEV_SERVER_PORT
69f9d5a feat(react-migration): Wizyty + Kalendarz — lista, szczegoly, create/edit, 3 widoki kalendarza, pasek month-cards
2ca59ba feat(react-migration): Faktury — lista, create/edit, sync sprzedawcow, eksport
d7e8c83 chore: usun przestarzaly scaffold planningowy (ai-devkit)
```
Wypchnięte na `origin/invoices-app` — potwierdzone (`HEAD` == `origin/invoices-app`). Po drodze
dwie pomyłki przy commitowaniu złapane i naprawione PRZED pushem (opisane w podsumowaniu sesji, nie
tutaj — nieistotne dla stanu kodu): przypadkowo za szeroki `git commit --amend` cofnięty przez
`git reset --soft HEAD~1`, oraz problem z cudzysłowami w wiadomości committa w Bashu, obejście przez
plik tymczasowy + `git commit -F`.

### Pierwszy ręczny QA na żywo — Faktury / Sprzedawcy / Wizyty — 2026-08-19

Po naprawie loginu użytkownik faktycznie przeklikał (pierwszy raz) moduł Faktury i moduł Wizyty +
Kalendarz (oba zbudowane dzień wcześniej, 2026-08-18, nigdy wcześniej nie klikane — patrz sekcje
wyżej "**Ręczny test na żywo nie wykonany**") plus wrócił do już wcześniej zweryfikowanych
Sprzedawców. Notatki zostawione w pliku roboczym **`react-UI-issues-fixes_19082026.txt`** (korzeń
repo, NIEZACOMMITOWANY — `git status` pokazuje go jako `??`; ten plik jest źródłem tej sekcji, nie
duplikatem do zignorowania — sprawdzić, czy nadal istnieje na dysku, jeśli potrzebny kontekst
źródłowy 1:1). Znaleziono **7 konkretnych usterek UI**, żadna jeszcze nie naprawiona:

1. **Faktury, edycja — panel podglądu PDF za mały i źle proporcjonowany.** Dziś: ~1/4 szerokości
   strony, kwadratowy (height=width). Oczekiwane: wysokość = od górnej krawędzi panelu w dół do
   stopki page-view (z zachowaniem obecnych odstępów), szerokość dobrana z proporcji A4 do TEJ
   wysokości (nie kwadrat). PDF ma się w pełni mieścić. Prawdopodobnie wymaga też przełożenia
   layoutu reszty formularza (węższe kolumny/pola), żeby nic nie wymagało scrolla pionowego —
   wszystko w jednym viewport. **Najbardziej inwazyjna zmiana z tej listy** (dotyka i panelu PDF, i
   układu formularza) — `FakturaFormPage.tsx`.
2. **Sprzedawcy, lista — nagłówki kolumn nie zawsze wyrównane tak jak wartości wierszy** (np.
   kolumna "Nazwa": nagłówek wyśrodkowany, wartość w wierszu do lewej). Naprawić: wyrównanie
   nagłówka ma iść za wyrównaniem jego kolumny w wierszach, nie odwrotnie — `SellersListPage.tsx`/
   CSS, prawdopodobnie reguła bazowa `.refined-table th` nieuwzględniająca wyrównania per-kolumna.
3. **Wizyta, widok szczegółów — brak przycisku "Powrót"** do poprzedniego widoku, i Escape też nie
   działa. Ten sam wzorzec co luka znaleziona 2026-08-18 (Escape-infra istniała, nie wszędzie
   podpięta) — `WizytaDetailPage.tsx` prawdopodobnie nigdy nie dostał `useEscapeBack(href)`
   (hook już istnieje, użyty gdzie indziej, patrz [[react-migration-ux-polish-2026-08-18]]).
   **Task 2 tej samej usterki:** przyciski zmiany statusu wizyty mają niejasne znaczenie/działanie —
   zastąpić pojedynczym dropdownem, wartość początkowa = aktualny status przy załadowaniu strony.
   ⚠️ **Niejednoznaczne, wymaga pytania doprecyzowującego przed implementacją** (zgodnie z
   `CLAUDE.md`'s "clarification policy") — m.in.: czy zmiana w dropdownie od razu zapisuje (PATCH/PUT
   natychmiast po `onChange`), czy wymaga osobnego przycisku "Zapisz"/potwierdzenia; czy dropdown ma
   pokazywać WYŁĄCZNIE statusy dozwolone wg `AppointmentStatus.VALID_TRANSITIONS`
   (`config/appointment_statuses.py`) czy wszystkie z nieprawidłowymi wyszarzonymi/disabled.
3.1. **Kalendarz, widok tygodnia** — siatka wyższa niż viewport, strona scrolluje w pionie.
   Oczekiwane: wysokość dopasowana do dostępnej przestrzeni, responsywnie, zero scrolla pionowego —
   cały kalendarz widoczny naraz. `CalendarWeekPage.tsx`.
3.2. **Kalendarz, widok dnia** — ta sama naprawa wysokości/viewportu co wyżej. DODATKOWO: istniejący
   lewy panel month-cards (`CalendarMonthSidebar`) ma się przenieść na PRAWĄ stronę widoku kalendarza
   (notatka użytkownika wymienia to wprost tylko dla widoku dnia — do potwierdzenia przy
   implementacji, czy dotyczy też tygodnia/listy, czy tylko dnia). `CalendarDayPage.tsx`.
3.3. **Wizyty, lista** — brakuje dokładnie tego wzorca tabel (sticky header, scrollowane wiersze,
   `.table-container` wypełniający dostępną wysokość, zero scrolla strony poza custom-stylowanym
   scrollbarem wierszy), który już powstał i został zastosowany na ~16 innych tabelach w przebiegu
   UX z 2026-08-18 (DESIGN.md §20, patrz [[react-migration-ux-polish-2026-08-18]]) — `WizytyListPage`
   był budowany PO tamtym przebiegu, tego samego dnia, i nigdy nie dostał retrofitu. Użytkownik
   explicite: *"refer strictly to existing clients-table"* — czysty przepis wzorca z
   `ClientsListPage`, żadnego nowego projektowania. `WizytyListPage.tsx`.

### Zaproponowana kolejność napraw dla następnej sesji

Rosnąco wg ryzyka/inwazyjności, z priorytetem dla mechanicznych retrofitów istniejącego wzorca
(szybkie, niskie ryzyko, budują pewność) przed nowym UX-em i najbardziej złożonym layoutem na
końcu:

1. **#7 Wizyty lista — retrofit `.table-container`/sticky-header wzorem `ClientsListPage`** —
   czysto mechaniczne, dokładny precedens sprzed doby, najniższe ryzyko.
2. **#2 Sprzedawcy — wyrównanie nagłówek/wartość** — trywialna, izolowana poprawka CSS.
3. **#3 (część 1) Wizyta detail — `useEscapeBack` + przycisk "Powrót"** — ponowne użycie istniejącego
   hooka, mechaniczne.
4. **#3 (Task 2) Wizyta detail — dropdown zmiany statusu** — ⚠️ najpierw zadać pytanie
   doprecyzowujące (patrz wyżej), dopiero potem implementować.
5. **#3.1 Kalendarz tydzień — dopasowanie wysokości do viewportu.**
6. **#3.2 Kalendarz dzień — to samo dopasowanie wysokości + przeniesienie sidebaru na prawo**
   (rób od razu po #5, bo dzieli tę samą naprawę CSS wysokości — różnica tylko w przeniesieniu
   sidebaru).
7. **#1 Faktury edycja — panel podglądu PDF (proporcja A4) + reflow formularza** — najbardziej
   inwazyjna, największe ryzyko efektów ubocznych na layout formularza — na koniec.

Backend: żadna z tych 7 usterek nie wymaga zmian w `routes/`/`repositories/` — to wyłącznie CSS/
layout/component-level fixes na już istniejących, poprawnie zabezpieczonych endpointach. Po każdej
grupie napraw: `npm run build`/`lint` + wizualna weryfikacja (idealnie `/browse` albo ponowne
ręczne klikanie przez użytkownika — poprzedni bug z `overflow: hidden` z 2026-08-18 pokazał, że ten
rodzaj usterki przechodzi build/lint czysto).

---

## Wszystkie 7 usterek z pierwszego ręcznego QA — naprawione, 2026-08-19

Kontynuacja tej samej sesji. Wykonano wszystkie 7 poprawek w zaproponowanej kolejności (rosnąco
wg ryzyka). `npm run build`/`lint` → **0 errors** po każdej pojedynczej poprawce (ten sam 1
nieszkodliwy pre-existing warning `useFocusTrap.ts` przez cały czas, bez zmian). Backend nietknięty
— potwierdzone: żadna z siedmiu nie dotyka `routes/`/`repositories/`.

**Wizualna weryfikacja na żywo — NIE wykonana w tej sesji.** Zarówno `/browse` (gstack — katalog
`~/.claude/skills/browse/` ma tylko `SKILL.md`, brak `dist/`/`bin/`/`setup`, nie do zbudowania), jak
i `mcp__claude-in-chrome__*` (rozszerzenie Chrome zgłasza "not connected") okazały się niedostępne w
tym środowisku. Za zgodą użytkownika: dalsze poprawki szły na samym build/lint + code-review, bez
możliwości zobaczenia efektu — **to jest jawnie zwiększone ryzyko** (dokładnie ten rodzaj usterki,
który już raz przeszedł build/lint czysto i okazał się złamany na żywo — `overflow: hidden` bug,
2026-08-18). Pierwszy ręczny click-through przez użytkownika jest teraz PRIORYTETOWYM następnym
krokiem, nie opcjonalnym.

### #1 Wizyty lista — retrofit `.table-container`/sticky-header (DESIGN.md §20)

Root cause: `page-fills-viewport` klasa siedziała na złym elemencie — na samym `.table-container`
zamiast na korzeniu strony (`.cal-grid-page`), więc globalna reguła `.page-fills-viewport >
.table-container` nigdy nie dopasowywała (te dwie klasy były na TYM SAMYM elemencie, nie w relacji
rodzic→dziecko). Naprawione: `page-fills-viewport` przeniesiona na root, plus nowa reguła w
`Appointments.css` (`.page-fills-viewport.cal-grid-page { flex-direction: row }` +
`> .cal-main > .table-container { flex:1; min-height:0 }`) — bo `.cal-grid-page`'s layout to ROW
(main + sidebar month-cards), nie kolumna jak zakłada wzorzec Klientów/Sprzedawców/Usług/
Pracowników (jedyne dwa DOM-kształty opisane w DESIGN.md §20.2). *(Ta reguła została później
usunięta i zastąpiona prostszą wersją przy okazji poprawki #6 — patrz niżej.)*

### #2 Sprzedawcy — wyrównanie nagłówków kolumn

Root cause (systemowy, nie tylko Sprzedawcy): `<th>` centruje się domyślnie w UA-stylesheet
KAŻDEJ przeglądarki (`<td>` — nie). `.refined-table th` (components.css) nigdy nie nadpisywał
`text-align`, więc każda kolumna BEZ jawnego `align` (tylko `:first-child` miał osobną regułę)
cicho dziedziczyła center, niezależnie od tego czy jej wartości w wierszach są wyrównane do lewej.
Naprawione JEDNĄ linią w bazowej regule (`text-align: left` na `.refined-table th`) — systemowy fix
w współdzielonym komponencie, nie page-owned override; naprawia też Wizyty (kolumny Klient/Usługa/
Pracownik/Ocena miały ten sam utajony bug, nigdy niezgłoszony osobno).

### #3 Wizyta detail — "Powrót do listy" + Escape, oraz dropdown zmiany statusu

`useEscapeBack('/wizyty')` + `<ButtonLink icon="arrow_back">Powrót do listy</ButtonLink>` w
action-bar — 1:1 wzorzec z `ClientDetailPage`/`EmployeeDetailPage` (import + wywołanie hooka +
button, ten sam układ: Edytuj → Powrót → akcja destrukcyjna).

**Task 2 (dropdown statusu) — zadano pytanie doprecyzowujące przed implementacją** (zgodnie z
`CLAUDE.md`, log sam to flagował jako niejednoznaczne). Odpowiedzi użytkownika: (a) wybór w
dropdownie NIE zapisuje od razu — otwiera istniejący `StatusChangeModal`/`CompleteVisitModal`
(zachowuje pole "powód" dla anulowania, chroni przed przypadkowym wyborem); (b) dropdown pokazuje
WYŁĄCZNIE `VALID_TRANSITIONS` (ten sam filtr `visibleTransitions`, którego już używały stare
przyciski) — jeden model reguł przejść w jednym miejscu, nie duplikowany. Zaimplementowane: rząd
przycisków zastąpiony jednym `<select className="status-select">` (nowa klasa w
`WizytaDetailPage.css`, rozmiar dopasowany do `.refined-btn-secondary`, natywna strzałka — wzorem
`EmployeeFilter`'s `.empf-dropdown select`, nie `.form-select`, bo ten wymaga `FieldWrapper`
którego action-bar nie ma). `value` dropdowna to zawsze `appt.status` (nie osobny local state) —
wybór inny niż bieżący status od razu otwiera odpowiedni modal; anulowanie modala "odskakuje" z
powrotem do prawdziwego statusu za darmo, bo select jest w pełni controlled przez dane z API, nie
przez tymczasowy wybór użytkownika.

### #4/#5 Kalendarz tydzień/dzień — dopasowanie wysokości siatki do viewportu

Root cause: `LANE_HEIGHT = 900` (px) był STAŁĄ na poziomie modułu, używaną do pozycjonowania KAŻDEGO
elementu absolutnego (linie godzin, bloki wizyt, nieobecności) — siatka zawsze renderowała się na
900px wysoka, niezależnie od realnej wysokości viewportu, więc CAŁA STRONA (nie tylko tabela)
scrollowała się w pionie.

Nowy współdzielony hook `lib/useElementHeight.ts` (callback-ref + `ResizeObserver`, nie zwykły
`useRef` — element mierzony renderuje się warunkowo za `loading`, więc zwykły ref nigdy by nie
"złapał" węzła, który zamontował się PO pierwszym efekcie) mierzy REALNĄ wysokość rzędu siatki na
żywo. `LANE_HEIGHT` stała → `LANE_HEIGHT_FALLBACK` (seed przed pierwszym pomiarem I stabilna
wartość na mobile, gdzie `.page-fills-viewport` się nie stosuje — DESIGN.md §20.2 celowo gate'uje to
tylko na desktop, więc mobile ma zostać dokładnie takie jak było). `position()`/nowy helper
`hourTop()` przyjmują `laneHeight` jako parametr zamiast czytać stałą z zamknięcia modułu.

Restrukturyzacja DOM (obie strony): nagłówek dnia/pracownika wydzielony do WŁASNEGO rzędu
(`flexShrink:0`) NAD rzędem siatki (`flex:1; minHeight:0`, tam gdzie podpięty jest
`useElementHeight`'s ref) — usuwa stary fudge-offset `+24` (kolumna godzin startowała na górze
CAŁEGO kontenera, podczas gdy kolumny dni miały własny nagłówek nad sobą; teraz kolumna godzin jest
w TYM SAMYM rzędzie co kolumny dni, więc linie godzin wyrównują się z siatką day-column co do
piksela, bez zgadywania offsetu).

### #6 Kalendarz dzień — przeniesienie sidebaru + wyrównanie page-header

**Odkrycie przy implementacji — kod przeczył notatce.** Notatka użytkownika: "existing LEFT panel
... move to right". Kod: `CalendarMonthSidebar` był DRUGIM dzieckiem w zwykłym `display:flex` rzędzie
(`.cal-grid-page`, brak `order`/`row-reverse` gdziekolwiek) — w standardowym LTR flexboksie to
oznacza, że POWINIEN renderować się po prawej już dziś, nie po lewej. **Zadano pytanie
doprecyzowujące zamiast zgadywać** (dokładnie zasada z `CLAUDE.md` — "which element" tu było "które
'lewo'"). Odpowiedź użytkownika: zostaw pozycję jak jest (== nie przesuwaj — notatka była
prawdopodobnie błędnym wspomnieniem z klikania), ALE dodatkowo: (a) górna/dolna krawędź sidebaru ma
się wyrównać z głównym oknem kalendarza/tabeli, (b) rząd przycisków page-header ma sięgać do
prawdziwej prawej krawędzi viewportu, nie tylko do krawędzi węższej kolumny `.cal-main`.

(a) okazało się **darmowym efektem ubocznym** naprawy wysokości: `.cal-grid-page` już miał
`align-items: stretch` w bazowej regule — wystarczyło, że rząd dostał realnie ograniczoną wysokość
(przez #4/#5), żeby `.cal-main` i `CalendarMonthSidebar` (rodzeństwo w tym samym rzędzie) zaczęły
kończyć się na tej samej wysokości automatycznie, bez dodatkowego CSS.

(b) wymagało realnej restrukturyzacji: `<header className="page-header">` był ZAGNIEŻDŻONY w
`.cal-main` (węższym niż pełna szerokość, bo nie obejmuje kolumny sidebaru) w OBU stronach
(`WizytyListPage.tsx` I `CalendarDayPage.tsx` — notatka użytkownika explicite: "day-calendar view
page (lub tabeli wizyt)", czyli obie). Przeniesiony na prawdziwy korzeń strony (nad
`.cal-grid-page`, nie w nim) w obu plikach — `justify-content: space-between` w `.page-header` teraz
faktycznie sięga do prawej krawędzi całej strony, łącznie z szerokością sidebaru. Skutek uboczny:
uproszczenie CSS — skoro `.page-fills-viewport` siedzi teraz na PRAWDZIWYM korzeniu (zwykła kolumna,
bez konfliktu row/column), specjalna reguła compound-selector z poprawki #1
(`.page-fills-viewport.cal-grid-page`) stała się zbędna i została zastąpiona prostszą wersją
(`.page-fills-viewport .cal-main > .table-container`) w `Appointments.css`.

### #7 Faktury edycja — panel podglądu PDF, proporcja A4 (najbardziej inwazyjna, zrobiona ostatnia)

Root cause: `.invoice-doc-card` nie miał żadnej jawnej wysokości — tylko `min-height: 320px` jako
podłoga, obok STAŁEJ szerokości 380px z grida (`grid-template-columns: 1fr 380px`) — stąd zawsze
renderował się mniej więcej kwadratowo, niezależnie od realnie dostępnej wysokości viewportu.

Naprawione BEZ JavaScriptu (w przeciwieństwie do #4/#5) — czysty CSS `aspect-ratio: 210 / 297`
(proporcja A4 portrait) na `.invoice-doc-card`, którego `height: 100%` liczy się teraz względem
realnie ograniczonej wysokości strony (`page-fills-viewport` na korzeniu, desktop-only jak wszędzie
indziej). Różnica względem #4/#5: tam JS był konieczny (`Math.max(16, ...)` na elementach
absolutnie pozycjonowanych potrzebuje prawdziwej liczby px w skrypcie), tutaj wystarczy JEDNA
deklaracja CSS, bo to dokładnie przypadek, do którego `aspect-ratio` został zaprojektowany — jeden
wymiar jawny (wysokość), drugi (szerokość) wyliczony z proporcji.

`.invoice-form-layout` przepisany z CSS Grid na flex (funkcjonalnie identyczny na dotychczasowych
szerokościach — ten sam efekt wizualny, `1fr` + 380px) — Grid nie licuje się niezawodnie z
`aspect-ratio`-driven, content-sized kolumną w torze `auto`, flex tak. Formularz dostaje
`overflow-y: auto` jako siatkę bezpieczeństwa (nie cel sam w sobie) — 3 `FormSection`y na tej
stronie są wystarczająco krótkie, że to zwykle będzie no-opem na realnym ekranie; gdyby jednak
kiedyś zabrakło miejsca, przewija się TYLKO formularz, nigdy cała strona (dokładnie ta sama
filozofia co `page-fills-viewport` wszędzie indziej w apce). Świadomie NIE ruszano wewnętrznego
layoutu `FormSection`/`TextField` (współdzielony komponent, wpłynąłby na każdy inny formularz w
apce) — poza zakresem tej pojedynczej, już wystarczająco inwazyjnej poprawki.

---

## Druga runda poprawek UI — `react-ui-corrections_19080026.txt`, 2026-08-19

Kolejny plik roboczy z konkretnymi usterkami znalezionymi po tym, jak poprzednia runda (7 poprawek
wyżej) trafiła do kodu — użytkownik przeklikał dalej i znalazł 5 nowych obszarów. `npm run build`/
`lint` → **0 errors** po całości (ten sam 1 nieszkodliwy warning). **Wizualna weryfikacja NADAL
niemożliwa** — sprawdzone ponownie na starcie tej rundy: `mcp__claude-in-chrome__*` dalej zgłasza
"not connected", `/browse` dalej bez binarki (patrz [[react-migration-browser-tooling-gap]]).

### #1 Boczny pasek month-cards — dni nachodzą na kartę

Root cause: `.month-card-day` używał `aspect-ratio: 1`, wiążąc WYSOKOŚĆ każdej komórki z jej
SZEROKOŚCIĄ (czyli szerokością kolumny gridu 7×, zależną od zmiennej szerokości sidebaru
220–280px). Na wystarczająco szerokim sidebarze każdy wiersz wychodził wyższy niż karta miała
miejsca na 5–6 wierszy — stąd dolne wiersze wizualnie wychodziły poza `.month-card`. Naprawione:
stały rozmiar `width/height: 1.375rem` (zamiast aspect-ratio), wyśrodkowany w komórce przez
`justify-self: center` — wysokość wiersza gridu staje się przewidywalna i mała niezależnie od
szerokości sidebaru. Kropka-wskaźnik wizyt (`::after`) usunięta — kodowanie kolorem (`.has-
appointments` już przełączał na `--color-ink` z domyślnego `--color-ink-subtle`) było już
zaimplementowane, wystarczyło usunąć zbędną kropkę.

### #2 Boczny pasek month-cards — brak nawigacji miesięcy

`months` (dotąd `useState` obliczany RAZ przy montowaniu, "fixed and never follows navigation")
zamieniony na `anchorMonth` + `useMemo`, nawigowalny o krok 3 miesięcy. Nowe przyciski
prev/next (`Icon name="expand_more"`, jeden z nich obrócony 180° przez `.icon-flip` — brak
`expand_less` w zestawie ikon, obrót tego samego glifu zamiast mieszania stylu z `arrow_upward`)
w `.cal-sidebar-topbar`, obok istniejącego przycisku zwiń/rozwiń, renderowane TYLKO gdy panel
rozwinięty. Po zmianie okna: `daysWithAppointments` refetchowany dla nowego zakresu (deps
`useEffect` zmienione z `[]` na `[anchorMonth]`), a po rozwiązaniu fetcha — jeśli zmiana była
wywołana nawigacją (`navigatedRef`, nie zwykłym mountem) — wywoływany jest TEN SAM `onDayClick`,
którego używa zwykłe kliknięcie dnia, z pierwszym dniem z wizytami w ŚRODKOWYM miesiącu (fallback:
1. dzień tego miesiąca, gdy brak wizyt). Zero nowego propa/callbacku — ponowne użycie istniejącego
mechanizmu hosta.

### #3 Dzień/tydzień kalendarza — pięć powiązanych usterek

a/b: `.wk-block`/`.day-block` miały płaskie tło `--color-surface-elevated` (identyczne z tłem
siatki — stąd niewidoczne) i `border-left-color` kodowany kolorem PRACOWNIKA, nie statusu.
Naprawione: pełna paleta `.status-badge.*` przeniesiona na warianty klasy statusu (`.scheduled`,
`.confirmed`, itd.) — ten sam schemat kolorów co wszędzie indziej w apce (lista, detail).
`borderLeftColor: empColor(...)` usunięty z inline style (inline zawsze wygrywa ze stylesheetem,
więc musiał zniknąć, żeby nowe klasy statusu faktycznie zadziałały). Import `empColor` usunięty z
`CalendarWeekPage.tsx` (nieużywany po tej zmianie — w widoku tygodnia zawsze jeden pracownik, więc
kolor pracownika i tak nic nie różnicował); w `CalendarDayPage.tsx` zostaje (nadal używany na
kolorze tekstu nagłówka kolumny pracownika — inne, dalej zasadne zastosowanie).

c: treść bloku rozszerzona z "pierwsze imię klienta + godzina startu" na: pełne imię i nazwisko
klienta, usługa(-i) (`a.service_name`, już comma-joined string z API), imię fryzjera(-ki)
(`a.employee_name`/`emp.full_name`, pierwszy człon), godzina startu + czas trwania w minutach
(nowy helper `durationMin()`). Tooltip (`title`) też wzbogacony, na wypadek gdy bardzo krótka
wizyta (`Math.max(16, ...)` floor wysokości) obcina tekst wizualnie.

d: nowa klasa `.cal-grid-header-cell` (`background: var(--color-surface)`) na wrapperze rzędu
nagłówka dnia/pracownika w obu plikach — było bez tła, więc dziedziczyło ten sam
`--color-surface-elevated` co siatka pod spodem.

e: mimo wcześniejszej naprawy #4/#5 (poprzednia runda) scroll pionowy dalej bywał widoczny.
Zdiagnozowane jako sub-pikselowe zaokrąglenie: `getBoundingClientRect()`/`ResizeObserver` mogą
zwrócić wartość ułamkową (np. `547.33px`), która następnie przechodzi przez dalszą arytmetykę
zmiennoprzecinkową (`position()`/`hourTop()`) — wystarczy, że którykolwiek wynik wyląduje ułamek
piksela NAD realnie dostępną przestrzenią, żeby `overflow: auto` pokazał scrollbar mimo braku
realnie obciętej treści. Naprawione w `lib/useElementHeight.ts` (jedno miejsce, obie strony
korzystają): `Math.floor()` + margines bezpieczeństwa 1px na każdym zwracanym pomiarze. Dodatkowo,
jako pas bezpieczeństwa nie do obejścia: `.table-container` w obu plikach dostał `overflow:
'hidden'` inline (nadpisuje bazowe `overflow: auto` — ten konkretny kalendarz ma być dokładnie
dopasowany, więc nie potrzebuje własnego scroll-fallbacku jak np. formularz faktury).

### #4 Widok miesiąca — szerokość + kolory statusów na liniach wizyt

`page-fills-viewport` dodany do korzenia `CalendarMonthPage.tsx` (jedyny z 3 widoków kalendarza,
który nigdy go nie dostał w poprzedniej rundzie — nie było go na oryginalnej liście 7 usterek).
Nowa reguła `.page-fills-viewport > .month-grid` (Shape 1, `.month-grid` jest bezpośrednim
dzieckiem korzenia mimo owinięcia w fragment React) + jawne `width: 100%` na `.month-grid`
(defensywnie, dla dosłownego "expand to all available space"). `.month-cell-appt` dostał te same
warianty statusu co `.wk-block`/`.day-block` (bez `.cancelled` — `dayAppts` już filtruje anulowane
przed renderem). Treść linii zmieniona z "godzina + imię klienta" na "pełne imię klienta (imię
fryzjera)" — zgodnie z nowym, węższym spec — godzina zostaje tylko w tooltipie (miejsca mało,
widok miesiąca to celowo kompaktowy przegląd, inaczej niż dzień/tydzień).

### #5 Podgląd PDF faktury — panel miniatur stron

Nie jest to bug w kodzie tej apki — to natywna przeglądarka PDF Chrome (PDFium), domyślnie
pokazująca własny boczny panel miniatur stron wewnątrz `<iframe>`, zjadający szerokość
i tak już wąskiego panelu podglądu. Naprawione parametrem URL rozpoznawanym przez wbudowaną
przeglądarkę PDF Chrome: `#navpanes=0` doklejony do `src` obu `<iframe>` (tryb create — podgląd
lokalnego pliku z `URL.createObjectURL`, i tryb edit — `invoicesApi.pdfUrl(...)`). Nie ruszano
paska narzędzi (`#toolbar=0`) — proszono wyłącznie o panel miniatur.

## Zatwierdzenie obu rund poprawek UI — 2026-08-19

Użytkownik potwierdził: całość UI z obu rund (12 usterek łącznie — 7 z pierwszego QA + 5 z
`react-ui-corrections_19080026.txt`) **zatwierdzona**. Moduły Wizyty+Kalendarz i Faktury
(częściowo) są od teraz zamknięte pod kątem zgłoszonych usterek UI — nie ma otwartych zadań z
tych dwóch przebiegów QA. Kod wypchnięty na `origin/invoices-app` (patrz commit poniżej najbliższy
tej dacie w historii gita).

**Dla świeżej sesji — stan i następny krok:**
- Fazy 0/1 zamknięte i zatwierdzone (2026-08-17).
- Faza 2: Dashboard/Sprzedawcy/Usługi/Pracownicy zbudowane i zweryfikowane wcześniej (2026-08-18).
  Faktury i Wizyty+Kalendarz zbudowane (2026-08-18), UI-przetestowane i zatwierdzone (2026-08-19)
  — ale oba mają świadomie odłożone kawałki poza zakresem samego UI-QA, patrz niżej.
- **Odłożone kawałki Faktur** (patrz sekcja "Faktury — piąty moduł..." wyżej): `/import-dokumentow`
  (staging wielu plików + SSE OCR progress), `/historia`, `/ustawienia/email`.
- **Odłożone kawałki Wizyt** (patrz sekcja "Wizyty + Kalendarz — szósty moduł..." wyżej):
  integracja z Nieobecnościami (reassign/reschedule/cancel-for-absence), wysyłka/log SMS na
  widoku szczegółów, "Rozlicz przeszłe wizyty" (skaner past-pending/past-status), `status-events`
  polling.
- **Moduły "Wymaga audytu" w ogóle nietknięte** (`module-inventory.md`): Analityka/KPI/Przychody,
  Nieobecności (wnioski), Bilanse urlopowe, Import danych/historia/OCR, Użytkownicy (RBAC), Role
  (RBAC), Ustawienia e-mail/SMS. Gotowe prompty audytowe do wklejenia dla każdego —
  `module-inventory.md`'s "Gotowe prompty do audytu modułów oznaczonych 'Wymaga audytu'".
- **Decyzja co robić dalej NIE jest podjęta** — żaden z powyższych trzech obszarów (odłożone
  Faktury, odłożone Wizyty, nowy moduł) nie jest z góry priorytetowy; do ustalenia z użytkownikiem
  na starcie następnej sesji.
- Backend: bez zmian w całej dzisiejszej sesji UI-poprawek (obie rundy) — `pytest` nie wymaga
  ponownego uruchomienia, nic w `routes/`/`repositories/` się nie zmieniło.

---

## 2026-08-24 — Option A rollout: pozostałe moduły "Wymaga audytu", tryb autonomiczny

Użytkownik jawnie zwolnił z zasady "pytaj przy niejasności" z `CLAUDE.md` dla tego przebiegu —
"decide yourself if any doubts", commit+push po każdym module, bez przystanków. Kolejność:
rosnące ryzyko, jak w Fazie 2 (`plan.md` §2). Każda decyzja bez oczywistej odpowiedzi w kodzie
zapisana tutaj, zamiast pytania użytkownika.

### Moduł: Ustawienia e-mail/SMS — zbudowany

Audyt: `/settings/email` (main_routes.py:540) była już czystym Jinja-shellem nad w pełni gotowym
JSON API (`/api/email/settings|test|folders`, routes/api_routes.py:1493-1601) — zero zmian
backendu. `/settings/sms` (sms_routes.py, 224 linie) była odwrotnie: cała logika (Twilio
credentials, CRUD typów wiadomości, log wysyłek) istniała tylko jako `request.form` +
`redirect`/`flash`, poza `/api/sms/stats|send|bulk-send|.../log` (już JSON) i
`.../message-type/<id>/delete` (już JSON, jedyny mutujący endpoint tej strony, który już był).

**Decyzja D26 — nowe `/api/sms/*` endpointy jako siostrzane do form-POST, nie zamiana:** dodano
`GET /api/sms/settings` (settings+message_types+stats w jednym payloadzie, mirror tego co Jinja
route zbierał do jednego `render_template`), `PUT /api/sms/credentials`, `PUT
/api/sms/message-types/<id>`, `POST /api/sms/message-types`, `DELETE /api/sms/message-types/<id>`
(nowy, czysty REST-owy odpowiednik istniejącego POST-owego `.../delete` — ten drugi zostaje
nietknięty, obsługuje starą stronę Jinja), `GET /api/sms/log`. Wszystkie owijają dokładnie te same
wywołania `SmsService`, które już używa strona Jinja — zero nowej logiki biznesowej, tylko JSON
in/out zamiast form-POST/redirect. `templates/settings/sms.html` i jej trasy zostają nietknięte
(zasada z `plan.md` §1: zmiany backendowe są addytywne).

**Frontend:** `EmailSettingsPage` (pojedynczy formularz + test połączenia + instrukcja Gmail/
Outlook, 1:1 port), `SmsSettingsPage` (staty miesiąc/3-miesiące, formularz danych Twilio z
podglądem tokenu, panel testu, karty typów wiadomości z inline edycją — w tym wiązanie
checkbox→textarea dla placeholderów linków, 1:1 z oryginalnym `wireUrlCheckbox`, formularz
dodawania własnego typu), `SmsLogPage` (tabela + offset-paginacja, bez selektora numeru strony,
1:1 z oryginałem). Wpięte pod istniejące, już poprawne guardy w `router.tsx`
(`requireModule="invoices"` dla `/ustawienia/email`, `requireModule="settings"` dla
`/ustawienia/sms`+`/ustawienia/sms/historia` — te trasy istniały już jako `ComingSoonPage` z
poprawnymi guardami od Fazy 0/D14, tylko podmienione na realne strony).

**Decyzja D27 — brak osobnego pliku CSS per strona, jeden współdzielony `SettingsPages.css`:**
obie strony + log dzielą prawie identyczny zestaw nowych klas (`.info-card`, `.badge-pill` +
warianty, `.password-field`/`-toggle`, staty SMS) — jeden plik zamiast trzech prawie identycznych
kopii. Klasy już globalne (`.checkbox-wrapper`, `.form-textarea`, `.stat-card`/`.stat-value`,
`.table-container`/`.refined-table`, sprawdzone grepem w `styles/components.css` przed pisaniem)
celowo NIE zduplikowane.

**Odkrycie — `node_modules/` w tym worktree było nieaktualne:** `npm run build` failował na
`Cannot find module 'chart.js'`, mimo że `chart.js` jest w `package.json` (dodane przy budowie
Dashboardu, Faza 2) — `npm install` nigdy nie uruchomiony w TYM konkretnym git worktree
(`faktura_scanner_flask-full-redesign-stitch`, osobny checkout od głównego repo). `npm install`
naprawiło to (261 pakietów, 0 błędów krytycznych) — niezwiązane z tym modułem, przedwarunek do
odhaczenia dla każdej przyszłej sesji pracującej w tym samym worktree.

**Weryfikacja:** `npm run build` → 0 błędów TS, 133 moduły. `npm run lint` → 0 errors (ten sam 1
nieszkodliwy warning z Fazy 1, bez zmian). Backend: `python -m pytest tests/ -q` → **657 passed**,
0 regresji. Ręczna weryfikacja wizualna nieosiągalna w tym środowisku (patrz
[[react-migration-browser-tooling-gap]]) — jak w każdej poprzedniej Fazie 2 sesji.

### Moduł: Bilanse urlopowe — zbudowany

Audyt: `absence_balance_routes.py` (361 linii) już było **w pełni JSON** poza samym HTML-shellem
`/absence-balances` — zero zmian backendu. Jedyna złożoność jest we froncie:
`templates/absences/balances.html` (765 linii) ma per-wiersz inline-edytowalne spinboxy
(wykorzystano/limit), pole okresu, warunkowe pole "powód zmiany" (pokazuje się tylko gdy
wykorzystanie się zmieniło — backend tego wymaga przy tworzeniu korekty), przycisk zapisu
(disabled dopóki nic się nie zmieniło LUB brakuje powodu), jednopoziomowe cofnięcie (undo state
przechowywany per wiersz), i reset-do-zera z potwierdzeniem. Strona ładuje dane w nietypowy,
ale świadomie 1:1 przeportowany sposób: `/api/absence-balances/summary` zwraca słownik
`{employee_id: ...}`, ale strona używa TYLKO `Object.keys()` na nim, żeby dostać listę ID —
pełne dane per pracownik i tak przychodzą osobnym fetchem `/api/employees/<id>/absence-balances`
(N+1, ale to jest dokładnie to, co robi oryginał — nie "naprawiane" tutaj, bo backend nie zmienia
się w tym przebiegu).

**Decyzja D28 — stan wiersza jako lokalny React state w `BalanceRow.tsx`, nie w rodzicu:** oryginał
trzymał "oryginalne"/"undo" wartości w `tr.dataset.*` per DOM-wiersz. Port 1:1 tego wzorca do
Reacta: każdy `<BalanceRowView>` ma własny `useState` dla used/limit/period/reason/undoState,
komunikuje się z rodzicem (`BalancesPage`) tylko przez `onChanged(patch)` po udanym zapisie —
rodzic aktualizuje `rows` (dla statystyk/filtrów), ale NIE zarządza stanem edycji każdego wiersza
(to by wymagało przeniesienia całego `tr.dataset`-owego mikro-stanu do jednej wielkiej struktury w
rodzicu, bez korzyści — wiersze nie współdzielą stanu ze sobą).

**Decyzja D29 — `useEscapeBack('/nieobecnosci')` mimo że ta trasa jest wciąż `ComingSoonPage`:**
oryginał robi `window.location.href = '/absences'` na Escape (chyba że modal potwierdzenia otwarty
— `ConfirmProvider`'s `useEscapeClose` już poprawnie zajmuje klawisz w tym przypadku, sprawdzone w
`ConfirmProvider.tsx`). Cel wskazuje na trasę modułu "Nieobecności (wnioski)", który jest
kolejnym modułem w tym samym przebiegu (Option A, punkt 3) — link zacznie realnie działać, gdy
tamten moduł zostanie zbudowany później w tej samej sesji, zamiast wskazywać donikąd.

**Weryfikacja:** `npm run build` → 0 błędów TS, 137 modułów. `npm run lint` → 0 errors (ten sam
nieszkodliwy warning). Backend bez zmian — `pytest` nie uruchamiany ponownie.

### Moduł: Nieobecności (wnioski) — zbudowany częściowo, świadomy zakres

Audyt: `absence_routes.py` (598 linii) miało dwa HTML-shelle (`/my-absences` self-service,
`/absences` 3-tabowy widok zarządzania — `templates/absences/my.html` 403 linii +
`templates/absences/management.html` 1086 linii + `static/js/absences.js` 1060 linii). Większość
mutacji zarządzania (approve/reject/approve-force/cancel-approved/manual create/update/delete/
hard-delete/kategorie CRUD) była **już JSON**. Trzy self-service akcje (submit/cancel/
cancel-approved) były **form-POST+redirect+flash** — jedyna realna luka backendu tego modułu.

**Decyzja D30 — nowe `/api/my-absences*` + `/api/absences/management` jako siostrzane JSON:**
dodano `GET/POST /api/my-absences[...]` (submit/cancel/cancel-approved, mirror `_svc()` wywołań z
Jinja routes) i `GET /api/absences/management` (mirror `management_index()`'s logiki: te same
gałęzie ról superuser/admin vs. przełożony). Nowy `_serialize_absence()` helper konwertuje
date/time/datetime pola na stringi przed `jsonify` (te same pola, które Jinja tylko domyślnie
stringify'uje przez `{{ }}`) — bez tego `jsonify()` serializowałby datetime do dziwnego formatu
RFC-822 zamiast ISO.

**Decyzja D31 — świadomie ODŁOŻONE (nie "zapomniane"), udokumentowane tutaj:**
1. **Tab "Kategorie"** (`management.html`'s trzeci tab, admin-only CRUD kategorii + balance-config)
   — osobna, samodzielna funkcja, JSON już gotowy (`/absences/categories*`), ale dodaje kolejną
   pełną formę z 8 polami (typ/śledzenie/okres/reset/limit) do w tej sesji i tak już bardzo długiego
   modułu.
2. **Per-konflikt reassign/reschedule** w modalu zatwierdzania — oryginał ma pełny multi-step state
   machine (`showConflictModal`/`_renderReassignStep`/`_renderRescheduleStep`, ~400 linii JS,
   oznaczone w kodzie źródłowym jako "Faza 3"). To DOKŁADNIE ta sama funkcja, którą
   `module-inventory.md`'s "Korekta zakresu — Wizyty + Kalendarz" już wcześniej świadomie odłożyła
   z drugiej strony (integracja Wizyt z Nieobecnościami) — spójna decyzja, nie nowa. Zbudowany widok
   pokazuje listę konfliktów + "Zatwierdź mimo to"/"Odrzuć", bez per-wiersz akcji naprawy.
3. **Historia rozwiązań konfliktów** (`/absences/<id>/resolutions`, read-only) — zależna od #2,
   bez sensu budować widoku historii dla akcji, których nie da się jeszcze wykonać.
4. **Hard-delete superusera** (nieobecności i kategorie, `/permanent`) — narzędzie porządkowe do
   czyszczenia danych testowych, niski priorytet względem codziennego workflow.
5. **Balance-hints w tabeli wniosków** (`(3.0/5d)` przy nazwisku pracownika) — kosmetyczna adnotacja
   z osobnego fetcha `/api/absence-balances/summary`, bez wpływu na funkcjonalność.

**Decyzja D32 — pre-submit conflict preview uproszczony do `useConfirm()` zamiast bespoke tabeli:**
oryginał (`my.html`) pokazuje pełną tabelę kolidujących wizyt w customowym modalu przed złożeniem
wniosku. Port używa `useConfirm()` z tekstowym podsumowaniem (liczba konfliktów + do 3 przykładów) —
ta sama nieblokująca semantyka (zero konfliktów = submit prosto, konflikty = pytanie o potwierdzenie),
bez budowania nowego bespoke komponentu tabeli-w-modalu dla czysto informacyjnego kroku.

**Weryfikacja:** `npm run build` → 0 błędów TS, 141 modułów. `npm run lint` → 0 errors (ten sam
nieszkodliwy warning). Backend: `python -m pytest tests/ -q` → **657 passed**, 0 regresji (uruchomione
po zmianach w `routes/absence_routes.py` — nowe endpointy, zero zmian w istniejących).

### Moduł: Użytkownicy + Role (RBAC) — zbudowany

Audyt: `routes/users/routes.py` (325 linii) i `routes/roles/routes.py` (170 linii) miały mieszankę
CRUD JSON (`/system/users/api*`, `/system/roles/api*` — już istniejące, kompletne) + 6 czystych
HTML-shelli (`users_list`/`create_user`/`edit_user`, `roles_list`/`create_role`/`edit_role`), z
których każdy przekazuje do szablonu dropdown-data (dostępni pracownicy, przypisywalne role,
lista modułów+etykiety, szczegóły uprawnień jednej roli) niedostępne jako JSON. Luka mniejsza niż
etykieta "Częściowa" sugerowała — sam CRUD (najbardziej ryzykowna część: walidacja unikalności
maila, blokada edycji/kasowania kont superusera przez non-superusera, blokada nadania roli
superuser) był już kompletny i przetestowany logiką backendu; brakowało tylko przezroczystych
"assemble dropdown data as JSON" siostrzanych endpointów.

**Decyzja D33 — 4 nowe endpointy `GET .../form-options` i `.../  <id>` (GET), zero zmian w
istniejących CRUD:** `GET /system/users/api/form-options` (available_employees + roles, filtrowane
tak samo jak `create_user()`/`edit_user()` — non-superuser nigdy nie widzi roli "superuser" jako
opcji), `GET /system/users/api/<id>` (user + linked_employee, do pre-fill formularza edycji — samo
`GET /system/users/api` [lista] już miało te dane per-wiersz, ale osobny endpoint jest czystszy niż
filtrowanie całej listy po stronie klienta dla jednego rekordu), `GET /system/roles/api/form-options`
(all_modules+module_display_names — statyczne dane z `role_repository.py`, ale serwowane z backendu
zamiast kopiowane na sztywno we froncie, żeby nie mogły się rozjechać), `GET /system/roles/api/<id>`
(role + pełny `permissions` detail, do pre-fill formularza edycji — `GET /system/roles/api` [lista]
już zwracał `permissions_detail` per rola, ale znowu: dedykowany endpoint czytelniejszy niż
filtrowanie listy).

**Odkrycie D-Sec5 — luka w `app.py`'s `AppError` handler wpływająca na jakość komunikatów błędów:**
`app.py`'s `handle_app_error()` zwraca JSON tylko gdy `request.path.startswith('/api/')`. Oba
blueprinty RBAC są zamontowane pod `/system/users/api/*` i `/system/roles/api/*` — **nie
zaczynają się od `/api/`** — więc każdy `raise ValidationError(...)`/`ConflictError(...)`/
`PermissionDeniedError(...)` w tych dwóch plikach (a WSZYSTKIE ścieżki błędów w obu plikach
przechodzą przez `raise AppError`, nie przez `return jsonify({success:false})`, 200) zwracał
**stronę HTML błędu 500 zamiast JSON**, nawet gdy wywołujący jawnie oczekuje JSON (fetch() w
oryginalnym `create.html`/`edit.html`, i `usersApi`/`rolesApi` w Reakcie). Efekt praktyczny:
`resp.json()` w oryginalnym Jinja rzuca `SyntaxError` (niezłapany — użytkownik nie widzi żadnego
komunikatu), a `lib/api/client.ts`'s `request()` w Reakcie **miał na to obronę** (sprawdza
`content-type` przed `JSON.parse`) — degradował się łagodnie do `ApiError('Błąd serwera (400)')`
zamiast precyzyjnego `"Email jest już zajęty"` itp. **To był realny, przedmigracyjny bug w
`app.py`, nie coś wprowadzone przez ten port** — odkryty przy budowie tego modułu, bo to pierwszy
moduł React, którego backend leży POZA prefiksem `/api/*` (każdy inny moduł Fazy 2 mapuje się na
`routes/api_routes.py`, montowany pod `/api`).

**Naprawione tego samego dnia (2026-08-24, na wyraźną prośbę użytkownika po dostarczeniu
podsumowania sesji):** `handle_app_error()` i `handle_csrf_error()` (ta sama luka, ten sam
sprawdzający warunek — `CSRFError` ma identyczny problem, niezauważony wcześniej bo nie było go w
zakresie audytu RBAC, ale naprawiony razem przy tej samej okazji) teraz wołają wspólny
`_wants_json_error()`, sprawdzający `/api/` jako **segment ścieżki** (`re.compile(r'(?:^|/)api(?:/|$)')`),
nie tylko prefiks. Zweryfikowane dwustopniowo przed commitem: (1) w Pythonie wprost przeciw 16
reprezentatywnym ścieżkom (wszystkie prawdziwe trasy `/system/users/api*`/`/system/roles/api*` →
`True`, wszystkie prawdziwe strony Jinja tych samych blueprintów typu `/system/users/create` →
`False`, żadnej zmiany zachowania dla już poprawnie działających `/api/*`); (2) `grep` po WSZYSTKICH
`.route()` w `routes/*.py` zawierających `api` — każde trafienie to legitymalny endpoint JSON, zero
fałszywych trafień na stronie HTML. Zasięg naprawy: tylko `users_bp`/`roles_bp` (jedyne blueprinty,
gdzie `api` jest segmentem wewnętrznym/końcowym, nie prefiksem — wszystkie inne blueprinty montują
JSON-owe trasy albo pod `/api` (rejestracja) albo z dosłownym `/api/...` w samym `@bp.route(...)`,
więc już pasowały do starego prefiksowego sprawdzenia i nie zmieniają zachowania).
`python -m pytest tests/ -q` → **657 passed**, 0 regresji. Docstring w `usersApi` (`lib/api/
users.ts`) zaktualizowany — nie opisuje już tego jako otwartej luki.

**Frontend:** `UsersListPage` (lista+search, superuser-only reset hasła przez `Modal`, delete z
regułami `isSelf`/`canDelete` 1:1 z backendem), `UserFormPage` (create/edit, edit ma osobną kartę
zmiany hasła — dwa niezależne submity, jak oryginał), `RolesListPage` (lista z kropkami uprawnień —
`module-dot-on`/`-off`, delete niechronionej roli), `RoleFormPage` (create: prosty toggle
has_access per moduł; edit: pełna siatka has_access/read_only/own_data + sub-flagi
`can_edit_price_history`[services]/`can_send_sms`[appointments], sub-flagi disabled gdy has_access
off — 1:1 z oryginalnym `flags_${m}.classList.toggle('disabled', !checked)`).

**Weryfikacja:** `npm run build` → 0 błędów TS, 149 modułów. `npm run lint` → 0 errors (jeden
nowy warning znaleziony i naprawiony od razu — `useMemo` zależący od `usersState.data ?? []`
tworzącego nową referencję co render, poprawione przez odczyt `usersState.data` bezpośrednio
wewnątrz callbacku zamiast przez pośrednią zmienną `users`). Backend: `python -m pytest tests/ -q`
uruchomiony po zmianach w `routes/users/routes.py`+`routes/roles/routes.py` (4 nowe GET-only
endpointy, zero zmian w istniejących) — **657 passed**, 0 regresji.

### Moduł: Analityka — KPI Matrix zbudowany, główny dashboard i `/income` świadomie odłożone

Audyt (`routes/analytics_routes.py`, 573 linii, 30 endpointów) ujawnił, że etykieta "Prawdopodobnie
kompletna / Wysoka (wykresy)" z `plan.md` §0 była **trzecią z rzędu niedoszacowaną złożonością**
(po Sprzedawcach i Usługach z Fazy 2) — i największą dotąd: to nie jedna strona, tylko **trzy**
(`/analiza-biznesowa` — 449+1475 linii, 10 wykresów Chart.js + custom heatmapa + kilka tabel +
stanowa nawigacja okresów; `/wskazniki-biznesowe` — 198+351 linii, znacznie mniejsza; `/income` —
155 linii, **całkowicie nieznana wcześniej trzecia strona**, nigdzie niewymieniona w żadnym
dotychczasowym dokumencie planu). Pełny opis w `module-inventory.md`'s nowej sekcji "Korekta
zakresu — Analityka / KPI / Przychody", razem z gotowymi promptami audytowymi dla obu odłożonych
stron.

**Decyzja D34 — zbudowano wyłącznie `/wskazniki-biznesowe`, świadomie odłożono resztę:** o 3-4 nad
ranem, bez dostępnych narzędzi przeglądarkowych do weryfikacji wizualnej (patrz
[[react-migration-browser-tooling-gap]]), wdrożenie 10-wykresowego dashboardu na ślepo byłoby
najwyższym ryzykiem tej całej sesji — błąd w jednym z 10 wykresów byłby niewidoczny aż do
pierwszego ręcznego testu użytkownika, dokładnie tak jak przy Wizytach/Fakturach (7+5 usterek UI
znalezionych dopiero przy pierwszym realnym kliknięciu, 2026-08-19). KPI Matrix jest znacznie
mniejsza, samodzielna, i jej jeden typ wykresu (bar+line combo, rozwijany per wiersz) jest bliżej
sprawdzonych wzorców (`MonthlyChart.tsx`, `PriceHistorySparkline.tsx`) niż 10 różnych typów
wykresów dashboardu.

**Frontend (`frontend/src/pages/analytics/`):** `KpiMatrixPage` (nawigacja rok wstecz/w
przód/picker/"Aktualny", sticky header, tabela 18 kolumn z `table-layout: fixed`), `KpiIndicatorRow`
(rowspan'owana komórka procesu na pierwszym wierszu grupy, kolorowanie status-good/-bad per
komórka wg `direction`/`target`, obsługa `unavailable_note` dla wskaźników bez danych źródłowych),
`KpiIndicatorChart` (rozwijany wykres bar+line combo per wiersz — Chart.js `BarController`+
`LineController` zarejestrowane razem, wzorem `MonthlyChart.tsx`/`PriceHistorySparkline.tsx`),
`kpiFormat.ts` (współdzielona logika formatowania — jedno miejsce decydujące "jak wydrukować tę
liczbę", żeby tabela i wykres nigdy się nie rozjechały, 1:1 z oryginalnym
`getFormatter()`/`fmtValue()`/`fmtPln()` z `kpi_matrix.js`). Fixed-position hover-tooltip (JS
`getBoundingClientRect()`-owy, nie CSS `:hover`) ported 1:1 — ucieka z `overflow:auto` tabeli,
tak jak w oryginale.

Backend: **bez zmian** — `/api/analytics/kpi-matrix` (mounted pod `analytics_bp`, `url_prefix='/api'`
w `app.py`) był już w pełni JSON, error-responses też poprawnie JSON (w przeciwieństwie do
`users`/`roles` blueprintów z D-Sec5 wcześniej w tej sesji — ten akurat leży POD `/api/*`).

**Weryfikacja:** `npm run build` → 0 błędów TS, 155 modułów. `npm run lint` → 0 errors (ten sam
jeden nieszkodliwy warning, bez zmian). Backend bez zmian — `pytest` nie uruchamiany ponownie.
Ręczna weryfikacja wizualna nieosiągalna w tym środowisku, jak w każdym poprzednim module tej
sesji.

### Moduł: Import danych (caldis.pl) — zbudowany, ostatni moduł Option A

Audyt: `routes/import_routes.py` (368 linii, 8 endpointów, w pełni JSON pod `import_bp`
mounted `url_prefix='/api'`) — nazwa w `module-inventory.md` ("Import danych / historia / OCR
upload") była myląca. To **nie jest faktura-OCR** (ten temat, pod `routes/upload_routes.py`,
zostaje odłożony w ramach modułu Faktury, tak jak było już ustalone przy jego budowie 2026-08-18)
— to osobne narzędzie admin-only: scraper rezerwacji z **caldis.pl** (legacy/konkurencyjny system,
z którego salon migruje dane) przez Playwright, z SSE-streamem postępu, zarządzaniem sesją, i
niezależnym skanem konfliktów wizyt (duplikaty po przełożeniu terminu). Jeden self-contained
szablon (`templates/data_import/index.html`, 679 linii, cały JS inline — brak osobnego pliku
`static/js/`), 3x mniejszy niż zdeferowany dashboard Analityki.

**Decyzja D35 — reconnect-session ported 1:1 mimo fundamentalnego ograniczenia:** `POST
/api/import/reconnect-session` odpala **headed** (widoczną) przeglądarkę Playwright **na maszynie
serwera Flask**, czeka do 120s na ręczne zalogowanie w tym oknie, i zapisuje sesję do pliku. To z
natury operacja wymagająca fizycznej obecności przy konsoli serwera — żadna zdalna sesja
przeglądarki (w tym ta React SPA, niezależnie jak dobrze zaimplementowana) nie może tego
interaktywnie dokończyć zamiast administratora przy serwerze. Port jest mimo to wierny 1:1:
przycisk wysyła request, endpoint zwraca 503 na środowiskach headless (Linux bez `$DISPLAY`) z
komunikatem `python scripts/import_appointments_playwright.py --headed` — dokładnie ta sama
architektura co oryginał, żadna próba "naprawienia" tego ograniczenia w Reakcie, bo nie jest ono
frontendowe.

**Decyzja D36 — natywny `EventSource` z `withCredentials: true`, nie owinięty w `lib/api/client.ts`:**
`EventSource` nie wspiera custom headerów (nie da się dołączyć `X-Requested-With`) ani nie wysyła
cookies domyślnie — stąd `new EventSource(url, { withCredentials: true })` bezpośrednio w
`DataImportPage.tsx`, jedyne miejsce w całej migracji poza samym `client.ts`, gdzie request idzie
z pominięciem współdzielonego wrappera (uzasadnione: SSE to fundamentalnie inny transport niż
fetch, `client.ts`'s abstrakcja go nie obejmuje). `@login_required` na `import_stream` polega na
cookie sesji, nie na `X-Requested-With`, więc `withCredentials: true` samo wystarcza.

**Frontend (`frontend/src/pages/dataImport/`):** `DataImportPage` (karta statusu sesji, formularz
importu, log-panel z auto-scroll, karta wyniku, tabela historii), `ConflictScanSection` (osobny
komponent, własny stan — read-only skan + destructive-ale-odwracalne zastosowanie przez
`useConfirm()`). Typy i klient API w `types/dataImport.ts`/`lib/api/dataImport.ts`.

**Weryfikacja:** `npm run build` → 0 błędów TS (2 nieużywane importy złapane i naprawione od razu
— `Icon`/`toast` w `ConflictScanSection.tsx`, nieużyte po finalnym kształcie komponentu), 159
modułów. `npm run lint` → 0 errors (ten sam jeden nieszkodliwy warning, bez zmian). Backend bez
zmian — `pytest` nie uruchamiany ponownie.

**To zamyka wszystkie 7 modułów z listy "Wymaga audytu" z `module-inventory.md`** (Ustawienia
e-mail/SMS, Bilanse urlopowe, Nieobecności [częściowo], Użytkownicy+Role RBAC, Analityka/KPI
[częściowo — tylko KPI Matrix], Import danych) — Option A z tej sesji zakończona. Świadomie
odłożone kawałki (udokumentowane per moduł powyżej): tab Kategorie + per-konflikt reassign/
reschedule + historia rozwiązań w Nieobecnościach; główny dashboard Analityki (10 wykresów +
heatmapa) + nowo odkryta strona `/income`. Oba mają gotowe prompty audytowe w
`module-inventory.md` dla następnej sesji.

---

## 2026-08-24 (po południu) — Implementacja świadomie odłożonych kawałków, na wyraźną prośbę
użytkownika ("go with deffered tasks implementation")

Tryb: ten sam co Option A — autonomiczny, decyzje własne, test+commit+push per jednostka pracy,
bez przystanków. Kolejność: od najmniejszych/samodzielnych kawałków w górę.

### Decyzja D37 — Nieobecności: tab Kategorie + superuser hard-delete (absencje i kategorie)

Audyt przed budową: `create_category()`/`update_category()`/`delete_category()`/
`hard_delete_category()` (`/absences/categories*`) były **już w pełni JSON** — nigdy nie
przechodziły przez Jinja-render, w przeciwieństwie do reszty modułu. Podobnie
`hard_delete_absence()` (`/absences/<id>/permanent`). **Zero zmian backendu potrzebnych do tej
całej jednostki pracy** — czysty frontend.

Odkrycie po drodze: `app.py`'s globalny `PostgreSQLJSONProvider` (linia ~70) już automatycznie
serializuje `datetime`/`date`/`time` → ISO i `Decimal` → float dla KAŻDEGO `jsonify()` w całej
aplikacji — co oznacza, że `_serialize_absence()` helper dodany wcześniej w tej sesji (moduł
Nieobecności, Option A #3) był technicznie zbędny (globalny provider i tak by to zrobił). Nie
usunięty — jest jawny, czytelny, i nieszkodliwy; usuwanie działającego, jawnego kodu tylko po to,
żeby polegać na milczącym mechanizmie globalnym, byłoby regresją czytelności bez żadnej korzyści.

**Frontend (`frontend/src/pages/absences/`):**
- `CategoryFormModal.tsx` (nowy plik) — formularz tworzenia/edycji kategorii, port
  `openCategoryForm()` z `static/js/absences.js` (ręcznie budowany `Modals.show()` tam) na
  właściwy kontrolowany formularz React w `Modal`. Warunkowa siatka pól "śledzenie bilansu"
  (okres/reset/limit/próg ostrzeżenia) pokazuje/chowa się jak w oryginale.
- `AbsencesManagementPage.tsx` rozszerzony: trzeci tab "Kategorie" (gated
  `auth.hasModuleAccess('absences')`, 1:1 z oryginalnym `{% if user_permissions.absences %}`),
  nowy komponent `CategoriesTab` (tabela z typem full-day/hourly, śledzony tak/nie, okres/reset/
  limit, status aktywna/usunięta, akcje edytuj/usuń dla aktywnych, usuń-trwale dla już-usuniętych
  gdy superuser). `reload()` teraz też zapisuje `r.categories` (już zwracane przez
  `GET /api/absences/management` od Option A #3, po prostu nieużywane do tej pory) do nowego stanu
  `categoriesWithDeleted` — osobnego od istniejącego `categories` (tylko aktywne, zasila dropdown
  formularza manualnego, zapytanie `/api/absence-categories` bez zmian).
- Hard-delete nieobecności: nowy hover-reveal przycisk (`.action-icon-btn.danger-reveal`, 1:1 z
  oryginalnym wzorcem CSS z `management.html`, teraz przeniesiony do `AbsencesPages.css` jako
  reużywalna klasa) na KAŻDYM wierszu tabeli Wnioski, tylko gdy `isSuperuser` — zgodnie z
  oryginałem (`hard_delete_absence` nie wymaga wcześniejszego soft-delete, więc dostępny
  niezależnie od statusu wniosku). Manual/L4 tab celowo NIE dostał tego przycisku — oryginał też
  go tam nie miał (tylko zwykłe "Usuń" = soft-delete).

**Weryfikacja:** `npm run build` → 0 błędów TS, 160 modułów. `npm run lint` → 0 errors (ten sam
jeden nieszkodliwy warning). Backend bez zmian — `pytest` nie uruchamiany ponownie.

---
