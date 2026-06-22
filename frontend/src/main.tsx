import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { AppRoot } from './AppRoot.tsx';
import { initCapacitorShell } from './platform/capacitor.ts';
import { QueryProvider } from './providers/QueryProvider.tsx';

void initCapacitorShell();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryProvider>
      <AppRoot />
    </QueryProvider>
  </StrictMode>,
);
