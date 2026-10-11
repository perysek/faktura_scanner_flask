import { useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import { Icon } from '../../lib/icons/Icon';
import { initials } from './pastVisitsShared';
import type { AppointmentListItem } from '../../types/appointment';

/** The day/week lanes span 07:00–22:00 and one calendar tick is 30 minutes. */
const LANE_MINUTES = 15 * 60;
const TICK_MINUTES = 30;
/** Two text lines at the bar font size (+ 1px padding top/bottom) need ≈ 36px. Anything shorter
 * than this (even a longer-than-30-min visit squeezed by a short viewport) falls back to the
 * one-line form with the hold-to-roll-out handle, rather than clipping line #2 for good. */
const TWO_LINE_MIN_PX = 37;

function toMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return h * 60 + m;
}

/** "Anna Maria Kowalska" → "Anna. Maria Kowalska" (first word = first name, the rest = last name);
 * a one-word name stays as is, no client gives "Bez klienta". The list payload only carries the
 * concatenated `client_name`, so the split is positional. */
function clientLabel(name: string | null): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return 'Bez klienta';
  if (words.length === 1) return words[0];
  return `${words[0]}. ${words.slice(1).join(' ')}`;
}

interface CalendarVisitBarProps {
  appt: AppointmentListItem;
  /** Which CSS family to wear — `wk-block` (week) or `day-block` (day). */
  variant: 'wk' | 'day';
  top: number;
  height: number;
  /** Measured lane height in px — one 30-min tick is `laneHeight / 30`. */
  laneHeight: number;
  /** Stylist of this lane — the badge initials (day: the column's name, week: the visit's). */
  employeeName: string | null;
  title: string;
  onOpen: () => void;
}

/**
 * Visit bar of the day and week calendars (shared so both views read the same).
 *
 *   line #1  hh:mm (bold)  Anna. Kowalska            [⌄] [AN]
 *   line #2  Strzyżenie, Modelowanie · 60 min  ★ 5   (★ only: completed AND rated)
 *
 * A bar that can't show both lines (a 30-min visit is exactly one tick) renders line #1 only,
 * plus a hairline chevron before the badge: press and HOLD it and the bar rolls out one tick
 * downward, opaque and above whatever sits there (z-index + a solid backdrop under the status
 * tint); release and it rolls back in. Line #2 is always in the DOM — in the compact form the
 * bar's `overflow: hidden` just clips it, so the roll-out is a plain height transition.
 */
export function CalendarVisitBar({ appt, variant, top, height, laneHeight, employeeName, title, onOpen }: CalendarVisitBarProps) {
  const [rolledOut, setRolledOut] = useState(false);

  const duration = toMinutes(appt.end_time) - toMinutes(appt.start_time);
  const tickPx = laneHeight / (LANE_MINUTES / TICK_MINUTES);
  const compact = duration <= TICK_MINUTES || height < TWO_LINE_MIN_PX;
  const rated = appt.status === 'completed' && appt.satisfaction_score != null;

  function pressStart(e: PointerEvent<HTMLButtonElement>) {
    e.stopPropagation();
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    try {
      // Capture so the release is seen even when the pointer has slid off the tiny handle.
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* synthetic / already-released pointer — the roll-in below still fires on pointerup */
    }
    setRolledOut(true);
  }
  function pressEnd(e: PointerEvent<HTMLButtonElement>) {
    e.stopPropagation();
    setRolledOut(false);
  }
  function keyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault();
    e.stopPropagation();
    if (!e.repeat) setRolledOut(true);
  }
  function keyUp(e: KeyboardEvent<HTMLButtonElement>) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    e.stopPropagation();
    setRolledOut(false);
  }

  const cls = [`${variant}-block`, appt.status, compact ? 'vb-compact' : '', rolledOut ? 'vb-rolled' : ''].filter(Boolean).join(' ');

  return (
    <div className={cls} style={{ top, height: rolledOut ? height + tickPx : height }} onClick={onOpen} title={title}>
      <div className="vb-line">
        <strong className="vb-time">{appt.start_time.slice(0, 5)}</strong>
        <span className="vb-client">{clientLabel(appt.client_name)}</span>
        {compact && (
          <button
            type="button"
            className="vb-roll"
            aria-label="Pokaż szczegóły wizyty (przytrzymaj)"
            onPointerDown={pressStart}
            onPointerUp={pressEnd}
            onPointerCancel={pressEnd}
            onLostPointerCapture={() => setRolledOut(false)}
            onKeyDown={keyDown}
            onKeyUp={keyUp}
            onBlur={() => setRolledOut(false)}
            onClick={(e) => e.stopPropagation()}
            onContextMenu={(e) => e.preventDefault()}
          >
            <Icon name="chevron_down_thin" />
          </button>
        )}
        <span className="vb-badge" title={employeeName ?? undefined} aria-label={employeeName ? `Pracownik: ${employeeName}` : 'Brak pracownika'}>
          {initials(employeeName)}
        </span>
      </div>
      <div className="vb-line" aria-hidden={compact && !rolledOut ? true : undefined}>
        {appt.service_name && <span className="vb-service">{appt.service_name}</span>}
        <span className="vb-meta">
          {appt.service_name ? '· ' : ''}
          {duration} min
        </span>
        {rated && (
          <span className="vb-rating" title={`Ocena klienta: ${appt.satisfaction_score}`}>
            <Icon name="star_filled" />
            {appt.satisfaction_score}
          </span>
        )}
      </div>
    </div>
  );
}
