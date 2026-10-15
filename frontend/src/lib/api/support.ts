/** Support tickets, author side — routes/support_routes.py (`/api/support/...`). */
import { api } from './client';

export type TicketKind = 'problem' | 'idea';
export type TicketStatus = 'new' | 'seen' | 'in_progress' | 'waiting_user' | 'resolved' | 'closed';

export interface TicketAttachment {
  id: number;
  filename: string;
  mime: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  url: string;
}

export interface TicketMessage {
  id: number;
  author_kind: 'user' | 'admin' | 'system';
  author_name: string | null;
  body: string;
  is_internal: boolean;
  event: 'status' | 'priority' | 'assigned' | null;
  meta: { from?: string; to?: string | number | null; reason?: string; by?: string } | null;
  created_at: string;
  attachments: TicketAttachment[];
}

export interface TicketSummary {
  id: number;
  kind: TicketKind;
  area_label: string;
  title: string;
  status: TicketStatus;
  close_reason: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  unread: boolean;
  last_body: string;
  last_author_kind: 'user' | 'admin' | null;
  last_message_at: string | null;
}

export interface TicketThread {
  id: number;
  kind: TicketKind;
  area_label: string;
  title: string;
  status: TicketStatus;
  close_reason: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  messages: TicketMessage[];
  can_reply: boolean;
}

/** What the SENDER sees for each status (plan §5) — human phrases, no jargon. */
export const USER_STATUS: Record<TicketStatus, { label: string; tone: 'neutral' | 'info' | 'warn' | 'ok' | 'muted' }> = {
  new: { label: 'Wysłane', tone: 'neutral' },
  seen: { label: 'Przeczytane', tone: 'info' },
  in_progress: { label: 'Zajmujemy się tym', tone: 'info' },
  waiting_user: { label: 'Czekamy na Twoją odpowiedź', tone: 'warn' },
  resolved: { label: 'Gotowe — sprawdź, czy działa', tone: 'ok' },
  closed: { label: 'Zakończone', tone: 'muted' },
};

function filesForm(fields: Record<string, string>, files: File[]): FormData {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  for (const file of files) form.append('files', file, file.name);
  return form;
}

export const supportApi = {
  create: (fields: { kind: TicketKind; area: string; area_label: string; body: string; context: string }, files: File[]) =>
    api.post<{ success: true; id: number }>('/api/support/tickets', filesForm(fields, files)),
  list: () => api.get<{ success: true; tickets: TicketSummary[]; unread: number }>('/api/support/tickets'),
  get: (id: number) => api.get<{ success: true; ticket: TicketThread }>(`/api/support/tickets/${id}`),
  reply: (id: number, body: string, files: File[]) =>
    api.post<{ success: true; id: number }>(`/api/support/tickets/${id}/messages`, filesForm({ body }, files)),
  confirm: (id: number) => api.post<{ success: true }>(`/api/support/tickets/${id}/confirm`),
  unreadCount: () => api.get<{ success: true; unread: number }>('/api/support/unread-count'),
};
