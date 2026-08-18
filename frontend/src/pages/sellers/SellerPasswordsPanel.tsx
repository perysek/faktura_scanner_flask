import { useEffect, useState } from 'react';
import './SellersListPage.css';
import { Modal } from '../../components/ui/Modal';
import { Button } from '../../components/ui/Button';
import { useToast } from '../../components/feedback/ToastProvider';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { sellerPasswordsApi } from '../../lib/api/sellerPasswords';
import { ApiError } from '../../lib/api/client';
import type { Seller, SellerPdfPassword } from '../../types/seller';

interface SellerPasswordsPanelProps {
  isOpen: boolean;
  onClose: () => void;
  sellers: Seller[];
}

/**
 * "Hasła PDF sprzedawców" — one of Sprzedawcy's three sub-features
 * (module-inventory.md korekta 2026-08-17). Ported from list_refined.html's
 * `openPasswordsPanel()`/`showPanelForm()`/`savePanelPassword()`/
 * `editPasswordEntry()`/`deletePasswordEntry()` — a single Modals.show()
 * call juggling a table + an inline add/edit form via raw DOM toggling.
 * Here that's just two pieces of component state (`passwords`, `editing`).
 */
export function SellerPasswordsPanel({ isOpen, onClose, sellers }: SellerPasswordsPanelProps) {
  const toast = useToast();
  const confirm = useConfirm();
  const [passwords, setPasswords] = useState<SellerPdfPassword[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<SellerPdfPassword | 'new' | null>(null);
  const [sellerId, setSellerId] = useState('');
  const [emailPattern, setEmailPattern] = useState('');
  const [password, setPassword] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await sellerPasswordsApi.getAll();
      setPasswords(data.passwords);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd ładowania haseł');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isOpen) {
      load();
      setEditing(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  function openForm(entry: SellerPdfPassword | 'new') {
    setEditing(entry);
    if (entry === 'new') {
      setSellerId('');
      setEmailPattern('');
      setPassword('');
      setDescription('');
    } else {
      setSellerId(entry.seller_id ? String(entry.seller_id) : '');
      setEmailPattern(entry.email_sender_pattern ?? '');
      setPassword(entry.pdf_password);
      setDescription(entry.description ?? '');
    }
  }

  async function handleSave() {
    if (!password.trim()) {
      toast.error('Hasło PDF jest wymagane');
      return;
    }
    setSaving(true);
    const values = {
      seller_id: sellerId ? parseInt(sellerId, 10) : null,
      email_sender_pattern: emailPattern.trim() || null,
      pdf_password: password.trim(),
      description: description.trim() || null,
    };
    try {
      if (editing && editing !== 'new') {
        await sellerPasswordsApi.update(editing.id, values);
        toast.success('Hasło zaktualizowane');
      } else {
        await sellerPasswordsApi.create(values);
        toast.success('Hasło dodane');
      }
      setEditing(null);
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd zapisu');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(entry: SellerPdfPassword) {
    const ok = await confirm({
      title: 'Kasujemy hasło PDF?',
      message: 'Skasować to hasło? Zaszyfrowane faktury tego sprzedawcy same się potem nie otworzą — będziesz klikać ręcznie.',
      confirmText: 'Kasuj',
    });
    if (!ok) return;
    try {
      await sellerPasswordsApi.delete(entry.id);
      toast.success('Hasło PDF usunięte');
      await load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd usuwania');
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Hasła PDF sprzedawców"
      size="large"
      footer={
        <>
          <Button variant="secondary" icon="add" onClick={() => openForm('new')}>
            Dodaj hasło
          </Button>
          <Button variant="primary" onClick={onClose}>
            Zamknij
          </Button>
        </>
      }
    >
      <p className="pwd-panel-intro">Hasła są używane do automatycznego odblokowywania zaszyfrowanych faktur PDF podczas importu.</p>

      <div className="table-container" style={{ maxHeight: '400px' }}>
        <table className="refined-table">
          <thead>
            <tr>
              <th>Sprzedawca</th>
              <th>Wzorzec e-mail</th>
              <th>Hasło</th>
              <th>Opis</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="pwd-panel-empty">
                  Ładowanie…
                </td>
              </tr>
            ) : !passwords || passwords.length === 0 ? (
              <tr>
                <td colSpan={5} className="pwd-panel-empty">
                  Brak skonfigurowanych haseł PDF
                </td>
              </tr>
            ) : (
              passwords.map((p) => (
                // No "view" action here — row-click mirrors "Edytuj" — DESIGN.md §20.
                <tr key={p.id} className="row-clickable" onClick={(e) => { if ((e.target as HTMLElement).closest('button')) return; openForm(p); }}>
                  <td>{p.seller_name ? <span style={{ fontWeight: 500 }}>{p.seller_name}</span> : <span className="pwd-panel-dim">—</span>}</td>
                  <td>{p.email_sender_pattern ? <span className="nip-number">{p.email_sender_pattern}</span> : <span className="pwd-panel-dim">—</span>}</td>
                  <td>
                    <code className="pwd-code">{p.pdf_password}</code>
                  </td>
                  <td>{p.description && <span className="pwd-panel-desc">{p.description}</span>}</td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '0.25rem', justifyContent: 'flex-end' }}>
                      <button type="button" className="action-btn" onClick={() => openForm(p)} title="Edytuj">
                        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      <button type="button" className="action-btn delete" onClick={() => handleDelete(p)} title="Usuń">
                        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="pwd-panel-form">
          <h4>{editing === 'new' ? 'Nowe hasło' : 'Edytuj hasło'}</h4>
          <div className="pwd-panel-form-grid">
            <div>
              <label className="form-label" htmlFor="pwd-panel-seller">
                Sprzedawca
              </label>
              <select id="pwd-panel-seller" className="form-select" value={sellerId} onChange={(e) => setSellerId(e.target.value)}>
                <option value="">— brak (wzorzec e-mail) —</option>
                {sellers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.seller_name} ({s.seller_nip || 'brak NIP'})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label" htmlFor="pwd-panel-email">
                Wzorzec e-mail
              </label>
              <input id="pwd-panel-email" className="form-input" placeholder="np. noreply@firma.pl" value={emailPattern} onChange={(e) => setEmailPattern(e.target.value)} />
            </div>
            <div>
              <label className="form-label" htmlFor="pwd-panel-password">
                Hasło PDF <span className="form-required">*</span>
              </label>
              <input id="pwd-panel-password" className="form-input" placeholder="Hasło do odblokowania PDF" autoComplete="off" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div>
              <label className="form-label" htmlFor="pwd-panel-description">
                Opis
              </label>
              <input id="pwd-panel-description" className="form-input" placeholder="np. NIP sprzedawcy" value={description} onChange={(e) => setDescription(e.target.value)} />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
            <Button variant="primary" isLoading={saving} loadingText="Zapisywanie…" onClick={handleSave}>
              Zapisz
            </Button>
            <Button variant="secondary" onClick={() => setEditing(null)}>
              Anuluj
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
