import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-server proxy target for the Flask backend. Override with
// VITE_API_PROXY_TARGET if your local Flask instance runs on a different
// port (see implementation-log.md, Decision D2 — no explicit app.run(port=...)
// was found in the repo, so this assumes the Flask default of 5000).
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:5000'

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
