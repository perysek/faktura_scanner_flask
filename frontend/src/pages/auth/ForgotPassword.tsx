import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError } from '../../lib/api/client';
import { Button } from '../../components/ui/Button';
import { AuthLayout } from './AuthLayout';

interface ForgotPasswordResponse {
  success: true;
  reset_url: string | null;
}

/**
 * Forgot-password screen — DESIGN.md §15.3. The dev-only "show the link on
 * screen instead of emailing it" delivery choice is intentional (see §15.3
 * and implementation-log.md Decision D4) — the response shape from the
 * backend is identical whether or not the account exists, so this screen
 * can't leak account existence either.
 */
export function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [resetUrl, setResetUrl] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const data = await api.post<ForgotPasswordResponse>('/auth/forgot-password', { email });
      setResetUrl(data.reset_url);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Nie udało się połączyć z serwerem');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <div style={{ marginBottom: '2rem' }}>
        <h1 className="refined-title refined-title-sm">Odzyskiwanie hasła</h1>
        <p className="refined-subtitle">Podaj adres email przypisany do konta</p>
      </div>

      {error && (
        <div className="flash-message flash-error" role="alert">
          {error}
        </div>
      )}

      {submitted ? (
        <>
          {/* Enumeration-safe message: neither reads as "found you" nor "not found" (§15.5). */}
          <div className="neutral-notice">
            Jeśli konto z podanym adresem istnieje, poniżej znajdziesz link do zresetowania hasła.
          </div>

          {resetUrl && (
            <div className="reset-link-box">
              <p className="reset-link-title">Link do resetowania hasła</p>
              <input
                type="text"
                className="reset-link-url"
                value={resetUrl}
                readOnly
                onClick={(e) => e.currentTarget.select()}
              />
              <p className="reset-link-hint">
                Kliknij w link lub skopiuj go i wklej w pasku adresu przeglądarki. Link jest ważny przez{' '}
                <strong>1 godzinę</strong>.
              </p>
            </div>
          )}

          {resetUrl && (
            <div style={{ marginTop: '1.25rem', textAlign: 'center' }}>
              <a href={resetUrl} className="refined-btn-primary" style={{ display: 'inline-block', textDecoration: 'none', padding: '0.625rem 1.5rem' }}>
                Przejdź do formularza
              </a>
            </div>
          )}
        </>
      ) : (
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div>
            <label htmlFor="email" className="refined-label">
              Adres email
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              className="refined-input"
              placeholder="twoj@email.pl"
            />
          </div>

          <Button type="submit" variant="primary" isLoading={isSubmitting} loadingText="Wysyłanie…" style={{ width: '100%' }}>
            Wyślij link resetujący
          </Button>
        </form>
      )}

      <Link to="/login" className="back-link">
        ← Wróć do logowania
      </Link>
    </AuthLayout>
  );
}
