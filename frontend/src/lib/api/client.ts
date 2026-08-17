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

/**
 * CSRF token cache (root-cause fix, 2026-08-17). Flask-WTF's CSRFProtect
 * (app.py) checks every POST/PUT/PATCH/DELETE, and `auth_bp` was never
 * exempted — the SPA had no way to obtain a token, so EVERY mutating
 * request (login included) was rejected with a 400 before it ever reached
 * the route handler. Fetched lazily and cached in memory; a session lives
 * for the lifetime of one tab load, so one token per page load is enough.
 * `null` means "not fetched yet", not "no token" — GET requests never need
 * one and never trigger this.
 */
let csrfTokenPromise: Promise<string> | null = null;

async function getCsrfToken(): Promise<string> {
  if (!csrfTokenPromise) {
    csrfTokenPromise = fetch('/auth/csrf-token', { credentials: 'include' })
      .then((r) => r.json())
      .then((d) => d.csrf_token as string)
      .catch((err) => {
        csrfTokenPromise = null; // allow retry on the next mutating call
        throw err;
      });
  }
  return csrfTokenPromise;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {
    'X-Requested-With': 'XMLHttpRequest',
  };
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
  }
  if (method !== 'GET') {
    headers['X-CSRFToken'] = await getCsrfToken();
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

  // 204 No Content / empty body — treat as a bare success. Any non-JSON
  // body (e.g. a CSRF/500 error under a route Flask renders as HTML —
  // routes/auth/routes.py only serves JSON errors for wants_json=True
  // requests, but app.py's error handlers key off request.path.startswith
  // ('/api/'), not the header) must NOT hit JSON.parse: an HTML page threw
  // an uncaught SyntaxError here, which the caller couldn't tell apart from
  // a real network failure — same misleading message either way. Root-cause
  // fix, 2026-08-17.
  const contentType = response.headers.get('content-type') ?? '';
  const text = await response.text();
  const data = text && contentType.includes('application/json') ? JSON.parse(text) : {};

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
  post: <T>(path: string, body?: unknown): Promise<T> => request<T>('POST', path, body ?? {}),
  put: <T>(path: string, body?: unknown): Promise<T> => request<T>('PUT', path, body ?? {}),
  del: <T>(path: string): Promise<T> => request<T>('DELETE', path),
};
