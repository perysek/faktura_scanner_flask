import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '@shared/contexts/AuthContext';
import { ApiError } from '@shared/lib/api/client';
import { Icon } from '@shared/lib/icons/Icon';
import { deskApi } from './api';
import type { Kind, Overview, Priority, SortKey, TicketRow, ViewCounts, ViewKey } from './api';
import { KIND_LABEL, PRIORITY_LABEL, ROLE_LABEL, SORT_LABEL, STATUS_LABEL, VIEWS } from './labels';
import { ageShort, duration, hoursSince } from './time';
import { TicketPane } from './TicketPane';

/**
 * The desk — three panes, the layout every helpdesk converged on (Help Scout,
 * Front, Zendesk Agent Workspace, Linear Triage): views on the left, the queue in
 * the middle, the open conversation on the right. View, filters, search and sort
 * live in the URL (?view=…&q=…), the open ticket in the path (/t/:id), so every
 * state is linkable and survives a refresh.
 */

const LIST_POLL_MS = 30_000;

export function Desk() {
  const auth = useAuth();
  const navigate = useNavigate();
  const { ticketId } = useParams();
  const selectedId = ticketId ? Number(ticketId) : null;
  const [params, setParams] = useSearchParams();
  const view = (params.get('view') as ViewKey) || 'open';
  const kind = (params.get('kind') as Kind | null) ?? '';
  const priority = (params.get('priority') as Priority | null) ?? '';
  const sort = (params.get('sort') as SortKey) || 'updated';
  const q = params.get('q') ?? '';

  const [rows, setRows] = useState<TicketRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<ViewCounts | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState(q);
  const [railOpen, setRailOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const setParam = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(params);
      if (value) next.set(key, value);
      else next.delete(key);
      if (key === 'view' && value === 'open') next.delete('view');
      setParams(next, { replace: key === 'q' });
    },
    [params, setParams],
  );

  const loadList = useCallback(async () => {
    try {
      const data = await deskApi.list({ view, kind, priority, q, sort });
      setRows(data.tickets);
      setTotal(data.total);
      setCounts(data.counts);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Nie udało się wczytać zgłoszeń');
    }
  }, [view, kind, priority, q, sort]);

  const loadOverview = useCallback(async () => {
    try {
      setOverview(await deskApi.overview());
    } catch {
      /* stats are decoration — the list shows real errors */
    }
  }, []);

  useEffect(() => {
    setRows(null);
    loadList();
  }, [loadList]);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadList();
        loadOverview();
      }
    }, LIST_POLL_MS);
    return () => window.clearInterval(timer);
  }, [loadList, loadOverview]);

  // Debounced search → URL.
  useEffect(() => {
    if (search === q) return undefined;
    const t = window.setTimeout(() => setParam('q', search.trim()), 300);
    return () => window.clearTimeout(t);
  }, [search, q, setParam]);

  // Unread count in the tab title — the desk usually sits in a background tab.
  useEffect(() => {
    const unread = counts?.unread ?? 0;
    document.title = unread ? `(${unread}) Zgłoszenia · MyWay` : 'Zgłoszenia · MyWay';
  }, [counts]);

  const open = useCallback(
    (id: number) => navigate({ pathname: `/t/${id}`, search: params.toString() ? `?${params}` : '' }),
    [navigate, params],
  );

  // Keyboard: "/" search, j/k next/previous ticket, Esc back to the queue (phones).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (target.closest('input, textarea, select, [contenteditable="true"]')) return;
      if (e.key === '/') {
        e.preventDefault();
        searchRef.current?.focus();
      } else if ((e.key === 'j' || e.key === 'k') && rows?.length) {
        const index = rows.findIndex((r) => r.id === selectedId);
        const nextIndex = e.key === 'j' ? Math.min(rows.length - 1, index + 1) : Math.max(0, index - 1);
        open(rows[nextIndex < 0 ? 0 : nextIndex].id);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [rows, selectedId, open]);

  useEffect(() => {
    listRef.current?.querySelector('.desk-row--active')?.scrollIntoView({ block: 'nearest' });
  }, [selectedId, rows]);

  const onTicketChanged = useCallback(() => {
    loadList();
    loadOverview();
  }, [loadList, loadOverview]);

  const stats = overview?.stats;

  return (
    <div className={`desk${selectedId ? ' desk--has-ticket' : ''}${railOpen ? ' desk--rail-open' : ''}`}>
      {/* ── rail ─────────────────────────────────────────────── */}
      <aside className="desk-rail" aria-label="Widoki zgłoszeń">
        <div className="desk-brand">
          <img src="/logo-inline.webp" alt="MyWay" />
          <span>Zgłoszenia</span>
        </div>
        <nav className="desk-views">
          {(['queue', 'archive'] as const).map((group) => (
            <div key={group} className="desk-view-group">
              <p className="desk-rail-heading">{group === 'queue' ? 'Kolejka' : 'Archiwum'}</p>
              {VIEWS.filter((v) => v.group === group).map((v) => (
                <button
                  key={v.key}
                  type="button"
                  className={`desk-view${view === v.key ? ' desk-view--active' : ''}`}
                  aria-current={view === v.key ? 'page' : undefined}
                  onClick={() => {
                    setParam('view', v.key);
                    setRailOpen(false);
                  }}
                >
                  <Icon name={v.icon} size="1.125rem" />
                  <span className="desk-view-label">{v.label}</span>
                  {counts && counts[v.key] > 0 && (
                    <span className={`desk-count${v.key === 'unread' || v.key === 'new' ? ' desk-count--hot' : ''}`}>{counts[v.key]}</span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </nav>

        {stats && (
          <dl className="desk-stats" aria-label="Ostatnie 30 dni">
            <p className="desk-rail-heading">Ostatnie 30 dni</p>
            <div>
              <dt>Nowe</dt>
              <dd>{stats.created_30d}</dd>
            </div>
            <div>
              <dt>Zamknięte</dt>
              <dd>{stats.closed_30d}</dd>
            </div>
            <div>
              <dt>1. odpowiedź (śr.)</dt>
              <dd>{duration(stats.avg_first_response_s)}</dd>
            </div>
            <div>
              <dt>Rozwiązanie (śr.)</dt>
              <dd>{duration(stats.avg_resolution_s)}</dd>
            </div>
          </dl>
        )}

        <div className="desk-user">
          <span className="sidebar-avatar desk-avatar" aria-hidden="true">
            {(auth.user?.full_name || auth.user?.email || '?').slice(0, 1).toUpperCase()}
          </span>
          <span className="desk-user-text">
            <span className="desk-user-name">{auth.user?.full_name || auth.user?.email}</span>
            <span className="desk-user-role">{ROLE_LABEL[auth.user?.role ?? ''] ?? auth.user?.role}</span>
          </span>
          <button type="button" className="desk-icon-btn" onClick={() => auth.logout()} aria-label="Wyloguj" title="Wyloguj">
            <Icon name="logout" size="1.125rem" />
          </button>
        </div>
      </aside>
      <button type="button" className="desk-rail-backdrop" aria-label="Zamknij menu" onClick={() => setRailOpen(false)} />

      {/* ── queue ────────────────────────────────────────────── */}
      <section className="desk-queue" aria-label="Lista zgłoszeń">
        <header className="desk-queue-head">
          <div className="desk-queue-title">
            <button type="button" className="desk-icon-btn desk-menu-btn" aria-label="Widoki" onClick={() => setRailOpen(true)}>
              <Icon name="filter_list" size="1.25rem" />
            </button>
            <h1>{VIEWS.find((v) => v.key === view)?.label ?? 'Zgłoszenia'}</h1>
            <span className="desk-queue-total">{rows ? total : ''}</span>
            <select className="form-select desk-sort" value={sort} onChange={(e) => setParam('sort', e.target.value === 'updated' ? '' : e.target.value)} aria-label="Sortowanie">
              {(Object.keys(SORT_LABEL) as SortKey[]).map((s) => (
                <option key={s} value={s}>
                  {SORT_LABEL[s]}
                </option>
              ))}
            </select>
            <button type="button" className="desk-icon-btn" onClick={onTicketChanged} aria-label="Odśwież" title="Odśwież">
              <Icon name="refresh" size="1.125rem" />
            </button>
          </div>
          <div className="desk-search">
            <Icon name="search" size="1rem" />
            <input
              ref={searchRef}
              type="search"
              className="desk-search-input"
              placeholder="Szukaj: treść, tytuł, osoba, #numer   ( / )"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Szukaj zgłoszeń"
            />
          </div>
          <div className="desk-filters">
            <select className="form-select desk-filter" value={kind} onChange={(e) => setParam('kind', e.target.value)} aria-label="Rodzaj">
              <option value="">Każdy rodzaj</option>
              {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABEL[k]}
                </option>
              ))}
            </select>
            <select className="form-select desk-filter" value={priority} onChange={(e) => setParam('priority', e.target.value)} aria-label="Priorytet">
              <option value="">Każdy priorytet</option>
              {(Object.keys(PRIORITY_LABEL) as Priority[]).map((p) => (
                <option key={p} value={p}>
                  {PRIORITY_LABEL[p]}
                </option>
              ))}
            </select>
          </div>
        </header>

        {error && <p className="desk-empty desk-empty--error">{error}</p>}
        {!error && !rows && (
          <ul className="desk-list" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <li key={i} className="desk-row-skeleton skeleton" />
            ))}
          </ul>
        )}
        {!error && rows && rows.length === 0 && (
          <div className="desk-empty">
            <Icon name="inbox" size="2.5rem" />
            <p>{q ? 'Nic nie pasuje do wyszukiwania.' : 'Pusto — wszystko załatwione. ☕'}</p>
          </div>
        )}
        {rows && rows.length > 0 && (
          <ul className="desk-list scroll-thin" ref={listRef}>
            {rows.map((t) => {
              const waitingOnUs = ['new', 'seen', 'in_progress'].includes(t.status);
              const age = hoursSince(t.last_user_activity_at);
              const ageTone = waitingOnUs ? (age > 72 ? ' desk-age--red' : age > 24 ? ' desk-age--amber' : '') : '';
              return (
                <li key={t.id}>
                  <button
                    type="button"
                    className={`desk-row${t.id === selectedId ? ' desk-row--active' : ''}${t.unread ? ' desk-row--unread' : ''}`}
                    onClick={() => open(t.id)}
                  >
                    <span className="desk-row-top">
                      {t.unread && <span className="desk-unread-dot" aria-label="Nieprzeczytane" />}
                      <span className="desk-row-who">{t.requester_name ?? 'Nieznany użytkownik'}</span>
                      <span className={`desk-age${ageTone}`} title="Od ostatniej wiadomości użytkownika">
                        {ageShort(t.last_message_at ?? t.updated_at)}
                      </span>
                    </span>
                    <span className="desk-row-title">
                      <span className="desk-id">#{t.id}</span> {t.title}
                    </span>
                    {t.last_body && (
                      <span className="desk-row-preview">
                        {t.last_author_kind === 'admin' ? 'Ty: ' : ''}
                        {t.last_body}
                      </span>
                    )}
                    <span className="desk-row-chips">
                      <span className={`desk-status desk-status--${t.status}`}>{STATUS_LABEL[t.status]}</span>
                      <span className={`desk-kind desk-kind--${t.kind}`}>
                        <Icon name={t.kind === 'idea' ? 'lightbulb' : 'bug_report'} size="0.875rem" />
                        {t.area_label}
                      </span>
                      {(t.priority === 'high' || t.priority === 'urgent') && (
                        <span className={`desk-prio desk-prio--${t.priority}`}>
                          <Icon name="flag" size="0.875rem" />
                          {PRIORITY_LABEL[t.priority]}
                        </span>
                      )}
                      {t.attachment_count > 0 && (
                        <span className="desk-meta" title="Zdjęcia">
                          <Icon name="attach_file" size="0.875rem" />
                          {t.attachment_count}
                        </span>
                      )}
                      {t.assignee_name && (
                        <span className="desk-meta" title="Przypisane">
                          <Icon name="person" size="0.875rem" />
                          {t.assignee_name.split(' ')[0]}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* ── ticket ───────────────────────────────────────────── */}
      <section className="desk-ticket" aria-label="Zgłoszenie">
        {selectedId ? (
          <TicketPane
            key={selectedId}
            id={selectedId}
            agents={overview?.agents ?? []}
            onChanged={onTicketChanged}
            onBack={() => navigate({ pathname: '/', search: params.toString() ? `?${params}` : '' })}
            onOpenTicket={open}
          />
        ) : (
          <div className="desk-empty desk-empty--pane">
            <Icon name="forum" size="3rem" />
            <p>Wybierz zgłoszenie z listy.</p>
            <p className="desk-hint">
              Skróty: <kbd>/</kbd> szukaj · <kbd>j</kbd> / <kbd>k</kbd> następne / poprzednie · <kbd>Ctrl</kbd>+<kbd>Enter</kbd> wyślij
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
