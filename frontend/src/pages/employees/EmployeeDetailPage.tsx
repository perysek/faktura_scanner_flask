import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './EmployeesListPage.css';
import { useApiData } from '../../lib/useApiData';
import { employeesApi } from '../../lib/api/employees';
import { employeeServicesApi } from '../../lib/api/employeeServices';
import { formyZatrudnieniaApi } from '../../lib/api/formyZatrudnienia';
import { servicesApi } from '../../lib/api/services';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { formatDate, formatPLN } from '../../lib/format';
import { useEscapeBack } from '../../lib/a11y/useEscapeBack';
import { useEscapeClose } from '../../lib/a11y/useEscapeClose';
import type { BalanceAdjustment } from '../../types/employee';
import type { Service } from '../../types/service';

const DAY_NAMES: Record<string, string> = { mon: 'Pon', tue: 'Wt', wed: 'Śr', thu: 'Czw', fri: 'Pt', sat: 'Sob', sun: 'Nd' };
const DAY_ORDER = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];

function balanceBarColor(status: string): string {
  if (status === 'exceeded') return 'var(--color-error)';
  if (status === 'warning') return '#c2410c';
  return 'var(--color-success)';
}

function employmentStatusLabel(status: string): string {
  if (status === 'active') return 'Aktywny';
  if (status === 'on_leave') return 'Na urlopie';
  if (status === 'terminated') return 'Zwolniony';
  return status;
}

function skillBadgeStyle(rating: number): { background: string; color: string } {
  if (rating >= 4) return { background: 'rgba(45,106,79,0.1)', color: 'var(--color-success)' };
  if (rating >= 3) return { background: 'rgba(234,88,12,0.08)', color: '#c2410c' };
  return { background: 'rgba(0,0,0,0.05)', color: 'var(--color-ink-muted)' };
}

/**
 * Pracownik — szczegóły. Ported 1:1 z templates/employees/view.html: dane
 * osobowe, wynagrodzenie, bilanse nieobecności (paski + historia korekt na
 * żądanie), umiejętności/specjalizacje, harmonogram, przypisane usługi
 * (inline formularz dodawania — ten sam mechanizm co oryginał: pobierz
 * WSZYSTKIE aktywne usługi, odfiltruj już przypisane po stronie klienta).
 * Zakładki "Analizy i wyniki" (5 zakładek, 8+ wykresów Chart.js, heatmapa,
 * radar) ŚWIADOMIE odłożone — patrz implementation-log.md, porównywalny
 * zakres do osobno śledzonego modułu "Analityka".
 */
export function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const employeeId = Number(id);
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  useEscapeBack('/pracownicy');

  const employeeState = useApiData(() => employeesApi.get(employeeId), [employeeId]);
  const employee = employeeState.data;

  // forma_zatrudnienia_id → nazwa. Employee.get(id) doesn't join the name in
  // (unlike the Jinja route, which passed a separate `forma_nazwa` context
  // var) — resolved client-side from the same forma list the edit form uses.
  const formyState = useApiData(() => formyZatrudnieniaApi.listFull(), []);
  const formaNazwa = employee?.forma_zatrudnienia_id ? formyState.data?.find((f) => f.id === employee.forma_zatrudnienia_id)?.nazwa : null;

  const balancesState = useApiData(() => employeesApi.getBalances(employeeId), [employeeId]);
  const balances = balancesState.data ?? [];

  const [adjOpen, setAdjOpen] = useState(false);
  const [adjustments, setAdjustments] = useState<BalanceAdjustment[] | null>(null);
  const [adjLoading, setAdjLoading] = useState(false);

  async function toggleAdjHistory() {
    const willOpen = !adjOpen;
    setAdjOpen(willOpen);
    if (willOpen && adjustments === null) {
      setAdjLoading(true);
      try {
        setAdjustments(await employeesApi.getBalanceAdjustments(employeeId));
      } catch {
        setAdjustments([]);
      } finally {
        setAdjLoading(false);
      }
    }
  }

  const servicesState = useApiData(() => employeeServicesApi.list(employeeId), [employeeId]);
  const assignedServices = servicesState.data ?? [];

  const [showAddForm, setShowAddForm] = useState(false);
  const [availableServices, setAvailableServices] = useState<Service[]>([]);
  const [newServiceId, setNewServiceId] = useState('');
  const [newCustomPrice, setNewCustomPrice] = useState('');
  const [newCommission, setNewCommission] = useState('');
  const [newDuration, setNewDuration] = useState('');
  const [assigning, setAssigning] = useState(false);

  function resetAssignForm() {
    setNewServiceId('');
    setNewCustomPrice('');
    setNewCommission('');
    setNewDuration('');
  }

  async function loadAvailableServices() {
    try {
      const all = await servicesApi.list({ activeOnly: true });
      const assignedIds = new Set(assignedServices.map((s) => s.service_id));
      setAvailableServices(all.filter((s) => !assignedIds.has(s.id)));
    } catch {
      toast.warning('Nie udało się załadować listy usług');
    }
  }

  function toggleAddForm() {
    if (!showAddForm) {
      loadAvailableServices();
    } else {
      toast.info('Anulowano dodawanie usługi');
    }
    setShowAddForm((v) => !v);
    resetAssignForm();
  }

  // Escape = "Anuluj" the inline "Dodaj usługę" form — claims the key so the
  // page's own useEscapeBack('/pracownicy') below doesn't fire instead (see
  // useEscapeClose's docstring for why a raw navigate binding alone isn't
  // enough here).
  useEscapeClose(showAddForm, toggleAddForm);

  async function handleAssignService() {
    if (!newServiceId) {
      toast.warning('Wybierz usługę');
      return;
    }
    setAssigning(true);
    try {
      await employeeServicesApi.assign(employeeId, {
        service_id: parseInt(newServiceId, 10),
        ...(newCustomPrice ? { custom_price: parseFloat(newCustomPrice) } : {}),
        ...(newCommission ? { commission_rate: parseFloat(newCommission) } : {}),
        ...(newDuration ? { duration_override: parseInt(newDuration, 10) } : {}),
      });
      toast.success('Usługa została przypisana');
      setShowAddForm(false);
      resetAssignForm();
      servicesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd przypisania usługi');
    } finally {
      setAssigning(false);
    }
  }

  async function handleRemoveService(esId: number) {
    const ok = await confirm({ title: 'Usuń przypisanie', message: 'Czy na pewno chcesz usunąć przypisanie tej usługi?', confirmText: 'Usuń' });
    if (!ok) return;
    try {
      await employeeServicesApi.remove(employeeId, esId);
      toast.success('Przypisanie zostało usunięte');
      servicesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania przypisania');
    }
  }

  async function handleDeactivate() {
    if (!employee) return;
    const isActive = employee.is_active;
    const ok = await confirm({
      title: isActive ? 'Dezaktywacja pracownika' : 'Usuń pracownika',
      message: `Czy na pewno chcesz ${isActive ? 'dezaktywować' : 'usunąć'} pracownika "${employee.full_name}"?`,
      confirmText: isActive ? 'Dezaktywuj' : 'Usuń',
    });
    if (!ok) return;
    try {
      const result = await employeesApi.deactivate(employeeId);
      toast.success(result.message);
      navigate('/pracownicy');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd dezaktywacji');
    }
  }

  if (employeeState.loading || !employee) {
    return (
      <div className="refined-page employee-detail-page">
        <p className="empty-text">Ładowanie…</p>
      </div>
    );
  }

  const initials = `${employee.first_name.charAt(0)}${employee.last_name.charAt(0)}`.toUpperCase();
  const badge = !employee.is_active
    ? { cls: 'inactive', label: 'Nieaktywny' }
    : employee.employment_status === 'on_leave'
      ? { cls: 'on-leave', label: 'Na urlopie' }
      : employee.employment_status === 'terminated'
        ? { cls: 'terminated', label: 'Zwolniony' }
        : { cls: 'active', label: 'Aktywny' };

  const skillEntries = Object.entries(employee.skills ?? {});
  const specs = employee.specializations ?? [];
  const schedule = employee.work_schedule ?? {};
  const hasSchedule = Object.keys(schedule).length > 0;

  return (
    <div className="refined-page employee-detail-page animate-fade-up">
      <header className="page-header">
        <div>
          {employee.photo_path ? (
            <img src={employee.photo_path} alt={employee.full_name} className="employee-avatar-large" style={{ objectFit: 'cover' }} />
          ) : (
            <div className="employee-avatar-large">{initials}</div>
          )}
          <h1 className="page-title">{employee.full_name}</h1>
          <p className="page-subtitle">
            {employee.position || 'Pracownik'} <span className={`status-badge ${badge.cls}`}>{badge.label}</span>
          </p>
        </div>
        <div className="page-header-actions">
          <ButtonLink variant="primary" icon="edit" small to={`/pracownicy/${employee.id}/edytuj`}>
            Edytuj
          </ButtonLink>
        </div>
      </header>

      {/* Dane osobowe */}
      <div className="refined-card">
        <h2 className="section-title">Dane osobowe</h2>
        <div className="emp-field-grid emp-field-grid-2">
          <div>
            <label className="emp-field-label">Imię</label>
            <p className="emp-field-value">{employee.first_name}</p>
          </div>
          <div>
            <label className="emp-field-label">Nazwisko</label>
            <p className="emp-field-value">{employee.last_name}</p>
          </div>
          <div>
            <label className="emp-field-label">Telefon</label>
            <p className={`emp-field-value${!employee.phone ? ' empty' : ''}`}>{employee.phone || 'Brak danych'}</p>
          </div>
          <div>
            <label className="emp-field-label">Email</label>
            <p className={`emp-field-value${!employee.email ? ' empty' : ''}`}>{employee.email || 'Brak danych'}</p>
          </div>
          <div>
            <label className="emp-field-label">Data zatrudnienia</label>
            <p className={`emp-field-value${!employee.hire_date ? ' empty' : ''}`}>{employee.hire_date ? formatDate(employee.hire_date) : 'Brak danych'}</p>
          </div>
          <div>
            <label className="emp-field-label">Status zatrudnienia</label>
            <p className="emp-field-value">{employmentStatusLabel(employee.employment_status)}</p>
          </div>
          {formaNazwa && (
            <div>
              <label className="emp-field-label">Forma zatrudnienia</label>
              <p className="emp-field-value">{formaNazwa}</p>
            </div>
          )}
        </div>
      </div>

      {/* Wynagrodzenie */}
      <div className="refined-card">
        <h2 className="section-title">Wynagrodzenie</h2>
        <div className="emp-field-grid emp-field-grid-2">
          <div>
            <label className="emp-field-label">Wynagrodzenie podstawowe</label>
            <p className={`emp-field-value${employee.base_salary == null ? ' empty' : ''}`}>{employee.base_salary != null ? formatPLN(employee.base_salary) : 'Brak danych'}</p>
          </div>
          <div>
            <label className="emp-field-label">Prowizja</label>
            <p className={`emp-field-value${employee.commission_rate == null ? ' empty' : ' highlight'}`}>{employee.commission_rate != null ? `${employee.commission_rate}%` : 'Brak danych'}</p>
          </div>
          <div>
            <label className="emp-field-label">Koszt pracodawcy (ZUS/podatki)</label>
            <p className="emp-field-value">
              <span className="status-badge" style={{ background: 'rgba(37,99,235,0.08)', color: 'var(--color-status-scheduled)' }}>
                {(employee.employer_cost_rate * 100).toFixed(1)}%
              </span>
            </p>
          </div>
          <div>
            <label className="emp-field-label">Maks. wizyt dziennie</label>
            <p className="emp-field-value">{employee.max_appointments_per_day}</p>
          </div>
        </div>
      </div>

      {/* Bilanse nieobecności */}
      <div className="refined-card">
        <div className="section-header">
          <h2 className="section-title">Bilanse nieobecności</h2>
        </div>
        {balancesState.loading ? (
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)' }}>Ładowanie bilansu…</p>
        ) : balances.length === 0 ? (
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)' }}>Brak śledzonych kategorii nieobecności.</p>
        ) : (
          <div style={{ marginTop: '1rem' }}>
            {balances.map((b) => {
              const pct = Math.min(b.pct || 0, 100);
              const unitL = b.unit === 'hours' ? 'godz.' : 'dni';
              const limitStr = b.has_limit ? b.limit : '∞';
              const usedStr = b.net_used.toFixed(b.unit === 'hours' ? 1 : 0);
              return (
                <div key={b.category_id} style={{ marginBottom: '1rem' }}>
                  <div className="balance-row-top">
                    <span style={{ fontSize: '0.8125rem', fontWeight: 500 }}>{b.category_name}</span>
                  </div>
                  <div className="balance-bar-track">
                    <div className="balance-bar-fill" style={{ width: `${pct}%`, background: balanceBarColor(b.status) }} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: '0.25rem' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--color-ink-subtle)' }}>
                      {b.has_limit ? `${b.pct.toFixed(1)}%` : 'Brak limitu'} — okres od {b.period_start || ''}
                    </span>
                    <span style={{ fontSize: '0.8125rem', color: 'var(--color-ink-subtle)', fontVariantNumeric: 'tabular-nums' }}>
                      {usedStr} / {limitStr} {unitL}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {adjOpen && (
          <div style={{ marginTop: '1rem', borderTop: '1px solid var(--color-border-subtle)', paddingTop: '1rem' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-ink-subtle)', marginBottom: '0.5rem' }}>Historia korekt bilansu</div>
            <div className="scroll-thin" style={{ maxHeight: '280px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
              <thead>
                <tr>
                  {['Kategoria', 'Korekta', 'Powód', 'Kto', 'Kiedy'].map((h) => (
                    <th
                      key={h}
                      style={{
                        textAlign: 'left',
                        padding: '0.25rem 0.5rem',
                        fontSize: '0.6875rem',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        color: 'var(--color-ink-subtle)',
                        position: 'sticky',
                        top: 0,
                        zIndex: 1,
                        background: 'var(--color-surface-elevated)',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {adjLoading ? (
                  <tr>
                    <td colSpan={5} style={{ padding: '0.5rem', color: 'var(--color-ink-subtle)' }}>
                      Ładowanie…
                    </td>
                  </tr>
                ) : !adjustments || adjustments.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ padding: '0.5rem', color: 'var(--color-ink-subtle)' }}>
                      Brak korekt.
                    </td>
                  </tr>
                ) : (
                  adjustments.map((a) => (
                    <tr key={a.id}>
                      <td style={{ padding: '0.375rem 0.5rem' }}>{a.category_name}</td>
                      <td style={{ padding: '0.375rem 0.5rem', fontVariantNumeric: 'tabular-nums' }}>
                        {a.delta_value > 0 ? '+' : ''}
                        {a.delta_value.toFixed(1)}
                      </td>
                      <td style={{ padding: '0.375rem 0.5rem' }}>{a.reason}</td>
                      <td style={{ padding: '0.375rem 0.5rem', color: 'var(--color-ink-subtle)' }}>{a.created_by_name || '—'}</td>
                      <td style={{ padding: '0.375rem 0.5rem', color: 'var(--color-ink-subtle)' }}>{a.created_at ? new Date(a.created_at).toLocaleDateString('pl-PL') : '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            </div>
          </div>
        )}
        <div style={{ marginTop: '0.75rem' }}>
          <Button variant="secondary" small icon="history" onClick={toggleAdjHistory}>
            Historia korekt
          </Button>
        </div>
      </div>

      {/* Umiejętności i specjalizacje */}
      {(skillEntries.length > 0 || specs.length > 0) && (
        <div className="refined-card">
          <h2 className="section-title">Umiejętności i specjalizacje</h2>
          {skillEntries.length > 0 && (
            <div style={{ marginBottom: '1.25rem' }}>
              <label className="emp-field-label" style={{ marginBottom: '0.75rem', display: 'block' }}>
                Umiejętności
              </label>
              <div className="skill-chip-list">
                {skillEntries.map(([name, rating]) => (
                  <span key={name} className="status-badge" style={skillBadgeStyle(rating)}>
                    {name} — {rating}/5
                  </span>
                ))}
              </div>
            </div>
          )}
          {specs.length > 0 && (
            <div>
              <label className="emp-field-label" style={{ marginBottom: '0.75rem', display: 'block' }}>
                Specjalizacje
              </label>
              <div className="spec-chip-list">
                {specs.map((s) => (
                  <span key={s} style={{ display: 'inline-flex', alignItems: 'center', padding: '0.25rem 0.75rem', background: 'rgba(37,99,235,0.08)', color: 'var(--color-status-scheduled)', borderRadius: '2px', fontSize: '0.75rem', fontWeight: 500 }}>
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Harmonogram pracy */}
      {hasSchedule && (
        <div className="refined-card">
          <h2 className="section-title">Harmonogram pracy</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '0.75rem' }}>
            {DAY_ORDER.map((dayKey) => {
              const working = dayKey in schedule;
              return (
                <div key={dayKey} className={`schedule-day-card ${working ? 'working' : 'off'}`}>
                  <div
                    style={{
                      fontSize: '0.6875rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      letterSpacing: '0.06em',
                      color: working ? 'var(--color-success)' : 'var(--color-ink-subtle)',
                      marginBottom: '0.25rem',
                    }}
                  >
                    {DAY_NAMES[dayKey]}
                  </div>
                  <div style={{ fontSize: working ? '0.8125rem' : '0.75rem', color: working ? 'var(--color-ink)' : 'var(--color-ink-subtle)' }}>{working ? schedule[dayKey] : 'wolny'}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Przypisane usługi */}
      <div className="refined-card">
        <div className="section-header">
          <h2 className="section-title">Przypisane usługi</h2>
          <Button variant="secondary" small icon={showAddForm ? 'remove' : 'add'} onClick={toggleAddForm}>
            {showAddForm ? 'Anuluj' : 'Dodaj usługę'}
          </Button>
        </div>

        {showAddForm && (
          <div className="add-service-form">
            <div className="assign-form-row">
              <div>
                <label>Usługa</label>
                <select className="form-select" value={newServiceId} onChange={(e) => setNewServiceId(e.target.value)}>
                  <option value="">{availableServices.length === 0 ? 'Wszystkie usługi już przypisane' : 'Wybierz usługę...'}</option>
                  {availableServices.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.formatted_price}, {s.formatted_duration})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Cena indyw. (PLN)</label>
                <input className="form-input" type="number" step="0.01" min={0} placeholder="domyślna" value={newCustomPrice} onChange={(e) => setNewCustomPrice(e.target.value)} />
              </div>
              <div>
                <label>Prowizja (%)</label>
                <input className="form-input" type="number" step="0.1" min={0} max={100} placeholder="domyślna" value={newCommission} onChange={(e) => setNewCommission(e.target.value)} />
              </div>
              <div>
                <label>Czas (min)</label>
                <input className="form-input" type="number" step={5} min={5} placeholder="domyślny" value={newDuration} onChange={(e) => setNewDuration(e.target.value)} />
              </div>
              <div>
                <Button variant="primary" small isLoading={assigning} loadingText="Dodawanie…" onClick={handleAssignService}>
                  Dodaj
                </Button>
              </div>
            </div>
          </div>
        )}

        {servicesState.loading ? (
          <p className="empty-text" style={{ padding: '2rem', textAlign: 'center' }}>
            Ładowanie…
          </p>
        ) : assignedServices.length === 0 ? (
          <div className="empty-state">
            <Icon name="content_cut" className="empty-icon" />
            <p className="empty-text">Brak przypisanych usług</p>
          </div>
        ) : (
          <div className="table-container" style={{ maxHeight: '420px' }}>
          <table className="refined-table stack-cards">
            <thead>
              <tr>
                <th>Usługa</th>
                <th>Cena</th>
                <th>Prowizja</th>
                <th>Czas</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {assignedServices.map((svc) => {
                const isCustom = svc.custom_price != null;
                const price = svc.effective_price != null ? svc.effective_price.toFixed(2) : '0.00';
                return (
                  <tr key={svc.id}>
                    <td className="cell-name">
                      <div style={{ fontWeight: 500 }}>{svc.service_name}</div>
                      {svc.service_category && <div style={{ fontSize: '0.75rem', color: 'var(--color-ink-subtle)' }}>{svc.service_category}</div>}
                    </td>
                    <td data-label="Cena">
                      <span className={isCustom ? 'price-custom' : 'price-default'}>
                        {price} zł{isCustom ? ' *' : ''}
                      </span>
                    </td>
                    <td data-label="Prowizja">{svc.effective_commission != null ? `${svc.effective_commission.toFixed(1)}%` : '—'}</td>
                    <td data-label="Czas">{svc.effective_duration != null ? `${svc.effective_duration} min` : '—'}</td>
                    <td className="cell-actions">
                      <button type="button" className="action-link-sm" onClick={() => handleRemoveService(svc.id)}>
                        Usuń
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* Notatki */}
      {employee.notes && (
        <div className="refined-card">
          <h2 className="section-title">Notatki</h2>
          <p className="emp-field-value">{employee.notes}</p>
        </div>
      )}

      {/* Analizy i wyniki — świadomie odłożone, patrz komentarz na górze pliku */}
      <div className="refined-card">
        <h2 className="section-title">Analizy i wyniki</h2>
        <div className="analytics-deferred-note">Szczegółowe analizy (przychody, wizyty, umiejętności, satysfakcja) będą dostępne wkrótce — moduł w przygotowaniu.</div>
      </div>

      {/* Akcje */}
      <div className="refined-card">
        <div className="action-bar">
          <ButtonLink variant="primary" icon="edit" to={`/pracownicy/${employee.id}/edytuj`}>
            Edytuj pracownika
          </ButtonLink>
          <ButtonLink variant="secondary" icon="arrow_back" to="/pracownicy">
            Powrót do listy
          </ButtonLink>
          <Button variant="danger" icon="delete" onClick={handleDeactivate}>
            {employee.is_active ? 'Dezaktywuj' : 'Usuń'}
          </Button>
        </div>
      </div>
    </div>
  );
}
