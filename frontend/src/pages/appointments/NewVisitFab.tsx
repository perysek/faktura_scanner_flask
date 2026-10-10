import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Icon } from '../../lib/icons/Icon';

/** Floating black "+" → new visit, on the Wizyty views (list, day, week, month). Same look as
 * the SMS back-to-top button; placement is CSS only (see `.appt-fab` in Appointments.css), so
 * render it as a direct child of the element it should sit in the corner of: `.cal-main` on the
 * list and day views, the page root on week and month. Renders nothing without write access to
 * 'appointments'. Phones have their own "+" in the bottom nav (CSS hides this one there). */
export function NewVisitFab() {
  const auth = useAuth();
  if (!auth.hasModuleWrite('appointments')) return null;
  return (
    <Link to="/wizyty/nowa" className="appt-fab" aria-label="Nowa wizyta" title="Nowa wizyta">
      <Icon name="add" />
    </Link>
  );
}
