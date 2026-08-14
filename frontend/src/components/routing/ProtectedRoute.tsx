import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import type { NavVisibilityCtx } from '../../types/auth';
import { LoadingScreen } from '../layout/LoadingScreen';

export interface ProtectedRouteProps {
  /** Sugar for the common single-module case. */
  requireModule?: string;
  /** Escape hatch for anything that isn't a plain single-module check —
   * literal-role gates, OR-of-conditions, "linked entity" gates. Wins if
   * both `requireModule` and `guard` are given. Receives the same ctx shape
   * as a sidebar NavLinkConfig.visible() — reuse the exact same boolean
   * expression for both (DESIGN.md §13.5/§14.2). */
  guard?: (ctx: NavVisibilityCtx) => boolean;
}

/**
 * Bare authentication gate (+ optional module/guard check) — DESIGN.md §14.1/
 * §14.2. Waits out AuthContext's initial session-check before deciding
 * anything, so a hard refresh on a protected route never flash-redirects to
 * /login before the real session state is known.
 */
export function ProtectedRoute({ requireModule, guard }: ProtectedRouteProps) {
  const auth = useAuth();
  const location = useLocation();

  if (auth.isLoading) {
    return <LoadingScreen />;
  }

  if (!auth.user) {
    return <Navigate to="/login" state={{ next: location.pathname }} replace />;
  }

  const ctx: NavVisibilityCtx = {
    user: auth.user,
    isSupervisor: auth.isSupervisor,
    hasLinkedEmployee: auth.hasLinkedEmployee,
    hasModuleAccess: auth.hasModuleAccess,
    hasModuleWrite: auth.hasModuleWrite,
  };

  const allowed = guard ? guard(ctx) : requireModule ? auth.hasModuleAccess(requireModule) : true;

  // Authenticated but disallowed → bounced to the default landing page, never
  // a blank/broken screen and never back to /login (§14.2).
  if (!allowed) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}
