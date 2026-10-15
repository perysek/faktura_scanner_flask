import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, FormEvent, MouseEvent as ReactMouseEvent, PointerEvent as ReactPointerEvent } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useEscapeClaim } from '../../lib/a11y/escapeScope';
import { useFocusTrap } from '../../lib/a11y/useFocusTrap';
import { Icon } from '../../lib/icons/Icon';
import { Button } from '../ui/Button';
import { TextareaField } from '../ui/form';

/**
 * "Napisz do administratora" — the ticket form opened by the sidebar row
 * 'Klikam w to co trzeba / ale coś mi nie pasuje'. Pops out of the bottom-left
 * corner of <main> (1×1px → 30vw × 60vh). FRONTEND ONLY for now: sending shows
 * the confirmation but nothing reaches the server yet — the API, inbox and
 * conversation view are designed in plans/261013-support-tickets/plan.md.
 *
 * 'Zaznacz miejsce' tucks the panel back into its corner and turns the pointer
 * into a light: hold + drag draws a rectangle, release grabs that part of the
 * page (html2canvas-pro, loaded on demand) and attaches it to the ticket.
 */

const TITLE = 'Zgłoś problem lub podziel się pomysłem';

type TicketKind = 'problem' | 'idea';

/** `tab` labels the kind switch; the panel itself has the one shared TITLE. */
const KIND_COPY: Record<TicketKind, { tab: string; lead: string; placeholder: string }> = {
  problem: {
    tab: 'Zgłoś problem',
    lead: 'Coś nie działa? Błędy, dziwne zachowanie albo kłopot z ustawieniami: napisz tutaj.',
    placeholder:
      'Opisz, co klikasz i co się dzieje, np. „Dodaję wizytę na 15:00, klikam Zapisz i nic się nie dzieje”. Przyciskiem „Zaznacz miejsce” pokażesz, gdzie to jest.',
  },
  idea: {
    tab: 'Podziel się pomysłem',
    lead: 'Masz pomysł, co by Ci ułatwiło pracę? Każdy pomysł czytamy.',
    placeholder:
      'Napisz, co by Ci ułatwiło pracę i jak to sobie wyobrażasz (tylko bez fantazji typu „fajnie by było gdyby dało się sterować aplikacją za pomocą umysłu” czy „Zróbcie, żeby aplikacja widziała jaki pracownik łapie za myszkę”).',
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

const MAX_SHOTS = 3;
const MIN_TEXT = 10;
/** A press-and-release smaller than this (either side) is a stray click, not a selection. */
const MIN_SHOT_PX = 12;
const POP_IN_MS = 420;
const POP_OUT_MS = 220;
/** Gap between the panel and <main>'s bottom-left corner. */
const ANCHOR_GAP_PX = 16;

/** A marked piece of the page, attached to the ticket as a PNG. */
interface Shot {
  file: File;
  url: string;
}

interface Point {
  x: number;
  y: number;
}

interface PickedRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

type ShotHint = { text: string; tone: 'busy' | 'ok' | 'error' };

function rectBetween(a: Point, b: Point): PickedRect {
  return {
    left: Math.min(a.x, b.x),
    top: Math.min(a.y, b.y),
    width: Math.abs(a.x - b.x),
    height: Math.abs(a.y - b.y),
  };
}

/** Grabs `rect` (viewport px) of the page as a PNG. The ticket layer carries
 * data-html2canvas-ignore, so neither the panel nor its backdrop end up in the shot. */
async function capturePageRect(rect: PickedRect): Promise<Blob> {
  const { default: html2canvas } = await import('html2canvas-pro');
  const canvas = await html2canvas(document.body, {
    x: rect.left + window.scrollX,
    y: rect.top + window.scrollY,
    width: rect.width,
    height: rect.height,
    windowWidth: window.innerWidth,
    windowHeight: window.innerHeight,
    scale: Math.min(window.devicePixelRatio || 1, 2),
    backgroundColor: getComputedStyle(document.body).backgroundColor,
    useCORS: true,
    logging: false,
  });
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
  if (!blob) throw new Error('canvas.toBlob returned null');
  return blob;
}

interface SpotPickerProps {
  start: Point;
  onPick: (rect: PickedRect) => void;
  onCancel: () => void;
}

/**
 * Full-screen picking layer. Hovering: a soft warm light follows the pointer.
 * Holding the button: the light narrows into an ocean-blue spotlight and a
 * rectangle stretches from the press point to the pointer. Light position and
 * rectangle are written straight to the DOM — no React render per pointermove.
 */
function SpotPicker({ start, onPick, onCancel }: SpotPickerProps) {
  const layerRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const anchorRef = useRef<Point | null>(null);
  const [dragging, setDragging] = useState(false);

  const moveLight = useCallback((p: Point) => {
    layerRef.current?.style.setProperty('--spot-x', `${p.x}px`);
    layerRef.current?.style.setProperty('--spot-y', `${p.y}px`);
  }, []);

  useLayoutEffect(() => moveLight(start), [moveLight, start]);

  // Escape backs out of picking only — capture phase, so the panel's own Escape (= close) never sees it.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      onCancel();
    }
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onCancel]);

  function drawBox(p: Point) {
    const anchor = anchorRef.current;
    const box = boxRef.current;
    if (!anchor || !box) return;
    const r = rectBetween(anchor, p);
    box.style.transform = `translate(${r.left}px, ${r.top}px)`;
    box.style.width = `${r.width}px`;
    box.style.height = `${r.height}px`;
  }

  const pointOf = (event: ReactPointerEvent) => ({ x: event.clientX, y: event.clientY });

  return (
    <div
      ref={layerRef}
      className={`spot-layer${dragging ? ' spot-layer--drag' : ''}`}
      data-html2canvas-ignore="true"
      onPointerMove={(event) => {
        const p = pointOf(event);
        moveLight(p);
        drawBox(p);
      }}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        const p = pointOf(event);
        anchorRef.current = p;
        moveLight(p);
        drawBox(p);
        setDragging(true);
      }}
      onPointerUp={(event) => {
        const anchor = anchorRef.current;
        if (!anchor) return;
        anchorRef.current = null;
        setDragging(false);
        const rect = rectBetween(anchor, pointOf(event));
        // Stray click: stay in picking mode and let them try again.
        if (rect.width < MIN_SHOT_PX || rect.height < MIN_SHOT_PX) return;
        onPick(rect);
      }}
      onPointerCancel={() => {
        anchorRef.current = null;
        setDragging(false);
      }}
      // Keep focus (and the focus trap) on the panel; no text selection while dragging.
      onMouseDown={(event) => event.preventDefault()}
      onContextMenu={(event) => event.preventDefault()}
    >
      <div ref={boxRef} className="spot-box" />
      <p className="spot-hint">Przytrzymaj i przeciągnij, żeby zaznaczyć miejsce · Esc anuluje</p>
    </div>
  );
}

export interface SupportTicketModalProps {
  onClose: () => void;
}

export function SupportTicketModal({ onClose }: SupportTicketModalProps) {
  const { pathname } = useLocation();
  const panelRef = useRef<HTMLDivElement>(null);
  const closingRef = useRef(false);
  const tuckRef = useRef<Animation | null>(null);

  const [kind, setKind] = useState<TicketKind>('problem');
  const [area, setArea] = useState(() => areaForPath('problem', pathname));
  const [areaError, setAreaError] = useState<string | undefined>();
  const [text, setText] = useState('');
  const [shots, setShots] = useState<Shot[]>([]);
  const [shotHint, setShotHint] = useState<ShotHint | undefined>();
  /** Where the light starts while picking (the clicked button); null = not picking. */
  const [pickFrom, setPickFrom] = useState<Point | null>(null);
  const [error, setError] = useState<string | undefined>();
  const [sent, setSent] = useState(false);

  // Thumbnail object URLs live until the panel unmounts.
  const shotsRef = useRef(shots);
  shotsRef.current = shots;
  useEffect(() => () => shotsRef.current.forEach((shot) => URL.revokeObjectURL(shot.url)), []);

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
  const popIn = useCallback(() => {
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

  /** popIn in reverse, held at 1×1px: the panel slips back out through its corner. */
  const shrinkOut = useCallback((): Animation | null => {
    const panel = panelRef.current;
    if (!panel) return null;
    if (reducedMotion) {
      return panel.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 120, fill: 'forwards' });
    }
    const { offsetWidth: w, offsetHeight: h } = panel;
    return panel.animate(
      [
        { transform: 'scale(1, 1)', opacity: 1 },
        { transform: `scale(${1 / w}, ${1 / h})`, opacity: 0 },
      ],
      { duration: POP_OUT_MS, easing: 'cubic-bezier(0.4, 0, 1, 1)', fill: 'forwards' },
    );
  }, [reducedMotion]);

  useLayoutEffect(popIn, [popIn]);

  // Focus trap lands on the first focusable (the close ×); the message box is
  // where the user actually wants to start typing.
  // After sending, the submit button is gone — move focus to "Wróć do pracy".
  useEffect(() => {
    panelRef.current?.querySelector<HTMLElement>(sent ? '.ticket-sent button' : 'textarea')?.focus();
  }, [sent]);

  function close() {
    if (closingRef.current) return;
    closingRef.current = true;
    if (reducedMotion) {
      onClose();
      return;
    }
    const anim = shrinkOut();
    if (anim) anim.onfinish = onClose;
    else onClose();
  }

  function startPicking(event: ReactMouseEvent<HTMLButtonElement>) {
    if (shots.length >= MAX_SHOTS) return;
    // Keyboard activation reports 0,0: start the light mid-screen instead.
    const fromPointer = event.clientX !== 0 || event.clientY !== 0;
    setPickFrom(fromPointer ? { x: event.clientX, y: event.clientY } : { x: window.innerWidth / 2, y: window.innerHeight / 2 });
    setShotHint(undefined);
    tuckRef.current = shrinkOut();
  }

  const stopPicking = useCallback(() => {
    setPickFrom(null);
    tuckRef.current?.cancel();
    tuckRef.current = null;
    popIn();
  }, [popIn]);

  const handlePick = useCallback(
    async (rect: PickedRect) => {
      // The panel comes straight back; the capture ignores it, so it can run underneath.
      stopPicking();
      setShotHint({ text: 'Zapisuję zaznaczenie…', tone: 'busy' });
      try {
        const blob = await capturePageRect(rect);
        const file = new File([blob], `zaznaczenie-${Date.now()}.png`, { type: 'image/png' });
        setShots((current) => [...current, { file, url: URL.createObjectURL(blob) }]);
        setShotHint({ text: 'Zaznaczone miejsce dodane do zgłoszenia', tone: 'ok' });
        setError(undefined);
      } catch {
        setShotHint({ text: 'Nie udało się zapisać zaznaczenia. Spróbuj jeszcze raz.', tone: 'error' });
      }
    },
    [stopPicking],
  );

  function removeShot(index: number) {
    URL.revokeObjectURL(shots[index].url);
    setShots((current) => current.filter((_, i) => i !== index));
    setShotHint(undefined);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!area) {
      setAreaError('Wybierz, czego dotyczy zgłoszenie');
      panelRef.current?.querySelector('select')?.focus();
      return;
    }
    if (text.trim().length < MIN_TEXT && shots.length === 0) {
      setError('Napisz chociaż jedno zdanie albo zaznacz miejsce na ekranie 🙂');
      panelRef.current?.querySelector('textarea')?.focus();
      return;
    }
    // TODO(plan 261013 §8): POST /api/support/tickets with kind, area, text,
    // shots + the auto-captured context (§6). Frontend-only until then.
    setSent(true);
  }

  const copy = KIND_COPY[kind];
  const shotsFull = shots.length >= MAX_SHOTS;

  return (
    <div
      className={`ticket-overlay${pickFrom ? ' ticket-overlay--picking' : ''}`}
      data-html2canvas-ignore="true"
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
            {sent ? 'Dostaliśmy! 🙌' : TITLE}
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
                  {KIND_COPY[k].tab}
                </button>
              ))}
            </div>

            {/* Select first (exactly as wide as the 'Zgłoś problem' tab above it), then its
                label pointing back at it, then 'Zaznacz miejsce'. */}
            <div className="ticket-area">
              <select
                id="ticket-area"
                className={`form-select${areaError ? ' error' : ''}`}
                value={area}
                aria-invalid={areaError ? true : undefined}
                aria-describedby={areaError ? 'ticket-area-error' : undefined}
                onChange={(event) => {
                  setArea(event.target.value);
                  setAreaError(undefined);
                }}
              >
                {kind === 'problem' && <option value="">Wybierz…</option>}
                {AREAS_BY_KIND[kind].map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <div className="ticket-area-side">
                <label htmlFor="ticket-area" className="ticket-area-label">
                  <span aria-hidden="true">← </span>Czego dotyczy
                </label>
                <Button
                  small
                  icon="center_focus_weak"
                  className="ticket-mark"
                  disabled={shotsFull}
                  title={shotsFull ? `Maksymalnie ${MAX_SHOTS} zaznaczenia` : 'Pokaż na ekranie, o które miejsce chodzi'}
                  onClick={startPicking}
                >
                  Zaznacz miejsce
                </Button>
              </div>
              {areaError && (
                <span id="ticket-area-error" className="form-error-text" role="alert">
                  {areaError}
                </span>
              )}
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

            {shots.length > 0 && (
              <ul className="ticket-photos" aria-label="Zaznaczone miejsca">
                {shots.map((shot, index) => (
                  <li key={shot.url} className="ticket-photo-chip">
                    <img className="ticket-shot-thumb" src={shot.url} alt="" />
                    <span className="ticket-photo-name">Zaznaczenie {index + 1}</span>
                    <button
                      type="button"
                      className="ticket-photo-remove"
                      aria-label={`Usuń zaznaczenie ${index + 1}`}
                      onClick={() => removeShot(index)}
                    >
                      <Icon name="close" size="0.875rem" />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            <div className="ticket-actions">
              {shotHint && (
                <p className={`ticket-shot-hint ticket-shot-hint--${shotHint.tone}`} role="status">
                  {shotHint.tone === 'ok' && <Icon name="check_circle" size="1rem" />}
                  {shotHint.text}
                </p>
              )}
              <Button type="submit" variant="primary" icon="forward_to_inbox">
                Wyślij zgłoszenie
              </Button>
            </div>
          </form>
        )}
      </div>
      {pickFrom && <SpotPicker start={pickFrom} onPick={handlePick} onCancel={stopPicking} />}
    </div>
  );
}
