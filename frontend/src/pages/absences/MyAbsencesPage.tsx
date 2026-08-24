import { useEffect, useState } from 'react';
import './AbsencesPages.css';
import { absencesApi } from '../../lib/api/absences';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
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

/** Moje nieobecności — self-service request form + history. Ported from
 * templates/absences/my.html + static/js/absences.js's initSubmitForm/
 * initPreviewConflicts. New /api/my-absences* JSON endpoints
 * (routes/absence_routes.py) added alongside the original form-POST routes.
 * The pre-submit conflict preview is simplified to a confirm summary instead
 * of the original's full table modal — same non-blocking behavior, lighter
 * UI (no new bespoke modal component for a purely informational step). */
export function MyAbsencesPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [absences, setAbsences] = useState<AbsenceRecord[]>([]);
  const [categories, setCategories] = useState<AbsenceCategory[]>([]);
  const [supervisors, setSupervisors] = useState<AbsenceSupervisor[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

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

  return (
    <div className="refined-page absences-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Moje nieobecności</h1>
          <p className="page-subtitle">Zarządzaj wnioskami o urlop i przeglądaj historię nieobecności</p>
        </div>
      </header>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Złóż wniosek o nieobecność</span>
        </div>
        <div className="card-body">
          {!loading && supervisors.length === 0 ? (
            <div className="no-supervisor-warning">Brak przypisanego przełożonego. Skontaktuj się z administratorem — nie możesz składać wniosków.</div>
          ) : (
            <form onSubmit={handleSubmit}>
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
                    <div className="form-grid">
                      <div>
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

              <div className="form-actions">
                <Button type="submit" variant="primary" icon="send" isLoading={submitting} loadingText="Wysyłanie…">
                  Złóż wniosek
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Historia wniosków</span>
          <span className="card-count">
            {absences.length} {absences.length === 1 ? 'wpis' : 'wpisów'}
          </span>
        </div>
        <div className="table-container stack-cards-wrap">
          {loading ? (
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
                        {a.status === 'pending' && (
                          <button
                            type="button"
                            className="action-icon-btn"
                            style={{ color: '#c2410c' }}
                            title="Anuluj wniosek"
                            aria-label="Anuluj wniosek"
                            onClick={async () => {
                              const ok = await confirm({ title: 'Anuluj wniosek', message: 'Anulować ten wniosek?', confirmText: 'Tak, anuluj' });
                              if (!ok) return;
                              const r = await absencesApi.cancel(a.id);
                              if (r.success) {
                                toast.success('Wniosek anulowany. Rozmyśliłeś się, bywa.');
                                reload();
                              } else {
                                toast.error(r.error);
                              }
                            }}
                          >
                            <Icon name="close" />
                          </button>
                        )}
                        {a.status === 'approved' && (
                          <button
                            type="button"
                            className="action-icon-btn"
                            style={{ color: '#c2410c' }}
                            title="Anuluj nieobecność (zwolnij sloty w kalendarzu)"
                            aria-label="Anuluj zatwierdzoną nieobecność"
                            onClick={async () => {
                              const ok = await confirm({
                                title: 'Anuluj nieobecność',
                                message: 'Anulować tę zatwierdzoną nieobecność? Twoje sloty w kalendarzu zostaną zwolnione.',
                                confirmText: 'Tak, anuluj',
                              });
                              if (!ok) return;
                              const r = await absencesApi.cancelApprovedOwn(a.id);
                              if (r.success) {
                                toast.success('Nieobecność anulowana — sloty wróciły do kalendarza, jakby nigdy nic.');
                                reload();
                              } else {
                                toast.error(r.error);
                              }
                            }}
                          >
                            <Icon name="delete" />
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
    </div>
  );
}
