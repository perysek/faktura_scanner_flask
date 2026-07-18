/**
 * Ported 1:1 from the <style> block in
 * templates/public/appointment_employee_status.html — keep both in sync.
 */
export const colors = {
  pageBackground: '#f5f5f0',
  cardBackground: '#ffffff',
  detailsBlockBackground: '#f9f9f7',
  textPrimary: '#1a1a1a',
  textSecondary: '#666666',
  textMuted: '#888888',
  buttonBackground: '#1a1a1a',
  buttonBackgroundPressed: '#333333',
  buttonText: '#ffffff',
  error: '#dc2626',
  shadow: 'rgba(0, 0, 0, 0.08)',
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
