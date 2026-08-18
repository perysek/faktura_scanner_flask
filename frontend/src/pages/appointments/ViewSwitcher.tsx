import { Link } from 'react-router-dom';

export interface ViewSwitcherProps {
  active: 'day' | 'week' | 'month' | 'list';
  /** Forwarded as `?date=`/`?employee_id=` on every tab link, so switching
   * views keeps looking at the same day/employee instead of resetting to
   * "today" — ported from list.html/calendar*.html's `updateViewLinks()`. */
  date?: string;
  employeeId?: number | null;
}

/** Dzień/Tydzień/Miesiąc/Lista tab strip — identical widget on all 4 Wizyty
 * pages (DESIGN.md has no prior instance of this pattern; first built here). */
export function ViewSwitcher({ active, date, employeeId }: ViewSwitcherProps) {
  const qs = new URLSearchParams();
  if (date) qs.set('date', date);
  if (employeeId) qs.set('employee_id', String(employeeId));
  const suffix = qs.toString() ? `?${qs.toString()}` : '';

  const tabs: Array<{ key: ViewSwitcherProps['active']; label: string; to: string }> = [
    { key: 'day', label: 'Dzień', to: `/wizyty/kalendarz${suffix}` },
    { key: 'week', label: 'Tydzień', to: `/wizyty/kalendarz/tydzien${suffix}` },
    { key: 'month', label: 'Miesiąc', to: `/wizyty/kalendarz/miesiac${suffix}` },
    { key: 'list', label: 'Lista', to: `/wizyty${suffix}` },
  ];

  return (
    <div className="view-toggle">
      {tabs.map((tab) => (
        <Link key={tab.key} to={tab.to} className={tab.key === active ? 'active' : undefined}>
          {tab.label}
        </Link>
      ))}
    </div>
  );
}
