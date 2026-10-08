import { Icon } from '../../lib/icons/Icon';
import type { SmsLogEntry, SmsResponse } from '../../types/settings';
import { fmtPhone, fmtVisit, fmtWhen } from './smsFormat';
import './sms.css';

/** Texts the system sends on its own carry no user: the scheduler, and the confirmation of an online booking. */
const AUTOMATIC_SENDERS = ['System (auto)', 'Rezerwacja online'];
const AUTOMATIC_LABEL = 'Algorytm';

export function creatorOf(row: Pick<SmsLogEntry, 'created_by_user_id' | 'created_by_name'>): { label: string; automatic: boolean } {
  const name = row.created_by_name?.trim() || null;
  // A user id means a person. Without one it is the system, unless a person's name survived (a deleted account).
  const automatic = row.created_by_user_id == null && (name == null || AUTOMATIC_SENDERS.includes(name));
  return { label: automatic ? AUTOMATIC_LABEL : name ?? '—', automatic };
}

type DeliveryState = 'failed' | 'responded' | 'sent' | 'pending';

const RESPONSE_LABEL: Record<SmsResponse, string> = {
  confirmed: 'Klient potwierdził wizytę',
  declined: 'Klient odwołał wizytę',
  rated: 'Klient ocenił wizytę',
};

/** One glyph per state, told apart by shape AND colour (never colour alone): ! failed, ✓ sent, ✓-in-a-circle answered. */
const STATE_ICON: Record<DeliveryState, string> = { failed: 'error', sent: 'check', responded: 'check_circle', pending: 'schedule' };

export function deliveryOf(row: SmsLogEntry): { state: DeliveryState; label: string } {
  if (row.status === 'failed') return { state: 'failed', label: row.error_message ? `Nie wysłano: ${row.error_message}` : 'Nie wysłano' };
  if (row.status === 'pending') return { state: 'pending', label: 'Oczekuje na wysłanie' };
  if (row.response) return { state: 'responded', label: RESPONSE_LABEL[row.response] };
  return { state: 'sent', label: row.status === 'delivered' ? 'Wysłano i dostarczono' : 'Wysłano' };
}

function DeliveryIcon({ row }: { row: SmsLogEntry }) {
  const { state, label } = deliveryOf(row);
  return (
    <span className={`sms-state sms-state--${state}`} role="img" aria-label={label} title={label}>
      <Icon name={STATE_ICON[state]} />
    </span>
  );
}

const COLUMNS = 7;

export interface SmsLogTableProps {
  rows: SmsLogEntry[];
  /** First load: nothing to show yet. */
  loading?: boolean;
  /** A reload with the previous rows still on screen (month change, paging): dim them rather than blank the table. */
  refreshing?: boolean;
}

/** Historia SMS, tab "Wysłane". Newest first; the recipient carries the delivery state as a trailing icon. */
export function SmsLogTable({ rows, loading, refreshing }: SmsLogTableProps) {
  return (
    <div className={`table-container stack-cards-wrap${refreshing ? ' sms-refreshing' : ''}`} aria-busy={refreshing || undefined}>
      <table className="refined-table stack-cards sms-table sms-table--log">
        <thead>
          <tr>
            <th>Utworzony przez</th>
            <th className="sms-col-when">Data wysyłki</th>
            <th>Typ SMS</th>
            <th className="sms-col-when">Wizyta z dnia</th>
            <th>Odbiorca</th>
            <th>Nr telefonu</th>
            <th>Tekst</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={COLUMNS} className="empty-state cell-empty">
                Ładowanie...
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={COLUMNS} className="empty-state cell-empty">
                Brak wysłanych SMS do końca wybranego miesiąca
              </td>
            </tr>
          ) : (
            rows.map((r) => {
              const creator = creatorOf(r);
              return (
                <tr key={r.id}>
                  <td data-label="Utworzony przez" title={creator.automatic ? r.created_by_name ?? 'Wysłane automatycznie' : undefined}>
                    {creator.label}
                  </td>
                  <td className="cell-name sms-when" data-label="Data wysyłki">
                    {fmtWhen(r.sent_at)}
                  </td>
                  <td data-label="Typ SMS">{r.type_name || r.message_type_key}</td>
                  <td className="sms-when" data-label="Wizyta z dnia">
                    {fmtVisit(r.appointment_date, r.start_time)}
                  </td>
                  <td data-label="Odbiorca">
                    <span className="sms-recipient">
                      {r.client_name}
                      <DeliveryIcon row={r} />
                    </span>
                  </td>
                  <td className="sms-phone" data-label="Nr telefonu">
                    <span className="mono">{fmtPhone(r.phone_number, { plus: false })}</span>
                  </td>
                  <td className="sms-text-cell" data-label="Tekst">
                    <span className="sms-text">{r.message_body || '—'}</span>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
