# Eggplant eval harness

Isolated environment for downloading external agent / prompt-injection datasets and running **offline** verification against this Personal AI codebase.

The name is intentional: a separate purple-skin env that does not pollute the main `.venv` or CI.

## Quick start

```bash
# From repo root
bash eggplant/scripts/setup.sh
bash eggplant/scripts/download_datasets.sh
bash eggplant/scripts/run_eval.sh
```

Outputs:

| Artifact | Purpose |
|----------|---------|
| `eggplant/datasets/*.json` | Sampled HF rows (gitignored) |
| `eggplant/results/eggplant-YYYY-MM-DD.json` | Full machine-readable report |
| `docs/results/eggplant-latest.json` | Latest report (committed) |
| `docs/eggplant-eval.md` | Human-readable summary |

## What gets downloaded

See `eggplant/manifest.json` — 27 entries covering:

- **ODSC** — 15 agent training/eval datasets ([article](https://odsc.medium.com/15-datasets-for-training-and-evaluating-ai-agents-c171dde4e0ce))
- **HiddenLayer** — 12 prompt-injection datasets ([article](https://www.hiddenlayer.com/research/evaluating-prompt-injection-datasets))
- **Internal** — `routing_golden.json`, `security_golden.json`

Only HuggingFace-hosted sets are auto-downloaded. GitHub-only benchmarks (WebArena, SWE-bench runtime, ToolAlpaca, etc.) are catalogued with skip reasons.

For **which HF corpora help this chatbot** (including the [WebDataset trending page](https://huggingface.co/datasets?library=library:datasets,library:webdataset&sort=trending)), see [docs/hf-dataset-selection.md](../docs/hf-dataset-selection.md).

Large corpora are **subsampled** (default 1000 rows; lower where noted in manifest) to keep downloads practical.

## What gets verified (offline)

1. **In-repo pytest** — routing golden + tenant isolation
2. **Security golden heuristics** — direct/indirect injection cases vs `information_routing` trivial-path checks
3. **Dataset probes** — row counts, columns, injection-label heuristics (not LLM calls)
4. **BFCL schema probe** — structural check only; tools are not mapped 1:1 to `builtin_tools`

This harness does **not** claim full jailbreak resistance on public corpora by default. For a **small live sample** against your inference backend (including **LM Studio**), use the live mode below.

## Live LLM smoke (LM Studio, Groq, etc.)

Eggplant does not call LM Studio directly. It POSTs to `/chat` on a **running Personal AI stack**, which routes chat to whatever provider is configured — typically LM Studio when you use `make up-remote`.

```bash
# 1. Start stack with remote inference (.env.remote → LLM_OPENAI_BASE_URL on :1234)
make up-remote

# 2. Run offline probes + ~12 live /chat prompts (security golden + routing + injection samples)
make eggplant-eval-live

# Optional tuning (local 14B is slow — default timeout is 180s per request)
EGGPLANT_LIVE_LIMIT=6 EGGPLANT_LIVE_TIMEOUT=240 make eggplant-eval-live
BASE_URL=http://127.0.0.1:8000 make eggplant-eval-live
```

**Cost:** zero API tokens when LM Studio serves the model locally. Expect **minutes** for a dozen prompts on a 14B GGUF (see `docs/model-stress-testing.md`).

**Scope:** connectivity + non-empty responses — not a full security benchmark. Do not run the full ~11k-row eggplant download through live mode.

### Extended live suite

```bash
make check-remote-inference          # LM Studio + Ollama preflight
make eggplant-eval-live-full         # /chat + indirect ingest/RAG + /workflow_chat
make model-accuracy-smoke            # live FX/weather/stock + LLM probes
make test-eval                       # all offline golden pytest modules
```

Indirect injection cases ingest malicious `document_text` fixtures, then query via `/rag_chat`.

## Makefile shortcuts

```bash
make eggplant-setup
make eggplant-download
make eggplant-eval
make eggplant-eval-live   # requires running app (e.g. make up-remote)
```

## Re-evaluate after heuristic changes

```bash
bash eggplant/scripts/run_eval.sh
```

No re-download needed if `eggplant/datasets/` is already populated.
