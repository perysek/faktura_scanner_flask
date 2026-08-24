import { useEffect, useState } from 'react';
import './SettingsPages.css';
import { emailSettingsApi } from '../../lib/api/emailSettings';
import { ApiError } from '../../lib/api/client';
import { useToast } from '../../components/feedback/ToastProvider';
import { Button } from '../../components/ui/Button';
import type { EmailSettings } from '../../types/settings';

const EMPTY: EmailSettings = { imap_server: '', imap_port: 993, email: '', password: '' };

/** Ustawienia e-mail — IMAP config for the invoice-import mailbox. Ported
 * from templates/settings/email.html; backend (`/api/email/*`,
 * routes/api_routes.py:1493-1601) was already fully JSON, no server change
 * needed here. Single form, 1:1 with the original: load → edit → save,
 * plus a live "Testuj połączenie" that hits the same IMAP creds without
 * saving them first. */
export function EmailSettingsPage() {
  const toast = useToast();
  const [values, setValues] = useState<EmailSettings>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    let cancelled = false;
    emailSettingsApi
      .get()
      .then((settings) => {
        if (!cancelled) setValues({ ...EMPTY, ...settings });
      })
      .catch(() => {
        /* No settings saved yet — keep the empty form, same as the original
         * page's behavior when config/email_settings.json doesn't exist. */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function update<K extends keyof EmailSettings>(key: K, value: EmailSettings[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await emailSettingsApi.save(values);
      toast.success('Ustawienia e-mail zapisane');
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Nie udało się zapisać ustawień');
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    if (!values.imap_server || !values.email || !values.password) {
      toast.warning('Uzupełnij serwer, e-mail i hasło przed testem');
      return;
    }
    setTesting(true);
    try {
      const result = await emailSettingsApi.test(values);
      if (result.success) {
        toast.success('Połączenie IMAP działa');
      } else {
        toast.error(result.error || 'Połączenie nieudane');
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Błąd testu połączenia');
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="refined-page settings-page animate-fade-up">
      <header className="page-header">
        <div>
          <h1 className="page-title">Ustawienia e-mail</h1>
          <p className="page-subtitle">Konfiguracja IMAP dla automatycznego importu faktur</p>
        </div>
      </header>

      <form className="form-card" onSubmit={handleSave}>
        <div className="form-grid">
          <div>
            <label className="form-label" htmlFor="imap-server">
              Serwer IMAP <span className="required-mark">*</span>
            </label>
            <input
              id="imap-server"
              className="form-input"
              placeholder="np. imap.gmail.com"
              required
              disabled={loading}
              value={values.imap_server}
              onChange={(e) => update('imap_server', e.target.value)}
            />
            <p className="form-helper-text">Adres serwera IMAP (np. imap.gmail.com, outlook.office365.com)</p>
          </div>
          <div>
            <label className="form-label" htmlFor="imap-port">
              Port IMAP
            </label>
            <input
              id="imap-port"
              type="number"
              className="form-input"
              disabled={loading}
              value={values.imap_port}
              onChange={(e) => update('imap_port', Number(e.target.value) || 993)}
            />
            <p className="form-helper-text">Domyślnie 993 (SSL)</p>
          </div>
          <div>
            <label className="form-label" htmlFor="imap-email">
              Adres e-mail <span className="required-mark">*</span>
            </label>
            <input
              id="imap-email"
              type="email"
              className="form-input"
              placeholder="twoj@email.com"
              required
              disabled={loading}
              value={values.email}
              onChange={(e) => update('email', e.target.value)}
            />
          </div>
          <div>
            <label className="form-label" htmlFor="imap-password">
              Hasło <span className="required-mark">*</span>
            </label>
            <div className="password-field">
              <input
                id="imap-password"
                type={showPassword ? 'text' : 'password'}
                className="form-input"
                required
                disabled={loading}
                value={values.password}
                onChange={(e) => update('password', e.target.value)}
              />
              <button type="button" className="password-toggle" onClick={() => setShowPassword((s) => !s)}>
                {showPassword ? 'Ukryj' : 'Pokaż'}
              </button>
            </div>
            <p className="form-helper-text">Dla Gmaila użyj hasła aplikacji, nie głównego hasła konta</p>
          </div>
        </div>

        <div className="form-actions">
          <Button type="submit" variant="primary" icon="save" isLoading={saving} loadingText="Zapisywanie…">
            Zapisz ustawienia
          </Button>
          <Button type="button" variant="secondary" icon="sync" isLoading={testing} loadingText="Testowanie…" onClick={handleTest}>
            Testuj połączenie
          </Button>
        </div>
      </form>

      <div className="info-card">
        <div className="info-header">
          <h3 className="info-title">Instrukcja konfiguracji</h3>
        </div>
        <div className="info-section">
          <h4 className="info-section-title">Gmail:</h4>
          <ul className="info-list">
            <li>
              Serwer: <code>imap.gmail.com</code>
            </li>
            <li>
              Port: <code>993</code>
            </li>
            <li>Włącz weryfikację dwuetapową w ustawieniach konta Google</li>
            <li>
              Wygeneruj hasło aplikacji w{' '}
              <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noreferrer">
                myaccount.google.com/apppasswords
              </a>
            </li>
          </ul>
        </div>
        <div className="info-section">
          <h4 className="info-section-title">Outlook/Office 365:</h4>
          <ul className="info-list">
            <li>
              Serwer: <code>outlook.office365.com</code>
            </li>
            <li>
              Port: <code>993</code>
            </li>
            <li>Użyj hasła do konta Microsoft</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
