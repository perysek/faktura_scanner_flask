import { useEffect, useState } from 'react';
import './AbsencesPages.css';
import { absencesApi } from '../../lib/api/absences';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Icon } from '../../lib/icons/Icon';
import { useHideOnScroll } from '../../lib/useHideOnScroll';
import { useIsMobile } from '../appointments/MobileWizytyCalendarView';
import type { AbsenceCategory, AbsenceRecord, AbsenceSupervisor } from '../../types/absence';

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  pending: { label: 'Oczekujący', className: 'ab-status--pending' },
  approved: { label: 'Zatwierdzony', className: 'ab-status--approved' },
  rejected: { label: 'Odrzucony', className: 'ab-status--rejected' },
  cancelled: { label: 'Anulowany', className: 'ab-status--cancelled' },
};

function formatPeriod(a: AbsenceRecord) {
  if (a.time_from) return `${a.date_from}, ${a.time_from}–${a.time_to}`;
  if (a.date_from === a.date_to) return a.date_from;
  return `${a.date_from} – ${a.date_to}`;
}

// Hardcoded, not Intl: the phone cards must read the same on every device
// locale, and Intl's short-month output differs between engines.
const MONTHS_SHORT = ['sty', 'lut', 'mar', 'kwi', 'maj', 'cze', 'lip', 'sie', 'wrz', 'paź', 'lis', 'gru'];

function parseYmd(ymd: string) {
  const [y, m, d] = ymd.split('-').map(Number);
  return { y, m, d };
}

/** "12–16 paź 2026", "28 wrz – 3 paź 2026", "5 paź 2026, 14:00–16:30" — the
 * phone card's headline, so it has to be scannable at a glance. */
function formatPeriodPhone(a: AbsenceRecord) {
  const from = parseYmd(a.date_from);
  const to = parseYmd(a.date_to);
  const day = (p: typeof from, withYear: boolean) => `${p.d} ${MONTHS_SHORT[p.m - 1]}${withYear ? ` ${p.y}` : ''}`;
  if (a.time_from) return `${day(from, true)}, ${a.time_from}–${a.time_to}`;
  if (a.date_from === a.date_to) return day(from, true);
  if (from.y === to.y && from.m === to.m) return `${from.d}–${to.d} ${MONTHS_SHORT[to.m - 1]} ${to.y}`;
  if (from.y === to.y) return `${day(from, false)} – ${day(to, true)}`;
  return `${day(from, true)} – ${day(to, true)}`;
}

/** "1 paź, 08:14" (year only when it isn't the current one). */
function formatRequestedPhone(ts: string | null) {
  if (!ts) return '—';
  const { y, m, d } = parseYmd(ts.slice(0, 10));
  const year = y === new Date().getFullYear() ? '' : ` ${y}`;
  return `${d} ${MONTHS_SHORT[m - 1]}${year}, ${ts.slice(11, 16)}`;
}

/** Moje nieobecności — self-service request form + history. Ported from
 * templates/absences/my.html + static/js/absences.js's initSubmitForm/
 * initPreviewConflicts. New /api/my-absences* JSON endpoints
 * (routes/absence_routes.py) added alongside the original form-POST routes.
 * The pre-submit conflict preview is simplified to a confirm summary instead
 * of the original's full table modal — same non-blocking behavior, lighter
 * UI (no new bespoke modal component for a purely informational step).
 *
 * Phone (≤640px) is history-first: most visits are "what happened to my
 * request?", filing is the rare task. So the phone view is a status-first card
 * list + a sticky "Nowy wniosek" bar, and the form opens in a bottom sheet
 * (same shape as Użytkownicy/Pracownicy). Desktop keeps the inline form card +
 * table. The form is rendered ONCE (JS-gated, not CSS-hidden) because its
 * field ids would collide if it existed twice in the DOM. */
export function MyAbsencesPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const isMobile = useIsMobile(640);
  const ctaHidden = useHideOnScroll();
  const [absences, setAbsences] = useState<AbsenceRecord[]>([]);
  const [categories, setCategories] = useState<AbsenceCategory[]>([]);
  const [supervisors, setSupervisors] = useState<AbsenceSupervisor[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);

  const [categoryId, setCategoryId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [timeFrom, setTimeFrom] = useState('');
  const [timeTo, setTimeTo] = useState('');
  const [approverId, setApproverId] = useState('');
  const [notes, setNotes] = useState('');

  function reload() {
    setLoading(true);
    absencesApi
      .myAbsences()
      .then((r) => {
        setAbsences(r.absences);
        setCategories(r.categories);
        setSupervisors(r.supervisors);
      })
      .finally(() => setLoading(false));
  }

  useEffect(reload, []);

  // Only the very first fetch blanks the list; a reload after cancel/submit
  // keeps the rows on screen instead of flashing "Ładowanie…" and jumping scroll.
  const initialLoad = loading && absences.length === 0;
  const cannotFile = !loading && supervisors.length === 0;

  const selectedCategory = categories.find((c) => String(c.id) === categoryId);
  const isFullDay = !selectedCategory || selectedCategory.absence_full_day;

  function resetForm() {
    setCategoryId('');
    setDateFrom('');
    setDateTo('');
    setTimeFrom('');
    setTimeTo('');
    setApproverId('');
    setNotes('');
  }

  async function doSubmit() {
    setSubmitting(true);
    try {
      const result = await absencesApi.submit({
        category_id: Number(categoryId),
        date_from: dateFrom,
        date_to: isFullDay ? dateTo : dateFrom,
        time_from: isFullDay ? null : timeFrom,
        time_to: isFullDay ? null : timeTo,
        approver_id: Number(approverId),
        notes: notes.trim() || null,
      });
      if (!result.success) {
        toast.error(result.error);
        return;
      }
      toast.success('Wniosek poszedł. Teraz czekaj i módl się o zatwierdzenie.');
      resetForm();
      setSheetOpen(false);
      reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd składania wniosku');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!categoryId || !dateFrom || !approverId) {
      toast.error('Uzupełnij wymagane pola');
      return;
    }
    if (isFullDay && !dateTo) {
      toast.error('Uzupełnij wymagane pola');
      return;
    }
    if (!isFullDay && (!timeFrom || !timeTo)) {
      toast.error('Uzupełnij godzinę od/do');
      return;
    }

    try {
      const preview = await absencesApi.previewConflicts({
        date_from: dateFrom,
        date_to: isFullDay ? dateTo : dateFrom,
        time_from: isFullDay ? undefined : timeFrom,
        time_to: isFullDay ? undefined : timeTo,
      });
      if (preview.success && preview.conflicts.length > 0) {
        const names = preview.conflicts
          .slice(0, 3)
          .map((c) => `${c.date} ${c.client_name ?? ''}`.trim())
          .join(', ');
        const ok = await confirm({
          title: 'Masz już zaplanowane wizyty w tym terminie',
          message: `${preview.conflicts.length} wizyt koliduje z tym terminem (${names}${preview.conflicts.length > 3 ? '…' : ''}). To tylko informacja — możesz mimo to złożyć wniosek, przełożony zobaczy te same konflikty przy zatwierdzaniu.`,
          confirmText: 'Potwierdź zgłoszenie',
        });
        if (!ok) return;
      }
    } catch {
      /* preview is best-effort — never block submission on it */
    }
    doSubmit();
  }

  /** Cancel a pending request, or an approved absence (which also frees the
   * employee's calendar slots) — one path for the desktop icon and the phone
   * card button. */
  async function cancelRecord(a: AbsenceRecord) {
    const approved = a.status === 'approved';
    const ok = await confirm(
      approved
        ? { title: 'Anuluj nieobecność', message: 'Anulować tę zatwierdzoną nieobecność? Twoje sloty w kalendarzu zostaną zwolnione.', confirmText: 'Tak, anuluj' }
        : { title: 'Anuluj wniosek', message: 'Anulować ten wniosek?', confirmText: 'Tak, anuluj' },
    );
    if (!ok) return;
    try {
      const r = approved ? await absencesApi.cancelApprovedOwn(a.id) : await absencesApi.cancel(a.id);
      if (r.success) {
        toast.success(approved ? 'Nieobecność anulowana — sloty wróciły do kalendarza, jakby nigdy nic.' : 'Wniosek anulowany. Rozmyśliłeś się, bywa.');
        reload();
      } else {
        toast.error(r.error);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się anulować');
    }
  }

  const requestForm = (
    <form id="ab-request-form" onSubmit={handleSubmit}>
      <div className="form-grid">
        <div className="form-col-full">
          <label className="field-label" htmlFor="ab-category">
            Rodzaj nieobecności <span className="field-required">*</span>
          </label>
          <select id="ab-category" className="refined-select" required value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">— wybierz kategorię —</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {!c.absence_full_day ? ' (godzinowa)' : ''}
              </option>
            ))}
          </select>
        </div>

        {isFullDay ? (
          <>
            <div>
              <label className="field-label" htmlFor="ab-date-from">
                Data od <span className="field-required">*</span>
              </label>
              <input id="ab-date-from" type="date" className="refined-input" required value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div>
              <label className="field-label" htmlFor="ab-date-to">
                Data do <span className="field-required">*</span>
              </label>
              <input id="ab-date-to" type="date" className="refined-input" required value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
          </>
        ) : (
          <div className="form-col-full">
            <div className="form-grid ab-slot-grid">
              <div className="ab-slot-date">
                <label className="field-label" htmlFor="ab-slot-date">
                  Data nieobecności <span className="field-required">*</span>
                </label>
                <input id="ab-slot-date" type="date" className="refined-input" required value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
              </div>
              <div />
              <div>
                <label className="field-label" htmlFor="ab-time-from">
                  Godzina od <span className="field-required">*</span>
                </label>
                <input id="ab-time-from" type="time" className="refined-input" required value={timeFrom} onChange={(e) => setTimeFrom(e.target.value)} />
              </div>
              <div>
                <label className="field-label" htmlFor="ab-time-to">
                  Godzina do <span className="field-required">*</span>
                </label>
                <input id="ab-time-to" type="time" className="refined-input" required value={timeTo} onChange={(e) => setTimeTo(e.target.value)} />
              </div>
            </div>
          </div>
        )}

        <div className="form-col-full">
          <label className="field-label" htmlFor="ab-approver">
            Przełożony (zatwierdzający) <span className="field-required">*</span>
          </label>
          <select id="ab-approver" className="refined-select" required value={approverId} onChange={(e) => setApproverId(e.target.value)}>
            <option value="">— wybierz przełożonego —</option>
            {supervisors.map((s) => (
              <option key={s.id} value={s.id}>
                {s.first_name} {s.last_name}
                {s.position ? ` – ${s.position}` : ''}
              </option>
            ))}
          </select>
        </div>

        <div className="form-col-full">
          <label className="field-label" htmlFor="ab-notes">
            Uwagi (opcjonalnie)
          </label>
          <textarea id="ab-notes" className="refined-textarea" placeholder="Dodatkowe informacje dla przełożonego…" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>

      {!isMobile && (
        <div className="form-actions">
          <Button type="submit" variant="primary" icon="send" isLoading={submitting} loadingText="Wysyłanie…">
            Złóż wniosek
          </Button>
        </div>
      )}
    </form>
  );

  const noSupervisorWarning = (
    <div className="no-supervisor-warning">Brak przypisanego przełożonego. Skontaktuj się z administratorem — nie możesz składać wniosków.</div>
  );

  return (
    <div className="refined-page absences-page my-absences-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Moje nieobecności</h1>
          <p className="page-subtitle">Zarządzaj wnioskami o urlop i przeglądaj historię nieobecności</p>
        </div>
      </header>

      {isMobile ? (
        <>
          {cannotFile && noSupervisorWarning}

          <h2 className="ab-section-title">
            <span>Historia wniosków</span>
            <span className="ab-section-count">{absences.length}</span>
          </h2>

          {initialLoad ? (
            <p className="ab-phone-empty">Ładowanie…</p>
          ) : absences.length === 0 ? (
            <p className="ab-phone-empty">
              Brak złożonych wniosków.
              {!cannotFile && <> Stuknij „Nowy wniosek”, żeby złożyć pierwszy.</>}
            </p>
          ) : (
            <ul className="ab-cards">
              {absences.map((a) => {
                const status = STATUS_LABEL[a.status];
                const canCancel = a.status === 'pending' || a.status === 'approved';
                return (
                  <li key={a.id} className="ab-card">
                    <div className="ab-card-top">
                      <span className="ab-card-category">{a.category_name}</span>
                      <span className={`ab-status ${status.className}`}>{status.label}</span>
                    </div>
                    <div className="ab-card-period">{formatPeriodPhone(a)}</div>
                    <div className="ab-card-meta">Przełożony: {a.approver_name || '—'}</div>
                    <div className="ab-card-meta">Złożono {formatRequestedPhone(a.requested_at)}</div>
                    {a.status === 'rejected' && a.rejection_reason && <p className="rejection-note ab-card-note">{a.rejection_reason}</p>}
                    {canCancel && (
                      <button type="button" className="ab-card-cancel" onClick={() => cancelRecord(a)}>
                        {a.status === 'approved' ? 'Anuluj nieobecność' : 'Anuluj wniosek'}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

          {!loading && !cannotFile && (
            <div className={`ab-mobile-cta${ctaHidden ? ' ab-mobile-cta--hidden' : ''}`}>
              <Button variant="primary" icon="add" onClick={() => setSheetOpen(true)}>
                Nowy wniosek
              </Button>
            </div>
          )}

          <Modal
            isOpen={sheetOpen}
            onClose={() => setSheetOpen(false)}
            title="Nowy wniosek"
            variant="sheet"
            footer={
              <Button type="submit" form="ab-request-form" variant="primary" icon="send" isLoading={submitting} loadingText="Wysyłanie…">
                Złóż wniosek
              </Button>
            }
          >
            {requestForm}
          </Modal>
        </>
      ) : (
        <>
          <div className="card">
            <div className="card-header">
              <span className="card-title">Złóż wniosek o nieobecność</span>
            </div>
            <div className="card-body">{cannotFile ? noSupervisorWarning : requestForm}</div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">Historia wniosków</span>
              <span className="card-count">
                {absences.length} {absences.length === 1 ? 'wpis' : 'wpisów'}
              </span>
            </div>
            <div className="table-container stack-cards-wrap">
              {initialLoad ? (
                <div className="empty-state">
                  <p className="empty-text">Ładowanie…</p>
                </div>
              ) : absences.length === 0 ? (
                <div className="empty-state">
                  <p className="empty-text">Brak złożonych wniosków</p>
                </div>
              ) : (
                <table className="refined-table stack-cards">
                  <thead>
                    <tr>
                      <th>Kategoria</th>
                      <th>Okres</th>
                      <th>Przełożony</th>
                      <th>Status</th>
                      <th>Złożono</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {absences.map((a) => {
                      const status = STATUS_LABEL[a.status];
                      return (
                        <tr key={a.id}>
                          <td className="cell-name">
                            <span style={{ fontWeight: 500 }}>{a.category_name}</span>
                            {a.absence_full_day === false && <span className="ab-hourly-tag">godzinowa</span>}
                          </td>
                          <td data-label="Okres">{formatPeriod(a)}</td>
                          <td data-label="Przełożony">{a.approver_name || '—'}</td>
                          <td data-label="Status">
                            <span className={`ab-status ${status.className}`}>{status.label}</span>
                            {a.status === 'rejected' && a.rejection_reason && <div className="rejection-note">{a.rejection_reason}</div>}
                          </td>
                          <td data-label="Złożono" className="ab-muted-nowrap">
                            {a.requested_at ? a.requested_at.slice(0, 16).replace('T', ' ') : '—'}
                          </td>
                          <td className="cell-actions">
                            {(a.status === 'pending' || a.status === 'approved') && (
                              <button
                                type="button"
                                className="action-icon-btn"
                                style={{ color: '#c2410c' }}
                                title={a.status === 'approved' ? 'Anuluj nieobecność (zwolnij sloty w kalendarzu)' : 'Anuluj wniosek'}
                                aria-label={a.status === 'approved' ? 'Anuluj zatwierdzoną nieobecność' : 'Anuluj wniosek'}
                                onClick={() => cancelRecord(a)}
                              >
                                <Icon name={a.status === 'approved' ? 'delete' : 'close'} />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
