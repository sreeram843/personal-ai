# Admin portal (`admin.cura-i.com`)

Platform admin for CurAI: providers/models, users/invites, token usage, signup mode.

## URLs

| Surface | URL |
|---------|-----|
| Chat app | `https://app.cura-i.com` |
| Admin portal | `https://admin.cura-i.com` |
| Local admin | `http://localhost:5173/admin` or host `admin.localhost` |

Admin UI mounts when the hostname starts with `admin.` **or** the path is `/admin`.

## Roles

- **admin** — full portal (providers, routing, signup mode, users)
- **support** — users, invites, usage (no provider secrets)
- **user** — chat only

### Allowlisted Google accounts

Only emails in `ADMIN_EMAILS` are promoted to **admin** on Google login (and may sign up without an invite when `AUTH_SIGNUP_MODE=invite`).

```bash
ADMIN_EMAILS=you@gmail.com,cofounder@gmail.com
AUTH_SIGNUP_MODE=invite
AUTH_DISABLED=false
GOOGLE_CLIENT_ID=....apps.googleusercontent.com
```

Anyone else:
- **Cannot** create an account (invite-only), unless you invite them
- **Cannot** open `/admin` unless their role is `admin` or `support`

Bootstrap admins with `ADMIN_EMAILS=you@example.com` (promoted on Google login).

## Security

- Provider API keys stored encrypted (`SETTINGS_SECRET_KEY` / Fernet); API never returns full keys
- `POST /auth/token` email minting disabled when `AUTH_DISABLED=false`
- `AUTH_SIGNUP_MODE=invite` (default) requires invite or admin email; set `open` for public Google signup

## Enable on production

1. Run migrations: `alembic upgrade head` (includes `004_admin_platform`)
2. DNS A record `admin.cura-i.com` → VM IP
3. Set in `.env.cloud`:
   - `CADDY_ADMIN_DOMAIN=admin.cura-i.com`
   - `ADMIN_EMAILS=…`
   - `SETTINGS_SECRET_KEY=…`
   - `CORS_ORIGINS=…,https://admin.cura-i.com`
4. Google OAuth: add `https://admin.cura-i.com` to Authorized JavaScript origins
5. Redeploy: `./scripts/deploy_prod.sh`

## API (staff JWT)

- `GET /admin/me`
- `GET/PATCH /admin/users`
- `GET/POST/DELETE /admin/invites`
- `GET/POST/PATCH /admin/providers` (admin only)
- `GET/PUT /admin/routing` (admin only) — each workflow stage can target a different enabled provider; the gateway registers one OpenAI-compatible adapter per provider at runtime
- `GET/PUT /admin/signup-mode` (admin only)
- `GET /admin/usage/summary`, `GET /admin/usage/by-user`

## Runtime model routing

1. Add providers under **Providers** (OpenAI-compatible `base_url` + API key). Presets in the admin UI:

   | Provider | `base_url` | Example model ids |
   |----------|------------|-------------------|
   | Groq | `https://api.groq.com/openai` | `llama-3.1-8b-instant`, `llama-3.3-70b-versatile` |
   | Perplexity (Sonar chat) | `https://api.perplexity.ai` | `sonar`, `sonar-pro`, `sonar-reasoning-pro` |
   | Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash`, `gemini-2.5-pro` |
   | OpenAI | `https://api.openai.com` | `gpt-4o-mini`, `gpt-4o` |
   | DeepSeek | `https://api.deepseek.com` | `deepseek-chat`, `deepseek-reasoner` |

   Env `PERPLEXITY_API_KEY` is still used for **web search**. Add Perplexity again under Providers only if you want Sonar as a chat/routing model.
2. On **Routing**, assign provider + model id per stage (default / planner / synthesizer / reviewer / writer).
3. Saving clears the in-process settings cache and rebuilds the LLM gateway — **no redeploy**. Next chat uses the new keys/models.
4. Env `LLM_OPENAI_*` still registers as provider `openai` when that name is not defined in the DB.
5. Native Anthropic Claude is not supported yet (needs a dedicated adapter or OpenAI-compat proxy).
