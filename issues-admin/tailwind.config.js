/** @type {import('tailwindcss').Config} */
// Same deal as frontend/tailwind.config.js: Tailwind is only the layout-utility layer;
// colour, radius and shadow come from the shared tokens.css + components.css.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}', '../frontend/src/components/**/*.{ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
}
