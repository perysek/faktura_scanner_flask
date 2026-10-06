import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-server proxy target for the Flask backend. Override with
// VITE_API_PROXY_TARGET if your local Flask instance runs on a different
// port. Defaults to 5002 — the port dev-start.ps1 always uses for this
// project (not Flask's own default 5000/5001, chosen specifically to avoid
// colliding with an unrelated local project that hardcodes 5001).
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:5002'

// Pages rendered by FLASK, not by the SPA — the links in client/employee SMS and the online
// booking page (+ the /static assets those standalone pages load, and the employee PWA).
// Without this, the SPA's catch-all route answers them with its own "Nie znaleziono" shell:
// every confirm/cancel/rate/visit link and /booking is dead on the React host (SMS review P0-5).
// KEEP IN SYNC with deploy/nginx/public-links.conf — tests/test_public_link_routing.py compares
// the two lists, so a change on one side only fails the build.
const flaskPublicPaths = ['confirm', 'cancel', 'rate', 'visit', 'booking', 'pracownik', 'static']

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Both /api/* (routes/api_routes.py + friends) and /auth/* (routes/auth/routes.py)
      // are proxied so the browser sees one effective origin for session-cookie
      // purposes even though Vite and Flask run on different ports in dev
      // (see implementation-log.md, Decision D1).
      '/api': { target: apiProxyTarget, changeOrigin: true },
      '/auth': { target: apiProxyTarget, changeOrigin: true },
      // The SPA also calls these Flask prefixes directly (lib/api/users.ts, roles.ts,
      // absences.ts, smsSettings.ts). None of them collide with an SPA route (those are
      // Polish: /uzytkownicy, /nieobecnosci, /ustawienia/...). The Vultr preview vhosts
      // (my-way-react-preview + -staging) carry the equivalent
      // `location ~ ^/(system|absences|settings)(/|$)` proxy block — keep both lists in sync.
      '/system': { target: apiProxyTarget, changeOrigin: true },
      '/absences': { target: apiProxyTarget, changeOrigin: true },
      '/settings': { target: apiProxyTarget, changeOrigin: true },
      // One regex key (a leading ^ makes Vite treat it as a RegExp): whole path segments only,
      // so a future SPA route such as /confirmation would not be swallowed.
      [`^/(${flaskPublicPaths.join('|')})(/|$)`]: { target: apiProxyTarget, changeOrigin: true },
    },
  },
})
