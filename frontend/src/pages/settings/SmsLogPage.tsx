import { useState } from 'react';
import { Link } from 'react-router-dom';
import './SettingsPages.css';
import { useApiData } from '../../lib/useApiData';
import { smsSettingsApi } from '../../lib/api/smsSettings';
import { SmsTabs, panelId, tabId } from '../../components/sms/SmsTabs';
import { SmsPendingTable } from '../../components/sms/SmsPendingTable';
import { fmtWhen } from '../../components/sms/smsFormat';

const PAGE_SIZE = 100;
const ID = 'sms-history';

type Tab = 'sent' | 'pending';

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  sent: { label: 'Wysłany', className: 'badge-green' },
  delivered: { label: 'Dostarczony', className: 'badge-teal' },
  failed: { label: 'Błąd', className: 'badge-red' },
  pending: { label: 'Oczekuje', className: 'badge-gray' },
};

function Pager({ offset, count, onOffset }: { offset: number; count: number; onOffset: (o: number) => void }) {
  return (
    <div className="sms-log-pagination">
      {offset > 0 && (
        <button type="button" className="refined-btn-secondary btn-press" onClick={() => onOffset(Math.max(0, offset - PAGE_SIZE))}>
          ← Poprzednie
        </button>
      )}
      {count === PAGE_SIZE && (
        <button type="button" className="refined-btn-secondary btn-press" onClick={() => onOffset(offset + PAGE_SIZE)}>
          Następne →
        </button>
      )}
    </div>
  );
}

/** Historia wysyłek SMS — ported from templates/settings/sms_log.html, now an expandable card with two
 * tabs: "Wysłane" (the original offset-paged log, 1:1) and "Oczekujące" (what the scheduler will still
 * send, with the exact tick that will carry each message). Both tabs show Warsaw wall-clock. */
export function SmsLogPage() {
  const [tab, setTab] = useState<Tab>('sent');
  const [offset, setOffset] = useState(0);
  const [pendingOffset, setPendingOffset] = useState(0);
  const logState = useApiData(() => smsSettingsApi.log(offset, PAGE_SIZE), [offset]);
  // Fetched on mount too (not only when the tab opens) so the tab can show its count.
  const pendingState = useApiData(() => smsSettingsApi.pending(pendingOffset, PAGE_SIZE), [pendingOffset]);
  const rows = logState.data?.rows ?? [];
  const pending = pendingState.data;
  // What will actually go out: rows the scheduler refuses (bad phone, deleted visit...) stay listed but do not count.
  const undeliverable = pending?.undeliverable ?? 0;       // `?? 0`: an older backend during a rolling deploy sends no such field
  const awaiting = pending ? pending.total - undeliverable : null;

  function changeTab(next: Tab) {
    setTab(next);
    if (next === 'pending') pendingState.reload(); // the queue moves every tick — never show a stale one
  }

  return (
    <div className="refined-page settings-page animate-fade-up">
      <header className="page-header sms-log-header">
        <Link to="/ustawienia/sms" className="settings-footer-link">
          ← Ustawienia SMS
        </Link>
        <h1 className="page-title">Historia wysyłek SMS</h1>
      </header>

      <details className="form-card sms-type-card sms-history-card" open>
        <summary className="sms-type-summary">
          Wysyłki SMS
          <span className="sms-history-meta">{awaiting != null ? `Oczekujące: ${awaiting}` : ''}</span>
        </summary>

        <SmsTabs<Tab>
          idPrefix={ID}
          ariaLabel="Historia i kolejka SMS"
          active={tab}
          onChange={changeTab}
          tabs={[
            { key: 'sent', label: 'Wysłane' },
            { key: 'pending', label: 'Oczekujące', count: awaiting },
          ]}
        />

        <div role="tabpanel" id={panelId(ID, 'sent')} aria-labelledby={tabId(ID, 'sent')} hidden={tab !== 'sent'}>
          <div className="table-container stack-cards-wrap">
            <table className="refined-table stack-cards">
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
                        <td className="cell-name" data-label="Data wysyłki">
                          {fmtWhen(r.sent_at)}
                        </td>
                        <td data-label="Typ SMS">{r.type_name || r.message_type_key}</td>
                        <td data-label="Klient">{r.client_name}</td>
                        <td className="mono" data-label="Telefon">
                          {r.phone_number}
                        </td>
                        <td data-label="Wizyta">
                          {r.appointment_date} {r.start_time?.slice(0, 5)}
                        </td>
                        <td data-label="Status">
                          <span className={`badge-pill ${status.className}`} title={r.status === 'failed' ? r.error_message ?? '' : undefined}>
                            {status.label}
                          </span>
                        </td>
                        <td className="mono" data-label="Twilio SID">
                          {r.twilio_sid || '—'}
                        </td>
                        <td data-label="Wysłał">{r.created_by_name || '—'}</td>
                        <td data-label="Potwierdzenie">
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
          <Pager offset={offset} count={rows.length} onOffset={setOffset} />
        </div>

        <div role="tabpanel" id={panelId(ID, 'pending')} aria-labelledby={tabId(ID, 'pending')} hidden={tab !== 'pending'}>
          {pendingState.error ? (
            <p className="sms-hint sms-hint--off">Nie udało się wczytać kolejki: {pendingState.error.message}</p>
          ) : pending && !pending.sms_active ? (
            <p className="sms-hint sms-hint--off">Wysyłanie SMS jest wyłączone w ustawieniach, więc harmonogram nic nie wyśle i kolejka jest pusta.</p>
          ) : (
            <p className="sms-hint">
              {pending?.estimated
                ? 'Czasy szacunkowe (~): ten serwer nie uruchamia harmonogramu, więc zaokrąglono je do pełnego kwadransa.'
                : pending?.next_tick_at
                  ? `Harmonogram wysyła co 15 minut. Najbliższy cykl: ${fmtWhen(pending.next_tick_at)}. „Zostanie wysłany” to cykl, który faktycznie zabierze wiadomość.`
                  : 'Wiadomości, które harmonogram jeszcze wyśle, najwcześniejsze na górze.'}
            </p>
          )}
          {pending && pending.sms_active && undeliverable > 0 && (
            <p className="sms-hint sms-hint--warn">
              {undeliverable} z {pending.total} pozycji (przekreślone) nie zostanie wysłanych: powód jest w kolumnie „Uwagi”, np. błędny numer telefonu klienta, który warto poprawić.
            </p>
          )}
          <SmsPendingTable rows={pending?.rows ?? []} loading={pendingState.loading && !pending} variant="history" />
          <Pager offset={pendingOffset} count={pending?.rows.length ?? 0} onOffset={setPendingOffset} />
        </div>
      </details>
    </div>
  );
}
