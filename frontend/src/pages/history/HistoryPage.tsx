import { useEffect, useMemo, useState } from 'react';
import './HistoryPage.css';
import { historyApi } from '../../lib/api/history';
import { useToast } from '../../components/feedback/ToastProvider';
import type { HistoryEntry } from '../../types/history';

/** A tab groups one or more audit `entity_type`s; `types: []` means "all". Related
 * entity types (e.g. client + client_preference) share a tab so the bar stays short. */
const ENTITY_TABS: Array<{ id: string; label: string; types: string[] }> = [
  { id: 'all', label: 'Wszystkie', types: [] },
  { id: 'invoice', label: 'Faktury', types: ['invoice'] },
  { id: 'import', label: 'Import', types: ['import'] },
  { id: 'appointment', label: 'Wizyty', types: ['appointment'] },
  { id: 'client', label: 'Klienci', types: ['client', 'client_preference'] },
  { id: 'employee', label: 'Pracownicy', types: ['employee', 'employee_service'] },
  { id: 'absence', label: 'Nieobecności', types: ['absence', 'absence_limit', 'absence_adjustment', 'absence_category'] },
  { id: 'service', label: 'Usługi', types: ['service', 'service_category'] },
  { id: 'seller', label: 'Dostawcy', types: ['seller', 'seller_password'] },
  { id: 'system', label: 'System', types: ['user', 'role', 'sms'] },
  { id: 'login', label: 'Logowania', types: ['login'] },
];

const ENTITY_LABELS: Record<string, string> = {
  invoice: 'Faktura',
  appointment: 'Wizyta',
  client: 'Klient',
  client_preference: 'Preferencja klienta',
  employee: 'Pracownik',
  employee_service: 'Usługa pracownika',
  service: 'Usługa',
  service_category: 'Kategoria usług',
  seller: 'Dostawca',
  seller_password: 'Hasło PDF',
  import: 'Import',
  login: 'Logowanie',
  absence: 'Nieobecność',
  absence_limit: 'Limit urlopu',
  absence_adjustment: 'Korekta salda',
  absence_category: 'Kategoria nieobecności',
  user: 'Użytkownik',
  role: 'Rola',
  sms: 'SMS',
};

const ACTION_LABELS: Record<string, { label: string; className: string }> = {
  CREATE: { label: 'Dodano', className: 'hx-action-create' },
  CREATE_MANUAL: { label: 'Dodano ręcznie', className: 'hx-action-create' },
  UPDATE: { label: 'Edytowano', className: 'hx-action-update' },
  DELETE: { label: 'Usunięto', className: 'hx-action-delete' },
  DELETE_PERMANENT: { label: 'Usunięto trwale', className: 'hx-action-delete' },
  RESTORE: { label: 'Przywrócono', className: 'hx-action-restore' },
  IMPORT: { label: 'Import', className: 'hx-action-import' },
  LOGIN: { label: 'Zalogowano', className: 'hx-action-login' },
  LOGIN_FAILED: { label: 'Błąd login', className: 'hx-action-login-failed' },
  LOGOUT: { label: 'Wylogowano', className: 'hx-action-logout' },
  PASSWORD_RESET_REQUESTED: { label: 'Prośba reset hasła', className: 'hx-action-login' },
  PASSWORD_RESET: { label: 'Reset hasła', className: 'hx-action-login' },
  STATUS_CHANGE: { label: 'Status', className: 'hx-action-status' },
  STATUS_CHANGED: { label: 'Status', className: 'hx-action-status' },
  COMPLETE: { label: 'Zakończono', className: 'hx-action-complete' },
  PRICE_CHANGE: { label: 'Zmiana ceny', className: 'hx-action-price-change' },
  APPROVE: { label: 'Zatwierdzono', className: 'hx-action-complete' },
  APPROVE_FORCED: { label: 'Zatwierdzono wymuszenie', className: 'hx-action-complete' },
  REJECT: { label: 'Odrzucono', className: 'hx-action-delete' },
  CANCEL: { label: 'Anulowano', className: 'hx-action-cancel' },
  CANCEL_APPROVED: { label: 'Anulowano zatwierdzoną', className: 'hx-action-cancel' },
  CANCEL_APPROVED_OWN: { label: 'Anulowano własną', className: 'hx-action-cancel' },
  SMS_SENT: { label: 'Wysłano SMS', className: 'hx-action-sms' },
  CLIENT_RATING: { label: 'Ocena klienta', className: 'hx-action-sms' },
  CLIENT_CONFIRMATION: { label: 'Potwierdzenie klienta', className: 'hx-action-sms' },
};

function formatTimestamp(timestamp: string | null): { date: string; time: string } {
  if (!timestamp) return { date: '—', time: '' };
  const d = new Date(timestamp);
  const date = `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getFullYear()).slice(-2)}`;
  const time = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  return { date, time };
}

/** Historia zdarzeń — audit log across every entity type, filterable by tab.
 * Ported from templates/history/list_refined.html — backend
 * (`GET /api/history`, routes/api_routes.py) was already fully JSON, no
 * server changes. The API response key is `timestamp` (AuditRepository.
 * get_all() renames the DB's `changed_at` column to `timestamp` in the row
 * dict it returns), matching the legacy page's `entry.timestamp` read. */
export function HistoryPage() {
  const toast = useToast();
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');

  useEffect(() => {
    historyApi
      .list()
      .then(setEntries)
      .catch(() => toast.error('Nie udało się wczytać historii'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: entries.length };
    for (const tab of ENTITY_TABS) {
      if (tab.types.length) c[tab.id] = entries.filter((e) => tab.types.includes(e.entity_type)).length;
    }
    return c;
  }, [entries]);

  const visible = useMemo(() => {
    const tab = ENTITY_TABS.find((t) => t.id === activeTab);
    return tab && tab.types.length ? entries.filter((e) => tab.types.includes(e.entity_type)) : entries;
  }, [entries, activeTab]);

  return (
    <div className="refined-page history-page fade-in">
      <header className="page-header">
        <h1 className="page-title">Historia zdarzeń</h1>
      </header>

      <div className="hx-tab-bar">
        {ENTITY_TABS.map((tab) => (
          <button key={tab.id} type="button" className={`hx-tab-btn${activeTab === tab.id ? ' active' : ''}`} onClick={() => setActiveTab(tab.id)}>
            {tab.label} <span className="hx-tab-count">{loading ? '—' : (counts[tab.id] ?? 0)}</span>
          </button>
        ))}
      </div>

      <div className="table-container">
        <div className="hx-table-scroll-wrapper">
          <table className="refined-table" style={{ flexShrink: 0 }}>
            <colgroup>
              <col className="hx-col-timestamp" />
              <col className="hx-col-entity-type" />
              <col className="hx-col-action" />
              <col className="hx-col-entity-label" />
              <col className="hx-col-field" />
              <col className="hx-col-old" />
              <col className="hx-col-new" />
              <col className="hx-col-user" />
            </colgroup>
            <thead>
              <tr>
                <th>Data i czas</th>
                <th>Moduł</th>
                <th>Akcja</th>
                <th>Obiekt</th>
                <th>Pole</th>
                <th className="hx-col-old">Było</th>
                <th>Zmieniono na</th>
                <th>Użytkownik</th>
              </tr>
            </thead>
          </table>

          <div className="hx-tbody-scroll">
            <table className="refined-table">
              <colgroup>
                <col className="hx-col-timestamp" />
                <col className="hx-col-entity-type" />
                <col className="hx-col-action" />
                <col className="hx-col-entity-label" />
                <col className="hx-col-field" />
                <col className="hx-col-old" />
                <col className="hx-col-new" />
                <col className="hx-col-user" />
              </colgroup>
              <tbody>
                {loading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 8 }).map((__, j) => (
                        <td key={j}>
                          <div className="hx-skeleton-bar" style={{ width: `${40 + ((i * 8 + j) % 5) * 8}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : visible.length === 0 ? null : (
                  visible.map((entry, index) => {
                    const ts = formatTimestamp(entry.timestamp);
                    const entityType = entry.entity_type || 'invoice';
                    const actionInfo = ACTION_LABELS[entry.action] ?? { label: entry.action, className: 'hx-action-update' };
                    const label = entry.entity_label || entry.invoice_number || '';
                    return (
                      <tr key={entry.id} className="hx-stagger-row" style={{ animationDelay: `${Math.min(index * 0.015, 0.25)}s` }}>
                        <td>
                          <span className="hx-timestamp-value">
                            <span className="hx-timestamp-date">{ts.date}</span> {ts.time}
                          </span>
                        </td>
                        <td>
                          <span className={`hx-entity-badge hx-entity-${entityType}`}>{ENTITY_LABELS[entityType] ?? entityType}</span>
                        </td>
                        <td>
                          <span className={`hx-action-badge ${actionInfo.className}`}>{actionInfo.label}</span>
                        </td>
                        <td>{label ? <span className="hx-entity-label-text" title={label}>{label}</span> : <span className="hx-value-empty">—</span>}</td>
                        <td>{entry.field_name ? <span className="hx-field-badge">{entry.field_name}</span> : <span className="hx-value-empty">—</span>}</td>
                        <td className="hx-col-old">{entry.old_value ? <span className="hx-value-old">{entry.old_value}</span> : <span className="hx-value-empty">—</span>}</td>
                        <td>{entry.new_value ? <span className="hx-value-new">{entry.new_value}</span> : <span className="hx-value-empty">—</span>}</td>
                        <td>{entry.user_name ? <span className="hx-user-chip" title={entry.user_name}>{entry.user_name.split(' ')[0]}</span> : <span className="hx-value-empty">—</span>}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>

            {!loading && visible.length === 0 && (
              <div className="empty-state">
                <svg className="hx-empty-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 className="hx-empty-title">Brak zdarzeń</h3>
                <p className="empty-text">Zdarzenia pojawią się po wykonaniu operacji w aplikacji.</p>
              </div>
            )}
          </div>
        </div>

        <div className="hx-pagination-bar">
          <span>
            Wyświetlono <span className="hx-pagination-count">{loading ? 0 : visible.length}</span> wpisów
          </span>
        </div>
      </div>
    </div>
  );
}
