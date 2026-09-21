import type { ModulePermissions } from '../../types/rbac';

const FLAG_LABELS = [
  ['read_only', 'tylko odczyt'],
  ['own_data', 'własne dane'],
  ['can_send_sms', 'SMS'],
  ['can_edit_price_history', 'historia cen'],
] as const;

interface Props {
  permissions: ModulePermissions;
  /** module key → Polish display name (the API sends these; never hardcode). */
  names: Record<string, string>;
  emptyText?: string;
}

/** Read-only summary of what a role can reach: one chip per module the role has
 * access to, with the restricting/extra flags spelled out next to it. */
export function ModuleChips({ permissions, names, emptyText = 'Brak dostępu do żadnego modułu.' }: Props) {
  const granted = Object.entries(permissions).filter(([, flags]) => flags.has_access);
  if (granted.length === 0) return <p className="rbac-muted">{emptyText}</p>;

  return (
    <ul className="module-chips">
      {granted.map(([mod, flags]) => (
        <li key={mod} className="module-chip">
          <span className="module-chip-name">{names[mod] ?? mod}</span>
          {FLAG_LABELS.filter(([key]) => flags[key]).map(([key, label]) => (
            <span key={key} className="module-chip-flag">
              {label}
            </span>
          ))}
        </li>
      ))}
    </ul>
  );
}
