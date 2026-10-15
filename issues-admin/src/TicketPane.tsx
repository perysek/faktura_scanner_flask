import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { ClipboardEvent as ReactClipboardEvent, FormEvent } from 'react';
import { Button } from '@shared/components/ui/Button';
import { useToast } from '@shared/components/feedback/ToastProvider';
import { useAuth } from '@shared/contexts/AuthContext';
import { ApiError } from '@shared/lib/api/client';
import { Icon } from '@shared/lib/icons/Icon';
import { deskApi } from './api';
import type { Agent, Attachment, CloseReason, Message, Priority, Status, TicketDetail } from './api';
import { CANNED_REPLIES, CLOSE_REASON_LABEL, KIND_LABEL, PRIORITY_LABEL, STATUS_LABEL, personLabel } from './labels';
import { between, clock, dateTime, ago } from './time';
import { TechContext } from './TechContext';
import { DESK_MODULE } from './DeskGate';

const DETAIL_POLL_MS = 20_000;
const MAX_FILES = 3;

interface Props {
  id: number;
  agents: Agent[];
  onChanged: () => void;
  onBack: () => void;
  onOpenTicket: (id: number) => void;
}

/** "Anna zmieniła status: W toku → Rozwiązane" — the agent-side reading of a system row. */
function eventLine(m: Message, agents: Agent[]): string {
  const who = m.meta?.by === 'user' ? 'Użytkownik' : (m.author_name ?? 'System');
  if (m.event === 'status') {
    const from = STATUS_LABEL[m.meta?.from as Status] ?? m.meta?.from;
    const to = STATUS_LABEL[m.meta?.to as Status] ?? m.meta?.to;
    const reason = m.meta?.reason ? ` (${CLOSE_REASON_LABEL[m.meta.reason as CloseReason] ?? m.meta.reason})` : '';
    if (m.meta?.by === 'user' && m.meta?.to === 'closed') return 'Użytkownik potwierdził, że działa — zamknięte';
    if (m.meta?.by === 'user') return `Użytkownik odpisał — ${from} → ${to}`;
    return `${who} zmienił(a) status: ${from} → ${to}${reason}`;
  }
  if (m.event === 'priority') {
    return `${who} zmienił(a) priorytet: ${PRIORITY_LABEL[m.meta?.from as Priority] ?? m.meta?.from} → ${PRIORITY_LABEL[m.meta?.to as Priority] ?? m.meta?.to}`;
  }
  if (m.event === 'assigned') {
    const agent = agents.find((a) => a.id === m.meta?.to);
    return m.meta?.to ? `${who} przypisał(a) do: ${agent?.full_name ?? `#${m.meta.to}`}` : `${who} usunął(a) przypisanie`;
  }
  return who;
}

function Shots({ items, onOpen }: { items: Attachment[]; onOpen: (a: Attachment) => void }) {
  if (!items.length) return null;
  return (
    <span className="tk-shots">
      {items.map((a) => (
        <button key={a.id} type="button" className="tk-shot" onClick={() => onOpen(a)} title={`${a.filename} · ${a.width}×${a.height}`}>
          <img src={a.url} alt={a.filename} loading="lazy" />
        </button>
      ))}
    </span>
  );
}

export function TicketPane({ id, agents, onChanged, onBack, onOpenTicket }: Props) {
  const auth = useAuth();
  const toast = useToast();
  const canWrite = auth.hasModuleWrite(DESK_MODULE);
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'public' | 'internal'>('public');
  const [body, setBody] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [submitAs, setSubmitAs] = useState<Status | ''>('');
  const [closeReason, setCloseReason] = useState<CloseReason>('done');
  const [sending, setSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lightbox, setLightbox] = useState<Attachment | null>(null);
  const [tab, setTab] = useState<'details' | 'tech'>('details');
  const streamRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const lastCount = useRef(0);
  const onChangedRef = useRef(onChanged);
  onChangedRef.current = onChanged;

  const load = useCallback(
    async (notify = false) => {
      try {
        const data = await deskApi.get(id);
        setTicket(data.ticket);
        setError(null);
        if (notify) onChangedRef.current();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Nie udało się wczytać zgłoszenia');
      }
    },
    [id],
  );

  // Opening marks it read (and 'new' → 'seen') server-side: refresh the queue once.
  useEffect(() => {
    load(true);
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') load();
    }, DETAIL_POLL_MS);
    return () => window.clearInterval(timer);
  }, [load]);

  useLayoutEffect(() => {
    const count = ticket?.messages.length ?? 0;
    if (count !== lastCount.current && streamRef.current) streamRef.current.scrollTop = streamRef.current.scrollHeight;
    lastCount.current = count;
  }, [ticket]);

  useEffect(() => () => previews.forEach((url) => URL.revokeObjectURL(url)), [previews]);

  useEffect(() => {
    if (!lightbox) return undefined;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setLightbox(null);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [lightbox]);

  function addFiles(list: FileList | File[]) {
    const images = Array.from(list).filter((f) => /^image\/(png|jpeg|webp)$/.test(f.type));
    if (!images.length) {
      toast.warning('Dozwolone są obrazy PNG, JPG lub WebP');
      return;
    }
    const room = MAX_FILES - files.length;
    const take = images.slice(0, room);
    if (images.length > room) toast.warning(`Maksymalnie ${MAX_FILES} zdjęcia w jednej wiadomości`);
    setFiles((cur) => [...cur, ...take]);
    setPreviews((cur) => [...cur, ...take.map((f) => URL.createObjectURL(f))]);
  }

  function removeFile(index: number) {
    URL.revokeObjectURL(previews[index]);
    setFiles((cur) => cur.filter((_, i) => i !== index));
    setPreviews((cur) => cur.filter((_, i) => i !== index));
  }

  function onPaste(e: ReactClipboardEvent<HTMLTextAreaElement>) {
    const pasted = Array.from(e.clipboardData.files);
    if (pasted.length) {
      e.preventDefault();
      addFiles(pasted);
    }
  }

  async function send(event?: FormEvent) {
    event?.preventDefault();
    if (!ticket || sending) return;
    if (!body.trim() && !files.length) {
      textRef.current?.focus();
      return;
    }
    setSending(true);
    try {
      await deskApi.reply(
        ticket.id,
        {
          body: body.trim(),
          is_internal: mode === 'internal',
          status: mode === 'internal' ? '' : submitAs,
          close_reason: submitAs === 'closed' ? closeReason : '',
        },
        files,
      );
      setBody('');
      previews.forEach((url) => URL.revokeObjectURL(url));
      setFiles([]);
      setPreviews([]);
      setSubmitAs('');
      toast.success(mode === 'internal' ? 'Notatka zapisana' : 'Odpowiedź wysłana');
      await load(true);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się wysłać');
    } finally {
      setSending(false);
    }
  }

  async function update(patch: Parameters<typeof deskApi.update>[1], okText: string) {
    if (!ticket) return;
    setSaving(true);
    try {
      await deskApi.update(ticket.id, patch);
      toast.success(okText);
      await load(true);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się zapisać');
    } finally {
      setSaving(false);
    }
  }

  if (error) {
    return (
      <div className="desk-empty desk-empty--pane desk-empty--error">
        <p>{error}</p>
        <Button icon="arrow_back" onClick={onBack}>
          Wróć do listy
        </Button>
      </div>
    );
  }
  if (!ticket) {
    return (
      <div className="desk-empty desk-empty--pane" role="status">
        Wczytuję zgłoszenie…
      </div>
    );
  }

  const ctx = ticket.context ?? {};
  const isClosed = ticket.status === 'closed';

  return (
    <div className="tk">
      <header className="tk-head">
        <button type="button" className="desk-icon-btn tk-back" onClick={onBack} aria-label="Wróć do listy">
          <Icon name="arrow_back" size="1.25rem" />
        </button>
        <div className="tk-head-main">
          <h2 className="tk-title">
            <span className="desk-id">#{ticket.id}</span> {ticket.title}
          </h2>
          <p className="tk-sub">
            <span className={`desk-kind desk-kind--${ticket.kind}`}>
              <Icon name={ticket.kind === 'idea' ? 'lightbulb' : 'bug_report'} size="0.875rem" />
              {KIND_LABEL[ticket.kind]} · {ticket.area_label}
            </span>
            <span>
              od <strong>{personLabel(ticket.requester.name, ticket.requester.role)}</strong>
            </span>
            <span title={dateTime(ticket.created_at)}>{ago(ticket.created_at)}</span>
            {ctx.page?.url && (
              <span className="tk-sub-page" title="Strona, na której wysłano zgłoszenie">
                <Icon name="web" size="0.875rem" />
                {ctx.page.url}
              </span>
            )}
          </p>
        </div>
        <span className={`desk-status desk-status--${ticket.status} tk-head-status`}>{STATUS_LABEL[ticket.status]}</span>
      </header>

      <div className="tk-body">
        {/* ── conversation ─────────────────────────────── */}
        <div className="tk-convo">
          <div className="tk-stream scroll-thin" ref={streamRef}>
            {ticket.messages.map((m) => {
              if (m.author_kind === 'system') {
                return (
                  <p key={m.id} className="tk-event">
                    {eventLine(m, agents)} · {clock(m.created_at)}
                  </p>
                );
              }
              if (m.is_internal) {
                return (
                  <div key={m.id} className="tk-note">
                    <span className="tk-note-head">
                      <Icon name="sticky_note_2" size="0.875rem" /> Notatka wewnętrzna · {m.author_name} · {clock(m.created_at)}
                    </span>
                    {m.body && <p className="tk-text">{m.body}</p>}
                    <Shots items={m.attachments} onOpen={setLightbox} />
                  </div>
                );
              }
              const agent = m.author_kind === 'admin';
              return (
                <div key={m.id} className={`tk-msg${agent ? ' tk-msg--agent' : ''}`}>
                  <span className="tk-avatar" aria-hidden="true">
                    {(m.author_name ?? '?').slice(0, 1).toUpperCase()}
                  </span>
                  <div className="tk-bubble">
                    <span className="tk-bubble-head">
                      <strong>{m.author_name ?? 'Użytkownik'}</strong>
                      {agent && <span className="tk-agent-tag">obsługa</span>}
                      <span title={dateTime(m.created_at)}>{clock(m.created_at)}</span>
                    </span>
                    {m.body && <p className="tk-text">{m.body}</p>}
                    <Shots items={m.attachments} onOpen={setLightbox} />
                  </div>
                </div>
              );
            })}
          </div>

          {canWrite ? (
            <form className={`tk-composer tk-composer--${mode}`} onSubmit={send}>
              <div className="tk-composer-tabs" role="tablist" aria-label="Rodzaj wiadomości">
                <button type="button" role="tab" aria-selected={mode === 'public'} className={mode === 'public' ? 'is-on' : ''} onClick={() => setMode('public')}>
                  <Icon name="send" size="0.875rem" /> Odpowiedź do użytkownika
                </button>
                <button type="button" role="tab" aria-selected={mode === 'internal'} className={mode === 'internal' ? 'is-on' : ''} onClick={() => setMode('internal')}>
                  <Icon name="sticky_note_2" size="0.875rem" /> Notatka wewnętrzna
                </button>
                <select
                  className="form-select tk-canned"
                  value=""
                  aria-label="Wstaw szablon odpowiedzi"
                  onChange={(e) => {
                    const reply = CANNED_REPLIES[Number(e.target.value)];
                    if (reply) {
                      setBody((cur) => (cur ? `${cur.trimEnd()}\n\n${reply.text}` : reply.text));
                      textRef.current?.focus();
                    }
                  }}
                >
                  <option value="">Szablony…</option>
                  {CANNED_REPLIES.map((r, i) => (
                    <option key={r.label} value={i}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>
              <textarea
                ref={textRef}
                className="form-textarea tk-input"
                placeholder={
                  mode === 'internal'
                    ? 'Notatka widoczna tylko dla obsługi…'
                    : isClosed
                      ? 'Rozmowa zamknięta — odpowiedź jej nie otworzy, chyba że wybierzesz status poniżej'
                      : 'Napisz odpowiedź… (wklej zrzut ekranu: Ctrl+V)'
                }
                value={body}
                maxLength={5000}
                onChange={(e) => setBody(e.target.value)}
                onPaste={onPaste}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send();
                }}
              />
              {previews.length > 0 && (
                <ul className="ticket-photos">
                  {previews.map((url, i) => (
                    <li key={url} className="ticket-photo-chip">
                      <img className="ticket-shot-thumb" src={url} alt="" />
                      <span className="ticket-photo-name">{files[i]?.name}</span>
                      <button type="button" className="ticket-photo-remove" aria-label="Usuń zdjęcie" onClick={() => removeFile(i)}>
                        <Icon name="close" size="0.875rem" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <div className="tk-composer-foot">
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  multiple
                  hidden
                  onChange={(e) => {
                    if (e.target.files) addFiles(e.target.files);
                    e.target.value = '';
                  }}
                />
                <Button small variant="ghost" icon="attach_file" disabled={files.length >= MAX_FILES} onClick={() => fileRef.current?.click()}>
                  Zdjęcie
                </Button>
                <span className="tk-foot-spacer" />
                {mode === 'public' && (
                  <>
                    <label className="tk-submit-as">
                      <span>Wyślij jako</span>
                      <select className="form-select" value={submitAs} onChange={(e) => setSubmitAs(e.target.value as Status | '')}>
                        <option value="">{['new', 'seen'].includes(ticket.status) ? 'W toku (domyślnie)' : `${STATUS_LABEL[ticket.status]} (bez zmian)`}</option>
                        <option value="in_progress">W toku</option>
                        <option value="waiting_user">Czeka na użytkownika</option>
                        <option value="resolved">Rozwiązane</option>
                        <option value="closed">Zamknięte</option>
                      </select>
                    </label>
                    {submitAs === 'closed' && (
                      <select className="form-select" value={closeReason} onChange={(e) => setCloseReason(e.target.value as CloseReason)} aria-label="Powód zamknięcia">
                        {(['done', 'declined', 'duplicate'] as CloseReason[]).map((r) => (
                          <option key={r} value={r}>
                            {CLOSE_REASON_LABEL[r]}
                          </option>
                        ))}
                      </select>
                    )}
                  </>
                )}
                <Button type="submit" small variant="primary" icon={mode === 'internal' ? 'save' : 'send'} isLoading={sending} loadingText="Wysyłam…">
                  {mode === 'internal' ? 'Zapisz notatkę' : 'Wyślij'}
                </Button>
              </div>
            </form>
          ) : (
            <p className="tk-readonly">Masz dostęp tylko do odczytu — odpowiadanie wyłączone w Poziomach dostępu.</p>
          )}
        </div>

        {/* ── properties + technical context ───────────── */}
        <aside className="tk-side scroll-thin" aria-label="Szczegóły zgłoszenia">
          <div className="tk-side-tabs" role="tablist">
            <button type="button" role="tab" aria-selected={tab === 'details'} className={tab === 'details' ? 'is-on' : ''} onClick={() => setTab('details')}>
              Szczegóły
            </button>
            <button type="button" role="tab" aria-selected={tab === 'tech'} className={tab === 'tech' ? 'is-on' : ''} onClick={() => setTab('tech')}>
              Dane techniczne
              {(ctx.console?.length || ctx.network?.some((n) => !n.ok)) && <span className="tk-tech-dot" title="Są błędy w danych technicznych" />}
            </button>
          </div>

          {tab === 'details' ? (
            <>
              <section className="tk-card">
                <label className="tk-field">
                  <span>Status</span>
                  <select
                    className="form-select"
                    value={ticket.status}
                    disabled={!canWrite || saving}
                    onChange={(e) => {
                      const status = e.target.value as Status;
                      update(status === 'closed' ? { status, close_reason: 'done' } : { status }, `Status: ${STATUS_LABEL[status]}`);
                    }}
                  >
                    {ticket.status === 'new' && <option value="new">Nowe</option>}
                    {(['seen', 'in_progress', 'waiting_user', 'resolved', 'closed'] as Status[]).map((s) => (
                      <option key={s} value={s}>
                        {STATUS_LABEL[s]}
                      </option>
                    ))}
                  </select>
                </label>
                {isClosed && (
                  <label className="tk-field">
                    <span>Powód zamknięcia</span>
                    <select
                      className="form-select"
                      value={ticket.close_reason ?? 'done'}
                      disabled={!canWrite || saving || ticket.close_reason === 'confirmed'}
                      onChange={(e) => update({ status: 'closed', close_reason: e.target.value as CloseReason }, 'Zapisano powód')}
                    >
                      {ticket.close_reason === 'confirmed' && <option value="confirmed">{CLOSE_REASON_LABEL.confirmed}</option>}
                      {(['done', 'declined', 'duplicate'] as CloseReason[]).map((r) => (
                        <option key={r} value={r}>
                          {CLOSE_REASON_LABEL[r]}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label className="tk-field">
                  <span>Priorytet</span>
                  <select
                    className={`form-select tk-prio-select tk-prio-select--${ticket.priority}`}
                    value={ticket.priority}
                    disabled={!canWrite || saving}
                    onChange={(e) => update({ priority: e.target.value as Priority }, 'Zmieniono priorytet')}
                  >
                    {(['urgent', 'high', 'normal', 'low'] as Priority[]).map((p) => (
                      <option key={p} value={p}>
                        {PRIORITY_LABEL[p]}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="tk-field">
                  <span>Przypisane do</span>
                  <select
                    className="form-select"
                    value={ticket.assigned_to ?? ''}
                    disabled={!canWrite || saving}
                    onChange={(e) => update({ assigned_to: e.target.value ? Number(e.target.value) : null }, 'Zmieniono przypisanie')}
                  >
                    <option value="">— nikt —</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.full_name}
                        {a.id === auth.user?.id ? ' (ja)' : ''}
                      </option>
                    ))}
                  </select>
                </label>
                {canWrite && ticket.assigned_to !== auth.user?.id && auth.user && agents.some((a) => a.id === auth.user?.id) && (
                  <Button small variant="ghost" icon="person" disabled={saving} onClick={() => update({ assigned_to: auth.user!.id }, 'Przypisano do Ciebie')}>
                    Przypisz do mnie
                  </Button>
                )}
              </section>

              <section className="tk-card">
                <h3 className="tk-card-title">Zgłaszający</h3>
                <p className="tk-person">
                  <span className="tk-avatar" aria-hidden="true">
                    {(ticket.requester.name ?? '?').slice(0, 1).toUpperCase()}
                  </span>
                  <span>
                    <strong>{ticket.requester.name ?? 'Nieznany użytkownik'}</strong>
                    <span className="tk-muted">{ticket.requester.role_label ?? ticket.requester.role}</span>
                    {ticket.requester.email && (
                      <a className="tk-muted" href={`mailto:${ticket.requester.email}`}>
                        {ticket.requester.email}
                      </a>
                    )}
                  </span>
                </p>
                {ticket.requester_history.length > 0 && (
                  <>
                    <h4 className="tk-card-sub">Inne zgłoszenia tej osoby</h4>
                    <ul className="tk-history">
                      {ticket.requester_history.map((h) => (
                        <li key={h.id}>
                          <button type="button" onClick={() => onOpenTicket(h.id)}>
                            <span className="desk-id">#{h.id}</span> {h.title}
                          </button>
                          <span className={`desk-status desk-status--${h.status}`}>{STATUS_LABEL[h.status]}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </section>

              <section className="tk-card">
                <h3 className="tk-card-title">Oś czasu</h3>
                <dl className="tk-dl">
                  <dt>Utworzono</dt>
                  <dd>{dateTime(ticket.created_at)}</dd>
                  <dt>Pierwsza odpowiedź</dt>
                  <dd>{ticket.first_response_at ? `${dateTime(ticket.first_response_at)} (po ${between(ticket.created_at, ticket.first_response_at)})` : 'jeszcze nie'}</dd>
                  <dt>Ostatnio użytkownik</dt>
                  <dd>{dateTime(ticket.last_user_activity_at)}</dd>
                  {ticket.resolved_at && (
                    <>
                      <dt>Rozwiązano</dt>
                      <dd>
                        {dateTime(ticket.resolved_at)} (po {between(ticket.created_at, ticket.resolved_at)})
                      </dd>
                    </>
                  )}
                  {ticket.closed_at && (
                    <>
                      <dt>Zamknięto</dt>
                      <dd>{dateTime(ticket.closed_at)}</dd>
                    </>
                  )}
                </dl>
              </section>
            </>
          ) : (
            <TechContext ctx={ctx} />
          )}
        </aside>
      </div>

      {lightbox && (
        <div className="tk-lightbox" role="dialog" aria-modal="true" aria-label={lightbox.filename} onClick={() => setLightbox(null)}>
          <img src={lightbox.url} alt={lightbox.filename} onClick={(e) => e.stopPropagation()} />
          <div className="tk-lightbox-bar" onClick={(e) => e.stopPropagation()}>
            <span>
              {lightbox.filename} · {lightbox.width}×{lightbox.height} · {Math.round(lightbox.size_bytes / 1024)} KB
            </span>
            <a href={lightbox.url} target="_blank" rel="noreferrer" className="refined-btn-secondary refined-btn-sm">
              Otwórz w nowej karcie
            </a>
            <button type="button" className="refined-btn-secondary refined-btn-sm" onClick={() => setLightbox(null)}>
              Zamknij
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
