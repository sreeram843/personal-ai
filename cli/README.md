# CurAI CLI

Installable terminal agent for **natural-language coding** in your project directory.

## Install

```bash
cd cli
pip install -e .
```

Requires **Python 3.11+**, a tool-calling capable model (e.g. `llama3.1` via Ollama), and **ripgrep** (`rg`) for code search.

## Quick start

```bash
# Default: Ollama at http://127.0.0.1:11434, model llama3.1
ollama pull llama3.1

cd /path/to/your/repo
curai ask "list the main Python modules and summarize app/main.py"
curai chat          # interactive REPL (also: bare `curai`)
```

## Configuration

Config lives at `~/.config/curai/config.json`:

```json
{
  "llm": {
    "provider": "ollama",
    "base_url": "http://127.0.0.1:11434",
    "model": "llama3.1"
  },
  "permission_mode": "ask",
  "max_agent_steps": 20
}
```

For OpenAI-compatible APIs (LM Studio, vLLM, Groq, DeepSeek, etc.):

```json
{
  "llm": {
    "provider": "openai",
    "base_url": "http://localhost:1234",
    "api_key": "sk-local",
    "model": "your-model"
  }
}
```

**DeepSeek** (tool-calling agent; use `deepseek-chat` or `deepseek-v4-pro`):

```json
{
  "llm": {
    "provider": "openai",
    "base_url": "https://api.deepseek.com",
    "api_key": "your-deepseek-api-key",
    "model": "deepseek-chat",
    "timeout": 120
  }
}
```

## Commands

| Command | Description |
|---------|-------------|
| `curai` / `curai chat` | Interactive coding REPL |
| `curai ask "..."` | One-shot task |
| `curai auth login` | Save JWT for CurAI API (optional) |
| `curai config` | Show config path and values |

### Flags

- `--permission ask|auto|plan` — tool approval (default: `ask`)
- `--model NAME` — override LLM model
- `-C /path` — workspace root (default: cwd)

## Tools (agent)

The agent can call: `list_directory`, `read_file`, `search_code`, `write_file`, `edit_file`, `run_command`, `git_status`, `git_diff`.

Writes and shell commands prompt for approval in `ask` mode.

## Tests

```bash
cd cli && pip install -e '.[dev]' && pytest -q
python cli/scripts/smoke_generic_answer.py   # mocked LLM, no Ollama
make cli-smoke                               # from repo root
```

## Architecture

The CLI runs a **local tool loop** against your LLM. The CurAI FastAPI backend is optional (auth, future RAG/history integration). See [../docs/architecture.md](../docs/architecture.md).
