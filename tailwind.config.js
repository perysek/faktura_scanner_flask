/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // Primary brand color with full shade palette
        primary: {
          DEFAULT: '#4472C4',
          50: '#E8EDF7',
          100: '#D1DBF0',
          200: '#A3B7E0',
          300: '#7593D1',
          400: '#4472C4',
          500: '#335AA3',
          600: '#284682',
          700: '#1D3461',
          800: '#122240',
          900: '#09101F',
        },
        // Surface/background colors
        surface: {
          DEFAULT: '#FFFFFF',
          secondary: '#F5F7FA',
          elevated: '#FAFBFC',
        },
        // Status colors for badges, alerts, etc.
        status: {
          success: '#28A745',
          warning: '#FFC107',
          error: '#DC3545',
          info: '#17A2B8',
        },
        // Semantic text colors
        text: {
          primary: '#111827',
          secondary: '#6B7280',
          tertiary: '#9CA3AF',
          inverse: '#FFFFFF',
        },
        // Semantic border colors
        border: {
          light: '#E5E7EB',
          DEFAULT: '#D1D5DB',
          dark: '#9CA3AF',
        },
      },
      fontFamily: {
        sans: ['Roboto', 'system-ui', 'sans-serif'],
      },
      // Consistent spacing scale
      spacing: {
        'xs': '4px',    // 0.25rem - Icon-text gaps, inline spacing
        'sm': '8px',    // 0.5rem  - Small element gaps, button padding
        'md': '16px',   // 1rem    - Card padding, form field gaps
        'lg': '24px',   // 1.5rem  - Section gaps, card margins
        'xl': '32px',   // 2rem    - Page section margins
        'xxl': '48px',  // 3rem    - Major section separators
      },
      // Font size scale for typography hierarchy
      fontSize: {
        'display': ['2.25rem', { lineHeight: '2.5rem', fontWeight: '700' }],    // 36px - Hero text
        'heading': ['1.5rem', { lineHeight: '2rem', fontWeight: '600' }],       // 24px - Page titles
        'subheading': ['1.25rem', { lineHeight: '1.75rem', fontWeight: '600' }], // 20px - Section titles
        'card-title': ['1.125rem', { lineHeight: '1.5rem', fontWeight: '600' }], // 18px - Card headers
        'body-lg': ['1rem', { lineHeight: '1.75rem', fontWeight: '400' }],       // 16px - Emphasized body
        'body': ['0.875rem', { lineHeight: '1.5rem', fontWeight: '400' }],       // 14px - Default body
        'caption': ['0.75rem', { lineHeight: '1.25rem', fontWeight: '400' }],    // 12px - Helper text
      },
      // Box shadow for elevation
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        'dropdown': '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
        'modal': '0 25px 50px -12px rgb(0 0 0 / 0.25)',
      },
      // Border radius consistency
      borderRadius: {
        'card': '8px',
        'button': '8px',
        'input': '6px',
        'badge': '9999px',
      },
    },
  },
  plugins: [],
}
