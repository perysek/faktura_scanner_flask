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
