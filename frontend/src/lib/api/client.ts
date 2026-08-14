/**
 * Thin fetch wrapper — DESIGN.md §18. Not axios/react-query: `api.get/post/put/del`.
 * Always sends `credentials: 'include'` (session cookie) and the
 * `X-Requested-With` header that signals "this is an API/SPA call" to the
 * backend (DESIGN.md §15.1) — every `routes/auth/routes.py` handler branches
 * on this header to return JSON instead of a redirect. The rest of the
 * backend (`/api/*`) is already a pure-JSON blueprint and ignores the header,
 * but sending it everywhere is harmless and keeps this client uniform.
 *
 * Any new direct `fetch()` call that bypasses this wrapper will silently lose
 * both credentials and the header, and will likely break auth on that call —
 * always go through `api`.
 */

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

type JsonBody = Record<string, unknown> | unknown[];

async function request<T>(method: string, path: string, body?: JsonBody): Promise<T> {
  const headers: Record<string, string> = {
    'X-Requested-With': 'XMLHttpRequest',
  };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }

  let response: Response;
  try {
    response = await fetch(path, {
      method,
      credentials: 'include',
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    // Network failure (server unreachable, offline, …) — same fallback string
    // used verbatim across the auth screens (DESIGN.md §18).
    throw new ApiError(0, 'Nie udało się połączyć z serwerem');
  }

  // 204 No Content / empty body — treat as a bare success.
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const message = (data && (data.error as string)) || `Błąd serwera (${response.status})`;
    throw new ApiError(response.status, message);
  }

  return data as T;
}

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> => {
    let url = path;
    if (params) {
      const qs = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== '') qs.set(key, String(value));
      }
      const qsString = qs.toString();
      if (qsString) url += (path.includes('?') ? '&' : '?') + qsString;
    }
    return request<T>('GET', url);
  },
  post: <T>(path: string, body?: JsonBody): Promise<T> => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body?: JsonBody): Promise<T> => request<T>('PUT', path, body ?? {}),
  del: <T>(path: string): Promise<T> => request<T>('DELETE', path),
};
