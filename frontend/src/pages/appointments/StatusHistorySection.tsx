import { Link } from 'react-router-dom';
import { useApiData } from '../../lib/useApiData';
import { appointmentsApi } from '../../lib/api/appointments';
import { STATUS_LABELS } from '../../types/appointment';
import type { AppointmentStatus, StatusHistoryEntry, StatusHistorySkeleton } from '../../types/appointment';
import type { SmsSentEntry } from '../../types/sms';
import { smsStatus } from '../../components/sms/smsFormat';
import '../../components/sms/sms.css';

export interface StatusHistorySectionProps {
  appointmentId: number;
  appointmentStatus: AppointmentStatus;
  /** Bumped by the page when something this section shows changed without the status moving,
   * e.g. a manual SMS send — the new message then appears in the timeline at once. */
  refreshKey?: number;
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return '—';
  // No timezone designator on the ISO string (backend already converted to
  // Warsaw local before serializing — utils.timezone.to_local) — the Date
  // constructor parses a date-time string with no offset as browser-local,
  // same assumption StatusDropdown's no_show time-window gate makes.
  return new Date(iso).toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** Which skeleton row stands for the visit's CURRENT status. `rescheduled` has no row of its own (the
 * visit is closed and the audit list below links to its successor), so nothing is marked for it. */
const CURRENT_ROW: Partial<Record<AppointmentStatus, number>> = {
  scheduled: 0,
  confirmed: 1,
  cancelled: 1,
  no_show: 2,
  in_progress: 3,
  completed: 4,
};

/** The fixed 5-checkpoint skeleton the user asked for, in order — checkpoint
 * #2 is a fork (a visit is either confirmed or cancelled, never both), shown
 * as one row that reflects whichever happened. */
function skeletonRows(s: StatusHistorySkeleton, status: AppointmentStatus): Array<{ label: string; at: string | null; current: boolean }> {
  const current = CURRENT_ROW[status] ?? -1;
  const cancelled = status === 'cancelled' || Boolean(s.cancelled_at);
  return [
    { label: STATUS_LABELS.scheduled, at: s.scheduled_at, current: current === 0 },
    { label: cancelled ? STATUS_LABELS.cancelled : STATUS_LABELS.confirmed, at: s.cancelled_at ?? s.confirmed_at, current: current === 1 },
    { label: STATUS_LABELS.no_show, at: s.no_show_at, current: current === 2 },
    { label: 'Rozpoczęcie (rzeczywiste)', at: s.started_at, current: current === 3 },
    { label: 'Zakończenie (rzeczywiste)', at: s.finished_at, current: current === 4 },
  ];
}

type TimelineItem = { kind: 'status'; at: string; entry: StatusHistoryEntry } | { kind: 'sms'; at: string; sms: SmsSentEntry };

/** Status changes and SMS sends in one chronological list. Both sides are Warsaw wall-clock ISO strings,
 * so lexicographic order IS chronological order. `Array.prototype.sort` is stable, so two events in the
 * same second keep "status change first, then the SMS it triggered". */
function mergeTimeline(history: StatusHistoryEntry[], sms: SmsSentEntry[]): TimelineItem[] {
  const items: TimelineItem[] = [
    ...history.map((entry): TimelineItem => ({ kind: 'status', at: entry.changed_at ?? '', entry })),
    ...sms.map((s): TimelineItem => ({ kind: 'sms', at: s.sent_at ?? '', sms: s })),
  ];
  return items.sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0));
}

/**
 * TASK3: finished-visit duration comparison + the always-shown "Historia
 * zmian statusu" audit trail, both driven by one status-history fetch. Self-
 * contained (fetches its own data) so WizytaDetailPage just mounts it below
 * its existing cards — same "own its own useApiData" shape as the rest of
 * that page's sections.
 *
 * Refetches whenever the visit's status or `refreshKey` changes, and keeps showing the previous answer
 * while it does (useApiData flips `loading` on every refetch but retains `data`) — a manual SMS send
 * must not blank the timeline.
 */
export function StatusHistorySection({ appointmentId, appointmentStatus, refreshKey = 0 }: StatusHistorySectionProps) {
  const state = useApiData(() => appointmentsApi.statusHistory(appointmentId), [appointmentId, appointmentStatus, refreshKey]);

  if (!state.data) {
    return (
      <div className="form-card">
        <h3 className="card-title">Historia zmian statusu</h3>
        {state.error ? (
          <p className="empty-text" style={{ color: 'var(--color-error)' }}>
            Błąd ładowania historii: {state.error.message}
          </p>
        ) : (
          <p className="empty-text">Ładowanie...</p>
        )}
      </div>
    );
  }

  const { history, skeleton, duration, sms = [] } = state.data;
  const timeline = mergeTimeline(history, sms);

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
          {skeletonRows(skeleton, appointmentStatus).map((row, i) => (
            <li
              key={i}
              aria-current={row.current ? 'step' : undefined}
              className={`status-skeleton-item${row.at ? ' status-skeleton-item--done' : ' status-skeleton-item--pending'}${row.current ? ' status-skeleton-item--current' : ''}`}
            >
              <span className="status-skeleton-dot" aria-hidden="true" />
              <span className="status-skeleton-label">
                {row.label}
                {row.current && <span className="status-skeleton-now">aktualny</span>}
              </span>
              <span className="status-skeleton-at">{fmtDateTime(row.at)}</span>
            </li>
          ))}
        </ol>

        {timeline.length === 0 ? (
          <p className="empty-text">Brak zarejestrowanych zmian statusu.</p>
        ) : (
          <ul className="status-audit-list">
            {timeline.map((item, i) =>
              item.kind === 'status' ? (
                <li key={`s${i}`} className="status-audit-item">
                  <span>
                    {item.entry.old_status ? `${STATUS_LABELS[item.entry.old_status]} → ` : ''}
                    {item.entry.linked_appointment_id != null ? (
                      <Link to={`/wizyty/${item.entry.linked_appointment_id}`} className="status-audit-link">
                        <strong>{STATUS_LABELS[item.entry.new_status]}</strong>
                      </Link>
                    ) : (
                      <strong>{STATUS_LABELS[item.entry.new_status]}</strong>
                    )}
                    {item.entry.detail && <span className="status-audit-detail"> — {item.entry.detail}</span>}
                  </span>
                  <span className="status-audit-meta">
                    {fmtDateTime(item.entry.changed_at)} · {item.entry.user_name || 'system'}
                  </span>
                </li>
              ) : (
                <li key={`m${item.sms.id}`} className="status-audit-item status-audit-item--sms">
                  <span>
                    <span className="status-audit-sms-tag">SMS</span>
                    <strong>{item.sms.type_name}</strong>{' '}
                    <span
                      className={`sms-pill ${smsStatus(item.sms.status).className}`}
                      title={item.sms.status === 'failed' ? (item.sms.error_message ?? '') : undefined}
                    >
                      {smsStatus(item.sms.status).label}
                    </span>
                  </span>
                  <span className="status-audit-meta">
                    {fmtDateTime(item.sms.sent_at)} · {item.sms.automatic ? 'System (auto)' : item.sms.sent_by || 'system'}
                  </span>
                </li>
              ),
            )}
          </ul>
        )}
        {state.error && (
          <p className="empty-text" style={{ color: 'var(--color-error)' }}>
            Nie udało się odświeżyć historii: {state.error.message}
          </p>
        )}
      </div>
    </>
  );
}
