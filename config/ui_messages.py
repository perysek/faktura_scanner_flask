"""
Centralized UI message catalog with switchable tone sets.

Every user-facing microcopy string (flash messages, toasts, confirm/alert
modals, validation hints) is identified by a stable id and stored here with
multiple *tone variants*:

    previous  — original neutral pre-snark wording (GitHub history)
    current   — first savage/teasing pass (Pass 1 + Pass 2, what shipped live)
    new       — refined register: savage where the user is at fault, calming
                for backend/permission/non-floppiness-auth failures

The single source of truth is Python (this module). The JS side never reads
this file directly — the active tone's flat {id: text} map is injected into
``base.html`` as ``window.UI_MESSAGES`` by the ``inject_globals`` context
processor, and resolved client-side by ``MSG()`` (static/js/messages.js).

Switching the whole app's voice is one variable: ``ACTIVE_TONE``. Wiring it to
a per-user setting later (settings page) is a one-line change in ``flat_map()``.

Tone rule (decided 2026-06-23):
  - User floppiness (empty required field, bad NIP, backwards date range,
    nothing selected, wrong file type, AND login/auth errors caused by the
    user — missing creds, password mismatch, weak password, not-logged-in)
    → SAVAGE.
  - Success / confirm / delete / info about the user's own choices → SAVAGE.
  - Backend failure the user can't control (server down, 500, connection drop,
    DB load fail, backend-caused save failures), permission-denied, and
    non-floppiness auth (session expiry, dead reset link) → CALMING.

Interpolation uses ``{param}`` placeholders (NOT f-strings / ${}) so the exact
same template resolves identically in Python and JS:

    msg('auth.login.welcome', name=user.full_name)      # Python
    MSG('auth.login.welcome', { name: userName })        # JS
"""

# Active tone for the whole app. One of: 'previous' | 'current' | 'new'.
# Later: read per-user preference here for a settings-page tone switch.
ACTIVE_TONE = 'new'

# Fallback order when a variant is missing for the active tone.
_FALLBACK_ORDER = ('new', 'current', 'previous')

# ---------------------------------------------------------------------------
# Catalog. id -> {previous, current, new}.  {param} placeholders interpolated.
# ---------------------------------------------------------------------------
MESSAGES = {
    # ── Auth: login / logout ────────────────────────────────────────────────
    'auth.login.missing_credentials': {
        'previous': 'Email i hasło są wymagane',
        'current':  'Email i hasło. Oba. Naprawdę.',
        'new':      'Email ORAZ hasło. Dwa pola. Naprawdę aż tak trudno?',
    },
    'auth.login.welcome': {
        'previous': 'Witaj, {name}!',
        'current':  'O, {name}! Patrzcie kto wrócił.',
        'new':      'No nareszcie, {name}. Faktury same się nie wprowadzą.',
    },
    'auth.logout': {
        'previous': 'Zostałeś wylogowany',
        'current':  'Wylogowano. Idź już, odpocznij od tych faktur.',
        'new':      'Wylogowano. Zmykaj — faktury poczekają do jutra.',
    },
    # ── Auth: change password (user floppiness → savage) ────────────────────
    'auth.change_password.missing_fields': {
        'previous': 'Wszystkie pola są wymagane',
        'current':  'Wypełnij wszystkie pola. Tak, wszystkie.',
        'new':      'Wszystkie pola. Każde jedno. Tak, to też.',
    },
    'auth.change_password.mismatch': {
        'previous': 'Nowe hasła nie pasują do siebie',
        'current':  'Te dwa hasła to nie ta sama para. Spróbuj jeszcze raz.',
        'new':      'Dwa różne hasła wklepałeś. Skup się i wpisz to samo dwa razy.',
    },
    'auth.change_password.success': {
        'previous': 'Hasło zostało zmienione',
        'current':  'Hasło zmienione. Tym razem je zapamiętaj, co?',
        'new':      'Hasło zmienione. Tym razem zapisz je gdzieś, mistrzu pamięci.',
    },
    # ── Auth: password reset ────────────────────────────────────────────────
    'auth.reset.weak_password': {
        'previous': 'Hasło musi mieć co najmniej 8 znaków.',
        'current':  'Minimum 8 znaków. „1234" to nie hasło, to zaproszenie dla włamywacza.',
        'new':      '8 znaków minimum. Twoje hasło złamałby 5-latek po ciemku. Wysil się.',
    },
    'auth.reset.mismatch': {
        'previous': 'Hasła nie pasują do siebie.',
        'current':  'Hasła się nie zgadzają. Skup się na chwilę.',
        'new':      'Hasła się nie zgadzają. Dwa razy to samo — naprawdę nie tak trudno.',
    },
    'auth.reset.success': {
        'previous': 'Hasło zostało zmienione. Możesz się teraz zalogować.',
        'current':  'Nowe hasło ustawione. Loguj się i tym razem go nie zgub.',
        'new':      'Nowe hasło gotowe. Loguj się — i tym razem go nie zgub.',
    },
    # link expired = time passed, NOT user fault → CALMING
    'auth.reset.link_dead': {
        'previous': 'Link wygasł lub został już użyty. Spróbuj ponownie.',
        'current':  'Ten link już nie żyje — wygasł albo ktoś go zużył. Bierz nowy.',
        'new':      'Ten link już wygasł — to normalne. Poproś o nowy i działamy dalej.',
    },
    # ── Auth: access guards ─────────────────────────────────────────────────
    # not-logged-in = floppiness → SAVAGE
    'auth.guard.login_required': {
        'previous': 'Musisz być zalogowany',
        'current':  'Najpierw się zaloguj. Nie ma drogi na skróty.',
        'new':      'Najpierw się zaloguj. Na skróty się nie da, sprytny inaczej.',
    },
    # session/CSRF expiry = time, not fault → CALMING
    'auth.session.expired': {
        'previous': 'Sesja wygasła. Odśwież stronę i spróbuj ponownie.',
        'current':  'Sesja Ci się zdrzemnęła. Odśwież stronę i do dzieła.',
        'new':      'Sesja się zdrzemnęła — bywa. Odśwież stronę i wracaj, nic nie przepadło.',
    },
    # ── Permission denied → CALMING ─────────────────────────────────────────
    'auth.permission.role_denied': {
        'previous': 'Brak uprawnień do tej strony',
        'current':  'Tu nie wejdziesz. Twoja rola na to nie pozwala.',
        'new':      'Ta strona jest poza Twoim zasięgiem — jeśli to pomyłka, daj znać szefowi.',
    },
    'auth.permission.module_denied': {
        'previous': 'Brak dostępu do modułu: {module}',
        'current':  'Moduł „{module}" nie dla Ciebie. Pogadaj z szefem.',
        'new':      'Nie masz dostępu do modułu „{module}" — jeśli to pomyłka, odezwij się do szefa.',
    },
    'auth.permission.absences_denied': {
        'previous': 'Brak uprawnień do zarządzania nieobecnościami',
        'current':  'Nieobecności to nie Twoja działka. Ręce przy sobie.',
        'new':      'Zarządzanie nieobecnościami jest poza Twoim zasięgiem — w razie potrzeby poproś szefa.',
    },
    'auth.permission.read_only': {
        'previous': 'Masz dostęp tylko do odczytu w module: {module}',
        'current':  'Moduł „{module}" masz tylko do podglądu — zmieniać go nie możesz.',
        'new':      'W module „{module}" masz dostęp tylko do odczytu — jeśli potrzebujesz edycji, poproś szefa.',
    },
    'users.edit.owner_denied': {
        'previous': 'Brak uprawnień do edycji konta właściciela',
        'current':  'Konta właściciela nie ruszasz. Próbowałeś, widzieliśmy.',
        'new':      'Konta właściciela nie da się stąd edytować — to ustawienie celowe.',
    },
    # ── Modal engine defaults (user action confirms → SAVAGE) ───────────────
    'modal.confirm.title': {
        'previous': 'Potwierdzenie',
        'current':  'Na pewno na pewno?',
        'new':      'No to jak, decydujesz się?',
    },
    'modal.confirm.message': {
        'previous': 'Czy na pewno?',
        'current':  'No to jak — robimy to, czy się rozmyślasz?',
        'new':      'Klikasz, czy się jeszcze wahasz? Nie mam całego dnia.',
    },
    'modal.confirm.confirm_btn': {
        'previous': 'Potwierdź',
        'current':  'No dawaj',
        'new':      'No dawaj',
    },
    'modal.confirm.cancel_btn': {
        'previous': 'Anuluj',
        'current':  'Jednak nie',
        'new':      'Jednak nie',
    },
    'modal.alert.title': {
        'previous': 'Informacja',
        'current':  'Słuchaj no',
        'new':      'Słuchaj no',
    },
    'modal.loading.title': {
        'previous': 'Proszę czekać',
        'current':  'Chwila, pracuję',
        'new':      'Chwila, pracuję',
    },
    'modal.loading.message': {
        'previous': 'Przetwarzanie...',
        'current':  'Mielę dane, nie poganiaj...',
        'new':      'Mielę dane, nie poganiaj...',
    },
    # generic delete confirm (confirmDelete / confirm_modal defaults) → SAVAGE
    'modal.delete.title': {
        'previous': 'Potwierdź usunięcie',
        'current':  'Kasujemy na amen?',
        'new':      'Kasujemy na amen?',
    },
    'modal.delete.message': {
        'previous': 'Czy na pewno chcesz usunąć "{item}"? Ta operacja jest nieodwracalna.',
        'current':  'Skasować „{item}" na zawsze? Tego się nie odklika, nie ma „ctrl+z".',
        'new':      'Kasujesz „{item}" na amen. „Ctrl+Z" nie zadziała, więc bądź pewny.',
    },
    'modal.delete.confirm_btn': {
        'previous': 'Usuń',
        'current':  'Kasuj',
        'new':      'Kasuj',
    },
    # ── Shared backend failure (server unreachable, ~15 call sites) → CALMING ─
    'error.server.unreachable': {
        'previous': 'Błąd połączenia z serwerem',
        'current':  'Serwer nie odpowiada. Chyba się obraził.',
        'new':      'Serwer się na chwilę zaciął — bez paniki, spróbuj ponownie za moment.',
    },

    # ════════════════════════════════════════════════════════════════════════
    # Increment 2 — long-tail toasts. Shared ids reused across call sites.
    # ════════════════════════════════════════════════════════════════════════

    # ── Common / shared (backend failures → CALMING; clipboard → light) ──────
    'common.save_error': {  # prefix + error.message
        'previous': 'Błąd zapisu: ',
        'current':  'Zapis się wyłożył: ',
        'new':      'Zapis nie przeszedł — to nie Ty. Spróbuj ponownie. Szczegóły: ',
    },
    'common.update_error': {  # prefix + error.message
        'previous': 'Błąd aktualizacji: ',
        'current':  'Aktualizacja się wyłożyła: ',
        'new':      'Aktualizacja nie doszła — spróbuj jeszcze raz za moment. Szczegóły: ',
    },
    'common.load_error': {  # prefix + error.message
        'previous': 'Błąd ładowania danych: ',
        'current':  'Dane nie dojechały: ',
        'new':      'Dane się nie wczytały — odśwież za chwilę. Szczegóły: ',
    },
    'common.delete_error': {  # prefix + error.message
        'previous': 'Błąd usuwania: ',
        'current':  'Nie chce się usunąć: ',
        'new':      'Usunięcie nie przeszło — spróbuj ponownie. Szczegóły: ',
    },
    'common.data_failed': {  # full string, generic load fail
        'previous': 'Błąd ładowania danych',
        'current':  'Dane się nie wczytały. Kaprys serwera.',
        'new':      'Dane się nie wczytały — odśwież stronę za moment.',
    },
    'common.clipboard_pasted': {
        'previous': 'Wklejono ze schowka',
        'current':  'Wklejone. Schowek się przydał.',
        'new':      'Wklejone ze schowka. Sprytnie.',
    },
    'common.clipboard_denied': {
        'previous': 'Nie można odczytać schowka',
        'current':  'Schowek zamknięty na cztery spusty.',
        'new':      'Nie udało się odczytać schowka — pozwól przeglądarce na dostęp i spróbuj ponownie.',
    },
    'common.validation_errors': {  # prefix + joined messages
        'previous': 'Błędy walidacji: ',
        'current':  'Walidacja się czepia: ',
        'new':      'Walidacja się czepia, i słusznie. Popraw: ',
    },
    'common.warnings': {  # prefix + joined warnings
        'previous': 'Ostrzeżenia: ',
        'current':  'Drobne zastrzeżenia: ',
        'new':      'Drobne zastrzeżenia, rzuć okiem: ',
    },
    'common.save_generic_failed': {  # full-sentence fallback after `||`
        'previous': 'Błąd zapisu',
        'current':  'Zapis się nie udał. Bywa.',
        'new':      'Zapis nie przeszedł — to nie Ty, spróbuj ponownie za moment.',
    },
    'common.delete_generic_failed': {  # full-sentence fallback after `||`
        'previous': 'Błąd usuwania',
        'current':  'Nie udało się usunąć',
        'new':      'Usunięcie nie przeszło — spróbuj ponownie za moment.',
    },

    # ── Absences (user actions → SAVAGE) ────────────────────────────────────
    'absence.approved':          {'previous': 'Wniosek zatwierdzony', 'current': 'Wniosek klepnięty ✔', 'new': 'Wniosek klepnięty. Następny!'},
    'absence.approved_conflict': {'previous': 'Wniosek zatwierdzony (mimo konfliktów)', 'current': 'Wniosek klepnięty — mimo że terminy się gryzą', 'new': 'Klepnięte, choć terminy się gryzą. Twoja decyzja, twój ból głowy.'},
    'absence.rejected':          {'previous': 'Wniosek odrzucony', 'current': 'Wniosek odrzucony. Bez sentymentów.', 'new': 'Odrzucony. Bez łez.'},
    'absence.deleted':           {'previous': 'Nieobecność usunięta', 'current': 'Nieobecność wykasowana', 'new': 'Nieobecność wykasowana. Czysto.'},
    'absence.cancelled_freed':   {'previous': 'Nieobecność anulowana — sloty zwolnione', 'current': 'Nieobecność anulowana — sloty znów wolne', 'new': 'Anulowane — sloty znów wolne, kalendarz odetchnął.'},
    'absence.category_deleted':  {'previous': 'Kategoria usunięta', 'current': 'Kategoria poszła do kosza', 'new': 'Kategoria w koszu. Następna.'},
    'absence.saved':             {'previous': 'Nieobecność zapisana', 'current': 'Nieobecność zapisana. Ktoś tu planuje wolne.', 'new': 'Zapisane. Ktoś tu sprytnie planuje wolne.'},
    'absence.saved_conflicts':   {'previous': 'Nieobecność zapisana. Uwaga: {count} kolidujących wizyt.', 'current': 'Nieobecność zapisana. Uwaga: {count} kolidujących wizyt.', 'new': 'Zapisane, ale uwaga: {count} wizyt się gryzie z terminem.'},
    'absence.fields_required':   {'previous': 'Uzupełnij wszystkie wymagane pola', 'current': 'Wypełnij wymagane pola. Te z gwiazdką nie są dla ozdoby.', 'new': 'Połowa pól świeci pustką. Gwiazdki to nie ozdoba choinkowa — uzupełnij.'},
    'absence.hours_required':    {'previous': 'Dla nieobecności godzinowej wymagane są godziny', 'current': 'Nieobecność godzinowa bez godzin? Podaj je, geniuszu.', 'new': 'Nieobecność godzinowa bez godzin? Genialne. Podaj je.'},
    'absence.hard_deleted_freed': {'previous': 'Nieobecność trwale usunięta — sloty zwolnione', 'current': 'Nieobecność trwale usunięta — sloty zwolnione', 'new': 'Wymazana na trwałe — sloty w kalendarzu znów wolne.'},
    'absence.hard_deleted':       {'previous': 'Nieobecność trwale usunięta', 'current': 'Nieobecność trwale usunięta', 'new': 'Wymazana na trwałe. Nie było, nie ma.'},
    'absence.category_hard_deleted': {'previous': 'Kategoria trwale usunięta', 'current': 'Kategoria trwale usunięta', 'new': 'Kategoria wymazana na trwałe. Koniec historii.'},

    # ── Past-visits scanner ─────────────────────────────────────────────────
    'visits.updated':         {'previous': 'Zaktualizowano {count} {label}', 'current': 'Zaktualizowano {count} {label}', 'new': 'Ogarnięte: {count} {label}. Dobra robota.'},
    'visits.updated_partial': {'previous': 'Zaktualizowano {ok} z {total} wizyt (błędów: {err})', 'current': 'Zaktualizowano {ok} z {total} wizyt (błędów: {err})', 'new': 'Poszło {ok} z {total} wizyt — {err} się postawiło. Sprawdź resztę.'},
    'visits.save_failed':     {'previous': 'Nie udało się zapisać zmian. Spróbuj ponownie.', 'current': 'Zapis nie wyszedł. Weź jeszcze raz, z uczuciem.', 'new': 'Zapis nie przeszedł — to nie Ty. Spróbuj jeszcze raz za chwilę.'},
    'visits.nothing.title':   {'previous': 'Brak wizyt do rozliczenia', 'current': 'Nic do rozliczenia', 'new': 'Nic do rozliczenia'},
    'visits.nothing.message': {'previous': 'Wszystkie przeszłe wizyty mają już ustawiony status końcowy.', 'current': 'Wszystkie wizyty już mają status. Czysto jak łza — możesz iść na kawę.', 'new': 'Wszystkie wizyty mają status. Czysto jak łza — leć na kawę.'},

    # ── Utils field paste ───────────────────────────────────────────────────
    'util.field_not_found': {'previous': 'Pole nie zostało znalezione', 'current': 'Nie ma takiego pola. Zniknęło? Dziwne.', 'new': 'Nie znalazłem tego pola — odśwież stronę i spróbuj ponownie.'},
    'util.clipboard_error': {'previous': 'Błąd wklejania: ', 'current': 'Schowek nie chce współpracować: ', 'new': 'Schowek nie chciał oddać treści — spróbuj ponownie. Szczegóły: '},

    # ── Analytics (user floppiness → SAVAGE) ────────────────────────────────
    'analytics.pick_both_dates': {'previous': 'Wybierz obie daty', 'current': 'Dwie daty, nie jedna. Matematyka.', 'new': 'Dwie daty. Nie jedna. To naprawdę nie matematyka wyższa.'},
    'analytics.date_order':      {'previous': 'Data początkowa musi być wcześniejsza niż końcowa', 'current': 'Początek po końcu? Czas tak nie działa.', 'new': 'Data końcowa przed początkową. Gratulacje, złamałeś czasoprzestrzeń. Popraw to.'},

    # ── Invoice upload ──────────────────────────────────────────────────────
    'upload.restored':           {'previous': 'Przywrócono {count} faktur', 'current': 'Przywrócono {count} faktur', 'new': 'Przywrócone: {count} faktur. Jak nowe.'},
    'upload.wrong_file_type':    {'previous': 'Proszę wybrać pliki PDF lub obrazy (JPG, PNG, TIFF, BMP)', 'current': 'PDF albo obrazek (JPG, PNG, TIFF, BMP). Nie mem, nie .exe.', 'new': 'To ma być PDF albo obrazek (JPG, PNG, TIFF, BMP), a nie cokolwiek to było. Czytaj ze zrozumieniem.'},
    'upload.sent':               {'previous': 'Przesłano {count} plików', 'current': 'Przesłano {count} plików', 'new': 'Wrzucone: {count} plików. Sprawnie.'},
    'upload.send_error':         {'previous': 'Błąd przesyłania plików: ', 'current': 'Wysyłka się zacięła: ', 'new': 'Wysyłka nie doszła — spróbuj ponownie za moment. Szczegóły: '},
    'upload.file_removed':       {'previous': 'Plik {name} usunięty', 'current': 'Plik {name} wyleciał', 'new': 'Plik {name} wyleciał. Pa.'},
    'upload.file_remove_error':  {'previous': 'Błąd usuwania pliku: ', 'current': 'Plik nie chce zniknąć: ', 'new': 'Plik nie chciał zniknąć — spróbuj jeszcze raz. Szczegóły: '},
    'upload.processed':          {'previous': 'Przetworzono {count} plików', 'current': 'Przetworzono {count} plików', 'new': 'Przerobione: {count} plików. Robota wre.'},
    'upload.processed_none':     {'previous': 'Nie udało się przetworzyć żadnych plików', 'current': 'Ani jednego pliku nie przerobiłem. Słaby wynik.', 'new': 'Żadnego pliku nie udało się przetworzyć — spróbuj ponownie za moment.'},
    'upload.process_error':      {'previous': 'Błąd przetwarzania: ', 'current': 'Przetwarzanie padło: ', 'new': 'Przetwarzanie się wyłożyło — spróbuj ponownie. Szczegóły: '},
    'upload.selected_valid':     {'previous': 'Zaznaczono {count} poprawnych faktur', 'current': 'Zaznaczono {count} poprawnych faktur', 'new': 'Zaznaczone: {count} poprawnych faktur.'},
    'upload.deselected_all':     {'previous': 'Odznaczono wszystkie faktury', 'current': 'Wszystko odznaczone. Zaczynamy od zera.', 'new': 'Wszystko odznaczone. Czysta karta.'},
    'upload.nothing_selected':   {'previous': 'Nie wybrano żadnych faktur do zapisu', 'current': 'Nic nie zaznaczyłeś. Mam zapisać powietrze?', 'new': 'Zaznaczyłeś dokładnie zero faktur. Genialnie. Co mam zapisać, powietrze?'},
    'upload.saved':              {'previous': 'Zapisano {count} faktur!', 'current': 'Zapisano {count} faktur. Brawo Ty.', 'new': 'Zapisane: {count} faktur. Patrz, jak ładnie potrafisz, jak ci się chce.'},
    'upload.save_failed_count':  {'previous': 'Nie udało się zapisać {count} faktur.', 'current': '{count} faktur się nie zapisało. Marudzą.', 'new': '{count} faktur się nie zapisało — spróbuj ponownie za moment.'},
    'upload.all_deleted':        {'previous': 'Wszystkie pliki usunięte', 'current': 'Wszystkie pliki w kosz. Czysto.', 'new': 'Wszystkie pliki w koszu. Czysto.'},
    'upload.files_delete_error': {'previous': 'Błąd usuwania plików: ', 'current': 'Pliki stawiają opór: ', 'new': 'Plików nie udało się usunąć — spróbuj ponownie. Szczegóły: '},
    'upload.folders_loaded':     {'previous': 'Załadowano {count} folderów', 'current': 'Załadowano {count} folderów', 'new': 'Załadowane: {count} folderów.'},
    'upload.no_folders':         {'previous': 'Nie znaleziono folderów e-mail', 'current': 'Zero folderów w mailu. Pusto jak w lodówce w niedzielę.', 'new': 'Zero folderów w mailu. Pusto jak w lodówce w niedzielę.'},
    'upload.folders_error':      {'previous': 'Błąd pobierania folderów: ', 'current': 'Foldery nie dojechały: ', 'new': 'Folderów nie udało się pobrać — spróbuj ponownie. Szczegóły: '},
    'upload.pick_folder':        {'previous': 'Proszę wybrać co najmniej jeden folder', 'current': 'Zaznacz chociaż jeden folder. Jeden. Błagam.', 'new': 'Zaznacz chociaż jeden folder. Jeden. Naprawdę jeden wystarczy.'},
    'upload.pick_date_range':    {'previous': 'Proszę wybrać zakres dat', 'current': 'Zakres dat by się przydał, nie sądzisz?', 'new': 'Bez zakresu dat ani rusz. Wpisz go.'},
    'upload.import_done':        {'previous': 'Import zakończony: pobrano {count} plików', 'current': 'Import zakończony: pobrano {count} plików', 'new': 'Import zrobiony: pobrane {count} plików.'},
    'upload.no_pdfs':            {'previous': 'Nie znaleziono plików PDF w wybranych folderach', 'current': 'Żadnych PDF-ów w tych folderach. Pustka.', 'new': 'Żadnych PDF-ów w tych folderach. Pustka.'},
    'upload.import_error':       {'previous': 'Błąd importu z e-mail: ', 'current': 'Import z maila legł: ', 'new': 'Import z maila się nie udał — spróbuj ponownie. Szczegóły: '},

    # ── Sellers (validation → SAVAGE; loads/saves → CALMING; success → SAVAGE) ─
    'seller.nip_name_required':  {'previous': 'NIP i nazwa są wymagane', 'current': 'NIP i nazwa. Bez nich ani rusz.', 'new': 'NIP i nazwa. Oba. Bez nich ani rusz.'},
    'seller.nip_ten_digits':     {'previous': 'NIP musi mieć 10 cyfr', 'current': 'NIP ma 10 cyfr. Nie 9, nie 11. Dziesięć.', 'new': 'Dziesięć cyfr. D-Z-I-E-S-I-Ę-Ć. Policz na palcach, jak musisz.'},
    'seller.already_exists':     {'previous': 'Sprzedawca już istnieje', 'current': 'Tego sprzedawcę już masz.', 'new': 'Tego sprzedawcę już masz na liście.'},
    'seller.name_changed':       {'previous': 'Nazwa sprzedawcy została zaktualizowana', 'current': 'Nazwa zmieniona.', 'new': 'Nazwa zmieniona. Gotowe.'},
    'seller.created':            {'previous': 'Sprzedawca został utworzony', 'current': 'Sprzedawca dodany. Witamy na pokładzie.', 'new': 'Sprzedawca dodany. Witamy na pokładzie.'},
    'seller.create_error':       {'previous': 'Błąd tworzenia sprzedawcy: ', 'current': 'Sprzedawca nie chciał się urodzić: ', 'new': 'Sprzedawcy nie udało się dodać — spróbuj ponownie. Szczegóły: '},
    'seller.name_required':      {'previous': 'Nazwa sprzedawcy jest wymagana', 'current': 'Nazwa sprzedawcy się sama nie wpisze.', 'new': 'Nazwa sprzedawcy się sama nie wpisze. Wklep ją.'},
    'seller.saved':              {'previous': 'Dane sprzedawcy zostały zaktualizowane', 'current': 'Zapisane. Sprzedawca odświeżony.', 'new': 'Zapisane. Sprzedawca odświeżony.'},
    'seller.data_load_failed':   {'previous': 'Błąd ładowania danych sprzedawcy', 'current': 'Dane sprzedawcy się nie wczytały.', 'new': 'Dane sprzedawcy się nie wczytały — odśwież za moment.'},
    'seller.invoices_update_error': {'previous': 'Błąd aktualizacji faktur: ', 'current': 'Faktury nie chcą się zaktualizować: ', 'new': 'Faktur nie udało się zaktualizować — spróbuj ponownie. Szczegóły: '},
    'seller.list_load_failed':   {'previous': 'Błąd ładowania sprzedawców', 'current': 'Sprzedawcy się nie wczytali. Strajk?', 'new': 'Sprzedawcy się nie wczytali — odśwież stronę za moment.'},
    'seller.list_load_error':    {'previous': 'Błąd ładowania sprzedawców: ', 'current': 'Sprzedawcy się buntują: ', 'new': 'Sprzedawców nie udało się wczytać — spróbuj ponownie. Szczegóły: '},
    'seller.invoices_load_failed': {'previous': 'Błąd pobierania faktur', 'current': 'Nie dało się pobrać faktur.', 'new': 'Faktur nie udało się pobrać — odśwież za moment.'},
    'seller.deleted':            {'previous': 'Sprzedawca został usunięty', 'current': 'Sprzedawca skasowany. Pa, pa.', 'new': 'Sprzedawca skasowany. Pa, pa.'},
    'seller.delete_failed':      {'previous': 'Błąd usuwania sprzedawcy', 'current': 'Sprzedawca nie chce zniknąć. Trzyma się życia.', 'new': 'Sprzedawcy nie udało się usunąć — spróbuj ponownie.'},
    'seller.sync_error':         {'previous': 'Błąd synchronizacji: ', 'current': 'Synchronizacja się wykrzaczyła: ', 'new': 'Synchronizacja się nie udała — spróbuj ponownie. Szczegóły: '},
    'seller.add_error':          {'previous': 'Błąd dodawania sprzedawcy: ', 'current': 'Nie dało się dodać sprzedawcy: ', 'new': 'Sprzedawcy nie udało się dodać — spróbuj ponownie. Szczegóły: '},
    'seller.fix_error':          {'previous': 'Błąd naprawiania niezgodności: ', 'current': 'Naprawa się nie udała: ', 'new': 'Naprawy nie udało się wykonać — spróbuj ponownie. Szczegóły: '},
    'seller.refresh_error':      {'previous': 'Błąd odświeżania: ', 'current': 'Odświeżanie się zacięło: ', 'new': 'Odświeżanie się nie udało — spróbuj ponownie. Szczegóły: '},
    'seller.sync_failed':        {'previous': 'Błąd synchronizacji', 'current': 'Synchronizacja się wykrzaczyła.', 'new': 'Synchronizacja się nie udała — spróbuj ponownie za moment.'},
    'seller.fix_failed':         {'previous': 'Błąd naprawiania niezgodności', 'current': 'Naprawa się nie udała.', 'new': 'Naprawa się nie udała — spróbuj ponownie za moment.'},
    'seller.create_failed':      {'previous': 'Błąd tworzenia sprzedawcy', 'current': 'Sprzedawca nie chciał się urodzić.', 'new': 'Sprzedawcy nie udało się dodać — spróbuj ponownie za moment.'},

    # ── PDF passwords (shared sellers/edit.js + sellers/list_refined.html) ───
    'pdfpwd.required':   {'previous': 'Hasło PDF jest wymagane', 'current': 'Hasło PDF poproszę. Puste pole nie przejdzie.', 'new': 'Hasło PDF poproszę. Puste pole nie przejdzie.'},
    'pdfpwd.deleted':    {'previous': 'Hasło usunięte', 'current': 'Hasło skasowane', 'new': 'Hasło skasowane.'},
    'pdfpwd.load_failed':{'previous': 'Błąd ładowania haseł', 'current': 'Blad ladowania hasel', 'new': 'Haseł nie udało się wczytać — odśwież za moment.'},
    'pdfpwd.panel_load_error': {'previous': 'Błąd ładowania haseł: ', 'current': 'Hasła się nie wczytały: ', 'new': 'Haseł nie udało się wczytać — spróbuj ponownie. Szczegóły: '},
    'pdfpwd.updated':    {'previous': 'Hasło zostało zaktualizowane', 'current': 'Hasło podmienione.', 'new': 'Hasło podmienione. Gotowe.'},
    'pdfpwd.created':    {'previous': 'Hasło zostało zapisane', 'current': 'Hasło zapisane.', 'new': 'Hasło zapisane. Gotowe.'},

    # ── Clients (loads → CALMING; success → SAVAGE) ─────────────────────────
    'client.services_load_failed': {'previous': 'Błąd wczytywania usług pracownika', 'current': 'Usługi pracownika się nie wczytały. Marudzą.', 'new': 'Usług pracownika nie udało się wczytać — odśwież za moment.'},
    'client.employees_load_failed':{'previous': 'Błąd wczytywania pracowników', 'current': 'Pracownicy się nie wczytali. Strajk?', 'new': 'Pracowników nie udało się wczytać — odśwież za moment.'},
    'client.prefs_load_failed':    {'previous': 'Błąd wczytywania preferencji', 'current': 'Preferencje się nie wczytały. Kaprys serwera.', 'new': 'Preferencji nie udało się wczytać — odśwież za moment.'},
    'client.pref_added':           {'previous': 'Preferencja została dodana', 'current': 'Preferencja zapisana. Klient ma gust.', 'new': 'Preferencja zapisana. Klient ma gust.'},
    'client.pref_deleted':         {'previous': 'Preferencja usunięta', 'current': 'Preferencja skasowana. Zdania się zmieniają.', 'new': 'Preferencja skasowana. Zdania się zmieniają.'},
    'common.error_detail':         {'previous': 'Błąd: ', 'current': 'Błąd: ', 'new': 'Coś nie pykło: '},

    # ── Employees (loads/500 → CALMING; success/validation → SAVAGE) ────────
    'emp.assign_cancelled':     {'previous': 'Przypisywanie usługi zostało przerwane', 'current': 'Przerwane. Rozmyśliłeś się w pół drogi.', 'new': 'Przerwane. Rozmyśliłeś się w pół drogi.'},
    'emp.services_load_warn':   {'previous': 'Nie można załadować listy usług', 'current': 'Lista usług się nie ładuje. Uparta.', 'new': 'Listy usług nie udało się wczytać — odśwież za moment.'},
    'emp.services_load_500':    {'previous': 'Błąd wczytywania usług (500)', 'current': 'Usługi padły z błędem 500. Serwer ma gorszy dzień.', 'new': 'Usług nie udało się wczytać (500) — to po naszej stronie, odśwież za moment.'},
    'emp.assigned_load_warn':   {'previous': 'Nie można załadować przypisanych usług', 'current': 'Przypisane usługi się nie ładują. Cierpliwości.', 'new': 'Przypisanych usług nie udało się wczytać — odśwież za moment.'},
    'emp.assigned_load_500':    {'previous': 'Błąd wczytywania przypisanych usług (500)', 'current': 'Przypisane usługi padły (500). Klasyka.', 'new': 'Przypisanych usług nie udało się wczytać (500) — odśwież za moment.'},
    'emp.pick_service':         {'previous': 'Wybierz usługę', 'current': 'Najpierw wybierz usługę. Telepatii nie mam.', 'new': 'Najpierw wybierz usługę. Telepatii nie opanowałem.'},
    'emp.service_assigned':     {'previous': 'Usługa została przypisana', 'current': 'Usługa przypisana. Robota się sama nie zrobi, ale ta już tak.', 'new': 'Usługa przypisana. Jedno z głowy.'},
    'emp.assignment_deleted':   {'previous': 'Przypisanie usunięte', 'current': 'Przypisanie skasowane.', 'new': 'Przypisanie skasowane.'},
    'emp.deactivated':          {'previous': 'Pracownik został dezaktywowany', 'current': 'Pracownik dezaktywowany. Pa, pa.', 'new': 'Pracownik dezaktywowany. Pa, pa.'},
    'emp.server_500':           {'previous': 'Błąd połączenia z serwerem (500)', 'current': 'Serwer padł (500). Klasyka gatunku.', 'new': 'Serwer chwilowo padł (500) — to nie Ty, odśwież za moment.'},
    'emp.limit_near':           {'previous': 'Uwaga: limit nieobecności przekroczony lub bliski przekroczenia', 'current': 'Limit nieobecności na granicy. Ktoś tu lubi wolne.', 'new': 'Limit nieobecności na granicy. Ktoś tu lubi wolne.'},

    # ── Appointments ────────────────────────────────────────────────────────
    'appt.rating_saved':  {'previous': 'Ocena {score}/5 zapisana', 'current': 'Ocena {score}/5 zapisana. Sąd okrutny, ale sprawiedliwy.', 'new': 'Ocena {score}/5 zapisana. Sąd okrutny, ale sprawiedliwy.'},
    'appt.sms_sent':      {'previous': 'SMS "{type}" wysłany', 'current': 'SMS „{type}" poszedł w świat.', 'new': 'SMS „{type}" poszedł w świat.'},
    'appt.sms_error':     {'previous': 'Błąd: ', 'current': 'Coś nie pykło: ', 'new': 'SMS nie poszedł: '},
    'appt.deleted':       {'previous': 'Wizyta #{id} usunięta', 'current': 'Wizyta #{id} wykasowana. Jakby jej nie było.', 'new': 'Wizyta #{id} wykasowana. Jakby jej nie było.'},

    # ── Settings: email + sms ───────────────────────────────────────────────
    'settings.email.saved':       {'previous': 'Ustawienia zostały zapisane', 'current': 'Ustawienia zapisane. Ogarnięte.', 'new': 'Ustawienia zapisane. Ogarnięte.'},
    'settings.email.save_failed': {'previous': 'Błąd zapisywania ustawień', 'current': 'Ustawienia nie chciały się zapisać. Foch.', 'new': 'Ustawień nie udało się zapisać — spróbuj ponownie za moment.'},
    'settings.email.fields_required': {'previous': 'Proszę wypełnić wszystkie wymagane pola', 'current': 'Wypełnij wymagane pola. Serwer telepatii nie zna.', 'new': 'Wypełnij wymagane pola. Wszystkie z gwiazdką.'},
    'settings.email.imap_ok':     {'previous': 'Połączenie z serwerem IMAP zostało nawiązane pomyślnie!', 'current': 'IMAP odebrał. Dogadaliście się!', 'new': 'IMAP odebrał. Dogadaliście się!'},
    'settings.email.imap_failed': {'previous': 'Nie udało się połączyć z serwerem. Sprawdź ustawienia i spróbuj ponownie.', 'current': 'Serwer nie odebrał. Sprawdź ustawienia i próbuj dalej.', 'new': 'Serwer nie odebrał — sprawdź spokojnie ustawienia i spróbuj ponownie.'},
    'settings.email.test_error':  {'previous': 'Błąd testowania połączenia: ', 'current': 'Test połączenia legł: ', 'new': 'Testu połączenia nie udało się wykonać — spróbuj ponownie. Szczegóły: '},
    'settings.sms.conn_failed':   {'previous': 'Błąd połączenia — spróbuj ponownie', 'current': 'Połączenie padło. Weź jeszcze raz.', 'new': 'Połączenie się urwało — spróbuj ponownie za moment.'},
    'settings.sms.server_status': {'previous': 'Błąd serwera ({status}) — spróbuj ponownie', 'current': 'Serwer rzucił {status}. Spróbuj jeszcze raz.', 'new': 'Serwer odpowiedział błędem {status} — spróbuj ponownie za moment.'},

    # ── History + Invoices list/create/edit ─────────────────────────────────
    'history.load_failed':       {'previous': 'Błąd ładowania historii', 'current': 'Historia się nie wczytała. Przeszłość bywa trudna.', 'new': 'Historii nie udało się wczytać — odśwież za moment.'},
    'invoice.list_load_failed':  {'previous': 'Błąd ładowania faktur', 'current': 'Faktury się nie wczytały. Grymaszą.', 'new': 'Faktur nie udało się wczytać — odśwież za moment.'},
    'invoice.status_failed':     {'previous': 'Błąd aktualizacji statusu', 'current': 'Status nie chciał się zmienić. Uparty.', 'new': 'Statusu nie udało się zmienić — spróbuj ponownie za moment.'},
    'invoice.no_pdf':            {'previous': 'Brak pliku PDF dla tej faktury', 'current': 'Tej faktury PDF nie uświadczysz. Nie ma i już.', 'new': 'Ta faktura nie ma PDF-a. Nie ma i już.'},
    'invoice.deleted':           {'previous': 'Faktura została usunięta', 'current': 'Faktura wykasowana. Już jej nie ma.', 'new': 'Faktura wykasowana. Już jej nie ma.'},
    'invoice.delete_failed':     {'previous': 'Błąd usuwania faktury', 'current': 'Faktura nie chce zniknąć. Trzyma się życia.', 'new': 'Faktury nie udało się usunąć — spróbuj ponownie za moment.'},
    'invoice.export_xlsx':       {'previous': 'Eksportowanie do Excel...', 'current': 'Lecę z tym do Excela...', 'new': 'Lecę z tym do Excela...'},
    'invoice.export_csv':        {'previous': 'Eksportowanie do CSV...', 'current': 'Pakuję do CSV...', 'new': 'Pakuję do CSV...'},
    'invoice.export_failed':     {'previous': 'Błąd eksportu', 'current': 'Eksport się wyłożył. Bez paniki.', 'new': 'Eksport się nie udał — spróbuj ponownie za moment.'},
    'invoice.links_ok':          {'previous': 'Wszystkie faktury są poprawnie powiązane ze sprzedawcami.', 'current': 'Wszystkie faktury ładnie powiązane. Porządek jak w aptece.', 'new': 'Wszystkie faktury ładnie powiązane. Porządek jak w aptece.'},
    'invoice.links_check_error': {'previous': 'Błąd sprawdzania powiązań: ', 'current': 'Nie dało się sprawdzić powiązań: ', 'new': 'Powiązań nie udało się sprawdzić — spróbuj ponownie. Szczegóły: '},
    'invoice.nothing_to_update': {'previous': 'Nie zaznaczono żadnych faktur do aktualizacji.', 'current': 'Nic nie zaznaczyłeś. Nie ma czego aktualizować.', 'new': 'Nic nie zaznaczyłeś — nie ma czego aktualizować.'},
    'invoice.file_too_big':      {'previous': 'Plik jest za duży. Maksymalny rozmiar: 10MB', 'current': 'Plik za gruby. Max 10MB, nie cała galeria.', 'new': 'Plik za gruby. Max 10MB, nie cała galeria.'},
    'invoice.saved':             {'previous': 'Faktura została zapisana pomyślnie', 'current': 'Faktura zapisana. Pierwsza klasa.', 'new': 'Faktura zapisana. Pierwsza klasa.'},
    'invoice.save_failed':       {'previous': 'Błąd zapisu faktury', 'current': 'Faktura nie chciała się zapisać.', 'new': 'Faktury nie udało się zapisać — spróbuj ponownie za moment.'},
    'invoice.updated':           {'previous': 'Faktura została zaktualizowana', 'current': 'Faktura zaktualizowana. Ładnie.', 'new': 'Faktura zaktualizowana. Ładnie.'},
    'invoice.update_failed':     {'previous': 'Błąd aktualizacji faktury', 'current': 'Faktura nie chciała się zaktualizować.', 'new': 'Faktury nie udało się zaktualizować — spróbuj ponownie za moment.'},
    'invoice.save_cancelled':    {'previous': 'Anulowano zapis - przywracanie oryginalnych wartości...', 'current': 'Anulowane. Wracam do tego, co było...', 'new': 'Anulowane. Wracam do tego, co było...'},
    'invoice.save_cancelled_short': {'previous': 'Anulowano zapis faktury', 'current': 'Zapis faktury anulowany. Rozmyśliłeś się.', 'new': 'Zapis faktury anulowany. Rozmyśliłeś się.'},

    # ── Absence balances ────────────────────────────────────────────────────
    'balance.limit_names':    {'previous': 'Przekroczony limit: {names}', 'current': 'Limit przekroczony: {names}. Ktoś tu lubi wolne.', 'new': 'Limit przekroczony: {names}. Ktoś tu lubi wolne.'},
    'balance.limit_exceeded': {'previous': 'Wartość wykorzystania przekracza limit!', 'current': 'Limit przekroczony! Ktoś tu lubi wolne.', 'new': 'Limit przekroczony! Ktoś tu lubi wolne.'},
    'balance.reason_required':{'previous': 'Podaj powód zmiany wykorzystania', 'current': 'Podaj powód. „Bo tak" się nie liczy.', 'new': 'Podaj powód. „Bo tak" się nie liczy.'},
    'balance.saved':          {'previous': 'Zmiany zapisane', 'current': 'Zmiany zapisane. Bilans się zgadza.', 'new': 'Zmiany zapisane. Bilans się zgadza.'},
    'balance.undo_failed':    {'previous': 'Błąd cofania', 'current': 'Cofnięcie się nie udało. Czas płynie tylko naprzód.', 'new': 'Cofnięcia nie udało się wykonać — spróbuj ponownie za moment.'},
    'balance.undone':         {'previous': 'Cofnięto ostatni zapis', 'current': 'Cofnięte. Jakby się nie stało.', 'new': 'Cofnięte. Jakby się nie stało.'},
    'balance.already_zero':   {'previous': 'Bilans już wynosi 0', 'current': 'Bilans już na zerze. Nie ma co zerować.', 'new': 'Bilans już na zerze. Nie ma co zerować.'},
    'balance.reset_zero':     {'previous': 'Bilans zresetowany do zera', 'current': 'Bilans wyzerowany. Czysta karta.', 'new': 'Bilans wyzerowany. Czysta karta.'},

    # ── Users ───────────────────────────────────────────────────────────────
    'user.deleted': {'previous': 'Użytkownik usunięty', 'current': 'Użytkownik wykasowany. Konto poszło w niebyt.', 'new': 'Użytkownik wykasowany. Konto poszło w niebyt.'},
}


def resolve(msg_id, tone=None, **params):
    """Return the catalog string for ``msg_id`` in the active (or given) tone,
    with ``{param}`` placeholders interpolated. Unknown ids return the id
    itself (fail-visible, never crash a route or a toast)."""
    entry = MESSAGES.get(msg_id)
    if entry is None:
        return msg_id
    tone = tone or ACTIVE_TONE
    text = entry.get(tone)
    if text is None:
        for fb in _FALLBACK_ORDER:
            if entry.get(fb) is not None:
                text = entry[fb]
                break
    if text is None:
        return msg_id
    if params:
        for key, value in params.items():
            text = text.replace('{' + key + '}', str(value))
    return text


# Convenience alias used at call sites.
msg = resolve


def flat_map(tone=None):
    """Return ``{id: text}`` for the active (or given) tone — the payload
    injected into the page as ``window.UI_MESSAGES`` for the JS ``MSG()``
    resolver. Only one tone crosses to the browser; the other sets stay
    server-side. Placeholders are left intact for client-side interpolation."""
    tone = tone or ACTIVE_TONE
    out = {}
    for msg_id, entry in MESSAGES.items():
        text = entry.get(tone)
        if text is None:
            for fb in _FALLBACK_ORDER:
                if entry.get(fb) is not None:
                    text = entry[fb]
                    break
        out[msg_id] = text if text is not None else msg_id
    return out
