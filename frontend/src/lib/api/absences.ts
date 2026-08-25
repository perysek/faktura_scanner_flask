import { api } from './client';
import type {
  AbsenceCategory,
  AbsenceRecord,
  AbsenceSupervisor,
  ApproveResult,
  BalanceCheckResult,
  BalanceSummaryEntry,
  ConflictResolution,
  LiveConflictsResult,
} from '../../types/absence';

export interface SubmitAbsencePayload {
  category_id: number;
  date_from: string;
  date_to: string;
  time_from?: string | null;
  time_to?: string | null;
  approver_id: number;
  notes?: string | null;
}

export interface ManualAbsencePayload {
  employee_id: number;
  category_id: number;
  date_from: string;
  date_to: string;
  time_from?: string | null;
  time_to?: string | null;
  notes?: string | null;
}

export interface CategoryPayload {
  name: string;
  description: string;
  absence_full_day: boolean;
  is_tracked: boolean;
  count_period: string;
  resets_at: number;
  default_max_value: number;
  warning_threshold_pct: number;
}

/** `/api/my-absences*` (new, react-migration) + `/absences*` (already JSON,
 * routes/absence_routes.py). See types/absence.ts for scope notes. */
export const absencesApi = {
  myAbsences: () => api.get<{ success: true; absences: AbsenceRecord[]; categories: AbsenceCategory[]; supervisors: AbsenceSupervisor[] }>('/api/my-absences'),

  submit: (payload: SubmitAbsencePayload) => api.post<{ success: true } | { success: false; error: string }>('/api/my-absences/submit', payload),

  cancel: (id: number) => api.post<{ success: true } | { success: false; error: string }>(`/api/my-absences/${id}/cancel`),

  cancelApprovedOwn: (id: number) => api.post<{ success: true } | { success: false; error: string }>(`/api/my-absences/${id}/cancel-approved`),

  previewConflicts: (params: { date_from: string; date_to: string; time_from?: string; time_to?: string }) =>
    api.get<{ success: true; conflicts: Array<{ date: string; start_time: string; end_time: string; client_name: string | null; service_name: string | null }> }>(
      '/my-absences/preview-conflicts',
      params,
    ),

  management: () =>
    api.get<{ success: true; requests_list: AbsenceRecord[]; manual_list: AbsenceRecord[]; categories: AbsenceCategory[]; pending_count: number; is_superuser: boolean }>(
      '/api/absences/management',
    ),

  approve: (id: number) => api.post<{ success: true } & ApproveResult | { success: false; error: string }>(`/absences/${id}/approve`),

  forceApprove: (id: number) => api.post<{ success: true; status: string } | { success: false; error: string }>(`/absences/${id}/approve/force`),

  reject: (id: number, reason: string) => api.post<{ success: true; status: string } | { success: false; error: string }>(`/absences/${id}/reject`, { rejection_reason: reason }),

  cancelApprovedManagement: (id: number) => api.post<{ success: true; status: string } | { success: false; error: string }>(`/absences/${id}/cancel-approved`),

  createManual: (payload: ManualAbsencePayload) => api.post<{ success: true; conflicts?: unknown[] } | { success: false; error: string }>('/absences/manual', payload),

  deleteAbsence: (id: number) => api.del<{ success: true } | { success: false; error: string }>(`/absences/${id}`),

  checkBalance: (payload: { employee_id: number; category_id: number; date_from: string; date_to?: string; time_from?: string; time_to?: string }) =>
    api.post<{ success: true; check: BalanceCheckResult; will_exceed: boolean }>('/api/absence-balance/check', payload),

  allCategories: () => api.get<{ success: true; categories: AbsenceCategory[] }>('/api/absence-categories').then((r) => r.categories),

  createCategory: (payload: CategoryPayload) => api.post<{ success: true; id: number } | { success: false; error: string }>('/absences/categories', payload),

  updateCategory: (id: number, payload: CategoryPayload) => api.put<{ success: true } | { success: false; error: string }>(`/absences/categories/${id}`, payload),

  deleteCategory: (id: number) => api.del<{ success: true } | { success: false; error: string }>(`/absences/categories/${id}`),

  hardDeleteCategory: (id: number) => api.del<{ success: true } | { success: false; error: string }>(`/absences/categories/${id}/permanent`),

  hardDeleteAbsence: (id: number) => api.del<{ success: true; slots_freed?: boolean } | { success: false; error: string }>(`/absences/${id}/permanent`),

  // ── Conflict-resolution modal support (dobudowane 2026-08-25) ────────────

  /** Re-fetched by ConflictResolutionModal after every reassign/reschedule/
   * cancel action — the live list IS the resolved-state (AD-8), there's no
   * separate client-side "resolved" bookkeeping. */
  conflicts: (absenceId: number) => api.get<LiveConflictsResult | { success: false; error: string }>(`/absences/${absenceId}/conflicts`),

  resolutions: (absenceId: number) => api.get<{ success: true; resolutions: ConflictResolution[] }>(`/absences/${absenceId}/resolutions`),

  /** GET /api/absence-balances/summary — {employee_id: BalanceSummaryEntry}.
   * Powers the inline balance-hint next to employee names (Wnioski +
   * L4/Manualne tables); non-critical, callers should swallow failures. */
  balancesSummary: () => api.get<{ success: true; balances: Record<number, BalanceSummaryEntry> }>('/api/absence-balances/summary'),
};
