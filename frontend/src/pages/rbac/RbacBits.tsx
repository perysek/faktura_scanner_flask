import { Button } from '../../components/ui/Button';
import { initials } from './rbacRules';

/** Role pill — the owner (superuser) gets its own tone, everyone else the neutral one. */
export function RoleBadge({ role, label }: { role: string; label: string }) {
  return <span className={`rbac-badge ${role === 'superuser' ? 'rbac-badge--owner' : 'rbac-badge--role'}`}>{label}</span>;
}

export function StatusBadge({ active }: { active: boolean }) {
  return <span className={`rbac-badge ${active ? 'rbac-badge--active' : 'rbac-badge--inactive'}`}>{active ? 'Aktywny' : 'Nieaktywny'}</span>;
}

export function Avatar({ name, size = 'md' }: { name: string; size?: 'md' | 'lg' }) {
  return (
    <span className={`rbac-avatar rbac-avatar--${size}`} aria-hidden="true">
      {initials(name)}
    </span>
  );
}

export function EmptyNotice({ children }: { children: string }) {
  return <div className="rbac-empty-state">{children}</div>;
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rbac-empty-state" role="alert">
      <p style={{ marginBottom: onRetry ? '1rem' : 0 }}>{message}</p>
      {onRetry && (
        <Button variant="secondary" icon="refresh" onClick={onRetry}>
          Spróbuj ponownie
        </Button>
      )}
    </div>
  );
}
