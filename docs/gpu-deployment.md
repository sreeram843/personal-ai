# GPU deployment guide

Personal AI supports GPU-accelerated chat through the **`gpu-vllm`** Compose profile while keeping embeddings on Ollama.

## Quick start (Compose)

```bash
cp .env.gpu-vllm.example .env.gpu-vllm
# Set HF_TOKEN and model ids
make up-gpu-vllm
```

- Chat: `http://localhost:8001/v1` (vLLM OpenAI-compatible API)
- Embeddings: `http://localhost:11434` (Ollama `nomic-embed-text`)
- App: `http://localhost:8000`

## Requirements

- NVIDIA GPU with sufficient VRAM for the chosen model (8B models typically need ~16GB)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-kit/install-guide.html)
- Hugging Face token for gated models (Llama, etc.)

## Kubernetes (Helm)

```bash
helm install personal-ai ./helm/personal-ai \
  --set image.repository=your-registry/personal-ai \
  --set env.LLM_OPENAI_BASE_URL=http://vllm:8000/v1 \
  --set env.LLM_DEFAULT_PROVIDER=openai
```

Wire probes to:

- Liveness: `GET /health`
- Readiness: `GET /ready`

Deploy vLLM as a separate GPU-tainted Deployment/Service and point `LLM_OPENAI_BASE_URL` at it. Keep Ollama (or a dedicated embed service) for `OLLAMA_BASE_URL`.

## Accuracy verification

Use the eval tests as regression guards for routing and grounding:

```bash
pytest tests/test_eval_routing_accuracy.py tests/test_eval_rag_grounding.py -q
```

For live LLM quality checks, run scripted prompts against **`POST /chat`** or **`POST /chat/stream`** and assert:

- workflow traces appear for multi-step prompts
- `/rag_chat` returns sources with document paths
- tenant isolation via `tests/test_workflow_run_scoping.py`

See also [compose-profiles.md](compose-profiles.md).
