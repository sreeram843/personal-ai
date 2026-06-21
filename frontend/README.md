# Personal AI Web UI

React + Vite chat shell for the Personal AI backend.

## Features

- Quick Chat and Smart Chat modes (backend auto-routes in Smart mode).
- Conversation list, new chat, document upload, light/dark theme.
- Streaming workflow trace, RAG sources, and step memory in assistant bubbles.
- Voice input (Web Speech API), accessibility landmarks, and Playwright UI tests.

## Development

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` in `frontend/.env` (default `http://localhost:8000`).

## Tests

```bash
npm run test:e2e      # interaction flows
npm run test:visual   # screenshot baselines
npm run test:ui       # both (used by quality gate)
```
