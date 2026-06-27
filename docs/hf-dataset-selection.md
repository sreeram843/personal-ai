# Hugging Face dataset selection for Personal AI

This doc explains which public datasets help **this** chatbot (text RAG + routing + tools + small context) and which do not — including the [HF trending WebDataset page](https://huggingface.co/datasets?library=library:datasets,library:webdataset&sort=trending).

## TL;DR

| Source | Take? | Why |
|--------|-------|-----|
| **HF text RAG sets** (HotpotQA, MS MARCO, NQ) | **Yes** — add to eggplant | Match retrieval, multi-hop, citation behavior |
| **Trending WebDataset — doc/planning** (DocReason25K, DeepPlanning, TableVQA) | **Partial** — cherry-pick | Only text-reasoning slices; heavy sandboxes for DeepPlanning |
| **Trending WebDataset — everything else** | **No** | Audio, video, robotics, image pretraining — wrong modality |

Eggplant manifest: `eggplant/manifest.json` (categories `hf-webdataset-trending`, `hf-text-rag-recommended`).

```bash
make eggplant-download   # pulls new manifest entries (subsampled)
make eggplant-eval
```

---

## Why the WebDataset trending page is mostly wrong for us

That filter surfaces **large-scale training shards** (audio, video, images, robotics) packaged as WebDataset tar streams — optimized for pretraining pipelines, not for evaluating a personal document chatbot.

From the current trending list:

| Dataset | Scale / type | Verdict | Reason |
|---------|----------------|---------|--------|
| amphion/Emilia-NV, Emilia-Dataset | Speech / TTS | **Skip** | No voice interface |
| builddotai/Egocentric-100K, AgiBotWorld | Video / robotics | **Skip** | No embodied agent |
| pixparse/cc12m-wds, GPT-Image-Edit, anime sets | Images | **Skip** | Not a vision chatbot |
| InternRobotics/OmniWorld, olmoearth | Billion-row pretrain | **Skip** | Training corpus, not eval |
| apple/DataCompDR-12M | Image-text pretrain | **Skip** | Same |
| bop-benchmark/hot3d | 3D hands | **Skip** | Irrelevant modality |
| atlasia/Moroccan-Darija-Wiki-Audio | Speech | **Skip** | Unless you add ASR |
| **mPLUG/DocReason25K** | Document reasoning | **Partial** | Closest match on the page |
| **terryoo/TableVQA-Bench** | Table/chart QA | **Partial** | If users upload tables |
| **Qwen/DeepPlanning** | Travel + shopping planning | **Partial** | Workflow planner stress-test; needs [Qwen-Agent sandboxes](https://github.com/QwenLM/Qwen-Agent/tree/main/benchmark/deepplanning) |
| TIGER-Lab/VISTA-400K | Vision-language | **Skip** | Multimodal |
| TalTechNLP/voxlingua107_wds | Speech | **Skip** | Audio |

**Do not bulk-download** trending WebDataset corpora into eggplant — disk, time, and eval signal are poor.

---

## What actually makes this chat agent better

Aligned with the P1–P10 stack (routing, retrieval, self-RAG, corpus synthesis, tools):

### 1. Retrieval + grounding (highest ROI)

| Dataset | HF id | Use |
|---------|-------|-----|
| HotpotQA | `hotpot_qa` | Multi-hop questions + supporting sentence labels → retrieval golden cases |
| MS MARCO | `microsoft/ms_marco` | Passage ranking → reranker / wide→narrow pack regression |
| Natural Questions | `google-research-datasets/natural_questions` | Long-form answers with Wikipedia context |

These are **not** on the WebDataset trending filter but are the right class for your product.

### 2. Tool + planning (medium ROI)

| Dataset | Use |
|---------|-----|
| [BFCL](https://huggingface.co/datasets/gorilla-llm/Berkeley-Function-Calling-Leaderboard) | Adapt cases to `search_documents`, `fx_rate`, weather tools |
| [Qwen/DeepPlanning](https://huggingface.co/datasets/Qwen/DeepPlanning) | Offline inspiration for orchestrated **workflow** planner; full eval needs isolated DB + toolkits |

### 3. Security (supplement)

HiddenLayer-recommended injection sets (already in eggplant) — not for “better answers,” but for abuse regression.

### 4. Internal goldens (best ROI)

`routing_golden.json`, `security_golden.json`, and a future `retrieval_golden.json` over **your** ingest fixtures beat any public trending set.

---

## WebDataset format note

WebDataset (`library:webdataset`) stores tar shards for high-throughput training. Eggplant uses the Hugging Face `datasets` library with **row slices** (`train[:500]`) into JSON for offline probes — fine for eval-sized sets, not for 7B-row pretraining dumps.

---

## Re-run after manifest changes

```bash
make eggplant-download
make eggplant-eval
```

See [eggplant-eval.md](./eggplant-eval.md) for latest download counts and probe results.
