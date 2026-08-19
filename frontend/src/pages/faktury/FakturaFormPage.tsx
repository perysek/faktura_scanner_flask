import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import './FakturyListPage.css';
import { useApiData } from '../../lib/useApiData';
import { invoicesApi } from '../../lib/api/invoices';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { Icon } from '../../lib/icons/Icon';
import { FormActions, FormSection, SelectField, TextField, TextareaField } from '../../components/ui/form';
import type { InvoiceConflictResponse, InvoiceFormValues } from '../../types/invoice';

export interface FakturaFormPageProps {
  mode: 'create' | 'edit';
}

const EMPTY_VALUES: InvoiceFormValues = {
  invoice_number: '',
  status: 'Nieopłacona',
  invoice_date: '',
  payment_due_date: '',
  payment_term: '',
  seller_name: '',
  seller_nip: '',
  bank_account: '',
  seller_address: '',
  amount: '',
  currency: 'PLN',
};

const STATUS_OPTIONS = [
  { value: 'Nieopłacona', label: 'Nieopłacona' },
  { value: 'Opłacona', label: 'Opłacona' },
];

const CURRENCY_OPTIONS = ['PLN', 'EUR', 'USD', 'GBP'].map((c) => ({ value: c, label: c }));

/** Pending seller-conflict decision — shape covers BOTH the create (multipart
 * resubmit via `pendingFormDataRef`, appending `seller_action` to the SAME
 * FormData the first POST used) and edit (JSON resubmit through the
 * `confirm-seller` endpoint) flows, so one modal pair serves both. */
type PendingConflict = { kind: 'name_mismatch'; existingSellerId: number; existingName: string; nip: string; proposedName: string } | { kind: 'new_seller'; nip: string; name: string };

/**
 * Faktura — create/edit (jedna strona, `mode`, wzorem SellerFormPage/
 * ClientFormPage). Ported 1:1 z templates/invoices/{create,edit}.html: te
 * same pola, ta sama walidacja HTML5 (`required`), ten sam dwuetapowy
 * przepływ konfliktu sprzedawcy (409 → modal decyzji → resubmit). Świadomie
 * pominięte względem oryginału: przyciski "Wklej ze schowka" przy każdym
 * polu (`pasteToField()` — wygoda przy przepisywaniu z OCR/innego okna, nie
 * ma odpowiednika w żadnym innym module Fazy 2, `TextField` nie ma slotu na
 * adornment) — formularz jest w pełni funkcjonalny bez tego, tylko bez tej
 * jednej wygody.
 */
export function FakturaFormPage({ mode }: FakturaFormPageProps) {
  const { id } = useParams<{ id: string }>();
  const invoiceId = mode === 'edit' && id ? Number(id) : undefined;
  const navigate = useNavigate();
  const toast = useToast();

  const invoiceState = useApiData(() => (mode === 'edit' && invoiceId ? invoicesApi.get(invoiceId) : Promise.resolve(null)), [mode, invoiceId]);

  const [values, setValues] = useState<InvoiceFormValues>(EMPTY_VALUES);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);
  const [pendingConflict, setPendingConflict] = useState<PendingConflict | null>(null);
  const pendingFormDataRef = useRef<FormData | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const hydratedRef = useRef(false);
  useEffect(() => {
    if (mode === 'edit' && invoiceState.data && !hydratedRef.current) {
      const inv = invoiceState.data;
      setValues({
        invoice_number: inv.invoice_number ?? '',
        status: inv.status ?? 'Nieopłacona',
        invoice_date: inv.invoice_date ?? '',
        payment_due_date: inv.payment_due_date ?? '',
        payment_term: inv.payment_term ?? '',
        seller_name: inv.seller_name ?? '',
        seller_nip: inv.seller_nip ?? '',
        bank_account: inv.bank_account ?? '',
        seller_address: '',
        amount: inv.amount !== null && inv.amount !== undefined ? String(inv.amount) : '',
        currency: inv.currency ?? 'PLN',
      });
      hydratedRef.current = true;
    }
  }, [mode, invoiceState.data]);

  useEffect(() => {
    return () => {
      if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    };
  }, [filePreviewUrl]);

  function set<K extends keyof InvoiceFormValues>(key: K, value: InvoiceFormValues[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0];
    if (!selected) return;
    if (selected.size > 10 * 1024 * 1024) {
      toast.error('Plik jest za duży (maksymalnie 10 MB)');
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    setFile(selected);
    setFilePreviewUrl(URL.createObjectURL(selected));
  }

  function clearFile() {
    if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    setFile(null);
    setFilePreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function buildFormData(): FormData {
    const fd = new FormData();
    (Object.keys(values) as Array<keyof InvoiceFormValues>).forEach((key) => fd.append(key, values[key]));
    if (file) fd.append('pdf_file', file);
    return fd;
  }

  function conflictFromError(err: ApiError): PendingConflict | null {
    const data = err.data as InvoiceConflictResponse | undefined;
    if (data?.seller_conflict) {
      const c = data.seller_conflict;
      return { kind: 'name_mismatch', existingSellerId: c.existing_seller.id, existingName: c.existing_seller.seller_name, nip: c.existing_seller.seller_nip, proposedName: c.proposed_name };
    }
    if (data?.seller_info?.new_seller) {
      return { kind: 'new_seller', nip: data.seller_info.seller_nip, name: data.seller_info.seller_name };
    }
    return null;
  }

  async function handleCreateSubmit() {
    setIsSubmitting(true);
    const fd = buildFormData();
    pendingFormDataRef.current = fd;
    try {
      const result = await invoicesApi.create(fd);
      toast.success('Faktura została dodana pomyślnie');
      if (result.warnings?.length) toast.info(result.warnings.join(', '));
      navigate('/faktury');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const conflict = conflictFromError(err);
        if (conflict) {
          setPendingConflict(conflict);
          return; // `finally` below still clears isSubmitting — correct: the
          // primary submit is no longer in flight, the decision modal (with
          // its own isSubmitting-driven busy state via resolveConflict) is.
        }
      }
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu faktury');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleEditSubmit() {
    if (!invoiceId) return;
    setIsSubmitting(true);
    const payload: Record<string, unknown> = { ...values };
    delete payload.seller_address; // edit.html has no address field — never sent on update
    try {
      const result = await invoicesApi.update(invoiceId, payload);
      toast.success(result.message || 'Faktura zaktualizowana');
      navigate('/faktury');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const conflict = conflictFromError(err);
        if (conflict) {
          setPendingConflict(conflict);
          return;
        }
      }
      toast.error(err instanceof ApiError ? err.message : 'Błąd aktualizacji faktury');
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (mode === 'create') void handleCreateSubmit();
    else void handleEditSubmit();
  }

  async function resolveConflict(action: 'create_new' | 'use_existing' | 'update_seller') {
    const conflict = pendingConflict;
    setPendingConflict(null);
    if (!conflict) return;
    setIsSubmitting(true);
    try {
      if (mode === 'create') {
        const fd = pendingFormDataRef.current;
        if (!fd) return;
        fd.set('seller_action', action);
        if (conflict.kind === 'name_mismatch') fd.set('existing_seller_id', String(conflict.existingSellerId));
        const result = await invoicesApi.create(fd);
        toast.success('Faktura została dodana pomyślnie');
        if (result.warnings?.length) toast.info(result.warnings.join(', '));
        navigate('/faktury');
      } else if (invoiceId) {
        const payload: Record<string, unknown> = { ...values };
        delete payload.seller_address;
        const existingSellerId = conflict.kind === 'name_mismatch' ? conflict.existingSellerId : undefined;
        const result = await invoicesApi.confirmSeller(invoiceId, action, payload, existingSellerId);
        toast.success(result.message || 'Faktura zaktualizowana');
        navigate('/faktury');
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu faktury');
    } finally {
      setIsSubmitting(false);
    }
  }

  const invoice = invoiceState.data;
  const fileExt = file?.name.split('.').pop()?.toLowerCase();
  const isImageFile = file && (file.type.startsWith('image/') || ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'].includes(fileExt ?? ''));
  const isPdfFile = file && (file.type === 'application/pdf' || fileExt === 'pdf');

  const existingPdfExt = invoice?.pdf_path?.split('.').pop()?.toLowerCase() ?? '';
  const existingIsImage = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'tif', 'webp'].includes(existingPdfExt);

  return (
    <div className="refined-page page-fills-viewport animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">{mode === 'create' ? 'Nowa faktura' : 'Edytuj fakturę'}</h1>
          <p className="page-subtitle">{mode === 'create' ? 'Wprowadź dane faktury ręcznie' : 'Zaktualizuj dane faktury'}</p>
        </div>
      </header>

      <div className="invoice-form-layout">
        <form onSubmit={handleSubmit}>
          <FormSection legend="Podstawowe dane">
            <TextField label="Numer faktury" required id="invoice_number" placeholder="FV/2024/01/001" value={values.invoice_number} onChange={(e) => set('invoice_number', e.target.value)} />
            <SelectField label="Status płatności" id="status" options={STATUS_OPTIONS} value={values.status} onChange={(e) => set('status', e.target.value)} />
            <TextField label="Data wystawienia" required id="invoice_date" type="date" value={values.invoice_date} onChange={(e) => set('invoice_date', e.target.value)} />
            <TextField label="Termin płatności" id="payment_due_date" type="date" value={values.payment_due_date} onChange={(e) => set('payment_due_date', e.target.value)} />
            <TextField
              label="Forma płatności"
              id="payment_term"
              fullWidth
              placeholder="np. Przelew, POBRANIE, 7 dni, 14 dni"
              value={values.payment_term}
              onChange={(e) => set('payment_term', e.target.value)}
            />
          </FormSection>

          <FormSection legend="Dane sprzedawcy">
            <TextField label="Nazwa sprzedawcy" required id="seller_name" fullWidth value={values.seller_name} onChange={(e) => set('seller_name', e.target.value)} />
            <TextField label="NIP" id="seller_nip" placeholder="np. 123-456-78-90" value={values.seller_nip} onChange={(e) => set('seller_nip', e.target.value)} />
            <TextField label="Numer konta bankowego" id="bank_account" placeholder="np. PL 12 1234 1234 1234 1234 1234 1234" value={values.bank_account} onChange={(e) => set('bank_account', e.target.value)} />
            {mode === 'create' && (
              <TextareaField label="Adres sprzedawcy" id="seller_address" fullWidth rows={1} value={values.seller_address} onChange={(e) => set('seller_address', e.target.value)} />
            )}
          </FormSection>

          <FormSection legend="Kwoty">
            <TextField label="Kwota" required id="amount" type="number" step="0.01" placeholder="np. 1234.56" value={values.amount} onChange={(e) => set('amount', e.target.value)} />
            <SelectField label="Waluta" id="currency" options={CURRENCY_OPTIONS} value={values.currency} onChange={(e) => set('currency', e.target.value)} />
            {mode === 'edit' && invoice?.ocr_confidence != null && (
              <div>
                <p className="form-label">Pewność OCR</p>
                <span className={`ocr-badge ${invoice.ocr_confidence >= 80 ? 'ocr-high' : invoice.ocr_confidence >= 60 ? 'ocr-medium' : 'ocr-low'}`}>{Math.round(invoice.ocr_confidence)}%</span>
              </div>
            )}
          </FormSection>

          <FormActions submitLabel={mode === 'create' ? 'Zapisz fakturę' : 'Zapisz zmiany'} isLoading={isSubmitting} cancelHref="/faktury" />
        </form>

        <div>
          {mode === 'create' ? (
            <div className="invoice-doc-card">
              <div className="invoice-doc-header">
                <span>Plik dokumentu</span>
                {file && (
                  <Button variant="ghost" small icon="delete" onClick={clearFile}>
                    Usuń plik
                  </Button>
                )}
              </div>
              {file && filePreviewUrl ? (
                <div className="invoice-doc-body">
                  {isPdfFile ? (
                    // `#navpanes=0` (fix #5, react-ui-corrections_19080026.txt) —
                    // Chrome's built-in PDF viewer shows its own page-thumbnails
                    // sidebar by default, eating into this already-narrow panel's
                    // width and shrinking the actual page view. This is a
                    // browser-native PDF-viewer URL param (not our app's CSS),
                    // same fix applied to the edit-mode preview below.
                    <iframe src={`${filePreviewUrl}#navpanes=0`} title="Podgląd pliku" />
                  ) : isImageFile ? (
                    <img src={filePreviewUrl} alt="Podgląd pliku" />
                  ) : (
                    <p className="empty-text">{file.name}</p>
                  )}
                </div>
              ) : (
                <div className="invoice-upload-placeholder" onClick={() => fileInputRef.current?.click()}>
                  <input ref={fileInputRef} type="file" style={{ display: 'none' }} accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif,.bmp,application/pdf,image/*" onChange={handleFileChange} />
                  <Icon name="upload_file" />
                  <p>Kliknij, aby wybrać plik</p>
                  <p className="invoice-upload-hint">PDF, JPG, PNG (max 10MB)</p>
                </div>
              )}
            </div>
          ) : (
            <div className="invoice-doc-card">
              <div className="invoice-doc-header">
                <span>Podgląd {existingIsImage ? 'obrazu' : 'PDF'}</span>
                {invoice?.pdf_path && (
                  <a href={invoicesApi.pdfUrl(invoice.id)} target="_blank" rel="noreferrer" className="action-btn" title="Otwórz w nowej karcie">
                    <Icon name="open_in_new" />
                  </a>
                )}
              </div>
              <div className="invoice-doc-body">
                {invoice?.pdf_path ? (
                  existingIsImage ? (
                    <img src={invoicesApi.pdfUrl(invoice.id)} alt="Podgląd faktury" />
                  ) : (
                    <iframe src={`${invoicesApi.pdfUrl(invoice.id)}#navpanes=0`} title="Podgląd PDF faktury" />
                  )
                ) : (
                  <p className="empty-text">Ta faktura nie ma załączonego pliku</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {pendingConflict?.kind === 'name_mismatch' && (
        <Modal
          isOpen
          onClose={() => setPendingConflict(null)}
          title="Konflikt danych sprzedawcy"
          footer={
            <>
              <Button variant="secondary" disabled={isSubmitting} onClick={() => setPendingConflict(null)}>
                Anuluj
              </Button>
              <Button variant="secondary" icon="people" disabled={isSubmitting} onClick={() => resolveConflict('use_existing')}>
                Użyj istniejącego
              </Button>
              <Button variant="primary" icon="edit" disabled={isSubmitting} onClick={() => resolveConflict('update_seller')}>
                Zaktualizuj nazwę
              </Button>
            </>
          }
        >
          <p>
            NIP <strong>{pendingConflict.nip}</strong> już istnieje w bazie z inną nazwą.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
            <div>
              <p className="form-label">Istniejąca nazwa</p>
              <p style={{ fontWeight: 600 }}>{pendingConflict.existingName}</p>
            </div>
            <div>
              <p className="form-label">Nazwa na fakturze</p>
              <p style={{ fontWeight: 600 }}>{pendingConflict.proposedName}</p>
            </div>
          </div>
        </Modal>
      )}

      {pendingConflict?.kind === 'new_seller' && (
        <Modal
          isOpen
          onClose={() => setPendingConflict(null)}
          title="Nowy sprzedawca"
          footer={
            <>
              <Button variant="secondary" disabled={isSubmitting} onClick={() => setPendingConflict(null)}>
                Nie, anuluj zapis faktury
              </Button>
              <Button variant="primary" icon="add" disabled={isSubmitting} onClick={() => resolveConflict('create_new')}>
                Tak, utwórz nowego sprzedawcę
              </Button>
            </>
          }
        >
          <p>
            Sprzedawca z NIP <strong>{pendingConflict.nip}</strong> nie istnieje jeszcze w bazie.
          </p>
          <p style={{ marginTop: '0.5rem' }}>
            Nazwa: <strong>{pendingConflict.name}</strong>
          </p>
          <p style={{ marginTop: '0.75rem', color: 'var(--color-ink-muted)' }}>Czy chcesz utworzyć nowego sprzedawcę w bazie danych?</p>
        </Modal>
      )}
    </div>
  );
}
