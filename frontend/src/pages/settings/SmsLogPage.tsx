import { useState } from 'react';
import { Link } from 'react-router-dom';
import './SettingsPages.css';
import { useApiData } from '../../lib/useApiData';
import { smsSettingsApi } from '../../lib/api/smsSettings';
import { SmsTabs, panelId, tabId } from '../../components/sms/SmsTabs';
import { SmsLogTable } from '../../components/sms/SmsLogTable';
import { SmsPendingTable } from '../../components/sms/SmsPendingTable';
import { MonthYearPicker } from '../../components/sms/MonthYearPicker';
import { TableScrollTop } from '../../components/sms/TableScrollTop';
import { currentMonthWarsaw, fmtWhen } from '../../components/sms/smsFormat';

const PAGE_SIZE = 100;
const ID = 'sms-history';

type Tab = 'sent' | 'pending';

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

/** Wysyłki SMS (was "Historia wysyłek SMS") — two tabs: "Wysłane" (what went out) and "Oczekujące" (what the
 * scheduler will still send, with the exact tick that will carry each message). Both show Warsaw wall-clock and
 * share one month picker: each table starts at the end of the picked month and runs back in time, newest first. */
export function SmsLogPage() {
  const [tab, setTab] = useState<Tab>('sent');
  const [month, setMonth] = useState(currentMonthWarsaw);
  const [offset, setOffset] = useState(0);
  const [pendingOffset, setPendingOffset] = useState(0);
  const logState = useApiData(() => smsSettingsApi.log(offset, PAGE_SIZE, month), [offset, month]);
  // Fetched on mount too (not only when the tab opens) so the tab can show its count.
  const pendingState = useApiData(() => smsSettingsApi.pending(pendingOffset, PAGE_SIZE, month, 'desc'), [pendingOffset, month]);
  const rows = logState.data?.rows ?? [];
  const pending = pendingState.data;
  // What will actually go out: rows the scheduler refuses (bad phone, deleted visit...) stay listed but do not count.
  const undeliverable = pending?.undeliverable ?? 0;       // `?? 0`: an older backend during a rolling deploy sends no such field
  const awaiting = pending ? pending.total - undeliverable : null;

  function changeTab(next: Tab) {
    setTab(next);
    if (next === 'pending') pendingState.reload(); // the queue moves every tick — never show a stale one
  }

  function changeMonth(next: string) {
    setMonth(next);
    setOffset(0);          // one batched render: both lists restart from their first page for the new month
    setPendingOffset(0);
  }

  return (
    <div className="refined-page settings-page sms-log-page animate-fade-up">
      <header className="page-header sms-log-header">
        <Link to="/ustawienia/sms" className="settings-footer-link">
          ← Ustawienia SMS
        </Link>
        <h1 className="page-title">Wysyłki SMS</h1>
      </header>

      <section className="form-card sms-history-card">
        <SmsTabs<Tab>
          idPrefix={ID}
          ariaLabel="Wysłane i oczekujące SMS"
          active={tab}
          onChange={changeTab}
          tabs={[
            { key: 'sent', label: 'Wysłane', count: logState.data?.total ?? null },
            { key: 'pending', label: 'Oczekujące', count: awaiting },
          ]}
          trailing={<MonthYearPicker value={month} onChange={changeMonth} />}
        />

        <div role="tabpanel" id={panelId(ID, 'sent')} aria-labelledby={tabId(ID, 'sent')} hidden={tab !== 'sent'}>
          <SmsLogTable rows={rows} loading={logState.loading && !logState.data} refreshing={logState.loading && !!logState.data} />
          <TableScrollTop />
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
                  ? `Harmonogram wysyła co 15 minut. Najbliższy cykl: ${fmtWhen(pending.next_tick_at)}. „Zaplanowany na” to cykl, który faktycznie zabierze wiadomość. Najnowsze na górze.`
                  : 'Wiadomości, które harmonogram jeszcze wyśle, najnowsze na górze.'}
            </p>
          )}
          {pending && pending.sms_active && undeliverable > 0 && (
            <p className="sms-hint sms-hint--warn">
              {undeliverable} z {pending.total} pozycji (przekreślone) nie zostanie wysłanych: powód widać pod numerem telefonu (np. „Nie zapisano”) albo w dymku nad przekreśloną datą. Warto poprawić numer klienta.
            </p>
          )}
          <SmsPendingTable
            rows={pending?.rows ?? []}
            loading={pendingState.loading && !pending}
            refreshing={pendingState.loading && !!pending}
            variant="history"
          />
          <TableScrollTop />
          <Pager offset={pendingOffset} count={pending?.rows.length ?? 0} onOffset={setPendingOffset} />
        </div>
      </section>
    </div>
  );
}
