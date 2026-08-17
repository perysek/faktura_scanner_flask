/** Full-viewport loading state shown while AuthContext's initial `/auth/me`
 * session-check is in flight (DESIGN.md §15.1) — used by ProtectedRoute and
 * the app shell so neither flash-renders a wrong state before the real
 * session status is known. */
export function LoadingScreen() {
  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--color-surface-warm)',
        color: 'var(--color-ink-subtle)',
        fontSize: '0.875rem',
      }}
      role="status"
      aria-live="polite"
    >
      Ładowanie…
    </div>
  );
}
