/** Types for Użytkownicy + Poziomy dostępu (RBAC) + Profil.
 * Mirror routes/users/routes.py, routes/roles/routes.py and routes/auth/routes.py field names. */

export interface UserListRow {
  id: number;
  email: string;
  full_name: string;
  role: string;
  role_display_name: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string | null;
  employee_id: number | null;
  employee_name: string | null;
}

export interface UserDetail {
  id: number;
  email: string;
  full_name: string;
  role: string;
  role_display_name: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string | null;
}

export interface LinkedEmployee {
  id: number;
  first_name: string;
  last_name: string;
}

export interface AvailableEmployee {
  id: number;
  first_name: string;
  last_name: string;
}

export interface RolePermissionFlags {
  has_access: boolean;
  read_only: boolean;
  own_data: boolean;
  can_edit_price_history: boolean;
  can_send_sms: boolean;
}

/** `/auth/me`-shaped permissions carry only the first three flags; the role
 * endpoints carry all five. Chips render whichever are present. */
export type ModuleFlags = Pick<RolePermissionFlags, 'has_access' | 'read_only' | 'own_data'> &
  Partial<Pick<RolePermissionFlags, 'can_edit_price_history' | 'can_send_sms'>>;

export type ModulePermissions = Record<string, ModuleFlags>;

export interface AssignableRole {
  name: string;
  display_name: string;
  permissions: Record<string, RolePermissionFlags>;
}

export interface RoleListRow {
  id: number;
  name: string;
  display_name: string;
  is_protected: boolean;
  access_count: number;
  user_count: number;
  permissions: Record<string, boolean>;
  permissions_detail: Record<string, RolePermissionFlags>;
}

export interface RoleDetail {
  id: number;
  name: string;
  display_name: string;
  is_protected: boolean;
}
