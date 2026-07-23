from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PermissionMode = Literal["auto", "ask", "plan"]
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "curai"
CONFIG_FILE = CONFIG_DIR / "config.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"


@dataclass
class LlmConfig:
    provider: Literal["ollama", "openai"] = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    api_key: str = ""
    model: str = "llama3.1"
    timeout: float = 120.0


@dataclass
class CuraiApiConfig:
    base_url: str = "http://127.0.0.1:8000"
    token: str = ""


@dataclass
class CliConfig:
    llm: LlmConfig = field(default_factory=LlmConfig)
    curai_api: CuraiApiConfig = field(default_factory=CuraiApiConfig)
    permission_mode: PermissionMode = "ask"
    max_agent_steps: int = 20


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_config() -> CliConfig:
    raw = _load_json(CONFIG_FILE)
    llm_raw = raw.get("llm") if isinstance(raw.get("llm"), dict) else {}
    api_raw = raw.get("curai_api") if isinstance(raw.get("curai_api"), dict) else {}
    creds = _load_json(CREDENTIALS_FILE)
    token = str(creds.get("token") or api_raw.get("token") or "")
    mode = str(raw.get("permission_mode") or "ask").strip().lower()
    if mode not in {"auto", "ask", "plan"}:
        mode = "ask"
    return CliConfig(
        llm=LlmConfig(
            provider="openai" if llm_raw.get("provider") == "openai" else "ollama",
            base_url=str(llm_raw.get("base_url") or LlmConfig.base_url),
            api_key=str(llm_raw.get("api_key") or ""),
            model=str(llm_raw.get("model") or LlmConfig.model),
            timeout=float(llm_raw.get("timeout") or 120.0),
        ),
        curai_api=CuraiApiConfig(
            base_url=str(api_raw.get("base_url") or CuraiApiConfig.base_url),
            token=token,
        ),
        permission_mode=mode,  # type: ignore[arg-type]
        max_agent_steps=int(raw.get("max_agent_steps") or 20),
    )


def save_config(config: CliConfig) -> None:
    _save_json(
        CONFIG_FILE,
        {
            "llm": {
                "provider": config.llm.provider,
                "base_url": config.llm.base_url,
                "api_key": config.llm.api_key,
                "model": config.llm.model,
                "timeout": config.llm.timeout,
            },
            "curai_api": {"base_url": config.curai_api.base_url},
            "permission_mode": config.permission_mode,
            "max_agent_steps": config.max_agent_steps,
        },
    )


def save_token(token: str) -> None:
    _save_json(CREDENTIALS_FILE, {"token": token})
    try:
        CREDENTIALS_FILE.chmod(0o600)
    except OSError:
        pass
