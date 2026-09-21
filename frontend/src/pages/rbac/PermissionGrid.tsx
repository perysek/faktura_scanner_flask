import { Switch } from './Switch';
import type { RolePermissionFlags } from '../../types/rbac';

type FlagKey = keyof RolePermissionFlags;

interface FlagDef {
  key: FlagKey;
  label: string;
  hint: string;
}

const COMMON_FLAGS: FlagDef[] = [
  { key: 'read_only', label: 'Tylko do odczytu', hint: 'Może przeglądać, nie może zmieniać' },
  { key: 'own_data', label: 'Tylko własne dane', hint: 'Widzi wyłącznie swoje rekordy' },
];

const MODULE_FLAGS: Record<string, FlagDef[]> = {
  services: [{ key: 'can_edit_price_history', label: 'Edycja historii cen', hint: 'Może poprawiać wpisy w historii zmian ceny' }],
  appointments: [{ key: 'can_send_sms', label: 'Wysyłanie SMS', hint: 'Ręczne SMS-y z widoku wizyty' }],
};

export const EMPTY_FLAGS: RolePermissionFlags = {
  has_access: false,
  read_only: false,
  own_data: false,
  can_edit_price_history: false,
  can_send_sms: false,
};

interface Props {
  modules: string[];
  names: Record<string, string>;
  flags: Record<string, RolePermissionFlags>;
  onChange: (module: string, key: FlagKey, value: boolean) => void;
}

/** One permission editor for role create AND edit: a card per module with a
 * master "dostęp" switch and, below it, the restricting/extra flags. Every row is
 * a <label> spanning the full width (≥48px on a phone), so the tap target is the
 * row, not the 44px track. Flags stay disabled until the module is switched on. */
export function PermissionGrid({ modules, names, flags, onChange }: Props) {
  return (
    <div className="perm-grid">
      {modules.map((mod) => {
        const f = flags[mod] ?? EMPTY_FLAGS;
        const label = names[mod] ?? mod;
        const flagDefs = [...COMMON_FLAGS, ...(MODULE_FLAGS[mod] ?? [])];
        return (
          <section key={mod} className={`perm-module${f.has_access ? ' is-on' : ''}`} aria-label={label}>
            <label className="perm-row perm-row--main">
              <span className="perm-text">
                <span className="perm-name">{label}</span>
                <span className="perm-key">{mod}</span>
              </span>
              <Switch checked={f.has_access} onChange={(e) => onChange(mod, 'has_access', e.target.checked)} aria-label={`Dostęp do modułu: ${label}`} />
            </label>
            <div className="perm-flags">
              {flagDefs.map((def) => (
                <label key={def.key} className="perm-row perm-row--flag">
                  <span className="perm-text">
                    <span className="perm-flag-label">{def.label}</span>
                    <span className="perm-hint">{def.hint}</span>
                  </span>
                  <Switch small checked={f[def.key]} disabled={!f.has_access} onChange={(e) => onChange(mod, def.key, e.target.checked)} aria-label={`${def.label} — ${label}`} />
                </label>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
