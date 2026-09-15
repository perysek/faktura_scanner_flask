import { useEffect, useRef, useState } from 'react';
import { appointmentsApi } from '../../lib/api/appointments';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import type { AppointmentDetailResponse, AppointmentListItem, AvailableSlot, EmployeeOption } from '../../types/appointment';

export interface RescheduleSheetProps {
  appointment: AppointmentListItem | null;
  isOpen: boolean;
  /** "Zostaw" and the overlay/Escape close path both land here. Since this
   * is a modal over the still-mounted list (not a route navigation), simply
   * closing it already satisfies "back to the list with scroll position and
   * filters preserved" — nothing was ever navigated away from. */
  onClose: () => void;
  employees: EmployeeOption[];
  /** Reload the host page's data after a successful reschedule. */
  onRescheduled: () => void;
}

function minutesBetween(start: string, end: string): number {
  const [sh, sm] = start.slice(0, 5).split(':').map(Number);
  const [eh, em] = end.slice(0, 5).split(':').map(Number);
  return eh * 60 + em - (sh * 60 + sm);
}

/**
 * TASK5 — opened by a swipe-left gesture on a card (MobileWizytyCalendarView)
 * or the desktop list's hover "Przełóż wizytę" button (WizytyListPage).
 * Progressive-reveal flow: date → (employees with >=30min free that day) →
 * (07:45-21:15/15-min slot grid sized to the visit's own duration, gray for
 * anything shorter than that) → "Przepisz" commits via
 * `appointmentsApi.rescheduleAppointment()` — freezes this appointment as
 * 'rescheduled' (frees its slot) and clones it onto the new date/time/
 * employee. Client, notes and services are never sent: the backend always
 * copies them from the original (client-unchanged is a hard invariant of
 * the reschedule workflow, not just a UI convention). Only reachable for
 * `scheduled`/`confirmed` appointments — see the swipe-gesture and
 * list-button guards at the call sites.
 */
export function RescheduleSheet({ appointment, isOpen, onClose, employees, onRescheduled }: RescheduleSheetProps) {
  const toast = useToast();

  const [detail, setDetail] = useState<AppointmentDetailResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [date, setDate] = useState('');
  const [employeeOptions, setEmployeeOptions] = useState<EmployeeOption[] | null>(null);
  const [employeeOptionsLoading, setEmployeeOptionsLoading] = useState(false);
  const [employeeId, setEmployeeId] = useState<number | null>(null);

  const [slots, setSlots] = useState<AvailableSlot[] | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<AvailableSlot | null>(null);

  const [submitting, setSubmitting] = useState(false);

  const detailToken = useRef(0);
  const empToken = useRef(0);
  const slotToken = useRef(0);

  // Fresh state every time the sheet opens for a (possibly different) card —
  // and the full detail fetch every step below depends on.
  useEffect(() => {
    if (!isOpen || !appointment) return;
    const token = ++detailToken.current;
    setDetail(null);
    setDetailLoading(true);
    setDate('');
    setEmployeeOptions(null);
    setEmployeeId(null);
    setSlots(null);
    setSelectedSlot(null);
    appointmentsApi
      .get(appointment.id)
      .then((res) => {
        if (detailToken.current !== token) return;
        setDetail(res);
      })
      .catch(() => {
        if (detailToken.current !== token) return;
        toast.error('Nie udało się wczytać szczegółów wizyty');
        onClose();
      })
      .finally(() => {
        if (detailToken.current === token) setDetailLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, appointment?.id]);

  // Date chosen → which employees actually have room that day (>=30min,
  // independent of this visit's own duration — a coarse "worth listing at
  // all" floor, same 07:45-21:15 window as the slot grid below it so the
  // two steps never disagree about what "available" means).
  useEffect(() => {
    if (!date || !detail || !appointment) return;
    const token = ++empToken.current;
    setEmployeeOptionsLoading(true);
    setEmployeeId(null);
    setSlots(null);
    setSelectedSlot(null);
    Promise.all(
      employees.map((e) =>
        appointmentsApi
          .slotsGrid({ employee_id: e.id, date, duration: 30, exclude_appointment_id: appointment.id })
          .then((res) => (res.some((s) => s.available) ? e : null))
          .catch(() => null),
      ),
    ).then((results) => {
      if (empToken.current !== token) return;
      setEmployeeOptions(results.filter((e): e is EmployeeOption => e !== null));
      setEmployeeOptionsLoading(false);
    });
  }, [date, detail, appointment, employees]);

  // Employee chosen → full 07:45-21:15/15-min grid, sized to THIS visit's
  // real duration (not the 30min floor above), unavailable ones kept (not
  // filtered out) so they render grayed instead of missing.
  useEffect(() => {
    if (!date || !employeeId || !detail || !appointment) return;
    const token = ++slotToken.current;
    setSlotsLoading(true);
    setSelectedSlot(null);
    const duration = detail.appointment.total_duration;
    appointmentsApi
      .slotsGrid({ employee_id: employeeId, date, duration, exclude_appointment_id: appointment.id })
      .then((res) => {
        if (slotToken.current !== token) return;
        setSlots(res);
      })
      .catch(() => {
        if (slotToken.current !== token) return;
        setSlots([]);
      })
      .finally(() => {
        if (slotToken.current === token) setSlotsLoading(false);
      });
  }, [date, employeeId, detail, appointment]);

  async function submitReschedule() {
    if (!appointment || !detail || !employeeId || !date || !selectedSlot) return;
    setSubmitting(true);
    try {
      await appointmentsApi.rescheduleAppointment(appointment.id, {
        new_date: date,
        new_start_time: selectedSlot.start_time,
        new_employee_id: employeeId,
      });
      toast.success('Wizyta przepisana');
      onRescheduled();
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd przepisania wizyty');
    } finally {
      setSubmitting(false);
    }
  }

  if (!isOpen || !appointment) return null;

  const todayStr = new Date().toISOString().slice(0, 10);
  const currentDurationLabel = detail ? `${minutesBetween(detail.appointment.start_time, detail.appointment.end_time || detail.appointment.start_time)} min` : '';

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Przepisz wizytę" size="large">
      {detailLoading || !detail ? (
        <p className="empty-text">Ładowanie szczegółów wizyty…</p>
      ) : (
        <>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)', marginBottom: '1rem' }}>
            {appointment.client_name || '—'} — obecny termin: {appointment.appointment_date} {appointment.start_time.slice(0, 5)}
            {detail.appointment.total_duration ? ` (${detail.appointment.total_duration} min)` : currentDurationLabel && ` (${currentDurationLabel})`}
          </p>

          <div style={{ marginBottom: '0.75rem' }}>
            <label className="field-label" htmlFor="reschedule-date">
              Nowa data
            </label>
            <input id="reschedule-date" type="date" className="form-input" min={todayStr} value={date} onChange={(e) => setDate(e.target.value)} />
          </div>

          {date && (
            <div className="reschedule-reveal" style={{ marginBottom: '0.75rem' }}>
              <label className="field-label" htmlFor="reschedule-employee">
                Pracownik
              </label>
              {employeeOptionsLoading ? (
                <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)' }}>Sprawdzam dostępność pracowników…</p>
              ) : employeeOptions && employeeOptions.length === 0 ? (
                <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)' }}>Brak dostępnych pracowników tego dnia.</p>
              ) : (
                <select id="reschedule-employee" className="form-select" value={employeeId ?? ''} onChange={(e) => setEmployeeId(e.target.value === '' ? null : Number(e.target.value))}>
                  <option value="">Wybierz pracownika</option>
                  {(employeeOptions ?? []).map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.full_name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {employeeId && (
            <div className="reschedule-reveal">
              <span className="field-label">Godzina</span>
              {slotsLoading ? (
                <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)' }}>Ładowanie wolnych terminów…</p>
              ) : slots === null || slots.length === 0 ? (
                <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)' }}>Brak terminów w tym oknie godzinowym.</p>
              ) : (
                <div className="reschedule-slot-grid">
                  {slots.map((s) => (
                    <button
                      key={s.start_time}
                      type="button"
                      className={`reschedule-slot-btn${selectedSlot?.start_time === s.start_time ? ' selected' : ''}`}
                      disabled={!s.available}
                      onClick={() => setSelectedSlot(s)}
                    >
                      {s.start_time}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="form-actions">
            <Button variant="secondary" onClick={onClose}>
              Zostaw
            </Button>
            <Button variant="primary" disabled={!selectedSlot || submitting} isLoading={submitting} loadingText="Zapisywanie…" onClick={submitReschedule}>
              Przepisz
            </Button>
          </div>
        </>
      )}
    </Modal>
  );
}
