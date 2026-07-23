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
- `GET/PUT /admin/routing` (admin only)
- `GET/PUT /admin/signup-mode` (admin only)
- `GET /admin/usage/summary`, `GET /admin/usage/by-user`
