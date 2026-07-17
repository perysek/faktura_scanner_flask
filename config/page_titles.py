"""
Per-route mobile-header titles (P08).

Maps a Flask endpoint (``request.endpoint``) to a Polish label, exposed to
templates as ``page_title`` by the ``inject_globals`` context processor in
``app.py``. ``base.html``'s ``{% block mobile_title %}`` defaults to this; pages
with an explicit block still override it.

Kept in its own module (not ``app.py``) so the mapping is importable in tests
without pulling in the app factory / DB initialisation.
"""

PAGE_TITLES = {
    'main.dashboard': 'Pulpit',
    'main.index': 'Pulpit',
    'main.analytics_dashboard': 'Analityka',
    'main.kpi_matrix': 'Wskaźniki biznesowe',
    'main.income_dashboard': 'Przychody',
    'main.history': 'Historia',
    'main.import_page': 'Import danych',
    'main.upload': 'Wgraj faktury',
    # Clients
    'main.clients_list': 'Klienci',
    'main.create_client': 'Nowy klient',
    # Appointments
    'main.appointments_list': 'Wizyty',
    'main.create_appointment': 'Nowa wizyta',
    'main.appointments_calendar': 'Kalendarz',
    'main.appointments_calendar_week': 'Kalendarz',
    'main.appointments_calendar_month': 'Kalendarz',
    'main.my_visits': 'Moje wizyty',
    'main.superadmin_edit_latest': 'Korekta wizyt',
    'main.superadmin_edit_table': 'Korekta wizyt',
    # Employees
    'main.employees_list': 'Pracownicy',
    'main.create_employee': 'Nowy pracownik',
    'main.formy_zatrudnienia_list': 'Formy zatrudnienia',
    # Services
    'main.services_list': 'Usługi',
    'main.create_service': 'Nowa usługa',
    'main.service_categories_list': 'Kategorie usług',
    # Invoices / sellers
    'main.invoices_list': 'Faktury',
    'main.create_invoice': 'Nowa faktura',
    'main.sellers_list': 'Sprzedawcy',
    'main.create_seller': 'Nowy sprzedawca',
    # Absences
    'absence.management_index': 'Nieobecności',
    'absence.my_absences': 'Moje nieobecności',
    'absence_balance.balances_index': 'Bilanse urlopowe',
    # Settings
    'main.email_settings': 'Ustawienia e-mail',
    'sms.sms_settings': 'Ustawienia SMS',
    'sms.sms_log': 'Log SMS',
    'auth.profile': 'Profil',
    'auth.change_password': 'Zmiana hasła',
    'main.user_manual': 'Instrukcja obsługi',
    # System (RBAC)
    'users.users_list': 'Użytkownicy',
    'users.create_user': 'Nowy użytkownik',
    'roles.roles_list': 'Role',
    'roles.create_role': 'Nowa rola',
}


def page_title_for(endpoint):
    """Return the Polish mobile-header title for a Flask endpoint, or '' if
    unmapped or None. Safe to call outside a request context."""
    return PAGE_TITLES.get(endpoint or '', '')
