import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { AppRoot } from './AppRoot.tsx';
import { QueryProvider } from './providers/QueryProvider.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryProvider>
      <AppRoot />
    </QueryProvider>
  </StrictMode>,
);
