import { useEffect, useMemo, useState } from 'react';
import './HistoryPage.css';
import { historyApi } from '../../lib/api/history';
import { useToast } from '../../components/feedback/ToastProvider';
import type { HistoryEntityType, HistoryEntry } from '../../types/history';

const ENTITY_TABS: Array<{ type: HistoryEntityType | ''; label: string }> = [
  { type: '', label: 'Wszystkie' },
  { type: 'invoice', label: 'Faktury' },
  { type: 'import', label: 'Import' },
  { type: 'appointment', label: 'Wizyty' },
  { type: 'client', label: 'Klienci' },
  { type: 'employee', label: 'Pracownicy' },
  { type: 'service', label: 'Usługi' },
  { type: 'seller', label: 'Dostawcy' },
  { type: 'login', label: 'Logowania' },
];

const ENTITY_LABELS: Record<string, string> = {
  invoice: 'Faktura',
  appointment: 'Wizyta',
  client: 'Klient',
  employee: 'Pracownik',
  service: 'Usługa',
  seller: 'Dostawca',
  import: 'Import',
  login: 'Logowanie',
};

const ACTION_LABELS: Record<string, { label: string; className: string }> = {
  CREATE: { label: 'Dodano', className: 'hx-action-create' },
  UPDATE: { label: 'Edytowano', className: 'hx-action-update' },
  DELETE: { label: 'Usunięto', className: 'hx-action-delete' },
  IMPORT: { label: 'Import', className: 'hx-action-import' },
  LOGIN: { label: 'Zalogowano', className: 'hx-action-login' },
  LOGIN_FAILED: { label: 'Błąd login', className: 'hx-action-login-failed' },
  LOGOUT: { label: 'Wylogowano', className: 'hx-action-logout' },
  STATUS_CHANGE: { label: 'Status', className: 'hx-action-status' },
  COMPLETE: { label: 'Zakończono', className: 'hx-action-complete' },
  PRICE_CHANGE: { label: 'Zmiana ceny', className: 'hx-action-price-change' },
};

function formatTimestamp(changedAt: string | null): { date: string; time: string } {
  if (!changedAt) return { date: '—', time: '' };
  const d = new Date(changedAt);
  const date = `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getFullYear()).slice(-2)}`;
  const time = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  return { date, time };
}

/** Historia zdarzeń — audit log across every entity type, filterable by tab.
 * Ported from templates/history/list_refined.html — backend
 * (`GET /api/history`, routes/api_routes.py) was already fully JSON, no
 * server changes. One fix applied during the port: the original page's JS
 * read `entry.timestamp`, a field that has never existed in this response
 * (the DB column is `changed_at`) — every row silently showed "—" for
 * date/time. Corrected here rather than carried forward; see
 * implementation-log.md. */
export function HistoryPage() {
  const toast = useToast();
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeType, setActiveType] = useState<HistoryEntityType | ''>('');

  useEffect(() => {
    historyApi
      .list()
      .then(setEntries)
      .catch(() => toast.error('Nie udało się wczytać historii'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const counts = useMemo(() => {
    const c: Record<string, number> = { '': entries.length };
    for (const tab of ENTITY_TABS) {
      if (tab.type) c[tab.type] = entries.filter((e) => e.entity_type === tab.type).length;
    }
    return c;
  }, [entries]);

  const visible = useMemo(() => (activeType ? entries.filter((e) => e.entity_type === activeType) : entries), [entries, activeType]);

  return (
    <div className="refined-page history-page fade-in">
      <header className="page-header">
        <h1 className="page-title">Historia zdarzeń</h1>
      </header>

      <div className="hx-tab-bar">
        {ENTITY_TABS.map((tab) => (
          <button key={tab.type} type="button" className={`hx-tab-btn${activeType === tab.type ? ' active' : ''}`} onClick={() => setActiveType(tab.type)}>
            {tab.label} <span className="hx-tab-count">{loading ? '—' : (counts[tab.type] ?? 0)}</span>
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
                    const ts = formatTimestamp(entry.changed_at);
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
