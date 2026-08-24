import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './SellersListPage.css';
import { useApiData } from '../../lib/useApiData';
import { sellersApi } from '../../lib/api/sellers';
import { sellerPasswordsApi } from '../../lib/api/sellerPasswords';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { FormActions, FormCard, TextField } from '../../components/ui/form';
import { formatCurrency, formatDate } from '../../lib/format';
import { useEscapeClose } from '../../lib/a11y/useEscapeClose';
import type { SellerPdfPassword, SellerPdfPasswordFormValues } from '../../types/seller';

export interface SellerFormPageProps {
  mode: 'create' | 'edit';
}

interface ExistingSellerRef {
  id: number;
  seller_nip: string;
  seller_name: string;
}

/**
 * Sprzedawca — create/edit (jedna strona, `mode`, wzorem ClientFormPage z
 * Fazy 1). Ported 1:1 z templates/sellers/{create,edit}.html +
 * static/js/sellers/{create,edit}.js. NIP jest niezmienny po utworzeniu
 * (readonly w trybie edit — jedyny identyfikator, tak jak dziś). Tryb edit
 * dokłada: statystyki, sekcję hasła PDF (dla TEGO sprzedawcy, inline —
 * osobna od listowego panelu wszystkich haseł), tabelę powiązanych faktur,
 * przycisk "Propaguj zmiany" (`bulk-update`).
 */
export function SellerFormPage({ mode }: SellerFormPageProps) {
  const { id } = useParams<{ id: string }>();
  const sellerId = mode === 'edit' && id ? Number(id) : undefined;
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();

  const sellerState = useApiData(() => (mode === 'edit' && sellerId ? sellersApi.get(sellerId) : Promise.resolve(null)), [mode, sellerId]);

  const [nip, setNip] = useState('');
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Create-mode live validation state — ported from static/js/sellers/create.js
  const [nipCheck, setNipCheck] = useState<'idle' | 'checking' | 'valid' | 'invalid'>('idle');
  const [nipError, setNipError] = useState('');
  const [existingByNip, setExistingByNip] = useState<ExistingSellerRef | null>(null);
  const [nameWarning, setNameWarning] = useState<string | null>(null);
  const [existingByName, setExistingByName] = useState<ExistingSellerRef | null>(null);
  const [nipConflict, setNipConflict] = useState<{ existing: ExistingSellerRef; proposedName: string } | null>(null);
  const nipDebounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Hydrate edit-mode fields once the seller loads.
  const hydratedRef = useRef(false);
  useEffect(() => {
    if (mode === 'edit' && sellerState.data && !hydratedRef.current) {
      setNip(sellerState.data.seller.seller_nip);
      setName(sellerState.data.seller.seller_name);
      setAddress(sellerState.data.seller.address ?? '');
      hydratedRef.current = true;
    }
  }, [mode, sellerState.data]);

  async function validateNip(value: string) {
    setExistingByNip(null);
    setNipError('');
    const trimmed = value.trim();
    if (!trimmed) {
      setNipCheck('idle');
      return;
    }
    const normalized = trimmed.replace(/\D/g, '');
    if (normalized.length !== 10) {
      setNipCheck('invalid');
      setNipError('NIP musi mieć 10 cyfr');
      return;
    }
    setNipCheck('checking');
    try {
      const result = await sellersApi.checkDuplicate(normalized, '');
      if (result.nip_exists && result.existing_by_nip) {
        setExistingByNip(result.existing_by_nip);
        setNipCheck('invalid');
        setNipError(`NIP już istnieje jako: ${result.existing_by_nip.seller_name}`);
      } else {
        setNipCheck('valid');
      }
    } catch {
      setNipCheck('idle');
    }
  }

  function handleNipChange(value: string) {
    setNip(value);
    clearTimeout(nipDebounceRef.current);
    nipDebounceRef.current = setTimeout(() => validateNip(value), 500);
  }

  async function checkNameDuplicate() {
    setExistingByName(null);
    setNameWarning(null);
    const trimmed = name.trim();
    if (!trimmed) return;
    try {
      const result = await sellersApi.checkDuplicate('', trimmed);
      if (result.name_exists && result.existing_by_name) {
        setExistingByName(result.existing_by_name);
        setNameWarning(`Sprzedawca o podobnej nazwie już istnieje z NIP: ${result.existing_by_name.seller_nip}`);
      }
    } catch {
      /* non-blocking — same as original, only a soft warning */
    }
  }

  async function doCreate(force = false) {
    setIsSubmitting(true);
    try {
      const result = await sellersApi.create({ seller_nip: nip.trim(), seller_name: name.trim(), address: address.trim() || null });
      if (result.success) {
        if (result.already_exists) {
          toast.info('Sprzedawca już istnieje');
          navigate(`/sprzedawcy/${result.seller.id}/edytuj`);
        } else {
          toast.success('Sprzedawca został utworzony');
          navigate('/sprzedawcy');
        }
        return;
      }
      if (result.conflict_type === 'nip_exists_different_name') {
        setNipConflict({ existing: result.existing_seller, proposedName: name.trim() });
      } else if (result.conflict_type === 'name_exists_different_nip' && !force) {
        const ok = await confirm({
          title: 'Podobna nazwa',
          message: `Sprzedawca o podobnej nazwie już istnieje (${result.existing_seller.seller_name}, NIP: ${result.existing_seller.seller_nip}). Czy na pewno chcesz utworzyć nowego sprzedawcę z innym NIP?`,
          confirmText: 'Utwórz mimo to',
          type: 'warning',
        });
        if (ok) await doCreate(true);
      } else {
        toast.error(result.message || 'Błąd tworzenia sprzedawcy');
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // create_seller returns 409 for the same two conflict shapes; message carries the reason.
        toast.error(err.message);
      } else {
        toast.error(err instanceof ApiError ? err.message : 'Błąd tworzenia sprzedawcy');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateSubmit() {
    if (!nip.trim() || !name.trim()) {
      toast.error('NIP i nazwa są wymagane');
      return;
    }
    const normalized = nip.trim().replace(/\D/g, '');
    if (normalized.length !== 10) {
      toast.error('NIP musi mieć 10 cyfr');
      return;
    }
    if (existingByNip) {
      const sameName = existingByNip.seller_name.toLowerCase().replace(/\s+/g, '') === name.trim().toLowerCase().replace(/\s+/g, '');
      if (sameName) {
        toast.info('Sprzedawca już istnieje');
        navigate(`/sprzedawcy/${existingByNip.id}/edytuj`);
        return;
      }
      setNipConflict({ existing: existingByNip, proposedName: name.trim() });
      return;
    }
    if (existingByName) {
      const ok = await confirm({
        title: 'Podobna nazwa',
        message: `Sprzedawca o podobnej nazwie już istnieje (${existingByName.seller_name}, NIP: ${existingByName.seller_nip}). Czy na pewno chcesz utworzyć nowego sprzedawcę z innym NIP?`,
        confirmText: 'Utwórz mimo to',
        type: 'warning',
      });
      if (!ok) return;
    }
    await doCreate();
  }

  async function handleUseExistingSeller() {
    if (!nipConflict) return;
    const existingId = nipConflict.existing.id;
    setNipConflict(null);
    navigate(`/sprzedawcy/${existingId}/edytuj`);
  }

  async function handleUpdateExistingName() {
    if (!nipConflict) return;
    const { existing, proposedName } = nipConflict;
    setNipConflict(null);
    try {
      await sellersApi.update(existing.id, { seller_name: proposedName });
      toast.success('Nazwa sprzedawcy zaktualizowana');
      navigate(`/sprzedawcy/${existing.id}/edytuj`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd aktualizacji nazwy');
    }
  }

  async function handleEditSubmit() {
    if (!sellerId) return;
    if (!name.trim()) {
      toast.error('Nazwa sprzedawcy jest wymagana');
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await sellersApi.update(sellerId, { seller_name: name.trim(), address: address.trim() || null });
      toast.success('Zapisano zmiany');
      const invoices = sellerState.data?.invoices ?? [];
      const differentNames = invoices.filter((inv) => (inv.seller_name ?? '').trim().toLowerCase() !== result.seller.seller_name.trim().toLowerCase());
      sellerState.reload();
      if (differentNames.length > 0) {
        const ok = await confirm({
          title: 'Zaktualizuj faktury',
          message: `${differentNames.length} faktur ma inną nazwę sprzedawcy niż zapisana w bazie. Czy chcesz zaktualizować nazwę sprzedawcy we wszystkich powiązanych fakturach?`,
          confirmText: 'Zaktualizuj faktury',
          cancelText: 'Nie teraz',
          type: 'info',
        });
        if (ok) await propagate();
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd aktualizacji');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function propagate() {
    if (!sellerId) return;
    try {
      const result = await sellersApi.bulkUpdate(sellerId);
      toast.success(`Zaktualizowano ${result.updated_count} z ${result.total_invoices} faktur`);
      sellerState.reload();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd aktualizacji faktur');
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (mode === 'create') void handleCreateSubmit();
    else void handleEditSubmit();
  }

  const seller = sellerState.data?.seller;
  const invoices = sellerState.data?.invoices ?? [];

  return (
    <div className="refined-page seller-form-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">{mode === 'create' ? 'Nowy sprzedawca' : 'Edytuj sprzedawcę'}</h1>
          <p className="page-subtitle">{mode === 'create' ? 'Wprowadź dane nowego sprzedawcy' : 'Zaktualizuj dane sprzedawcy'}</p>
        </div>
      </header>

      <FormCard>
        <form onSubmit={handleSubmit}>
          {mode === 'create' ? (
            <div className="input-with-status">
              <TextField
                label="NIP"
                required
                id="seller_nip"
                placeholder="1234567890"
                maxLength={15}
                value={nip}
                onChange={(e) => handleNipChange(e.target.value)}
                error={nipCheck === 'invalid' ? nipError : undefined}
                helper={nipCheck !== 'invalid' ? 'Format: 10 cyfr (np. 1234567890 lub 123-456-78-90)' : undefined}
                inputClassName={nipCheck === 'invalid' ? 'input-warn' : undefined}
              />
              {nipCheck !== 'idle' && (
                <span className={`input-status ${nipCheck}`}>
                  {nipCheck === 'checking' && (
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  )}
                  {nipCheck === 'valid' && (
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  )}
                  {nipCheck === 'invalid' && (
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  )}
                </span>
              )}
            </div>
          ) : (
            <TextField label="NIP" id="seller_nip" value={nip} readOnly disabled helper="NIP nie może być zmieniony - jest unikalnym identyfikatorem" />
          )}

          <TextField
            label="Nazwa sprzedawcy"
            required
            id="seller_name"
            placeholder="Nazwa firmy Sp. z o.o."
            value={name}
            onChange={(e) => setName(e.target.value)}
            onBlur={mode === 'create' ? checkNameDuplicate : undefined}
            helper={mode === 'create' && nameWarning ? undefined : undefined}
            error={mode === 'create' ? nameWarning ?? undefined : undefined}
          />

          <TextField label="Adres" id="address" placeholder="ul. Przykładowa 1, 00-000 Warszawa" value={address} onChange={(e) => setAddress(e.target.value)} helper="Opcjonalny" />

          {mode === 'edit' && seller && (
            <div className="seller-stats-grid">
              <div className="stat-item">
                <span className="stat-value">{invoices.length}</span>
                <span className="stat-label">Liczba faktur</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{formatDate(seller.first_seen)}</span>
                <span className="stat-label">Pierwsza faktura</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{formatDate(seller.last_updated)}</span>
                <span className="stat-label">Ostatnia aktualizacja</span>
              </div>
            </div>
          )}

          <FormActions
            submitLabel={mode === 'create' ? 'Zapisz sprzedawcę' : 'Zapisz zmiany'}
            isLoading={isSubmitting}
            cancelHref="/sprzedawcy"
            middleActions={
              mode === 'edit' && (
                <Button type="button" variant="secondary" icon="sync" onClick={propagate} title="Zaktualizuj nazwę we wszystkich fakturach">
                  Propaguj zmiany
                </Button>
              )
            }
          />
        </form>
      </FormCard>

      {mode === 'edit' && sellerId && <PdfPasswordSection sellerId={sellerId} />}

      {mode === 'edit' && (
        <div className="invoices-table-card">
          <div className="invoices-table-header">
            <h3 className="invoices-table-title">Powiązane faktury</h3>
            <span className="invoices-table-count">{invoices.length}</span>
          </div>
          <div className="table-container" style={{ maxHeight: '400px', border: 'none', borderRadius: 0, boxShadow: 'none' }}>
          <table className="refined-table">
            <thead>
              <tr>
                <th>Nr faktury</th>
                <th>Data</th>
                <th>Kwota</th>
                <th>Status</th>
                <th>Nazwa na fakturze</th>
              </tr>
            </thead>
            <tbody>
              {sellerState.loading ? (
                <tr>
                  <td colSpan={5} className="empty-state">
                    <p className="empty-text">Ładowanie…</p>
                  </td>
                </tr>
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={5} className="empty-state">
                    <p className="empty-text">Brak powiązanych faktur</p>
                  </td>
                </tr>
              ) : (
                invoices.map((inv) => {
                  const differs = (inv.seller_name ?? '').trim().toLowerCase() !== (seller?.seller_name ?? '').trim().toLowerCase();
                  return (
                    <tr key={inv.id}>
                      <td style={{ fontWeight: 500 }}>{inv.invoice_number || '—'}</td>
                      <td>{formatDate(inv.invoice_date)}</td>
                      <td style={{ textAlign: 'right', fontWeight: 500 }}>{formatCurrency(inv.amount, inv.currency ?? 'PLN')}</td>
                      <td>
                        <span className={`status-badge ${inv.status === 'Opłacona' ? 'status-paid' : 'status-unpaid'}`}>{inv.status || 'Nieopłacona'}</span>
                      </td>
                      <td className={differs ? 'invoice-seller-name-mismatch' : undefined} title={differs ? 'Różni się od nazwy sprzedawcy' : undefined}>
                        {inv.seller_name || '—'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {nipConflict && (
        <Modal
          isOpen
          onClose={() => setNipConflict(null)}
          title="Konflikt NIP"
          footer={
            <>
              <Button variant="secondary" onClick={() => setNipConflict(null)}>
                Anuluj
              </Button>
              <Button variant="secondary" icon="people" onClick={handleUseExistingSeller}>
                Użyj istniejącego
              </Button>
              <Button variant="primary" icon="edit" onClick={handleUpdateExistingName}>
                Zaktualizuj nazwę
              </Button>
            </>
          }
        >
          <p>
            NIP <strong>{nipConflict.existing.seller_nip}</strong> już istnieje w bazie.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
            <div>
              <p className="form-label">Istniejąca nazwa</p>
              <p style={{ fontWeight: 600 }}>{nipConflict.existing.seller_name}</p>
            </div>
            <div>
              <p className="form-label">Nowa nazwa</p>
              <p style={{ fontWeight: 600 }}>{nipConflict.proposedName}</p>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

/** Inline PDF-password section — edit page only, scoped to THIS seller (the
 * "Hasła PDF" panel on the list page manages all sellers at once; this is
 * static/js/sellers/edit.js's loadPasswordData()/renderPasswordSection()). */
function PdfPasswordSection({ sellerId }: { sellerId: number }) {
  const toast = useToast();
  const confirm = useConfirm();
  const [entry, setEntry] = useState<SellerPdfPassword | null | undefined>(undefined);
  const [editing, setEditing] = useState(false);
  // Escape = "Anuluj" this inline edit form — claims the key so the page-level
  // FormActions' Escape-cancel doesn't navigate away mid-edit instead.
  useEscapeClose(editing, () => setEditing(false));
  const [password, setPassword] = useState('');
  const [emailPattern, setEmailPattern] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const data = await sellerPasswordsApi.getForSeller(sellerId);
      setEntry(data.password);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd ładowania hasła');
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sellerId]);

  function openForm() {
    setEditing(true);
    setPassword(entry?.pdf_password ?? '');
    setEmailPattern(entry?.email_sender_pattern ?? '');
    setDescription(entry?.description ?? '');
  }

  async function handleSave() {
    if (!password.trim()) {
      toast.error('Hasło PDF jest wymagane');
      return;
    }
    setSaving(true);
    const values: SellerPdfPasswordFormValues = {
      seller_id: sellerId,
      pdf_password: password.trim(),
      email_sender_pattern: emailPattern.trim() || null,
      description: description.trim() || null,
    };
    try {
      if (entry) {
        await sellerPasswordsApi.update(entry.id, values);
        toast.success('Hasło zaktualizowane');
      } else {
        await sellerPasswordsApi.create(values);
        toast.success('Hasło dodane');
      }
      setEditing(false);
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!entry) return;
    const ok = await confirm({
      title: 'Kasujemy hasło PDF?',
      message: 'Skasować hasło PDF tego sprzedawcy? Zaszyfrowane faktury same się potem nie otworzą — będziesz klikać ręcznie.',
      confirmText: 'Kasuj',
    });
    if (!ok) return;
    try {
      await sellerPasswordsApi.delete(entry.id);
      toast.success('Hasło PDF usunięte');
      setEntry(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  return (
    <FormCard>
      <div className="pdf-password-card">
        <div className="pdf-password-header">
          <div className="pdf-password-header-label">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <h3>Hasło PDF</h3>
          </div>
          {entry && !editing && (
            <div className="row-actions">
              <button type="button" className="action-btn" onClick={openForm} title="Edytuj hasło">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
              <button type="button" className="action-btn delete" onClick={handleDelete} title="Usuń hasło">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {editing ? (
          <div>
            <TextField label="Hasło PDF" required id="pwd-password" placeholder="Hasło do odblokowania PDF" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} />
            <TextField
              label="Wzorzec e-mail nadawcy"
              id="pwd-email-pattern"
              placeholder="np. noreply@firma.pl lub %@firma.pl"
              value={emailPattern}
              onChange={(e) => setEmailPattern(e.target.value)}
              helper="Używane do automatycznego dopasowania hasła przy imporcie z e-mail"
            />
            <TextField label="Opis" id="pwd-description" placeholder="np. NIP sprzedawcy, nr klienta" value={description} onChange={(e) => setDescription(e.target.value)} />
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
              <Button variant="primary" isLoading={saving} loadingText="Zapisywanie…" onClick={handleSave}>
                Zapisz hasło
              </Button>
              <Button variant="secondary" onClick={() => setEditing(false)}>
                Anuluj
              </Button>
            </div>
          </div>
        ) : entry === undefined ? (
          <p className="pdf-password-none">Ładowanie…</p>
        ) : entry ? (
          <div>
            <div className="seller-stats-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
              <div className="stat-item">
                <span className="stat-value pdf-password-value">{entry.pdf_password}</span>
                <span className="stat-label">Hasło</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{entry.email_sender_pattern || '—'}</span>
                <span className="stat-label">Wzorzec e-mail</span>
              </div>
            </div>
            {entry.description && <p className="pdf-password-none">{entry.description}</p>}
          </div>
        ) : (
          <div>
            <p className="pdf-password-none">Brak skonfigurowanego hasła. Jeśli faktury tego sprzedawcy są zabezpieczone hasłem PDF, dodaj je tutaj.</p>
            <Button variant="secondary" icon="add" onClick={openForm}>
              Dodaj hasło PDF
            </Button>
          </div>
        )}
      </div>
    </FormCard>
  );
}
