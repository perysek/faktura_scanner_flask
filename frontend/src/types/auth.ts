/**
 * Shapes mirrored 1:1 from `config/auth_config.py`'s `get_all_permission_flags`
 * (the same function `app.py`'s Jinja context processor already uses) — see
 * `GET /auth/me` in routes/auth/routes.py. One source of truth for what a
 * module permission means, shared by the React frontend and any remaining
 * Jinja page during the migration.
 */
export interface PermissionFlags {
  has_access: boolean;
  read_only: boolean;
  own_data: boolean;
}

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
}

/**
 * The predicate context passed to a sidebar NavLinkConfig.visible() and a
 * ProtectedRoute guard() — DESIGN.md §13.5. Both must express the *exact
 * same* access rule for a given route; this shared shape is what makes that
 * possible without copy-pasting the same boolean expression twice.
 */
export interface NavVisibilityCtx {
  user: AuthUser | null;
  isSupervisor: boolean;
  hasLinkedEmployee: boolean;
  hasModuleAccess: (moduleName: string) => boolean;
  /** Access AND NOT read_only — mirrors the backend's MUTATING_METHODS guard
   * in `module_permission_required` (config/auth_config.py). Not part of
   * DESIGN.md's minimal ctx sketch, but required to gate write-only UI
   * (Add/Edit/Delete buttons) exactly like `user_write_permissions` already
   * does in the Jinja templates it replaces. */
  hasModuleWrite: (moduleName: string) => boolean;
}
