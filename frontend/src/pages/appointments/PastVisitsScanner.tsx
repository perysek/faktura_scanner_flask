import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import './PastVisitsScanner.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { useToast } from '../../components/feedback/ToastProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import type { PastPendingAppointment, PastResolutionStatus } from '../../types/appointment';
import { STATUS_LABELS } from '../../types/appointment';
import { useIsMobile } from './MobileWizytyCalendarView';
import { RESOLUTIONS, durationMinutes, fmtDateMonth, fmtHours, fmtTime, pluralVisits } from './pastVisitsShared';

const STATUS_VAR: Record<string, string> = {
  scheduled: '--color-status-scheduled',
  confirmed: '--color-status-confirmed',
  in_progress: '--color-status-in-progress',
  completed: '--color-status-completed',
  cancelled: '--color-status-cancelled',
  no_show: '--color-status-no-show',
};

/** Reads a `--color-status-*` custom property at call time and returns the
 * cycle-button inline style — mirrors static/js/
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

/** "Rozlicz przeszłe wizyty" — a shared trigger + modal dropped into every
 * Wizyty page's header (list + 3 calendar views), ported from
 * static/js/past_visits_scanner.js. Self-contained: fetches its own count on
 * mount and stays hidden while zero. Desktop opens a modal with a compact
 * sticky-header table and a single per-row "cycle status" button (original →
 * completed → cancelled → no_show → original …). Phones (≤640px) don't get the
 * modal at all — the trigger is a link to the full-screen `PastVisitsPage`
 * (`/wizyty/rozlicz`), which is built for thumbs. Backend
 * (`/api/appointments/past-pending` + `/api/appointments/<id>/past-status`)
 * was already fully JSON. */
export function PastVisitsScanner() {
  const toast = useToast();
  const isPhone = useIsMobile(640);
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

  if (isPhone) {
    return (
      <Link
        to="/wizyty/rozlicz"
        className="refined-btn-secondary refined-btn-sm pv-trigger pv-trigger--phone"
        aria-label={`Rozlicz przeszłe wizyty, ${appointments.length} do rozliczenia`}
      >
        Rozlicz <span className="pv-trigger-count" aria-hidden="true">{appointments.length}</span>
      </Link>
    );
  }

  return (
    <>
      <button type="button" className="refined-btn-secondary refined-btn-sm pv-trigger" onClick={open}>
        Rozlicz przeszłe wizyty <span className="pv-trigger-count">{appointments.length}</span>
      </button>

      <Modal isOpen={isOpen} onClose={() => setIsOpen(false)} title="Przeszłe wizyty do rozliczenia" size="large">
        <div className="pv-note">Zaktualizuj status przeszłych wizyt.</div>

        <>
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
        </>

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
