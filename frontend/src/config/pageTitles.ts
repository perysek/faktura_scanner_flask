/**
 * Per-route mobile-header titles — DESIGN.md §12. Ported from
 * `config/page_titles.py`'s `PAGE_TITLES` dict, but the matching strategy is
 * DELIBERATELY different, not a 1:1 key copy (phase-00-foundations.md §0.4):
 * the Flask version keys off `request.endpoint` (exact match); this version
 * keys off `pathname.startsWith(prefix)` (prefix match). Longest/most
 * specific prefix is listed BEFORE shorter parent prefixes, since lookup is
 * first-match-wins.
 */
export const PAGE_TITLE_ENTRIES: Array<[string, string]> = [
  ['/dashboard', 'Pulpit'],
  ['/faktury', 'Faktury'],
  ['/sprzedawcy', 'Sprzedawcy'],
  ['/import-dokumentow', 'Wgraj faktury'],
  ['/analiza-biznesowa', 'Analityka'],
  ['/wskazniki-biznesowe', 'Wskaźniki biznesowe'],
  ['/wizyty', 'Wizyty'],
  ['/klienci/nowy', 'Nowy klient'],
  ['/klienci', 'Klienci'],
  ['/pracownicy', 'Pracownicy'],
  ['/nieobecnosci', 'Nieobecności'],
  ['/bilanse-urlopow', 'Bilanse urlopowe'],
  ['/moje-nieobecnosci', 'Moje nieobecności'],
  ['/uslugi', 'Usługi'],
  ['/kategorie-uslug', 'Kategorie usług'],
  ['/formy-zatrudnienia', 'Formy zatrudnienia'],
  ['/korekta/wizyty', 'Korekta wizyt'],
  ['/korekta/tabela', 'Korekta wizyt'],
  ['/historia', 'Historia'],
  ['/ustawienia/email', 'Ustawienia e-mail'],
  ['/uzytkownicy', 'Użytkownicy'],
  ['/poziomy-dostepu', 'Role'],
  ['/ustawienia/sms', 'Ustawienia SMS'],
  ['/import-danych', 'Import danych'],
  ['/instrukcja', 'Instrukcja obsługi'],
  ['/profil', 'Profil'],
];

export function pageTitleFor(pathname: string): string {
  for (const [prefix, title] of PAGE_TITLE_ENTRIES) {
    if (pathname.startsWith(prefix)) return title;
  }
  return '';
}
