import { Fragment, memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, MouseEvent, TouchEvent } from 'react';
import { createPortal } from 'react-dom';
import { Link, useNavigate } from 'react-router-dom';
import { Button, ButtonLink } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { useConfirm } from '../../components/feedback/ConfirmProvider';
import { isVipClient } from '../../components/clients/TrendSparkline';
import { Icon } from '../../lib/icons/Icon';
import { formatDate, formatNextVisitLine1, formatPhone, telHref } from '../../lib/format';
import { useHideOnScroll } from '../../lib/useHideOnScroll';
import { DEFAULT_SORT_DIR, alphabetLetters, clientInitials, clientLetter, clientRingStyle, newVisitHref } from './clientsListShared';
import type { SortField, SortState } from './clientsListShared';
import { ClientsAlphabetIndex } from './ClientsAlphabetIndex';
import { createGlide } from './glideScroll';
import type { Client } from '../../types/client';

const SORT_OPTIONS: Array<{ field: SortField; label: string; hints: Record<SortState['dir'], string> }> = [
  { field: 'last_visit_date', label: 'Ostatnia wizyta', hints: { desc: 'Najnowsza najpierw', asc: 'Najstarsza najpierw' } },
  { field: 'next_visit_date', label: 'Następna wizyta', hints: { asc: 'Najbliższa najpierw', desc: 'Najdalsza najpierw' } },
  { field: 'full_name', label: 'Imię i nazwisko', hints: { asc: 'A → Z', desc: 'Z → A' } },
  { field: 'completed_visits', label: 'Liczba wizyt', hints: { desc: 'Najwięcej najpierw', asc: 'Najmniej najpierw' } },
  { field: 'no_show_count', label: 'No-show', hints: { desc: 'Najwięcej najpierw', asc: 'Najmniej najpierw' } },
];

// Desktop can also sort by Status (a table header); the phone sheet doesn't offer it
// (the filter chips cover it) but a restored session may still carry it.
const SORT_LABEL: Record<SortField, string> = {
  full_name: 'Imię i nazwisko',
  last_visit_date: 'Ostatnia wizyta',
  next_visit_date: 'Następna wizyta',
  completed_visits: 'Liczba wizyt',
  no_show_count: 'No-show',
  is_active: 'Status',
};

/** Same mechanics (and thresholds) as the employees list's card swipe, itself ported from the visits
 * list — hand-rolled, no gesture library in this project's deps. A horizontal drag must dominate the
 * vertical one by 1.5x before it counts as a swipe at all, so an ordinary list scroll that starts on
 * a card is never hijacked. Swipe LEFT → the client's page; swipe RIGHT → a new visit for them. */
const SWIPE_TRIGGER_PX = 84;
const SWIPE_MAX_PX = 120;

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** The card at the top of the list's visible area (just under the sticky toolbar), found by hit-testing
 * a point there — one cheap call however long the list is. The later probes clear the gap between cards
 * and, in a name-sorted list, the sticky letter header that sits on top of the first visible card. */
function cardAtTop(toolbar: HTMLElement): HTMLElement | null {
  const x = Math.round(window.innerWidth / 2);
  const bottom = toolbar.getBoundingClientRect().bottom;
  for (const dy of [14, 34, 54]) {
    const card = document.elementFromPoint(x, bottom + dy)?.closest<HTMLElement>('[data-letter]');
    if (card) return card;
  }
  return null;
}

/** How many cards play the arrival motion, and the classes that carry it (see ClientsListPage.css). */
const ARRIVE_MAX = 6;
const ARRIVE_CLASSES = ['is-arriving-down', 'is-arriving-up'];

/**
 * The motion that says "you have arrived here": when a glide settles, the cards now on screen (the first
 * few, staggered) ease in — rising from below if you travelled DOWN the list, dropping in from above if
 * you travelled UP — so the movement itself tells you which way you came. Skipped for a nudge, and for
 * anyone who asked for reduced motion.
 */
function playArrive(list: HTMLElement, toolbar: HTMLElement, travelled: number) {
  if (Math.abs(travelled) < 24 || prefersReducedMotion()) return;
  list.querySelectorAll('.is-arriving-down, .is-arriving-up').forEach((el) => el.classList.remove(...ARRIVE_CLASSES));
  void list.offsetWidth; // flush, so a repeat arrival restarts the animation instead of being swallowed
  const cls = travelled > 0 ? 'is-arriving-down' : 'is-arriving-up';
  let card = cardAtTop(toolbar) ?? list.querySelector<HTMLElement>('[data-letter]');
  for (let i = 0; i < ARRIVE_MAX && card; ) {
    if (card.getBoundingClientRect().top >= window.innerHeight) break;
    // Letter headers (`.mw-group`) are sticky — they don't travel, so they don't arrive either.
    if (card.dataset.letter) {
      card.style.setProperty('--arrive-i', String(i));
      card.classList.add(cls);
      i++;
    }
    card = card.nextElementSibling as HTMLElement | null;
  }
}

export interface ClientsMobileViewProps {
  /** Already filtered + sorted. */
  clients: Client[];
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
  searchInput: string;
  onSearchChange: (value: string) => void;
  onSearchSubmit: () => void;
  /** True = the inactive clients are listed (instead of the active ones, VIP and not). */
  showInactive: boolean;
  onShowInactiveChange: (show: boolean) => void;
  sort: SortState;
  onSelectSort: (field: SortField) => void;
  canWrite: boolean;
  /** May create visits (`appointments` write) — gates swipe-right ("Umów wizytę"). */
  canSchedule: boolean;
  /** The logged-in user's own employee, if their account is linked to one — prefilled in the new visit. */
  linkedEmployeeId: number | null;
  showNotes: boolean;
  onBulkUpdatePreferences: () => void;
  isUpdatingPrefs: boolean;
}

/**
 * Klienci — phone rendering (≤640px). Same shape as Użytkownicy: a sticky search bar
 * (with a "Nieaktywni" toggle — VIP clients just sit in the list, tagged), a card list (tap opens the client, swipe left opens it, swipe right books
 * a visit), and the page's primary action pinned to the thumb zone. A right-edge A–Z
 * index jumps through long lists. What the table's sortable headers did lives in a sort
 * sheet — the headers are hidden on a phone, so without it there would be no sorting.
 * Editing and deactivating a client live on the client's own page.
 */
export function ClientsMobileView({
  clients,
  loading,
  error,
  onRetry,
  searchInput,
  onSearchChange,
  onSearchSubmit,
  showInactive,
  onShowInactiveChange,
  sort,
  onSelectSort,
  canWrite,
  canSchedule,
  linkedEmployeeId,
  showNotes,
  onBulkUpdatePreferences,
  isUpdatingPrefs,
}: ClientsMobileViewProps) {
  const confirm = useConfirm();
  const [sortOpen, setSortOpen] = useState(false);
  const [headerSlot, setHeaderSlot] = useState<HTMLElement | null>(null);
  const [searchFocused, setSearchFocused] = useState(false);
  // The bottom bar slides away on scroll-down. While a finger is held on the A–Z index — and while the
  // glide it started is still settling — the PAGE is being scrolled by the index, not by the user, so the
  // hook is paused (it would flip the bar every ~120ms). The bar stays hidden for the whole hold, comes
  // back the moment the finger lifts, and the hook resumes once the glide has settled.
  // `scrollHidden` is the hook's own state, `ctaHidden` what the bar actually does.
  const [indexHeld, setIndexHeld] = useState(false);
  const [gliding, setGliding] = useState(false);
  const scrollHidden = useHideOnScroll(120, 80, indexHeld || gliding);
  const ctaHidden = indexHeld || (!gliding && scrollHidden);
  // The letter of the card at the top of the visible list: the index highlights it, so it always shows
  // which start letter the cards on screen belong to.
  const [readingLetter, setReadingLetter] = useState<string | null>(null);
  const glideRef = useRef<ReturnType<typeof createGlide> | null>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);
  const ctaRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  // `top` / `bottom` = the viewport px the index keeps clear (sticky toolbar above; below, only the
  // screen edge); `cta` = the height of the bottom action bar, reserved only while that bar shows.
  const [alphaBounds, setAlphaBounds] = useState<{ top: number; bottom: number; cta: number } | null>(null);
  const letters = useMemo(() => alphabetLetters(clients), [clients]);
  // A jump-to-letter index only makes sense in an alphabetical list, so it slides in for "name A→Z"
  // and out for every other order. It also steps aside while the search box has focus (the keyboard
  // is up and the index is viewport-fixed). The cards use the same flag to give up / reclaim its width.
  const nameAsc = sort.field === 'full_name' && sort.dir === 'asc';
  const alphaVisible = nameAsc && !searchFocused;
  // Sticky letter headers (P4) sit right under the sticky toolbar, so they need its live height.
  const [toolbarH, setToolbarH] = useState(0);
  useLayoutEffect(() => {
    const toolbar = toolbarRef.current;
    if (!toolbar) return;
    const observer = new ResizeObserver(() => setToolbarH(toolbar.offsetHeight));
    observer.observe(toolbar);
    setToolbarH(toolbar.offsetHeight);
    return () => observer.disconnect();
  }, []);

  // The shell's top bar has a slot for page-level actions (the visits page parks
  // "Rozlicz przeszłe wizyty" there) — the bulk preferences refresh lives in it, since
  // the page header itself is dropped on a phone to win back viewport height.
  useEffect(() => {
    setHeaderSlot(document.getElementById('mobile-header-actions'));
  }, []);

  async function handleBulkClick() {
    const ok = await confirm({
      title: 'Aktualizacja preferencji',
      message: 'Przeliczyć preferencje wszystkich klientów na podstawie historii ich wizyt?',
      confirmText: 'Aktualizuj',
    });
    if (ok) onBulkUpdatePreferences();
  }

  function handleSortPick(field: SortField) {
    onSelectSort(field);
    setSortOpen(false);
  }

  // The index is viewport-fixed, so it must know where the scroll region really starts and ends:
  // below the sticky toolbar, above the bottom action bar. Measured (not guessed in CSS) because
  // the shell's header and footer heights aren't ours; re-measured when the box or list resizes.
  // It is only offered when the page actually scrolls — on a short list there is nothing to jump to.
  useLayoutEffect(() => {
    const scroller = document.getElementById('main-content');
    const toolbar = toolbarRef.current;
    if (!scroller || !toolbar || letters.length < 2) {
      setAlphaBounds(null);
      return;
    }
    function measure() {
      if (!scroller || !toolbar) return;
      const box = scroller.getBoundingClientRect();
      const scrolls = scroller.scrollHeight > scroller.clientHeight + 1;
      setAlphaBounds(scrolls ? { top: box.top + toolbar.offsetHeight + 4, bottom: window.innerHeight - box.bottom + 4, cta: ctaRef.current?.offsetHeight ?? 0 } : null);
    }
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(scroller);
    if (listRef.current) observer.observe(listRef.current);
    window.addEventListener('resize', measure);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [letters.length, loading]);

  // The scroll glide (glideScroll.ts) the index drives instead of jumping: it chases whichever letter the
  // finger is on, so dragging along the index is one continuous, decelerating motion rather than a
  // series of teleports. When it settles, the cards now on screen play their arrival (playArrive).
  useEffect(() => {
    const scroller = document.getElementById('main-content');
    if (!scroller) return;
    const glide = createGlide(
      {
        getTop: () => scroller.scrollTop,
        setTop: (y) => {
          scroller.scrollTop = y;
        },
        maxTop: () => scroller.scrollHeight - scroller.clientHeight,
        viewport: () => scroller.clientHeight,
      },
      {
        reduced: prefersReducedMotion,
        onStart: () => setGliding(true),
        onEnd: ({ from, to, interrupted }) => {
          setGliding(false);
          if (!interrupted && listRef.current && toolbarRef.current) playArrive(listRef.current, toolbarRef.current, to - from);
        },
      },
    );
    glideRef.current = glide;
    // Grabbing the list (touch or wheel) takes over from the glide — except a touch on the index itself,
    // which sits inside the scroll container in the DOM and would otherwise cancel the glide it just started.
    const takeOver = (e: Event) => {
      if (!(e.target instanceof Element && e.target.closest('.clients-alpha'))) glide.stop();
    };
    scroller.addEventListener('touchstart', takeOver, { passive: true });
    scroller.addEventListener('wheel', takeOver, { passive: true });
    return () => {
      scroller.removeEventListener('touchstart', takeOver);
      scroller.removeEventListener('wheel', takeOver);
      glide.stop();
      glideRef.current = null;
    };
  }, []);

  // Scroll-spy for the index: which start letter do the cards on screen belong to? Re-read on every
  // scroll frame (hit-test, one call) and whenever the list changes; only a CHANGE re-renders.
  const alphaOn = alphaBounds !== null;
  useEffect(() => {
    const scroller = document.getElementById('main-content');
    if (!scroller || !alphaOn || !alphaVisible || loading) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const list = listRef.current;
      const toolbar = toolbarRef.current;
      if (!list || !toolbar) return;
      const letter = (cardAtTop(toolbar) ?? list.querySelector<HTMLElement>('[data-letter]'))?.dataset.letter ?? null;
      setReadingLetter((prev) => (prev === letter ? prev : letter));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    scroller.addEventListener('scroll', onScroll, { passive: true });
    update();
    return () => {
      scroller.removeEventListener('scroll', onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [alphaOn, alphaVisible, loading, clients]);

  // Glides the first card filed under `letter` (in the list's current order) to just below the sticky
  // toolbar — or, in a name-sorted list, that letter's header, so the header doesn't land on the card.
  // The target is an absolute scroll offset, so it stays right while a glide is already moving.
  function jumpToLetter(letter: string) {
    const scroller = document.getElementById('main-content');
    const list = listRef.current;
    const target = list?.querySelector<HTMLElement>(`[data-group="${letter}"]`) ?? list?.querySelector<HTMLElement>(`[data-letter="${letter}"]`);
    if (!scroller || !target) return;
    const toolbarH = toolbarRef.current?.offsetHeight ?? 0;
    const top = target.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - toolbarH - 8;
    glideRef.current?.to(Math.max(0, top));
  }

  // The arrow above "A": all the way up, so the first card (and the count / sort row above it) shows.
  function jumpToTop() {
    glideRef.current?.to(0);
  }

  return (
    <div className="refined-page clients-page clients-page--mobile animate-fade-up">
      {/* The shell's top bar already names the page — keep the h1 for screen readers only. */}
      <h1 className="clients-sr-only">Klienci</h1>

      <div className="clients-toolbar" ref={toolbarRef}>
        <div className="clients-search">
          <Icon name="search" />
          <input
            type="search"
            className="form-input"
            placeholder="Szukaj: imię, telefon, email…"
            aria-label="Szukaj klientów"
            enterKeyHint="search"
            value={searchInput}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                onSearchSubmit();
                e.currentTarget.blur();
              }
            }}
          />
        </div>
        <button
          type="button"
          className={`clients-inactive-btn${showInactive ? ' active' : ''}`}
          aria-pressed={showInactive}
          title="Pokaż nieaktywnych klientów"
          onClick={() => onShowInactiveChange(!showInactive)}
        >
          Nieaktywni
        </button>
      </div>

      <div className="clients-listbar">
        <span className="clients-count" aria-live="polite">
          {loading ? ' ' : `${clients.length} ${clients.length === 1 ? 'klient' : 'klientów'}`}
        </span>
        <button type="button" className="clients-sort-btn" aria-haspopup="dialog" onClick={() => setSortOpen(true)}>
          Sortuj: <strong>{SORT_LABEL[sort.field]}</strong>
          <Icon name={sort.dir === 'asc' ? 'arrow_upward' : 'arrow_downward'} />
        </button>
      </div>

      {loading ? (
        <ul className="client-cards" aria-label="Ładowanie klientów">
          {Array.from({ length: 6 }).map((_, i) => (
            <li key={i} className="client-card client-card--skeleton mw-card">
              <div className="skeleton" style={{ width: '2.5rem', height: '2.5rem', borderRadius: '50%', flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div className="skeleton" style={{ height: '0.9375rem', width: '55%', marginBottom: '0.5rem' }} />
                <div className="skeleton" style={{ height: '0.75rem', width: '80%' }} />
              </div>
            </li>
          ))}
        </ul>
      ) : error ? (
        <div className="clients-state" role="alert">
          <p style={{ color: 'var(--color-error)' }}>Błąd ładowania klientów: {error.message}</p>
          <Button variant="secondary" icon="refresh" onClick={onRetry}>
            Spróbuj ponownie
          </Button>
        </div>
      ) : clients.length === 0 ? (
        <div className="clients-state">
          <Icon name="search_off" className="empty-icon" />
          <p>Nie znaleziono klientów</p>
        </div>
      ) : (
        <ul
          className={`client-cards${alphaBounds && alphaVisible ? ' has-alpha' : ''}`}
          ref={listRef}
          style={{ '--group-top': `${toolbarH}px` } as CSSProperties}
          // An arrival animation (playArrive) is done: drop its class, so the card goes back to plain CSS.
          onAnimationEnd={(e) => {
            const el = e.target as HTMLElement;
            if (el.classList.contains('client-card-wrap')) el.classList.remove(...ARRIVE_CLASSES);
          }}
        >
          {clients.map((client, i) => {
            const letter = clientLetter(client);
            const card = <ClientCard key={client.id} client={client} showNotes={showNotes} canSchedule={canSchedule} linkedEmployeeId={linkedEmployeeId} />;
            // P4 · a sticky letter header opens each letter's run, only while the list is sorted A→Z.
            if (!nameAsc || (i > 0 && clientLetter(clients[i - 1]) === letter)) return card;
            return (
              <Fragment key={client.id}>
                <li className="mw-group" data-group={letter} aria-hidden="true">
                  {letter}
                </li>
                {card}
              </Fragment>
            );
          })}
        </ul>
      )}

      {/* Mounted whenever it could be shown (not just when visible), so sliding out can animate. */}
      {alphaBounds && !loading && !error && (
        <ClientsAlphabetIndex
          letters={letters}
          onSelect={jumpToLetter}
          onTop={jumpToTop}
          visible={alphaVisible}
          onHold={setIndexHeld}
          activeLetter={readingLetter}
          top={alphaBounds.top}
          // It fills the viewport from the toolbar down: above the action bar while that shows, and all
          // the way to the bottom edge (clear of the home-indicator inset) once it has slid away. While a
          // finger is on it the bottom edge follows `scrollHidden` (the state from BEFORE the press), not
          // the bar: pressing hides the bar, and the index must not resize under the finger that is
          // choosing a letter on it. Once the finger lifts it follows the bar again.
          bottom={
            canWrite && (indexHeld ? !scrollHidden : !ctaHidden)
              ? `${alphaBounds.bottom + alphaBounds.cta}px`
              : `calc(${alphaBounds.bottom}px + env(safe-area-inset-bottom, 0px))`
          }
        />
      )}

      {canWrite && (
        <div className={`mw-bar${ctaHidden ? ' mw-bar--hidden' : ''}`} ref={ctaRef}>
          <ButtonLink to="/klienci/nowy" variant="primary" icon="add">
            Dodaj klienta
          </ButtonLink>
        </div>
      )}

      {canWrite &&
        headerSlot &&
        createPortal(
          <button
            type="button"
            className="clients-header-btn"
            aria-label="Aktualizuj preferencje klientów"
            title="Aktualizuj preferencje"
            aria-busy={isUpdatingPrefs}
            disabled={isUpdatingPrefs}
            onClick={handleBulkClick}
          >
            <Icon name={isUpdatingPrefs ? 'hourglass_top' : 'auto_awesome'} />
          </button>,
          headerSlot,
        )}

      <Modal isOpen={sortOpen} onClose={() => setSortOpen(false)} title="Sortuj klientów" variant="sheet">
        <ul className="mw-actionlist">
          {SORT_OPTIONS.map((opt) => {
            const active = sort.field === opt.field;
            return (
              <li key={opt.field}>
                <button type="button" className={`mw-actionitem${active ? ' is-on' : ''}`} aria-pressed={active} onClick={() => handleSortPick(opt.field)}>
                  <span className="mw-actionitem__text">
                    <span>{opt.label}</span>
                    <small>{opt.hints[active ? sort.dir : DEFAULT_SORT_DIR[opt.field]]}</small>
                  </span>
                  {active && <Icon name={sort.dir === 'asc' ? 'arrow_upward' : 'arrow_downward'} className="mw-actionitem__check" />}
                </button>
              </li>
            );
          })}
        </ul>
        <p className="mw-reason">Dotknij aktywnego pola ponownie, aby odwrócić kolejność.</p>
      </Modal>
    </div>
  );
}

interface ClientCardProps {
  client: Client;
  showNotes: boolean;
  canSchedule: boolean;
  linkedEmployeeId: number | null;
}

/** Per-card drag state. `dx` is signed: negative = dragging left, positive = dragging right. */
function useCardSwipe(allowRight: boolean, onLeft: () => void, onRight: () => void) {
  const [dx, setDx] = useState(0);
  const startRef = useRef<{ x: number; y: number } | null>(null);
  // A triggered swipe can be followed by a synthetic click on the card; swallow exactly that one.
  const suppressClickRef = useRef(false);

  function onTouchStart(e: TouchEvent) {
    const t = e.touches[0];
    startRef.current = { x: t.clientX, y: t.clientY };
    suppressClickRef.current = false;
  }
  function onTouchMove(e: TouchEvent) {
    const start = startRef.current;
    if (!start) return;
    const t = e.touches[0];
    const moveX = t.clientX - start.x;
    const moveY = t.clientY - start.y;
    if (Math.abs(moveX) <= Math.abs(moveY) * 1.5) return;
    if (moveX < 0) setDx(Math.max(moveX, -SWIPE_MAX_PX));
    else if (allowRight) setDx(Math.min(moveX, SWIPE_MAX_PX));
  }
  function onTouchEnd() {
    startRef.current = null;
    const final = dx;
    setDx(0);
    if (final <= -SWIPE_TRIGGER_PX) {
      suppressClickRef.current = true;
      onLeft();
    } else if (allowRight && final >= SWIPE_TRIGGER_PX) {
      suppressClickRef.current = true;
      onRight();
    }
  }
  function onTouchCancel() {
    startRef.current = null;
    setDx(0);
  }
  /** True when the click that just fired belongs to a swipe and must be ignored. */
  function consumeSuppressedClick(): boolean {
    const was = suppressClickRef.current;
    suppressClickRef.current = false;
    return was;
  }

  return { dx, handlers: { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel }, consumeSuppressedClick };
}

const stopPropagation = (e: MouseEvent) => e.stopPropagation();

// Memoised: the list re-renders whenever the bottom bar slides in or out on scroll, and with a few
// hundred clients that must not mean re-rendering every card (its props are all stable between those).
const ClientCard = memo(function ClientCard({ client, showNotes, canSchedule, linkedEmployeeId }: ClientCardProps) {
  const navigate = useNavigate();
  const noShows = client.no_show_count ?? 0;
  const hasMeta = noShows > 0 || !client.is_active;
  const viewHref = `/klienci/${client.id}`;
  const visitHref = newVisitHref(client, linkedEmployeeId);
  const swipe = useCardSwipe(
    canSchedule,
    () => navigate(viewHref),
    () => navigate(visitHref),
  );
  const note = showNotes ? client.recent_notes?.[0] : undefined;
  const armedLeft = swipe.dx <= -SWIPE_TRIGGER_PX;
  const armedRight = swipe.dx >= SWIPE_TRIGGER_PX;

  return (
    <li className="client-card-wrap mw-swipe" data-letter={clientLetter(client)}>
      {swipe.dx < 0 && (
        <div className={`mw-swipe__reveal mw-swipe__reveal--info${armedLeft ? ' is-armed' : ''}`} aria-hidden="true">
          <div className="mw-swipe__content mw-swipe__content--right-edge mw-swipe__content--info" style={{ transform: `translateX(${swipe.dx}px)` }}>
            <Icon name="visibility" />
            <span className="mw-swipe__label">Zobacz</span>
          </div>
        </div>
      )}
      {canSchedule && swipe.dx > 0 && (
        <div className={`mw-swipe__reveal mw-swipe__reveal--success${armedRight ? ' is-armed' : ''}`} aria-hidden="true">
          <div className="mw-swipe__content mw-swipe__content--left-edge mw-swipe__content--success" style={{ transform: `translateX(${swipe.dx}px)` }}>
            <span className="mw-swipe__label">Nowa wizyta</span>
            <Icon name="edit_calendar" />
          </div>
        </div>
      )}
      <div
        className={`client-card mw-card${client.phone ? '' : ' client-card--no-phone'}${armedLeft ? ' is-armed-left' : ''}${armedRight ? ' is-armed-right' : ''}`}
        style={swipe.dx !== 0 ? { transform: `translateX(${swipe.dx}px)`, transition: 'none' } : undefined}
        onClick={() => {
          if (swipe.consumeSuppressedClick()) return;
          navigate(viewHref);
        }}
        {...swipe.handlers}
      >
        {/* Top row: avatar · name · call. The rows below span the full card width. */}
        <span className="client-avatar" style={clientRingStyle(client)}>
          {clientInitials(client)}
        </span>
        {/* The card is a div (it has to host a tel: link, and anchors can't nest); the name is the
            focusable link that keeps keyboard and screen-reader access to the client's page. */}
        <Link to={viewHref} className="client-card-name" onClick={stopPropagation}>
          {client.full_name}
          {isVipClient(client) && <span className="vip-tag">★ VIP</span>}
        </Link>
        {client.phone && (
          <span className="client-card-phone-row">
            <a className="client-phone-btn" href={telHref(client.phone)} aria-label={`Zadzwoń: ${formatPhone(client.phone)}`} onClick={stopPropagation}>
              <Icon name="call" />
            </a>
            <span className="client-card-phone">{formatPhone(client.phone)}</span>
          </span>
        )}

        <div className="client-card-facts">
          <span className="client-pill client-visits">
            Wizyt <strong>{client.completed_visits ?? 0}</strong>
          </span>
          <span className="client-fact">
            <span className="client-fact-label">Ostatnia</span>
            {formatDate(client.last_visit_date)}
          </span>
          <span className="client-fact">
            <span className="client-fact-label">Następna</span>
            {client.next_visit_date ? formatNextVisitLine1(client.next_visit_date, client.next_visit_time) : '—'}
          </span>
        </div>

        {hasMeta && (
          <div className="client-card-meta">
            {noShows > 0 && (
              <span className={`client-pill${noShows > 2 ? ' client-pill--danger' : ''}`}>
                No-show <strong>{noShows}</strong>
              </span>
            )}
            {!client.is_active && <span className="client-pill client-pill--muted">Nieaktywny</span>}
          </div>
        )}

        {note && (
          <p className="client-card-note">
            <span className="client-note-text">{note.text}</span>
            {note.service_name && <span className="client-note-service">({note.service_name})</span>}
          </p>
        )}
      </div>
    </li>
  );
});
