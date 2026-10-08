import { Link } from 'react-router-dom';
import type { SmsPendingEntry } from '../../types/sms';
import { fmtPhone, fmtVisit, fmtWhen, fmtWhenExact } from './smsFormat';
import './sms.css';

/** Strict `=== false`: a response without the flag (an older backend during a rolling deploy) means "deliverable". */
const isRefused = (r: SmsPendingEntry) => r.deliverable === false;

/** Short, printed in red under the number. The full reason stays in `note` (tooltip on the struck-through time). */
const PHONE_PROBLEM_LABEL = { missing: 'Nie zapisano', invalid: 'Błędny numer' } as const;

export interface SmsPendingTableProps {
  rows: SmsPendingEntry[];
  loading?: boolean;
  /** A reload with the previous rows still on screen (month change, paging): dim them rather than blank the table. */
  refreshing?: boolean;
  /** `history`: the global queue on Wysyłki SMS (client, phone, link to the visit). `visit`: one visit's queue. */
  variant: 'history' | 'visit';
  emptyText?: string;
}

/** Messages the scheduler will still send, with the exact tick that will carry each one.
 * `~` + a tooltip mark an ESTIMATED time (the serving process has no scheduler anchor); a struck-through
 * time marks a row the scheduler will refuse (`deliverable: false`). On the visit card the reason is its own
 * "Uwagi" column; on Wysyłki SMS it is a short red label under the phone number (a number problem) or the
 * tooltip of the struck-through time (anything else), so the table needs no notes column. */
export function SmsPendingTable({ rows, loading, refreshing, variant, emptyText = 'Brak oczekujących wiadomości SMS' }: SmsPendingTableProps) {
  const history = variant === 'history';
  const columns = history ? 5 : 4;
  const whenLabel = history ? 'Zaplanowany na' : 'Zostanie wysłany';
  const typeLabel = history ? 'Typ' : 'Typ SMS';

  return (
    <div className={`table-container stack-cards-wrap${refreshing ? ' sms-refreshing' : ''}`} aria-busy={refreshing || undefined}>
      <table className="refined-table stack-cards sms-table">
        <thead>
          <tr>
            <th>{whenLabel}</th>
            <th>{typeLabel}</th>
            <th>Odbiorca</th>
            {history && <th>Nr tel</th>}
            {history && <th>Wizyta z dnia</th>}
            {!history && <th>Uwagi</th>}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns} className="empty-state cell-empty">
                Ładowanie...
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={columns} className="empty-state cell-empty">
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((r) => (
              <tr key={r.key}>
                <td className="cell-name sms-when" data-label={whenLabel}>
                  {!isRefused(r) ? (
                    <span title={r.estimated ? 'Szacunek: ten serwer nie uruchamia harmonogramu, czas zaokrąglony do kwadransa' : fmtWhenExact(r.will_be_sent_at)}>
                      {r.estimated && '~'}
                      {fmtWhen(r.will_be_sent_at)}
                    </span>
                  ) : (
                    // Not a promise: the scheduler reaches this row on that tick and refuses it. Struck through for
                    // sighted users, spelled out for screen readers; the reason is in "Uwagi" (visit card) or the tooltip.
                    <span className="sms-skipped" title={history ? r.note ?? undefined : undefined}>
                      <span className="sr-only">Nie zostanie wysłany{history && r.note ? ` (${r.note})` : ''}: </span>
                      <s>{fmtWhen(r.will_be_sent_at)}</s>
                    </span>
                  )}
                </td>
                <td data-label={typeLabel}>{r.type_name}</td>
                <td data-label="Odbiorca">
                  {r.recipient_name || '—'}
                  {r.recipient_kind === 'employee' && <span className="sms-recipient-tag">pracownik</span>}
                </td>
                {history && (
                  <td className="sms-phone" data-label="Nr tel">
                    <span className="mono">{r.phone_number ? fmtPhone(r.phone_number) : '—'}</span>
                    {r.phone_problem && <span className="sms-phone-error">{PHONE_PROBLEM_LABEL[r.phone_problem]}</span>}
                  </td>
                )}
                {history && (
                  <td data-label="Wizyta z dnia">
                    {r.appointment_id != null ? (
                      <Link to={`/wizyty/${r.appointment_id}`} className="sms-visit-link">
                        {fmtVisit(r.appointment_date, r.start_time)}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                )}
                {!history && (
                  <td className={`sms-note${isRefused(r) ? ' sms-note--warn' : ''}`} data-label="Uwagi">
                    {r.note || '—'}
                  </td>
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
