import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * issues-admin — the support-ticket desk at issues.my-way-solutions.com.
 *
 * A separate SPA with its own build and deploy, but NOT a separate design system:
 * `@shared/*` points at the main app's frontend/src, so tokens, components.css,
 * <Button>, <Icon>, the form fields, the toast stack, AuthContext and the fetch
 * client are the very same files. Shared files import 'react' from THEIR folder,
 * so every runtime dependency is pinned to this app's node_modules below — one
 * React instance, one router, whatever is (or isn't) installed in frontend/.
 */
const here = (p: string) => fileURLToPath(new URL(p, import.meta.url));

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:5002';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      { find: '@shared', replacement: here('../frontend/src') },
      { find: /^react$/, replacement: here('./node_modules/react/index.js') },
      { find: /^react\/jsx-runtime$/, replacement: here('./node_modules/react/jsx-runtime.js') },
      { find: /^react\/jsx-dev-runtime$/, replacement: here('./node_modules/react/jsx-dev-runtime.js') },
      { find: /^react-dom$/, replacement: here('./node_modules/react-dom/index.js') },
      { find: /^react-dom\/client$/, replacement: here('./node_modules/react-dom/client.js') },
      { find: /^react-router-dom$/, replacement: here('./node_modules/react-router-dom') },
      { find: /^@fontsource-variable\/geist$/, replacement: here('./node_modules/@fontsource-variable/geist/index.css') },
    ],
    dedupe: ['react', 'react-dom', 'react-router-dom'],
  },
  server: {
    port: 5174,
    fs: { allow: [here('..')] },
    proxy: {
      '/api': { target: apiProxyTarget, changeOrigin: true },
      '/auth': { target: apiProxyTarget, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
