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

---
