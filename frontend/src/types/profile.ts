import type { ModulePermissions } from './rbac';

/** `GET /auth/profile` (routes/auth/routes.py `_profile_payload`). The employee
 * block is a server-side allowlist: it never carries compensation fields. */
export interface ProfileUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  role_display_name: string;
  is_active: boolean;
  last_login: string | null;
  created_at: string | null;
}

export interface ProfileEmployee {
  id: number;
  first_name: string;
  last_name: string;
  position: string | null;
  employment_status: string;
  hire_date: string | null;
}

export interface ProfileResponse {
  success: true;
  user: ProfileUser;
  employee: ProfileEmployee | null;
  permissions: ModulePermissions;
  module_display_names: Record<string, string>;
}

export interface ChangePasswordPayload {
  old_password: string;
  new_password: string;
  confirm_password: string;
}
