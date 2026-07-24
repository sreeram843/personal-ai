# Portfolio embed demo

Embed a **5-question CurAI preview** on your portfolio site. Visitors can try the assistant without signing in; after the limit they are prompted to open the full app.

## Enable on the server

Set these in **`.env.cloud`** on the production VM (see `.env.cloud.example`). The app container reads them via `docker-compose.yml` — a restart/rebuild is required after changes.

```bash
DEMO_ENABLED=true
DEMO_MAX_QUESTIONS=5
DEMO_FULL_APP_URL=https://app.cura-i.com
DEMO_CONTEXT_MAX_CHARS=12000
# Optional custom intro shown as the first assistant message
# DEMO_INTRO=Ask about my work in AI, healthcare engineering, academics, or cricket — or try a live weather/FX question.
# Allow your portfolio to iframe /demo (comma-separated origins)
DEMO_EMBED_ALLOWED_ORIGINS=https://yourname.dev,https://www.yourname.dev
```

On the VM:

```bash
cd /opt/personal-ai
# edit .env.cloud, then:
./scripts/deploy_prod.sh
curl -s https://app.cura-i.com/demo/config
```

Redeploy or restart the stack after changing env vars.

## Embed on your portfolio

Add an iframe pointing at the demo route:

```html
<iframe
  src="https://app.cura-i.com/demo"
  title="CurAI demo"
  width="100%"
  height="560"
  style="border: 0; border-radius: 12px; max-width: 720px;"
  loading="lazy"
  allow="clipboard-write"
></iframe>
```

Adjust `height` to match your layout (minimum ~480px recommended).

### iframe permissions

If the browser blocks embedding, set `DEMO_EMBED_ALLOWED_ORIGINS` to your portfolio origin(s). The API adds a `Content-Security-Policy: frame-ancestors` header on `/demo` responses.

Your portfolio does **not** need to be listed in `CORS_ORIGINS` — the iframe loads CurAI same-origin; chat calls go to the same host.

## Local development

```bash
# In .env or docker env
DEMO_ENABLED=true
AUTH_DISABLED=true make up-cloud   # or your usual dev stack

# Frontend dev server
cd frontend && npm run dev
# Open http://localhost:5173/demo
```

With the API on port 8000 and Vite on 5173, use `http://localhost:5173/demo` (Vite proxies API calls via `VITE_API_BASE_URL`).

## Behavior

| Item | Detail |
|------|--------|
| Quota | Per browser session (`localStorage` session id), in-memory on the server (resets on deploy/restart) |
| Knowledge | `app/prompts/demo-about.md` + `app/prompts/demo-cricket.md` (resume, academics, cricket stats) |
| Live teaser | Allowlisted **weather** and **FX** queries inject verified live context into the reply (no full tool agent) |
| Auth | None required for `/demo` |
| Features | Fast chat + optional live teaser; streaming status→final over SSE; no uploads, conversations, or sign-in |
| UX | Suggested starter chips, always-visible Full app CTA when `DEMO_FULL_APP_URL` is set, action buttons hidden |
| Limit UI | Counter in header; input disabled after N questions with link to full app |

`GET /demo/config` returns `intro`, `max_questions`, `full_app_url`, and `suggested_prompts`. Chat uses `POST /demo/chat` or `POST /demo/chat/stream`.

## Files

- Backend: `app/api/demo_routes.py`, `app/services/demo_quota.py`, `app/schemas/demo.py`
- Profile knowledge: `app/prompts/demo-about.md`, `app/prompts/demo-cricket.md`
- Refresh cricket stats: `node scripts/sync_demo_cricket_profile.mjs --from-file <saved-page.html>`
- Frontend: `frontend/src/DemoApp.tsx`, route at `/demo`
- Reference snippet: `frontend/public/demo-embed.html`
