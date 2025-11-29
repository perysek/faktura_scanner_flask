/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
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
        surface: {
          DEFAULT: '#FFFFFF',
          secondary: '#F5F7FA',
        },
        status: {
          success: '#28A745',
          warning: '#FFC107',
          error: '#DC3545',
          info: '#17A2B8',
        }
      },
      fontFamily: {
        sans: ['Roboto', 'system-ui', 'sans-serif'],
      },
      spacing: {
        'xs': '4px',
        'sm': '8px',
        'md': '16px',
        'lg': '24px',
        'xl': '32px',
        'xxl': '48px',
      },
    },
  },
  plugins: [],
}
