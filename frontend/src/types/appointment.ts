/** Types for the Wizyty + Kalendarz module — Faza 2 (module-inventory.md: szósty
 * moduł, największy w całej apce — 9449 linii w 10 szablonach + 28 endpointów w
 * `routes/appointment_routes.py`). Zakres tego przebiegu (patrz
 * implementation-log.md dla pełnej listy odłożonych kawałków): lista, widok
 * szczegółów, formularz create/edit, 3 widoki kalendarza (dzień/tydzień/miesiąc),
 * boczny pasek month-cards, skaner "przeszłych wizyt do rozliczenia" (dodany
 * później, deferred-tasks przebieg 2026-08-24). **2026-08-25:** integracja z
 * nieobecnościami (reassign/reschedule/cancel-for-absence, gate
 * `@absence_management_required`) i globalne toasty statusu (status-events
 * polling) DOBUDOWANE — patrz `ReassignmentCandidate`/`AvailableSlot`/
 * `StatusChangeEvent` niżej, `pages/absences/ConflictResolutionModal.tsx` i
 * `components/feedback/StatusEventsPoller.tsx`. Wciąż poza zakresem: wysyłka/
 * log SMS na widoku szczegółów (własny moduł Ustawienia SMS), superadmin
 * power-editor (już poza zakresem — osobny moduł `data_correction`),
 * `/my-visits` (mobilny widok pracownika, bez bramki modułowej — nie ten
 * frontend). */

export type AppointmentStatus = 'scheduled' | 'pending' | 'confirmed' | 'in_progress' | 'completed' | 'cancelled' | 'no_show';

export const STATUS_LABELS: Record<AppointmentStatus, string> = {
  scheduled: 'Zaplanowana',
  pending: 'Oczekująca',
  confirmed: 'Potwierdzona',
  in_progress: 'W trakcie',
  completed: 'Zakończona',
  cancelled: 'Anulowana',
  no_show: 'Nieobecność',
};

/** `config/appointment_statuses.py`'s `VALID_TRANSITIONS` — the backend's own
 * "single source of truth" docstring. Deliberately NOT ported from
 * `list.html`'s JS `VALID_TRANSITIONS` constant, which is missing
 * `scheduled → in_progress` (the documented "walk-in bypass, no confirmation
 * needed") — a stale duplicate in the original app, not a second rule to
 * honour. `completed`/`cancelled`/`no_show` have no further transitions. */
export const VALID_TRANSITIONS: Partial<Record<AppointmentStatus, AppointmentStatus[]>> = {
  scheduled: ['confirmed', 'in_progress', 'cancelled'],
  pending: ['confirmed', 'cancelled'],
  confirmed: ['in_progress', 'cancelled', 'no_show'],
  in_progress: ['completed', 'cancelled'],
};

/** GET /api/appointments/past-pending row — routes/appointment_routes.py's
 * `get_past_pending_appointments()`. Resolvable final statuses only. */
export type PastResolutionStatus = 'completed' | 'cancelled' | 'no_show';

export interface PastPendingAppointment {
  id: number;
  client_id: number;
  client_name: string | null;
  employee_id: number;
  employee_name: string | null;
  appointment_date: string;
  start_time: string;
  end_time: string;
  status: AppointmentStatus;
  service_names: string | null;
  total_price: number;
  notes: string | null;
}

/** List-row shape — GET /api/appointments. Column names read off `dict(row)`
 * on the Python side (a SQL view/join, no dataclass) — inferred from every
 * place list.html/view.html/calendar templates actually read a field off it. */
export interface AppointmentListItem {
  id: number;
  client_id: number;
  client_name: string | null;
  employee_id: number;
  employee_name: string | null;
  appointment_date: string;
  start_time: string;
  end_time: string;
  status: AppointmentStatus;
  /** Comma-joined service names for the row — an appointment usually has 1+
   * services; the list query concatenates them for display, doesn't return
   * an array. */
  service_name: string | null;
  total_price: number | null;
  satisfaction_score: number | null;
  confirmation_status: 'pending' | 'confirmed' | 'declined' | null;
  notes: string | null;
}

export interface AppointmentsListResponse {
  success: true;
  appointments: AppointmentListItem[];
  count: number;
  sms_sent_map: Record<string, string[]>;
  sms_types: Array<{ type_key: string; name: string }>;
}

export interface AppointmentService {
  appointment_service_id?: number;
  service_id: number;
  service_name: string;
  price_charged: number;
  duration_minutes: number;
  is_addon: boolean;
  added_at?: string | null;
  current_catalogue_price?: number | null;
}

export interface AppointmentTotals {
  main_total: number;
  addon_total: number;
  addon_count: number;
  total_commission: number;
  total_price: number;
}

/** GET /api/appointments/<id> — full detail, spread at the top level
 * (`{success: true, **details}`), not nested under an `appointment` key
 * for the services/totals parts. */
export interface AppointmentDetail {
  id: number;
  client_id: number;
  client_name: string | null;
  employee_id: number;
  employee_name: string | null;
  appointment_date: string;
  start_time: string;
  end_time: string;
  total_duration: number;
  status: AppointmentStatus;
  notes: string | null;
  satisfaction_score: number | null;
  rating_status?: string | null;
  rated_on?: string | null;
  confirmation_status: 'pending' | 'confirmed' | 'declined' | null;
}

export interface AppointmentDetailResponse {
  success: true;
  appointment: AppointmentDetail;
  main_services: AppointmentService[];
  addon_services: AppointmentService[];
  totals: AppointmentTotals;
  can_add_addon: boolean;
}

export interface AppointmentFormService {
  service_id: number;
  service_name: string;
  effective_duration: number;
  effective_price: number;
  service_type: 'main' | 'addon';
}

export interface ConflictCheckResult {
  success: true;
  has_conflict: boolean;
  conflict_type: 'employee' | 'client' | null;
  message: string | null;
}

export interface EmployeeOption {
  id: number;
  full_name: string;
  position: string | null;
}

export interface CalendarAbsence {
  employee_id: number;
  date_from: string;
  date_to: string;
  time_from: string | null;
  time_to: string | null;
  category_name: string;
  status: 'approved' | 'pending';
}

/** GET /api/appointments/multi-employee-schedule — day-view's paginated
 * multi-employee columns. */
export interface MultiEmployeeScheduleResponse {
  success: true;
  date: string;
  employees: EmployeeOption[];
  schedules: Record<number, AppointmentListItem[]>;
  absences: Record<number, Array<{ id: number; category_name: string; time_from: string | null; time_to: string | null; status: string }>>;
  total_employees: number;
  page: number;
  total_pages: number;
  has_prev: boolean;
  has_next: boolean;
}

// ── Absence conflict-resolution (Faza 3, dobudowane 2026-08-25) ─────────────
// `routes/appointment_routes.py`'s `@absence_management_required` cluster —
// consumed by `pages/absences/ConflictResolutionModal.tsx`, triggered from
// AbsencesManagementPage's approve-conflict flow (the only entry point this
// ever had, even in the legacy Jinja app — there is no separate Wizyty-side
// UI for it).

/** GET /api/appointments/<id>/reassignment-candidates — eligible replacement
 * employees (`AppointmentBusinessService.get_reassignment_candidates`: can
 * perform every service ∩ not absence-approved ∩ not double-booked).
 * `is_preferred: false` flags a stylist not on the client's preferred list —
 * shown as a warning icon, not a disqualification. */
export interface ReassignmentCandidate {
  employee_id: number;
  name: string;
  position: string | null;
  is_preferred: boolean;
}

export interface ReassignForAbsenceResult {
  success: true;
  /** Appointment ids the reassignment was applied to (always includes the
   * triggering one; more than one only when `bulk: true`). */
  applied: number[];
  /** bulk-only: appointment ids skipped because this employee wasn't a valid
   * candidate for them — surfaced to the user, not silently dropped. */
  skipped: number[];
}

export interface RescheduleForAbsenceResult {
  success: true;
  appointment_id: number;
}

export interface CancelForAbsenceResult {
  success: true;
  applied: number[];
}

/** GET /api/appointments/available-slots — reschedule step's date picker. */
export interface AvailableSlot {
  start_time: string;
  end_time: string;
  available: boolean;
}

export interface AvailableSlotsResponse {
  success: true;
  slots: AvailableSlot[];
}

// ── Global status-change toasts (Faza "P10", dobudowane 2026-08-25) ─────────
// Ported from templates/base.html's 5s-poll toast, which is still live for
// the legacy Jinja pages — same endpoint, same `since=`/`server_time`
// catch-up contract, now also driving `StatusEventsPoller`.

export interface StatusChangeEvent {
  client_name: string | null;
  new_status: AppointmentStatus;
}

export interface StatusEventsResponse {
  events: StatusChangeEvent[];
  server_time: string;
}
