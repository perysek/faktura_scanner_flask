import { useState } from 'react';
import type { ReactNode } from 'react';
import { useToast } from '@shared/components/feedback/ToastProvider';
import { Icon } from '@shared/lib/icons/Icon';
import type { TicketContext } from './api';
import { clock, dateTime } from './time';

/**
 * "Dane techniczne" — the snapshot frontend/src/lib/support/diagnostics.ts froze when
 * the user pressed Wyślij, plus what the server saw (IP, UA, commit). Failed API calls
 * and console errors open by default: they are usually the whole story ("nie działa
 * zapisz" = POST /api/appointments → 409 two minutes earlier).
 */

function Section({ title, icon, badge, tone, defaultOpen = false, children }: {
  title: string;
  icon: string;
  badge?: string | number;
  tone?: 'error';
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="tc-section" open={defaultOpen}>
      <summary>
        <Icon name={icon} size="1rem" />
        <span>{title}</span>
        {badge !== undefined && badge !== '' && <span className={`tc-badge${tone === 'error' ? ' tc-badge--error' : ''}`}>{badge}</span>}
        <Icon name="expand_more" size="1rem" className="tc-chevron" />
      </summary>
      <div className="tc-body">{children}</div>
    </details>
  );
}

function KV({ rows }: { rows: [string, ReactNode][] }) {
  const visible = rows.filter(([, v]) => v !== undefined && v !== null && v !== '');
  if (!visible.length) return <p className="tc-none">Brak danych</p>;
  return (
    <dl className="tc-kv">
      {visible.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** 1 błąd · 2–4 błędy · 5+ błędów (12–14 → błędów). */
function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (n === 1) return `${n} ${one}`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} ${few}`;
  return `${n} ${many}`;
}

function fmt(value: unknown): string {
  if (value === true) return 'tak';
  if (value === false) return 'nie';
  if (value && typeof value === 'object') return JSON.stringify(value);
  return String(value ?? '');
}

/** "Chrome 129 · Windows" out of a user-agent string — good enough for a glance. */
function browserOf(ua?: string): string {
  if (!ua) return '';
  const browser = /Edg\/(\d+)/.exec(ua)
    ? `Edge ${/Edg\/(\d+)/.exec(ua)![1]}`
    : /OPR\/(\d+)/.exec(ua)
      ? `Opera ${/OPR\/(\d+)/.exec(ua)![1]}`
      : /Chrome\/(\d+)/.exec(ua)
        ? `Chrome ${/Chrome\/(\d+)/.exec(ua)![1]}`
        : /Firefox\/(\d+)/.exec(ua)
          ? `Firefox ${/Firefox\/(\d+)/.exec(ua)![1]}`
          : /Version\/(\d+).*Safari/.exec(ua)
            ? `Safari ${/Version\/(\d+)/.exec(ua)![1]}`
            : 'Przeglądarka';
  const os = /iPhone|iPad/.test(ua)
    ? 'iOS'
    : /Android/.test(ua)
      ? 'Android'
      : /Windows/.test(ua)
        ? 'Windows'
        : /Mac OS X/.test(ua)
          ? 'macOS'
          : /Linux/.test(ua)
            ? 'Linux'
            : '';
  return [browser, os].filter(Boolean).join(' · ');
}

export function TechContext({ ctx }: { ctx: TicketContext }) {
  const toast = useToast();
  const [showText, setShowText] = useState(false);
  const env = (ctx.environment ?? {}) as Record<string, unknown>;
  const app = (ctx.app ?? {}) as Record<string, unknown>;
  const network = ctx.network ?? [];
  const failed = network.filter((n) => !n.ok);
  const consoleRows = ctx.console ?? [];
  const page = ctx.page ?? {};
  const viewport = env.viewport as { w: number; h: number } | undefined;

  if (ctx._error) return <p className="tc-none">Kontekst nieczytelny: {ctx._error}</p>;

  async function copy() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(ctx, null, 2));
      toast.success('Skopiowano JSON do schowka');
    } catch {
      toast.error('Nie udało się skopiować');
    }
  }

  function download() {
    const blob = new Blob([JSON.stringify(ctx, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `zgloszenie-kontekst-${ctx.sent_at?.slice(0, 19).replace(/[:T]/g, '-') ?? 'x'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="tc">
      <section className="tk-card tc-summary">
        <KV
          rows={[
            ['Wysłano', ctx.sent_at ? `${dateTime(ctx.sent_at)}` : undefined],
            ['Strona', page.url],
            ['Tytuł strony', page.title],
            ['Urządzenie', [browserOf(env.user_agent as string), viewport && `${viewport.w}×${viewport.h}`, env.mobile ? 'telefon' : undefined].filter(Boolean).join(' · ')],
            ['Błędy API', failed.length ? `${failed.length} z ${network.length}` : network.length ? `0 z ${network.length}` : undefined],
            ['Błędy konsoli', consoleRows.length || undefined],
            ['Wersja (commit)', ctx.server?.app_commit ?? undefined],
          ]}
        />
        <div className="tc-actions">
          <button type="button" className="refined-btn-secondary refined-btn-sm" onClick={copy}>
            Kopiuj JSON
          </button>
          <button type="button" className="refined-btn-secondary refined-btn-sm" onClick={download}>
            Pobierz JSON
          </button>
        </div>
      </section>

      <Section title="Wywołania API i odpowiedzi serwera" icon="lan" badge={failed.length ? plural(failed.length, 'błąd', 'błędy', 'błędów') : network.length} tone={failed.length ? 'error' : undefined} defaultOpen={failed.length > 0}>
        {network.length === 0 ? (
          <p className="tc-none">Brak wywołań w tej sesji</p>
        ) : (
          <ol className="tc-net">
            {[...network].reverse().map((n, i) => (
              <li key={`${n.at}-${i}`} className={n.ok ? '' : 'is-err'}>
                <span className="tc-net-line">
                  <span className="tc-time">{clock(n.at)}</span>
                  <span className={`tc-method tc-method--${n.method}`}>{n.method}</span>
                  <span className={`tc-code${n.ok ? '' : ' tc-code--err'}`}>{n.status || 'ERR'}</span>
                  <span className="tc-path" title={n.path}>
                    {n.path}
                  </span>
                  <span className="tc-ms">{n.ms} ms</span>
                </span>
                {n.error && <span className="tc-net-detail tc-err-text">{n.error}</span>}
                {n.shape && <span className="tc-net-detail">{n.shape}</span>}
                {n.body && !n.error?.includes(n.body) && <pre className="tc-pre">{n.body}</pre>}
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="Konsola i błędy JS" icon="terminal" badge={consoleRows.length || ''} tone={consoleRows.length ? 'error' : undefined} defaultOpen={consoleRows.length > 0}>
        {consoleRows.length === 0 ? (
          <p className="tc-none">Bez błędów</p>
        ) : (
          <ol className="tc-console">
            {[...consoleRows].reverse().map((c, i) => (
              <li key={`${c.at}-${i}`} className={`tc-console--${c.level}`}>
                <span className="tc-net-line">
                  <span className="tc-time">{clock(c.at)}</span>
                  <span className="tc-level">{c.level}</span>
                  <span className="tc-msg">{c.message}</span>
                </span>
                {c.source && <span className="tc-net-detail">{c.source}</span>}
                {c.stack && <pre className="tc-pre">{c.stack}</pre>}
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="Widok strony" icon="web" badge={page.fields?.length ? plural(page.fields.length, 'pole', 'pola', 'pól') : ''}>
        <KV
          rows={[
            ['Adres', page.url],
            ['Nagłówki', page.headings?.join(' › ')],
            ['Otwarte okna', page.open_dialogs?.join(', ')],
            ['Komunikaty na ekranie', page.visible_messages?.join(' | ')],
            ['Przewinięcie', page.scroll ? `${page.scroll.main_top}px` : undefined],
            ['Tabele', page.tables?.map((t) => `${t.rows} wierszy [${t.columns.join(', ')}]`).join('; ')],
          ]}
        />
        {page.fields && page.fields.length > 0 && (
          <table className="refined-table tc-table">
            <thead>
              <tr>
                <th>Pole</th>
                <th>Wartość</th>
              </tr>
            </thead>
            <tbody>
              {page.fields.map((f, i) => (
                <tr key={`${f.label}-${i}`}>
                  <td>{f.label}</td>
                  <td>
                    {f.value || <span className="tc-none">(puste)</span>}
                    {f.disabled && <span className="tc-none"> · wyłączone</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {page.text && (
          <>
            <button type="button" className="refined-btn-ghost refined-btn-sm" onClick={() => setShowText((v) => !v)}>
              {showText ? 'Ukryj tekst strony' : 'Pokaż tekst widoczny na stronie'}
            </button>
            {showText && <pre className="tc-pre tc-pre--tall">{page.text}</pre>}
          </>
        )}
        <p className="tc-note">Numery telefonów i adresy e-mail są maskowane po stronie przeglądarki.</p>
      </Section>

      <Section title="Historia nawigacji" icon="history" badge={ctx.routes?.length || ''}>
        {ctx.routes?.length ? (
          <ol className="tc-routes">
            {[...ctx.routes].reverse().map((r, i) => (
              <li key={`${r.at}-${i}`}>
                <span className="tc-time">{clock(r.at)}</span> <code>{r.path}</code>
              </li>
            ))}
          </ol>
        ) : (
          <p className="tc-none">Brak danych</p>
        )}
      </Section>

      <Section title="Użytkownik i uprawnienia" icon="person">
        <KV
          rows={[
            ['Konto', ctx.user ? `${ctx.user.full_name} <${ctx.user.email}> (#${ctx.user.id})` : undefined],
            ['Rola', ctx.user?.role],
            ['Superuser', ctx.user ? fmt(ctx.user.is_superuser) : undefined],
            ['Powiązany pracownik', ctx.user?.linked_employee_id ?? undefined],
            ['Dane własne aktywne', ctx.user ? fmt(ctx.user.own_data_active) : undefined],
            ['Moduły', ctx.user?.modules?.join(', ')],
            ['Formularz', ctx.form ? `${ctx.form.kind} · ${ctx.form.area_label} · otwarty na ${ctx.form.opened_on} · zrzutów: ${ctx.form.screenshots}` : undefined],
          ]}
        />
      </Section>

      <Section title="Pamięć aplikacji" icon="storage" badge={(ctx.storage?.local?.length ?? 0) + (ctx.storage?.session?.length ?? 0) || ''}>
        {(['local', 'session'] as const).map((kind) => {
          const rows = ctx.storage?.[kind] ?? [];
          return (
            <div key={kind}>
              <h4 className="tk-card-sub">{kind === 'local' ? 'localStorage' : 'sessionStorage'}</h4>
              {rows.length === 0 ? (
                <p className="tc-none">pusto</p>
              ) : (
                <table className="refined-table tc-table">
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.key}>
                        <td>
                          <code>{r.key}</code>
                        </td>
                        <td className="tc-preview">{r.preview}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          );
        })}
        {ctx.storage?.cookie_names?.length ? <p className="tc-note">Ciasteczka (nazwy): {ctx.storage.cookie_names.join(', ')}</p> : null}
      </Section>

      <Section title="Urządzenie i przeglądarka" icon="devices">
        <KV rows={Object.entries(env).map(([k, v]) => [k, fmt(v)] as [string, ReactNode])} />
      </Section>

      <Section title="Aplikacja i serwer" icon="info_outline">
        <KV
          rows={[
            ...Object.entries(app).map(([k, v]) => [k, fmt(v)] as [string, ReactNode]),
            ['server: odebrano', ctx.server?.received_at_local],
            ['server: IP', ctx.server?.ip],
            ['server: host', ctx.server?.host],
            ['server: commit', ctx.server?.app_commit ?? undefined],
            ['server: user-agent', ctx.server?.user_agent],
          ]}
        />
      </Section>
    </div>
  );
}
