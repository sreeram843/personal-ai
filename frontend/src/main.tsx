import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { AppRoot } from './AppRoot.tsx';
import { initCapacitorShell } from './platform/capacitor.ts';
import { QueryProvider } from './providers/QueryProvider.tsx';

void initCapacitorShell();

function isDemoRoute(): boolean {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  return path === '/demo';
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryProvider>
      <AppRoot demoMode={isDemoRoute()} />
    </QueryProvider>
  </StrictMode>,
);
