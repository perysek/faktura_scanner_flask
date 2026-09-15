import { Link } from 'react-router-dom';
import { useApiData } from '../../lib/useApiData';
import { appointmentsApi } from '../../lib/api/appointments';
import { STATUS_LABELS } from '../../types/appointment';
import type { AppointmentStatus, StatusHistorySkeleton } from '../../types/appointment';

export interface StatusHistorySectionProps {
  appointmentId: number;
  appointmentStatus: AppointmentStatus;
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return '—';
  // No timezone designator on the ISO string (backend already converted to
  // Warsaw local before serializing — utils.timezone.to_local) — the Date
  // constructor parses a date-time string with no offset as browser-local,
  // same assumption StatusDropdown's no_show time-window gate makes.
  return new Date(iso).toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** The fixed 5-checkpoint skeleton the user asked for, in order — checkpoint
 * #2 is a fork (a visit is either confirmed or cancelled, never both), shown
 * as one row that reflects whichever happened. */
function skeletonRows(s: StatusHistorySkeleton): Array<{ label: string; at: string | null }> {
  return [
    { label: STATUS_LABELS.scheduled, at: s.scheduled_at },
    { label: s.cancelled_at ? STATUS_LABELS.cancelled : STATUS_LABELS.confirmed, at: s.cancelled_at ?? s.confirmed_at },
    { label: STATUS_LABELS.no_show, at: s.no_show_at },
    { label: 'Rozpoczęcie (rzeczywiste)', at: s.started_at },
    { label: 'Zakończenie (rzeczywiste)', at: s.finished_at },
  ];
}

/**
 * TASK3: finished-visit duration comparison + the always-shown "Historia
 * zmian statusu" audit trail, both driven by one status-history fetch. Self-
 * contained (fetches its own data) so WizytaDetailPage just mounts it below
 * its existing cards — same "own its own useApiData" shape as the rest of
 * that page's sections.
 */
export function StatusHistorySection({ appointmentId, appointmentStatus }: StatusHistorySectionProps) {
  const state = useApiData(() => appointmentsApi.statusHistory(appointmentId), [appointmentId]);

  if (state.loading) {
    return (
      <div className="form-card">
        <h3 className="card-title">Historia zmian statusu</h3>
        <p className="empty-text">Ładowanie...</p>
      </div>
    );
  }
  if (state.error || !state.data) {
    return (
      <div className="form-card">
        <h3 className="card-title">Historia zmian statusu</h3>
        <p className="empty-text" style={{ color: 'var(--color-error)' }}>
          Błąd ładowania historii: {state.error?.message}
        </p>
      </div>
    );
  }

  const { history, skeleton, duration } = state.data;

  return (
    <>
      {appointmentStatus === 'completed' && (
        <div className="form-card">
          <h3 className="card-title">Czas trwania</h3>
          <div className="duration-compare">
            <div className="duration-compare-row">
              <span>Zaplanowany:</span>
              <span>{duration.scheduled_minutes} min</span>
            </div>
            <div className="duration-compare-row">
              <span>Rzeczywisty:</span>
              <span>
                {duration.actual_minutes !== null ? (
                  <>
                    {duration.actual_minutes} min
                    {duration.ratio_pct !== null && <span className="duration-ratio"> ({duration.ratio_pct}%)</span>}
                  </>
                ) : (
                  <span className="empty-text">nie zmierzono czasu trwania</span>
                )}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="form-card">
        <h3 className="card-title">Historia zmian statusu</h3>

        <ol className="status-skeleton">
          {skeletonRows(skeleton).map((row, i) => (
            <li key={i} className={`status-skeleton-item${row.at ? ' status-skeleton-item--done' : ' status-skeleton-item--pending'}`}>
              <span className="status-skeleton-dot" aria-hidden="true" />
              <span className="status-skeleton-label">{row.label}</span>
              <span className="status-skeleton-at">{fmtDateTime(row.at)}</span>
            </li>
          ))}
        </ol>

        {history.length === 0 ? (
          <p className="empty-text">Brak zarejestrowanych zmian statusu.</p>
        ) : (
          <ul className="status-audit-list">
            {history.map((entry, i) => (
              <li key={i} className="status-audit-item">
                <span>
                  {entry.old_status ? `${STATUS_LABELS[entry.old_status]} → ` : ''}
                  {entry.linked_appointment_id != null ? (
                    <Link to={`/wizyty/${entry.linked_appointment_id}`} className="status-audit-link">
                      <strong>{STATUS_LABELS[entry.new_status]}</strong>
                    </Link>
                  ) : (
                    <strong>{STATUS_LABELS[entry.new_status]}</strong>
                  )}
                </span>
                <span className="status-audit-meta">
                  {fmtDateTime(entry.changed_at)} · {entry.user_name || 'system'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
