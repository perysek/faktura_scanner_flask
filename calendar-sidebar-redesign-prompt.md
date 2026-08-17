# Calendar month-cards sidebar — UI/UX specification

Redesign the two appointment calendar views — the day-view (a single day's
schedule) and the list-view (a chronological appointments list) — by adding
a collapsible month-cards sidebar. Keep all existing styling, colors, and
behavior of the current views exactly as they are; this is purely additive.

## Layout
- Add a new column on the right of the existing main content, roughly a
  20/80 split with the current view (tolerance ±10%).
- The new column must stretch to the full height of the main view (match
  whatever height the existing content — day-grid timeline / appointments
  list — ends up at).
- The whole column must be collapsible via an icon-button "roll in/out"
  toggle, with its collapsed/expanded state remembered across visits,
  collapsing down to a slim edge tab that stays clickable to re-expand.
- Desktop only: hide this sidebar entirely on narrow/mobile viewports,
  consistent with how other secondary controls on these pages already
  adapt for mobile.

## Month cards
- Inside the sidebar: 3 stacked month-cards, each stretched to an equal
  share of the sidebar's full height.
- Card 1 = the current real-world calendar month (today's actual month) —
  NOT whatever date the main view happens to be browsing. Card 2 =
  current+1 month. Card 3 = current+2 month. This 3-month window is fixed
  and never follows navigation in the main view (e.g. clicking "next day"
  repeatedly in the day-view must NOT shift which 3 months the sidebar
  shows).
- Each card's visual language: a compact header showing the month name and
  year, a row of single/double-letter weekday abbreviations, and below it
  a 7-column grid of circular day-number buttons (no leading/trailing
  filler beyond the current month's own days). No prev/next navigation
  arrows on these 3 cards — they are fixed, read-only date pickers, not
  paginated calendars.
- Each day-number in every card must be clickable.
- Days that have ≥1 scheduled appointment (excluding cancelled/no-show)
  must be visually distinguishable from days with zero appointments,
  directly on the card itself (before any click) — e.g. a small
  dot/marker plus bolder text on days with visits, muted/lighter text on
  empty days.
- Today's date gets its own distinct highlight — a filled, colored circle
  behind the day number (matching the project's own accent/functional
  color, not an imported color).
- Whichever date is currently the active/selected one (in either view)
  gets its own distinct highlight too (e.g. a ring/outline), separate
  from and combinable with the "today" highlight.

## Day-view click behavior
Clicking any day-number in any of the 3 month-cards (while on the
day-view page) simply switches the existing day-grid to show that
clicked date — reuse the exact existing day-grid rendering unchanged,
just re-target it to the new date (same as using the page's own date
picker/prev/next controls). Keep the sidebar's active-day highlight in
sync with whichever navigation control was used (arrows, "today" button,
date input, or a month-card click).

## List-view click behavior — progressive "day-chain"
Clicking a day-number in a month-card while on the list-view page does
the following:

1. Switches the appointments list to show ONLY that single clicked
   day's appointments (not a pre-loaded range).
2. If the clicked day has zero appointments, snap forward to the
   nearest day within the same calendar month that has ≥1 appointment
   (skip empty days silently); if none remain later in that month, fall
   back to the nearest earlier day with appointments in that month; if
   the whole month has zero appointments, show an empty state.
3. Below the list, show a subdued, secondary-styled clickable trigger —
   "Show next day" — with a downward chevron/arrow icon indicating more
   will load beneath it.
4. Clicking that trigger appends the next day (again skipping empty
   days) to the bottom of the list. After each append, the trigger
   re-appears — repeat until the last day of that month with ≥1
   appointment is reached, at which point the trigger disappears (do
   not spill into the next month).
5. Clicking a different day-number on any month-card, OR re-clicking
   the day currently at the top/start of the loaded list, resets the
   list back to showing just that single (newly) clicked day.
6. Default sort for this whole flow is ASCENDING by date+time (earliest
   first) — this overrides any other default sort direction elsewhere
   on the page for this specific flow.
7. Any row whose appointment end-time is already in the past relative
   to the real current time — regardless of its status
   (scheduled/confirmed/etc.) — renders with slightly muted/greyed
   text, to distinguish already-finished visits at a glance.
8. Interacting with the page's own existing week navigation
   (prev/next-week arrows, "today" button, date-picker) exits this
   day-chain mode and returns to the normal default week-window
   browsing behavior already present on the page.

## Design consistency
- Do not change the existing day-grid rendering itself, the existing
  week-window list logic, or any existing colors/typography/spacing
  outside of what's needed to add this sidebar.
- Reuse the project's existing design system — colors, corner radii,
  shadows, spacing scale, button/icon styles — rather than introducing a
  new, foreign visual language for this sidebar.
