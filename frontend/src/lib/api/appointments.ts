import { api } from './client';
import type {
  AppointmentDetailResponse,
  AppointmentFormService,
  AppointmentsListResponse,
  AppointmentStatus,
  CalendarAbsence,
  ConflictCheckResult,
  EmployeeOption,
  MultiEmployeeScheduleResponse,
} from '../../types/appointment';

interface CreateAppointmentPayload {
  client_id: number;
  employee_id: number;
  service_ids: number[];
  appointment_date: string;
  start_time: string;
  notes: string | null;
}

interface CreateAppointmentResult {
  success: true;
  appointment_id: number;
}

interface UpdateAppointmentServicePayload {
  service_id: number;
  price_charged: number;
  duration_minutes: number;
  is_addon: boolean;
}

interface UpdateAppointmentPayload {
  client_id: number;
  employee_id: number;
  status: AppointmentStatus;
  appointment_date: string;
  start_time: string;
  notes: string | null;
  services: UpdateAppointmentServicePayload[];
  force?: boolean;
  timing_change_by?: 'client' | 'salon';
  discount_amount?: number;
  satisfaction_score?: number;
}

/**
 * Client-side wrapper over `routes/appointment_routes.py`'s `/api/appointments/*`
 * (module-inventory.md: szósty moduł Fazy 2). Only the endpoints this round's
 * pages actually use — the absence-conflict-resolution and SMS-adjacent
 * endpoints are deliberately not wrapped here (out of scope, see
 * `types/appointment.ts`'s header comment).
 */
export const appointmentsApi = {
  /** GET /api/appointments — date-range/employee/status filtered list.
   * `mode: 'latest'` (used by the Dashboard widget) isn't wrapped here — this
   * client is for the Wizyty pages, which always pass a date range. */
  list: (params: { start_date: string; end_date: string; employee_id?: number; status?: string }) =>
    api.get<AppointmentsListResponse>('/api/appointments', params),

  get: (id: number) => api.get<AppointmentDetailResponse>(`/api/appointments/${id}`),

  create: (payload: CreateAppointmentPayload) => api.post<CreateAppointmentResult>('/api/appointments', payload),

  update: (id: number, payload: UpdateAppointmentPayload) => api.put<{ success: true }>(`/api/appointments/${id}`, payload),

  updateStatus: (id: number, status: AppointmentStatus, cancellationReason?: string) =>
    api.put<{ success: boolean }>(`/api/appointments/${id}/status`, { status, cancellation_reason: cancellationReason }),

  complete: (id: number, paymentMethod?: string, discountAmount?: number) =>
    api.post<{ success: true }>(`/api/appointments/${id}/complete`, { payment_method: paymentMethod, discount_amount: discountAmount }),

  delete: (id: number) => api.del<{ success: true; restore_url: string }>(`/api/appointments/${id}`),

  restore: (id: number) => api.post<{ success: true; message: string }>(`/api/appointments/${id}/restore`),

  checkConflict: (params: { employee_id: number; client_id?: number; appointment_date: string; start_time: string; duration_minutes: number; exclude_appointment_id?: number }) =>
    api.get<ConflictCheckResult>('/api/appointments/check-conflict', params),

  employees: () => api.get<EmployeeOption[]>('/api/appointments/employees'),

  absences: (startDate: string, endDate: string) =>
    api.get<{ success: true; absences: CalendarAbsence[] }>('/api/appointments/absences', { start_date: startDate, end_date: endDate }).then((r) => r.absences),

  multiEmployeeSchedule: (date: string, offset = 0, limit = 8) =>
    api.get<MultiEmployeeScheduleResponse>('/api/appointments/multi-employee-schedule', { date, offset, limit }),

  /** GET /api/employees/<id>/services — reused from the already-built
   * Pracownicy module's endpoint (not a `/appointments/*` route), filtered
   * client-side to `service_type === 'main'` where the original create.html
   * did (addons are added post-creation from the detail page instead). */
  employeeServices: (employeeId: number) => api.get<{ success: true; services: AppointmentFormService[] }>(`/api/employees/${employeeId}/services`).then((r) => r.services),

  availableAddons: (appointmentId: number) => api.get<{ success: true; addons: AppointmentFormService[] }>(`/api/appointments/${appointmentId}/addons`).then((r) => r.addons),

  addAddon: (appointmentId: number, serviceId: number) => api.post<{ success: true }>(`/api/appointments/${appointmentId}/addons`, { service_id: serviceId }),

  setSatisfaction: (appointmentId: number, score: number) => api.patch<{ success: true }>(`/api/appointments/${appointmentId}/satisfaction`, { score }),

  /** GET /api/appointments/<id>/events — SSE stream of confirmation-status
   * changes (edit form's live badge). Not a fetch — returns the raw URL for
   * an EventSource, which needs a plain GET-able URL, not the JSON `api`
   * wrapper (SSE isn't a JSON response). */
  eventsUrl: (appointmentId: number) => `/api/appointments/${appointmentId}/events`,
};
