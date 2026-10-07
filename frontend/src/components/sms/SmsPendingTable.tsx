import { Link } from 'react-router-dom';
import type { SmsPendingEntry } from '../../types/sms';
import { fmtVisit, fmtWhen, fmtWhenExact } from './smsFormat';
import './sms.css';

/** Strict `=== false`: a response without the flag (an older backend during a rolling deploy) means "deliverable". */
const isRefused = (r: SmsPendingEntry) => r.deliverable === false;

export interface SmsPendingTableProps {
  rows: SmsPendingEntry[];
  loading?: boolean;
  /** `history`: the global queue (client, phone, link to the visit). `visit`: one visit's queue. */
  variant: 'history' | 'visit';
  emptyText?: string;
}

/** Messages the scheduler will still send, with the exact tick that will carry each one.
 * `~` + a tooltip mark an ESTIMATED time (the serving process has no scheduler anchor); a struck-through
 * time marks a row the scheduler will refuse (`deliverable: false`), explained in "Uwagi". */
export function SmsPendingTable({ rows, loading, variant, emptyText = 'Brak oczekujących wiadomości SMS' }: SmsPendingTableProps) {
  const history = variant === 'history';
  const columns = history ? 6 : 4;

  return (
    <div className="table-container stack-cards-wrap">
      <table className="refined-table stack-cards sms-table">
        <thead>
          <tr>
            <th>Zostanie wysłany</th>
            <th>Typ SMS</th>
            <th>Odbiorca</th>
            {history && <th>Telefon</th>}
            {history && <th>Wizyta</th>}
            <th>Uwagi</th>
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
                <td className="cell-name sms-when" data-label="Zostanie wysłany">
                  {!isRefused(r) ? (
                    <span title={r.estimated ? 'Szacunek: ten serwer nie uruchamia harmonogramu, czas zaokrąglony do kwadransa' : fmtWhenExact(r.will_be_sent_at)}>
                      {r.estimated && '~'}
                      {fmtWhen(r.will_be_sent_at)}
                    </span>
                  ) : (
                    // Not a promise: the scheduler reaches this row on that tick and refuses it. Struck through for
                    // sighted users, spelled out for screen readers; the reason is in "Uwagi".
                    <span className="sms-skipped">
                      <span className="sr-only">Nie zostanie wysłany: </span>
                      <s>{fmtWhen(r.will_be_sent_at)}</s>
                    </span>
                  )}
                </td>
                <td data-label="Typ SMS">{r.type_name}</td>
                <td data-label="Odbiorca">
                  {r.recipient_name || '—'}
                  {r.recipient_kind === 'employee' && <span className="sms-recipient-tag">pracownik</span>}
                </td>
                {history && (
                  <td className="mono" data-label="Telefon">
                    {r.phone_number || '—'}
                  </td>
                )}
                {history && (
                  <td data-label="Wizyta">
                    {r.appointment_id != null ? (
                      <Link to={`/wizyty/${r.appointment_id}`} className="sms-visit-link">
                        {fmtVisit(r.appointment_date, r.start_time)}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                )}
                <td className={`sms-note${isRefused(r) ? ' sms-note--warn' : ''}`} data-label="Uwagi">
                  {r.note || '—'}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
