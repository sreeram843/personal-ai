# Contributing

Thanks for helping build CurieAI. This guide is for humans; the agent-facing
operating manual is [AGENTS.md](AGENTS.md).

## Before you start

- Check [docs/roadmap.md](docs/roadmap.md) for what's planned and what's done.
- Look for an existing issue or discussion before opening a new one.
- Small doc/typo fixes can go straight to a PR. Anything behavioral should be
  discussed first so it doesn't duplicate or conflict with in-flight work.

## Local development setup

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Start Postgres + Qdrant + Ollama (Docker recommended: `make up`), then:
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Full stack via Docker: `cp .env.example .env && make up && make db-migrate`.

## Branch naming

- `feature/<short-description>` — new capability
- `fix/<short-description>` — bug fix
- `docs/<short-description>` — documentation only
- `learn/<short-description>` — `docs/agent-lab/` experiments (isolated from the
  production chat path)

Keep branches small and single-purpose.

## Pull requests

1. Open a PR against `main` and fill out the PR template (`.github/pull_request_template.md`).
2. Reference the issue you're closing (e.g. `Closes #12`).
3. Keep the change focused; split unrelated work into separate PRs.

### Definition of done

A PR is ready for review when:

- [ ] `./scripts/quality_gate.sh` passes (backend pytest, frontend lint/build/unit, compose validate)
- [ ] `cd frontend && npm run test:ui` passes (Playwright flows + visual)
- [ ] New behavior has tests; existing tests still pass
- [ ] Any doc that describes changed behavior is updated **in the same PR** (see
      "Documentation" below)
- [ ] No secrets, no hardcoded values (use `app/core/config.py` + env vars)

## Review expectations

- Reviewers check correctness, test coverage, and whether the change honors the
  conventions in [AGENTS.md](AGENTS.md) (Python type hints/snake_case, strict
  TypeScript, Tailwind with CSS vars).
- CI must be green before merge; `main` should always build and deploy.
- Don't lower the coverage gate (`--cov-fail-under=35`) casually.

## Documentation

Docs drift is treated as a bug. Any PR that changes behavior must update the
describing doc in the same PR, never as a follow-up:

- Landing + routing: `README.md`
- Architecture / "why": `docs/architecture.md`, `docs/adr/`
- API surface: `docs/api.md`
- Operations: `docs/runbooks/`
- Assistant behavior: `docs/traits.md` (source of truth for `app/prompts/system.md`)

New significant architectural decisions get an ADR under `docs/adr/` (see the
template in that folder). ADR numbers are never reused; a superseded ADR keeps its
number and is marked `Superseded`.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
