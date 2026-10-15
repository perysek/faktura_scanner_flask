import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider, createBrowserRouter, Navigate } from 'react-router-dom';
import './styles.css';
import { AuthProvider } from '@shared/contexts/AuthContext';
import { ToastProvider } from '@shared/components/feedback/ToastProvider';
import { installDiagnostics } from '@shared/lib/support/diagnostics';
import { LoginPage } from './LoginPage';
import { DeskGate } from './DeskGate';
import { Desk } from './Desk';

installDiagnostics();

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: <DeskGate />,
    children: [
      { index: true, element: <Desk /> },
      { path: 't/:ticketId', element: <Desk /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </AuthProvider>
  </StrictMode>,
);
