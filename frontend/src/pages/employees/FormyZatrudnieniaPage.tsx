import { useState } from 'react';
import './FormyZatrudnieniaPage.css';
import { useApiData } from '../../lib/useApiData';
import { formyZatrudnieniaApi } from '../../lib/api/formyZatrudnienia';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Button } from '../../components/ui/Button';
import { useEscapeAction } from '../../lib/a11y/escapeScope';

function boolBadge(val: boolean) {
  return <span className={`boolean-badge ${val ? 'yes' : 'no'}`}>{val ? 'Tak' : 'Nie'}</span>;
}

/**
 * Rodzaje zatrudnienia — ported 1:1 z
 * templates/employees/formy_zatrudnienia/list.html: formularz tworzenia +
 * tabela z edycją wierszową inline (druga taka strona w całej migracji po
 * Kategoriach usług — korekta wcześniejszego "jedyne miejsce" z
 * implementation-log.md, patrz wpis Pracownicy). Usuwanie proste (bez
 * 3-drożnego confirmu jak kategorie usług — backend nie ma tu odpowiednika
 * ochrony "kategoria ma przypisane usługi"), więc `useConfirm()` wystarcza.
 */
export function FormyZatrudnieniaPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const formyState = useApiData(() => formyZatrudnieniaApi.listFull(), []);
  const formy = formyState.data ?? [];

  const [nazwa, setNazwa] = useState('');
  const [uwagi, setUwagi] = useState('');
  const [minSalary, setMinSalary] = useState(false);
  const [grantedSalary, setGrantedSalary] = useState(false);
  const [commisionIncluded, setCommisionIncluded] = useState(false);
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  // Escape = "Anuluj" the inline row edit — 1:1 z oryginałem
  // (formy_zatrudnienia/list.html: `if (editingId) cancelEdit();`), bez
  // guarda na pisanie w polu (tam też go nie było — Escape podczas edycji
  // wiersza ma anulować, to standardowa konwencja inline-edit).
  useEscapeAction(() => setEditingId(null), editingId !== null, false);
  const [editNazwa, setEditNazwa] = useState('');
  const [editUwagi, setEditUwagi] = useState('');
  const [editMinSalary, setEditMinSalary] = useState(false);
  const [editGrantedSalary, setEditGrantedSalary] = useState(false);
  const [editCommision, setEditCommision] = useState(false);
  const [saving, setSaving] = useState(false);

  function resetCreateForm() {
    setNazwa('');
    setUwagi('');
    setMinSalary(false);
    setGrantedSalary(false);
    setCommisionIncluded(false);
  }

  async function handleCreate() {
    if (!nazwa.trim()) {
      toast.error('Nazwa jest wymagana');
      return;
    }
    setCreating(true);
    try {
      await formyZatrudnieniaApi.create({
        nazwa: nazwa.trim(),
        uwagi: uwagi.trim() || null,
        min_salary_required: minSalary,
        granted_salary: grantedSalary,
        commision_included: commisionIncluded,
      });
      toast.success('Forma zatrudnienia została dodana');
      resetCreateForm();
      formyState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd tworzenia');
    } finally {
      setCreating(false);
    }
  }

  function startEdit(f: (typeof formy)[number]) {
    setEditingId(f.id);
    setEditNazwa(f.nazwa);
    setEditUwagi(f.uwagi ?? '');
    setEditMinSalary(f.min_salary_required);
    setEditGrantedSalary(f.granted_salary);
    setEditCommision(f.commision_included);
  }

  async function saveEdit(id: number) {
    if (!editNazwa.trim()) {
      toast.error('Nazwa jest wymagana');
      return;
    }
    setSaving(true);
    try {
      await formyZatrudnieniaApi.update(id, {
        nazwa: editNazwa.trim(),
        uwagi: editUwagi.trim() || null,
        min_salary_required: editMinSalary,
        granted_salary: editGrantedSalary,
        commision_included: editCommision,
      });
      toast.success('Zapisano zmiany');
      setEditingId(null);
      formyState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(f: (typeof formy)[number]) {
    const ok = await confirm({
      title: 'Usuń formę zatrudnienia',
      message: `Usunąć formę zatrudnienia "${f.nazwa}"? Operacja jest nieodwracalna.`,
      confirmText: 'Usuń',
    });
    if (!ok) return;
    try {
      await formyZatrudnieniaApi.delete(f.id);
      toast.success('Forma zatrudnienia została usunięta');
      formyState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  return (
    <div className="refined-page formy-page page-fills-viewport animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Rodzaje zatrudnienia</h1>
          <p className="page-subtitle">Zarządzanie typami umów i form zatrudnienia pracowników</p>
        </div>
      </header>

      <div className="form-card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="section-title">Nowa forma zatrudnienia</h2>
        <div className="form-grid">
          <div>
            <label className="form-label" htmlFor="input-nazwa">
              Nazwa <span className="required-mark">*</span>
            </label>
            <input id="input-nazwa" className="form-input" placeholder="np. Umowa o pracę, B2B, Umowa zlecenie" maxLength={100} value={nazwa} onChange={(e) => setNazwa(e.target.value)} />
          </div>
          <div>
            <label className="form-label" htmlFor="input-uwagi">
              Uwagi
            </label>
            <input id="input-uwagi" className="form-input" placeholder="Opcjonalne uwagi" value={uwagi} onChange={(e) => setUwagi(e.target.value)} />
          </div>
        </div>
        <div className="checkbox-row">
          <div className="checkbox-wrapper">
            <input type="checkbox" id="input-min-salary" className="refined-checkbox" checked={minSalary} onChange={(e) => setMinSalary(e.target.checked)} />
            <label htmlFor="input-min-salary" className="checkbox-label">
              Min. wynagrodzenie wymagane
            </label>
          </div>
          <div className="checkbox-wrapper">
            <input type="checkbox" id="input-granted-salary" className="refined-checkbox" checked={grantedSalary} onChange={(e) => setGrantedSalary(e.target.checked)} />
            <label htmlFor="input-granted-salary" className="checkbox-label">
              Wynagrodzenie gwarantowane
            </label>
          </div>
          <div className="checkbox-wrapper">
            <input type="checkbox" id="input-commision" className="refined-checkbox" checked={commisionIncluded} onChange={(e) => setCommisionIncluded(e.target.checked)} />
            <label htmlFor="input-commision" className="checkbox-label">
              Prowizja wliczona
            </label>
          </div>
        </div>
        <div className="form-actions">
          <Button variant="primary" icon="add" isLoading={creating} loadingText="Dodawanie…" onClick={handleCreate}>
            Dodaj formę zatrudnienia
          </Button>
        </div>
      </div>

      <div className="form-card">
        <h2 className="section-title">Formy zatrudnienia ({formy.length})</h2>
        <div className="table-container stack-cards-wrap">
          <table className="refined-table stack-cards">
            <thead>
              <tr>
                <th>Nazwa</th>
                <th>Uwagi</th>
                <th style={{ textAlign: 'center' }}>Min. wynagrodzenie</th>
                <th style={{ textAlign: 'center' }}>Gwarantowane</th>
                <th style={{ textAlign: 'center' }}>Prowizja</th>
                <th>Akcje</th>
              </tr>
            </thead>
            <tbody>
              {formyState.loading ? (
                <tr>
                  <td colSpan={6} className="empty-state cell-empty">
                    Ładowanie...
                  </td>
                </tr>
              ) : formy.length === 0 ? (
                <tr>
                  <td colSpan={6} className="empty-state cell-empty">
                    Brak form zatrudnienia. Dodaj pierwszą powyżej.
                  </td>
                </tr>
              ) : (
                formy.map((f) =>
                  editingId === f.id ? (
                    <tr key={f.id}>
                      <td>
                        <input className="inline-input" value={editNazwa} maxLength={100} onChange={(e) => setEditNazwa(e.target.value)} autoFocus />
                      </td>
                      <td>
                        <input className="inline-input" value={editUwagi} placeholder="Uwagi" onChange={(e) => setEditUwagi(e.target.value)} />
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <input type="checkbox" className="refined-checkbox" checked={editMinSalary} onChange={(e) => setEditMinSalary(e.target.checked)} />
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <input type="checkbox" className="refined-checkbox" checked={editGrantedSalary} onChange={(e) => setEditGrantedSalary(e.target.checked)} />
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <input type="checkbox" className="refined-checkbox" checked={editCommision} onChange={(e) => setEditCommision(e.target.checked)} />
                      </td>
                      <td>
                        <div className="table-actions">
                          <Button variant="primary" small isLoading={saving} loadingText="Zapisywanie…" onClick={() => saveEdit(f.id)}>
                            Zapisz
                          </Button>
                          <Button variant="ghost" small onClick={() => setEditingId(null)}>
                            Anuluj
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    // No "view" action for formy zatrudnienia — row-click
                    // mirrors "Edytuj" (enters the same inline edit mode) —
                    // DESIGN.md §20.
                    <tr
                      key={f.id}
                      className="row-clickable"
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest('.action-icons')) return;
                        startEdit(f);
                      }}
                    >
                      <td className="cell-name">
                        <strong>{f.nazwa}</strong>
                      </td>
                      <td data-label="Uwagi">{f.uwagi || <span style={{ color: 'var(--color-ink-subtle)' }}>—</span>}</td>
                      <td data-label="Min. wynagrodzenie" style={{ textAlign: 'center' }}>
                        {boolBadge(f.min_salary_required)}
                      </td>
                      <td data-label="Gwarantowane" style={{ textAlign: 'center' }}>
                        {boolBadge(f.granted_salary)}
                      </td>
                      <td data-label="Prowizja" style={{ textAlign: 'center' }}>
                        {boolBadge(f.commision_included)}
                      </td>
                      <td className="cell-actions">
                        <div className="action-icons">
                          <button type="button" className="action-icon-btn" title="Edytuj" aria-label="Edytuj" onClick={() => startEdit(f)}>
                            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button type="button" className="action-icon-btn danger" title="Usuń" aria-label="Usuń" onClick={() => handleDelete(f)}>
                            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ),
                )
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
