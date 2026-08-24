import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { ProtectedRoute } from './components/routing/ProtectedRoute';
import { Login } from './pages/auth/Login';
import { ForgotPassword } from './pages/auth/ForgotPassword';
import { ResetPassword } from './pages/auth/ResetPassword';
import { ComingSoonPage } from './pages/ComingSoonPage';
import { ClientsListPage } from './pages/clients/ClientsListPage';
import { ClientFormPage } from './pages/clients/ClientFormPage';
import { ClientDetailPage } from './pages/clients/ClientDetailPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { SellersListPage } from './pages/sellers/SellersListPage';
import { SellerFormPage } from './pages/sellers/SellerFormPage';
import { ServicesListPage } from './pages/services/ServicesListPage';
import { ServiceFormPage } from './pages/services/ServiceFormPage';
import { ServiceDetailPage } from './pages/services/ServiceDetailPage';
import { ServiceCategoriesPage } from './pages/services/ServiceCategoriesPage';
import { EmployeesListPage } from './pages/employees/EmployeesListPage';
import { EmployeeFormPage } from './pages/employees/EmployeeFormPage';
import { EmployeeDetailPage } from './pages/employees/EmployeeDetailPage';
import { FormyZatrudnieniaPage } from './pages/employees/FormyZatrudnieniaPage';
import { FakturyListPage } from './pages/faktury/FakturyListPage';
import { FakturaFormPage } from './pages/faktury/FakturaFormPage';
import { WizytyListPage } from './pages/appointments/WizytyListPage';
import { WizytaDetailPage } from './pages/appointments/WizytaDetailPage';
import { WizytaFormPage } from './pages/appointments/WizytaFormPage';
import { CalendarDayPage } from './pages/appointments/CalendarDayPage';
import { CalendarWeekPage } from './pages/appointments/CalendarWeekPage';
import { CalendarMonthPage } from './pages/appointments/CalendarMonthPage';
import { EmailSettingsPage } from './pages/settings/EmailSettingsPage';
import { SmsSettingsPage } from './pages/settings/SmsSettingsPage';
import { SmsLogPage } from './pages/settings/SmsLogPage';

/**
 * Route tree — DESIGN.md §14.1. Public auth routes sit outside any guard;
 * everything else nests inside one outer bare-auth <ProtectedRoute>
 * (+ <AppShell> chrome), with a second, more specific <ProtectedRoute
 * guard=.../requireModule=.../> nested wherever the backend has an
 * additional gate (§14.3).
 *
 * Every `guard`/`requireModule` here reuses the EXACT boolean expression
 * from the matching `NavLinkConfig.visible` in navConfig.ts — including the
 * five real backend-vs-sidebar mismatches traced in implementation-log.md
 * Decision/Discovery D14 (e.g. Historia/Ustawienia require 'invoices', not
 * 'reports'/'settings'; Analiza biznesowa/Wskaźniki require 'appointments',
 * not 'invoices'; Użytkownicy/Role are literal-role gates, not a module
 * check).
 */
export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/forgot-password', element: <ForgotPassword /> },
  { path: '/reset-password/:token', element: <ResetPassword /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <Navigate to="/dashboard" replace /> },

          // No module gate on the backend (@login_required only) — any
          // authenticated user (D14 point 5). Faza 2, moduł Dashboard/Pulpit.
          { path: 'dashboard', element: <DashboardPage /> },
          { path: 'instrukcja', element: <ComingSoonPage title="Instrukcja obsługi" /> },
          { path: 'profil', element: <ComingSoonPage title="Profil" /> },

          // requireModule="invoices" — includes historia/ustawienia/email,
          // which the sidebar mis-labels 'reports'/'settings' (D14 pts 1-2).
          {
            element: <ProtectedRoute requireModule="invoices" />,
            children: [
              // Faktury — Faza 2, piąty moduł, największa dotąd złożoność
              // backendu. Tylko list+CRUD+konflikt-sprzedawcy+sync+eksport —
              // import-dokumentow/historia/ustawienia-email zostają
              // ComingSoonPage, patrz implementation-log.md (decyzja o zakresie).
              { path: 'faktury', element: <FakturyListPage /> },
              { path: 'faktury/nowa', element: <FakturaFormPage mode="create" /> },
              { path: 'faktury/:id/edytuj', element: <FakturaFormPage mode="edit" /> },
              // Sprzedawcy — Faza 2. URL-e po polsku (/sprzedawcy/nowy,
              // /sprzedawcy/:id/edytuj), wzorem Klientów z Fazy 1 — nie 1:1
              // kopia starych angielskich /seller/create, /seller/<id>/edit.
              { path: 'sprzedawcy', element: <SellersListPage /> },
              { path: 'sprzedawcy/nowy', element: <SellerFormPage mode="create" /> },
              { path: 'sprzedawcy/:id/edytuj', element: <SellerFormPage mode="edit" /> },
              { path: 'import-dokumentow', element: <ComingSoonPage title="Import dokumentów" /> },
              { path: 'historia', element: <ComingSoonPage title="Historia zmian" /> },
              { path: 'ustawienia/email', element: <EmailSettingsPage /> },
            ],
          },

          // requireModule="appointments" — includes analytics/kpi, which the
          // sidebar mis-nests under the invoices-gated Finanse section (D14 pt. 3).
          {
            element: <ProtectedRoute requireModule="appointments" />,
            children: [
              // Wizyty + Kalendarz — Faza 2, szósty moduł, największy w apce
              // (module-inventory.md). Zakres: lista, widok szczegółów,
              // create/edit, 3 widoki kalendarza (dzień/tydzień/miesiąc) +
              // boczny pasek month-cards (dzień+lista). Poza zakresem:
              // integracja z nieobecnościami, SMS na widoku szczegółów,
              // "rozlicz przeszłe wizyty" — patrz implementation-log.md.
              { path: 'wizyty', element: <WizytyListPage /> },
              { path: 'wizyty/kalendarz', element: <CalendarDayPage /> },
              { path: 'wizyty/kalendarz/tydzien', element: <CalendarWeekPage /> },
              { path: 'wizyty/kalendarz/miesiac', element: <CalendarMonthPage /> },
              { path: 'wizyty/nowa', element: <WizytaFormPage mode="create" /> },
              { path: 'wizyty/:id/edytuj', element: <WizytaFormPage mode="edit" /> },
              { path: 'wizyty/:id', element: <WizytaDetailPage /> },
              { path: 'analiza-biznesowa', element: <ComingSoonPage title="Analiza biznesowa" /> },
              { path: 'wskazniki-biznesowe', element: <ComingSoonPage title="Wskaźniki biznesowe" /> },
            ],
          },

          // Klienci — Faza 1, fully built.
          {
            element: <ProtectedRoute requireModule="clients" />,
            children: [
              { path: 'klienci', element: <ClientsListPage /> },
              { path: 'klienci/nowy', element: <ClientFormPage mode="create" /> },
              { path: 'klienci/:id/edytuj', element: <ClientFormPage mode="edit" /> },
              { path: 'klienci/:id', element: <ClientDetailPage /> },
            ],
          },

          {
            element: <ProtectedRoute requireModule="employees" />,
            children: [
              // Pracownicy — Faza 2, największy moduł dotąd. URL-e po polsku,
              // wzorem Klientów/Sprzedawców/Usług. Zakładki analityczne strony
              // szczegółów świadomie odłożone — patrz EmployeeDetailPage.tsx.
              { path: 'pracownicy', element: <EmployeesListPage /> },
              { path: 'pracownicy/nowy', element: <EmployeeFormPage mode="create" /> },
              { path: 'pracownicy/:id/edytuj', element: <EmployeeFormPage mode="edit" /> },
              { path: 'pracownicy/:id', element: <EmployeeDetailPage /> },
              { path: 'formy-zatrudnienia', element: <FormyZatrudnieniaPage /> },
            ],
          },

          {
            element: <ProtectedRoute guard={(ctx) => ctx.isSupervisor || ctx.hasModuleAccess('absences')} />,
            children: [
              { path: 'nieobecnosci', element: <ComingSoonPage title="Nieobecności" /> },
              { path: 'bilanse-urlopow', element: <ComingSoonPage title="Bilanse urlopów" /> },
            ],
          },

          {
            element: <ProtectedRoute guard={(ctx) => ctx.hasLinkedEmployee} />,
            children: [{ path: 'moje-nieobecnosci', element: <ComingSoonPage title="Moje nieobecności" /> }],
          },

          {
            element: <ProtectedRoute requireModule="services" />,
            children: [
              // Usługi — Faza 2. URL-e po polsku (/uslugi/nowa, /uslugi/:id,
              // /uslugi/:id/edytuj), wzorem Klientów/Sprzedawców.
              { path: 'uslugi', element: <ServicesListPage /> },
              { path: 'uslugi/nowa', element: <ServiceFormPage mode="create" /> },
              { path: 'uslugi/:id/edytuj', element: <ServiceFormPage mode="edit" /> },
              { path: 'uslugi/:id', element: <ServiceDetailPage /> },
              { path: 'kategorie-uslug', element: <ServiceCategoriesPage /> },
            ],
          },

          {
            element: <ProtectedRoute requireModule="data_correction" />,
            children: [
              { path: 'korekta/wizyty', element: <ComingSoonPage title="Edycja wizyt" /> },
              { path: 'korekta/tabela', element: <ComingSoonPage title="Tabela wizyt" /> },
            ],
          },

          // Literal-role gates (D14 pt. 4) — NOT a 'settings' module check.
          {
            element: <ProtectedRoute guard={(ctx) => ctx.user?.role === 'superuser' || ctx.user?.role === 'admin'} />,
            children: [{ path: 'uzytkownicy', element: <ComingSoonPage title="Użytkownicy" /> }],
          },
          {
            element: <ProtectedRoute guard={(ctx) => ctx.user?.role === 'superuser'} />,
            children: [{ path: 'poziomy-dostepu', element: <ComingSoonPage title="Poziomy dostępu" /> }],
          },

          {
            element: <ProtectedRoute requireModule="settings" />,
            children: [
              { path: 'ustawienia/sms', element: <SmsSettingsPage /> },
              { path: 'ustawienia/sms/historia', element: <SmsLogPage /> },
            ],
          },

          {
            element: <ProtectedRoute requireModule="data_import" />,
            children: [{ path: 'import-danych', element: <ComingSoonPage title="Import danych" /> }],
          },

          { path: '*', element: <ComingSoonPage title="Nie znaleziono" /> },
        ],
      },
    ],
  },
]);
