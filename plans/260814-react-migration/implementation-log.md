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
- [ ] 4 motywy przetestowane wizualnie — **ZAREZERWOWANE dla ręcznego testu** (zgodnie z
      poleceniem użytkownika).
- [ ] Klawiatura: sortowanie nagłówków (real `<button>`), formularz, modal potwierdzenia — kod
      zbudowany z pełną intencją dostępności (prawdziwe `<button>` wszędzie, `aria-sort`,
      focus-trap w confirm, Ctrl+S/Esc), ale **ZAREZERWOWANE dla ręcznego testu klawiaturą**.
- [ ] Czas budowy — patrz sekcja wyżej (nie zmierzony, brak narzędzia).

---
