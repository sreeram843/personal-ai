# Admin Portal

Platform admin for CurAI: providers/models, users/invites, token usage, signup mode.

## URLs

| Surface | URL |
|---------|-----|
| Chat | https://app.cura-i.com |
| Admin | https://admin.cura-i.com |
| Local | http://localhost:5173/admin or host `admin.localhost` |

Admin UI mounts when hostname starts with `admin.` **or** path is `/admin`.

## Enable on production

1. Migrations: `alembic upgrade head` (includes admin platform revision)
2. DNS: `admin.cura-i.com` → VM IP
3. `.env.cloud`: `CADDY_ADMIN_DOMAIN`, `ADMIN_EMAILS`, `SETTINGS_SECRET_KEY`, CORS includes admin origin
4. Google OAuth: add admin origin
5. Redeploy: `./scripts/deploy_prod.sh`

## Staff API (JWT)

- `GET /admin/me`
- Users: `GET/PATCH /admin/users`
- Invites: `GET/POST/DELETE /admin/invites`
- Providers: `GET/POST/PATCH /admin/providers` (admin)
- Routing: `GET/PUT /admin/routing` (admin) — per-stage provider + model
- Signup mode: `GET/PUT /admin/signup-mode` (admin)
- Usage: `GET /admin/usage/summary`, `GET /admin/usage/by-user`

## Runtime model routing

1. Add providers (OpenAI-compatible `base_url` + API key). Common presets:

| Provider | Example base_url | Example models |
|----------|------------------|----------------|
| Groq | `https://api.groq.com/openai` | current Groq chat ids |
| Perplexity Sonar | `https://api.perplexity.ai` | `sonar`, `sonar-pro`, … |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash`, … |
| OpenAI | `https://api.openai.com` | `gpt-4o-mini`, … |
| DeepSeek | `https://api.deepseek.com` | `deepseek-v4-flash`, … |

2. On **Routing**, assign provider + model for default / planner / synthesizer / reviewer / writer.

Legacy model id remaps exist for some Groq/DeepSeek aliases — see `docs/admin-portal.md`.

## Related

- [Authentication](Authentication)
- [Chat and Routing](Chat-and-Routing)
- [Configuration](Configuration)
