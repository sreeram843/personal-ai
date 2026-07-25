# Authentication

## Modes

| Mode | Env | Behavior |
|------|-----|----------|
| Local / CI | `AUTH_DISABLED=true` | No Google required; easy smoke tests |
| Production | `AUTH_DISABLED=false` | Google OAuth + JWT |

## Google OAuth

Configure:

- `GOOGLE_CLIENT_ID`
- Authorized JavaScript origins for app + admin hosts
- CORS: `CORS_ORIGINS` must include chat and admin origins

## Signup

`AUTH_SIGNUP_MODE`:

- **`invite`** (default) — needs invite **or** email in `ADMIN_EMAILS`
- **`open`** — public Google signup

`ADMIN_EMAILS` — comma-separated Google accounts promoted to **admin** on login.

## Roles

| Role | Access |
|------|--------|
| `user` | Chat app |
| `support` | Admin users / invites / usage (no provider secrets) |
| `admin` | Full admin portal including providers + routing |

## Tokens

- Browser holds JWT for API calls
- `POST /auth/token` email minting is disabled when auth is on
- OpenAI `/v1` uses the same `Authorization: Bearer` JWT

## Security notes

- Provider API keys encrypted at rest (`SETTINGS_SECRET_KEY` / Fernet); APIs never return full keys
- Prefer invite mode in production until you intentionally open signup

## Related

- [Admin Portal](Admin-Portal)
- [Deployment](Deployment) — OAuth console + Caddy domains
- In-repo: `docs/admin-portal.md`
