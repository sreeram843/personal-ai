import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { AdminApp } from './AdminApp.tsx';
import { AppRoot } from './AppRoot.tsx';
import { LegalPage } from './components/LegalPage.tsx';
import { initCapacitorShell } from './platform/capacitor.ts';
import { QueryProvider } from './providers/QueryProvider.tsx';

void initCapacitorShell();

function isDemoRoute(): boolean {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  return path === '/demo';
}

function isAdminHost(): boolean {
  const host = window.location.hostname.toLowerCase();
  if (host === 'admin.cura-i.com' || host.startsWith('admin.')) {
    return true;
  }
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  return path === '/admin' || path.startsWith('/admin/');
}

function legalDocument(): 'privacy' | 'terms' | null {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  if (path === '/privacy') {
    return 'privacy';
  }
  if (path === '/terms') {
    return 'terms';
  }
  return null;
}

const legal = legalDocument();
const root = (
  <StrictMode>
    <QueryProvider>
      {legal ? <LegalPage document={legal} /> : isAdminHost() ? <AdminApp /> : <AppRoot demoMode={isDemoRoute()} />}
    </QueryProvider>
  </StrictMode>
);

createRoot(document.getElementById('root')!).render(root);
