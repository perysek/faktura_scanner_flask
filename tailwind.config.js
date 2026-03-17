/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',  // Main primary
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        accent: {
          400: '#34d399',
          500: '#10b981',  // Main accent
          600: '#059669',
        },
        brand: {
          50:  '#fdf8ec',
          100: '#f9eecc',
          200: '#f2d98a',
          300: '#e8c050',
          400: '#d9a82e',
          500: '#c9a227',  // Gold accent — matches --color-accent in content pages
          600: '#a8851f',
          700: '#866817',
          800: '#644e11',
          900: '#42330b',
        },
        slate: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          850: '#162032', // Custom for sidebar
          900: '#0f172a',
        },
        // Semantic overrides if needed, mapping to the above
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
      },
      boxShadow: {
        'xl': '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
        '2xl': '0 25px 50px -12px rgb(0 0 0 / 0.25)',
      }
    },
  },
  plugins: [],
}
