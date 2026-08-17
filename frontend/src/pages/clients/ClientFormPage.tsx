import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './ClientFormPage.css';
import { useApiData } from '../../lib/useApiData';
import { clientsApi } from '../../lib/api/clients';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { isEscapeClaimed } from '../../lib/a11y/escapeScope';
import { Icon } from '../../lib/icons/Icon';
import { FormActions, FormCard, TextField, TextareaField, CheckboxField } from '../../components/ui/form';
import type { ClientFormValues } from '../../lib/api/clients';
import type { DuplicateMatch } from '../../types/client';

export interface ClientFormPageProps {
  mode: 'create' | 'edit';
}

function DupHint({ matches }: { matches: DuplicateMatch[] }) {
  if (!matches.length) return null;
  const hasHigh = matches.some((m) => m.severity === 'high');
  return (
    <div className={`dup-hint${hasHigh ? ' is-danger' : ''}`} role="alert" aria-live="polite">
      <ul>
        {matches.map((m) => (
          <li key={`${m.field}-${m.id}-${m.category}`}>
            <span className="dh-icon">
              <Icon name="warning" />
            </span>
            <span>
              {m.message}{' '}
              <a href={`/klienci/${m.id}`} target="_blank" rel="noopener noreferrer">
                Zobacz
              </a>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Client create/edit — one page, `mode` prop, per phase-01-pilot-clients.md
 * §1.3 ("Jeden ClientFormPage.tsx z mode: 'create' | 'edit'" — create.html
 * and edit.html are ~90% identical markup/script). Live duplicate-detection
 * + submit confirm-gate ported 1:1 from both source templates.
 */
export function ClientFormPage({ mode }: ClientFormPageProps) {
  const { id } = useParams<{ id: string }>();
  const clientId = mode === 'edit' && id ? Number(id) : undefined;
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const formRef = useRef<HTMLFormElement>(null);

  const clientState = useApiData(
    () => (mode === 'edit' && clientId ? clientsApi.get(clientId) : Promise.resolve(null)),
    [mode, clientId],
  );

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [notes, setNotes] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [matches, setMatches] = useState<DuplicateMatch[]>([]);
  const lastToastSig = useRef('');
  const primedRef = useRef(mode === 'create');

  const cancelHref = mode === 'edit' && clientId ? `/klienci/${clientId}` : '/klienci';

  function clearFieldError(field: string) {
    setFieldErrors((current) => {
      if (!(field in current)) return current;
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  const runDuplicateCheck = useCallback(
    async (silent: boolean) => {
      const fn = firstName.trim();
      const ln = lastName.trim();
      const ph = phone.trim();
      const phoneReady = ph.replace(/\D/g, '').length >= 9;
      if (!phoneReady && !(fn && ln)) {
        setMatches([]);
        lastToastSig.current = '';
        return;
      }
      try {
        const result = await clientsApi.duplicateCheck({ firstName: fn, lastName: ln, phone: ph, excludeId: clientId });
        setMatches(result);
        const strong = result.filter((m) => m.severity === 'high' || m.severity === 'medium');
        const sig = strong
          .map((m) => `${m.id}:${m.category}`)
          .sort()
          .join('|');
        if (!silent && sig && sig !== lastToastSig.current) {
          toast.warning(strong[0].message, 7000);
        }
        lastToastSig.current = sig;
      } catch {
        // Non-blocking helper — never interrupt the form on a check failure.
      }
    },
    [firstName, lastName, phone, clientId, toast],
  );

  // Prime fields once client data arrives (edit mode) and prime the
  // duplicate hints SILENTLY — surfaces an existing conflict without a toast.
  useEffect(() => {
    if (mode === 'edit' && clientState.data) {
      const c = clientState.data;
      setFirstName(c.first_name);
      setLastName(c.last_name);
      setPhone(c.phone ?? '');
      setEmail(c.email ?? '');
      setDateOfBirth(c.date_of_birth ?? '');
      setNotes(c.notes ?? '');
      setIsActive(c.is_active);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, clientState.data]);

  // Debounced live duplicate check on first/last/phone change — skipped
  // until the edit-mode prime above has silently run once (primedRef).
  useEffect(() => {
    if (!primedRef.current) {
      if (mode === 'edit' && clientState.data) {
        runDuplicateCheck(true).then(() => {
          primedRef.current = true;
        });
      }
      return;
    }
    const timer = setTimeout(() => runDuplicateCheck(false), 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firstName, lastName, phone]);

  // Ctrl+S = save, Esc = cancel (skipped while typing in a field, or while
  // a popover/modal/confirm dialog already claims Escape — §11.2).
  useEffect(() => {
    function handleKeydown(event: KeyboardEvent) {
      if (event.ctrlKey && event.key === 's') {
        event.preventDefault();
        formRef.current?.requestSubmit();
      }
      if (event.key === 'Escape') {
        if (isEscapeClaimed()) return;
        const tag = (document.activeElement as HTMLElement | null)?.tagName;
        if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT') return;
        navigate(cancelHref);
      }
    }
    document.addEventListener('keydown', handleKeydown);
    return () => document.removeEventListener('keydown', handleKeydown);
  }, [navigate, cancelHref]);

  function assignFieldError(message: string) {
    const lower = message.toLowerCase();
    let field = 'first_name';
    if (lower.includes('imię') || lower.includes('first')) field = 'first_name';
    else if (lower.includes('nazwisko') || lower.includes('last')) field = 'last_name';
    else if (lower.includes('telefon') || lower.includes('phone')) field = 'phone';
    else if (lower.includes('email') || lower.includes('e-mail')) field = 'email';
    else if (lower.includes('data') || lower.includes('birth')) field = 'date_of_birth';
    setFieldErrors({ [field]: message });
  }

  async function submitClient() {
    setIsSubmitting(true);
    setFieldErrors({});
    const values: ClientFormValues = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      phone: phone.trim() || null,
      email: email.trim() || null,
      date_of_birth: dateOfBirth || null,
      notes: notes.trim() || null,
      ...(mode === 'edit' ? { is_active: isActive } : {}),
    };
    try {
      if (mode === 'create') {
        await clientsApi.create(values);
        toast.success('Klient został utworzony pomyślnie!');
        navigate('/klienci');
      } else if (clientId) {
        await clientsApi.update(clientId, values);
        navigate(`/klienci/${clientId}`);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        assignFieldError(err.message);
      } else {
        toast.error('Nie udało się połączyć z serwerem');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const strong = matches.filter((m) => m.severity === 'high' || m.severity === 'medium');
    if (strong.length) {
      const names = [...new Set(strong.slice(0, 3).map((m) => m.name))].join(', ');
      const ok = await confirm({
        title: 'Możliwy duplikat klienta',
        message: `Wykryto możliwe duplikaty: ${names}. Sprawdź poprawność danych. Zapisać mimo to?`,
        confirmText: 'Zapisz mimo to',
        cancelText: 'Wróć i popraw',
      });
      if (!ok) return;
    }
    await submitClient();
  }

  const nameMatches = matches.filter((m) => m.field === 'name');
  const phoneMatches = matches.filter((m) => m.field === 'phone');

  if (mode === 'edit' && clientState.loading) {
    return (
      <div className="refined-page client-form-page animate-fade-up">
        <div className="skeleton" style={{ height: '2rem', width: '12rem', marginBottom: '1.5rem' }} />
        <div className="form-card">
          <div className="skeleton" style={{ height: '16rem' }} />
        </div>
      </div>
    );
  }

  return (
    <div className="refined-page client-form-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">{mode === 'create' ? 'Nowy klient' : 'Edytuj klienta'}</h1>
          <p className="page-subtitle">
            {mode === 'create' ? 'Dodaj nowego klienta do bazy' : clientState.data?.full_name}
          </p>
        </div>
      </header>

      <FormCard>
        <form ref={formRef} onSubmit={handleSubmit}>
          <fieldset className="form-fieldset">
            <legend>Dane podstawowe</legend>
            <div className="form-grid">
              <TextField
                label="Imię"
                required
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="np. Anna"
                error={fieldErrors.first_name}
                onFocus={() => clearFieldError('first_name')}
              />
              <TextField
                label="Nazwisko"
                required
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="np. Kowalska"
                error={fieldErrors.last_name}
                onFocus={() => clearFieldError('last_name')}
              />
            </div>
            <DupHint matches={nameMatches} />
          </fieldset>

          <fieldset className="form-fieldset">
            <legend>Dane kontaktowe</legend>
            <div className="form-grid">
              <div>
                <TextField
                  label="Telefon"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="np. 123-456-789"
                  autoComplete="off"
                  error={fieldErrors.phone}
                  onFocus={() => clearFieldError('phone')}
                  inputClassName={phoneMatches.length ? (phoneMatches.some((m) => m.severity === 'high') ? 'input-danger' : 'input-warn') : undefined}
                />
                <DupHint matches={phoneMatches} />
              </div>
              <TextField
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="np. anna@example.com"
                error={fieldErrors.email}
                onFocus={() => clearFieldError('email')}
              />
            </div>
          </fieldset>

          <fieldset className="form-fieldset">
            <legend>Informacje dodatkowe</legend>
            <div className="form-grid">
              <TextField
                label="Data urodzenia"
                type="date"
                value={dateOfBirth}
                onChange={(e) => setDateOfBirth(e.target.value)}
                error={fieldErrors.date_of_birth}
                onFocus={() => clearFieldError('date_of_birth')}
              />
              <TextareaField
                label="Notatki"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Dodatkowe informacje o kliencie..."
                fullWidth
              />
              {mode === 'edit' && (
                <div className="form-field-full">
                  <CheckboxField label="Klient aktywny" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
                </div>
              )}
            </div>
          </fieldset>

          <FormActions
            submitLabel={mode === 'create' ? 'Zapisz klienta' : 'Zapisz zmiany'}
            isLoading={isSubmitting}
            cancelHref={cancelHref}
          />
        </form>
      </FormCard>
    </div>
  );
}
