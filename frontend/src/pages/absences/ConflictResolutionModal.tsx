import { useEffect, useRef, useState } from 'react';
import { absencesApi } from '../../lib/api/absences';
import { appointmentsApi } from '../../lib/api/appointments';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import type { AppointmentConflict, ConflictResolution } from '../../types/absence';
import type { AvailableSlot, ReassignmentCandidate } from '../../types/appointment';

interface Props {
  isOpen: boolean;
  absenceId: number | null;
  employeeId: number | null;
  initialConflicts: AppointmentConflict[];
  onClose: () => void;
  /** Delegates to AbsencesManagementPage's existing standalone reject modal
   * (same reason-required flow every other pending request uses) — this
   * component only closes itself, it doesn't duplicate that form. */
  onReject: () => void;
  /** True-approve or force-approve succeeded — parent closes + reloads. */
  onApproved: () => void;
}

type Step = 'list' | 'reassign' | 'no-candidates' | 'reschedule';

const TITLES: Record<Step, string> = {
  list: 'Konflikty z wizytami klientów',
  reassign: 'Zmień stylistę',
  'no-candidates': 'Brak dostępnych stylistów',
  reschedule: 'Zmień termin',
};

function minutesBetween(start: string, end: string) {
  const [sh, sm] = start.slice(0, 5).split(':').map(Number);
  const [eh, em] = end.slice(0, 5).split(':').map(Number);
  return eh * 60 + em - (sh * 60 + sm);
}

const RESOLUTION_TYPE_LABEL: Record<string, string> = {
  reassigned: 'Zmieniono stylistę',
  rescheduled: 'Zmieniono termin',
  cancelled: 'Anulowano wizytę',
};

function resolutionDetail(r: ConflictResolution) {
  if (r.resolution_type === 'reassigned') return `${r.previous_employee_name ?? '—'} → ${r.new_employee_name ?? '—'}`;
  if (r.resolution_type === 'rescheduled') return `${r.previous_date ?? ''} ${r.previous_start_time ?? ''} → ${r.new_date ?? ''} ${r.new_start_time ?? ''}`;
  return r.cancellation_reason ?? '—';
}

/**
 * Multi-step conflict-resolution flow for the "Zatwierdź" action on an
 * absence request that overlaps booked appointments — reassign to an
 * eligible replacement, reschedule to a free slot, or cancel (with opt-in
 * client SMS). Ported from `static/js/absences.js`'s `showConflictModal()` +
 * its step renderers (`_renderReassignStep`/`_renderNoCandidatesStep`/
 * `_renderRescheduleStep`), as a controlled state machine instead of that
 * file's imperative `_setBody`/`_setFooter` DOM patching.
 *
 * This is the ONLY entry point this feature has ever had, in the legacy app
 * too — there's no separate Wizyty-side UI for it (module-inventory.md's
 * "integracja z Nieobecnościami" deferred item was this exact modal, not a
 * second surface to build).
 *
 * Root-cause fix vs. the reference: see the long comment in
 * `lib/api/appointments.ts`'s absence-conflict-resolution section — the
 * legacy JS calls these four endpoints without the `/api` prefix
 * `appointment_bp` is actually registered under, so they've likely never
 * worked in production. This port uses the correct, verified paths.
 */
export function ConflictResolutionModal({ isOpen, absenceId, employeeId, initialConflicts, onClose, onReject, onApproved }: Props) {
  const toast = useToast();
  const [step, setStep] = useState<Step>('list');
  const [conflicts, setConflicts] = useState<AppointmentConflict[]>(initialConflicts);
  const [activeConflict, setActiveConflict] = useState<AppointmentConflict | null>(null);
  const [hasHistory, setHasHistory] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [approving, setApproving] = useState<'true' | 'force' | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Reassign step
  const [candidates, setCandidates] = useState<ReassignmentCandidate[] | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);
  const [reassignBulk, setReassignBulk] = useState(false);

  // No-candidates step
  const [cancelSendSms, setCancelSendSms] = useState(true);
  const [cancelBulk, setCancelBulk] = useState(false);

  // Reschedule step
  const [rescheduleDate, setRescheduleDate] = useState('');
  const [slots, setSlots] = useState<AvailableSlot[] | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<AvailableSlot | null>(null);

  // Invalidates in-flight candidate/slot fetches when the user navigates away
  // mid-request (legacy's `if (ctx.currentStep !== 'reassign') return;` guard).
  const requestToken = useRef(0);

  useEffect(() => {
    if (!isOpen || absenceId == null) return;
    setStep('list');
    setConflicts(initialConflicts);
    setActiveConflict(null);
    setHasHistory(false);
    // Background check — doesn't block the list step, doesn't clobber a step
    // the user already moved to by the time it resolves.
    absencesApi
      .resolutions(absenceId)
      .then((r) => {
        if (r.success && r.resolutions.length > 0) setHasHistory(true);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, absenceId]);

  function backToList() {
    requestToken.current++;
    setStep('list');
    setActiveConflict(null);
  }

  async function refresh() {
    try {
      const res = await absencesApi.conflicts(absenceId!);
      if (res.success) setConflicts(res.conflicts);
    } catch {
      /* keep the stale list rather than crash the modal */
    }
    backToList();
  }

  async function handleTrueApprove() {
    setApproving('true');
    try {
      const result = await absencesApi.approve(absenceId!);
      if (!result.success) {
        toast.error(result.error);
        return;
      }
      if (result.status === 'conflict') {
        // Shouldn't happen (button only enables when conflicts is empty), but
        // the DB is the real source of truth — resync rather than trust it.
        setConflicts(result.conflicts ?? []);
        return;
      }
      toast.success('Wniosek zatwierdzony');
      onApproved();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zatwierdzania wniosku');
    } finally {
      setApproving(null);
    }
  }

  async function handleForceApprove() {
    setApproving('force');
    try {
      const result = await absencesApi.forceApprove(absenceId!);
      if (!result.success) {
        toast.error(result.error);
        return;
      }
      toast.success('Wniosek zatwierdzony mimo konfliktów');
      onApproved();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zatwierdzania');
    } finally {
      setApproving(null);
    }
  }

  async function openReassign(conflict: AppointmentConflict) {
    const token = ++requestToken.current;
    setActiveConflict(conflict);
    setStep('reassign');
    setCandidates(null);
    setSelectedCandidate(null);
    setReassignBulk(false);
    try {
      const list = await appointmentsApi.reassignmentCandidates(conflict.appointment_id);
      if (requestToken.current !== token) return;
      setCandidates(list);
      if (list.length === 0) {
        setCancelSendSms(true);
        setCancelBulk(false);
        setStep('no-candidates');
      }
    } catch {
      if (requestToken.current !== token) return;
      setCandidates([]);
      setCancelSendSms(true);
      setCancelBulk(false);
      setStep('no-candidates');
    }
  }

  async function submitReassign() {
    if (!activeConflict || selectedCandidate == null) return;
    setSubmitting(true);
    try {
      const res = await appointmentsApi.reassignForAbsence(activeConflict.appointment_id, {
        absence_id: absenceId!,
        new_employee_id: selectedCandidate,
        bulk: reassignBulk,
      });
      if (!res.success) {
        toast.error(res.error);
        return;
      }
      if (reassignBulk && res.skipped.length > 0) {
        toast.error(`Zastosowano do ${res.applied.length} wizyt. ${res.skipped.length} konfliktów wymaga ręcznej obsługi.`);
      } else {
        toast.success('Stylista zmieniony');
      }
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zmiany stylisty');
    } finally {
      setSubmitting(false);
    }
  }

  async function submitCancel() {
    if (!activeConflict) return;
    setSubmitting(true);
    try {
      const res = await appointmentsApi.cancelForAbsence(activeConflict.appointment_id, {
        absence_id: absenceId!,
        cancellation_reason: 'Brak dostępnego zastępstwa — nieobecność pracownika',
        send_sms: cancelSendSms,
        bulk: cancelBulk,
      });
      if (!res.success) {
        toast.error(res.error);
        return;
      }
      toast.success(cancelBulk ? `Anulowano ${res.applied.length} wizyt` : 'Wizyta anulowana');
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd anulowania wizyty');
    } finally {
      setSubmitting(false);
    }
  }

  function openReschedule(conflict: AppointmentConflict) {
    requestToken.current++;
    setActiveConflict(conflict);
    setStep('reschedule');
    setRescheduleDate(conflict.date);
    setSlots(null);
    setSelectedSlot(null);
  }

  const durationMin = activeConflict ? minutesBetween(activeConflict.start_time, activeConflict.end_time) : 0;

  useEffect(() => {
    if (step !== 'reschedule' || !activeConflict || !rescheduleDate || employeeId == null) return;
    const token = ++requestToken.current;
    setSlotsLoading(true);
    setSelectedSlot(null);
    appointmentsApi
      .availableSlots({ employee_id: employeeId, date: rescheduleDate, duration: durationMin })
      .then((available) => {
        if (requestToken.current !== token) return;
        setSlots(available);
      })
      .catch(() => {
        if (requestToken.current !== token) return;
        setSlots([]);
      })
      .finally(() => {
        if (requestToken.current === token) setSlotsLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, activeConflict, rescheduleDate, employeeId, durationMin]);

  async function submitReschedule() {
    if (!activeConflict || !selectedSlot || !rescheduleDate) return;
    setSubmitting(true);
    try {
      const res = await appointmentsApi.rescheduleForAbsence(activeConflict.appointment_id, {
        absence_id: absenceId!,
        new_date: rescheduleDate,
        new_start_time: selectedSlot.start_time,
        new_end_time: selectedSlot.end_time,
      });
      if (!res.success) {
        toast.error(res.error);
        return;
      }
      toast.success('Termin zmieniony');
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zmiany terminu');
    } finally {
      setSubmitting(false);
    }
  }

  // All hooks above must run unconditionally on every render (rules-of-hooks)
  // — this guard has to come after every useState/useEffect/useRef call, not
  // before them.
  if (!isOpen || absenceId == null || employeeId == null) return null;

  const todayStr = new Date().toISOString().slice(0, 10);

  return (
    <>
      <Modal isOpen={isOpen} onClose={onClose} title={TITLES[step]} size="large">
        {step === 'list' && (
          <>
            {conflicts.length === 0 ? (
              <p style={{ color: 'var(--color-success)', fontSize: '0.8125rem', marginBottom: '1rem' }}>Wszystkie konflikty rozwiązane — możesz zatwierdzić wniosek.</p>
            ) : (
              <p style={{ color: 'var(--color-ink-subtle)', fontSize: '0.8125rem', marginBottom: '1rem' }}>
                Zatwierdzenie tej nieobecności koliduje z poniższymi wizytami klientów. Zmień stylistę lub termin każdej z nich, albo zatwierdź mimo to.
              </p>
            )}
            {conflicts.length > 0 && (
              <div className="table-container">
                <table className="refined-table">
                  <thead>
                    <tr>
                      <th>Data</th>
                      <th>Godzina</th>
                      <th>Klient</th>
                      <th>Usługa</th>
                      <th style={{ textAlign: 'right' }}>Akcje</th>
                    </tr>
                  </thead>
                  <tbody>
                    {conflicts.map((c) => (
                      <tr key={c.appointment_id}>
                        <td>{c.date}</td>
                        <td>
                          {c.start_time.slice(0, 5)} – {c.end_time.slice(0, 5)}
                        </td>
                        <td>{c.client_name ?? '—'}</td>
                        <td>{c.service_name ?? '—'}</td>
                        <td className="cell-actions">
                          <div className="action-icons">
                            <button type="button" className="action-icon-btn" title="Zmień stylistę" aria-label="Zmień stylistę" onClick={() => openReassign(c)}>
                              <Icon name="person_search" />
                            </button>
                            <button type="button" className="action-icon-btn" title="Zmień termin" aria-label="Zmień termin" onClick={() => openReschedule(c)}>
                              <Icon name="edit_calendar" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {hasHistory && (
              <button type="button" className="crm-history-link" onClick={() => setHistoryOpen(true)}>
                Historia rozwiązań →
              </button>
            )}
            <div className="form-actions">
              <Button variant="primary" disabled={conflicts.length > 0 || approving !== null} isLoading={approving === 'true'} loadingText="Zatwierdzanie…" onClick={handleTrueApprove}>
                Zatwierdź
              </Button>
              <Button variant="danger" disabled={approving !== null} isLoading={approving === 'force'} loadingText="Zatwierdzanie…" onClick={handleForceApprove}>
                Zatwierdź mimo to
              </Button>
              <Button variant="secondary" onClick={onReject}>
                Odrzuć
              </Button>
              <Button variant="secondary" onClick={onClose}>
                Anuluj
              </Button>
            </div>
          </>
        )}

        {step === 'reassign' && (
          <>
            {candidates === null ? (
              <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)' }}>Szukam dostępnych zastępstw…</p>
            ) : (
              <>
                <div className="table-container" style={{ marginBottom: '0.75rem' }}>
                  <table className="refined-table">
                    <thead>
                      <tr>
                        <th>Pracownik</th>
                        <th>Stanowisko</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.map((c) => (
                        <tr key={c.employee_id}>
                          <td>
                            <label className="crm-candidate-row">
                              <input type="radio" name="reassign-candidate" checked={selectedCandidate === c.employee_id} onChange={() => setSelectedCandidate(c.employee_id)} />
                              {c.name}
                            </label>
                          </td>
                          <td>{c.position ?? '—'}</td>
                          <td>
                            {!c.is_preferred && (
                              <span
                                role="img"
                                aria-label="nie figuruje na liście preferowanych przez klienta stylistów"
                                title="Nie figuruje na liście preferowanych przez klienta stylistów"
                                className="crm-warning-icon"
                              >
                                <Icon name="warning_amber" />
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <label className="crm-checkbox-row">
                  <input type="checkbox" checked={reassignBulk} onChange={(e) => setReassignBulk(e.target.checked)} />
                  Zastosuj wybór do wszystkich pozostałych konfliktów tego pracownika
                </label>
              </>
            )}
            <div className="form-actions">
              <Button variant="secondary" onClick={backToList}>
                ← Wróć
              </Button>
              {candidates !== null && (
                <Button variant="primary" disabled={selectedCandidate == null || submitting} isLoading={submitting} loadingText="Zapisywanie…" onClick={submitReassign}>
                  Potwierdź zastępstwo
                </Button>
              )}
            </div>
          </>
        )}

        {step === 'no-candidates' && (
          <>
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)', marginBottom: '1rem' }}>
              Żaden pracownik nie jest dostępny jako zastępstwo dla tej wizyty. Możesz ją anulować.
            </p>
            <label className="crm-checkbox-row">
              <input type="checkbox" checked={cancelSendSms} onChange={(e) => setCancelSendSms(e.target.checked)} />
              Wyślij SMS do klienta (informacja o odwołaniu + link do rezerwacji)
            </label>
            <label className="crm-checkbox-row">
              <input type="checkbox" checked={cancelBulk} onChange={(e) => setCancelBulk(e.target.checked)} />
              Anuluj też wszystkie pozostałe skonfliktowane wizyty tego pracownika
            </label>
            <div className="form-actions">
              <Button variant="secondary" onClick={backToList}>
                ← Wróć
              </Button>
              <Button variant="danger" disabled={submitting} isLoading={submitting} loadingText="Anulowanie…" onClick={submitCancel}>
                Anuluj wizytę
              </Button>
            </div>
          </>
        )}

        {step === 'reschedule' && (
          <>
            <div style={{ marginBottom: '0.75rem' }}>
              <label className="field-label" htmlFor="crm-reschedule-date">
                Nowa data
              </label>
              <input id="crm-reschedule-date" type="date" className="refined-input" min={todayStr} value={rescheduleDate} onChange={(e) => setRescheduleDate(e.target.value)} />
            </div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)' }}>
              {!rescheduleDate ? (
                'Wybierz datę, żeby zobaczyć wolne terminy.'
              ) : slotsLoading ? (
                'Ładowanie wolnych terminów…'
              ) : slots === null ? null : slots.length === 0 ? (
                'Brak wolnych terminów tego dnia.'
              ) : (
                <div className="crm-slots">
                  {slots.map((s) => (
                    <button
                      key={`${s.start_time}-${s.end_time}`}
                      type="button"
                      className={`crm-slot-btn${selectedSlot?.start_time === s.start_time ? ' selected' : ''}`}
                      onClick={() => setSelectedSlot(s)}
                    >
                      {s.start_time}–{s.end_time}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="form-actions">
              <Button variant="secondary" onClick={backToList}>
                ← Wróć
              </Button>
              <Button variant="primary" disabled={!selectedSlot || submitting} isLoading={submitting} loadingText="Zapisywanie…" onClick={submitReschedule}>
                Potwierdź zmianę terminu
              </Button>
            </div>
          </>
        )}
      </Modal>

      <ResolutionHistoryModal isOpen={historyOpen} absenceId={absenceId} onClose={() => setHistoryOpen(false)} />
    </>
  );
}

/** Read-only leaf view (its own Modal, not a step) — ported from
 * `static/js/absences.js`'s `showResolutionHistory()`. */
function ResolutionHistoryModal({ isOpen, absenceId, onClose }: { isOpen: boolean; absenceId: number; onClose: () => void }) {
  const [resolutions, setResolutions] = useState<ConflictResolution[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    absencesApi
      .resolutions(absenceId)
      .then((r) => setResolutions(r.resolutions))
      .catch(() => setResolutions([]))
      .finally(() => setLoading(false));
  }, [isOpen, absenceId]);

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Historia rozwiązań" size="large">
      {loading ? (
        <p className="empty-text">Ładowanie…</p>
      ) : resolutions.length === 0 ? (
        <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)' }}>Brak zapisanej historii.</p>
      ) : (
        <div className="table-container">
          <table className="refined-table">
            <tbody>
              {resolutions.map((r) => (
                <tr key={r.id}>
                  <td>
                    {r.client_name ?? '—'} — {r.service_name ?? '—'}
                  </td>
                  <td>{RESOLUTION_TYPE_LABEL[r.resolution_type] ?? r.resolution_type}</td>
                  <td>{resolutionDetail(r)}</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--color-ink-subtle)' }}>
                    {r.resolved_by_name ?? '—'}
                    <br />
                    {r.resolved_at ?? ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="form-actions">
        <Button variant="secondary" onClick={onClose}>
          Zamknij
        </Button>
      </div>
    </Modal>
  );
}
