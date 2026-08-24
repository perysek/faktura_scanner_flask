/** Types for Użytkownicy + Role (RBAC) — Faza 2, "Wymaga audytu" list.
 * Mirrors routes/users/routes.py + routes/roles/routes.py field names. */

export interface UserListRow {
  id: number;
  email: string;
  full_name: string;
  role: string;
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
  is_active: boolean;
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

export interface AssignableRole {
  name: string;
  display_name: string;
}

export interface RolePermissionFlags {
  has_access: boolean;
  read_only: boolean;
  own_data: boolean;
  can_edit_price_history: boolean;
  can_send_sms: boolean;
}

export interface RoleListRow {
  id: number;
  name: string;
  display_name: string;
  is_protected: boolean;
  access_count: number;
  permissions: Record<string, boolean>;
  permissions_detail: Record<string, RolePermissionFlags>;
}

export interface RoleDetail {
  id: number;
  name: string;
  display_name: string;
  is_protected: boolean;
}

export const MODULE_LABELS: Record<string, string> = {
  invoices: 'Faktury',
  appointments: 'Wizyty',
  clients: 'Klienci',
  employees: 'Pracownicy',
  services: 'Usługi',
  settings: 'Ustawienia',
  reports: 'Historia',
};
