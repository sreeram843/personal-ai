# CurAI Marketing Site and Domain Architecture

## Domain architecture

| Host | Purpose | Owner |
|------|---------|-------|
| `https://cura-i.com` | Public marketing site, product overview, legal navigation | Squarespace |
| `https://www.cura-i.com` | Redirect to `https://cura-i.com` | Squarespace / DNS |
| `https://app.cura-i.com` | CurAI product and public `/privacy` + `/terms` fallbacks | CurAI deployment |
| `https://admin.cura-i.com` | Restricted administration portal | CurAI deployment |
| `https://grafana.app.cura-i.com` | Restricted operations dashboards | CurAI deployment |

The application includes public legal pages at:

- `https://app.cura-i.com/privacy`
- `https://app.cura-i.com/terms`

These can be used for Google OAuth verification immediately. The Squarespace site should either publish equivalent pages at `https://cura-i.com/privacy` and `https://cura-i.com/terms`, or redirect those paths to the app-hosted pages.

## Squarespace landing-page specification

Use the transparent CurAI mark from `frontend/public/curai-favicon.svg` and the product’s warm amber accent. Keep the page compact:

1. **Hero**
   - Eyebrow: `A personal AI that knows when to think deeper`
   - Heading: `Chat fast. Search your knowledge. Work through complex problems.`
   - Body: `CurAI combines direct AI chat, document-grounded answers, live information, and multi-step workflows in one private workspace.`
   - Primary CTA: `Open CurAI` → `https://app.cura-i.com`
   - Secondary CTA: `Learn how it works` → feature section
2. **Core capabilities**
   - `Direct chat` — Fast answers for everyday questions and writing.
   - `Grounded answers` — Upload documents and see the sources behind each response.
   - `Live information` — Weather, markets, news, and nearby places with provenance.
   - `Smart workflows` — Route complex requests through planning, retrieval, and review.
3. **Trust section**
   - `Your conversations and documents stay scoped to your account.`
   - `Live answers show their source and freshness.`
   - `Export or delete your account data from settings.`
4. **Final CTA**
   - Heading: `Bring your questions, documents, and decisions together.`
   - Button: `Launch CurAI` → `https://app.cura-i.com`
5. **Footer**
   - Privacy → `/privacy`
   - Terms → `/terms`
   - Product → `https://app.cura-i.com`
   - Support contact once issue #25 is completed

## Publishing checklist

- [ ] Connect `cura-i.com` and set it as the Squarespace primary domain.
- [ ] Redirect `www` to the apex domain.
- [ ] Add the CurAI favicon/logo without an opaque white background.
- [ ] Publish Privacy and Terms pages or redirects.
- [ ] Link every CTA to `https://app.cura-i.com`.
- [ ] Verify mobile layout and metadata/social preview.
- [ ] Set `PRIVACY_POLICY_URL` and `TERMS_OF_SERVICE_URL` in `.env.cloud`.
- [ ] Add the public legal URLs to the Google OAuth consent screen.

Recommended production values while the app hosts the canonical legal copy:

```dotenv
PRIVACY_POLICY_URL=https://app.cura-i.com/privacy
TERMS_OF_SERVICE_URL=https://app.cura-i.com/terms
```

After Squarespace publishes canonical legal pages, switch both variables to the apex-domain URLs.

> Legal note: the included policy and terms are a practical product template, not legal advice. Review them for the operator’s jurisdiction and business model before broad public launch.
