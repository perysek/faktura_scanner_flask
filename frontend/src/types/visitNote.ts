/**
 * Visit notes ("Uwagi i zalecenia z wizyt") — mirrors routes/visit_note_routes.py
 * and services/visit_note_service.py (`_serialize`). created_on / created_by are
 * stored but deliberately never sent.
 */
export interface VisitNote {
  id: number;
  appointment_id: number;
  /** YYYY-MM-DD — the visit's date. */
  appointment_date: string;
  client_name: string | null;
  /** First service of the visit (a main service before any add-on). */
  service_name: string | null;
  note_text: string;
  /** Warsaw-local ISO without a designator, e.g. "2026-10-01T08:15:00". */
  updated_at: string | null;
  updated_by_name: string | null;
  /** Server-decided: writable role AND the visit is inside the caller's own-data scope. */
  can_edit: boolean;
}

export interface VisitNotesPage {
  notes: VisitNote[];
  total: number;
  has_more: boolean;
  /** Server-decided: whether the "Dodaj uwagę" button should show at all. */
  can_add: boolean;
}

/** A completed visit a note can be attached to (client-page picker). */
export interface NoteableVisit {
  appointment_id: number;
  appointment_date: string;
  service_name: string | null;
  employee_name: string | null;
}

/** One entry of the list columns' digest: `include_notes=1` on the clients and visits lists. */
export interface RecentNote {
  text: string;
  /** Warsaw-local ISO without a designator. */
  at: string | null;
}
