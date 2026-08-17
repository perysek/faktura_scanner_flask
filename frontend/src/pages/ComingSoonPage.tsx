/**
 * Placeholder for modules not yet migrated (Faza 2, see module-inventory.md).
 * Reachable only if the user's real backend permissions allow it — the route
 * guard and sidebar link are already correct (implementation-log.md Decision
 * D7); only the page content is still pending.
 */
export function ComingSoonPage({ title }: { title?: string }) {
  return (
    <div className="refined-page" style={{ maxWidth: '640px', margin: '4rem auto', textAlign: 'center' }}>
      <h1 className="page-title">{title ?? 'Wkrótce'}</h1>
      <p className="page-subtitle" style={{ marginTop: '0.5rem' }}>
        Ten moduł jest w trakcie migracji na nowy interfejs.
      </p>
    </div>
  );
}
