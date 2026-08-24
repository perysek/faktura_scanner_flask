import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './ServicesListPage.css';
import { useApiData } from '../../lib/useApiData';
import { servicesApi } from '../../lib/api/services';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button, ButtonLink } from '../../components/ui/Button';
import { SelectField } from '../../components/ui/form';
import { PriceHistorySparkline } from './PriceHistorySparkline';
import { useEscapeBack } from '../../lib/a11y/useEscapeBack';
import { useEscapeClose } from '../../lib/a11y/useEscapeClose';
import type { CompatibleAddon } from '../../types/service';

function fmtDate(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('pl-PL', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

/**
 * Usługa — szczegóły. Ported 1:1 z templates/services/view.html: podstawowe
 * info, historia cen w `<details>` (RBAC `service_prices`, sparkline
 * rysowany dopiero po rozwinięciu — Chart.js liczy 0×0 w zwiniętym elemencie),
 * kompatybilne mikrousługi (tylko dla usług głównych — mechanika oryginału:
 * dodanie/usunięcie idzie przez pobranie reguł DANEJ mikrousługi i PUT całej
 * listy `main_service_ids`, nie osobny endpoint add/remove).
 */
export function ServiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const serviceId = Number(id);
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const auth = useAuth();
  const canSeePriceHistory = auth.hasModuleAccess('service_prices');
  // Backend's `can_edit_price_history` is role-based, not module-based (routes'
  // own config.auth_config.can_edit_service_price_history) — mirrored via the
  // same helper exposed on AuthContext's user role, not a module permission.
  const canEditPriceHistory = auth.user?.role === 'superuser' || auth.user?.role === 'admin';
  useEscapeBack('/uslugi');

  const serviceState = useApiData(() => servicesApi.get(serviceId), [serviceId]);
  const service = serviceState.data;

  const [historyOpen, setHistoryOpen] = useState(false);
  const historyState = useApiData(() => (canSeePriceHistory ? servicesApi.priceHistory(serviceId) : Promise.resolve([])), [serviceId, canSeePriceHistory]);

  const [addons, setAddons] = useState<CompatibleAddon[] | null>(null);
  const [allAddons, setAllAddons] = useState<CompatibleAddon[]>([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedAddonId, setSelectedAddonId] = useState('');

  async function loadAddons() {
    try {
      const list = await servicesApi.compatibleAddons(serviceId, true);
      setAddons(list);
    } catch {
      setAddons([]);
    }
  }

  async function loadAllAddonOptions(compatibleIds: Set<number>) {
    try {
      const all = await servicesApi.allAddonServices();
      setAllAddons(all.filter((a) => a.is_active && !compatibleIds.has(a.id)));
    } catch {
      /* non-critical */
    }
  }

  useEffect(() => {
    if (service?.service_type === 'main') {
      loadAddons();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [service?.service_type, serviceId]);

  function toggleAddForm() {
    if (!showAddForm) loadAllAddonOptions(new Set((addons ?? []).map((a) => a.id)));
    setShowAddForm((v) => !v);
    setSelectedAddonId('');
  }
  // Escape = "Anuluj" the inline "Dodaj mikrousługę" form — claims the key so
  // the page's own useEscapeBack('/uslugi') doesn't fire instead.
  useEscapeClose(showAddForm, toggleAddForm);

  async function addCompatibleAddon() {
    const addonId = parseInt(selectedAddonId, 10);
    if (!addonId) {
      toast.warning('Proszę wybrać mikrousługę');
      return;
    }
    try {
      const rules = await servicesApi.addonRules(addonId);
      const currentMainIds = rules.map((r) => r.main_service_id);
      if (currentMainIds.includes(serviceId)) {
        toast.warning('Ta mikrousługa jest już przypisana');
        return;
      }
      await servicesApi.setCompatibility(addonId, [...currentMainIds, serviceId]);
      setShowAddForm(false);
      await loadAddons();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem');
    }
  }

  async function removeCompatibleAddon(addonId: number) {
    const ok = await confirm({ title: 'Usuń mikrousługę', message: 'Czy na pewno chcesz usunąć tę mikrousługę z listy kompatybilnych?', confirmText: 'Usuń' });
    if (!ok) return;
    try {
      const rules = await servicesApi.addonRules(addonId);
      const newMainIds = rules.map((r) => r.main_service_id).filter((mid) => mid !== serviceId);
      await servicesApi.setCompatibility(addonId, newMainIds);
      await loadAddons();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem');
    }
  }

  async function handleDeactivate() {
    if (!service) return;
    const ok = await confirm({
      title: 'Dezaktywacja usługi',
      message: `Czy na pewno chcesz dezaktywować usługę "${service.name}"?`,
      confirmText: 'Dezaktywuj',
    });
    if (!ok) return;
    try {
      const result = await servicesApi.delete(serviceId);
      toast.success(result.message);
      navigate('/uslugi');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd dezaktywacji');
    }
  }

  async function handleDeleteHistoryEntry(entryId: number, isOpen: boolean) {
    const ok = await confirm({
      title: 'Usuń wpis historii cen',
      message: isOpen
        ? 'To jest aktualna cena usługi. Po usunięciu poprzednia cena z historii zostanie przywrócona jako bieżąca cena usługi. Kontynuować?'
        : 'Czy na pewno usunąć ten wpis z historii cen?',
      confirmText: 'Usuń',
    });
    if (!ok) return;
    try {
      const result = await servicesApi.deletePriceHistoryEntry(serviceId, entryId);
      toast.success(result.message);
      if (result.reopened) {
        serviceState.reload();
      }
      historyState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się usunąć wpisu');
    }
  }

  if (serviceState.loading || !service) {
    return (
      <div className="refined-page service-detail-page">
        <p className="empty-text">Ładowanie…</p>
      </div>
    );
  }

  const history = historyState.data ?? [];

  return (
    <div className="refined-page service-detail-page animate-fade-up">
      <header style={{ marginBottom: '2rem' }}>
        <h1 className="page-title">{service.name}</h1>
        <p className="page-subtitle">
          {service.category} <span style={{ color: 'var(--color-border)' }}>|</span>{' '}
          <span className={`type-badge ${service.service_type}`}>{service.service_type === 'addon' ? 'Dodatkowa' : 'Główna'}</span>{' '}
          <span className={`status-badge ${service.is_active ? 'active' : 'inactive'}`}>{service.is_active ? 'Aktywna' : 'Nieaktywna'}</span>
        </p>
      </header>

      <div className="form-card">
        <h2 className="section-title">Informacje podstawowe</h2>
        <div className="field-grid">
          <div>
            <label className="field-label">Nazwa</label>
            <p className="field-value">{service.name}</p>
          </div>
          <div>
            <label className="field-label">Kategoria</label>
            <p className="field-value">{service.category}</p>
          </div>
          <div>
            <label className="field-label">Typ usługi</label>
            <p className="field-value">{service.service_type === 'addon' ? 'Dodatkowa (mikrousługa)' : 'Główna'}</p>
          </div>
        </div>
      </div>

      <div className="form-card">
        <h2 className="section-title">Cena i czas</h2>
        <div className="field-grid">
          <div>
            <label className="field-label">Cena</label>
            <p className="field-value">{service.formatted_price}</p>
          </div>
          <div>
            <label className="field-label">Czas trwania</label>
            <p className="field-value">{service.formatted_duration}</p>
          </div>
        </div>
      </div>

      <div className="form-card">
        <h2 className="section-title">Dodatkowe informacje</h2>
        <label className="field-label">Opis</label>
        <p className={`field-value${!service.description ? ' empty' : ''}`}>{service.description || 'Brak opisu'}</p>
      </div>

      {canSeePriceHistory && (
        <details className="price-history-panel" open={historyOpen} onToggle={(e) => setHistoryOpen((e.target as HTMLDetailsElement).open)}>
          <summary>
            Historia cen
            {!historyState.loading && <span className="badge-count">{history.length}</span>}
          </summary>
          <div style={{ paddingBottom: '1rem' }}>
            {historyState.loading ? (
              <p style={{ padding: '1.5rem 0', color: 'var(--color-ink-subtle)', fontSize: '0.8125rem' }}>Wczytywanie historii…</p>
            ) : history.length === 0 ? (
              <div className="empty-state" style={{ padding: '1.5rem 1rem' }}>
                <p className="empty-text">Brak zarejestrowanych zmian cen</p>
              </div>
            ) : (
              <div>
                {historyOpen && (
                  <div className="price-history-chart-wrap">
                    <PriceHistorySparkline history={history} />
                  </div>
                )}
                <div className="table-container" style={{ maxHeight: '360px' }}>
                <table className="refined-table">
                  <thead>
                    <tr>
                      <th>Data od</th>
                      <th>Data do</th>
                      <th style={{ textAlign: 'right' }}>Cena</th>
                      <th>Powód</th>
                      <th>Zmienił</th>
                      {canEditPriceHistory && <th style={{ textAlign: 'right' }}>Akcje</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((h) => {
                      const isOpenEntry = !h.effective_to;
                      return (
                        <tr key={h.id}>
                          <td>{isOpenEntry ? <span className="price-current-badge">aktualnie</span> : fmtDate(h.effective_from)}</td>
                          <td>{h.effective_to ? fmtDate(h.effective_to) : <span className="price-current-badge">aktualnie</span>}</td>
                          <td style={{ textAlign: 'right', fontWeight: 500 }}>
                            {new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(h.price)} {h.currency}
                          </td>
                          <td>{h.change_reason || <span style={{ color: 'var(--color-ink-subtle)' }}>—</span>}</td>
                          <td>{h.changed_by_name || <span style={{ color: 'var(--color-ink-subtle)' }}>—</span>}</td>
                          {canEditPriceHistory && (
                            <td style={{ textAlign: 'right' }}>
                              <button type="button" className="ph-del-btn" title="Usuń wpis" onClick={() => handleDeleteHistoryEntry(h.id, isOpenEntry)}>
                                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                              </button>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>
              </div>
            )}
          </div>
        </details>
      )}

      {service.service_type === 'main' && (
        <div className="form-card">
          <h2 className="section-title">Kompatybilne mikrousługi</h2>
          {!addons ? (
            <p className="empty-text">Ładowanie…</p>
          ) : addons.length === 0 ? (
            <div className="empty-state">
              <p className="empty-text">Brak przypisanych mikrousług</p>
            </div>
          ) : (
            <div style={{ marginBottom: '1.5rem' }}>
              {addons.map((addon) => (
                <div key={addon.id} className="addon-item">
                  <div className="addon-info">
                    <span className="type-badge addon">Dodatkowa</span>
                    <div>
                      <div className="addon-name">{addon.name}</div>
                      <div style={{ display: 'flex', gap: '1rem', marginTop: '0.25rem' }}>
                        <span className="addon-price">{addon.formatted_price || `${addon.price} zł`}</span>
                        <span className="addon-duration">{addon.formatted_duration || `${addon.duration_minutes} min`}</span>
                      </div>
                    </div>
                  </div>
                  <button type="button" className="addon-remove-btn" onClick={() => removeCompatibleAddon(addon.id)}>
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Usuń
                  </button>
                </div>
              ))}
            </div>
          )}

          <div style={{ borderTop: '1px solid var(--color-border-subtle)', paddingTop: '1.5rem' }}>
            {!showAddForm ? (
              <Button variant="secondary" icon="add" onClick={toggleAddForm}>
                Dodaj mikrousługę
              </Button>
            ) : (
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: '220px' }}>
                  <SelectField
                    label="Wybierz mikrousługę"
                    id="addon-select"
                    placeholder={allAddons.length === 0 ? 'Wszystkie mikrousługi już przypisane' : '-- Wybierz --'}
                    options={allAddons.map((a) => ({ value: String(a.id), label: `${a.name} (${a.formatted_price || `${a.price} zł`})` }))}
                    value={selectedAddonId}
                    onChange={(e) => setSelectedAddonId(e.target.value)}
                  />
                </div>
                <Button variant="primary" onClick={addCompatibleAddon}>
                  Dodaj
                </Button>
                <Button variant="secondary" onClick={toggleAddForm}>
                  Anuluj
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="form-card">
        <div className="action-bar">
          <ButtonLink variant="primary" icon="edit" to={`/uslugi/${service.id}/edytuj`}>
            Edytuj usługę
          </ButtonLink>
          <ButtonLink variant="secondary" icon="arrow_back" to="/uslugi">
            Powrót do listy
          </ButtonLink>
          <Button variant="danger" icon="delete" onClick={handleDeactivate}>
            {service.is_active ? 'Dezaktywuj' : 'Usuń'}
          </Button>
        </div>
      </div>
    </div>
  );
}
