/** The single source of "who may do what to which account" for the SPA. The
 * list, the view page and the form all call these, so the three can never
 * disagree. Every rule mirrors a refusal the backend enforces regardless
 * (routes/users/routes.py) — the UI just doesn't offer what the API would reject. */

interface Actor {
  id: number;
  role: string;
}

interface Target {
  id: number;
  role: string;
}

/** Only the owner (superuser) touches superuser accounts. */
export function canManageUser(actor: Actor | null | undefined, target: Pick<Target, 'role'>): boolean {
  if (!actor) return false;
  return actor.role === 'superuser' || target.role !== 'superuser';
}

/** Deactivate / delete: never yourself, never an account you can't manage. */
export function canRemoveUser(actor: Actor | null | undefined, target: Target): boolean {
  return !!actor && actor.id !== target.id && canManageUser(actor, target);
}

/** Resetting someone else's password is an owner-only action in the UI. */
export function canResetPassword(actor: Actor | null | undefined, target: Target): boolean {
  return actor?.role === 'superuser' && canManageUser(actor, target);
}

/** The superuser role is only ever offered to the owner. */
export function assignableRoles<T extends { name: string }>(actor: Actor | null | undefined, roles: T[]): T[] {
  return actor?.role === 'superuser' ? roles : roles.filter((r) => r.name !== 'superuser');
}

/** "1 użytkownik", "3 użytkownicy", "5 użytkowników" — Polish numeral agreement. */
export function usersLabel(n: number): string {
  if (n === 1) return '1 użytkownik';
  const last = n % 10;
  const lastTwo = n % 100;
  if (last >= 2 && last <= 4 && !(lastTwo >= 12 && lastTwo <= 14)) return `${n} użytkownicy`;
  return `${n} użytkowników`;
}

export function initials(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  const first = parts[0][0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1][0] ?? '') : (parts[0][1] ?? '');
  return (first + last).toUpperCase();
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('pl-PL', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

export function employmentStatusLabel(status: string): string {
  if (status === 'active') return 'Aktywny';
  if (status === 'on_leave') return 'Na urlopie';
  if (status === 'terminated') return 'Zwolniony';
  return status;
}
