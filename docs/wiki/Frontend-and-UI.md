# Frontend and UI

## Stack

- React + Vite
- React Query for server state (`frontend/src/query/hooks.ts`)
- Chat shell: sidebar, messages, sources panel, reasoning panel, empty state

## Surfaces

| Route / host | UI |
|--------------|-----|
| App host | Chat |
| `admin.*` or `/admin` | Admin portal |
| `/demo` | Portfolio embed demo (optional, rate-limited) |

## Design sources

Design HTML / Penpot assets may live under `CurAI Designs/` in the repo. Prefer existing CSS variables and components over inventing a new visual system.

## Dev

```bash
cd frontend
npm install
npm run dev
```

Playwright baselines under frontend test folders; update when intentional UI changes land.

## Verification

Use IronBee DevTools browser MCP against the running app (ARIA snapshot first, then interact). See project rules for IronBee.

## Related

- [Chat and Routing](Chat-and-Routing)
- [Admin Portal](Admin-Portal)
- [Testing and Quality](Testing-and-Quality)
