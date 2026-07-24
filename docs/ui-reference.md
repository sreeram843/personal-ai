# Frontend UI reference

Current chat shell behavior (web + Capacitor). Last updated **2026-06-30**.

## Layout

| Area | Behavior |
|------|----------|
| **Sidebar** | Assistant picker, conversation list (pinned + grouped), new chat, account menu |
| **Header** | Conversation title, assistant name, hamburger (mobile), thinking logo while responding |
| **Empty state** | “What can I help with?” with starter chips (docs, nearby places, workflows, etc.) |
| **Message list** | User bubbles right; assistant plain text + action row |
| **Composer** | Fixed bottom dock, safe-area aware, keyboard-aware on mobile |

There is a **Chat vs Smart mode toggle** in the sidebar. Chat uses `POST /chat/stream` (direct fast path). Smart uses `POST /smart_chat/stream` (automatic routing).

## Account menu (sidebar footer)

| Item | Action |
|------|--------|
| Settings | Opens settings panel (profile, appearance, tool permissions, MCP, skills, assistants, tasks, doctor) |
| About | Opens about panel |
| Log out | Clears session |

Theme is configured under **Settings → Appearance** (light/dark), persisted as `personal-ai-theme`.

## Assistant message actions

Shown when the response is complete (not streaming):

| Control | Purpose |
|---------|---------|
| Copy | Copy message text |
| Regenerate | Re-run last user turn |
| Thumbs up / down | Feedback placeholder |
| **Response time** | `latency_ms` from API, e.g. `17.5s` or `456 ms` |

Latency is stored in Postgres message metadata (`latency_ms`) and survives reload after backend deploy.

## Live-data cards

Assistant messages may include structured cards (weather, FX, stocks, news, **nearby places**, etc.) rendered from `content_blocks` in the API response.

## Metadata not shown in bubbles

Sources, workflow trace, and step memory are not rendered inline for a cleaner UI. Workflow data may still exist in API responses for future use.

## Mobile-specific

- Navigation drawer (`< md`) with overlay dismiss
- Touch targets ≥ 44px on action buttons
- `.message-log` scroll container; body scroll locked on Capacitor native
- Bottom sheets for About and Settings on small screens

See [CAPACITOR.md](../frontend/CAPACITOR.md) for native build and simulator steps.

## Tests

```bash
cd frontend
npm run test:capacitor   # drawer + settings theme
npm run test:e2e         # unified chat flows (/chat/stream)
```
