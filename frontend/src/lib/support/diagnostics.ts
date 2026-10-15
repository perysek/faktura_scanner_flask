/**
 * Technical snapshot attached to every support ticket (plan 261013 §6) — invisible to
 * the sender, shown to the administrator in the issues app's "Szczegóły techniczne".
 *
 * Ring buffers fill from app start: API calls (recorded by lib/api/client.ts — method,
 * path, status, time, and the server's answer: its error text for failures, its shape
 * for successes), console errors/warnings + uncaught errors, and route history
 * (AppShell). `collectContext()` adds the moment-of-sending state: page view (title,
 * headings, visible text, tables, form fields), storage, device and app build.
 *
 * Privacy: phone numbers and e-mail addresses are masked in every free-text field we
 * scrape (page text, form values, storage previews); successful API response BODIES are
 * never kept — only their shape (keys + list lengths); storage keys that look like
 * secrets are redacted. The session cookie is httpOnly and unreachable from here anyway.
 */

const MAX_NET = 40;
const MAX_CONSOLE = 30;
const MAX_ROUTES = 15;
const MAX_TEXT = 8000;

export interface NetEntry {
  at: string;
  method: string;
  path: string;
  status: number;
  ok: boolean;
  ms: number;
  /** Server's `error` field (failures) or the network-failure note. */
  error?: string;
  /** Failures: the first 600 chars of the raw answer. */
  body?: string;
  /** Successes: top-level keys, arrays as `name[length]`. */
  shape?: string;
  bytes?: number;
}

export interface ConsoleEntry {
  at: string;
  level: 'error' | 'warn' | 'uncaught' | 'rejection';
  message: string;
  stack?: string;
  source?: string;
}

export interface RouteEntry {
  at: string;
  path: string;
}

const net: NetEntry[] = [];
const consoleLog: ConsoleEntry[] = [];
const routes: RouteEntry[] = [];
const startedAt = new Date();

function push<T>(buffer: T[], item: T, max: number) {
  buffer.push(item);
  if (buffer.length > max) buffer.splice(0, buffer.length - max);
}

const now = () => new Date().toISOString();

const PHONE_RE = /(?<![\d-])(?:\+?48[\s-]?)?\d{3}[\s-]?\d{3}[\s-]?\d{3}(?![\d-])/g;
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

/** Masks phone numbers and e-mail addresses (RODO): the ticket must not carry contact data. */
export function mask(text: string): string {
  return text.replace(EMAIL_RE, '[e-mail]').replace(PHONE_RE, '[telefon]');
}

function clip(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}… [+${text.length - max} znaków]` : text;
}

/** `{success, records: [...], count}` → "success, records[42], count". */
function shapeOf(data: unknown): string | undefined {
  if (Array.isArray(data)) return `[${data.length}]`;
  if (!data || typeof data !== 'object') return undefined;
  return Object.entries(data as Record<string, unknown>)
    .slice(0, 20)
    .map(([key, value]) => (Array.isArray(value) ? `${key}[${value.length}]` : key))
    .join(', ');
}

// Background polling would flood the log with noise and push real calls out.
const QUIET_PATHS = ['/api/support/unread-count', '/api/appointments/status-events'];

export function recordApiCall(entry: {
  method: string;
  path: string;
  status: number;
  ms: number;
  data?: unknown;
  rawText?: string;
  error?: string;
}) {
  if (QUIET_PATHS.some((p) => entry.path.startsWith(p))) return;
  const ok = entry.status >= 200 && entry.status < 400;
  push(
    net,
    {
      at: now(),
      method: entry.method,
      path: clip(entry.path, 300),
      status: entry.status,
      ok,
      ms: Math.round(entry.ms),
      error: entry.error,
      body: !ok && entry.rawText ? clip(mask(entry.rawText), 600) : undefined,
      shape: ok ? shapeOf(entry.data) : undefined,
      bytes: entry.rawText?.length,
    },
    MAX_NET,
  );
}

export function recordRoute(path: string) {
  if (routes.length && routes[routes.length - 1].path === path) return;
  push(routes, { at: now(), path }, MAX_ROUTES);
}

function stringifyArg(arg: unknown): string {
  if (arg instanceof Error) return `${arg.name}: ${arg.message}`;
  if (typeof arg === 'string') return arg;
  try {
    return JSON.stringify(arg);
  } catch {
    return String(arg);
  }
}

let installed = false;

/** Once, at app start (main.tsx): console + global error capture. */
export function installDiagnostics() {
  if (installed || typeof window === 'undefined') return;
  installed = true;

  for (const level of ['error', 'warn'] as const) {
    const original = console[level].bind(console);
    console[level] = (...args: unknown[]) => {
      try {
        const err = args.find((a): a is Error => a instanceof Error);
        push(
          consoleLog,
          { at: now(), level, message: clip(mask(args.map(stringifyArg).join(' ')), 800), stack: err?.stack ? clip(err.stack, 1500) : undefined },
          MAX_CONSOLE,
        );
      } catch {
        /* never let diagnostics break logging */
      }
      original(...args);
    };
  }

  window.addEventListener('error', (event) => {
    push(
      consoleLog,
      {
        at: now(),
        level: 'uncaught',
        message: clip(mask(event.message || String(event.error)), 800),
        stack: event.error?.stack ? clip(String(event.error.stack), 1500) : undefined,
        source: event.filename ? `${event.filename}:${event.lineno}:${event.colno}` : undefined,
      },
      MAX_CONSOLE,
    );
  });
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    push(
      consoleLog,
      {
        at: now(),
        level: 'rejection',
        message: clip(mask(stringifyArg(reason)), 800),
        stack: reason instanceof Error && reason.stack ? clip(reason.stack, 1500) : undefined,
      },
      MAX_CONSOLE,
    );
  });
}

// ── moment-of-sending snapshot ─────────────────────────────────────────────

const SECRET_KEY_RE = /token|secret|password|passwd|csrf|auth|session|pin/i;

function storageDump(storage: Storage | undefined) {
  const out: { key: string; length: number; preview: string }[] = [];
  if (!storage) return out;
  try {
    for (let i = 0; i < storage.length && out.length < 60; i += 1) {
      const key = storage.key(i);
      if (!key) continue;
      const value = storage.getItem(key) ?? '';
      out.push({ key, length: value.length, preview: SECRET_KEY_RE.test(key) ? '[ukryte]' : clip(mask(value), 300) });
    }
  } catch {
    /* storage blocked (private mode) */
  }
  return out;
}

function labelFor(el: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement): string {
  const byFor = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent : null;
  const wrapping = el.closest('label')?.textContent;
  return (byFor || wrapping || el.getAttribute('aria-label') || el.name || el.getAttribute('placeholder') || el.id || el.tagName.toLowerCase())
    .trim()
    .slice(0, 80);
}

function pageSnapshot() {
  const main = document.getElementById('main-content');
  const root: HTMLElement = main ?? document.body;
  const headings = Array.from(root.querySelectorAll('h1, h2, h3'))
    .map((h) => (h.textContent ?? '').trim())
    .filter(Boolean)
    .slice(0, 20);
  const tables = Array.from(root.querySelectorAll('table'))
    .slice(0, 5)
    .map((table) => ({
      columns: Array.from(table.querySelectorAll('thead th'))
        .map((th) => (th.textContent ?? '').trim())
        .filter(Boolean)
        .slice(0, 20),
      rows: table.querySelectorAll('tbody tr').length,
    }));
  const fields = Array.from(root.querySelectorAll<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('input, select, textarea'))
    .filter((el) => !(el instanceof HTMLInputElement && ['password', 'hidden', 'file'].includes(el.type)))
    .slice(0, 40)
    .map((el) => {
      let value: string;
      if (el instanceof HTMLInputElement && (el.type === 'checkbox' || el.type === 'radio')) value = el.checked ? 'zaznaczone' : 'nie';
      else if (el instanceof HTMLSelectElement) value = el.selectedOptions[0]?.textContent?.trim() ?? el.value;
      else value = el.value;
      return { label: labelFor(el), value: clip(mask(value), 200), disabled: el.disabled || undefined };
    });
  const dialogs = Array.from(document.querySelectorAll('[role="dialog"], [role="alertdialog"]'))
    .filter((d) => !d.closest('[data-html2canvas-ignore]'))
    .map((d) => (d.getAttribute('aria-label') || d.querySelector('h2, h3')?.textContent || '').trim())
    .filter(Boolean);
  const alerts = Array.from(document.querySelectorAll('[role="alert"], .form-error-text, .flash-error, .toast'))
    .filter((d) => !d.closest('[data-html2canvas-ignore]'))
    .map((d) => clip(mask((d.textContent ?? '').trim()), 200))
    .filter(Boolean)
    .slice(0, 10);
  const text = clip(mask((root.innerText ?? '').replace(/\n{3,}/g, '\n\n').trim()), MAX_TEXT);
  return {
    url: `${location.pathname}${location.search}${location.hash}`,
    title: document.title,
    headings,
    tables,
    fields,
    open_dialogs: dialogs,
    visible_messages: alerts,
    scroll: { main_top: Math.round(main?.scrollTop ?? 0), window_y: Math.round(window.scrollY) },
    text,
  };
}

function environment() {
  const nav = navigator as Navigator & {
    connection?: { effectiveType?: string; downlink?: number; saveData?: boolean };
    deviceMemory?: number;
    userAgentData?: { platform?: string; mobile?: boolean; brands?: { brand: string; version: string }[] };
  };
  return {
    user_agent: nav.userAgent,
    platform: nav.userAgentData?.platform ?? nav.platform,
    mobile: nav.userAgentData?.mobile,
    brands: nav.userAgentData?.brands?.map((b) => `${b.brand} ${b.version}`).join(', '),
    language: nav.language,
    languages: nav.languages?.slice(0, 5),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    tz_offset_min: -new Date().getTimezoneOffset(),
    viewport: { w: window.innerWidth, h: window.innerHeight },
    screen: { w: window.screen.width, h: window.screen.height },
    dpr: window.devicePixelRatio,
    touch_points: nav.maxTouchPoints,
    standalone_pwa: window.matchMedia('(display-mode: standalone)').matches,
    theme: document.documentElement.getAttribute('data-theme') || 'default',
    reduced_motion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    online: nav.onLine,
    connection: nav.connection
      ? { type: nav.connection.effectiveType, downlink_mbps: nav.connection.downlink, save_data: nav.connection.saveData }
      : undefined,
    device_memory_gb: nav.deviceMemory,
    cpu_cores: nav.hardwareConcurrency,
    cookies_enabled: nav.cookieEnabled,
  };
}

function appInfo() {
  const scripts = Array.from(document.querySelectorAll<HTMLScriptElement>('script[src]'))
    .map((s) => s.getAttribute('src') ?? '')
    .filter((src) => src.includes('/assets/'));
  const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
  const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory;
  return {
    build_assets: scripts,
    origin: location.origin,
    session_started_at: startedAt.toISOString(),
    page_age_s: Math.round((Date.now() - startedAt.getTime()) / 1000),
    load_ms: navEntry ? Math.round(navEntry.loadEventEnd - navEntry.startTime) : undefined,
    js_heap_mb: memory ? Math.round(memory.usedJSHeapSize / 1048576) : undefined,
  };
}

export interface ContextUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  permissions: Record<string, { has_access: boolean; read_only: boolean; own_data: boolean }>;
  is_superuser: boolean;
  linked_employee_id: number | null;
  own_data_active: boolean;
}

/** Everything above, frozen at the moment of sending. Never throws. */
export function collectContext(user: ContextUser | null, extra: Record<string, unknown> = {}) {
  const safe = <T>(fn: () => T): T | { error: string } => {
    try {
      return fn();
    } catch (err) {
      return { error: String(err) };
    }
  };
  const sentAt = new Date();
  return {
    schema: 1,
    sent_at: sentAt.toISOString(),
    sent_at_local: sentAt.toLocaleString('pl-PL'),
    ...extra,
    user: user && {
      id: user.id,
      email: user.email,
      full_name: user.full_name,
      role: user.role,
      is_superuser: user.is_superuser,
      linked_employee_id: user.linked_employee_id,
      own_data_active: user.own_data_active,
      modules: Object.entries(user.permissions)
        .filter(([, f]) => f.has_access)
        .map(([name, f]) => `${name}${f.read_only ? ' (tylko odczyt)' : ''}${f.own_data ? ' (własne dane)' : ''}`),
    },
    page: safe(pageSnapshot),
    routes: [...routes],
    network: [...net],
    console: [...consoleLog],
    storage: safe(() => ({
      local: storageDump(window.localStorage),
      session: storageDump(window.sessionStorage),
      cookie_names: document.cookie
        .split(';')
        .map((c) => c.split('=')[0].trim())
        .filter(Boolean),
    })),
    environment: safe(environment),
    app: safe(appInfo),
  };
}
