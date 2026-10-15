import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@shared/contexts/AuthContext';
import { AuthLayout } from '@shared/pages/auth/AuthLayout';
import { Button } from '@shared/components/ui/Button';

export const DESK_MODULE = 'support_tickets';

/**
 * Two gates, same as the backend's: a session (else → /login) AND the
 * 'support_tickets' module (Poziomy dostępu → "Zgłoszenia — panel obsługi").
 * The API refuses every /api/support/admin call without the module anyway — this
 * only spares a logged-in salon user an empty, failing desk.
 */
export function DeskGate() {
  const auth = useAuth();
  const location = useLocation();

  if (auth.isLoading) {
    return (
      <div className="desk-loading" role="status">
        Wczytuję…
      </div>
    );
  }
  if (!auth.user) return <Navigate to="/login" replace state={{ next: location.pathname }} />;
  if (!auth.hasModuleAccess(DESK_MODULE)) {
    return (
      <AuthLayout>
        <div className="desk-noaccess">
          <h1 className="refined-title">Brak dostępu</h1>
          <p>
            Konto <strong>{auth.user.email}</strong> nie ma uprawnienia „Zgłoszenia — panel obsługi”. Włączysz je w aplikacji
            salonu: Poziomy dostępu → Edytuj rolę.
          </p>
          <Button variant="secondary" icon="logout" onClick={() => auth.logout()}>
            Wyloguj
          </Button>
        </div>
      </AuthLayout>
    );
  }
  return <Outlet />;
}
