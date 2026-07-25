# Wiki maintenance

## Source of truth

| Layer | Role |
|-------|------|
| This GitHub Wiki | Navigable handbook for humans |
| `docs/*.md` in the repo | Deep, versioned with code |
| `.env*.example` | Exact config knobs |

When behavior changes, update **both** the relevant `docs/` file (or README) and the matching wiki page.

## Edit options

1. GitHub website: Wiki tab → edit page  
2. Git: clone `https://github.com/sreeram843/personal-ai.wiki.git`, edit `*.md`, commit, push  

Page names use spaces as hyphens in filenames (`Getting-Started.md` → “Getting Started”).

## Bootstrap from repo

Canonical pages live under **`docs/wiki/`** in the main repository (versioned with code).

```bash
# One-time: if wiki git remote does not exist yet
# → https://github.com/sreeram843/personal-ai/wiki → "Create the first page" → Save

./scripts/publish_wiki.sh
```

That rsyncs `docs/wiki/` into `personal-ai.wiki.git` and pushes.
