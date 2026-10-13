import { useEffect, useRef, useState } from 'react';
import { absencesApi } from '../../lib/api/absences';
import { appointmentsApi } from '../../lib/api/appointments';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { useIsMobile } from '../appointments/MobileWizytyCalendarView';
import { formatPeriodPhone } from './absenceFormat';
import type { AppointmentConflict, ConflictResolution, ResolutionSmsType, ResolutionsResult } from '../../types/absence';
import type { AvailableSlot, ReassignmentCandidate, SmsAvailability } from '../../types/appointment';

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

/** Which client SMS "Wyślij wiadomość" queues for a resolved row. */
function smsTypeFor(r: ConflictResolution): ResolutionSmsType {
  return r.resolution_type === 'cancelled' ? 'absence_cancellation' : 'absence_visit_update';
}

/** Only scheduled/confirmed visits can be cancelled from the conflict table (an older
 * payload without `status` keeps the button — the server re-validates the transition). */
function isCancellable(c: AppointmentConflict) {
  return !c.status || c.status === 'scheduled' || c.status === 'confirmed';
}

const QUICK_CANCEL_REASON = 'Brak dostępnego zastępstwa — nieobecność pracownika';

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
  const isMobile = useIsMobile(640);
  const [step, setStep] = useState<Step>('list');
  const [conflicts, setConflicts] = useState<AppointmentConflict[]>(initialConflicts);
  const [activeConflict, setActiveConflict] = useState<AppointmentConflict | null>(null);
  // "Historia rozwiązań" now lives in the main modal, under the conflict table: every
  // resolution moves a row from the top table to this one.
  const [resolutions, setResolutions] = useState<ConflictResolution[]>([]);
  const [resolutionSms, setResolutionSms] = useState<ResolutionsResult['sms'] | null>(null);
  // "Wyślij wiadomość" marks — staged here, queued server-side only when the absence is approved.
  const [smsMarked, setSmsMarked] = useState<Set<number>>(() => new Set());
  // Two-click guard on the table's "Anuluj wizytę" icon: first click arms, second cancels.
  const [armedCancelId, setArmedCancelId] = useState<number | null>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [approving, setApproving] = useState<'true' | 'force' | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Reassign step
  const [candidates, setCandidates] = useState<ReassignmentCandidate[] | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);
  const [reassignBulk, setReassignBulk] = useState(false);

  // No-candidates step. `smsStatus` is the server's answer to "can this client SMS actually go
  // out?" — the box is only offered (and only ticked by default) when it can; otherwise staff
  // would tick it and believe the client was told while the disabled SMS type sent nothing.
  const [cancelSendSms, setCancelSendSms] = useState(false);
  const [smsStatus, setSmsStatus] = useState<SmsAvailability>({ available: false, reason: '' });
  const [cancelBulk, setCancelBulk] = useState(false);

  // Reschedule step
  const [rescheduleDate, setRescheduleDate] = useState('');
  const [slots, setSlots] = useState<AvailableSlot[] | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<AvailableSlot | null>(null);

  // Invalidates in-flight candidate/slot fetches when the user navigates away
  // mid-request (legacy's `if (ctx.currentStep !== 'reassign') return;` guard).
  const requestToken = useRef(0);

  async function loadResolutions(id: number) {
    try {
      const r = await absencesApi.resolutions(id);
      if (r.success) {
        setResolutions(r.resolutions);
        setResolutionSms(r.sms ?? null);
      }
    } catch {
      /* history is informational — a failed fetch leaves the last known list */
    }
  }

  useEffect(() => {
    if (!isOpen || absenceId == null) return;
    setStep('list');
    setConflicts(initialConflicts);
    setActiveConflict(null);
    setResolutions([]);
    setResolutionSms(null);
    setSmsMarked(new Set());
    setArmedCancelId(null);
    // Background load — doesn't block the list step.
    loadResolutions(absenceId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, absenceId]);

  // Disarm the cancel icon if the second click doesn't come within a few seconds.
  useEffect(() => {
    if (armedCancelId == null) return;
    const t = window.setTimeout(() => setArmedCancelId(null), 4000);
    return () => window.clearTimeout(t);
  }, [armedCancelId]);

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
    await loadResolutions(absenceId!);
    backToList();
  }

  function toggleSms(appointmentId: number) {
    setSmsMarked((prev) => {
      const next = new Set(prev);
      if (next.has(appointmentId)) next.delete(appointmentId);
      else next.add(appointmentId);
      return next;
    });
  }

  /** Marks that still point at a visible history row (the server ignores unknown ids anyway —
   * this just keeps the payload honest). */
  function markedIds() {
    const visible = new Set(resolutions.map((r) => r.appointment_id));
    return [...smsMarked].filter((id) => visible.has(id));
  }

  async function quickCancel(c: AppointmentConflict) {
    if (armedCancelId !== c.appointment_id) {
      setArmedCancelId(c.appointment_id);
      return;
    }
    setArmedCancelId(null);
    setCancellingId(c.appointment_id);
    try {
      const res = await appointmentsApi.cancelForAbsence(c.appointment_id, {
        absence_id: absenceId!,
        cancellation_reason: QUICK_CANCEL_REASON,
        // The client notice is opt-in from the history table ("Wyślij wiadomość").
        send_sms: false,
        bulk: false,
      });
      if (!res.success) {
        toast.error(res.error);
        return;
      }
      toast.success('Wizyta anulowana');
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd anulowania wizyty');
    } finally {
      setCancellingId(null);
    }
  }

  function smsSummary(queued: number) {
    return queued > 0 ? ` SMS w kolejce: ${queued}.` : '';
  }

  async function handleTrueApprove() {
    setApproving('true');
    try {
      const result = await absencesApi.approve(absenceId!, markedIds());
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
      toast.success(`Wniosek zatwierdzony.${smsSummary(result.sms_queued?.length ?? 0)}`);
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
      const result = await absencesApi.forceApprove(absenceId!, markedIds());
      if (!result.success) {
        toast.error(result.error);
        return;
      }
      if (result.defer_error) {
        // Approved, but the unresolved visits were NOT parked for auto-cancel — say so loudly.
        toast.error(`Wniosek zatwierdzony, ale nie zaplanowano auto-anulowania wizyt: ${result.defer_error}`);
      } else {
        const n = result.deferred?.length ?? 0;
        toast.success(
          `Wniosek zatwierdzony mimo konfliktów.${n > 0 ? ` Nierozwiązane wizyty (${n}) zostaną automatycznie anulowane 48 h przed terminem.` : ''}${smsSummary(result.sms_queued?.length ?? 0)}`,
        );
      }
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
      const { candidates: list, sms } = await appointmentsApi.reassignmentCandidates(conflict.appointment_id);
      if (requestToken.current !== token) return;
      setCandidates(list);
      setSmsStatus(sms);
      if (list.length === 0) {
        setCancelSendSms(sms.available);
        setCancelBulk(false);
        setStep('no-candidates');
      }
    } catch {
      if (requestToken.current !== token) return;
      setCandidates([]);
      setSmsStatus({ available: false, reason: 'Nie udało się sprawdzić ustawień SMS.' });
      setCancelSendSms(false);
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
        send_sms: cancelSendSms && smsStatus.available,
        bulk: cancelBulk,
      });
      if (!res.success) {
        toast.error(res.error);
        return;
      }
      if (res.sms.requested && res.sms.failed > 0) {
        // The cancellation itself succeeded — but the person who ticked "Wyślij SMS" must know
        // the client was NOT told, so they can phone them.
        toast.error(`${cancelBulk ? `Anulowano ${res.applied.length} wizyt` : 'Wizyta anulowana'}, ale SMS do klienta nie został wysłany (${res.sms.failed}): ${res.sms.error}`);
      } else {
        toast.success(cancelBulk ? `Anulowano ${res.applied.length} wizyt` : 'Wizyta anulowana');
      }
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
      <Modal isOpen={isOpen} onClose={onClose} title={TITLES[step]} size="large" variant="sheet">
        {step === 'list' && (
          <>
            {conflicts.length === 0 ? (
              <p style={{ color: 'var(--color-success)', fontSize: '0.8125rem', marginBottom: '1rem' }}>Wszystkie konflikty rozwiązane — możesz zatwierdzić wniosek.</p>
            ) : (
              <p style={{ color: 'var(--color-ink-subtle)', fontSize: '0.8125rem', marginBottom: '1rem' }}>
                Zatwierdzenie tej nieobecności koliduje z poniższymi wizytami klientów. Zmień stylistę, termin albo anuluj każdą z nich. „Zatwierdź mimo to” zostawia
                nierozwiązane wizyty do automatycznego anulowania 48 h przed terminem (z SMS do klienta).
              </p>
            )}
            {conflicts.length > 0 && isMobile && (
              <ul className="crm-conflicts">
                {conflicts.map((c) => (
                  <li key={c.appointment_id} className="crm-conflict">
                    <div className="crm-conflict-when">
                      {formatPeriodPhone({ date_from: c.date, date_to: c.date, time_from: c.start_time.slice(0, 5), time_to: c.end_time.slice(0, 5) })}
                    </div>
                    <div className="crm-conflict-who">{c.client_name ?? '—'}</div>
                    <div className="ab-card-meta">{c.service_name ?? '—'}</div>
                    <div className="crm-conflict-actions crm-conflict-actions--3">
                      <Button variant="secondary" icon="person_search" onClick={() => openReassign(c)}>
                        Stylista
                      </Button>
                      <Button variant="secondary" icon="edit_calendar" onClick={() => openReschedule(c)}>
                        Termin
                      </Button>
                      {isCancellable(c) && (
                        <Button
                          variant={armedCancelId === c.appointment_id ? 'danger' : 'secondary'}
                          icon="event_busy"
                          disabled={cancellingId !== null}
                          isLoading={cancellingId === c.appointment_id}
                          loadingText="…"
                          onClick={() => quickCancel(c)}
                        >
                          {armedCancelId === c.appointment_id ? 'Na pewno?' : 'Anuluj'}
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {conflicts.length > 0 && !isMobile && (
              <div className="table-container">
                <table className="refined-table crm-table">
                  <colgroup>
                    <col className="crm-col-date" />
                    <col className="crm-col-time" />
                    <col />
                    <col />
                    <col className="crm-col-actions" />
                  </colgroup>
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
                        <td title={c.client_name ?? undefined}>{c.client_name ?? '—'}</td>
                        <td title={c.service_name ?? undefined}>{c.service_name ?? '—'}</td>
                        <td className="cell-actions">
                          <div className="action-icons">
                            <button type="button" className="action-icon-btn" title="Zmień stylistę" aria-label="Zmień stylistę" onClick={() => openReassign(c)}>
                              <Icon name="person_search" />
                            </button>
                            <button type="button" className="action-icon-btn" title="Zmień termin" aria-label="Zmień termin" onClick={() => openReschedule(c)}>
                              <Icon name="edit_calendar" />
                            </button>
                            {isCancellable(c) && (
                              <button
                                type="button"
                                className={`action-icon-btn danger crm-cancel-btn${armedCancelId === c.appointment_id ? ' is-armed' : ''}`}
                                title={armedCancelId === c.appointment_id ? 'Kliknij ponownie, aby anulować wizytę' : 'Anuluj wizytę'}
                                aria-label={armedCancelId === c.appointment_id ? 'Potwierdź anulowanie wizyty' : 'Anuluj wizytę'}
                                disabled={cancellingId !== null}
                                onClick={() => quickCancel(c)}
                              >
                                <Icon name="event_busy" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Resolved conflicts — every resolution moves its row from the table above into
                this one, so the combined height stays put. */}
            <hr className="crm-separator" />
            <div className="crm-history-head">Historia rozwiązań</div>
            {resolutions.length === 0 ? (
              <p className="crm-history-empty">Brak rozwiązanych konfliktów.</p>
            ) : isMobile ? (
              <ul className="crm-conflicts">
                {resolutions.map((r) => {
                  const sms = resolutionSms?.[smsTypeFor(r)];
                  const marked = smsMarked.has(r.appointment_id);
                  return (
                    <li key={r.id} className="crm-conflict">
                      <div className="crm-conflict-when">
                        {formatPeriodPhone({ date_from: r.date, date_to: r.date, time_from: r.start_time, time_to: r.end_time })}
                      </div>
                      <div className="crm-conflict-who">{r.client_name ?? '—'}</div>
                      <div className="ab-card-meta">
                        {RESOLUTION_TYPE_LABEL[r.resolution_type] ?? r.resolution_type} · {resolutionDetail(r)}
                      </div>
                      <div className="crm-conflict-actions crm-conflict-actions--1">
                        <Button
                          variant="secondary"
                          icon={marked ? 'check' : 'send'}
                          className={`crm-msg-btn${marked ? ' is-marked' : ''}`}
                          disabled={!sms?.available}
                          aria-pressed={marked}
                          title={sms?.available ? undefined : sms?.reason}
                          onClick={() => toggleSms(r.appointment_id)}
                        >
                          {marked ? 'Wiadomość zaplanowana' : 'Wyślij wiadomość'}
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="table-container">
                <table className="refined-table crm-table">
                  <colgroup>
                    <col className="crm-col-date" />
                    <col className="crm-col-time" />
                    <col />
                    <col />
                    <col />
                    <col className="crm-col-actions" />
                  </colgroup>
                  <thead>
                    <tr>
                      <th>Data</th>
                      <th>Godzina</th>
                      <th>Klient</th>
                      <th>Usługa</th>
                      <th>Rozwiązanie</th>
                      <th style={{ textAlign: 'right' }}>Akcje</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resolutions.map((r) => {
                      const sms = resolutionSms?.[smsTypeFor(r)];
                      const marked = smsMarked.has(r.appointment_id);
                      const detail = `${RESOLUTION_TYPE_LABEL[r.resolution_type] ?? r.resolution_type}: ${resolutionDetail(r)}`;
                      const meta = [r.resolved_by_name, r.resolved_at].filter(Boolean).join(' · ');
                      return (
                        <tr key={r.id}>
                          <td>{r.date}</td>
                          <td>
                            {r.start_time} – {r.end_time}
                          </td>
                          <td title={r.client_name ?? undefined}>{r.client_name ?? '—'}</td>
                          <td title={r.service_name ?? undefined}>{r.service_name ?? '—'}</td>
                          <td title={meta ? `${detail}\n${meta}` : detail}>{detail}</td>
                          <td className="cell-actions">
                            <div className="action-icons">
                              <button
                                type="button"
                                className={`action-icon-btn crm-msg-btn${marked ? ' is-marked' : ''}`}
                                title={!sms?.available ? sms?.reason || 'SMS niedostępny' : marked ? 'Wiadomość zaplanowana — kliknij, aby cofnąć' : 'Wyślij wiadomość'}
                                aria-label="Wyślij wiadomość"
                                aria-pressed={marked}
                                disabled={!sms?.available}
                                onClick={() => toggleSms(r.appointment_id)}
                              >
                                <Icon name="send" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {smsMarked.size > 0 && (
              <p className="crm-sms-note" role="status">
                Zaznaczone wiadomości ({smsMarked.size}) trafią do kolejki SMS po zatwierdzeniu wniosku.
              </p>
            )}

            <div className={`form-actions crm-actions${conflicts.length === 0 ? ' crm-actions--resolved' : ''}`}>
              <Button variant="primary" className="crm-act-approve" disabled={conflicts.length > 0 || approving !== null} isLoading={approving === 'true'} loadingText="Zatwierdzanie…" onClick={handleTrueApprove}>
                Zatwierdź wniosek i rozwiąż konflikty
              </Button>
              {/* "Mimo to" only means something while conflicts remain: with none left
                  the primary button is the one honest way to approve. */}
              {conflicts.length > 0 && (
                <Button variant="danger" className="crm-act-force" disabled={approving !== null} isLoading={approving === 'force'} loadingText="Zatwierdzanie…" onClick={handleForceApprove}>
                  Zatwierdź mimo to
                </Button>
              )}
              <Button variant="secondary" className="crm-act-reject" onClick={onReject}>
                Odrzuć
              </Button>
              <Button variant="secondary" className="crm-act-cancel" onClick={onClose}>
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
                {isMobile ? (
                  <ul className="crm-candidates">
                    {candidates.map((c) => (
                      <li key={c.employee_id}>
                        <label className={`crm-candidate-card${selectedCandidate === c.employee_id ? ' selected' : ''}`}>
                          <input type="radio" name="reassign-candidate" checked={selectedCandidate === c.employee_id} onChange={() => setSelectedCandidate(c.employee_id)} />
                          <span className="crm-candidate-text">
                            <span className="crm-candidate-name">{c.name}</span>
                            <span className="crm-candidate-pos">{c.position ?? '—'}</span>
                          </span>
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
                        </label>
                      </li>
                    ))}
                  </ul>
                ) : (
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
                )}
                <label className="crm-checkbox-row">
                  <input type="checkbox" checked={reassignBulk} onChange={(e) => setReassignBulk(e.target.checked)} />
                  Zastosuj wybór do wszystkich pozostałych konfliktów tego pracownika
                </label>
              </>
            )}
            <div className="form-actions crm-actions crm-actions--steps">
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
            {smsStatus.available ? (
              <label className="crm-checkbox-row">
                <input type="checkbox" checked={cancelSendSms} onChange={(e) => setCancelSendSms(e.target.checked)} />
                Wyślij SMS do klienta (informacja o odwołaniu + link do rezerwacji)
              </label>
            ) : (
              <p role="status" style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)', marginBottom: '0.75rem' }}>
                Klient nie dostanie SMS-a o odwołaniu. {smsStatus.reason} Poinformuj go telefonicznie.
              </p>
            )}
            <label className="crm-checkbox-row">
              <input type="checkbox" checked={cancelBulk} onChange={(e) => setCancelBulk(e.target.checked)} />
              Anuluj też wszystkie pozostałe skonfliktowane wizyty tego pracownika
            </label>
            <div className="form-actions crm-actions crm-actions--steps">
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
            <div className="form-actions crm-actions crm-actions--steps">
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

    </>
  );
}
