import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api, ApiError } from '../lib/api/client';
import type { AuthUser, NavVisibilityCtx, PermissionFlags } from '../types/auth';

interface MeResponse {
  success: true;
  user: AuthUser;
  permissions: Record<string, PermissionFlags>;
  is_supervisor: boolean;
  has_linked_employee: boolean;
  linked_employee_id: number | null;
  is_superuser: boolean;
  admin_view_active: boolean;
  own_data_active: boolean;
}

interface LoginResult {
  success: boolean;
  error?: string;
}

interface AuthContextValue extends NavVisibilityCtx {
  isLoading: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<LoginResult>;
  logout: () => Promise<void>;
  /** "Widok administratora" (config/admin_view.py) — superuser-only, always
   * false for anyone else regardless of stale client state. */
  isSuperuser: boolean;
  adminViewActive: boolean;
  ownDataActive: boolean;
  /** Posts whichever of "Widok administratora" / "Dane własne" actually
   * changed (admin-view first — the own-data endpoint 400s unless admin view
   * is already ON) to the Flask session flags shared with the Jinja pages
   * (routes/main_routes.py `/api/admin-view` + `/api/own-data`), then reloads
   * once so every server render AND every SPA fetch re-runs under the new
   * flags — same full-reload contract as the Jinja sidebar's own toggle JS,
   * not a client-side state patch. No-op (no reload) if neither changed. */
  applyScopeToggles: (adminView: boolean, ownData: boolean) => Promise<void>;
  /** The employee record linked to the logged-in user, if any — used as the
   * default "Pracownik" filter selection (mobile Wizyty filter modal), not
   * just the `hasLinkedEmployee` boolean the nav-visibility rules use. */
  linkedEmployeeId: number | null;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Session-check-on-load pattern (DESIGN.md §15.1): the SPA has no
 * server-rendered "who is logged in" context, so on every fresh load it
 * calls `GET /auth/me` once and holds `isLoading: true` until that resolves.
 * Every piece of UI that depends on auth state must wait out this initial
 * load rather than assume "no user yet" means "logged out" — collapsing
 * those two states causes a login-page flash on every hard refresh of a
 * protected page.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [permissions, setPermissions] = useState<Record<string, PermissionFlags>>({});
  const [isSupervisor, setIsSupervisor] = useState(false);
  const [hasLinkedEmployee, setHasLinkedEmployee] = useState(false);
  const [linkedEmployeeId, setLinkedEmployeeId] = useState<number | null>(null);
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [adminViewActive, setAdminViewActive] = useState(false);
  const [ownDataActive, setOwnDataActive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const hydrate = useCallback(async () => {
    try {
      const data = await api.get<MeResponse>('/auth/me');
      setUser(data.user);
      setPermissions(data.permissions);
      setIsSupervisor(data.is_supervisor);
      setHasLinkedEmployee(data.has_linked_employee);
      setLinkedEmployeeId(data.linked_employee_id);
      setIsSuperuser(data.is_superuser);
      setAdminViewActive(data.admin_view_active);
      setOwnDataActive(data.own_data_active);
    } catch (err) {
      // 401 (no session) is the expected "logged out" outcome, not an error
      // to surface — anything else (network failure) also just means "we
      // don't know who this is," so the route guard sends them to /login.
      setUser(null);
      setPermissions({});
      setIsSupervisor(false);
      setHasLinkedEmployee(false);
      setLinkedEmployeeId(null);
      setIsSuperuser(false);
      setAdminViewActive(false);
      setOwnDataActive(false);
      if (!(err instanceof ApiError) || err.status !== 401) {
        console.error('Session check failed', err);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const login = useCallback(
    async (email: string, password: string, remember: boolean): Promise<LoginResult> => {
      try {
        await api.post('/auth/login', { email, password, remember });
        // Re-fetch /auth/me to hydrate the full user/permissions/role context
        // (DESIGN.md §15.2 step 2) rather than trusting the login response.
        await hydrate();
        return { success: true };
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem';
        return { success: false, error: message };
      }
    },
    [hydrate],
  );

  const logout = useCallback(async () => {
    try {
      await api.get('/auth/logout');
    } finally {
      setUser(null);
      setPermissions({});
      setIsSupervisor(false);
      setHasLinkedEmployee(false);
      setLinkedEmployeeId(null);
      setIsSuperuser(false);
      setAdminViewActive(false);
      setOwnDataActive(false);
    }
  }, []);

  const applyScopeToggles = useCallback(async (adminView: boolean, ownData: boolean) => {
    let changed = false;
    if (adminView !== adminViewActive) {
      await api.post<{ ok: boolean; enabled: boolean }>('/api/admin-view', { enabled: adminView });
      changed = true;
    }
    // Only POST own-data while the *target* admin-view is ON — the endpoint
    // 400s ("Najpierw wlacz widok administratora") whenever admin-view is
    // currently off, which it already is server-side the instant the
    // admin-view POST above turns it off (that POST auto-clears own-data too).
    // Skipping this call in that case avoids the 400 that used to abort the
    // whole function before it reached the reload below.
    if (adminView && ownData !== ownDataActive) {
      await api.post<{ ok: boolean; enabled: boolean }>('/api/own-data', { enabled: ownData });
      changed = true;
    }
    if (changed) window.location.reload();
  }, [adminViewActive, ownDataActive]);

  const hasModuleAccess = useCallback(
    (moduleName: string) => permissions[moduleName]?.has_access ?? false,
    [permissions],
  );
  const hasModuleWrite = useCallback(
    (moduleName: string) => {
      const flags = permissions[moduleName];
      return !!flags && flags.has_access && !flags.read_only;
    },
    [permissions],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isSupervisor,
      hasLinkedEmployee,
      linkedEmployeeId,
      hasModuleAccess,
      hasModuleWrite,
      isLoading,
      login,
      logout,
      isSuperuser,
      adminViewActive,
      ownDataActive,
      applyScopeToggles,
    }),
    [
      user,
      isSupervisor,
      hasLinkedEmployee,
      linkedEmployeeId,
      hasModuleAccess,
      hasModuleWrite,
      isLoading,
      login,
      logout,
      isSuperuser,
      adminViewActive,
      ownDataActive,
      applyScopeToggles,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
