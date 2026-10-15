import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { FormEvent, MouseEvent as ReactMouseEvent } from 'react';
import { ApiError } from '../../lib/api/client';
import { supportApi, USER_STATUS } from '../../lib/api/support';
import type { TicketMessage, TicketSummary, TicketThread } from '../../lib/api/support';
import { Icon } from '../../lib/icons/Icon';
import { Button } from '../ui/Button';

/**
 * "Twoje rozmowy" — the sender's side of the conversation with the administrator,
 * inside the phone button's pop-out (plan 261013 §2 + §4): a list of their tickets,
 * then a Messenger-style thread with a reply box. Replies can carry the same
 * 'Zaznacz miejsce' screenshots as a new ticket (the picker lives in the modal).
 */

const THREAD_POLL_MS = 15_000;

function when(iso: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  const time = date.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
  if (sameDay) return time;
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return `wczoraj ${time}`;
  return `${date.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })} ${time}`;
}

const CLOSE_REASON_TEXT: Record<string, string> = {
  confirmed: 'Potwierdzone — działa. Dzięki!',
  declined: 'Nie tym razem 🙏 — wyjaśnienie znajdziesz wyżej.',
  duplicate: 'Połączyliśmy to z Twoją wcześniejszą wiadomością.',
  done: 'Rozmowa zakończona.',
};

/** One grey centred line for a system event (status change only — the rest is admin bookkeeping). */
function eventText(message: TicketMessage): string | null {
  if (message.event !== 'status' || !message.meta?.to) return null;
  const to = message.meta.to as keyof typeof USER_STATUS;
  if (to === 'closed') return CLOSE_REASON_TEXT[message.meta.reason ?? 'done'] ?? 'Rozmowa zakończona.';
  if (to === 'in_progress' && message.meta.by === 'user') return 'Rozmowa wznowiona';
  return USER_STATUS[to] ? `${USER_STATUS[to].label}` : null;
}

export interface ReplyShots {
  files: File[];
  urls: string[];
  full: boolean;
  onPick: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  onRemove: (index: number) => void;
  onClear: () => void;
}

// ── list ──────────────────────────────────────────────────────────────────

export function ConversationList({ onOpen, onNew }: { onOpen: (id: number) => void; onNew: () => void }) {
  const [tickets, setTickets] = useState<TicketSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    supportApi
      .list()
      .then((data) => alive && setTickets(data.tickets))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : 'Nie udało się wczytać rozmów'));
    return () => {
      alive = false;
    };
  }, []);

  if (error) return <p className="convo-empty convo-empty--error">{error}</p>;
  if (!tickets) return <p className="convo-empty">Wczytuję…</p>;
  if (tickets.length === 0) {
    return (
      <div className="convo-empty">
        <p>Nie masz jeszcze żadnych rozmów. Coś nie działa albo masz pomysł? Napisz — czytamy wszystko.</p>
        <Button variant="primary" icon="forward_to_inbox" onClick={onNew}>
          Napisz do nas
        </Button>
      </div>
    );
  }
  return (
    <ul className="convo-list" aria-label="Twoje rozmowy">
      {tickets.map((t) => {
        const status = USER_STATUS[t.status];
        return (
          <li key={t.id}>
            <button type="button" className={`convo-item${t.unread ? ' convo-item--unread' : ''}`} onClick={() => onOpen(t.id)}>
              <span className={`convo-kind convo-kind--${t.kind}`} aria-hidden="true">
                <Icon name={t.kind === 'idea' ? 'lightbulb' : 'bug_report'} size="1.125rem" />
              </span>
              <span className="convo-item-main">
                <span className="convo-item-title">{t.title}</span>
                <span className={`convo-status convo-status--${status.tone}`}>{status.label}</span>
                {t.last_body && (
                  <span className="convo-item-last">
                    {t.last_author_kind === 'admin' ? 'Administrator: ' : 'Ty: '}
                    {t.last_body}
                  </span>
                )}
              </span>
              <span className="convo-item-side">
                <span className="convo-item-time">{when(t.last_message_at ?? t.updated_at)}</span>
                {t.unread && <span className="convo-dot" aria-label="Nowa odpowiedź" />}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

// ── thread ────────────────────────────────────────────────────────────────

export function ConversationThread({
  id,
  shots,
  onLoaded,
  onNew,
}: {
  id: number;
  shots: ReplyShots;
  onLoaded: (ticket: TicketThread) => void;
  onNew: () => void;
}) {
  const [ticket, setTicket] = useState<TicketThread | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const replyRef = useRef<HTMLTextAreaElement>(null);
  const lastCount = useRef(0);
  const onLoadedRef = useRef(onLoaded);
  onLoadedRef.current = onLoaded;

  const load = useCallback(async () => {
    try {
      const data = await supportApi.get(id);
      setTicket(data.ticket);
      setError(null);
      onLoadedRef.current(data.ticket);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Nie udało się wczytać rozmowy');
    }
  }, [id]);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, THREAD_POLL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  // Newest message in view whenever the thread grows.
  useLayoutEffect(() => {
    const count = ticket?.messages.length ?? 0;
    if (count !== lastCount.current && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    lastCount.current = count;
  }, [ticket]);

  async function send(event?: FormEvent) {
    event?.preventDefault();
    if (!reply.trim() && shots.files.length === 0) {
      setSendError('Napisz wiadomość');
      replyRef.current?.focus();
      return;
    }
    setSending(true);
    setSendError(null);
    try {
      await supportApi.reply(id, reply.trim(), shots.files);
      setReply('');
      shots.onClear();
      await load();
    } catch (err) {
      setSendError(err instanceof ApiError ? err.message : 'Nie udało się wysłać');
    } finally {
      setSending(false);
    }
  }

  async function confirm() {
    setSending(true);
    try {
      await supportApi.confirm(id);
      await load();
    } catch (err) {
      setSendError(err instanceof ApiError ? err.message : 'Nie udało się zapisać');
    } finally {
      setSending(false);
    }
  }

  if (error) return <p className="convo-empty convo-empty--error">{error}</p>;
  if (!ticket) return <p className="convo-empty">Wczytuję…</p>;

  const resolved = ticket.status === 'resolved';

  return (
    <div className="convo-thread">
      <div className="convo-messages" ref={scrollRef}>
        {ticket.messages.map((m) => {
          if (m.author_kind === 'system') {
            const text = eventText(m);
            return text ? (
              <p key={m.id} className="convo-event">
                {text} · {when(m.created_at)}
              </p>
            ) : null;
          }
          const mine = m.author_kind === 'user';
          return (
            <div key={m.id} className={`convo-bubble-row${mine ? ' convo-bubble-row--mine' : ''}`}>
              <div className={`convo-bubble${mine ? ' convo-bubble--mine' : ' convo-bubble--admin'}`}>
                {!mine && <span className="convo-bubble-author">Administrator{m.author_name ? ` · ${m.author_name}` : ''}</span>}
                {m.body && <p className="convo-bubble-text">{m.body}</p>}
                {m.attachments.length > 0 && (
                  <span className="convo-bubble-shots">
                    {m.attachments.map((a) => (
                      <a key={a.id} href={a.url} target="_blank" rel="noreferrer" title="Otwórz zdjęcie">
                        <img src={a.url} alt={`Zdjęcie: ${a.filename}`} loading="lazy" />
                      </a>
                    ))}
                  </span>
                )}
                <span className="convo-bubble-time">{when(m.created_at)}</span>
              </div>
            </div>
          );
        })}
      </div>

      {!ticket.can_reply ? (
        <div className="convo-closed">
          <p>Ta rozmowa jest zamknięta — napisz nową wiadomość.</p>
          <Button variant="primary" icon="forward_to_inbox" onClick={onNew}>
            Nowa wiadomość
          </Button>
        </div>
      ) : (
        <form className="convo-reply" onSubmit={send}>
          {resolved && (
            <div className="convo-resolved">
              <span>Sprawdź, czy już działa:</span>
              <Button small variant="primary" icon="check_circle" onClick={confirm} disabled={sending}>
                Działa
              </Button>
              <Button small onClick={() => replyRef.current?.focus()} disabled={sending}>
                Nadal nie działa
              </Button>
            </div>
          )}
          {shots.urls.length > 0 && (
            <ul className="ticket-photos" aria-label="Zaznaczone miejsca">
              {shots.urls.map((url, index) => (
                <li key={url} className="ticket-photo-chip">
                  <img className="ticket-shot-thumb" src={url} alt="" />
                  <span className="ticket-photo-name">Zaznaczenie {index + 1}</span>
                  <button type="button" className="ticket-photo-remove" aria-label={`Usuń zaznaczenie ${index + 1}`} onClick={() => shots.onRemove(index)}>
                    <Icon name="close" size="0.875rem" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <label htmlFor="convo-reply-text" className="sr-only">
            Twoja odpowiedź
          </label>
          <textarea
            id="convo-reply-text"
            ref={replyRef}
            className={`form-textarea convo-reply-text${sendError ? ' error' : ''}`}
            placeholder={ticket.status === 'closed' ? 'Napisz, jeśli coś nadal nie działa — wznowimy rozmowę' : 'Napisz odpowiedź…'}
            value={reply}
            rows={2}
            maxLength={5000}
            onChange={(e) => {
              setReply(e.target.value);
              if (sendError) setSendError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send();
            }}
          />
          <div className="convo-reply-actions">
            {sendError ? (
              <p className="ticket-shot-hint ticket-shot-hint--error" role="alert">
                {sendError}
              </p>
            ) : (
              <span />
            )}
            <Button
              small
              icon="center_focus_weak"
              disabled={shots.full || sending}
              title={shots.full ? 'Maksymalnie 3 zaznaczenia' : 'Pokaż na ekranie, o które miejsce chodzi'}
              onClick={shots.onPick}
            >
              Zaznacz miejsce
            </Button>
            <Button small type="submit" variant="primary" icon="send" isLoading={sending} loadingText="Wysyłam…">
              Wyślij
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
