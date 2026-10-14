import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, FormEvent } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useEscapeClaim } from '../../lib/a11y/escapeScope';
import { useFocusTrap } from '../../lib/a11y/useFocusTrap';
import { Icon } from '../../lib/icons/Icon';
import { Button } from '../ui/Button';
import { SelectField, TextareaField } from '../ui/form';

/**
 * "Napisz do administratora" — the ticket form opened by the sidebar row
 * 'Klikam w to co trzeba / ale coś mi nie pasuje'. Pops out of the bottom-left
 * corner of <main> (1×1px → 30vw × 60vh). FRONTEND ONLY for now: sending shows
 * the confirmation but nothing reaches the server yet — the API, inbox and
 * conversation view are designed in plans/261013-support-tickets/plan.md.
 */

type TicketKind = 'problem' | 'idea';

const KIND_COPY: Record<TicketKind, { title: string; lead: string; placeholder: string }> = {
  problem: {
    title: 'Zgłoś problem',
    lead: 'Coś nie działa? Błędy, dziwne zachowanie albo kłopot z ustawieniami: napisz tutaj.',
    placeholder:
      'Opisz, co klikasz i co się dzieje, np. „Dodaję wizytę na 15:00, klikam Zapisz i nic się nie dzieje”. Zdjęcie ekranu możesz dołączyć poniżej.',
  },
  idea: {
    title: 'Podziel się pomysłem',
    lead: 'Masz pomysł, co by Ci ułatwiło pracę? Każdy pomysł czytamy.',
    placeholder: 'Napisz, co by Ci ułatwiło pracę i jak to sobie wyobrażasz.',
  },
};

interface AreaOption {
  value: string;
  label: string;
  /** Routes that pre-select this area when the form is opened on them (plan §3 step 2).
   * First match in list order wins, so '/wizyty/nowa' must sit above '/wizyty'. */
  prefixes: string[];
}

/** 'Zgłoś problem' areas — Piotr's list (2026-10-14). No catch-all on purpose: when the
 * current page maps to none of them, the user has to pick one. */
const PROBLEM_AREAS: AreaOption[] = [
  { value: 'sms', label: 'Wysyłki SMS', prefixes: ['/ustawienia/sms'] },
  { value: 'rezerwacje', label: 'Rezerwacje wizyt', prefixes: ['/wizyty/nowa'] },
  { value: 'obsluga-wizyt', label: 'Obsługa wizyt', prefixes: ['/wizyty', '/korekta'] },
  { value: 'formularze', label: 'Formularze online klienta', prefixes: [] },
  { value: 'nieobecnosci', label: 'Nieobecności', prefixes: ['/nieobecnosci', '/bilanse-urlopow', '/moje-nieobecnosci'] },
  { value: 'faktury', label: 'Faktury', prefixes: ['/faktury', '/sprzedawcy'] },
  { value: 'przychody', label: 'Przychody', prefixes: ['/dashboard', '/analiza-biznesowa', '/wskazniki-biznesowe'] },
  { value: 'kalendarz', label: 'Kalendarz i konflikty', prefixes: [] },
  { value: 'personel', label: 'Zarządzanie personelem', prefixes: ['/pracownicy', '/formy-zatrudnienia'] },
  { value: 'wynagrodzenia', label: 'Wynagrodzenia', prefixes: [] },
  { value: 'uzytkownicy', label: 'Użytkownicy i poziomy dostępu', prefixes: ['/uzytkownicy', '/poziomy-dostepu', '/profil'] },
  { value: 'konfiguracja', label: 'Konfiguracja i ustawienia', prefixes: ['/ustawienia', '/uslugi', '/kategorie-uslug', '/historia'] },
];

/** 'Podziel się pomysłem' areas, named after the app's own sidebar sections. */
const IDEA_AREAS: AreaOption[] = [
  { value: 'wizyty', label: 'Wizyty', prefixes: ['/wizyty', '/korekta'] },
  { value: 'klienci', label: 'Klienci', prefixes: ['/klienci'] },
  { value: 'uslugi', label: 'Usługi i kategorie', prefixes: ['/uslugi', '/kategorie-uslug'] },
  { value: 'sms', label: 'Komunikacja SMS', prefixes: ['/ustawienia/sms'] },
  { value: 'nieobecnosci', label: 'Nieobecności i urlopy', prefixes: ['/nieobecnosci', '/bilanse-urlopow', '/moje-nieobecnosci'] },
  { value: 'pracownicy', label: 'Pracownicy', prefixes: ['/pracownicy', '/formy-zatrudnienia'] },
  { value: 'finanse', label: 'Koszty i dostawcy', prefixes: ['/faktury', '/sprzedawcy', '/dashboard'] },
  { value: 'analityka', label: 'Analityka', prefixes: ['/analiza-biznesowa', '/wskazniki-biznesowe'] },
  { value: 'konto', label: 'Logowanie i konto', prefixes: ['/profil', '/uzytkownicy', '/poziomy-dostepu'] },
  { value: 'inne', label: 'Inne / nie wiem', prefixes: [] },
];

const AREAS_BY_KIND: Record<TicketKind, AreaOption[]> = { problem: PROBLEM_AREAS, idea: IDEA_AREAS };

/** Pre-selected area for this page; '' (= "Wybierz…") for a problem with no match, 'inne' for an idea. */
function areaForPath(kind: TicketKind, pathname: string): string {
  const match = AREAS_BY_KIND[kind].find((area) => area.prefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`)));
  return match?.value ?? (kind === 'idea' ? 'inne' : '');
}

const MAX_PHOTOS = 3;
const MIN_TEXT = 10;
const POP_IN_MS = 420;
const POP_OUT_MS = 220;
/** Gap between the panel and <main>'s bottom-left corner. */
const ANCHOR_GAP_PX = 16;

export interface SupportTicketModalProps {
  onClose: () => void;
}

export function SupportTicketModal({ onClose }: SupportTicketModalProps) {
  const { pathname } = useLocation();
  const panelRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const closingRef = useRef(false);

  const [kind, setKind] = useState<TicketKind>('problem');
  const [area, setArea] = useState(() => areaForPath('problem', pathname));
  const [areaError, setAreaError] = useState<string | undefined>();
  const [text, setText] = useState('');
  const [photos, setPhotos] = useState<File[]>([]);
  const [error, setError] = useState<string | undefined>();
  const [sent, setSent] = useState(false);

  // Anchor to <main>'s bottom-left corner, measured once at open — the sidebar,
  // footer and mobile tab bar all sit outside <main>, so this clears every one of them.
  const [anchor] = useState<CSSProperties>(() => {
    const main = document.getElementById('main-content');
    if (!main) return { left: ANCHOR_GAP_PX, bottom: ANCHOR_GAP_PX };
    const rect = main.getBoundingClientRect();
    return {
      left: rect.left + ANCHOR_GAP_PX,
      bottom: window.innerHeight - rect.bottom + ANCHOR_GAP_PX,
      '--ticket-anchor-left': `${rect.left + ANCHOR_GAP_PX}px`,
    } as CSSProperties;
  });

  useEscapeClaim(true);
  useFocusTrap(true, panelRef);

  const reducedMotion = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Pop-out: scale from exactly 1×1px up to the panel's real size, growing out of
  // its bottom-left corner. Scale (not width/height) so the content never reflows mid-animation.
  useLayoutEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    if (reducedMotion) {
      panel.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 150, easing: 'ease-out' });
      return;
    }
    const { offsetWidth: w, offsetHeight: h } = panel;
    panel.animate(
      [
        { transform: `scale(${1 / w}, ${1 / h})`, opacity: 0.4 },
        { transform: 'scale(1, 1)', opacity: 1 },
      ],
      { duration: POP_IN_MS, easing: 'cubic-bezier(0.34, 1.32, 0.64, 1)' },
    );
  }, [reducedMotion]);

  // Focus trap lands on the first focusable (the close ×); the message box is
  // where the user actually wants to start typing.
  // After sending, the submit button is gone — move focus to "Wróć do pracy".
  useEffect(() => {
    panelRef.current?.querySelector<HTMLElement>(sent ? '.ticket-sent button' : 'textarea')?.focus();
  }, [sent]);

  function close() {
    if (closingRef.current) return;
    closingRef.current = true;
    const panel = panelRef.current;
    if (!panel || reducedMotion) {
      onClose();
      return;
    }
    const { offsetWidth: w, offsetHeight: h } = panel;
    const anim = panel.animate(
      [
        { transform: 'scale(1, 1)', opacity: 1 },
        { transform: `scale(${1 / w}, ${1 / h})`, opacity: 0 },
      ],
      { duration: POP_OUT_MS, easing: 'cubic-bezier(0.4, 0, 1, 1)', fill: 'forwards' },
    );
    anim.onfinish = onClose;
  }

  function addPhotos(files: FileList | null) {
    if (!files) return;
    const images = Array.from(files).filter((f) => f.type.startsWith('image/'));
    setPhotos((current) => [...current, ...images].slice(0, MAX_PHOTOS));
    setError(undefined);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!area) {
      setAreaError('Wybierz, czego dotyczy zgłoszenie');
      panelRef.current?.querySelector('select')?.focus();
      return;
    }
    if (text.trim().length < MIN_TEXT && photos.length === 0) {
      setError('Napisz chociaż jedno zdanie albo dodaj zdjęcie ekranu 🙂');
      panelRef.current?.querySelector('textarea')?.focus();
      return;
    }
    // TODO(plan 261013 §8): POST /api/support/tickets with kind, area, text,
    // photos + the auto-captured context (§6). Frontend-only until then.
    setSent(true);
  }

  const copy = KIND_COPY[kind];

  return (
    <div
      className="ticket-overlay"
      onClick={(event) => {
        if (event.target === event.currentTarget) close();
      }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation();
          close();
        }
      }}
    >
      <div
        ref={panelRef}
        className="ticket-pop"
        style={anchor}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ticket-title"
      >
        <div className="ticket-head">
          <h2 id="ticket-title" className="ticket-title">
            {sent ? 'Dostaliśmy! 🙌' : copy.title}
          </h2>
          <button type="button" className="modal-close" onClick={close} aria-label="Zamknij">
            <Icon name="close" size="1.125rem" />
          </button>
        </div>

        {sent ? (
          <div className="ticket-sent">
            <p className="ticket-lead">
              Odpiszemy tutaj: zobaczysz kropkę przy <strong>Klikam w to co trzeba</strong>. Zwykle odpowiadamy w ciągu
              jednego dnia roboczego.
            </p>
            <p className="ticket-preview-note">
              <Icon name="info_outline" size="1rem" />
              Wersja podglądowa: wiadomość nie trafiła jeszcze do administratora. Wysyłka ruszy razem z backendem.
            </p>
            <div className="ticket-actions">
              <Button variant="primary" onClick={close}>
                Wróć do pracy
              </Button>
            </div>
          </div>
        ) : (
          <form className="ticket-form" onSubmit={handleSubmit} noValidate>
            <p className="ticket-lead">
              {copy.lead} Nie wiesz, jak coś zrobić? Zajrzyj do{' '}
              <Link to="/instrukcja-recepcja" onClick={close}>
                W co mam kliknąć
              </Link>
              .
            </p>

            <div className="ticket-tabs" role="radiogroup" aria-label="Rodzaj wiadomości">
              {(['problem', 'idea'] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  role="radio"
                  aria-checked={kind === k}
                  className={`ticket-tab${kind === k ? ' ticket-tab--active' : ''}`}
                  onClick={() => {
                    if (k === kind) return;
                    // Each kind has its own area list: re-pick from the current page.
                    setKind(k);
                    setArea(areaForPath(k, pathname));
                    setAreaError(undefined);
                  }}
                >
                  {KIND_COPY[k].title}
                </button>
              ))}
            </div>

            <div className="ticket-area">
              <SelectField
                label="Czego dotyczy"
                value={area}
                onChange={(event) => {
                  setArea(event.target.value);
                  setAreaError(undefined);
                }}
                options={AREAS_BY_KIND[kind].map(({ value, label }) => ({ value, label }))}
                placeholder={kind === 'problem' ? 'Wybierz…' : undefined}
                error={areaError}
              />
            </div>

            <div className="ticket-text">
              <TextareaField
                label="Treść wiadomości"
                placeholder={copy.placeholder}
                value={text}
                onChange={(event) => {
                  setText(event.target.value);
                  if (error) setError(undefined);
                }}
                error={error}
                helper="Nie wpisuj tu numerów telefonów ani danych klientów."
              />
            </div>

            {photos.length > 0 && (
              <ul className="ticket-photos" aria-label="Dołączone zdjęcia">
                {photos.map((photo, index) => (
                  <li key={`${photo.name}-${index}`} className="ticket-photo-chip">
                    <span className="ticket-photo-name">{photo.name}</span>
                    <button
                      type="button"
                      className="ticket-photo-remove"
                      aria-label={`Usuń ${photo.name}`}
                      onClick={() => setPhotos((current) => current.filter((_, i) => i !== index))}
                    >
                      <Icon name="close" size="0.875rem" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div className="ticket-actions">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                multiple
                hidden
                onChange={(event) => {
                  addPhotos(event.target.files);
                  event.target.value = '';
                }}
              />
              <button
                type="button"
                className="ticket-attach"
                aria-label="Dołącz zdjęcie ekranu"
                title={photos.length >= MAX_PHOTOS ? `Maksymalnie ${MAX_PHOTOS} zdjęcia` : 'Dołącz zdjęcie ekranu'}
                disabled={photos.length >= MAX_PHOTOS}
                onClick={() => fileRef.current?.click()}
              >
                <Icon name="attach_file" size="1.375rem" />
              </button>
              <Button type="submit" variant="primary" icon="forward_to_inbox">
                Wyślij zgłoszenie
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
