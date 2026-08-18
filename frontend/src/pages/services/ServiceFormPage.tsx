import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './ServicesListPage.css';
import { useApiData } from '../../lib/useApiData';
import { servicesApi } from '../../lib/api/services';
import { serviceCategoriesApi } from '../../lib/api/serviceCategories';
import { ApiError } from '../../lib/api/client';
import { useAuth } from '../../contexts/AuthContext';
import { useToast } from '../../components/feedback/ToastProvider';
import { FormActions, FormCard, SelectField, TextField, TextareaField } from '../../components/ui/form';
import type { ServiceType } from '../../types/service';

export interface ServiceFormPageProps {
  mode: 'create' | 'edit';
}

/**
 * Usługa — create/edit (mode prop, jak Sellers/Clients). Ported 1:1 z
 * templates/services/{create,edit}.html: typ usługi (główna/dodatkowa)
 * przełącza widoczność/wymagalność pola kategorii, edit-mode dokłada pole
 * "powód zmiany ceny" — widoczne tylko gdy user ma 'service_prices' I cena
 * faktycznie się zmieniła względem wartości przy załadowaniu strony.
 */
export function ServiceFormPage({ mode }: ServiceFormPageProps) {
  const { id } = useParams<{ id: string }>();
  const serviceId = mode === 'edit' && id ? Number(id) : undefined;
  const navigate = useNavigate();
  const toast = useToast();
  const auth = useAuth();
  const canSeePriceReason = auth.hasModuleAccess('service_prices');

  const serviceState = useApiData(() => (mode === 'edit' && serviceId ? servicesApi.get(serviceId) : Promise.resolve(null)), [mode, serviceId]);
  const categoriesState = useApiData(() => serviceCategoriesApi.list(), []);

  const [serviceType, setServiceType] = useState<ServiceType>('main');
  const [name, setName] = useState('');
  const [category, setCategory] = useState('');
  const [price, setPrice] = useState('');
  const [duration, setDuration] = useState('');
  const [description, setDescription] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [changeReason, setChangeReason] = useState('');
  const [originalPrice, setOriginalPrice] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<{ field: string; message: string } | null>(null);

  const hydrated = useRef(false);
  useEffect(() => {
    if (mode === 'edit' && serviceState.data && !hydrated.current) {
      const s = serviceState.data;
      setServiceType(s.service_type);
      setName(s.name);
      setCategory(s.category ?? '');
      setPrice(String(s.price));
      setOriginalPrice(s.price);
      setDuration(String(s.duration_minutes));
      setDescription(s.description ?? '');
      setIsActive(s.is_active);
      hydrated.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, serviceState.data]);

  const priceChanged = mode === 'edit' && originalPrice !== null && parseFloat(price || '0') !== originalPrice;
  const cancelHref = mode === 'edit' && serviceId ? `/uslugi/${serviceId}` : '/uslugi';

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFieldError(null);

    const values = {
      name: name.trim(),
      price: parseFloat(price),
      duration_minutes: parseInt(duration, 10),
      description: description.trim() || null,
      service_type: serviceType,
      ...(serviceType === 'main' ? { category } : {}),
      ...(mode === 'create' ? { currency: 'PLN', is_active: true } : { is_active: isActive }),
      ...(mode === 'edit' && canSeePriceReason ? { change_reason: changeReason.trim() || null } : {}),
    };

    setIsSubmitting(true);
    try {
      if (mode === 'create') {
        await servicesApi.create(values as never);
        toast.success('Usługa została utworzona pomyślnie!');
        navigate('/uslugi');
      } else if (serviceId) {
        await servicesApi.update(serviceId, values as never);
        navigate(`/uslugi/${serviceId}`);
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem';
      const lower = message.toLowerCase();
      if (mode === 'edit') {
        if (lower.includes('nazwa') || lower.includes('name')) setFieldError({ field: 'name', message });
        else if (lower.includes('kategoria') || lower.includes('category')) setFieldError({ field: 'category', message });
        else if (lower.includes('cena') || lower.includes('price')) setFieldError({ field: 'price', message });
        else if (lower.includes('czas') || lower.includes('duration')) setFieldError({ field: 'duration_minutes', message });
        else setFieldError({ field: 'name', message });
      } else {
        toast.error(message);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  const categoryOptions = (categoriesState.data ?? []).map((c) => ({ value: c.name, label: c.name }));

  return (
    <div className="refined-page service-detail-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">{mode === 'create' ? 'Nowa usługa' : 'Edytuj usługę'}</h1>
          <p className="page-subtitle">{mode === 'create' ? 'Dodaj nową usługę do katalogu' : serviceState.data?.name}</p>
        </div>
      </header>

      <FormCard>
        <form onSubmit={handleSubmit}>
          <div className="form-field" style={{ marginBottom: '1.25rem' }}>
            <label className="form-label">
              Typ <span className="required-mark">*</span>
            </label>
            <div style={{ display: 'flex', gap: '1.5rem', padding: '0.5rem 0' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.8125rem' }}>
                <input type="radio" name="service_type" value="main" checked={serviceType === 'main'} onChange={() => setServiceType('main')} />
                Główna
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.8125rem' }}>
                <input type="radio" name="service_type" value="addon" checked={serviceType === 'addon'} onChange={() => setServiceType('addon')} />
                Dodatkowa
              </label>
            </div>
            <p className="form-helper-text">Usługa dodatkowa może być dodana tylko podczas wizyty</p>
          </div>

          <div className="form-grid">
            <TextField label="Nazwa usługi" required id="name" placeholder="np. Strzyżenie damskie" value={name} onChange={(e) => setName(e.target.value)} error={fieldError?.field === 'name' ? fieldError.message : undefined} />
            {serviceType === 'main' && (
              <SelectField
                label="Kategoria"
                required
                id="category"
                placeholder="Wybierz kategorię"
                options={categoryOptions}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                error={fieldError?.field === 'category' ? fieldError.message : undefined}
              />
            )}
          </div>

          <div className="form-grid">
            <div>
              <TextField
                label="Cena"
                required
                id="price"
                type="number"
                step="0.01"
                min={0}
                placeholder="0.00"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                error={fieldError?.field === 'price' ? fieldError.message : undefined}
              />
              {mode === 'edit' && canSeePriceReason && priceChanged && (
                <div style={{ marginTop: '0.75rem' }}>
                  <TextField
                    label="Powód zmiany ceny"
                    id="change_reason"
                    maxLength={255}
                    placeholder="np. Podwyżka inflacyjna, nowy cennik 2026…"
                    value={changeReason}
                    onChange={(e) => setChangeReason(e.target.value)}
                    helper="Opcjonalnie — pojawi się w historii cen"
                  />
                </div>
              )}
            </div>
            <TextField
              label="Czas trwania (min)"
              required
              id="duration_minutes"
              type="number"
              min={serviceType === 'addon' ? 0 : 5}
              step={5}
              placeholder={serviceType === 'addon' ? '0' : '60'}
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
              error={fieldError?.field === 'duration_minutes' ? fieldError.message : undefined}
            />
          </div>

          <TextareaField label="Opis" id="description" placeholder="Opcjonalny opis usługi..." value={description} onChange={(e) => setDescription(e.target.value)} fullWidth />

          {mode === 'edit' && (
            <div className="checkbox-wrapper" style={{ marginTop: '0.5rem' }}>
              <input type="checkbox" id="is_active" className="refined-checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
              <label htmlFor="is_active" className="checkbox-label">
                Usługa aktywna
              </label>
            </div>
          )}

          <FormActions submitLabel={mode === 'create' ? 'Zapisz usługę' : 'Zapisz zmiany'} isLoading={isSubmitting} cancelHref={cancelHref} />
        </form>
      </FormCard>
    </div>
  );
}
