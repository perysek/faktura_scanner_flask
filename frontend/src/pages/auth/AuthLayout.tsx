import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

/**
 * Shared layout for the three auth screens — DESIGN.md §15.5. Full-height
 * flex-centered column on the app's warm canvas, independent of the
 * authenticated app shell (no sidebar, no header/footer chrome).
 */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth-layout">
      <div className="auth-card-wrap">
        <div className="refined-card">
          <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            <Link to="/" className="logo-home-link" title="Strona główna" aria-label="Wróć na stronę główną">
              <img
                src="/logo-inline.webp"
                alt="MyWay Nails &amp; Beauty"
                style={{ display: 'block', width: '100%', maxWidth: '220px', height: 'auto', objectFit: 'contain', margin: '0 auto' }}
              />
            </Link>
          </div>
          {children}
          <div className="refined-footer">
            <p>© {new Date().getFullYear()} MyWay Beauty Salon. Wszelkie prawa zastrzeżone.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
