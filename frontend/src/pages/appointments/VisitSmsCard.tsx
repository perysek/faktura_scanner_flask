import { useEffect, useId, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useApiData } from '../../lib/useApiData';
import { visitSmsApi } from '../../lib/api/visitSms';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { SmsTabs, panelId, tabId } from '../../components/sms/SmsTabs';
import { SmsSentTable } from '../../components/sms/SmsSentTable';
import { SmsPendingTable } from '../../components/sms/SmsPendingTable';
import type { AppointmentStatus } from '../../types/appointment';
import type { SmsSendType } from '../../types/sms';
import '../../components/sms/sms.css';

type Tab = 'sent' | 'pending';

const ITEM = '[role="menuitem"]';

interface SendMenuProps {
  types: SmsSendType[];
  busy: boolean;
  onPick: (type: SmsSendType) => void;
}

/**
 * "Wyślij SMS" dropdown. A real menu: ArrowUp/Down/Home/End move, Escape closes and returns focus to the
 * trigger, Tab closes, a press outside closes. Types that cannot be sent right now stay in the list and
 * stay focusable (`aria-disabled`, not `disabled`) so the reason beside them can be read by everyone.
 */
function SendMenu({ types, busy, onPick }: SendMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    const menu = menuRef.current;
    (menu?.querySelector<HTMLElement>(`${ITEM}:not([aria-disabled="true"])`) ?? menu?.querySelector<HTMLElement>(ITEM))?.focus();
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  function closeAndRefocus() {
    setOpen(false);
    rootRef.current?.querySelector<HTMLElement>('button[aria-haspopup]')?.focus();
  }

  function onMenuKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeAndRefocus();
      return;
    }
    if (e.key === 'Tab') {
      setOpen(false);
      return;
    }
    const items = Array.from(menuRef.current?.querySelectorAll<HTMLElement>(ITEM) ?? []);
    if (items.length === 0) return;
    const at = items.indexOf(document.activeElement as HTMLElement);
    let next = -1;
    if (e.key === 'ArrowDown') next = at + 1 >= items.length ? 0 : at + 1;
    else if (e.key === 'ArrowUp') next = at <= 0 ? items.length - 1 : at - 1;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = items.length - 1;
    if (next < 0) return;
    e.preventDefault();
    items[next].focus();
  }

  return (
    <div className="sms-send" ref={rootRef}>
      <Button
        type="button"
        variant="secondary"
        icon="send"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        isLoading={busy}
        loadingText="Wysyłanie…"
        onClick={() => setOpen((o) => !o)}
      >
        Wyślij SMS
        <Icon name="expand_more" />
      </Button>

      {open && (
        <div ref={menuRef} id={menuId} role="menu" aria-label="Wyślij SMS" className="sms-send-menu" onKeyDown={onMenuKeyDown}>
          {types.length === 0 ? (
            <p className="sms-send-empty">Brak włączonych typów wiadomości.</p>
          ) : (
            types.map((t) => (
              <button
                key={t.type_key}
                type="button"
                role="menuitem"
                className="sms-send-item"
                aria-disabled={!t.available || undefined}
                title={t.reason ?? undefined}
                onClick={() => {
                  if (!t.available) return;
                  setOpen(false);
                  onPick(t);
                }}
              >
                <span>
                  {t.name}
                  {t.already_sent && <span className="sms-sent-badge">Wysłano</span>}
                </span>
                {!t.available && t.reason && <span className="sms-send-item-reason">{t.reason}</span>}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export interface VisitSmsCardProps {
  appointmentId: number;
  appointmentStatus: AppointmentStatus;
  clientName: string | null;
  /** Called after a send attempt so the page can refresh the timeline that lists the message. */
  onSent: () => void;
}

/**
 * "Wiadomości SMS" on the visit page: what was sent ("Wysłane"), what the scheduler will still send and
 * on which tick ("Do wysłania"), and the manual "Wyślij SMS" dropdown (roles with `can_send_sms` only).
 * Refetches when the visit's status changes — confirming a visit is what puts the "only confirmed"
 * reminder into the queue — and keeps showing the previous answer while it does.
 */
export function VisitSmsCard({ appointmentId, appointmentStatus, clientName, onSent }: VisitSmsCardProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const idPrefix = useId();
  const [tab, setTab] = useState<Tab>('sent');
  const [busy, setBusy] = useState(false);
  const state = useApiData(() => visitSmsApi.overview(appointmentId), [appointmentId, appointmentStatus]);
  const data = state.data;

  async function handlePick(type: SmsSendType) {
    const ok = await confirm({
      title: 'Wyślij SMS',
      message:
        `Wysłać wiadomość „${type.name}” do klienta${clientName ? ` ${clientName}` : ''}? SMS pójdzie od razu i trafi do historii wizyty.` +
        (type.already_sent ? ' Uwaga: ten typ SMS został już wysłany do tej wizyty.' : ''),
      confirmText: 'Wyślij SMS',
      type: type.already_sent ? 'warning' : 'info',
    });
    if (!ok) return;
    setBusy(true);
    let sent = false;
    try {
      await visitSmsApi.send(appointmentId, type.type_key);
      sent = true;
      toast.success(`SMS „${type.name}” wysłany`);
    } catch (err) {
      // /api/sms/send explains a refusal in `message`; ApiError.message only reads `error`.
      const body = err instanceof ApiError ? (err.data as { message?: string } | undefined) : undefined;
      toast.error(body?.message || (err instanceof Error ? err.message : 'Nie udało się wysłać SMS'));
    } finally {
      setBusy(false);
      state.reload(); // a failed attempt can still have logged a row
      onSent();
      if (sent) setTab('sent');
    }
  }

  if (!data) {
    return (
      <div className="form-card">
        <h3 className="card-title">Wiadomości SMS</h3>
        {state.error ? (
          <p className="empty-text" style={{ color: 'var(--color-error)' }}>
            Błąd ładowania wiadomości SMS: {state.error.message}
          </p>
        ) : (
          <p className="empty-text">Ładowanie...</p>
        )}
      </div>
    );
  }

  const pendingEmpty = !data.sms_active ? 'Wysyłanie SMS jest wyłączone' : 'Brak oczekujących wiadomości SMS dla tej wizyty';

  return (
    <div className="form-card" aria-busy={state.loading || undefined}>
      <div className="sms-card-head">
        <h3 className="card-title">Wiadomości SMS</h3>
        {data.can_send && <SendMenu types={data.send_types} busy={busy} onPick={handlePick} />}
      </div>

      {!data.sms_active && (
        <p className="sms-hint sms-hint--off">Wysyłanie SMS jest wyłączone w ustawieniach: harmonogram nic nie wyśle, a ręczna wysyłka jest niedostępna.</p>
      )}

      <SmsTabs<Tab>
        idPrefix={idPrefix}
        ariaLabel="Wiadomości SMS tej wizyty"
        active={tab}
        onChange={setTab}
        tabs={[
          { key: 'sent', label: 'Wysłane', count: data.sent.length },
          { key: 'pending', label: 'Do wysłania', count: data.pending.length },
        ]}
      />

      <div role="tabpanel" id={panelId(idPrefix, 'sent')} aria-labelledby={tabId(idPrefix, 'sent')} hidden={tab !== 'sent'}>
        <SmsSentTable rows={data.sent} />
      </div>

      <div role="tabpanel" id={panelId(idPrefix, 'pending')} aria-labelledby={tabId(idPrefix, 'pending')} hidden={tab !== 'pending'}>
        {data.sms_active && data.pending.length > 0 && (
          <p className="sms-hint">
            {data.pending_estimated
              ? 'Czasy szacunkowe (~): ten serwer nie uruchamia harmonogramu, więc zaokrąglono je do pełnego kwadransa.'
              : 'Harmonogram wysyła co 15 minut. „Zostanie wysłany” to cykl, który faktycznie zabierze wiadomość.'}
          </p>
        )}
        <SmsPendingTable rows={data.pending} variant="visit" emptyText={pendingEmpty} />
      </div>

      {state.error && (
        <p className="empty-text" style={{ color: 'var(--color-error)' }}>
          Nie udało się odświeżyć wiadomości SMS: {state.error.message}
        </p>
      )}
    </div>
  );
}
