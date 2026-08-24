import { useNavigate } from 'react-router-dom';
import { useEscapeAction } from './escapeScope';

/**
 * Page-level "Escape = go back" binding for a single fixed target —
 * DESIGN.md §11.2. Every Detail page's "Powrót do listy" link gets one call
 * to this at the component's top level (the visible button and the Escape
 * binding always point at the same href — no need to re-derive it twice).
 * `FormActions`' "Anuluj" button uses `useEscapeAction` directly instead,
 * since it also supports an arbitrary `onCancel` callback, not just a fixed
 * href. Ported from the original app's per-page inline `keydown`/Escape
 * handlers (e.g. templates/clients/view.html, templates/employees/view.html)
 * — same guard behaviour (`useEscapeAction`'s claim check + typing guard),
 * just centralised instead of copy-pasted per page.
 */
export function useEscapeBack(href: string | undefined, enabled = true): void {
  const navigate = useNavigate();
  useEscapeAction(() => navigate(href as string), enabled && !!href);
}
