import type { NavVisibilityCtx } from '../../types/auth';

export interface NavLinkConfig {
  label: string;
  to: string;
  /** 24×24 stroke path(s) — DESIGN.md §9's NavIcon system. */
  iconPath: string | string[];
  /** Density trim for the flattened mobile list — NEVER for access control
   * (DESIGN.md §13.5/§16). */
  mobileHide?: boolean;
  visible: (ctx: NavVisibilityCtx) => boolean;
}

export interface NavSectionConfig {
  id: string;
  title: string;
  links: NavLinkConfig[];
}

/**
 * Sidebar content — DESIGN.md §13.5. Ported from
 * `templates/macros/sidebar_macros.html` + `templates/components/sidebar.html`'s
 * per-section calls, with ONE deliberate correction: every `visible` predicate
 * here mirrors the REAL backend route guard (traced in `routes/main_routes.py` /
 * `routes/users/routes.py` / `routes/roles/routes.py`), not the `{% if %}`
 * condition the Jinja sidebar happens to wrap each link in — those two
 * diverge in five places today. See implementation-log.md Decision/Discovery
 * D14 for the full list; this file does NOT reproduce those five bugs.
 *
 * Only `/klienci` (Faza 1) routes to a fully-built page today. Every other
 * link is real (correct label/icon/visibility) but routes to a
 * <ComingSoonPage> placeholder until its module's turn in Faza 2 — see
 * implementation-log.md Decision D7.
 */
export const NAV_SECTIONS: NavSectionConfig[] = [
  {
    id: 'finanse',
    title: 'Finanse',
    links: [
      {
        label: 'Koszty',
        to: '/dashboard',
        mobileHide: true,
        // main.dashboard has NO module decorator (@login_required only) —
        // real gate is "any authenticated user" (D14 point 5).
        iconPath:
          'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z',
        visible: () => true,
      },
      {
        label: 'Lista faktur',
        to: '/faktury',
        iconPath: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
        visible: (ctx) => ctx.hasModuleAccess('invoices'),
      },
      {
        label: 'Lista sprzedawców',
        to: '/sprzedawcy',
        mobileHide: true,
        iconPath:
          'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
        visible: (ctx) => ctx.hasModuleAccess('invoices'),
      },
      {
        label: 'Import dokumentów',
        to: '/import-dokumentow',
        mobileHide: true,
        iconPath: 'M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12',
        visible: (ctx) => ctx.hasModuleAccess('invoices'),
      },
      {
        label: 'Analiza biznesowa',
        to: '/analiza-biznesowa',
        mobileHide: true,
        // Sidebar shows this under 'invoices'; the real route
        // (@main_bp.route('/analytics')) requires 'appointments' (D14 pt. 3).
        iconPath:
          'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
        visible: (ctx) => ctx.hasModuleAccess('appointments'),
      },
      {
        label: 'Wskaźniki biznesowe',
        to: '/wskazniki-biznesowe',
        mobileHide: true,
        // Same real gate as above — 'appointments', not 'invoices' (D14 pt. 3).
        iconPath:
          'M9 17V9m0 8H5a2 2 0 01-2-2V9a2 2 0 012-2h4m0 10h6m-6 0V5a2 2 0 012-2h2a2 2 0 012 2v12m0 0h4a2 2 0 002-2v-4a2 2 0 00-2-2h-4',
        visible: (ctx) => ctx.hasModuleAccess('appointments'),
      },
    ],
  },
  {
    id: 'salon',
    title: 'Salon',
    links: [
      {
        label: 'Wizyty',
        to: '/wizyty',
        iconPath: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
        visible: (ctx) => ctx.hasModuleAccess('appointments'),
      },
      {
        label: 'Klienci',
        to: '/klienci',
        iconPath:
          'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z',
        visible: (ctx) => ctx.hasModuleAccess('clients'),
      },
    ],
  },
  {
    id: 'zarzadzanie',
    title: 'Zarządzanie',
    links: [
      {
        label: 'Pracownicy',
        to: '/pracownicy',
        iconPath:
          'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
        visible: (ctx) => ctx.hasModuleAccess('employees'),
      },
      {
        label: 'Nieobecności',
        to: '/nieobecnosci',
        iconPath: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
        visible: (ctx) => ctx.isSupervisor || ctx.hasModuleAccess('absences'),
      },
      {
        label: 'Bilanse urlopów',
        to: '/bilanse-urlopow',
        mobileHide: true,
        iconPath:
          'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
        visible: (ctx) => ctx.isSupervisor || ctx.hasModuleAccess('absences'),
      },
      {
        label: 'Moje nieobecności',
        to: '/moje-nieobecnosci',
        iconPath: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
        visible: (ctx) => ctx.hasLinkedEmployee,
      },
      {
        label: 'Usługi',
        to: '/uslugi',
        mobileHide: true,
        iconPath: 'M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
        visible: (ctx) => ctx.hasModuleAccess('services'),
      },
      {
        label: 'Kategorie usług',
        to: '/kategorie-uslug',
        mobileHide: true,
        iconPath: 'M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z',
        visible: (ctx) => ctx.hasModuleAccess('services'),
      },
      {
        label: 'Rodzaje zatrudnienia',
        to: '/formy-zatrudnienia',
        mobileHide: true,
        iconPath: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
        visible: (ctx) => ctx.hasModuleAccess('services'),
      },
    ],
  },
  {
    id: 'korekta',
    title: 'Korekta danych',
    links: [
      {
        label: 'Edycja wizyt',
        to: '/korekta/wizyty',
        mobileHide: true,
        iconPath:
          'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z',
        visible: (ctx) => ctx.hasModuleAccess('data_correction'),
      },
      {
        label: 'Tabela wizyt',
        to: '/korekta/tabela',
        mobileHide: true,
        iconPath: 'M3 10h18M3 14h18M3 6h18M3 18h18M7 6v12M17 6v12',
        visible: (ctx) => ctx.hasModuleAccess('data_correction'),
      },
    ],
  },
  {
    id: 'system',
    title: 'System',
    links: [
      {
        label: 'Historia zmian',
        to: '/historia',
        mobileHide: true,
        // Sidebar shows this under 'reports'; the real route
        // (@main_bp.route('/history')) requires 'invoices' (D14 pt. 1).
        iconPath: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z',
        visible: (ctx) => ctx.hasModuleAccess('invoices'),
      },
      {
        label: 'Ustawienia',
        to: '/ustawienia/email',
        mobileHide: true,
        // Sidebar shows this under 'settings'; the real route
        // (@main_bp.route('/settings/email')) requires 'invoices' (D14 pt. 2).
        iconPath: [
          'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z',
          'M15 12a3 3 0 11-6 0 3 3 0 016 0z',
        ],
        visible: (ctx) => ctx.hasModuleAccess('invoices'),
      },
      {
        label: 'Użytkownicy',
        to: '/uzytkownicy',
        mobileHide: true,
        // Sidebar shows this under 'settings'; the real route uses a literal
        // role check, @role_required('superuser','admin') (D14 pt. 4).
        iconPath:
          'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
        visible: (ctx) => ctx.user?.role === 'superuser' || ctx.user?.role === 'admin',
      },
      {
        label: 'Poziomy dostępu',
        to: '/poziomy-dostepu',
        mobileHide: true,
        // Real route: @role_required('superuser') only (D14 pt. 4).
        iconPath:
          'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
        visible: (ctx) => ctx.user?.role === 'superuser',
      },
      {
        label: 'Ustawienia SMS',
        to: '/ustawienia/sms',
        iconPath: 'M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z',
        visible: (ctx) => ctx.hasModuleAccess('settings'),
      },
      {
        label: 'Import danych',
        to: '/import-danych',
        mobileHide: true,
        iconPath: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4',
        visible: (ctx) => ctx.hasModuleAccess('data_import'),
      },
      {
        label: 'Instrukcja obsługi',
        to: '/instrukcja',
        iconPath:
          'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253',
        visible: () => true,
      },
      {
        label: 'Profil',
        to: '/profil',
        iconPath: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
        visible: () => true,
      },
    ],
  },
];
