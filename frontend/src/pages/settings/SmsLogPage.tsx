import { useState } from 'react';
import { Link } from 'react-router-dom';
import './SettingsPages.css';
import { useApiData } from '../../lib/useApiData';
import { smsSettingsApi } from '../../lib/api/smsSettings';
import { SmsTabs, panelId, tabId } from '../../components/sms/SmsTabs';
import { SmsLogTable } from '../../components/sms/SmsLogTable';
import { SmsPendingTable } from '../../components/sms/SmsPendingTable';
import { MonthYearPicker } from '../../components/sms/MonthYearPicker';
import { SmsMonthCost } from '../../components/sms/SmsMonthCost';
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
 * scheduler will still send, with the exact tick that will carry each message). Both show Warsaw wall-clock.
 * The one month picker belongs to the ACTIVE tab: each tab remembers its own month (and page) while you switch
 * back and forth, and each list is cut off at the end of its month.
 *   Wysłane:    newest first; nothing is ever sent in the future, so months after the current one cannot be picked.
 *   Oczekujące: soonest first; nothing is queued in the past, so months before the current one cannot be picked. */
export function SmsLogPage() {
  const [tab, setTab] = useState<Tab>('sent');
  const thisMonth = currentMonthWarsaw();
  const [sentPicked, setSentPicked] = useState(thisMonth);
  const [pendingPicked, setPendingPicked] = useState(thisMonth);
  // Clamped on read: a page left open over a month change must not keep a month the picker no longer allows.
  const sentMonth = sentPicked > thisMonth ? thisMonth : sentPicked;
  const pendingMonth = pendingPicked < thisMonth ? thisMonth : pendingPicked;
  const [offset, setOffset] = useState(0);
  const [pendingOffset, setPendingOffset] = useState(0);
  const logState = useApiData(() => smsSettingsApi.log(offset, PAGE_SIZE, sentMonth), [offset, sentMonth]);
  // Fetched on mount too (not only when the tab opens) so the tab can show its count.
  const pendingState = useApiData(() => smsSettingsApi.pending(pendingOffset, PAGE_SIZE, pendingMonth, 'asc'), [pendingOffset, pendingMonth]);
  const rows = logState.data?.rows ?? [];
  const pending = pendingState.data;
  // What will actually go out: rows the scheduler refuses (bad phone, deleted visit...) stay listed but do not count.
  const undeliverable = pending?.undeliverable ?? 0;       // `?? 0`: an older backend during a rolling deploy sends no such field
  const awaiting = pending ? pending.total - undeliverable : null;

  function changeTab(next: Tab) {
    setTab(next);
    if (next === 'pending') pendingState.reload(); // the queue moves every tick — never show a stale one
  }

  function changeSentMonth(next: string) {
    setSentPicked(next);
    setOffset(0);          // one batched render: the list restarts from its first page for the new month
  }

  function changePendingMonth(next: string) {
    setPendingPicked(next);
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
          trailing={
            // `key` remounts the picker per tab, so an open calendar never carries one tab's year into the other.
            tab === 'sent' ? (
              <MonthYearPicker key="sent" value={sentMonth} onChange={changeSentMonth} max={thisMonth} />
            ) : (
              <MonthYearPicker key="pending" value={pendingMonth} onChange={changePendingMonth} min={thisMonth} />
            )
          }
        />

        <div role="tabpanel" id={panelId(ID, 'sent')} aria-labelledby={tabId(ID, 'sent')} hidden={tab !== 'sent'}>
          <SmsMonthCost month={sentMonth} kind="sent" />
          <SmsLogTable rows={rows} loading={logState.loading && !logState.data} refreshing={logState.loading && !!logState.data} />
          <TableScrollTop />
          <Pager offset={offset} count={rows.length} onOffset={setOffset} />
        </div>

        <div role="tabpanel" id={panelId(ID, 'pending')} aria-labelledby={tabId(ID, 'pending')} hidden={tab !== 'pending'}>
          <SmsMonthCost month={pendingMonth} kind="pending" />
          {pendingState.error ? (
            <p className="sms-hint sms-hint--off">Nie udało się wczytać kolejki: {pendingState.error.message}</p>
          ) : pending && !pending.sms_active ? (
            <p className="sms-hint sms-hint--off">Wysyłanie SMS jest wyłączone w ustawieniach, więc harmonogram nic nie wyśle i kolejka jest pusta.</p>
          ) : (
            <p className="sms-hint">
              {pending?.estimated
                ? 'Czasy szacunkowe (~): ten serwer nie uruchamia harmonogramu, więc zaokrąglono je do pełnego kwadransa.'
                : pending?.next_tick_at
                  ? `Harmonogram wysyła co 15 minut. Najbliższy cykl: ${fmtWhen(pending.next_tick_at)}. „Zaplanowany na” to cykl, który faktycznie zabierze wiadomość. Najbliższe na górze.`
                  : 'Wiadomości, które harmonogram jeszcze wyśle, najbliższe na górze.'}
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
