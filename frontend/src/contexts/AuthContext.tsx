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
}

interface LoginResult {
  success: boolean;
  error?: string;
}

interface AuthContextValue extends NavVisibilityCtx {
  isLoading: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<LoginResult>;
  logout: () => Promise<void>;
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
  const [isLoading, setIsLoading] = useState(true);

  const hydrate = useCallback(async () => {
    try {
      const data = await api.get<MeResponse>('/auth/me');
      setUser(data.user);
      setPermissions(data.permissions);
      setIsSupervisor(data.is_supervisor);
      setHasLinkedEmployee(data.has_linked_employee);
    } catch (err) {
      // 401 (no session) is the expected "logged out" outcome, not an error
      // to surface — anything else (network failure) also just means "we
      // don't know who this is," so the route guard sends them to /login.
      setUser(null);
      setPermissions({});
      setIsSupervisor(false);
      setHasLinkedEmployee(false);
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
    }
  }, []);

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
      hasModuleAccess,
      hasModuleWrite,
      isLoading,
      login,
      logout,
    }),
    [user, isSupervisor, hasLinkedEmployee, hasModuleAccess, hasModuleWrite, isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
