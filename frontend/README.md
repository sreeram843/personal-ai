# Personal AI Web UI

React + Vite chat shell for the Personal AI backend (CurAI).

## Features

- **Unified chat** — backend auto-routes each message (live data, documents, workflows).
- Server-synced conversations (TanStack Query), new chat, document upload.
- **Per-message response time** next to copy / feedback actions.
- **Account menu:** theme toggle (light/dark), about, logout.
- Mobile navigation drawer, safe-area + keyboard-aware composer.
- Voice input (Web Speech API), Playwright UI tests.
- Capacitor iOS/Android shells — see [CAPACITOR.md](./CAPACITOR.md).

UI details: [docs/ui-reference.md](../docs/ui-reference.md).

## Development

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` in `frontend/.env` (default `http://localhost:8000`).

## Tests

```bash
npm run test:unit      # platform helpers (Vitest)
npm run test:e2e       # interaction flows
npm run test:capacitor # mobile drawer + user menu theme
npm run test:visual    # screenshot baselines
npm run test:ui        # all Playwright tests (used by quality gate)
```

## Capacitor (iOS / Android)

See [CAPACITOR.md](./CAPACITOR.md) for native app build, iPhone 17 simulator, and production API URL.

## Benchmarks

API latency data (local 14B vs prod cloud): [docs/model-stress-testing.md](../docs/model-stress-testing.md).
