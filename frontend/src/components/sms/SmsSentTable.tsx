import type { SmsSentEntry } from '../../types/sms';
import { fmtWhen, smsStatus } from './smsFormat';
import './sms.css';

export interface SmsSentTableProps {
  rows: SmsSentEntry[];
  emptyText?: string;
}

/** One visit's sent (and failed) messages, newest first as the server returns them. */
export function SmsSentTable({ rows, emptyText = 'Brak wysłanych wiadomości SMS' }: SmsSentTableProps) {
  return (
    <div className="table-container stack-cards-wrap">
      <table className="refined-table stack-cards sms-table">
        <thead>
          <tr>
            <th>Wysłano</th>
            <th>Typ SMS</th>
            <th>Status</th>
            <th>Wysłał</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={4} className="empty-state cell-empty">
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((r) => {
              const status = smsStatus(r.status);
              return (
                <tr key={r.id}>
                  <td className="cell-name sms-when" data-label="Wysłano">
                    {fmtWhen(r.sent_at)}
                  </td>
                  <td data-label="Typ SMS">{r.type_name}</td>
                  <td data-label="Status">
                    <span className={`sms-pill ${status.className}`} title={r.status === 'failed' ? r.error_message ?? '' : undefined}>
                      {status.label}
                    </span>
                  </td>
                  <td data-label="Wysłał">{r.automatic ? 'System (auto)' : r.sent_by || '—'}</td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
