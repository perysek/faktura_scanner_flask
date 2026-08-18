import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './Appointments.css';
import './WizytaDetailPage.css';
import { useApiData } from '../../lib/useApiData';
import { appointmentsApi } from '../../lib/api/appointments';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { formatPLN } from '../../lib/format';
import { empColor } from '../../lib/appointments/employeeColor';
import { StatusChangeModal } from './StatusChangeModal';
import { CompleteVisitModal } from './CompleteVisitModal';
import { STATUS_LABELS, VALID_TRANSITIONS } from '../../types/appointment';
import type { AppointmentFormService, AppointmentStatus } from '../../types/appointment';

function clientInitials(name: string | null): string {
  if (!name) return '—';
  return name.trim().split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase();
}
function fmtDate(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}

/**
 * Wizyta — widok szczegółów. Ported z templates/appointments/view.html.
 * Świadomie pominięte: rozwijana lista "Wyślij SMS" + log SMS (własny moduł
 * Ustawienia SMS, patrz implementation-log.md), `visit-link`/token pracownika
 * (mobilny self-service, `/my-visits`, nie ten frontend).
 */
export function WizytaDetailPage() {
  const { id } = useParams<{ id: string }>();
  const appointmentId = Number(id);
  const navigate = useNavigate();
  const auth = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const canWrite = auth.hasModuleWrite('appointments');

  const detailState = useApiData(() => appointmentsApi.get(appointmentId), [appointmentId]);
  const [statusTarget, setStatusTarget] = useState<AppointmentStatus | null>(null);
  const [completeOpen, setCompleteOpen] = useState(false);
  const [addons, setAddons] = useState<AppointmentFormService[] | null>(null);
  const [selectedScore, setSelectedScore] = useState<number | null>(null);
  const [savingScore, setSavingScore] = useState(false);

  const appt = detailState.data?.appointment;

  useEffect(() => {
    setSelectedScore(appt?.satisfaction_score ?? null);
  }, [appt?.satisfaction_score]);

  useEffect(() => {
    if (detailState.data?.can_add_addon && appointmentId) {
      appointmentsApi.availableAddons(appointmentId).then(setAddons).catch(() => setAddons([]));
    }
  }, [detailState.data?.can_add_addon, appointmentId]);

  async function handleAddAddon(serviceId: number) {
    try {
      await appointmentsApi.addAddon(appointmentId, serviceId);
      toast.success('Mikrousługa dodana');
      detailState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd dodawania usługi');
    }
  }

  async function handleSaveScore() {
    if (!selectedScore) return;
    setSavingScore(true);
    try {
      await appointmentsApi.setSatisfaction(appointmentId, selectedScore);
      toast.success(`Ocena zapisana: ${selectedScore}/5`);
      detailState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu oceny');
    } finally {
      setSavingScore(false);
    }
  }

  async function handleDelete() {
    const ok = await confirm({
      title: 'Usuń wizytę',
      message: `Czy na pewno chcesz usunąć tę wizytę? ${appt?.client_name ? `Klient: ${appt.client_name}.` : ''}`,
      confirmText: 'Usuń',
    });
    if (!ok) return;
    try {
      await appointmentsApi.delete(appointmentId);
      toast.success('Wizyta usunięta');
      navigate('/wizyty');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania wizyty');
    }
  }

  if (detailState.loading) {
    return (
      <div className="refined-page fade-in">
        <p className="empty-text">Ładowanie...</p>
      </div>
    );
  }
  if (detailState.error || !detailState.data || !appt) {
    return (
      <div className="refined-page fade-in">
        <p className="empty-text" style={{ color: 'var(--color-error)' }}>
          Błąd ładowania wizyty: {detailState.error?.message}
        </p>
      </div>
    );
  }

  const { main_services, addon_services, totals } = detailState.data;
  const services = [...main_services, ...addon_services];
  const nextStatuses = VALID_TRANSITIONS[appt.status] ?? [];
  const isNoShowAllowed = (() => {
    const start = new Date(`${appt.appointment_date}T${appt.start_time}`);
    return start.getTime() - Date.now() <= 30 * 60 * 1000;
  })();
  const visibleTransitions = nextStatuses.filter((s) => s !== 'no_show' || isNoShowAllowed);

  return (
    <div className="refined-page appt-detail-page fade-in">
      <header className="appt-hero">
        <a className="appt-hero-avatar" href={`/klienci/${appt.client_id}`} style={{ background: empColor(appt.employee_id) }}>
          {clientInitials(appt.client_name)}
        </a>
        <div className="appt-hero-info">
          <h1 className="page-title">{appt.client_name || `Wizyta #${appointmentId}`}</h1>
          <span className={`status-badge ${appt.status}`}>{STATUS_LABELS[appt.status]}</span>
          <p className="page-subtitle">
            {appt.appointment_date.split('-').reverse().join('.')} · {appt.start_time.slice(0, 5)}–{appt.end_time.slice(0, 5)} · {appt.total_duration} min · {appt.employee_name || '—'}
          </p>
        </div>
        <div className="appt-hero-price">{formatPLN(totals.total_price)}</div>
      </header>

      {appt.confirmation_status === 'confirmed' && <div className="confirm-chip confirm-chip--ok">✓ Klient potwierdził przez SMS</div>}
      {appt.confirmation_status === 'declined' && <div className="confirm-chip confirm-chip--bad">✕ Klient odmówił przez SMS</div>}

      <div className="action-bar">
        {canWrite && appt.status !== 'cancelled' && appt.status !== 'completed' && (
          <ButtonLink variant="secondary" icon="edit" to={`/wizyty/${appointmentId}/edytuj`}>
            Edytuj
          </ButtonLink>
        )}
        {canWrite &&
          visibleTransitions.map((s) =>
            s === 'completed' ? (
              <Button key={s} variant="primary" icon="check_circle" onClick={() => setCompleteOpen(true)}>
                {STATUS_LABELS[s]}
              </Button>
            ) : (
              <Button key={s} variant={s === 'cancelled' ? 'danger' : 'secondary'} onClick={() => setStatusTarget(s)}>
                {STATUS_LABELS[s]}
              </Button>
            ),
          )}
        {canWrite && (
          <Button variant="ghost" icon="delete" onClick={handleDelete}>
            Usuń
          </Button>
        )}
      </div>

      <div className="form-card">
        <h3 className="card-title">Szczegóły</h3>
        <div className="appt-detail-grid">
          <div>
            <p className="form-label">Data</p>
            <p>{fmtDate(appt.appointment_date)}</p>
          </div>
          <div>
            <p className="form-label">Godzina</p>
            <p>
              {appt.start_time.slice(0, 5)} — {appt.end_time.slice(0, 5)}
            </p>
          </div>
          <div>
            <p className="form-label">Pracownik</p>
            <p>{appt.employee_name || '—'}</p>
          </div>
          <div>
            <p className="form-label">Czas trwania</p>
            <p>{appt.total_duration} min</p>
          </div>
        </div>
      </div>

      <div className="form-card">
        <h3 className="card-title">Usługi</h3>
        <ul className="svc-list">
          {services.map((s, i) => (
            <li key={i} className="svc-item">
              <div>
                <span className="svc-name">{s.service_name}</span>
                <span className={`service-item-badge ${s.is_addon ? 'addon' : 'main'}`}>{s.is_addon ? 'Dodatkowa' : 'Główna'}</span>
              </div>
              <span className="svc-price">{formatPLN(s.price_charged)}</span>
            </li>
          ))}
        </ul>
        <div className="summary-box">
          <div className="summary-row">
            <span>Usługi główne:</span>
            <span>{formatPLN(totals.main_total)}</span>
          </div>
          {totals.addon_count > 0 && (
            <div className="summary-row">
              <span>Mikrousługi ({totals.addon_count}):</span>
              <span>{formatPLN(totals.addon_total)}</span>
            </div>
          )}
          <div className="summary-row">
            <span>Prowizja:</span>
            <span>{formatPLN(totals.total_commission)}</span>
          </div>
          <div className="summary-row total">
            <span>Razem:</span>
            <span>{formatPLN(totals.total_price)}</span>
          </div>
        </div>

        {detailState.data.can_add_addon && (
          <div className="add-service-section">
            <label className="form-label">Dodaj mikrousługę</label>
            {!addons ? (
              <p className="empty-text">Ładowanie...</p>
            ) : addons.length === 0 ? (
              <p className="empty-text">Brak dostępnych mikrousług</p>
            ) : (
              <div className="addon-btn-row">
                {addons.map((a) => (
                  <button key={a.service_id} type="button" className="addon-btn" onClick={() => handleAddAddon(a.service_id)}>
                    <Icon name="add" /> {a.service_name} ({formatPLN(a.effective_price)})
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {appt.status === 'completed' ? (
        <div className="form-card">
          <h3 className="card-title">Ocena satysfakcji</h3>
          <div className="satisfaction-stars">
            {[1, 2, 3, 4, 5].map((s) => (
              <button key={s} type="button" className={`star-btn${selectedScore && s <= selectedScore ? ' active' : ''}`} disabled={!canWrite} onClick={() => setSelectedScore(s)}>
                {selectedScore && s <= selectedScore ? '★' : '☆'}
              </button>
            ))}
            <span className="score-label">{selectedScore ? `${selectedScore} / 5 gwiazdek` : 'Brak oceny'}</span>
          </div>
          {canWrite && (
            <Button variant="primary" small disabled={!selectedScore} isLoading={savingScore} loadingText="Zapisywanie…" onClick={handleSaveScore} style={{ marginTop: '0.75rem' }}>
              Zapisz ocenę
            </Button>
          )}
        </div>
      ) : (
        <p className="empty-text">Ocena satysfakcji dostępna po zakończeniu wizyty.</p>
      )}

      {appt.notes && (
        <div className="form-card">
          <h3 className="card-title">Uwagi</h3>
          <p>{appt.notes}</p>
        </div>
      )}

      {statusTarget && (
        <StatusChangeModal
          isOpen
          onClose={() => setStatusTarget(null)}
          appointmentId={appointmentId}
          currentStatus={appt.status}
          fixedStatus={statusTarget}
          onSuccess={() => {
            setStatusTarget(null);
            detailState.reload();
          }}
        />
      )}
      <CompleteVisitModal
        isOpen={completeOpen}
        onClose={() => setCompleteOpen(false)}
        appointmentId={appointmentId}
        onSuccess={() => {
          setCompleteOpen(false);
          detailState.reload();
        }}
      />
    </div>
  );
}
