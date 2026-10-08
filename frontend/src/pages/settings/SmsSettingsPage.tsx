import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import './SettingsPages.css';
import { useApiData } from '../../lib/useApiData';
import { smsSettingsApi, type MessageTypeCreateValues, type MessageTypeSaveValues } from '../../lib/api/smsSettings';
import { ApiError } from '../../lib/api/client';
import { planAccordion, playMotion, settlePanel, type PanelEls } from '../../lib/accordionMotion';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import type { SmsMessageType, SmsSettings, TriggerMode } from '../../types/settings';

const EMPTY_CREDS: SmsSettings = { account_sid: '', auth_token: '', from_number: '', messaging_service_sid: '', is_active: false };
const CREDS_FORM_ID = 'sms-creds-form';

/** Exhaustive on purpose: adding a TriggerMode without a label fails the build. */
const TRIGGER_MODE_LABELS: Record<TriggerMode, string> = {
  before_visit: 'Przed wizytą',
  on_status: 'Po zmianie statusu',
  manual: 'Ręcznie / przez system',
};

/** Older servers don't send trigger_mode; the legacy flag tells the two time-ish modes apart. */
function triggerModeOf(mt: SmsMessageType): TriggerMode {
  return mt.trigger_mode ?? (mt.is_event_triggered ? 'on_status' : 'before_visit');
}

function percent(numerator: number, denominator: number) {
  return denominator ? Math.round((numerator / denominator) * 100) : 0;
}

/** What a panel hands the page: its elements for the motion driver, and a way to save its draft now. */
type PanelHandle = PanelEls & { flush: () => Promise<void> };

const sameValues = (a: MessageTypeSaveValues, b: MessageTypeSaveValues) => JSON.stringify(a) === JSON.stringify(b);

interface MessageTypeCardProps {
  mt: SmsMessageType;
  open: boolean;
  onToggle: () => void;
  onSaved: () => void;
  onDeleted: () => void;
  register: (id: number, handle: PanelHandle | null) => void;
}

/** Message-type editor panel, one per row — mirrors the original's `<details>`-per-type layout
 * (templates/settings/sms.html), including the URL-placeholder checkbox → textarea wiring (checking
 * "include X link" appends the placeholder token if missing; unchecking strips it).
 *
 * Not a `<details>`: the page opens one panel at a time and animates height and page scroll off one
 * clock (lib/accordionMotion.ts), which `<details>` can't do. There is no Save button either — the
 * draft is saved, silently, when the panel hides (collapsed, replaced by another panel, or the page
 * left), or when the page's own "Zapisz" is pressed. */
function MessageTypeCard({ mt, open, onToggle, onSaved, onDeleted, register }: MessageTypeCardProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const [values, setValues] = useState<MessageTypeSaveValues>({
    name: mt.name,
    is_enabled: mt.is_enabled,
    send_hours_before: mt.send_hours_before,
    send_delay_minutes: mt.send_delay_minutes ?? 0,
    template_text: mt.template_text,
    include_confirm_link: mt.include_confirm_link,
    include_cancel_link: mt.include_cancel_link,
    include_rate_link: mt.include_rate_link,
    include_booking_link: mt.include_booking_link,
    send_only_if_confirmed: mt.send_only_if_confirmed,
  });

  const cardRef = useRef<HTMLElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const openAtMount = useRef(open);
  const latest = useRef(values);
  latest.current = values;
  const saved = useRef(values); // what the server holds, so only a changed draft is sent
  const deleted = useRef(false);
  const queue = useRef<Promise<void>>(Promise.resolve()); // saves go out one after another, never overlapping

  /** Silent: no success toast (the panel closing is the confirmation); a failure still says so. */
  const persist = useCallback((): Promise<void> => {
    queue.current = queue.current.then(async () => {
      const draft = latest.current;
      if (deleted.current || sameValues(draft, saved.current)) return;
      try {
        await smsSettingsApi.saveMessageType(mt.id, draft);
        saved.current = draft;
        onSaved();
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : `Nie udało się zapisać typu „${draft.name}”`);
      }
    });
    return queue.current;
  }, [mt.id, onSaved, toast]);
  const persistRef = useRef(persist);
  persistRef.current = persist;

  useLayoutEffect(() => {
    const card = cardRef.current;
    const body = bodyRef.current;
    const inner = innerRef.current;
    if (!card || !body || !inner) return;
    settlePanel(body, openAtMount.current); // from here on the motion driver owns the body's height
    register(mt.id, { card, body, inner, flush: () => persistRef.current() });
    return () => register(mt.id, null);
  }, [mt.id, register]);

  const wasOpen = useRef(open);
  useEffect(() => {
    if (wasOpen.current && !open) void persistRef.current();
    wasOpen.current = open;
  }, [open]);

  // Leaving the page with this panel still open must not eat the edit either.
  useEffect(
    () => () => {
      void persistRef.current();
    },
    [],
  );

  function toggleLink(field: 'include_confirm_link' | 'include_cancel_link' | 'include_booking_link' | 'include_rate_link', placeholder: string) {
    setValues((v) => {
      const next = !v[field];
      let template = v.template_text;
      if (next) {
        if (!template.includes(placeholder)) template = template.trimEnd() + '\n' + placeholder;
      } else {
        template = template
          .split(placeholder)
          .join('')
          .replace(/\n{3,}/g, '\n\n')
          .trimEnd();
      }
      return { ...v, [field]: next, template_text: template };
    });
  }

  async function handleDelete() {
    const ok = await confirm({
      title: 'Usuń typ wiadomości',
      message: 'Czy na pewno chcesz usunąć ten typ wiadomości? Tej operacji nie można cofnąć.',
      confirmText: 'Usuń',
    });
    if (!ok) return;
    deleted.current = true; // a draft left on this panel must not be saved into a type that is going away
    try {
      const result = await smsSettingsApi.deleteMessageType(mt.id);
      if (result.success) {
        toast.success('Typ wiadomości usunięty');
        onDeleted();
      } else {
        deleted.current = false;
        toast.error(result.message || 'Nie można usunąć tego typu wiadomości');
      }
    } catch (err) {
      deleted.current = false;
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  const charCount = values.template_text.length;
  const segments = Math.ceil(charCount / 160) || 1;
  const mode = triggerModeOf(mt);
  const timing =
    mode === 'on_status'
      ? `${mt.send_delay_minutes ?? 0}min po zmianie statusu`
      : mode === 'before_visit'
        ? `${mt.send_hours_before}h przed wizytą`
        : TRIGGER_MODE_LABELS.manual;
  const headId = `sms-type-head-${mt.id}`;
  const bodyId = `sms-type-body-${mt.id}`;

  return (
    <section className="form-card sms-acc-card" ref={cardRef}>
      <div className="sms-acc-head">
        <button type="button" id={headId} className="sms-acc-toggle" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
          <span className="sms-type-name">{mt.name}</span>
          <span className={`badge-pill ${mt.is_enabled ? 'badge-green' : 'badge-gray'}`}>{mt.is_enabled ? 'Aktywny' : 'Nieaktywny'}</span>
          <span className="badge-pill badge-gray" title="Kiedy ta wiadomość jest wysyłana">{TRIGGER_MODE_LABELS[mode]}</span>
          {mt.is_enabled && <span className="sms-type-timing">{timing}</span>}
        </button>
        {mt.is_custom && (
          <button type="button" className="sms-delete-type" title="Usuń typ wiadomości" aria-label="Usuń typ wiadomości" onClick={handleDelete}>
            ✕
          </button>
        )}
      </div>

      <div id={bodyId} ref={bodyRef} className="sms-acc-body" role="region" aria-labelledby={headId}>
        <div ref={innerRef} className="sms-acc-inner">
          <div className="form-field">
            <label className="form-label">Nazwa</label>
            <input
              className="form-input"
              value={values.name}
              readOnly={!mt.is_custom}
              onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))}
            />
          </div>

          {mode === 'manual' ? (
            <div className="form-field">
              <p className="form-helper-text">
                Ten SMS nie jest wysyłany o stałej porze przed wizytą. Wysyła go system w konkretnej sytuacji (np. tuż po rezerwacji online
                albo przy odwołaniu wizyty z powodu nieobecności pracownika) lub recepcja ręcznie — dlatego nie ma tu ustawienia „ile godzin przed”.
                Przełącznik poniżej decyduje, czy ten typ w ogóle może być użyty.
              </p>
            </div>
          ) : mode === 'on_status' ? (
            <div className="form-field">
              <label className="form-label">Opóźnienie wysyłki (minuty)</label>
              <input
                type="number"
                className="form-input"
                style={{ width: 120 }}
                min={0}
                max={1440}
                value={values.send_delay_minutes}
                onChange={(e) => setValues((v) => ({ ...v, send_delay_minutes: Number(e.target.value) || 0 }))}
              />
              <p className="form-helper-text">
                0 = natychmiast po zmianie statusu. Wyzwalacz: status <strong>{mt.trigger_on_status}</strong>
              </p>
            </div>
          ) : (
            <div className="form-field">
              <label className="form-label">Wyślij X godzin przed wizytą</label>
              <input
                type="number"
                className="form-input"
                style={{ width: 120 }}
                min={1}
                max={168}
                value={values.send_hours_before}
                onChange={(e) => setValues((v) => ({ ...v, send_hours_before: Number(e.target.value) || 1 }))}
              />
              <p className="form-helper-text">Zakres: 1h – 168h (7 dni)</p>
            </div>
          )}

          <div className="form-field">
            <label className="form-label">Treść wiadomości</label>
            <textarea className="form-textarea" rows={3} value={values.template_text} onChange={(e) => setValues((v) => ({ ...v, template_text: e.target.value }))} />
            <p className="form-helper-text" style={{ color: charCount > 160 ? 'var(--color-error)' : undefined }}>
              {charCount} znaków{segments > 1 ? ` (${segments} SMS)` : ''}
            </p>
          </div>

          <div className="checkbox-row">
            <div className="checkbox-wrapper">
              <input type="checkbox" className="refined-checkbox" id={`cl-${mt.id}`} checked={values.include_confirm_link} onChange={() => toggleLink('include_confirm_link', '{confirm_url}')} />
              <label className="checkbox-label" htmlFor={`cl-${mt.id}`}>
                Dołącz link potwierdzenia ({'{confirm_url}'})
              </label>
            </div>
            <div className="checkbox-wrapper">
              <input type="checkbox" className="refined-checkbox" id={`cxl-${mt.id}`} checked={values.include_cancel_link} onChange={() => toggleLink('include_cancel_link', '{cancel_url}')} />
              <label className="checkbox-label" htmlFor={`cxl-${mt.id}`}>
                Dołącz link anulowania ({'{cancel_url}'})
              </label>
            </div>
            <div className="checkbox-wrapper">
              <input type="checkbox" className="refined-checkbox" id={`bkl-${mt.id}`} checked={values.include_booking_link} onChange={() => toggleLink('include_booking_link', '{booking_url}')} />
              <label className="checkbox-label" htmlFor={`bkl-${mt.id}`}>
                Dołącz link do rezerwacji online ({'{booking_url}'})
              </label>
            </div>
            {mt.is_event_triggered && (
              <div className="checkbox-wrapper">
                <input type="checkbox" className="refined-checkbox" id={`rl-${mt.id}`} checked={values.include_rate_link} onChange={() => toggleLink('include_rate_link', '{rate_url}')} />
                <label className="checkbox-label" htmlFor={`rl-${mt.id}`}>
                  Dołącz link oceny wizyty ({'{rate_url}'})
                </label>
              </div>
            )}
            <div className="checkbox-wrapper">
              <input
                type="checkbox"
                className="refined-checkbox"
                id={`en-${mt.id}`}
                checked={values.is_enabled}
                onChange={(e) => setValues((v) => ({ ...v, is_enabled: e.target.checked }))}
              />
              <label className="checkbox-label" htmlFor={`en-${mt.id}`}>
                {mode === 'manual' ? 'Włącz ten typ (dostępny dla systemu i do wysyłki ręcznej)' : 'Włącz automatyczne wysyłanie'}
              </label>
            </div>
            <div className="checkbox-wrapper">
              <input
                type="checkbox"
                className="refined-checkbox"
                id={`soc-${mt.id}`}
                checked={values.send_only_if_confirmed}
                onChange={(e) => setValues((v) => ({ ...v, send_only_if_confirmed: e.target.checked }))}
              />
              <label className="checkbox-label" htmlFor={`soc-${mt.id}`}>
                Wysyłaj tylko jeżeli status <strong>Potwierdzona</strong>
              </label>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

type Period = 'mtd1' | 'prev';

/** Ustawienia SMS — Twilio credentials, stats, message-type templates.
 * Ported from templates/settings/sms.html + services/sms_service.py. New
 * `/api/sms/*` JSON endpoints (routes/sms_routes.py) added alongside the
 * original form-POST routes, which stay live for the Jinja page. */
export function SmsSettingsPage() {
  const toast = useToast();
  const bundleState = useApiData(() => smsSettingsApi.get(), []);
  const [period, setPeriod] = useState<Period>('mtd1');
  const [creds, setCreds] = useState<SmsSettings | null>(null);
  const [savingCreds, setSavingCreds] = useState(false);
  const [testTo, setTestTo] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [showToken, setShowToken] = useState(false);
  const [newType, setNewType] = useState<MessageTypeCreateValues>({
    name: '',
    send_hours_before: 24,
    template_text: '',
    include_confirm_link: false,
    include_cancel_link: false,
    include_booking_link: false,
  });
  const [creatingType, setCreatingType] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const panels = useRef(new Map<number, PanelHandle>());

  const registerPanel = useCallback((id: number, handle: PanelHandle | null) => {
    if (handle) panels.current.set(id, handle);
    else panels.current.delete(id);
  }, []);
  const togglePanel = useCallback((id: number) => setOpenId((current) => (current === id ? null : id)), []);

  // One panel open at a time. Whenever that changes, the panels' heights and the page scroll move on one
  // clock; the cleanup stops a motion the user interrupts, and the next plan resumes from where it stopped.
  useLayoutEffect(() => {
    const plan = planAccordion(panels.current, openId, window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    return plan ? playMotion(plan) : undefined;
  }, [openId]);

  const activeCreds = creds ?? bundleState.data?.settings ?? EMPTY_CREDS;
  const stats = bundleState.data?.stats;

  const statCards = useMemo(() => {
    if (!stats) return null;
    const get = (suffix: string) => stats[`${period}_${suffix}` as keyof typeof stats];
    const sent = get('sent');
    const failed = get('failed');
    const confirmRequests = get('confirm_requests');
    const confirmed = get('confirmed');
    const declined = get('declined');
    return [
      { label: 'Wysłane SMS', value: sent },
      { label: 'Nieudane', value: failed },
      { label: 'Prośby o potwierdzenie', value: confirmRequests },
      { label: 'Potwierdzenia', value: confirmed, sub: `${percent(confirmed, confirmRequests)}%` },
      { label: 'Odmowy', value: declined, sub: `${percent(declined, confirmRequests)}%` },
    ];
  }, [stats, period]);

  /** Both "Zapisz" buttons submit the credentials form. A panel left open with unsaved edits is saved too,
   * so the page has no state in which pressing Zapisz leaves a typed change behind. */
  async function handleSaveCreds(e: React.FormEvent) {
    e.preventDefault();
    setSavingCreds(true);
    try {
      await Promise.all([smsSettingsApi.saveCredentials(activeCreds), ...[...panels.current.values()].map((panel) => panel.flush())]);
      toast.success('Dane Twilio zapisane. Teraz SMS-y mają z czego latać.');
      setCreds(activeCreds);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu');
    } finally {
      setSavingCreds(false);
    }
  }

  async function handleTest() {
    if (!testTo.trim()) {
      setTestResult({ ok: false, text: 'Wpisz numer odbiorcy' });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const result = await smsSettingsApi.test({
        account_sid: activeCreds.account_sid ?? '',
        auth_token: activeCreds.auth_token ?? '',
        from_number: activeCreds.from_number ?? '',
        to_number: testTo.trim(),
        messaging_service_sid: activeCreds.messaging_service_sid || null,
      });
      setTestResult({ ok: result.success, text: result.success ? `✓ Wysłano — SID: ${result.result}` : `✗ Błąd: ${result.result}` });
    } catch (err) {
      setTestResult({ ok: false, text: err instanceof ApiError ? `✗ ${err.message}` : '✗ Błąd połączenia' });
    } finally {
      setTesting(false);
    }
  }

  async function handleCreateType() {
    if (!newType.name.trim()) {
      toast.error('Nazwa się sama nie wymyśli. Wpisz coś.');
      return;
    }
    setCreatingType(true);
    try {
      await smsSettingsApi.createMessageType(newType);
      toast.success('Nowy typ SMS-a na pokładzie.');
      setNewType({ name: '', send_hours_before: 24, template_text: '', include_confirm_link: false, include_cancel_link: false, include_booking_link: false });
      bundleState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd tworzenia');
    } finally {
      setCreatingType(false);
    }
  }

  const messageTypes = bundleState.data?.message_types ?? [];

  return (
    <div className="refined-page settings-page animate-fade-up">
      <header className="page-header sms-settings-header">
        <div>
          <h1 className="page-title">Ustawienia SMS</h1>
          <p className="page-subtitle">Konfiguracja Twilio i szablonów wiadomości SMS</p>
        </div>
        <div className="sms-header-actions">
          <ButtonLink to="/ustawienia/sms/historia" variant="primary">
            Lista SMS
          </ButtonLink>
          <Button type="submit" form={CREDS_FORM_ID} variant="primary" isLoading={savingCreds} loadingText="Zapisywanie…">
            Zapisz
          </Button>
        </div>
      </header>

      <div className="sms-stats-section">
        <div className="period-tabs">
          <button type="button" className={`period-tab${period === 'mtd1' ? ' active' : ''}`} onClick={() => setPeriod('mtd1')}>
            Bieżący miesiąc
          </button>
          <button type="button" className={`period-tab${period === 'prev' ? ' active' : ''}`} onClick={() => setPeriod('prev')}>
            Poprzedni miesiąc
          </button>
        </div>
        <div className="sms-stats-grid">
          {statCards?.map((s) => (
            <div className="stat-card" key={s.label}>
              <p className="stat-label">{s.label}</p>
              <p className="stat-value">{s.value ?? 0}</p>
              {s.sub && <p className="stat-sub">{s.sub}</p>}
            </div>
          ))}
        </div>
      </div>

      <form id={CREDS_FORM_ID} className="form-card" onSubmit={handleSaveCreds}>
        <h2 className="section-title">Dane dostępowe Twilio</h2>
        <div className="form-field">
          <label className="form-label">Account SID</label>
          <input
            className="form-input"
            placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            value={activeCreds.account_sid ?? ''}
            onChange={(e) => setCreds({ ...activeCreds, account_sid: e.target.value })}
          />
        </div>
        <div className="form-field">
          <label className="form-label">Auth Token</label>
          <div className="password-field">
            <input
              type={showToken ? 'text' : 'password'}
              className="form-input"
              placeholder="••••••••••••••••••••••••••••••••"
              value={activeCreds.auth_token ?? ''}
              onChange={(e) => setCreds({ ...activeCreds, auth_token: e.target.value })}
            />
            <button type="button" className="password-toggle" onClick={() => setShowToken((s) => !s)}>
              {showToken ? 'Ukryj' : 'Pokaż'}
            </button>
          </div>
        </div>
        <div className="form-field">
          <label className="form-label">Numer nadawcy</label>
          <input className="form-input" placeholder="+48XXXXXXXXX" value={activeCreds.from_number ?? ''} onChange={(e) => setCreds({ ...activeCreds, from_number: e.target.value })} />
          <p className="form-helper-text">Numer Twilio w formacie E.164. Używany gdy Messaging Service SID nie jest ustawiony.</p>
        </div>
        <div className="form-field">
          <label className="form-label">Messaging Service SID (opcjonalnie)</label>
          <input
            className="form-input"
            placeholder="MGxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            value={activeCreds.messaging_service_sid ?? ''}
            onChange={(e) => setCreds({ ...activeCreds, messaging_service_sid: e.target.value })}
          />
          <p className="form-helper-text">
            SID z konsoli Twilio → Messaging → Services. Jeśli ustawiony, <strong>ma pierwszeństwo</strong> przed numerem nadawcy i umożliwia wysyłkę z puli numerów (Copilot).
          </p>
        </div>
        <div className="checkbox-wrapper">
          <input
            type="checkbox"
            className="refined-checkbox"
            id="sms-active"
            checked={activeCreds.is_active}
            onChange={(e) => setCreds({ ...activeCreds, is_active: e.target.checked })}
          />
          <label className="checkbox-label" htmlFor="sms-active">
            Włącz wysyłanie SMS
          </label>
        </div>
      </form>

      <details className="form-card">
        <summary className="sms-type-summary">Test połączenia Twilio</summary>
        <div className="form-field">
          <label className="form-label">Numer testowy (odbiorcy)</label>
          <input className="form-input" placeholder="+48XXXXXXXXX" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
        </div>
        <div className="sms-test-row">
          <Button type="button" variant="secondary" isLoading={testing} loadingText="Wysyłanie…" onClick={handleTest}>
            Wyślij test
          </Button>
          {testResult && <span style={{ color: testResult.ok ? 'var(--color-success)' : 'var(--color-error)', fontSize: '0.8125rem' }}>{testResult.text}</span>}
        </div>
      </details>

      <h2 className="settings-subheading">Typy wiadomości SMS</h2>

      {/* Only the very first load replaces the list: a reload after a silent save must keep the panels mounted. */}
      {bundleState.loading && !bundleState.data ? (
        <p className="form-helper-text">Ładowanie…</p>
      ) : (
        messageTypes.map((mt) => (
          <MessageTypeCard
            key={mt.id}
            mt={mt}
            open={openId === mt.id}
            onToggle={() => togglePanel(mt.id)}
            onSaved={bundleState.reload}
            onDeleted={bundleState.reload}
            register={registerPanel}
          />
        ))
      )}

      <div className="variable-reference">
        <p className="var-ref-title">Dostępne zmienne w treści wiadomości:</p>
        {['{salon_name}', '{client_name}', '{date}', '{time}', '{employee_name}', '{services}', '{hours_before}', '{confirm_url}', '{cancel_url}', '{rate_url}', '{booking_url}'].map((v) => (
          <code key={v}>{v}</code>
        ))}
      </div>

      <details className="form-card" style={{ marginTop: '1rem' }}>
        <summary>+ Dodaj własny typ wiadomości</summary>
        <div className="form-field">
          <label className="form-label">
            Nazwa <span className="required-mark">*</span>
          </label>
          <input className="form-input" placeholder="np. Przypomnienie 3 dni" value={newType.name} onChange={(e) => setNewType((v) => ({ ...v, name: e.target.value }))} />
        </div>
        <div className="form-field">
          <label className="form-label">Wyślij X godzin przed wizytą</label>
          <input
            type="number"
            className="form-input"
            style={{ width: 120 }}
            min={1}
            max={168}
            value={newType.send_hours_before}
            onChange={(e) => setNewType((v) => ({ ...v, send_hours_before: Number(e.target.value) || 24 }))}
          />
        </div>
        <div className="form-field">
          <label className="form-label">Treść wiadomości</label>
          <textarea className="form-textarea" rows={3} value={newType.template_text} onChange={(e) => setNewType((v) => ({ ...v, template_text: e.target.value }))} />
        </div>
        <div className="checkbox-row">
          <div className="checkbox-wrapper">
            <input
              type="checkbox"
              className="refined-checkbox"
              id="new-cl"
              checked={newType.include_confirm_link}
              onChange={(e) => setNewType((v) => ({ ...v, include_confirm_link: e.target.checked }))}
            />
            <label className="checkbox-label" htmlFor="new-cl">
              Dołącz link potwierdzenia
            </label>
          </div>
          <div className="checkbox-wrapper">
            <input
              type="checkbox"
              className="refined-checkbox"
              id="new-cxl"
              checked={newType.include_cancel_link}
              onChange={(e) => setNewType((v) => ({ ...v, include_cancel_link: e.target.checked }))}
            />
            <label className="checkbox-label" htmlFor="new-cxl">
              Dołącz link anulowania
            </label>
          </div>
          <div className="checkbox-wrapper">
            <input
              type="checkbox"
              className="refined-checkbox"
              id="new-bkl"
              checked={newType.include_booking_link}
              onChange={(e) => setNewType((v) => ({ ...v, include_booking_link: e.target.checked }))}
            />
            <label className="checkbox-label" htmlFor="new-bkl">
              Dołącz link do rezerwacji online
            </label>
          </div>
        </div>
        <div className="form-actions">
          <Button variant="primary" isLoading={creatingType} loadingText="Dodawanie…" onClick={handleCreateType}>
            Dodaj typ
          </Button>
        </div>
      </details>

      <div className="settings-footer">
        <Button type="submit" form={CREDS_FORM_ID} variant="primary" isLoading={savingCreds} loadingText="Zapisywanie…">
          Zapisz
        </Button>
      </div>
    </div>
  );
}
