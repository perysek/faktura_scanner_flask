import { useState } from 'react';
import { Link } from 'react-router-dom';
import './SettingsPages.css';
import { useApiData } from '../../lib/useApiData';
import { smsSettingsApi } from '../../lib/api/smsSettings';

const PAGE_SIZE = 100;

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  sent: { label: 'Wysłany', className: 'badge-green' },
  delivered: { label: 'Dostarczony', className: 'badge-teal' },
  failed: { label: 'Błąd', className: 'badge-red' },
  pending: { label: 'Oczekuje', className: 'badge-gray' },
};

/** Historia wysyłek SMS — ported from templates/settings/sms_log.html.
 * Offset-based pagination, 1:1 with the original (no page-number picker,
 * just Poprzednie/Następne). */
export function SmsLogPage() {
  const [offset, setOffset] = useState(0);
  const logState = useApiData(() => smsSettingsApi.log(offset, PAGE_SIZE), [offset]);
  const rows = logState.data?.rows ?? [];

  return (
    <div className="refined-page settings-page animate-fade-up">
      <header className="page-header sms-log-header">
        <Link to="/ustawienia/sms" className="settings-footer-link">
          ← Ustawienia SMS
        </Link>
        <h1 className="page-title">Historia wysyłek SMS</h1>
      </header>

      <div className="table-container">
        <table className="refined-table">
          <thead>
            <tr>
              <th>Data wysyłki</th>
              <th>Typ SMS</th>
              <th>Klient</th>
              <th>Telefon</th>
              <th>Wizyta</th>
              <th>Status</th>
              <th>Twilio SID</th>
              <th>Wysłał</th>
              <th>Potwierdzenie</th>
            </tr>
          </thead>
          <tbody>
            {logState.loading ? (
              <tr>
                <td colSpan={9} className="empty-state cell-empty">
                  Ładowanie...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="empty-state cell-empty">
                  Brak historii wysyłek SMS
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const status = STATUS_LABEL[r.status] ?? STATUS_LABEL.pending;
                return (
                  <tr key={r.id}>
                    <td>{r.sent_at ? r.sent_at.slice(0, 16).replace('T', ' ') : '—'}</td>
                    <td>{r.type_name || r.message_type_key}</td>
                    <td>{r.client_name}</td>
                    <td className="mono">{r.phone_number}</td>
                    <td>
                      {r.appointment_date} {r.start_time?.slice(0, 5)}
                    </td>
                    <td>
                      <span className={`badge-pill ${status.className}`} title={r.status === 'failed' ? r.error_message ?? '' : undefined}>
                        {status.label}
                      </span>
                    </td>
                    <td className="mono">{r.twilio_sid || '—'}</td>
                    <td>{r.created_by_name || '—'}</td>
                    <td>
                      {r.appt_confirmation_status === 'confirmed' ? (
                        <span style={{ color: 'var(--color-success)' }}>✓</span>
                      ) : r.appt_confirmation_status === 'declined' ? (
                        <span style={{ color: 'var(--color-error)' }}>✗</span>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      <div className="sms-log-pagination">
        {offset > 0 && (
          <button type="button" className="refined-btn-secondary btn-press" onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            ← Poprzednie
          </button>
        )}
        {rows.length === PAGE_SIZE && (
          <button type="button" className="refined-btn-secondary btn-press" onClick={() => setOffset(offset + PAGE_SIZE)}>
            Następne →
          </button>
        )}
      </div>
    </div>
  );
}
