# Frontend UI reference

Current chat shell behavior (web + Capacitor). Last updated **2026-06-22**.

## Layout

| Area | Behavior |
|------|----------|
| **Sidebar** | Conversations, Chat/Smart mode, new chat, account menu |
| **Header** | Conversation title, hamburger (mobile), thinking logo while responding |
| **Message list** | User bubbles right; assistant plain text + action row |
| **Composer** | Fixed bottom dock, safe-area aware, keyboard-aware on mobile |

## Account menu (sidebar footer)

| Item | Action |
|------|--------|
| About | Opens about panel |
| Light / Dark mode | Toggles theme (persisted in localStorage) |
| Log out | Clears session |

Theme and settings are **not** in the header anymore (settings panel removed).

## Assistant message actions

Shown when the response is complete (not streaming):

| Control | Purpose |
|---------|---------|
| Copy | Copy message text |
| Regenerate | Re-run last user turn |
| Thumbs up / down | Feedback placeholder |
| **Response time** | `latency_ms` from API, e.g. `17.5s` or `456 ms` |

Latency is stored in Postgres message metadata (`latency_ms`) and survives reload after backend deploy.

## Removed from header

- Share conversation button
- Settings button / settings bottom sheet
- Ready status chip (replaced by animated logo while busy)

## Smart mode metadata in bubbles

Sources, workflow trace, step memory, and header latency chips were removed from assistant bubbles for a cleaner UI. Workflow data may still exist in API responses for future use.

## Mobile-specific

- Navigation drawer (`< md`) with overlay dismiss
- Touch targets ≥ 44px on action buttons
- `.message-log` scroll container; body scroll locked on Capacitor native
- Bottom sheets for About on small screens

See [CAPACITOR.md](../frontend/CAPACITOR.md) for native build and simulator steps.

## Tests

```bash
cd frontend
npm run test:capacitor   # drawer + user menu theme
npm run test:e2e         # full flows
```
