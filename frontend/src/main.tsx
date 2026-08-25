import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import './styles/index.css';
import { AuthProvider } from './contexts/AuthContext';
import { ToastProvider } from './components/feedback/ToastProvider';
import { ConfirmProvider } from './components/feedback/ConfirmProvider';
import { StatusEventsPoller } from './components/feedback/StatusEventsPoller';
import { router } from './router';

// Mounted once at the app root, per DESIGN.md §8: AuthContext (session/
// permissions), ToastProvider, ConfirmProvider — the system's only global
// state providers. StatusEventsPoller (dobudowane 2026-08-25) rides inside
// both — it needs `useAuth()` to gate on a real session and `useToast()` to
// deliver — and renders nothing itself, so it sits alongside RouterProvider
// rather than wrapping it.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <ToastProvider>
        <ConfirmProvider>
          <StatusEventsPoller />
          <RouterProvider router={router} />
        </ConfirmProvider>
      </ToastProvider>
    </AuthProvider>
  </StrictMode>,
);
