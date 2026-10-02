import type { RecentNote } from './visitNote';

/**
 * Mirrors GET /api/clients / GET /api/clients/<id> 1:1 — routes/api_routes.py
 * lines ~2552-3078 (phase-01-pilot-clients.md §1.2). Dates are ISO strings
 * (backend calls `.isoformat()`), not Date objects.
 */
export interface Client {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string | null;
  email: string | null;
  date_of_birth: string | null;
  notes: string | null;
  preferences: Record<string, unknown> | null;
  first_visit_date: string | null;
  last_visit_date: string | null;
  is_active: boolean;
  age: number | null;
  created_at: string | null;
  updated_at: string | null;
  // Present only on GET /api/clients (joined visit-stats query) — absent on
  // the single-client GET /api/clients/<id>.
  completed_visits?: number;
  no_show_count?: number;
  cancelled_count?: number;
  rescheduled_count?: number;
  visits_last_8w?: number;
  next_visit_date?: string | null;
  next_visit_time?: string | null;
  next_visit_employee?: string | null;
  // Only on GET /api/clients?include_notes=1, and only for a caller with
  // `appointments` access: the 2 newest visit notes, newest first.
  recent_notes?: RecentNote[];
  // Only on GET /api/clients?include_last_service=1: the main service of the client's latest
  // completed visit (null when there is none) — the new-visit form preselects it.
  last_service_id?: number | null;
}

export interface DuplicateMatch {
  id: number;
  name: string;
  field: 'name' | 'phone';
  severity: 'high' | 'medium' | 'low';
  category: string;
  message: string;
}

export interface ClientPreference {
  id: number;
  client_id: number;
  preferred_employee_id: number;
  employee_name?: string;
  service_id: number | null;
  service_name?: string | null;
  service_category?: string | null;
  notes: string | null;
}

export interface ClientAppointmentHistoryItem {
  id: number;
  appointment_date: string;
  start_time: string;
  end_time: string;
  employee_name?: string;
  status: string;
  total_price: number | null;
}

export interface ClientStatistics {
  total_clients: number;
  active_clients: number;
  recent_visitors: number;
  clients_with_birthdate: number;
}

/** {client_id: [week0_count, ..., week_n_count]} — GET /api/clients/visit-trends. */
export type VisitTrends = Record<number, number[]>;
