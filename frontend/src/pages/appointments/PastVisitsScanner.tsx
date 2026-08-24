import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import './PastVisitsScanner.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { useToast } from '../../components/feedback/ToastProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import type { PastPendingAppointment, PastResolutionStatus } from '../../types/appointment';
import { STATUS_LABELS } from '../../types/appointment';

const RESOLUTIONS: PastResolutionStatus[] = ['completed', 'cancelled', 'no_show'];

const STATUS_LABELS_SHORT: Record<PastResolutionStatus, string> = {
  completed: 'Zakończona',
  cancelled: 'Anulowana',
  no_show: 'No-show',
};

const STATUS_VAR: Record<string, string> = {
  scheduled: '--color-status-scheduled',
  confirmed: '--color-status-confirmed',
  in_progress: '--color-status-in-progress',
  completed: '--color-status-completed',
  cancelled: '--color-status-cancelled',
  no_show: '--color-status-no-show',
};

const MONTHS_PL = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca', 'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia'];

function fmtDateMonth(dateStr: string): string {
  const [, m, d] = dateStr.split('-').map(Number);
  return `${d} ${MONTHS_PL[m - 1] ?? ''}`.trim();
}
function fmtTime(t: string): string {
  return t.slice(0, 5);
}
function durationMinutes(start: string, end: string): number | null {
  const toMin = (t: string) => {
    const [h, m] = t.split(':').map(Number);
    return Number.isNaN(h) || Number.isNaN(m) ? null : h * 60 + m;
  };
  const a = toMin(start);
  const b = toMin(end);
  if (a == null || b == null) return null;
  let diff = b - a;
  if (diff < 0) diff += 24 * 60;
  return diff;
}
function fmtHours(minutes: number): string {
  return String(Math.round((minutes / 60) * 100) / 100).replace('.', ',');
}
function initials(name: string | null): string {
  if (!name) return '—';
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
function pluralVisits(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (n === 1) return 'wizytę';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'wizyty';
  return 'wizyt';
}

/** Reads a `--color-status-*` custom property at call time and returns the
 * cycle-button/card-toggle inline style — mirrors static/js/
 * past_visits_scanner.js's `badgeStyle()`/`cssVar()`/`cssVarAlpha()`, which
 * read the CSS custom property live (so it follows theme switches) rather
 * than hardcoding a palette here. */
function statusStyle(status: string): CSSProperties {
  const varName = STATUS_VAR[status] ?? '--color-ink-muted';
  const hex = getComputedStyle(document.documentElement).getPropertyValue(varName).trim() || '#6b6b6b';
  const r = parseInt(hex.slice(1, 3), 16) || 107;
  const g = parseInt(hex.slice(3, 5), 16) || 107;
  const b = parseInt(hex.slice(5, 7), 16) || 107;
  return {
    background: `rgba(${r},${g},${b},0.12)`,
    color: hex,
    border: `1px solid rgba(${r},${g},${b},0.35)`,
  };
}

/** "Rozlicz przeszłe wizyty" — a shared trigger button + modal dropped into
 * every Wizyty page's header (list + 3 calendar views), ported from
 * static/js/past_visits_scanner.js. Self-contained: fetches its own count on
 * mount, stays hidden while zero, opens a modal on click. Desktop shows a
 * compact sticky-header table with a single per-row "cycle status" button
 * (original → completed → cancelled → no_show → original …); mobile (≤640px,
 * `.pv-mobile`/`.pv-desktop` toggle in PastVisitsScanner.css, ported 1:1 from
 * static/css/input.css) shows horizontally-scrollable cards with a 3-way
 * toggle instead. Backend (`/api/appointments/past-pending` +
 * `/api/appointments/<id>/past-status`) was already fully JSON. */
export function PastVisitsScanner() {
  const toast = useToast();
  const [appointments, setAppointments] = useState<PastPendingAppointment[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [selections, setSelections] = useState<Record<number, PastResolutionStatus>>({});
  const [saving, setSaving] = useState(false);

  function refreshCount() {
    appointmentsApi
      .pastPending()
      .then(setAppointments)
      .catch(() => setAppointments([]));
  }

  useEffect(refreshCount, []);

  async function open() {
    try {
      const fresh = await appointmentsApi.pastPending();
      setAppointments(fresh);
      if (fresh.length === 0) {
        toast.success('Brak przeszłych wizyt do rozliczenia');
        return;
      }
      setSelections({});
      setIsOpen(true);
    } catch {
      if (appointments.length > 0) {
        setSelections({});
        setIsOpen(true);
      }
    }
  }

  function cycleStatus(apt: PastPendingAppointment) {
    const cycle: string[] = [apt.status, ...RESOLUTIONS];
    const current = selections[apt.id] ?? apt.status;
    const idx = cycle.indexOf(current);
    const next = cycle[(idx + 1) % cycle.length];
    setSelections((prev) => {
      const copy = { ...prev };
      if (next === apt.status) {
        delete copy[apt.id];
      } else {
        copy[apt.id] = next as PastResolutionStatus;
      }
      return copy;
    });
  }

  function selectStatus(apt: PastPendingAppointment, status: PastResolutionStatus) {
    setSelections((prev) => {
      const copy = { ...prev };
      if (copy[apt.id] === status) {
        delete copy[apt.id];
      } else {
        copy[apt.id] = status;
      }
      return copy;
    });
  }

  function markAllCompleted() {
    const next: Record<number, PastResolutionStatus> = {};
    appointments.forEach((a) => {
      next[a.id] = 'completed';
    });
    setSelections(next);
  }

  async function saveChanges() {
    const changes = Object.entries(selections).map(([id, status]) => ({ appointmentId: Number(id), status }));
    if (changes.length === 0) return;
    setSaving(true);

    let successCount = 0;
    let errorCount = 0;
    for (const change of changes) {
      try {
        await appointmentsApi.updatePastStatus(change.appointmentId, change.status);
        successCount++;
      } catch {
        errorCount++;
      }
    }

    setSaving(false);
    if (successCount > 0) {
      setIsOpen(false);
      if (errorCount > 0) {
        toast.warning(`Zaktualizowano ${successCount}/${changes.length} wizyt — ${errorCount} błędów`);
      } else {
        toast.success(`Zaktualizowano ${successCount} ${pluralVisits(successCount)}`);
      }
      refreshCount();
    } else {
      toast.error('Nie udało się zapisać zmian');
    }
  }

  const changedCount = Object.keys(selections).length;

  if (appointments.length === 0) return null;

  return (
    <>
      <button type="button" className="refined-btn-secondary refined-btn-sm pv-trigger" onClick={open}>
        Rozlicz przeszłe wizyty <span className="pv-trigger-count">{appointments.length}</span>
      </button>

      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Przeszłe wizyty do rozliczenia" size="large">
        <div className="pv-note">Zaktualizuj status przeszłych wizyt.</div>

        <div className="pv-desktop">
          <div className="pv-table-wrap">
            <table className="pv-table">
              <thead>
                <tr>
                  <th>Klient</th>
                  <th>Pracownik</th>
                  <th>Data i godzina</th>
                  <th>Usługi</th>
                  <th className="pv-th-status">Status</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map((apt) => {
                  const status = selections[apt.id] ?? apt.status;
                  const mins = durationMinutes(apt.start_time, apt.end_time);
                  const fullName = (apt.client_name ?? '').trim();
                  const sp = fullName.indexOf(' ');
                  const firstName = sp === -1 ? fullName : fullName.slice(0, sp);
                  const lastName = sp === -1 ? '' : fullName.slice(sp + 1);
                  return (
                    <tr key={apt.id}>
                      <td className="pv-cell-name">
                        <span>{firstName}</span>
                        <span>{lastName}</span>
                      </td>
                      <td>{apt.employee_name}</td>
                      <td className="pv-cell-dt">
                        <span className="pv-date">{fmtDateMonth(apt.appointment_date)}</span>
                        <span className="pv-time">{fmtTime(apt.start_time)}</span>
                        <span className="pv-dur">{mins != null ? `${mins}min (${fmtHours(mins)}h)` : ''}</span>
                      </td>
                      <td className="pv-cell-services" title={apt.service_names ?? 'Brak'}>
                        {apt.service_names ?? 'Brak'}
                      </td>
                      <td className="pv-status-cell">
                        <button
                          type="button"
                          className={`pv-cycle${selections[apt.id] ? ' pv-cycle--changed' : ''}`}
                          style={statusStyle(status)}
                          aria-label="Zmień status — kliknij, aby przełączyć"
                          title="Kliknij, aby przełączyć status"
                          onClick={() => cycleStatus(apt)}
                        >
                          <span className="pv-cycle-label">{STATUS_LABELS[status as keyof typeof STATUS_LABELS] ?? status}</span>
                          <span className="pv-cycle-icon" aria-hidden="true">
                            ↻
                          </span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="pv-mobile">
          <div className="pv-cards">
            {appointments.map((apt) => {
              const selected = selections[apt.id];
              const mins = durationMinutes(apt.start_time, apt.end_time);
              return (
                <div key={apt.id} className={`pv-card${selected ? ' pv-card--changed' : ''}`}>
                  <div className="pv-card-name" title={apt.client_name ?? ''}>
                    {apt.client_name}
                  </div>
                  <div className="pv-card-service" title={apt.service_names ?? 'Brak usługi'}>
                    {apt.service_names ?? 'Brak usługi'}
                  </div>
                  <div className="pv-card-meta">
                    <span className="pv-card-initials" title={apt.employee_name ?? ''}>
                      {initials(apt.employee_name)}
                    </span>
                    <span className="pv-card-dt">
                      {fmtDateMonth(apt.appointment_date)}, {fmtTime(apt.start_time)}
                      {mins != null ? ` · ${mins}min` : ''}
                    </span>
                  </div>
                  <div className="pv-card-toggle" role="group" aria-label="Status wizyty">
                    {RESOLUTIONS.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className="pv-toggle-btn"
                        style={selected === s ? statusStyle(s) : undefined}
                        aria-pressed={selected === s}
                        onClick={() => selectStatus(apt, s)}
                      >
                        {STATUS_LABELS_SHORT[s]}
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="form-actions pv-footer">
          <Button variant="secondary" onClick={markAllCompleted}>
            Wszystkie na zakończone
          </Button>
          <span className="pv-progress">
            {changedCount}/{appointments.length}
          </span>
          <Button variant="primary" disabled={changedCount === 0} isLoading={saving} loadingText="Zapisywanie…" onClick={saveChanges}>
            Zapisz zmiany
          </Button>
        </div>
      </Modal>
    </>
  );
}
