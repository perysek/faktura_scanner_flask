/**
 * Ported 1:1 from Claude Design's "Employee Visit App.dc.html" mockup
 * (Claude-design/Mobile app with Vultr database-handoff.zip) — keep in sync.
 */
export const colors = {
  pageBackground: '#f5f5f0',
  cardBackground: '#ffffff',
  detailsBlockBackground: '#f9f9f7',
  rowBorder: '#f0eee7',
  textPrimary: '#1a1a1a',
  textSecondary: '#666666',
  textMuted: '#888888',
  buttonBackground: '#1a1a1a',
  buttonBackgroundPressed: '#333333',
  buttonText: '#ffffff',
  error: '#dc2626',
  shadow: 'rgba(0, 0, 0, 0.08)',
} as const;

// Status pill per visit state — background/text/pulse-dot, straight from the mockup.
// 'success' never actually appears in a /today row (it's a transient detail-screen
// state after an action) but is included so the lookup stays exhaustive/type-safe.
export const pillColors = {
  already_done: { bg: '#eeece5', fg: '#8a8a80', dot: false },
  end_visit: { bg: '#e7f2ea', fg: '#2d6a4f', dot: true },
  start_visit: { bg: '#1a1a1a', fg: '#ffffff', dot: false },
  too_early: { bg: '#f5f5f0', fg: '#8a8a80', dot: false },
  wrong_status: { bg: '#fbeceb', fg: '#9b2c2c', dot: false },
  success: { bg: '#eeece5', fg: '#8a8a80', dot: false },
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
