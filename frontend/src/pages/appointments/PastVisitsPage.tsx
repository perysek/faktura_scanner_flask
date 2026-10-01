import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import './PastVisitsPage.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { SearchableSelect } from '../../components/ui/SearchableSelect';
import { Icon } from '../../lib/icons/Icon';
import type { PastPendingAppointment, PastResolutionStatus } from '../../types/appointment';
import { STATUS_LABELS } from '../../types/appointment';
import { MONTHS_PL, RESOLUTIONS, durationMinutes, fmtTime, initials, pluralVisits } from './pastVisitsShared';

const STORAGE_KEY = 'pvp-selections';

const CHOICE_LABEL: Record<PastResolutionStatus, string> = {
  completed: 'Zakończona',
  cancelled: 'Anulowana',
  no_show: 'No-show',
};
const CHOICE_ICON: Record<PastResolutionStatus, string> = {
  completed: 'check',
  cancelled: 'close',
  no_show: 'person_off',
};
const SUMMARY_LABEL: Record<PastResolutionStatus, string> = {
  completed: 'Zakończone',
  cancelled: 'Anulowane',
  no_show: 'No-show',
};

const WEEKDAY_FMT = new Intl.DateTimeFormat('pl-PL', { weekday: 'long' });

function pad(n: number): string {
  return String(n).padStart(2, '0');
}
function isoOf(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function dayHeading(dateStr: string): { rel: string | null; text: string } {
  const [y, m, d] = dateStr.split('-').map(Number);
  const today = new Date();
  const yesterday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 1);
  const rel = dateStr === isoOf(today) ? 'Dziś' : dateStr === isoOf(yesterday) ? 'Wczoraj' : null;
  return { rel, text: `${WEEKDAY_FMT.format(new Date(y, m - 1, d))}, ${d} ${MONTHS_PL[m - 1] ?? ''}`.trim() };
}
function pluralChanges(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (n === 1) return 'zmianę';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'zmiany';
  return 'zmian';
}

/** Picks survive an accidental back-swipe or refresh (15 taps are expensive to
 * redo) — sessionStorage, so they die with the tab instead of going stale. */
function readStoredSelections(): Record<number, PastResolutionStatus> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, string>;
    const out: Record<number, PastResolutionStatus> = {};
    for (const [id, status] of Object.entries(parsed)) {
      if ((RESOLUTIONS as string[]).includes(status)) out[Number(id)] = status as PastResolutionStatus;
    }
    return out;
  } catch {
    return {};
  }
}
function writeStoredSelections(selections: Record<number, PastResolutionStatus>) {
  try {
    if (Object.keys(selections).length === 0) sessionStorage.removeItem(STORAGE_KEY);
    else sessionStorage.setItem(STORAGE_KEY, JSON.stringify(selections));
  } catch {
    /* private mode / blocked storage — the page works fine without it */
  }
}

/** "Rozlicz przeszłe wizyty" — phone page. The desktop modal (PastVisitsScanner)
 * is a table-in-a-dialog; on a phone that became a sideways strip of 11rem cards
 * with ~20px targets. This is its own route instead: a vertical list grouped by
 * day, one card per visit with three 56px status buttons, and a pinned bottom
 * bar for the bulk actions + save.
 *
 * Bulk "Zakończ pozostałe" only touches visits with NO pick yet — it never
 * overwrites an explicit anulowana/no-show. Save asks for confirmation first,
 * because `PUT /appointments/<id>/past-status` is one-way (final statuses are
 * rejected afterwards) and `completed` books revenue + schedules the post-visit
 * SMS. Saves run one at a time, like the modal: each completed visit creates a
 * revenue row and an SMS job, and sequential keeps failures attributable to a
 * single card. */
export function PastVisitsPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [appointments, setAppointments] = useState<PastPendingAppointment[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [selections, setSelections] = useState<Record<number, PastResolutionStatus>>(readStoredSelections);
  const [errors, setErrors] = useState<Record<number, string>>({});
  const [employeeId, setEmployeeId] = useState('');
  const [saving, setSaving] = useState<{ done: number; total: number } | null>(null);
  const emptyHeadingRef = useRef<HTMLHeadingElement>(null);
  const hadItems = useRef(false);

  function load() {
    setLoadFailed(false);
    appointmentsApi
      .pastPending()
      .then((list) => {
        setAppointments(list);
        // A stored pick for a visit that has since been settled elsewhere is dead weight.
        const ids = new Set(list.map((a) => a.id));
        setSelections((prev) => {
          const next: Record<number, PastResolutionStatus> = {};
          for (const [id, status] of Object.entries(prev)) if (ids.has(Number(id))) next[Number(id)] = status;
          return next;
        });
      })
      .catch(() => setLoadFailed(true));
  }

  useEffect(load, []);
  useEffect(() => writeStoredSelections(selections), [selections]);

  useEffect(() => {
    if (Object.keys(errors).length === 0) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.querySelector('.pvp-card--error')?.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
  }, [errors]);

  const all = useMemo(() => appointments ?? [], [appointments]);
  const total = all.length;

  // Everything settled in this session → move focus to the "all done" heading,
  // otherwise a screen-reader user is left on a button that no longer exists.
  useEffect(() => {
    if (total > 0) hadItems.current = true;
    else if (appointments && hadItems.current) emptyHeadingRef.current?.focus();
  }, [total, appointments]);

  const employees = useMemo(() => {
    const byId = new Map<number, { name: string; count: number }>();
    for (const a of all) {
      const entry = byId.get(a.employee_id);
      if (entry) entry.count += 1;
      else byId.set(a.employee_id, { name: a.employee_name ?? 'Bez pracownika', count: 1 });
    }
    return [...byId.entries()].map(([id, v]) => ({ id, ...v })).sort((a, b) => a.name.localeCompare(b.name, 'pl'));
  }, [all]);

  // A filter pointing at an employee whose visits are all settled falls back to "everyone".
  const activeEmployee = employees.some((e) => String(e.id) === employeeId) ? employeeId : '';

  const visible = useMemo(() => all.filter((a) => !activeEmployee || String(a.employee_id) === activeEmployee), [all, activeEmployee]);

  const groups = useMemo(() => {
    const byDate = new Map<string, PastPendingAppointment[]>();
    for (const a of visible) {
      const bucket = byDate.get(a.appointment_date);
      if (bucket) bucket.push(a);
      else byDate.set(a.appointment_date, [a]);
    }
    return [...byDate.entries()]
      .sort(([a], [b]) => (a < b ? 1 : a > b ? -1 : 0))
      .map(([date, items]) => ({ date, items: items.sort((x, y) => x.start_time.localeCompare(y.start_time)) }));
  }, [visible]);

  const changedCount = Object.keys(selections).length;
  const remainingVisible = visible.filter((a) => !selections[a.id]);
  const isSaving = saving !== null;

  function choose(apt: PastPendingAppointment, status: PastResolutionStatus) {
    setSelections((prev) => {
      const next = { ...prev };
      if (next[apt.id] === status) delete next[apt.id];
      else next[apt.id] = status;
      return next;
    });
    setErrors((prev) => {
      if (!(apt.id in prev)) return prev;
      const next = { ...prev };
      delete next[apt.id];
      return next;
    });
  }

  function completeRemaining(items: PastPendingAppointment[]) {
    setSelections((prev) => {
      const next = { ...prev };
      for (const a of items) if (!next[a.id]) next[a.id] = 'completed';
      return next;
    });
  }

  function clearAll() {
    setSelections({});
    setErrors({});
  }

  async function save() {
    const entries = Object.entries(selections).map(([id, status]) => ({ id: Number(id), status }));
    if (entries.length === 0 || isSaving) return;

    const tally = RESOLUTIONS.map((s) => ({ s, n: entries.filter((e) => e.status === s).length })).filter((t) => t.n > 0);
    const hasNegative = tally.some((t) => t.s !== 'completed');
    const ok = await confirm({
      title: `Zapisać ${entries.length} ${pluralChanges(entries.length)}?`,
      message: `${tally.map((t) => `${SUMMARY_LABEL[t.s]}: ${t.n}`).join(' · ')}. Statusu końcowego nie da się potem zmienić z tego widoku.`,
      type: hasNegative ? 'warning' : 'info',
      confirmText: 'Zapisz',
      cancelText: 'Wróć',
    });
    if (!ok) return;

    setSaving({ done: 0, total: entries.length });
    const failed: Record<number, string> = {};
    const settled: number[] = [];
    for (let i = 0; i < entries.length; i++) {
      try {
        await appointmentsApi.updatePastStatus(entries[i].id, entries[i].status);
        settled.push(entries[i].id);
      } catch (err) {
        failed[entries[i].id] = err instanceof ApiError ? err.message : 'Nie udało się zapisać';
      }
      setSaving({ done: i + 1, total: entries.length });
    }
    setSaving(null);

    if (settled.length > 0) {
      const gone = new Set(settled);
      setAppointments((prev) => (prev ? prev.filter((a) => !gone.has(a.id)) : prev));
      setSelections((prev) => {
        const next = { ...prev };
        for (const id of settled) delete next[id];
        return next;
      });
    }
    setErrors(failed);

    const failCount = entries.length - settled.length;
    if (failCount === 0) toast.success(`Zaktualizowano ${settled.length} ${pluralVisits(settled.length)}`);
    else if (settled.length > 0) toast.warning(`Zapisano ${settled.length}/${entries.length} — ${failCount} z błędem, zaznaczone na liście`);
    else toast.error('Nie udało się zapisać zmian');
  }

  let body: ReactNode;
  if (loadFailed) {
    body = (
      <div className="pvp-state" role="alert">
        <h2 className="pvp-state-title">Nie udało się pobrać wizyt</h2>
        <p className="pvp-state-text">Sprawdź połączenie i spróbuj jeszcze raz.</p>
        <Button variant="primary" onClick={load}>
          Spróbuj ponownie
        </Button>
      </div>
    );
  } else if (appointments === null) {
    body = (
      <p className="pvp-state-text pvp-loading" role="status">
        Ładowanie…
      </p>
    );
  } else if (total === 0) {
    body = (
      <div className="pvp-state">
        <span className="pvp-state-icon" aria-hidden="true">
          <Icon name="check_circle" className="pvp-state-svg" />
        </span>
        <h2 className="pvp-state-title" tabIndex={-1} ref={emptyHeadingRef}>
          Wszystko rozliczone
        </h2>
        <p className="pvp-state-text">Żadna przeszła wizyta nie czeka już na status.</p>
        <ButtonLink variant="primary" to="/wizyty">
          Wróć do wizyt
        </ButtonLink>
      </div>
    );
  } else {
    body = (
      <>
        {employees.length > 1 && (
          <div className="pvp-filter">
            <label className="pvp-filter-label" htmlFor="pvp-employee">
              Pracownik
            </label>
            <SearchableSelect
              id="pvp-employee"
              triggerClassName="refined-select"
              searchPlaceholder="Szukaj pracownika…"
              options={[{ value: '', label: `Wszyscy (${total})` }, ...employees.map((e) => ({ value: String(e.id), label: `${e.name} (${e.count})` }))]}
              value={activeEmployee}
              onChange={setEmployeeId}
            />
          </div>
        )}

        {groups.map((g) => {
          const heading = dayHeading(g.date);
          const dayRemaining = g.items.filter((a) => !selections[a.id]);
          return (
            <section key={g.date} className="pvp-day" aria-labelledby={`pvp-day-${g.date}`}>
              <div className="pvp-day-head">
                <h2 className="pvp-day-title" id={`pvp-day-${g.date}`}>
                  {heading.rel && <span className="pvp-day-rel">{heading.rel} · </span>}
                  {heading.text}
                  <span className="pvp-day-count"> · {g.items.length}</span>
                </h2>
                {groups.length > 1 && (
                  <button type="button" className="pvp-day-bulk" disabled={dayRemaining.length === 0 || isSaving} onClick={() => completeRemaining(g.items)}>
                    {dayRemaining.length === 0 ? 'Dzień oznaczony' : `Zakończ pozostałe (${dayRemaining.length})`}
                  </button>
                )}
              </div>

              <ul className="pvp-cards">
                {g.items.map((apt) => {
                  const picked = selections[apt.id];
                  const error = errors[apt.id];
                  const mins = durationMinutes(apt.start_time, apt.end_time);
                  const client = apt.client_name?.trim() || 'Brak klienta';
                  return (
                    <li key={apt.id} className={`pvp-card${error ? ' pvp-card--error' : ''}`} data-status={picked ?? ''}>
                      <div className="pvp-card-head">
                        <span className="pvp-time">
                          {fmtTime(apt.start_time)}–{fmtTime(apt.end_time)}
                          {mins != null && <span className="pvp-dur"> · {mins} min</span>}
                        </span>
                        <span className="pvp-current">{STATUS_LABELS[apt.status] ?? apt.status}</span>
                      </div>
                      <h3 className="pvp-client">{client}</h3>
                      <p className="pvp-services">{apt.service_names ?? 'Brak usługi'}</p>
                      <p className="pvp-employee">
                        <span className="pvp-avatar" aria-hidden="true">
                          {initials(apt.employee_name)}
                        </span>
                        {apt.employee_name ?? 'Bez pracownika'}
                      </p>
                      <div className="pvp-choices" role="group" aria-label={`Status wizyty: ${client}, ${fmtTime(apt.start_time)}`}>
                        {RESOLUTIONS.map((s) => (
                          <button
                            key={s}
                            type="button"
                            className="pvp-choice"
                            data-status={s}
                            aria-pressed={picked === s}
                            disabled={isSaving}
                            onClick={() => choose(apt, s)}
                          >
                            <Icon name={CHOICE_ICON[s]} />
                            <span>{CHOICE_LABEL[s]}</span>
                          </button>
                        ))}
                      </div>
                      {error && (
                        <p className="pvp-error" role="alert">
                          {error}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </>
    );
  }

  return (
    <div className="refined-page pvp-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Rozlicz przeszłe wizyty</h1>
          <p className="page-subtitle">Ustaw status wizyt, które już się odbyły</p>
        </div>
      </header>

      {total > 0 && (
        <div className="pvp-top">
          <div className="pvp-top-row">
            <Link to="/wizyty" className="pvp-back">
              <Icon name="arrow_back" />
              Wizyty
            </Link>
            <p className="pvp-counter" aria-live="polite" aria-atomic="true">
              Oznaczono <strong>{changedCount}</strong> z {total}
            </p>
            <button type="button" className={`pvp-clear${changedCount === 0 ? ' pvp-clear--idle' : ''}`} disabled={isSaving} onClick={clearAll}>
              Wyczyść
            </button>
          </div>
          <div className="pvp-progress" aria-hidden="true">
            <span style={{ width: `${Math.round((changedCount / total) * 100)}%` }} />
          </div>
        </div>
      )}

      {body}

      {total > 0 && (
        <div className="pvp-bar">
          <Button variant="secondary" className="pvp-bar-btn" disabled={remainingVisible.length === 0 || isSaving} onClick={() => completeRemaining(visible)}>
            Zakończ pozostałe
            {remainingVisible.length > 0 && <span className="pvp-bar-count">{remainingVisible.length}</span>}
          </Button>
          <Button
            variant="primary"
            className="pvp-bar-btn"
            disabled={changedCount === 0}
            isLoading={isSaving}
            loadingText={saving ? `Zapisuję ${saving.done}/${saving.total}…` : 'Zapisuję…'}
            onClick={save}
          >
            Zapisz{changedCount > 0 ? ` (${changedCount})` : ''}
          </Button>
        </div>
      )}
    </div>
  );
}
