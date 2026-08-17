/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  // Visual identity (color/radius/shadow) comes from tokens.css + components.css,
  // never Tailwind's default palette — see DESIGN.md §0. Tailwind here is only the
  // layout-utility layer (flex/gap/px/py/...); we deliberately do NOT extend
  // theme.colors/borderRadius/boxShadow so nobody can accidentally reach for
  // `bg-blue-500`/`rounded-2xl` instead of a token/named class.
  theme: {
    extend: {},
  },
  plugins: [],
}
