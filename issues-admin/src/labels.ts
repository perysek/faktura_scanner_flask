import type { CloseReason, Kind, Priority, SortKey, Status, ViewKey } from './api';

export const STATUS_LABEL: Record<Status, string> = {
  new: 'Nowe',
  seen: 'Przeczytane',
  in_progress: 'W toku',
  waiting_user: 'Czeka na użytkownika',
  resolved: 'Rozwiązane',
  closed: 'Zamknięte',
};

export const PRIORITY_LABEL: Record<Priority, string> = {
  urgent: 'Pilny',
  high: 'Wysoki',
  normal: 'Normalny',
  low: 'Niski',
};

export const CLOSE_REASON_LABEL: Record<CloseReason, string> = {
  done: 'Załatwione',
  confirmed: 'Potwierdzone przez użytkownika',
  declined: 'Odrzucone',
  duplicate: 'Duplikat',
};

export const KIND_LABEL: Record<Kind, string> = { problem: 'Problem', idea: 'Pomysł' };

export const ROLE_LABEL: Record<string, string> = {
  superuser: 'Superadmin',
  admin: 'Administrator',
  accountant: 'Księgowa',
  receptionist: 'Recepcjonistka',
  stylist: 'Stylistka',
};

export const VIEWS: { key: ViewKey; label: string; icon: string; group: 'queue' | 'archive' }[] = [
  { key: 'open', label: 'Wszystkie otwarte', icon: 'inbox', group: 'queue' },
  { key: 'unread', label: 'Nieprzeczytane', icon: 'email', group: 'queue' },
  { key: 'new', label: 'Nowe', icon: 'add_circle_outline', group: 'queue' },
  { key: 'in_progress', label: 'W toku', icon: 'hourglass_top', group: 'queue' },
  { key: 'waiting_user', label: 'Czeka na użytkownika', icon: 'schedule', group: 'queue' },
  { key: 'mine', label: 'Przypisane do mnie', icon: 'person', group: 'queue' },
  { key: 'unassigned', label: 'Nieprzypisane', icon: 'person_off', group: 'queue' },
  { key: 'resolved', label: 'Rozwiązane', icon: 'check_circle', group: 'archive' },
  { key: 'closed', label: 'Zamknięte', icon: 'done_all', group: 'archive' },
  { key: 'all', label: 'Wszystkie', icon: 'folder_open', group: 'archive' },
];

export const SORT_LABEL: Record<SortKey, string> = {
  updated: 'Aktywność',
  created: 'Najnowsze',
  oldest: 'Najstarsze',
  priority: 'Priorytet',
};

/** Saved replies ("Szablony") — plan 261013 §7. */
export const CANNED_REPLIES: { label: string; text: string }[] = [
  { label: 'Potwierdzenie przyjęcia', text: 'Dzięki za zgłoszenie! Sprawdzam to i wracam z odpowiedzią najszybciej, jak się da.' },
  {
    label: 'Prośba o szczegóły',
    text: 'Żeby to dobrze sprawdzić, napisz proszę: na jakim urządzeniu to się dzieje (telefon czy komputer) i mniej więcej o której godzinie ostatnio się pojawiło?',
  },
  {
    label: 'Naprawione — sprawdź',
    text: 'Poprawione. Odśwież stronę (na telefonie przeciągnij ekran w dół) i daj znać, czy już wszystko gra 🙂',
  },
  { label: 'Instrukcja', text: 'To da się zrobić tak: ' },
  { label: 'Pomysł przyjęty', text: 'Dzięki za pomysł! Dopisałem go do listy zmian — dam znać tutaj, gdy będzie gotowy.' },
  { label: 'Pomysł odrzucony', text: 'Dzięki za pomysł. Tym razem go nie wprowadzimy, bo ' },
];

export function personLabel(name: string | null | undefined, role: string | null | undefined): string {
  const who = name || 'Nieznany użytkownik';
  return role ? `${who} · ${ROLE_LABEL[role] ?? role}` : who;
}
