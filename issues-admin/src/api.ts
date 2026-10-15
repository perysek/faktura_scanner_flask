/** Agent side of the support-ticket API — routes/support_routes.py `/api/support/admin/*`. */
import { api } from '@shared/lib/api/client';

export type Kind = 'problem' | 'idea';
export type Status = 'new' | 'seen' | 'in_progress' | 'waiting_user' | 'resolved' | 'closed';
export type Priority = 'low' | 'normal' | 'high' | 'urgent';
export type CloseReason = 'done' | 'confirmed' | 'declined' | 'duplicate';
export type ViewKey =
  | 'open'
  | 'unread'
  | 'new'
  | 'in_progress'
  | 'waiting_user'
  | 'resolved'
  | 'mine'
  | 'unassigned'
  | 'closed'
  | 'all';
export type SortKey = 'updated' | 'created' | 'oldest' | 'priority';

export interface Attachment {
  id: number;
  filename: string;
  mime: string;
  size_bytes: number;
  width: number | null;
  height: number | null;
  url: string;
}

export interface Message {
  id: number;
  author_kind: 'user' | 'admin' | 'system';
  author_name: string | null;
  body: string;
  is_internal: boolean;
  event: 'status' | 'priority' | 'assigned' | null;
  meta: { from?: string; to?: string | number | null; reason?: string; by?: string } | null;
  created_at: string;
  attachments: Attachment[];
}

export interface TicketRow {
  id: number;
  kind: Kind;
  area: string;
  area_label: string;
  title: string;
  status: Status;
  close_reason: CloseReason | null;
  priority: Priority;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  requester_name: string | null;
  requester_role: string | null;
  assigned_to: number | null;
  assignee_name: string | null;
  unread: boolean;
  last_body: string;
  last_author_kind: 'user' | 'admin' | null;
  last_message_at: string | null;
  last_user_activity_at: string | null;
  first_response_at: string | null;
  attachment_count: number;
  message_count: number;
}

export interface TicketDetail {
  id: number;
  kind: Kind;
  area: string;
  area_label: string;
  title: string;
  status: Status;
  close_reason: CloseReason | null;
  priority: Priority;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  resolved_at: string | null;
  first_response_at: string | null;
  last_user_activity_at: string | null;
  last_admin_activity_at: string | null;
  assigned_to: number | null;
  assignee_name: string | null;
  can_reply: boolean;
  messages: Message[];
  context: TicketContext;
  requester: { id: number | null; name: string | null; email: string | null; role: string | null; role_label: string | null };
  requester_history: { id: number; title: string; status: Status; kind: Kind; created_at: string }[];
}

/** Shape written by frontend/src/lib/support/diagnostics.ts (+ `server` from the backend). */
export interface TicketContext {
  schema?: number;
  sent_at?: string;
  sent_at_local?: string;
  form?: { kind?: string; area?: string; area_label?: string; opened_on?: string; screenshots?: number };
  user?: {
    id: number;
    email: string;
    full_name: string;
    role: string;
    is_superuser?: boolean;
    linked_employee_id?: number | null;
    own_data_active?: boolean;
    modules?: string[];
  } | null;
  page?: {
    url?: string;
    title?: string;
    headings?: string[];
    tables?: { columns: string[]; rows: number }[];
    fields?: { label: string; value: string; disabled?: boolean }[];
    open_dialogs?: string[];
    visible_messages?: string[];
    scroll?: { main_top: number; window_y: number };
    text?: string;
    error?: string;
  };
  routes?: { at: string; path: string }[];
  network?: {
    at: string;
    method: string;
    path: string;
    status: number;
    ok: boolean;
    ms: number;
    error?: string;
    body?: string;
    shape?: string;
    bytes?: number;
  }[];
  console?: { at: string; level: string; message: string; stack?: string; source?: string }[];
  storage?: {
    local?: { key: string; length: number; preview: string }[];
    session?: { key: string; length: number; preview: string }[];
    cookie_names?: string[];
    error?: string;
  };
  environment?: Record<string, unknown>;
  app?: Record<string, unknown>;
  server?: {
    received_at_local?: string;
    ip?: string;
    user_agent?: string;
    host?: string;
    app_commit?: string | null;
    user?: { id: number; email: string; full_name: string; role: string };
  };
  _error?: string;
}

export interface Agent {
  id: number;
  full_name: string;
  email: string;
}

export type ViewCounts = Record<ViewKey, number>;

export interface Overview {
  counts: ViewCounts;
  stats: {
    open: number;
    created_30d: number;
    closed_30d: number;
    avg_first_response_s: number | null;
    avg_resolution_s: number | null;
  };
  agents: Agent[];
}

export interface ListParams {
  view: ViewKey;
  kind?: Kind | '';
  priority?: Priority | '';
  q?: string;
  sort?: SortKey;
  limit?: number;
  offset?: number;
}

function form(fields: Record<string, string>, files: File[]): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  for (const f of files) fd.append('files', f, f.name);
  return fd;
}

export const deskApi = {
  overview: () => api.get<{ success: true } & Overview>('/api/support/admin/overview'),
  list: (p: ListParams) =>
    api.get<{ success: true; tickets: TicketRow[]; total: number; counts: ViewCounts }>('/api/support/admin/tickets', {
      view: p.view,
      kind: p.kind || undefined,
      priority: p.priority || undefined,
      q: p.q || undefined,
      sort: p.sort,
      limit: p.limit ?? 100,
      offset: p.offset,
    }),
  get: (id: number) => api.get<{ success: true; ticket: TicketDetail }>(`/api/support/admin/tickets/${id}`),
  reply: (id: number, fields: { body: string; is_internal: boolean; status?: Status | ''; close_reason?: CloseReason | '' }, files: File[]) =>
    api.post<{ success: true; id: number }>(
      `/api/support/admin/tickets/${id}/messages`,
      form(
        {
          body: fields.body,
          is_internal: fields.is_internal ? 'true' : 'false',
          ...(fields.status ? { status: fields.status } : {}),
          ...(fields.close_reason ? { close_reason: fields.close_reason } : {}),
        },
        files,
      ),
    ),
  update: (id: number, patch: { status?: Status; close_reason?: CloseReason; priority?: Priority; assigned_to?: number | null }) =>
    api.patch<{ success: true }>(`/api/support/admin/tickets/${id}`, patch),
};
