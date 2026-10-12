import { Navigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { expandMonthSidebar } from '../../pages/appointments/CalendarMonthSidebar';

/** Same breakpoint as the phone layouts (useIsMobile(640)). */
export function isPhoneViewport(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(max-width: 640px)').matches;
}

/**
 * The app's landing page (`/`, also where login sends you). Desktop users with
 * Wizyty access land on the day calendar for today with the 3-month panel
 * expanded; everyone else, and every phone, keeps the old landing (Pulpit).
 * No loop: /wizyty/* bounces users WITHOUT access back to `/`, and those go to
 * /dashboard here.
 */
export function HomeRedirect() {
  const auth = useAuth();
  if (!isPhoneViewport() && auth.hasModuleAccess('appointments')) {
    expandMonthSidebar();
    return <Navigate to="/wizyty/kalendarz" replace />;
  }
  return <Navigate to="/dashboard" replace />;
}
