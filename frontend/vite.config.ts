import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-server proxy target for the Flask backend. Override with
// VITE_API_PROXY_TARGET if your local Flask instance runs on a different
// port. Defaults to 5002 — the port dev-start.ps1 always uses for this
// project (not Flask's own default 5000/5001, chosen specifically to avoid
// colliding with an unrelated local project that hardcodes 5001).
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:5002'

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
    },
  },
})
