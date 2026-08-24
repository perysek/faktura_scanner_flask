import { useEffect, useMemo, useState } from 'react';
import './AbsencesPages.css';
import { absencesApi } from '../../lib/api/absences';
import { employeesApi } from '../../lib/api/employees';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { CategoryFormModal } from './CategoryFormModal';
import { useAuth } from '../../contexts/AuthContext';
import type { AbsenceCategory, AbsenceRecord, AppointmentConflict } from '../../types/absence';
import type { EmployeeListRow } from '../../types/employee';

const STATUS_LABEL: Record<string, { label: string; className: string }> = {
  pending: { label: 'Oczekujący', className: 'ab-status--pending' },
  approved: { label: 'Zatwierdzony', className: 'ab-status--approved' },
  rejected: { label: 'Odrzucony', className: 'ab-status--rejected' },
  cancelled: { label: 'Anulowany', className: 'ab-status--cancelled' },
};

function formatPeriod(a: AbsenceRecord) {
  if (a.time_from) return `${a.date_from}, ${a.time_from}–${a.time_to}`;
  if (a.date_from === a.date_to) return a.date_from;
  return `${a.date_from} – ${a.date_to}`;
}

type SortKey = 'employee' | 'category' | 'period' | 'status' | 'requested' | 'responded';

/** Zarządzanie nieobecnościami — supervisor "Wnioski" + "L4/Manualne" +
 * "Kategorie" tabs. Ported from templates/absences/management.html +
 * static/js/absences.js.
 *
 * Deliberately still deferred (documented in implementation-log.md, same
 * pattern as the already-deferred Wizyty↔Nieobecności integration): the
 * per-conflict reassign/reschedule steps in the approve-conflict flow (here
 * it's list + force-approve only), the read-only resolution-history view
 * (depends on those actions existing to have anything to show), and the
 * inline balance-hint annotations next to employee names. Superuser
 * hard-delete (absences + categories) IS implemented — see D37 in
 * implementation-log.md. */
export function AbsencesManagementPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const auth = useAuth();

  const [tab, setTab] = useState<'requests' | 'manual' | 'categories'>('requests');
  const [requests, setRequests] = useState<AbsenceRecord[]>([]);
  const [manualList, setManualList] = useState<AbsenceRecord[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [loading, setLoading] = useState(true);

  const [categories, setCategories] = useState<AbsenceCategory[]>([]);
  const [categoriesWithDeleted, setCategoriesWithDeleted] = useState<AbsenceCategory[]>([]);
  const [employees, setEmployees] = useState<EmployeeListRow[]>([]);
  const [categoryModal, setCategoryModal] = useState<{ open: boolean; category: AbsenceCategory | null }>({ open: false, category: null });

  const canManageCategories = auth.hasModuleAccess('absences');

  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  const [rejectId, setRejectId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [conflictModal, setConflictModal] = useState<{ absenceId: number; conflicts: AppointmentConflict[] } | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  function reload() {
    setLoading(true);
    absencesApi
      .management()
      .then((r) => {
        setRequests(r.requests_list);
        setManualList(r.manual_list.filter((a) => a.source === 'manual'));
        setPendingCount(r.pending_count);
        setIsSuperuser(r.is_superuser);
        setCategoriesWithDeleted(r.categories);
      })
      .finally(() => setLoading(false));
  }

  useEffect(reload, []);
  useEffect(() => {
    absencesApi.allCategories().then(setCategories);
    employeesApi.list({ activeOnly: true }).then(setEmployees);
  }, []);

  const sortedRequests = useMemo(() => {
    if (!sortKey) return requests;
    const key: Record<SortKey, (a: AbsenceRecord) => string> = {
      employee: (a) => a.employee_name ?? '',
      category: (a) => a.category_name,
      period: (a) => a.date_from,
      status: (a) => a.status,
      requested: (a) => a.requested_at ?? '',
      responded: (a) => a.responded_at ?? '',
    };
    const get = key[sortKey];
    const sorted = [...requests].sort((a, b) => {
      const va = get(a).toLowerCase();
      const vb = get(b).toLowerCase();
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [requests, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  async function handleApprove(id: number) {
    setBusyId(id);
    try {
      const result = await absencesApi.approve(id);
      if (!result.success) {
        toast.error(result.error);
        return;
      }
      if (result.status === 'conflict') {
        setConflictModal({ absenceId: id, conflicts: result.conflicts ?? [] });
      } else {
        toast.success('Wniosek zatwierdzony');
        reload();
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zatwierdzania wniosku');
    } finally {
      setBusyId(null);
    }
  }

  async function handleForceApprove() {
    if (!conflictModal) return;
    try {
      const result = await absencesApi.forceApprove(conflictModal.absenceId);
      if (result.success) {
        toast.success('Wniosek zatwierdzony mimo konfliktów');
        setConflictModal(null);
        reload();
      } else {
        toast.error(result.error);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zatwierdzania');
    }
  }

  async function handleRejectSubmit() {
    if (!rejectId || !rejectReason.trim()) return;
    try {
      const result = await absencesApi.reject(rejectId, rejectReason.trim());
      if (result.success) {
        toast.success('Wniosek odrzucony');
        setRejectId(null);
        setRejectReason('');
        reload();
      } else {
        toast.error(result.error);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd odrzucania');
    }
  }

  async function handleCancelApproved(id: number) {
    const ok = await confirm({
      title: 'Anuluj nieobecność',
      message: 'Anulować tę zatwierdzoną nieobecność? Sloty pracownika w kalendarzu zostaną zwolnione.',
      confirmText: 'Tak, anuluj',
    });
    if (!ok) return;
    try {
      const result = await absencesApi.cancelApprovedManagement(id);
      if (result.success) {
        toast.success('Nieobecność anulowana');
        reload();
      } else {
        toast.error(result.error);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd anulowania');
    }
  }

  async function handleDeleteManual(a: AbsenceRecord) {
    const ok = await confirm({
      title: 'Usuń nieobecność',
      message: `Usunąć nieobecność ${a.employee_name ?? ''} — ${a.category_name}?`,
      confirmText: 'Usuń',
    });
    if (!ok) return;
    try {
      const result = await absencesApi.deleteAbsence(a.id);
      if (result.success) {
        toast.success('Nieobecność usunięta');
        reload();
      } else {
        toast.error(result.error);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  // Superuser-only permanent delete — D37, ported from management.html's
  // Absences.hardDelete()/_absDangerModal. Available on every row of the
  // Wnioski table regardless of status (the backend has no soft-delete
  // precondition for absences, unlike categories).
  async function handleHardDeleteAbsence(a: AbsenceRecord) {
    const isApproved = a.status === 'approved';
    const ok = await confirm({
      title: 'Trwałe usunięcie nieobecności',
      message: `Trwale usunąć nieobecność ${a.employee_name ?? ''} — ${a.category_name} (${a.date_from})? Tej operacji nie można cofnąć — wpis zniknie z historii.${
        isApproved ? ' Ta nieobecność jest zatwierdzona — jej trwałe usunięcie zwolni zajęte sloty w kalendarzu.' : ''
      }`,
      confirmText: 'Usuń trwale',
    });
    if (!ok) return;
    try {
      const result = await absencesApi.hardDeleteAbsence(a.id);
      if (result.success) {
        toast.success(result.slots_freed ? 'Nieobecność usunięta trwale — sloty zwolnione' : 'Nieobecność usunięta trwale');
        reload();
      } else {
        toast.error(result.error);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  async function handleDeleteCategory(c: AbsenceCategory) {
    const ok = await confirm({
      title: 'Usuń kategorię',
      message: `Skasować kategorię „${c.name}"? Stare wnioski to przeżyją, spokojnie.`,
      confirmText: 'Usuń',
    });
    if (!ok) return;
    try {
      const result = await absencesApi.deleteCategory(c.id);
      if (result.success) {
        toast.success('Kategoria usunięta');
        reload();
      } else {
        toast.error(result.error);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  async function handleHardDeleteCategory(c: AbsenceCategory) {
    const ok = await confirm({
      title: 'Trwałe usunięcie kategorii',
      message: `Trwale wyczyścić usuniętą kategorię „${c.name}"? Tej operacji nie można cofnąć. Usunięcie zostanie zablokowane, jeśli kategoria jest powiązana z jakąkolwiek nieobecnością. Powiązana konfiguracja i historia bilansu zostaną skasowane.`,
      confirmText: 'Usuń trwale',
    });
    if (!ok) return;
    try {
      const result = await absencesApi.hardDeleteCategory(c.id);
      if (result.success) {
        toast.success('Kategoria usunięta trwale');
        reload();
      } else {
        toast.error(result.error);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  return (
    <div className="refined-page absences-page management-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Zarządzanie nieobecnościami</h1>
          <p className="page-subtitle">Wnioski pracowników i L4 / manualne wpisy</p>
        </div>
      </header>

      <div className="ab-tabs" role="tablist">
        <button type="button" className={`ab-tab${tab === 'requests' ? ' active' : ''}`} role="tab" aria-selected={tab === 'requests'} onClick={() => setTab('requests')}>
          <Icon name="inbox" /> Wnioski
          <span className={`ab-tab-count${pendingCount === 0 ? ' zero' : ''}`}>{pendingCount}</span>
        </button>
        <button type="button" className={`ab-tab${tab === 'manual' ? ' active' : ''}`} role="tab" aria-selected={tab === 'manual'} onClick={() => setTab('manual')}>
          <Icon name="edit_calendar" /> L4 / Manualne
        </button>
        {canManageCategories && (
          <button type="button" className={`ab-tab${tab === 'categories' ? ' active' : ''}`} role="tab" aria-selected={tab === 'categories'} onClick={() => setTab('categories')}>
            <Icon name="category" /> Kategorie
          </button>
        )}
      </div>

      {tab === 'requests' && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Wnioski pracowników</span>
            <span className="card-count">
              {requests.length} {requests.length === 1 ? 'wpis' : 'wpisów'}
            </span>
          </div>
          <div className="table-container stack-cards-wrap">
            {loading ? (
              <div className="empty-state">
                <p className="empty-text">Ładowanie…</p>
              </div>
            ) : requests.length === 0 ? (
              <div className="empty-state">
                <p className="empty-text">Brak wniosków</p>
              </div>
            ) : (
              <table className="refined-table stack-cards">
                <thead>
                  <tr>
                    {(['employee', 'category', 'period', 'status', 'requested', 'responded'] as SortKey[]).map((key) => {
                      const active = sortKey === key;
                      return (
                        <th
                          key={key}
                          className={`th-sortable${active ? ' sort-active' : ''}`}
                          aria-sort={active ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                          onClick={() => toggleSort(key)}
                        >
                          {{ employee: 'Pracownik', category: 'Kategoria', period: 'Okres', status: 'Status', requested: 'Złożono', responded: 'Odpowiedź' }[key]}{' '}
                          <span className="th-sort-icon" aria-hidden="true">
                            {active ? (sortDir === 'asc' ? '▲' : '▼') : '↕'}
                          </span>
                        </th>
                      );
                    })}
                    <th style={{ textAlign: 'right' }}>Akcje</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedRequests.map((a) => {
                    const status = STATUS_LABEL[a.status];
                    return (
                      <tr key={a.id}>
                        <td className="cell-name" style={{ fontWeight: 500 }}>
                          {a.employee_name}
                        </td>
                        <td data-label="Kategoria">
                          {a.category_name}
                          {a.absence_full_day === false && <span className="ab-hourly-tag" style={{ display: 'inline' }}>{' '}godzinowa</span>}
                        </td>
                        <td data-label="Okres" style={{ whiteSpace: 'nowrap' }}>
                          {formatPeriod(a)}
                        </td>
                        <td data-label="Status">
                          <span className={`ab-status ${status.className}`}>{status.label}</span>
                          {a.status === 'rejected' && a.rejection_reason && <div className="rejection-note">{a.rejection_reason.slice(0, 60)}</div>}
                        </td>
                        <td data-label="Złożono" className="ab-muted-nowrap" style={{ fontSize: '0.75rem' }}>
                          {a.requested_at ? a.requested_at.slice(0, 16).replace('T', ' ') : '—'}
                        </td>
                        <td data-label="Odpowiedź" className="ab-muted-nowrap" style={{ fontSize: '0.75rem' }}>
                          {a.responded_at ? a.responded_at.slice(0, 16).replace('T', ' ') : '—'}
                        </td>
                        <td className="cell-actions">
                          <div className="action-icons">
                            {isSuperuser && (
                              <button type="button" className="action-icon-btn danger-reveal" title="Usuń trwale" aria-label="Usuń nieobecność trwale" onClick={() => handleHardDeleteAbsence(a)}>
                                <Icon name="delete" />
                              </button>
                            )}
                            {a.status === 'pending' && (
                              <>
                                <button type="button" className="action-icon-btn" title="Zatwierdź" aria-label="Zatwierdź wniosek" disabled={busyId === a.id} onClick={() => handleApprove(a.id)}>
                                  <Icon name="check" />
                                </button>
                                <button type="button" className="action-icon-btn" title="Odrzuć" aria-label="Odrzuć wniosek" onClick={() => setRejectId(a.id)}>
                                  <Icon name="close" />
                                </button>
                              </>
                            )}
                            {a.status === 'approved' && isSuperuser && (
                              <button
                                type="button"
                                className="action-icon-btn"
                                title="Anuluj nieobecność (zwolnij sloty w kalendarzu)"
                                aria-label="Anuluj zatwierdzoną nieobecność"
                                onClick={() => handleCancelApproved(a.id)}
                              >
                                <Icon name="delete" />
                              </button>
                            )}
                            {a.status !== 'pending' && !(a.status === 'approved' && isSuperuser) && !isSuperuser && <span style={{ color: 'var(--color-ink-subtle)', fontSize: '0.75rem' }}>—</span>}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {tab === 'manual' && (
        <ManualTab
          categories={categories}
          employees={employees}
          manualList={manualList}
          loading={loading}
          onCreated={reload}
          onDelete={handleDeleteManual}
        />
      )}

      {tab === 'categories' && canManageCategories && (
        <CategoriesTab
          categories={categoriesWithDeleted}
          loading={loading}
          isSuperuser={isSuperuser}
          onNew={() => setCategoryModal({ open: true, category: null })}
          onEdit={(c) => setCategoryModal({ open: true, category: c })}
          onDelete={handleDeleteCategory}
          onHardDelete={handleHardDeleteCategory}
        />
      )}

      <Modal isOpen={rejectId !== null} onClose={() => setRejectId(null)} title="Odrzuć wniosek">
        <p style={{ color: 'var(--color-ink-subtle)', fontSize: '0.8125rem', marginBottom: '0.75rem' }}>Podaj powód odrzucenia — zostanie on przekazany pracownikowi.</p>
        <textarea className="refined-textarea" rows={3} placeholder="Powód odrzucenia wniosku…" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} autoFocus />
        <div className="form-actions">
          <Button variant="danger" disabled={!rejectReason.trim()} onClick={handleRejectSubmit}>
            Odrzuć wniosek
          </Button>
          <Button variant="secondary" onClick={() => setRejectId(null)}>
            Anuluj
          </Button>
        </div>
      </Modal>

      <Modal isOpen={conflictModal !== null} onClose={() => setConflictModal(null)} title="Konflikty z wizytami klientów" size="large">
        {conflictModal && conflictModal.conflicts.length === 0 ? (
          <p style={{ color: 'var(--color-success)', fontSize: '0.8125rem' }}>Wszystkie konflikty rozwiązane — możesz zatwierdzić wniosek.</p>
        ) : (
          <>
            <p style={{ color: 'var(--color-ink-subtle)', fontSize: '0.8125rem', marginBottom: '1rem' }}>
              Zatwierdzenie tej nieobecności koliduje z poniższymi wizytami klientów. Zmiana stylisty/terminu per wizyta nie jest jeszcze dostępna z tego widoku — zatwierdź mimo to lub odrzuć
              wniosek.
            </p>
            <div className="table-container">
              <table className="refined-table">
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Godzina</th>
                    <th>Klient</th>
                    <th>Usługa</th>
                  </tr>
                </thead>
                <tbody>
                  {conflictModal?.conflicts.map((c) => (
                    <tr key={c.appointment_id}>
                      <td>{c.date}</td>
                      <td>
                        {c.start_time.slice(0, 5)} – {c.end_time.slice(0, 5)}
                      </td>
                      <td>{c.client_name ?? '—'}</td>
                      <td>{c.service_name ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        <div className="form-actions">
          <Button variant="danger" onClick={handleForceApprove}>
            Zatwierdź mimo to
          </Button>
          <Button variant="secondary" onClick={() => setConflictModal(null)}>
            Anuluj
          </Button>
        </div>
      </Modal>

      <CategoryFormModal isOpen={categoryModal.open} category={categoryModal.category} onClose={() => setCategoryModal({ open: false, category: null })} onSaved={reload} />
    </div>
  );
}

interface CategoriesTabProps {
  categories: AbsenceCategory[];
  loading: boolean;
  isSuperuser: boolean;
  onNew: () => void;
  onEdit: (c: AbsenceCategory) => void;
  onDelete: (c: AbsenceCategory) => void;
  onHardDelete: (c: AbsenceCategory) => void;
}

const COUNT_PERIOD_LABEL: Record<string, string> = { yearly: 'Roczny', monthly: 'Miesięczny', rolling: 'Kroczący' };

/** Kategorie tab — admin CRUD for absence categories, ported from
 * templates/absences/management.html's TAB 3 + static/js/absences.js's
 * openCategoryForm()/deleteCategory()/hardDeleteCategory(). Gated by the
 * same `hasModuleAccess('absences')` check as the original's `{% if
 * user_permissions.absences %}`. */
function CategoriesTab({ categories, loading, isSuperuser, onNew, onEdit, onDelete, onHardDelete }: CategoriesTabProps) {
  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Kategorie nieobecności</span>
        <Button variant="primary" icon="add" onClick={onNew}>
          Nowa kategoria
        </Button>
      </div>
      <div className="table-container stack-cards-wrap">
        {loading ? (
          <div className="empty-state">
            <p className="empty-text">Ładowanie…</p>
          </div>
        ) : categories.length === 0 ? (
          <div className="empty-state">
            <p className="empty-text">Brak kategorii</p>
          </div>
        ) : (
          <table className="refined-table stack-cards">
            <thead>
              <tr>
                <th>Nazwa</th>
                <th>Opis</th>
                <th>Typ</th>
                <th>Śledzony</th>
                <th>Okres</th>
                <th style={{ textAlign: 'center' }}>Reset</th>
                <th style={{ textAlign: 'right' }}>Limit</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Akcje</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.id} className={c.is_deleted ? 'row-deleted' : undefined}>
                  <td className="cell-name" style={{ fontWeight: 500 }}>
                    {c.name}
                  </td>
                  <td data-label="Opis" className="cat-desc-cell">
                    {c.description || '—'}
                  </td>
                  <td data-label="Typ">
                    <span className={`cat-type-badge ${c.absence_full_day ? 'cat-type-full' : 'cat-type-slot'}`}>{c.absence_full_day ? 'Całodniowa' : 'Godzinowa'}</span>
                  </td>
                  <td data-label="Śledzony">{c.is_tracked ? <span className="ab-status ab-status--approved small-status">Tak</span> : <span className="ab-status small-status">Nie</span>}</td>
                  <td data-label="Okres">{c.is_tracked ? (COUNT_PERIOD_LABEL[c.count_period] ?? c.count_period) : <span className="ab-dash">—</span>}</td>
                  <td data-label="Reset" style={{ textAlign: 'center', fontVariantNumeric: 'tabular-nums' }}>
                    {c.is_tracked ? (c.count_period === 'rolling' ? `${c.rolling_days ?? '—'} d` : (c.resets_at ?? 1)) : <span className="ab-dash">—</span>}
                  </td>
                  <td data-label="Limit" style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {!c.is_tracked || c.default_max_value === 0 ? <span className="ab-dash">—</span> : `${Math.trunc(c.default_max_value)} ${c.absence_full_day ? 'd' : 'h'}`}
                  </td>
                  <td data-label="Status">
                    {c.is_deleted ? <span className="ab-status ab-status--cancelled">Usunięta</span> : <span className="ab-status ab-status--approved">Aktywna</span>}
                  </td>
                  <td className="cell-actions">
                    <div className="action-icons">
                      {!c.is_deleted ? (
                        <>
                          <button type="button" className="action-icon-btn" title="Edytuj" aria-label="Edytuj kategorię" onClick={() => onEdit(c)}>
                            <Icon name="edit" />
                          </button>
                          <button type="button" className="action-icon-btn" title="Usuń" aria-label="Usuń kategorię" onClick={() => onDelete(c)}>
                            <Icon name="delete" />
                          </button>
                        </>
                      ) : isSuperuser ? (
                        <button type="button" className="action-icon-btn danger-reveal" title="Usuń trwale (wyczyść)" aria-label="Usuń kategorię trwale" onClick={() => onHardDelete(c)}>
                          <Icon name="delete" />
                        </button>
                      ) : (
                        <span style={{ color: 'var(--color-ink-subtle)', fontSize: '0.75rem' }}>—</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

interface ManualTabProps {
  categories: AbsenceCategory[];
  employees: EmployeeListRow[];
  manualList: AbsenceRecord[];
  loading: boolean;
  onCreated: () => void;
  onDelete: (a: AbsenceRecord) => void;
}

function ManualTab({ categories, employees, manualList, loading, onCreated, onDelete }: ManualTabProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const [employeeId, setEmployeeId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [timeFrom, setTimeFrom] = useState('');
  const [timeTo, setTimeTo] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const selectedCategory = categories.find((c) => String(c.id) === categoryId);
  const isFullDay = !selectedCategory || selectedCategory.absence_full_day;

  // Debounced limit-exceeded pre-check, same 450ms delay as the original.
  const [limitWarning, setLimitWarning] = useState<{ willExceed: boolean; message?: string } | null>(null);
  useEffect(() => {
    if (!employeeId || !categoryId || !dateFrom) {
      setLimitWarning(null);
      return;
    }
    if (isFullDay && !dateTo) return;
    if (!isFullDay && (!timeFrom || !timeTo)) return;
    const timer = setTimeout(() => {
      absencesApi
        .checkBalance({
          employee_id: Number(employeeId),
          category_id: Number(categoryId),
          date_from: dateFrom,
          date_to: isFullDay ? dateTo : undefined,
          time_from: isFullDay ? undefined : timeFrom,
          time_to: isFullDay ? undefined : timeTo,
        })
        .then((r) => {
          if (!r.success) return;
          setLimitWarning({ willExceed: r.will_exceed, message: r.check.message });
          if (r.check.warning && r.check.message) toast.warning(r.check.message, 7000);
        })
        .catch(() => setLimitWarning(null));
    }, 450);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [employeeId, categoryId, dateFrom, dateTo, timeFrom, timeTo, isFullDay]);

  async function doSubmit() {
    setSaving(true);
    try {
      const result = await absencesApi.createManual({
        employee_id: Number(employeeId),
        category_id: Number(categoryId),
        date_from: dateFrom,
        date_to: isFullDay ? dateTo : dateFrom,
        time_from: isFullDay ? null : timeFrom,
        time_to: isFullDay ? null : timeTo,
        notes: notes.trim() || null,
      });
      if (!result.success) {
        toast.error(result.error);
        return;
      }
      toast.success(result.conflicts && result.conflicts.length > 0 ? `Zapisano — ${result.conflicts.length} konflikt(ów) z wizytami` : 'Nieobecność zapisana');
      setEmployeeId('');
      setCategoryId('');
      setDateFrom('');
      setDateTo('');
      setTimeFrom('');
      setTimeTo('');
      setNotes('');
      setLimitWarning(null);
      onCreated();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu');
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmit() {
    if (!employeeId || !categoryId || !dateFrom) {
      toast.error('Uzupełnij wymagane pola');
      return;
    }
    if (isFullDay && !dateTo) {
      toast.error('Uzupełnij wymagane pola');
      return;
    }
    if (!isFullDay && (!timeFrom || !timeTo)) {
      toast.error('Uzupełnij godzinę od/do');
      return;
    }
    if (limitWarning?.willExceed) {
      const ok = await confirm({
        title: 'Uwaga: Przekroczenie limitu',
        message: `${limitWarning.message ?? 'Ta nieobecność przekroczy limit bilansu.'} Czy zapisać mimo to?`,
        confirmText: 'Zapisz mimo to',
      });
      if (!ok) return;
    }
    doSubmit();
  }

  return (
    <>
      <div className="card">
        <div className="card-header">
          <span className="card-title">Rejestruj nieobecność manualnie</span>
          <span className="card-count">Nieobecności L4 i inne — automatycznie zatwierdzone</span>
        </div>
        <div className="card-body">
          <div className="form-grid">
            <div>
              <label className="field-label" htmlFor="manual-employee">
                Pracownik <span className="field-required">*</span>
              </label>
              <select id="manual-employee" className="refined-select" required value={employeeId} onChange={(e) => setEmployeeId(e.target.value)}>
                <option value="">— wybierz pracownika —</option>
                {employees.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.full_name}
                    {e.position ? ` – ${e.position}` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="manual-category">
                Kategoria <span className="field-required">*</span>
              </label>
              <select id="manual-category" className="refined-select" required value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                <option value="">— wybierz —</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div />

            <div>
              <label className="field-label" htmlFor="manual-date-from">
                Data od <span className="field-required">*</span>
              </label>
              <input id="manual-date-from" type="date" className="refined-input" required value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            {isFullDay && (
              <div>
                <label className="field-label" htmlFor="manual-date-to">
                  Data do <span className="field-required">*</span>
                </label>
                <input id="manual-date-to" type="date" className="refined-input" required value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
              </div>
            )}
            <div />

            {!isFullDay && (
              <div className="form-col-full">
                <div className="form-grid">
                  <div>
                    <label className="field-label" htmlFor="manual-time-from">
                      Godzina od <span className="field-required">*</span>
                    </label>
                    <input id="manual-time-from" type="time" className="refined-input" value={timeFrom} onChange={(e) => setTimeFrom(e.target.value)} />
                  </div>
                  <div>
                    <label className="field-label" htmlFor="manual-time-to">
                      Godzina do <span className="field-required">*</span>
                    </label>
                    <input id="manual-time-to" type="time" className="refined-input" value={timeTo} onChange={(e) => setTimeTo(e.target.value)} />
                  </div>
                  <div />
                </div>
              </div>
            )}

            <div className="form-col-full">
              <label className="field-label" htmlFor="manual-notes">
                Uwagi
              </label>
              <textarea id="manual-notes" className="refined-textarea" placeholder="Np. numer zwolnienia L4, dodatkowe informacje…" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          </div>
          <div className="form-actions">
            <Button variant="primary" icon="save" isLoading={saving} loadingText="Zapisywanie…" onClick={handleSubmit}>
              Zapisz nieobecność
            </Button>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Zarejestrowane nieobecności manualne</span>
          <span className="card-count">{manualList.length} wpisów</span>
        </div>
        <div className="table-container stack-cards-wrap">
          {loading ? (
            <div className="empty-state">
              <p className="empty-text">Ładowanie…</p>
            </div>
          ) : manualList.length === 0 ? (
            <div className="empty-state">
              <p className="empty-text">Brak manualnych nieobecności</p>
            </div>
          ) : (
            <table className="refined-table stack-cards">
              <thead>
                <tr>
                  <th>Pracownik</th>
                  <th>Kategoria</th>
                  <th>Okres</th>
                  <th>Źródło</th>
                  <th>Dodano</th>
                  <th style={{ textAlign: 'right' }}>Akcje</th>
                </tr>
              </thead>
              <tbody>
                {manualList.map((a) => (
                  <tr key={a.id}>
                    <td className="cell-name" style={{ fontWeight: 500 }}>
                      {a.employee_name}
                    </td>
                    <td data-label="Kategoria">{a.category_name}</td>
                    <td data-label="Okres" style={{ whiteSpace: 'nowrap' }}>
                      {formatPeriod(a)}
                    </td>
                    <td data-label="Źródło">
                      <span className="ab-status ab-status--manual">Ręczna</span>
                    </td>
                    <td data-label="Dodano" style={{ color: 'var(--color-ink-subtle)', fontSize: '0.75rem' }}>
                      {a.requested_at ? a.requested_at.slice(0, 10) : '—'}
                    </td>
                    <td className="cell-actions">
                      <div className="action-icons">
                        <button type="button" className="action-icon-btn" title="Usuń" aria-label="Usuń nieobecność" onClick={() => onDelete(a)}>
                          <Icon name="delete" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}
