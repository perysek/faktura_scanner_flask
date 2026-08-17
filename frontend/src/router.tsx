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
          // authenticated user (D14 point 5).
          { path: 'dashboard', element: <ComingSoonPage title="Koszty" /> },
          { path: 'instrukcja', element: <ComingSoonPage title="Instrukcja obsługi" /> },
          { path: 'profil', element: <ComingSoonPage title="Profil" /> },

          // requireModule="invoices" — includes historia/ustawienia/email,
          // which the sidebar mis-labels 'reports'/'settings' (D14 pts 1-2).
          {
            element: <ProtectedRoute requireModule="invoices" />,
            children: [
              { path: 'faktury', element: <ComingSoonPage title="Lista faktur" /> },
              { path: 'sprzedawcy', element: <ComingSoonPage title="Sprzedawcy" /> },
              { path: 'import-dokumentow', element: <ComingSoonPage title="Import dokumentów" /> },
              { path: 'historia', element: <ComingSoonPage title="Historia zmian" /> },
              { path: 'ustawienia/email', element: <ComingSoonPage title="Ustawienia" /> },
            ],
          },

          // requireModule="appointments" — includes analytics/kpi, which the
          // sidebar mis-nests under the invoices-gated Finanse section (D14 pt. 3).
          {
            element: <ProtectedRoute requireModule="appointments" />,
            children: [
              { path: 'wizyty', element: <ComingSoonPage title="Wizyty" /> },
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
              { path: 'pracownicy', element: <ComingSoonPage title="Pracownicy" /> },
              { path: 'formy-zatrudnienia', element: <ComingSoonPage title="Rodzaje zatrudnienia" /> },
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
              { path: 'uslugi', element: <ComingSoonPage title="Usługi" /> },
              { path: 'kategorie-uslug', element: <ComingSoonPage title="Kategorie usług" /> },
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
            children: [{ path: 'ustawienia/sms', element: <ComingSoonPage title="Ustawienia SMS" /> }],
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
