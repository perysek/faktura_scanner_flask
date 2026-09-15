import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import './Appointments.css';
import './WizytaFormPage.css';
import { appointmentsApi } from '../../lib/api/appointments';
import { clientsApi } from '../../lib/api/clients';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { FormActions, FormSection, SelectField, TextareaField, TextField } from '../../components/ui/form';
import { useEscapeAction } from '../../lib/a11y/escapeScope';
import { formatPLN } from '../../lib/format';
import { STATUS_LABELS } from '../../types/appointment';
import type { AppointmentFormService, AppointmentService, AppointmentStatus, AvailableSlot } from '../../types/appointment';

export interface WizytaFormPageProps {
  mode: 'create' | 'edit';
}

interface ClientOption {
  id: number;
  label: string;
}

// 'rescheduled' excluded on purpose — it's never a plain status flip, always
// the compound freeze+clone operation behind handleEditSubmit's timing-
// change branch below. Leaving it selectable here would let staff flip an
// appointment straight to 'rescheduled' with no clone ever created.
const STATUS_OPTIONS = (Object.keys(STATUS_LABELS) as AppointmentStatus[])
  .filter((v) => v !== 'rescheduled')
  .map((v) => ({ value: v, label: STATUS_LABELS[v] }));

function todayIso(): string {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
}

/**
 * Wizyta — create/edit. Ported z templates/appointments/{create,edit}.html.
 * Świadomie uproszczone względem oryginału (opisane też w
 * implementation-log.md): klient/pracownik jako zwykły `<select>` zamiast
 * `SearchableSelect` JS-widgetu (natywny select i tak wspiera "wpisz literę,
 * skocz do opcji" — brak dedykowanego React combobox to realne ograniczenie
 * UX przy dużej bazie klientów, nie utrata funkcji); walidacja okna czasowego
 * dla zmiany statusu w edit (np. "za wcześnie na rozpoczęcie") pominięta —
 * to był tylko client-side pre-check dla szybszego feedbacku, serwer i tak
 * odrzuci nieprawidłowe przejście.
 */
export function WizytaFormPage({ mode }: WizytaFormPageProps) {
  const { id } = useParams<{ id: string }>();
  const appointmentId = mode === 'edit' && id ? Number(id) : undefined;
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const auth = useAuth();
  const confirm = useConfirm();

  const [clients, setClients] = useState<ClientOption[]>([]);
  const [employees, setEmployees] = useState<Array<{ id: number; full_name: string; position: string | null }>>([]);
  const [clientId, setClientId] = useState(searchParams.get('client_id') ?? '');
  const [employeeId, setEmployeeId] = useState(searchParams.get('employee_id') ?? '');
  const [status, setStatus] = useState<AppointmentStatus>('scheduled');
  const [date, setDate] = useState(searchParams.get('date') ?? todayIso());
  const [time, setTime] = useState(searchParams.get('start_time')?.slice(0, 5) ?? '');
  const [notes, setNotes] = useState('');

  // Create-mode: main-service checkbox picker + slot grid.
  const [employeeServices, setEmployeeServices] = useState<AppointmentFormService[]>([]);
  const [selectedServiceIds, setSelectedServiceIds] = useState<Set<number>>(new Set());
  const [slots, setSlots] = useState<AvailableSlot[]>([]);

  // Edit-mode: editable services list (main + addon), loaded from GET /appointments/<id>.
  const [currentServices, setCurrentServices] = useState<AppointmentService[]>([]);
  const [availableToAdd, setAvailableToAdd] = useState<AppointmentFormService[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [originalDate, setOriginalDate] = useState<string | null>(null);
  const [originalTime, setOriginalTime] = useState<string | null>(null);
  const [originalStatus, setOriginalStatus] = useState<AppointmentStatus | null>(null);
  const [wasConfirmed, setWasConfirmed] = useState(false);
  const [confirmationStatus, setConfirmationStatus] = useState<'pending' | 'confirmed' | 'declined' | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [timingModal, setTimingModal] = useState<Record<string, unknown> | null>(null);
  const hydratedRef = useRef(false);

  useEffect(() => {
    clientsApi
      .list()
      .then((list) => setClients(list.map((c) => ({ id: c.id, label: `${c.first_name} ${c.last_name}` }))))
      .catch(() => {});
    appointmentsApi.employees().then(setEmployees).catch(() => {});
  }, []);

  // Create-mode: services for the selected employee (main only — addons are
  // added post-creation from the detail page, same as the original).
  useEffect(() => {
    if (mode !== 'create') return;
    if (!employeeId) {
      setEmployeeServices([]);
      setSelectedServiceIds(new Set());
      return;
    }
    appointmentsApi
      .employeeServices(Number(employeeId))
      .then((services) => setEmployeeServices(services.filter((s) => s.service_type === 'main')))
      .catch(() => setEmployeeServices([]));
  }, [mode, employeeId]);

  const createTotals = useMemo(() => {
    let price = 0;
    let duration = 0;
    for (const s of employeeServices) {
      if (selectedServiceIds.has(s.service_id)) {
        price += s.effective_price;
        duration += s.effective_duration;
      }
    }
    return { price, duration };
  }, [employeeServices, selectedServiceIds]);

  // Create-mode: slot grid data for the chosen employee+date. Fires as soon
  // as an employee is picked (using `date`'s already-defaulted-to-today
  // value even before the visitor touches the date field) — a nominal
  // 30-min duration stands in for "no service chosen yet" purely so the
  // grid can already show which slots fall outside the employee's working
  // hours (`within_hours`, independent of service). Re-fires on every
  // date/employee/duration change, so picking services re-checks real
  // conflicts against their actual total duration.
  useEffect(() => {
    if (mode !== 'create' || !employeeId || !date) {
      setSlots([]);
      return;
    }
    let cancelled = false;
    appointmentsApi
      .slotsGrid({
        employee_id: Number(employeeId),
        date,
        duration: createTotals.duration || 30,
        work_start: '07:00',
        work_end: '20:30',
        interval: 30,
      })
      .then((res) => {
        if (cancelled) return;
        setSlots(res);
        const current = res.find((s) => s.start_time.slice(0, 5) === time);
        if (time && (!current || !current.available || !current.within_hours)) setTime('');
      })
      .catch(() => {
        if (!cancelled) setSlots([]);
      });
    return () => {
      cancelled = true;
    };
    // `time` deliberately excluded — read only to clear a slot that just
    // became unbookable, not a trigger to re-fetch (see taken-slots note
    // this replaced).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, employeeId, date, createTotals.duration]);

  // Edit-mode: hydrate from the existing appointment.
  useEffect(() => {
    if (mode !== 'edit' || !appointmentId || hydratedRef.current) return;
    appointmentsApi
      .get(appointmentId)
      .then((detail) => {
        const a = detail.appointment;
        setClientId(String(a.client_id));
        setEmployeeId(String(a.employee_id));
        setStatus(a.status);
        setDate(a.appointment_date);
        setTime(a.start_time.slice(0, 5));
        setNotes(a.notes ?? '');
        setOriginalDate(a.appointment_date);
        setOriginalTime(a.start_time.slice(0, 5));
        setOriginalStatus(a.status);
        setWasConfirmed(a.confirmation_status === 'confirmed');
        setConfirmationStatus(a.confirmation_status);
        setCurrentServices(
          [...detail.main_services, ...detail.addon_services].map((s) => ({
            ...s,
            appointment_service_id: s.appointment_service_id,
            is_addon: s.is_addon,
          })),
        );
        hydratedRef.current = true;
      })
      .catch((err) => toast.error(err instanceof ApiError ? err.message : 'Błąd ładowania wizyty'));
  }, [mode, appointmentId, toast]);

  // Edit-mode: SSE confirmation-status badge.
  useEffect(() => {
    if (mode !== 'edit' || !appointmentId) return;
    const src = new EventSource(appointmentsApi.eventsUrl(appointmentId));
    src.onmessage = (e) => {
      try {
        setConfirmationStatus(JSON.parse(e.data).confirmation_status);
      } catch {
        /* malformed heartbeat/frame — ignore */
      }
    };
    return () => src.close();
  }, [mode, appointmentId]);

  function toggleCreateService(sid: number) {
    setSelectedServiceIds((prev) => {
      const next = new Set(prev);
      if (next.has(sid)) next.delete(sid);
      else next.add(sid);
      return next;
    });
  }

  const editTotals = useMemo(() => {
    const duration = currentServices.reduce((sum, s) => sum + s.duration_minutes, 0);
    const price = currentServices.reduce((sum, s) => sum + s.price_charged, 0);
    return { price, duration };
  }, [currentServices]);

  async function openAddServicePicker() {
    if (!employeeId) return;
    setPickerOpen((v) => !v);
    if (!pickerOpen) {
      const services = await appointmentsApi.employeeServices(Number(employeeId)).catch(() => []);
      const existingIds = new Set(currentServices.map((s) => s.service_id));
      setAvailableToAdd(services.filter((s) => !existingIds.has(s.service_id)));
    }
  }
  function addServiceToEdit(s: AppointmentFormService) {
    setCurrentServices((prev) => [...prev, { service_id: s.service_id, service_name: s.service_name, price_charged: s.effective_price, duration_minutes: s.effective_duration, is_addon: s.service_type === 'addon' }]);
    setAvailableToAdd((prev) => prev.filter((x) => x.service_id !== s.service_id));
    setPickerOpen(false);
  }
  function removeServiceFromEdit(index: number) {
    setCurrentServices((prev) => prev.filter((_, i) => i !== index));
  }

  function backUrl(): string {
    const from = searchParams.get('from');
    const params = new URLSearchParams();
    if (searchParams.get('date')) params.set('date', searchParams.get('date')!);
    if (searchParams.get('employee_id')) params.set('employee_id', searchParams.get('employee_id')!);
    const qs = params.toString() ? `?${params}` : '';
    if (mode === 'edit' && appointmentId) return `/wizyty/${appointmentId}${qs}`;
    if (from === 'calendar') return `/wizyty/kalendarz${qs}`;
    if (from === 'week') return `/wizyty/kalendarz/tydzien${qs}`;
    if (from === 'month') return `/wizyty/kalendarz/miesiac${qs}`;
    return `/wizyty${qs}`;
  }

  async function handleCreateSubmit() {
    if (!clientId || !employeeId || selectedServiceIds.size === 0 || !date || !time) return;
    setIsSubmitting(true);
    try {
      const result = await appointmentsApi.create({
        client_id: Number(clientId),
        employee_id: Number(employeeId),
        service_ids: [...selectedServiceIds],
        appointment_date: date,
        start_time: time,
        notes: notes.trim() || null,
      });
      toast.success('Wizyta zarezerwowana');
      navigate(`/wizyty/${result.appointment_id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd rezerwacji wizyty');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function performEditSave(force: boolean, timingChangeBy?: 'client' | 'salon') {
    if (!appointmentId) return;
    setIsSubmitting(true);
    try {
      await appointmentsApi.update(appointmentId, {
        client_id: Number(clientId),
        employee_id: Number(employeeId),
        status,
        appointment_date: date,
        start_time: time,
        notes: notes.trim() || null,
        services: currentServices.map((s) => ({ service_id: s.service_id, price_charged: s.price_charged, duration_minutes: s.duration_minutes, is_addon: s.is_addon })),
        force,
        timing_change_by: timingChangeBy,
      });
      toast.success('Wizyta zaktualizowana');
      navigate(backUrl());
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Błąd aktualizacji wizyty';
      if (err instanceof ApiError && err.status === 409 && auth.user?.role === 'superuser') {
        setIsSubmitting(false);
        const proceed = await confirm({
          title: 'Konflikt terminu',
          message: `${message} Zapisać mimo konfliktu?`,
          confirmText: 'Zapisz mimo to',
          type: 'warning',
        });
        if (proceed) await performEditSave(true, timingChangeBy);
        return;
      }
      toast.error(message);
      setIsSubmitting(false);
    }
  }

  // A date/time change on a scheduled/confirmed original routes through
  // reschedule_appointment (freeze original + clone) instead of an in-place
  // PUT — see plan §6. Employee/service/notes-only edits, or a timing change
  // on a non-eligible source status, are unaffected: still a plain save.
  async function performReschedule(force: boolean, timingChangeBy?: 'client' | 'salon') {
    if (!appointmentId) return;
    setIsSubmitting(true);
    try {
      const result = await appointmentsApi.rescheduleAppointment(appointmentId, {
        new_date: date,
        new_start_time: time,
        new_employee_id: Number(employeeId),
        notes: notes.trim() || null,
        timing_change_by: timingChangeBy,
        force,
      });
      // reschedule_appointment always clones with the ORIGINAL services
      // verbatim (it has no `services` param, by design — see the service
      // method's docstring). If this submission also edited the services
      // list, that edit needs a second, ordinary save on the new clone so
      // it isn't silently dropped. `status` here is the server's own
      // computed new_status (scheduled, or confirmed when the client
      // requested the move) — never the stale form value, which still
      // reflects the frozen original's status.
      await appointmentsApi.update(result.new_appointment_id, {
        client_id: Number(clientId),
        employee_id: Number(employeeId),
        status: result.new_status,
        appointment_date: date,
        start_time: time,
        notes: notes.trim() || null,
        services: currentServices.map((s) => ({ service_id: s.service_id, price_charged: s.price_charged, duration_minutes: s.duration_minutes, is_addon: s.is_addon })),
      });
      toast.success('Wizyta przepisana');
      navigate(`/wizyty/${result.new_appointment_id}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Błąd przepisania wizyty';
      if (err instanceof ApiError && err.status === 409 && auth.user?.role === 'superuser') {
        setIsSubmitting(false);
        const proceed = await confirm({
          title: 'Konflikt terminu',
          message: `${message} Zapisać mimo konfliktu?`,
          confirmText: 'Zapisz mimo to',
          type: 'warning',
        });
        if (proceed) await performReschedule(true, timingChangeBy);
        return;
      }
      toast.error(message);
      setIsSubmitting(false);
    }
  }

  async function handleEditSubmit() {
    if (!currentServices.length) {
      toast.error('Wizyta musi mieć co najmniej jedną usługę');
      return;
    }
    const timingChanged = originalDate !== null && (date !== originalDate || time !== originalTime);
    const eligibleForReschedule = originalStatus === 'scheduled' || originalStatus === 'confirmed';

    if (timingChanged && eligibleForReschedule) {
      if (wasConfirmed) {
        setTimingModal({});
        return;
      }
      await performReschedule(false);
      return;
    }
    if (timingChanged && wasConfirmed) {
      // Timing changed but the source status isn't reschedule-eligible
      // (e.g. in_progress) — still worth asking who requested it before a
      // plain in-place save, same as before this feature existed.
      setTimingModal({});
      return;
    }
    await performEditSave(false);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (mode === 'create') void handleCreateSubmit();
    else void handleEditSubmit();
  }

  const canSaveCreate = !!(clientId && employeeId && selectedServiceIds.size > 0 && date && time);
  // Grid only becomes clickable once date + employee + at least one service
  // are all chosen — before that, slots still render (so out-of-hours ones
  // already show grayed the moment an employee is picked, per `slots`'
  // effect above), just not selectable.
  const slotGridReady = !!(date && employeeId && selectedServiceIds.size > 0);

  // Create-mode has no <FormActions> (custom summary-card layout instead), so
  // it doesn't get that component's built-in Escape-cancel for free — bound
  // directly here instead, matching the original create.html's own explicit
  // keydown handler (DESIGN.md §11.2). Edit-mode gets it from <FormActions>.
  useEscapeAction(() => navigate(backUrl()), mode === 'create');

  return (
    <div className="refined-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">{mode === 'create' ? 'Nowa wizyta' : `Edytuj wizytę #${appointmentId}`}</h1>
          <p className="page-subtitle">{mode === 'create' ? 'Wypełnij formularz, aby zarezerwować wizytę' : 'Zaktualizuj dane wizyty'}</p>
        </div>
      </header>

      {mode === 'edit' && confirmationStatus === 'confirmed' && <div className="confirm-chip confirm-chip--ok">✓ Klient potwierdził przez SMS</div>}
      {mode === 'edit' && confirmationStatus === 'declined' && <div className="confirm-chip confirm-chip--bad">✕ Klient odmówił przez SMS</div>}

      <div className="appt-form-layout">
        <form onSubmit={handleSubmit}>
          <FormSection legend="Klient i pracownik">
            <SelectField label="Klient" required id="client-select" placeholder="Wybierz klienta..." options={clients.map((c) => ({ value: String(c.id), label: c.label }))} value={clientId} onChange={(e) => setClientId(e.target.value)} />
            <SelectField
              label="Pracownik"
              required
              id="employee-select"
              placeholder="Wybierz pracownika..."
              options={employees.map((e) => ({ value: String(e.id), label: e.position ? `${e.full_name} — ${e.position}` : e.full_name }))}
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
            />
            {mode === 'edit' && <SelectField label="Status" id="status-select" options={STATUS_OPTIONS} value={status} onChange={(e) => setStatus(e.target.value as AppointmentStatus)} />}
          </FormSection>

          <FormSection legend="Data i godzina">
            <TextField label="Data wizyty" required id="appt-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            {mode === 'edit' && <TextField label="Godzina rozpoczęcia" required id="appt-time" type="time" step={900} value={time} onChange={(e) => setTime(e.target.value)} />}
          </FormSection>

          {mode === 'create' ? (
            <div className="time-and-services">
              <div className="form-card time-slot-card">
                <h3 className="card-title">Godzina rozpoczęcia</h3>
                <SlotGrid slots={slots} selected={time} onSelect={setTime} interactive={slotGridReady} />
              </div>
              <div className="form-card services-card">
                <h3 className="card-title">Usługi</h3>
                {!employeeId ? (
                  <p className="svc-empty">Wybierz pracownika, aby zobaczyć dostępne usługi.</p>
                ) : employeeServices.length === 0 ? (
                  <p className="svc-empty">Brak przypisanych usług dla tego pracownika.</p>
                ) : (
                  <div className="svc-picker">
                    {employeeServices.map((s) => (
                      <label key={s.service_id} className="svc-option">
                        <input type="checkbox" checked={selectedServiceIds.has(s.service_id)} onChange={() => toggleCreateService(s.service_id)} />
                        <span className="svc-name">{s.service_name}</span>
                        <span className="svc-dur">{s.effective_duration} min</span>
                        <span className="svc-price">{formatPLN(s.effective_price)}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="form-card">
              <h3 className="card-title">Usługi</h3>
              <ul className="service-list">
                {currentServices.map((s, i) => (
                  <li key={i} className={`service-item${s.is_addon ? ' addon' : ''}`}>
                    <div className="service-item-info">
                      <span className="service-item-name">{s.service_name}</span>
                      <span className={`service-item-badge ${s.is_addon ? 'addon' : 'main'}`}>{s.is_addon ? 'Dodatek' : 'Główna'}</span>
                    </div>
                    <span className="service-item-price">{formatPLN(s.price_charged)}</span>
                    <button type="button" className="btn-remove" onClick={() => removeServiceFromEdit(i)}>
                      Usuń
                    </button>
                  </li>
                ))}
              </ul>
              <div className="add-service-section">
                <Button type="button" variant="secondary" small disabled={!employeeId} onClick={openAddServicePicker}>
                  + Dodaj usługę lub dodatek
                </Button>
                {pickerOpen && (
                  <div className="service-picker">
                    {availableToAdd.length === 0 ? (
                      <p className="svc-empty">Brak dostępnych usług do dodania.</p>
                    ) : (
                      availableToAdd.map((s) => (
                        <div key={s.service_id} className="service-option" onClick={() => addServiceToEdit(s)}>
                          <div className="service-option-info">
                            <span className="service-option-name">{s.service_name}</span>
                            <span className="service-option-meta">
                              {s.effective_duration} min · {formatPLN(s.effective_price)}
                            </span>
                          </div>
                          <button type="button" className="btn-add-service">
                            Dodaj
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
              <div className="summary-box" style={{ marginTop: '1rem' }}>
                <div className="summary-row">
                  <span>Czas trwania:</span>
                  <span>{editTotals.duration} min</span>
                </div>
                <div className="summary-row total">
                  <span>Razem:</span>
                  <span>{formatPLN(editTotals.price)}</span>
                </div>
              </div>
            </div>
          )}

          <FormSection legend="Uwagi">
            <TextareaField label="Uwagi" id="appt-notes" fullWidth rows={3} placeholder="Opcjonalne uwagi do wizyty..." value={notes} onChange={(e) => setNotes(e.target.value)} />
          </FormSection>

          {mode === 'edit' && <FormActions submitLabel="Zapisz zmiany" isLoading={isSubmitting} cancelHref={backUrl()} />}
        </form>

        {mode === 'create' && (
          <div className="summary-card">
            <h3 className="card-title">Podsumowanie</h3>
            <p className="summary-line">
              Klient: <strong>{clients.find((c) => String(c.id) === clientId)?.label ?? '—'}</strong>
            </p>
            <p className="summary-line">
              Pracownik: <strong>{employees.find((e) => String(e.id) === employeeId)?.full_name ?? '—'}</strong>
            </p>
            <p className="summary-line">
              Data: <strong>{date.split('-').reverse().join('.')}</strong>
            </p>
            <p className="summary-line">
              Godzina: <strong>{time || '—'}</strong>
            </p>
            <div className="summary-totals">
              <div className="row">
                <span>Czas trwania</span>
                <span>{createTotals.duration ? `${createTotals.duration} min` : '—'}</span>
              </div>
              <div className="row total">
                <span>Razem</span>
                <span>{formatPLN(createTotals.price)}</span>
              </div>
            </div>
            <Button variant="primary" icon="check" isLoading={isSubmitting} loadingText="Zapisywanie…" disabled={!canSaveCreate} onClick={handleCreateSubmit} style={{ width: '100%', justifyContent: 'center' }}>
              Zarezerwuj wizytę
            </Button>
            <Button type="button" variant="secondary" onClick={() => navigate(backUrl())} style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}>
              Anuluj
            </Button>
          </div>
        )}
      </div>

      {timingModal && (
        <Modal
          isOpen
          onClose={() => setTimingModal(null)}
          title="Zmiana terminu potwierdzonej wizyty"
          footer={
            <>
              <Button
                variant="secondary"
                icon="person"
                disabled={isSubmitting}
                onClick={() => {
                  setTimingModal(null);
                  const eligible = originalStatus === 'scheduled' || originalStatus === 'confirmed';
                  void (eligible ? performReschedule(false, 'client') : performEditSave(false, 'client'));
                }}
              >
                Zmianę zgłosił klient
              </Button>
              <Button
                variant="primary"
                icon="send"
                disabled={isSubmitting}
                onClick={() => {
                  setTimingModal(null);
                  const eligible = originalStatus === 'scheduled' || originalStatus === 'confirmed';
                  void (eligible ? performReschedule(false, 'salon') : performEditSave(false, 'salon'));
                }}
              >
                Salon zmienił termin (wyślij SMS)
              </Button>
            </>
          }
        >
          <p>
            Klient potwierdził tę wizytę przez SMS. Zmieniasz termin na <strong>{date} {time}</strong>.
          </p>
          <p style={{ marginTop: '0.5rem', color: 'var(--color-ink-muted)' }}>Kto zażądał zmiany terminu?</p>
        </Modal>
      )}
    </div>
  );
}

// 07:00-20:30/30-min — must match the work_start/work_end/interval passed
// to `appointmentsApi.slotsGrid` in the effect above, so every label here
// has a same-keyed entry to look up in the fetched `slots` response.
const SLOT_TIMES: string[] = [];
for (let h = 7; h < 21; h++) {
  for (const mi of [0, 30]) {
    SLOT_TIMES.push(`${String(h).padStart(2, '0')}:${String(mi).padStart(2, '0')}`);
  }
}

function SlotGrid({ slots, selected, onSelect, interactive }: { slots: AvailableSlot[]; selected: string; onSelect: (t: string) => void; interactive: boolean }) {
  const slotsByTime = useMemo(() => new Map(slots.map((s) => [s.start_time.slice(0, 5), s])), [slots]);
  return (
    <div className="slot-grid">
      {SLOT_TIMES.map((t) => {
        const info = slotsByTime.get(t);
        // No `info` at all means the fetched grid doesn't cover this start
        // time (e.g. the selected services' total duration wouldn't fit
        // before closing) — treated the same as "taken": disabled, greyed.
        const blocked = !info || !info.available || !info.within_hours;
        const bookable = interactive && !blocked;
        return (
          <button
            key={t}
            type="button"
            className={`slot-btn${blocked ? ' taken' : ''}${selected === t ? ' selected' : ''}`}
            disabled={!bookable}
            onClick={() => onSelect(t)}
          >
            {t}
          </button>
        );
      })}
    </div>
  );
}
