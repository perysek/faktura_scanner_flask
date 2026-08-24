import { useEffect, useState } from 'react';
import { absencesApi, type CategoryPayload } from '../../lib/api/absences';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import type { AbsenceCategory } from '../../types/absence';

interface Props {
  isOpen: boolean;
  category: AbsenceCategory | null; // null = create
  onClose: () => void;
  onSaved: () => void;
}

const DEFAULTS: CategoryPayload = {
  name: '',
  description: '',
  absence_full_day: true,
  is_tracked: false,
  count_period: 'yearly',
  resets_at: 1,
  default_max_value: 0,
  warning_threshold_pct: 0.8,
};

/** Create/edit form for an absence category — ported from
 * static/js/absences.js's `openCategoryForm()` (a hand-built Modals.show()
 * call there; here a proper Modal + controlled form). Both endpoints
 * (`POST`/`PUT /absences/categories*`) were already fully JSON — no backend
 * changes needed. */
export function CategoryFormModal({ isOpen, category, onClose, onSaved }: Props) {
  const toast = useToast();
  const [values, setValues] = useState<CategoryPayload>(DEFAULTS);
  const [saving, setSaving] = useState(false);
  const isNew = category === null;

  useEffect(() => {
    if (!isOpen) return;
    setValues(
      category
        ? {
            name: category.name,
            description: category.description ?? '',
            absence_full_day: category.absence_full_day,
            is_tracked: category.is_tracked,
            count_period: category.count_period,
            resets_at: category.resets_at ?? 1,
            default_max_value: category.default_max_value,
            warning_threshold_pct: category.warning_threshold_pct,
          }
        : DEFAULTS,
    );
  }, [isOpen, category]);

  async function handleSave() {
    if (!values.name.trim()) {
      toast.error('Nazwa jest wymagana');
      return;
    }
    setSaving(true);
    try {
      const payload: CategoryPayload = { ...values, name: values.name.trim() };
      const result = isNew ? await absencesApi.createCategory(payload) : await absencesApi.updateCategory(category!.id, payload);
      if (!result.success) {
        toast.error(result.error);
        return;
      }
      toast.success(isNew ? 'Kategoria utworzona' : 'Kategoria zaktualizowana');
      onSaved();
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isNew ? 'Nowa kategoria nieobecności' : 'Edytuj kategorię'}>
      <div className="field-group">
        <label className="field-label" htmlFor="cat-name">
          Nazwa <span className="required-mark">*</span>
        </label>
        <input id="cat-name" className="field-input" placeholder="np. Urlop okolicznościowy" value={values.name} onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))} autoFocus />
      </div>
      <div className="field-group">
        <label className="field-label" htmlFor="cat-desc">
          Opis
        </label>
        <input id="cat-desc" className="field-input" placeholder="Opcjonalny opis…" value={values.description} onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))} />
      </div>
      <div className="checkbox-wrapper cat-toggle-row" onClick={() => setValues((v) => ({ ...v, absence_full_day: !v.absence_full_day }))}>
        <input type="checkbox" className="refined-checkbox" checked={values.absence_full_day} onChange={(e) => setValues((v) => ({ ...v, absence_full_day: e.target.checked }))} />
        <div>
          <div className="cat-toggle-title">Nieobecność całodniowa</div>
          <div className="cat-toggle-hint">Odznacz dla nieobecności godzinowych</div>
        </div>
      </div>

      <div className="cat-tracking-block">
        <div className="checkbox-wrapper cat-toggle-row" onClick={() => setValues((v) => ({ ...v, is_tracked: !v.is_tracked }))}>
          <input type="checkbox" className="refined-checkbox" checked={values.is_tracked} onChange={(e) => setValues((v) => ({ ...v, is_tracked: e.target.checked }))} />
          <div>
            <div className="cat-toggle-title">Śledzenie bilansu</div>
            <div className="cat-toggle-hint">Włącz aby kontrolować limity i saldo tej kategorii</div>
          </div>
        </div>

        {values.is_tracked && (
          <div className="cat-tracking-details">
            <div>
              <label className="field-label" htmlFor="cat-period">
                Okres rozliczeniowy
              </label>
              <select id="cat-period" className="field-select" value={values.count_period} onChange={(e) => setValues((v) => ({ ...v, count_period: e.target.value }))}>
                <option value="yearly">Roczny</option>
                <option value="monthly">Miesięczny</option>
                <option value="rolling">Kroczący</option>
              </select>
            </div>
            <div>
              <label className="field-label" htmlFor="cat-resets">
                Reset (dzień)
              </label>
              <input
                id="cat-resets"
                type="number"
                min={1}
                max={28}
                className="field-input"
                value={values.resets_at}
                onChange={(e) => setValues((v) => ({ ...v, resets_at: Number(e.target.value) || 1 }))}
              />
            </div>
            <div>
              <label className="field-label" htmlFor="cat-maxval">
                Domyślny limit
              </label>
              <input
                id="cat-maxval"
                type="number"
                min={0}
                step={0.5}
                className="field-input"
                value={values.default_max_value}
                onChange={(e) => setValues((v) => ({ ...v, default_max_value: Number(e.target.value) || 0 }))}
              />
            </div>
            <div>
              <label className="field-label" htmlFor="cat-warnpct">
                Próg ostrzeżenia (%)
              </label>
              <input
                id="cat-warnpct"
                type="number"
                min={0}
                max={100}
                step={5}
                className="field-input"
                value={Math.round(values.warning_threshold_pct * 100)}
                onChange={(e) => setValues((v) => ({ ...v, warning_threshold_pct: (Number(e.target.value) || 0) / 100 }))}
              />
            </div>
          </div>
        )}
      </div>

      <div className="form-actions">
        <Button variant="primary" isLoading={saving} loadingText="Zapisywanie…" onClick={handleSave}>
          {isNew ? 'Utwórz' : 'Zapisz'}
        </Button>
        <Button variant="secondary" onClick={onClose}>
          Anuluj
        </Button>
      </div>
    </Modal>
  );
}
