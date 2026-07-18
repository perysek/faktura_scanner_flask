/**
 * Ported from GUI-GOLDEN-BOOK.md §3 (Design Tokens) and §5 System A
 * (Refined Minimal) — the same tokens the Flask desktop app builds from.
 * Keep this in sync with input.css's :root custom properties.
 */
export const colors = {
  // Ink / text
  ink: '#1a1a1a',
  inkMuted: '#525252',
  inkSubtle: '#8a8a8a',

  // Surfaces
  surface: '#fafafa',
  surfaceWarm: '#f7f6f3',
  cardBackground: '#ffffff',

  // Borders
  border: '#e8e6e1',
  borderSubtle: '#f0eeea',

  // Brand / accent
  accent: '#c9a227',
  accentMuted: 'rgba(201, 162, 39, 0.12)',

  // Semantic
  success: '#2d6a4f',
  warning: '#9a6700',
  error: '#9b2c2c',
  info: '#1e6091',

  // App-specific derived values (not literal tokens, but needed as concrete
  // RN style values built from the tokens above)
  buttonText: '#ffffff',
} as const;

// Status pill per visit state — System A's Status Badge Pattern (§19) keeps
// rounded-full for badges specifically, so only the fill/text colors change
// here, mapped onto the desktop app's real Appointment Status Colors (§3)
// wherever the visit state has a direct equivalent.
export const pillColors = {
  // already_done collapses completed/cancelled/no_show -- completed is the
  // common case, so its color represents the group.
  already_done: { bg: '#f0fdf4', fg: '#2d6a4f', dot: false },
  // end_visit === the appointment is actually in_progress right now.
  end_visit: { bg: '#fffbeb', fg: '#d97706', dot: true },
  // start_visit ("ready now") has no desktop status equivalent -- it's a
  // mobile-only synthetic state, so it gets the same ink-fill treatment as
  // .btn-refined-primary (System A's primary-action convention).
  start_visit: { bg: colors.ink, fg: '#ffffff', dot: false },
  // too_early is still a future scheduled/confirmed/pending visit.
  too_early: { bg: '#eff6ff', fg: '#2563eb', dot: false },
  // wrong_status signals something needs checking -- cancelled's red.
  wrong_status: { bg: '#fef2f2', fg: '#dc2626', dot: false },
  // never appears in a /today row; included so the lookup stays exhaustive.
  success: { bg: '#f0fdf4', fg: '#2d6a4f', dot: false },
} as const;

export const fonts = {
  light: 'Inter_300Light',
  regular: 'Inter_400Regular',
  medium: 'Inter_500Medium',
  semiBold: 'Inter_600SemiBold',
} as const;

export const spacing = {
  cardPaddingVertical: 32,
  cardPaddingHorizontal: 24,
  cardMaxWidth: 420,
  screenPadding: 16,
} as const;

// System A — Refined Minimal: 2px everywhere except badges (rounded-full, §19).
export const radii = {
  control: 2,
  badge: 999,
} as const;
