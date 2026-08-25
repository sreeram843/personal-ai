// Online-only shell; not an offline app.

self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

const API_PREFIXES = [
  '/chat',
  '/api',
  '/auth',
  '/conversations',
  '/documents',
  '/ingest',
  '/demo',
  '/admin',
  '/users',
  '/openai',
  '/v1',
  '/smart_chat',
  '/rag_chat',
  '/workflow',
  '/health',
  '/ready',
];

function isApiPath(pathname) {
  return API_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') {
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || isApiPath(url.pathname)) {
    return;
  }

  if (request.mode !== 'navigate') {
    return;
  }

  event.respondWith(fetch(request));
});
