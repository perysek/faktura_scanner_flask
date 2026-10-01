import { api } from './client';
import type { NoteableVisit, VisitNotesPage } from '../../types/visitNote';

/**
 * Client-side wrapper over routes/visit_note_routes.py.
 *
 * Deliberately NOT under `/api/appointments`: lib/api/client.ts fires the
 * "appointments changed" event (calendar + income refetch) for any write below
 * that prefix, and a note changes neither.
 */
export const visitNotesApi = {
  /** A client's notes across all their visits, newest edit first. Pass `appointmentId`
   * on a visit page so `can_add` reflects that visit (completed, in scope). */
  list: (clientId: number, params: { limit?: number; offset?: number; appointmentId?: number } = {}) =>
    api.get<{ success: true } & VisitNotesPage>(`/api/clients/${clientId}/visit-notes`, {
      limit: params.limit,
      offset: params.offset,
      appointment_id: params.appointmentId,
    }),

  /** Completed visits (in the caller's scope) a note can be attached to. */
  visits: (clientId: number) =>
    api.get<{ success: true; visits: NoteableVisit[] }>(`/api/clients/${clientId}/visit-notes/visits`).then((r) => r.visits),

  create: (appointmentId: number, noteText: string) =>
    api.post<{ success: true; id: number }>('/api/visit-notes', { appointment_id: appointmentId, note_text: noteText }),

  update: (noteId: number, noteText: string) => api.put<{ success: true }>(`/api/visit-notes/${noteId}`, { note_text: noteText }),

  remove: (noteId: number) => api.del<{ success: true }>(`/api/visit-notes/${noteId}`),
};
