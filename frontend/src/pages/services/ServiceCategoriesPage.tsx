import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './ServicesListPage.css';
import { useApiData } from '../../lib/useApiData';
import { serviceCategoriesApi } from '../../lib/api/serviceCategories';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { useEscapeAction } from '../../lib/a11y/escapeScope';
import type { CategoryServiceRow, ServiceCategory } from '../../types/service';

type SortColumn = 'name' | 'additional_description' | 'service_count';

/**
 * Kategorie usług — czwarta (i ostatnia) pod-strona modułu Usługi. Ported
 * 1:1 z templates/services/categories/list.html: formularz tworzenia +
 * tabela z edycją WIERSZOWĄ inline (nie osobna strona edycji — jedyne
 * miejsce w całej migracji, gdzie oryginał robi to tak), modal z listą usług
 * danej kategorii, i 3-drożny confirm usuwania (Anuluj / Usuń tylko
 * kategorię / Usuń z usługami) — stąd generyczny `Modal`, nie `useConfirm()`.
 */
export function ServiceCategoriesPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const categoriesState = useApiData(() => serviceCategoriesApi.list(), []);
  const [sort, setSort] = useState<{ column: SortColumn | null; dir: 'asc' | 'desc' }>({ column: null, dir: 'asc' });

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  // Escape = "Anuluj" the inline row edit — 1:1 z oryginałem
  // (categories/list.html: `if (editingId) cancelEdit();`). Modal's own
  // Escape-to-close (useEscapeClaim) already covers deleteTarget/
  // modalCategory, so nothing extra needed for those here.
  useEscapeAction(() => setEditingId(null), editingId !== null, false);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [saving, setSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string; serviceCount: number } | null>(null);
  const [modalCategory, setModalCategory] = useState<{ id: number; name: string; count: number } | null>(null);
  const [modalServices, setModalServices] = useState<CategoryServiceRow[] | null>(null);

  const categories = useMemo(() => categoriesState.data ?? [], [categoriesState.data]);
  const sorted = useMemo(() => {
    if (!sort.column) return categories;
    const { column, dir } = sort;
    return [...categories].sort((a, b) => {
      const av = column === 'service_count' ? (a.service_count ?? 0) : String(a[column] ?? '').toLowerCase();
      const bv = column === 'service_count' ? (b.service_count ?? 0) : String(b[column] ?? '').toLowerCase();
      const cmp = typeof av === 'number' && typeof bv === 'number' ? av - bv : av < bv ? -1 : av > bv ? 1 : 0;
      return dir === 'asc' ? cmp : -cmp;
    });
  }, [categories, sort]);

  function handleSort(column: SortColumn) {
    setSort((current) => (current.column === column ? { column, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { column, dir: 'asc' }));
  }

  function sortIndicator(column: SortColumn) {
    if (sort.column !== column) return { ariaSort: 'none' as const, glyph: '↕', active: false };
    const ariaSort = sort.dir === 'asc' ? ('ascending' as const) : ('descending' as const);
    return { ariaSort, glyph: sort.dir === 'asc' ? '↑' : '↓', active: true };
  }

  async function handleCreate() {
    if (!name.trim()) {
      toast.error('Nazwa jest wymagana');
      return;
    }
    setCreating(true);
    try {
      await serviceCategoriesApi.create({ name: name.trim(), additional_description: description.trim() || null });
      setName('');
      setDescription('');
      toast.success('Kategoria została dodana');
      categoriesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd tworzenia');
    } finally {
      setCreating(false);
    }
  }

  function startEdit(cat: ServiceCategory) {
    setEditingId(cat.id);
    setEditName(cat.name);
    setEditDesc(cat.additional_description ?? '');
  }

  async function saveEdit(id: number) {
    if (!editName.trim()) {
      toast.error('Nazwa jest wymagana');
      return;
    }
    setSaving(true);
    try {
      await serviceCategoriesApi.update(id, { name: editName.trim(), additional_description: editDesc.trim() || null });
      toast.success('Zapisano zmiany');
      setEditingId(null);
      categoriesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(cat: ServiceCategory) {
    try {
      const result = await serviceCategoriesApi.delete(cat.id);
      if (result.success) {
        toast.success('Kategoria została usunięta');
        categoriesState.reload();
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setDeleteTarget({ id: cat.id, name: cat.name, serviceCount: cat.service_count ?? 0 });
      } else {
        toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
      }
    }
  }

  async function confirmDeleteOnly() {
    if (!deleteTarget) return;
    const { id } = deleteTarget;
    setDeleteTarget(null);
    try {
      await serviceCategoriesApi.delete(id, { categoryOnly: true });
      toast.success('Kategoria została usunięta (usługi pozostały bez zmian)');
      categoriesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  async function confirmDeleteForce() {
    if (!deleteTarget) return;
    const { id } = deleteTarget;
    setDeleteTarget(null);
    try {
      await serviceCategoriesApi.delete(id, { force: true });
      toast.success('Kategoria i powiązane usługi zostały usunięte');
      categoriesState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  async function openServicesModal(cat: ServiceCategory) {
    setModalCategory({ id: cat.id, name: cat.name, count: cat.service_count ?? 0 });
    setModalServices(null);
    try {
      const services = await serviceCategoriesApi.servicesInCategory(cat.id);
      setModalServices(services);
    } catch {
      setModalServices([]);
    }
  }

  const columns: Array<{ column: SortColumn; label: string }> = [
    { column: 'name', label: 'Nazwa' },
    { column: 'additional_description', label: 'Dodatkowy opis' },
    { column: 'service_count', label: 'Usługi' },
  ];

  return (
    <div className="refined-page services-page page-fills-viewport animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Kategorie usług</h1>
          <p className="page-subtitle">Zarządzanie kategoriami katalogu usług salonowych</p>
        </div>
      </header>

      <div className="form-card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="section-title">Nowa kategoria</h2>
        <div className="form-grid">
          <div>
            <label className="form-label" htmlFor="input-name">
              Nazwa <span className="required-mark">*</span>
            </label>
            <input id="input-name" className="form-input" placeholder="np. Strzyżenie, Koloryzacja" maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="form-label" htmlFor="input-desc">
              Dodatkowy opis
            </label>
            <input id="input-desc" className="form-input" placeholder="Opcjonalny opis kategorii" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
        </div>
        <div className="form-actions">
          <Button variant="primary" icon="add" isLoading={creating} loadingText="Dodawanie…" onClick={handleCreate}>
            Dodaj kategorię
          </Button>
        </div>
      </div>

      <div className="form-card">
        <h2 className="section-title">Kategorie usług ({categories.length})</h2>
        <div className="table-container stack-cards-wrap">
          <table className="refined-table stack-cards">
            <thead>
              <tr>
                {columns.map((col) => {
                  const ind = sortIndicator(col.column);
                  return (
                    <th key={col.column} className={`th-sortable${ind.active ? ' sort-active' : ''}`} aria-sort={ind.ariaSort} style={col.column === 'service_count' ? { textAlign: 'center' } : undefined}>
                      <button type="button" className="th-sort-btn" onClick={() => handleSort(col.column)}>
                        {col.label} <span className="th-sort-icon" aria-hidden="true">{ind.glyph}</span>
                      </button>
                    </th>
                  );
                })}
                <th>Akcje</th>
              </tr>
            </thead>
            <tbody>
              {categoriesState.loading ? (
                <tr>
                  <td colSpan={4} className="empty-state cell-empty">
                    Ładowanie...
                  </td>
                </tr>
              ) : sorted.length === 0 ? (
                <tr>
                  <td colSpan={4} className="empty-state cell-empty">
                    Brak kategorii. Dodaj pierwszą powyżej.
                  </td>
                </tr>
              ) : (
                sorted.map((cat) =>
                  editingId === cat.id ? (
                    <tr key={cat.id}>
                      <td>
                        <input className="inline-input" value={editName} maxLength={100} onChange={(e) => setEditName(e.target.value)} autoFocus />
                      </td>
                      <td>
                        <input className="inline-input" value={editDesc} placeholder="Dodatkowy opis" onChange={(e) => setEditDesc(e.target.value)} />
                      </td>
                      <td />
                      <td>
                        <div className="table-actions">
                          <Button variant="primary" small isLoading={saving} onClick={() => saveEdit(cat.id)}>
                            Zapisz
                          </Button>
                          <Button variant="ghost" small onClick={() => setEditingId(null)}>
                            Anuluj
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    // No "view" action for categories — row-click mirrors "Edytuj"
                    // (enters the same inline edit mode) — DESIGN.md §20. The
                    // service-count badge and action icons are their own
                    // click targets, excluded via .closest() below.
                    <tr
                      key={cat.id}
                      className="row-clickable"
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest('.action-icons, .service-count-badge')) return;
                        startEdit(cat);
                      }}
                    >
                      <td className="cell-name">
                        <strong>{cat.name}</strong>
                      </td>
                      <td data-label="Dodatkowy opis">{cat.additional_description || <span style={{ color: 'var(--color-ink-subtle)' }}>—</span>}</td>
                      <td data-label="Usługi" style={{ textAlign: 'center' }}>
                        {(cat.service_count ?? 0) > 0 ? (
                          <button type="button" className="service-count-badge has-services" title="Pokaż usługi w tej kategorii" onClick={() => openServicesModal(cat)}>
                            {cat.service_count}
                          </button>
                        ) : (
                          <span className="service-count-badge">0</span>
                        )}
                      </td>
                      <td className="cell-actions">
                        <div className="action-icons">
                          <button type="button" className="action-icon-btn" title="Edytuj" aria-label="Edytuj" onClick={() => startEdit(cat)}>
                            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button type="button" className="action-icon-btn danger" title="Usuń" aria-label="Usuń" onClick={() => handleDelete(cat)}>
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

      {deleteTarget && (
        <Modal
          isOpen
          onClose={() => setDeleteTarget(null)}
          title={`Usuń kategorię "${deleteTarget.name}"`}
          footer={
            <>
              <Button variant="secondary" onClick={() => setDeleteTarget(null)}>
                Anuluj
              </Button>
              <Button variant="danger" onClick={confirmDeleteOnly}>
                Usuń tylko kategorię
              </Button>
              <Button variant="danger" onClick={confirmDeleteForce}>
                Usuń z usługami
              </Button>
            </>
          }
        >
          <p>
            Ta kategoria jest przypisana do <strong>{deleteTarget.serviceCount}</strong> usług(i).
          </p>
          <p style={{ marginTop: '0.75rem' }}>Możesz usunąć tylko kategorię (usługi pozostają bez kategorii) lub usunąć kategorię razem ze wszystkimi powiązanymi usługami.</p>
          <p style={{ marginTop: '0.75rem', fontWeight: 600 }}>Obie operacje są nieodwracalne.</p>
        </Modal>
      )}

      {modalCategory && (
        <Modal isOpen onClose={() => setModalCategory(null)} title="Usługi w kategorii" size="medium">
          <p style={{ marginBottom: '1rem', color: 'var(--color-ink-muted)', fontSize: '0.8125rem' }}>
            {modalCategory.name} — {modalCategory.count} usług(i) w tej kategorii
          </p>
          {modalServices === null ? (
            <div className="cat-modal-empty">Ładowanie...</div>
          ) : modalServices.length === 0 ? (
            <div className="cat-modal-empty">Brak usług w tej kategorii</div>
          ) : (
            <div className="scroll-thin" style={{ maxHeight: '50vh' }}>
            <table className="cat-modal-table">
              <thead>
                <tr>
                  <th>Nazwa</th>
                  <th>Cena</th>
                  <th>Czas</th>
                  <th>Typ</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {modalServices.map((s) => (
                  // Row-click mirrors the name link (the row's only "view"
                  // action) — DESIGN.md §20.
                  <tr
                    key={s.id}
                    onClick={(e) => {
                      if ((e.target as HTMLElement).closest('a')) return;
                      setModalCategory(null);
                      navigate(`/uslugi/${s.id}`);
                    }}
                  >
                    <td>
                      <Link to={`/uslugi/${s.id}`} style={{ color: 'var(--color-ink)', textDecoration: 'none', fontWeight: 500 }} onClick={() => setModalCategory(null)}>
                        {s.name}
                      </Link>
                    </td>
                    <td>{s.price.toFixed(2)} zł</td>
                    <td>{s.duration_minutes} min</td>
                    <td style={{ color: 'var(--color-ink-subtle)', fontSize: '0.75rem' }}>{s.service_type === 'addon' ? 'Dodatkowa' : 'Główna'}</td>
                    <td>
                      <span className={`status-badge ${s.is_active ? 'active' : 'inactive'}`}>{s.is_active ? 'Aktywna' : 'Nieaktywna'}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </Modal>
      )}
    </div>
  );
}
