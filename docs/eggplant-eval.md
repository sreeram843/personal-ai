# Eggplant dataset evaluation

Generated: `2026-06-26T19:38:46.468471+00:00`

## Summary

- Datasets on disk: **17**
- Missing HF downloads: **8**
- Not on HuggingFace (manifest only): **13**
- In-repo golden tests passed: **True**

## Manifest verdicts

- use: 7
- partial: 13
- skip: 18

## In-repo checks

- routing golden pytest: pass
- tenant isolation pytest: pass
- security golden heuristics: pass
- retrieval golden pytest: pass
- tool routing pytest: pass
- workflow routing pytest: pass

## Dataset probes

| ID | Status | Rows | Verdict | Notes |
|----|--------|------|---------|-------|
| odsc-arcee-agent-data | present | 1000 | partial | Training corpus; tool schemas do not match builtin_tools. |
| odsc-toolbench | present | 1000 | skip | General tool SFT; not mapped to this app's tool surface. |
| odsc-toolalpaca | not_on_huggingface | — | skip | GitHub-only; 400+ fictional tools. |
| odsc-api-bank | not_on_huggingface | — | skip | Paper + custom runtime; not on HuggingFace as a single dataset. |
| odsc-webshop | not_on_huggingface | — | skip | Browser shopping simulator; no browser agent in this app. |
| odsc-webshop-trajectories | present | 580 | skip | WebShop rollouts only. |
| odsc-alfred | not_on_huggingface | — | skip | Embodied vision + control. |
| odsc-webarena | not_on_huggingface | — | skip | Self-hosted browser benchmark; requires Playwright agent stack. |
| odsc-webchorearena | not_on_huggingface | — | skip | Long web chore tasks. |
| odsc-miniwob | not_on_huggingface | — | skip | Synthetic UI click policies. |
| odsc-gaia | missing_download | — | partial | Manual E2E smoke only; hidden test answers. |
| odsc-agentbench | not_on_huggingface | — | skip | External OS/DB/game simulators. |
| odsc-swebench | present | 50 | skip | Coding-agent patch benchmark; not this product. |
| odsc-omniact | present | 6 | skip | Desktop multimodal automation. |
| odsc-bfcl | missing_download | — | use | Adapt pattern to builtin_tools; HF tool defs differ from ours. |
| hl-qualifire | missing_download | — | partial | Best labeled direct-injection baseline per HiddenLayer. |
| hl-xxz224 | present | 1000 | partial | Unlabeled; red-team prompt bank. |
| hl-yanismiraoui | present | 1000 | partial | Multilingual simple injections. |
| hl-jayavibhav-safety | present | 2000 | partial | Large labeled set; subsample for offline eval. |
| hl-jayavibhav | present | 2000 | partial | Use with caution; label noise on benign class. |
| hl-deepset | present | 546 | skip | Political-bias focused; not core threat model. |
| hl-hackaprompt | missing_download | — | skip | CTF PWNED focus; low real-world signal. |
| hl-cgoosen-password | present | 82 | partial | Small; scenario relevant for RAG secret-leak tests. |
| hl-cgoosen-ctf2 | present | 83 | skip | Narrow CTF. |
| hl-geekyrakshit | present | 500 | skip | Label quality issues. |
| hl-imoxto | present | 500 | skip | Repackaged HackAPrompt. |
| hl-lakera-mosscap | present | 500 | skip | Unlabeled CTF red-team data. |
| internal-routing-golden | not_on_huggingface | — | use | In-repo routing golden set. |
| internal-security-golden | not_on_huggingface | — | use | App-specific direct + indirect injection scenarios. |
| hf-wds-deepplanning | missing_download | — | partial | Long-horizon travel/shopping planning; needs Qwen-Agent sandboxes for real scori |
| hf-wds-docreason25k | present | 500 | partial | Document reasoning QA; closest trending fit for RAG answer quality probes. |
| hf-wds-tablevqa | missing_download | — | partial | Table/chart QA — only if you ingest spreadsheet or table-heavy docs. |
| hf-rag-hotpotqa | present | 500 | use | Multi-hop QA with supporting facts — strong retrieval + synthesis eval seed (not |
| hf-rag-msmarco | missing_download | — | partial | Passage ranking benchmark; good for reranker regression, not end-to-end chat. |
| internal-retrieval-golden | not_on_huggingface | — | use | HotpotQA-inspired rerank/pack + corpus routing hints. |
| internal-tool-calling-golden | not_on_huggingface | — | use | BFCL-adapted live-intent → builtin_tools mapping. |
| internal-workflow-golden | not_on_huggingface | — | use | DeepPlanning-style workflow routing + optional /workflow_chat smoke. |
| hf-rag-natural-questions | missing_download | — | partial | Open-domain QA with long answers; useful for citation-style answer eval. |

## How to re-run

```bash
make eggplant-setup
make eggplant-download
make eggplant-eval
# Live sample against LM Studio (app must be running):
make up-remote
make eggplant-eval-live
make eggplant-eval-live-full   # + indirect injection + workflow + connectivity
make check-remote-inference
make test-eval
make model-accuracy-smoke
```

Full JSON artifact: see `docs/results/eggplant-latest.json`.

## Download notes

- **Gated HF sets** (GAIA, Qualifire, HackAPrompt): set `HF_TOKEN` and accept the Hub license, then re-run download.
- **BFCL**: Hub repo layout may not expose a loadable split; use as a pattern reference only.
- **GitHub-only benchmarks** (WebArena, SWE-bench runtime, AgentBench): listed in manifest with skip reasons.

This harness runs **offline probes** and in-repo golden tests by default.
Use `make eggplant-eval-live` to POST a small prompt sample to `/chat` on a running stack
(e.g. `make up-remote` → LM Studio on :1234).
