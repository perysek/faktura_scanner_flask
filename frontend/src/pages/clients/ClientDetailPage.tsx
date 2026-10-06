import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import './ClientDetailPage.css';
import { useApiData } from '../../lib/useApiData';
import { clientsApi } from '../../lib/api/clients';
import { lookupsApi } from '../../lib/api/lookups';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { SearchableSelectField, TextareaField } from '../../components/ui/form';
import { Icon } from '../../lib/icons/Icon';
import { VisitNotesSection } from '../../components/visitNotes/VisitNotesSection';
import { formatDate, formatPhone } from '../../lib/format';
import { useEscapeBack } from '../../lib/a11y/useEscapeBack';
import { useIsMobile } from '../appointments/MobileWizytyCalendarView';
import { useHideOnScroll } from '../../lib/useHideOnScroll';

/** Phone history list: this many newest visits, then a "Pokaż wszystkie" button. */
const MOBILE_HISTORY_PREVIEW = 5;

const STATUS_LABELS: Record<string, string> = {
  scheduled: 'Zaplanowana',
  confirmed: 'Potwierdzona',
  in_progress: 'W trakcie',
  completed: 'Zakończona',
  cancelled: 'Anulowana',
  no_show: 'Nieobecność',
  rescheduled: 'Zmieniona',
};
// DESIGN.md §2.9: status/categorical colors are constant tokens across every
// theme. no_show deliberately has no -bg token ("rare/muted state") — render
// it without a tinted background, not a hardcoded rgba fallback.
const STATUS_COLOR_VAR: Record<string, string> = {
  scheduled: 'var(--color-status-scheduled)',
  confirmed: 'var(--color-status-confirmed)',
  in_progress: 'var(--color-status-in-progress)',
  completed: 'var(--color-status-completed)',
  cancelled: 'var(--color-status-cancelled)',
  no_show: 'var(--color-status-no-show)',
  rescheduled: 'var(--color-status-rescheduled)',
};
const STATUS_BG_VAR: Record<string, string> = {
  scheduled: 'var(--color-status-scheduled-bg)',
  confirmed: 'var(--color-status-confirmed-bg)',
  in_progress: 'var(--color-status-in-progress-bg)',
  completed: 'var(--color-status-completed-bg)',
  cancelled: 'var(--color-status-cancelled-bg)',
  no_show: 'transparent',
  rescheduled: 'var(--color-status-rescheduled-bg)',
};

function formatAppointmentDate(dateString: string): string {
  const datePart = dateString.split('T')[0];
  const [y, m, d] = datePart.split('-').map(Number);
  if (!y || !m || !d) return '—';
  return new Date(y, m - 1, d).toLocaleDateString('pl-PL', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatPrice(price: number | null): string {
  if (price == null) return '—';
  return `${price.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} zł`;
}

/**
 * Client detail — ported from templates/clients/view.html
 * (phase-01-pilot-clients.md §1.4): basic/contact/additional info (merge
 * into one card group on mobile), preferences CRUD, appointment history,
 * action bar. `Modals.confirm` → useConfirm(); native confirm() forbidden.
 */
export function ClientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const clientId = Number(id);
  const navigate = useNavigate();
  const auth = useAuth();
  const toast = useToast();
  const confirm = useConfirm();
  const canWrite = auth.hasModuleWrite('clients');
  // History rows open the visit page, which sits behind the `appointments` module.
  const canOpenVisits = auth.hasModuleAccess('appointments');
  const isMobile = useIsMobile(640);
  const mobileBarHidden = useHideOnScroll();
  useEscapeBack('/klienci');

  const clientState = useApiData(() => clientsApi.get(clientId), [clientId]);
  const preferencesState = useApiData(() => clientsApi.preferences(clientId), [clientId]);
  const appointmentsState = useApiData(() => clientsApi.appointmentHistory(clientId, 50), [clientId]);
  const employeesState = useApiData(() => lookupsApi.employees(), []);
  const servicesState = useApiData(() => lookupsApi.services(), []);

  const [showAddForm, setShowAddForm] = useState(false);
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [selectedServiceId, setSelectedServiceId] = useState('');
  const [selectedEmployeeId, setSelectedEmployeeId] = useState('');
  const [prefNotes, setPrefNotes] = useState('');
  const [prefError, setPrefError] = useState<{ field: 'service' | 'employee'; message: string } | null>(null);
  const [filteredServices, setFilteredServices] = useState<Array<{ value: string; label: string }> | null>(null);
  const [filteredEmployees, setFilteredEmployees] = useState<Array<{ value: string; label: string }> | null>(null);

  async function handleEmployeeFilterChange(value: string) {
    setSelectedEmployeeId(value);
    setPrefError(null);
    if (!value) {
      setFilteredServices(null);
      return;
    }
    try {
      const services = await lookupsApi.servicesForEmployee(Number(value));
      setFilteredServices(services.map((s) => ({ value: String(s.service_id), label: s.service_name })));
    } catch {
      // Non-critical — leave the full service list in place.
    }
  }

  async function handleServiceFilterChange(value: string) {
    setSelectedServiceId(value);
    setPrefError(null);
    if (!value) {
      setFilteredEmployees(null);
      return;
    }
    try {
      const employees = await lookupsApi.employeesForService(Number(value));
      setFilteredEmployees(employees.map((e) => ({ value: String(e.employee_id), label: `${e.first_name} ${e.last_name}` })));
    } catch {
      // Non-critical — leave the full employee list in place.
    }
  }

  async function handleAddPreference() {
    if (!selectedServiceId) {
      setPrefError({ field: 'service', message: 'Wybierz usługę' });
      return;
    }
    if (!selectedEmployeeId) {
      setPrefError({ field: 'employee', message: 'Wybierz pracownika' });
      return;
    }
    const existing = preferencesState.data ?? [];
    const isDuplicate = existing.some(
      (p) => p.service_id === Number(selectedServiceId) && p.preferred_employee_id === Number(selectedEmployeeId),
    );
    if (isDuplicate) {
      setPrefError({ field: 'employee', message: 'Ta kombinacja usługi i pracownika już istnieje' });
      return;
    }
    try {
      await clientsApi.addPreference(clientId, {
        service_id: Number(selectedServiceId),
        preferred_employee_id: Number(selectedEmployeeId),
        notes: prefNotes.trim() || null,
      });
      setSelectedServiceId('');
      setSelectedEmployeeId('');
      setPrefNotes('');
      setFilteredServices(null);
      setFilteredEmployees(null);
      setPrefError(null);
      setShowAddForm(false);
      preferencesState.reload();
      toast.success('Preferencja została dodana');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem');
    }
  }

  async function handleRemovePreference(prefId: number) {
    const ok = await confirm({
      title: 'Usuń preferencję',
      message: 'Czy na pewno chcesz usunąć tę preferencję?',
      confirmText: 'Usuń',
    });
    if (!ok) return;
    try {
      await clientsApi.removePreference(clientId, prefId);
      preferencesState.reload();
      toast.success('Preferencja została usunięta');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem');
    }
  }

  async function handleDeleteOrDeactivate() {
    const client = clientState.data;
    if (!client) return;
    const isActive = client.is_active;
    const ok = await confirm({
      title: isActive ? 'Dezaktywacja klienta' : 'Usuń klienta',
      message: `Czy na pewno chcesz ${isActive ? 'dezaktywować' : 'usunąć'} klienta "${client.full_name}"?`,
      confirmText: isActive ? 'Dezaktywuj' : 'Usuń',
    });
    if (!ok) return;
    try {
      await clientsApi.delete(clientId);
      // The delete is soft on the backend (it answers with a restore_url), so offer an undo.
      toast.success(isActive ? 'Klient został dezaktywowany' : 'Klient został usunięty', undefined, {
        label: 'Cofnij',
        onClick: async () => {
          try {
            await clientsApi.restore(clientId);
            toast.success('Klient został przywrócony');
            navigate(`/klienci/${clientId}`);
          } catch (err) {
            toast.error(err instanceof ApiError ? err.message : 'Nie udało się przywrócić klienta');
          }
        },
      });
      navigate('/klienci');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem');
    }
  }

  if (clientState.loading) {
    return (
      <div className="refined-page client-detail-page animate-fade-up">
        <div className="skeleton" style={{ height: '5rem', width: '5rem', borderRadius: '50%', marginBottom: '1rem' }} />
        <div className="skeleton" style={{ height: '2rem', width: '16rem', marginBottom: '2rem' }} />
        <div className="detail-card">
          <div className="skeleton" style={{ height: '8rem' }} />
        </div>
      </div>
    );
  }

  if (clientState.error || !clientState.data) {
    return (
      <div className="refined-page client-detail-page animate-fade-up">
        <p className="empty-text" style={{ color: 'var(--color-error)' }}>
          Błąd ładowania klienta: {clientState.error?.message ?? 'nie znaleziono'}
        </p>
        <Button variant="secondary" style={{ marginTop: '0.75rem' }} onClick={() => navigate('/klienci')}>
          Powrót do listy
        </Button>
      </div>
    );
  }

  const client = clientState.data;
  const initials = `${client.first_name?.[0] ?? '?'}${client.last_name?.[0] ?? ''}`;
  const serviceOptions = filteredServices ?? (servicesState.data ?? []).map((s) => ({ value: String(s.id), label: s.name }));
  const employeeOptions =
    filteredEmployees ?? (employeesState.data ?? []).map((e) => ({ value: String(e.id), label: `${e.first_name} ${e.last_name}` }));

  const history = appointmentsState.data ?? [];
  const shownHistory = isMobile && !showAllHistory ? history.slice(0, MOBILE_HISTORY_PREVIEW) : history;

  return (
    <div className={`refined-page client-detail-page${isMobile ? ' client-detail-page--mobile' : ''} animate-fade-up`}>
      <header className="page-header">
        <div>
          <div className="client-avatar-large">{initials}</div>
          <h1 className="page-title">{client.full_name}</h1>
          <p className="page-subtitle">
            {client.age ? `${client.age} lat` : null}
            {client.age && ' · '}
            <span className={`status-badge ${client.is_active ? 'active' : 'inactive'}`}>{client.is_active ? 'Aktywny' : 'Nieaktywny'}</span>
          </p>
        </div>
        {/* Phone: "Edytuj" lives in the sticky bottom bar instead. */}
        {canWrite && !isMobile && (
          <ButtonLink variant="primary" small icon="edit" to={`/klienci/${client.id}/edytuj`}>
            Edytuj
          </ButtonLink>
        )}
      </header>

      <div className="basic-info-group">
        <div className="detail-card">
          <h2 className="detail-section-title">Dane podstawowe</h2>
          <div className="field-grid field-grid-2 field-grid-pair">
            <div>
              <label className="field-label">Imię</label>
              <p className="field-value">{client.first_name}</p>
            </div>
            <div>
              <label className="field-label">Nazwisko</label>
              <p className="field-value">{client.last_name}</p>
            </div>
          </div>
        </div>

        <div className="detail-card">
          <h2 className="detail-section-title">Dane kontaktowe</h2>
          <div className="field-grid field-grid-2">
            <div>
              <label className="field-label">Telefon</label>
              <p className={`field-value${client.phone ? '' : ' empty'}`}>{client.phone ? formatPhone(client.phone) : 'Brak danych'}</p>
            </div>
            <div>
              <label className="field-label">Email</label>
              <p className={`field-value${client.email ? '' : ' empty'}`}>{client.email ?? 'Brak danych'}</p>
            </div>
          </div>
        </div>

        <div className="detail-card">
          <h2 className="detail-section-title">Informacje dodatkowe</h2>
          <div className="field-grid field-grid-pair">
            <div>
              <label className="field-label">Data urodzenia</label>
              <p className={`field-value${client.date_of_birth ? '' : ' empty'}`}>
                {client.date_of_birth ? `${formatDate(client.date_of_birth)}${client.age ? ` (${client.age} lat)` : ''}` : 'Brak danych'}
              </p>
            </div>
            <div>
              <label className="field-label">Pierwsza wizyta</label>
              <p className={`field-value${client.first_visit_date ? '' : ' empty'}`}>
                {client.first_visit_date ? formatDate(client.first_visit_date) : 'Brak danych'}
              </p>
            </div>
            <div>
              <label className="field-label">Ostatnia wizyta</label>
              <p className={`field-value${client.last_visit_date ? '' : ' empty'}`}>
                {client.last_visit_date ? formatDate(client.last_visit_date) : 'Brak danych'}
              </p>
            </div>
            <div>
              <label className="field-label">Zmienione wizyty</label>
              <p className="field-value">{client.rescheduled_count ?? 0}</p>
            </div>
            <div className="field-wide">
              <label className="field-label">Notatki</label>
              <p className={`field-value${client.notes ? '' : ' empty'}`}>{client.notes ?? 'Brak notatek'}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="detail-card">
        <div className="detail-section-header">
          <h2 className="detail-section-title">Preferencje klienta</h2>
          {canWrite && (
            <Button variant="secondary" small icon="add" className="add-pref-btn" onClick={() => setShowAddForm((v) => !v)}>
              Dodaj preferencję
            </Button>
          )}
        </div>

        {showAddForm && (
          <div className="add-pref-form">
            <div className="pref-form-row">
              <SearchableSelectField
                label="Usługa"
                placeholder="Wybierz usługę..."
                searchPlaceholder="Szukaj usługi…"
                options={serviceOptions}
                value={selectedServiceId}
                onChange={handleServiceFilterChange}
                error={prefError?.field === 'service' ? prefError.message : undefined}
              />
              <SearchableSelectField
                label="Preferowany pracownik"
                placeholder="Wybierz pracownika..."
                searchPlaceholder="Szukaj pracownika…"
                options={employeeOptions}
                value={selectedEmployeeId}
                onChange={handleEmployeeFilterChange}
                error={prefError?.field === 'employee' ? prefError.message : undefined}
              />
              <Button variant="primary" small className="pref-submit" onClick={handleAddPreference}>
                Dodaj
              </Button>
            </div>
            <div className="pref-form-row full">
              <TextareaField
                label="Notatki"
                placeholder="np. Woli ciche środowisko..."
                value={prefNotes}
                onChange={(e) => setPrefNotes(e.target.value)}
              />
            </div>
          </div>
        )}

        {preferencesState.data && preferencesState.data.length > 0 ? (
          isMobile ? (
            // Phone: the table would have to hide its notes + "Usuń" columns, which made
            // preferences impossible to remove — a card per preference keeps all of it.
            <ul className="pref-cards">
              {preferencesState.data.map((pref) => (
                <li key={pref.id} className="pref-card">
                  <div className="pref-card-text">
                    <span className="pref-card-title">
                      {pref.service_name ? `Usługa: ${pref.service_name}` : pref.service_category ? `Kategoria: ${pref.service_category}` : 'Ogólna preferencja'}
                    </span>
                    <span className="pref-card-sub">{pref.employee_name ?? 'Nieznany'}</span>
                    {pref.notes && <span className="pref-card-notes">{pref.notes}</span>}
                  </div>
                  {canWrite && (
                    <button type="button" className="pref-card-remove" aria-label="Usuń preferencję" onClick={() => handleRemovePreference(pref.id)}>
                      Usuń
                    </button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
          <div className="scroll-thin" style={{ maxHeight: '320px' }}>
          <table className="pref-table">
            <thead>
              <tr>
                <th>Typ</th>
                <th>Preferowany pracownik</th>
                <th>Notatki</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {preferencesState.data.map((pref) => (
                <tr key={pref.id}>
                  <td>
                    {pref.service_name ? (
                      <span style={{ fontWeight: 500 }}>Usługa: {pref.service_name}</span>
                    ) : pref.service_category ? (
                      <span style={{ fontWeight: 500 }}>Kategoria: {pref.service_category}</span>
                    ) : (
                      <span style={{ color: 'var(--color-ink-subtle)' }}>Ogólna preferencja</span>
                    )}
                  </td>
                  <td>{pref.employee_name ?? 'Nieznany'}</td>
                  <td style={{ maxWidth: '250px' }}>{pref.notes ?? '—'}</td>
                  <td style={{ textAlign: 'right' }}>
                    {canWrite && (
                      <button type="button" className="action-link-sm" onClick={() => handleRemovePreference(pref.id)}>
                        Usuń
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          )
        ) : (
          <div className="empty-preferences">
            <Icon name="person_search" size="2rem" />
            <div style={{ marginTop: '0.5rem' }}>Brak zdefiniowanych preferencji</div>
          </div>
        )}
      </div>

      <div className="detail-card history-visits-card">
        <div className="detail-section-header">
          <h2 className="detail-section-title">Historia wizyt</h2>
          {appointmentsState.data && appointmentsState.data.length > 0 && (
            <span style={{ fontSize: '0.75rem', color: 'var(--color-ink-subtle)' }}>{appointmentsState.data.length} wizyt łącznie</span>
          )}
        </div>

        {appointmentsState.loading ? (
          <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--color-ink-subtle)', fontSize: '0.875rem' }}>
            Ładowanie historii wizyt...
          </div>
        ) : !appointmentsState.data || appointmentsState.data.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '1.5rem' }}>
            <Icon name="event_busy" size="2rem" />
            <p style={{ color: 'var(--color-ink-subtle)', fontSize: '0.8125rem', marginTop: '0.5rem' }}>Brak historii wizyt</p>
          </div>
        ) : isMobile ? (
          <>
            <ul className="hist-cards">
              {shownHistory.map((a) => {
                const body = (
                  <>
                    <span className="hist-card-when">
                      <strong>{formatAppointmentDate(a.appointment_date)}</strong> · {a.start_time?.slice(0, 5)}–{a.end_time?.slice(0, 5)}
                    </span>
                    <span
                      className="appt-status-pill hist-card-status"
                      style={{ background: STATUS_BG_VAR[a.status] ?? 'rgba(0,0,0,0.05)', color: STATUS_COLOR_VAR[a.status] ?? 'var(--color-ink-muted)' }}
                    >
                      {STATUS_LABELS[a.status] ?? a.status}
                    </span>
                    <span className="hist-card-what">
                      {a.employee_name ?? '—'} · {formatPrice(a.total_price)}
                    </span>
                  </>
                );
                return (
                  <li key={a.id} className="hist-card">
                    {canOpenVisits ? (
                      <Link to={`/wizyty/${a.id}`} className="hist-card-link">
                        {body}
                      </Link>
                    ) : (
                      <div className="hist-card-link hist-card-link--static">{body}</div>
                    )}
                  </li>
                );
              })}
            </ul>
            {!showAllHistory && history.length > MOBILE_HISTORY_PREVIEW && (
              <Button variant="secondary" className="hist-more" onClick={() => setShowAllHistory(true)}>
                Pokaż wszystkie ({history.length})
              </Button>
            )}
          </>
        ) : (
          <div className="scroll-thin" style={{ maxHeight: '420px' }}>
            <table className="appt-table">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Godziny</th>
                  <th>Pracownik</th>
                  <th>Status</th>
                  <th>Kwota</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {appointmentsState.data.map((a) => (
                  // Wizyty is an SPA route (`wizyty/:id`) — row-click mirrors the
                  // "Szczegóły" link; it's only wired up when the caller may open visits.
                  <tr key={a.id} className={canOpenVisits ? 'row-clickable' : undefined} onClick={canOpenVisits ? (e) => {
                    if ((e.target as HTMLElement).closest('a')) return;
                    navigate(`/wizyty/${a.id}`);
                  } : undefined}>
                    <td style={{ fontWeight: 500 }}>{formatAppointmentDate(a.appointment_date)}</td>
                    <td style={{ color: 'var(--color-ink-muted)' }}>
                      {a.start_time?.slice(0, 5)}–{a.end_time?.slice(0, 5)}
                    </td>
                    <td>{a.employee_name ?? '—'}</td>
                    <td>
                      <span
                        className="appt-status-pill"
                        style={{ background: STATUS_BG_VAR[a.status] ?? 'rgba(0,0,0,0.05)', color: STATUS_COLOR_VAR[a.status] ?? 'var(--color-ink-muted)' }}
                      >
                        {STATUS_LABELS[a.status] ?? a.status}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right', color: 'var(--color-ink-muted)' }}>{formatPrice(a.total_price)}</td>
                    <td style={{ textAlign: 'right' }}>
                      {canOpenVisits && (
                        <Link to={`/wizyty/${a.id}`} title="Szczegóły" aria-label="Szczegóły" style={{ color: 'var(--color-status-scheduled)' }}>
                          <Icon name="open_in_new" />
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {auth.hasModuleAccess('appointments') && <VisitNotesSection variant="detail" clientId={clientId} />}

      {isMobile ? (
        <>
          {canWrite && (
            <div className="detail-card client-danger-zone">
              <h2 className="detail-section-title detail-section-title--danger">Strefa ryzyka</h2>
              {client.is_active && <p className="field-value">Klient trafi na listę nieaktywnych.</p>}
              <Button variant="danger" icon="delete" onClick={handleDeleteOrDeactivate}>
                {client.is_active ? 'Dezaktywuj klienta' : 'Usuń klienta'}
              </Button>
            </div>
          )}
          <div className={`mw-bar${mobileBarHidden ? ' mw-bar--hidden' : ''}`}>
            <ButtonLink variant="secondary" icon="arrow_back" to="/klienci">
              Powrót
            </ButtonLink>
            {canWrite && (
              <ButtonLink variant="primary" icon="edit" to={`/klienci/${client.id}/edytuj`}>
                Edytuj
              </ButtonLink>
            )}
          </div>
        </>
      ) : (
        <div className="detail-card">
          <div className="action-bar">
            {canWrite && (
              <ButtonLink variant="primary" icon="edit" to={`/klienci/${client.id}/edytuj`}>
                Edytuj klienta
              </ButtonLink>
            )}
            <ButtonLink variant="secondary" icon="arrow_back" to="/klienci">
              Powrót do listy
            </ButtonLink>
            {canWrite && (
              <Button variant="danger" icon="delete" onClick={handleDeleteOrDeactivate}>
                {client.is_active ? 'Dezaktywuj' : 'Usuń'}
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
