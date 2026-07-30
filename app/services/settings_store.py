"""DB-backed LLM settings overlay with env fallback and short TTL cache."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import LlmProvider, LlmRouting, SystemFlag
from app.services.secret_box import SettingsCryptoError, decrypt_secret

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 15.0
_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}

FLAG_SIGNUP_MODE = "auth_signup_mode"


@dataclass(frozen=True)
class EffectiveOpenAIConfig:
    base_url: Optional[str]
    api_key: Optional[str]
    provider_name: str = "openai"


@dataclass(frozen=True)
class EffectiveRouting:
    default_provider: str
    default_model: str
    planner_provider: str
    planner_model: str
    synthesizer_provider: str
    synthesizer_model: str
    reviewer_provider: str
    reviewer_model: str
    writer_provider: str
    writer_model: str


def clear_settings_cache() -> None:
    with _lock:
        _cache.clear()


def _cached(key: str, factory):
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]
    value = factory()
    with _lock:
        _cache[key] = (now, value)
    return value


def get_signup_mode(db: Session, settings: Optional[Settings] = None) -> str:
    cfg = settings or get_settings()
    # Do not cache signup mode: it must reflect DB flags and Settings immediately in tests and admin toggles.
    row = db.get(SystemFlag, FLAG_SIGNUP_MODE)
    if row and row.value.strip() in {"invite", "open"}:
        return row.value.strip()
    mode = (cfg.auth_signup_mode or "invite").strip().lower()
    return mode if mode in {"invite", "open"} else "invite"


def set_signup_mode(db: Session, mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in {"invite", "open"}:
        raise ValueError("signup mode must be invite or open")
    row = db.get(SystemFlag, FLAG_SIGNUP_MODE)
    if row is None:
        row = SystemFlag(key=FLAG_SIGNUP_MODE, value=normalized)
        db.add(row)
    else:
        row.value = normalized
    db.commit()
    clear_settings_cache()
    return normalized


def _provider_to_config(provider: LlmProvider, cfg: Settings) -> EffectiveOpenAIConfig | None:
    api_key = None
    if provider.encrypted_api_key:
        try:
            api_key = decrypt_secret(provider.encrypted_api_key, cfg)
        except SettingsCryptoError:
            logger.warning(
                "Skipping provider %s: cannot decrypt API key (SETTINGS_SECRET_KEY mismatch?). "
                "Re-save the key in Admin.",
                provider.name,
            )
            return None
    return EffectiveOpenAIConfig(
        base_url=provider.base_url,
        api_key=api_key,
        provider_name=provider.name,
    )


def list_enabled_provider_configs(db: Session, settings: Optional[Settings] = None) -> list[EffectiveOpenAIConfig]:
    """Return decrypted configs for every enabled OpenAI-compatible admin provider."""
    cfg = settings or get_settings()

    def load() -> list[EffectiveOpenAIConfig]:
        rows = list(
            db.scalars(
                select(LlmProvider).where(LlmProvider.enabled.is_(True)).order_by(LlmProvider.created_at.asc())
            ).all()
        )
        configs: list[EffectiveOpenAIConfig] = []
        for row in rows:
            config = _provider_to_config(row, cfg)
            if config is not None:
                configs.append(config)
        return configs

    return list(_cached("enabled_providers", load))


def get_effective_openai_config(db: Session, settings: Optional[Settings] = None) -> EffectiveOpenAIConfig:
    cfg = settings or get_settings()

    def load() -> EffectiveOpenAIConfig:
        routing = get_effective_routing(db, cfg)
        providers = list_enabled_provider_configs(db, cfg)
        by_name = {item.provider_name: item for item in providers}
        if routing.default_provider in by_name:
            return by_name[routing.default_provider]
        if providers:
            return providers[0]
        return EffectiveOpenAIConfig(
            base_url=cfg.llm_openai_base_url,
            api_key=cfg.llm_openai_api_key,
            provider_name="openai",
        )

    return _cached("openai_config", load)


def get_effective_routing(db: Session, settings: Optional[Settings] = None) -> EffectiveRouting:
    cfg = settings or get_settings()

    def load() -> EffectiveRouting:
        row = db.scalar(select(LlmRouting).order_by(LlmRouting.id.asc()).limit(1))
        if row is not None:
            return EffectiveRouting(
                default_provider=row.default_provider,
                default_model=row.default_model,
                planner_provider=row.planner_provider,
                planner_model=row.planner_model,
                synthesizer_provider=row.synthesizer_provider,
                synthesizer_model=row.synthesizer_model,
                reviewer_provider=row.reviewer_provider,
                reviewer_model=row.reviewer_model,
                writer_provider=row.writer_provider,
                writer_model=row.writer_model,
            )
        return EffectiveRouting(
            default_provider=cfg.llm_default_provider,
            default_model=cfg.llm_default_model,
            planner_provider=cfg.llm_planner_provider,
            planner_model=cfg.llm_planner_model,
            synthesizer_provider=cfg.llm_synthesizer_provider,
            synthesizer_model=cfg.llm_synthesizer_model,
            reviewer_provider=cfg.llm_reviewer_provider,
            reviewer_model=cfg.llm_reviewer_model,
            writer_provider=cfg.llm_writer_provider,
            writer_model=cfg.llm_writer_model,
        )

    return _cached("routing", load)


def resolve_chat_default_route(settings: Optional[Settings] = None) -> tuple[str, str]:
    """Provider/model for single-call Chat paths — prefer Admin Default routing."""
    cfg = settings or get_settings()
    try:
        from app.db.session import get_session_factory

        db = get_session_factory()()
        try:
            routing = get_effective_routing(db, cfg)
            provider = (routing.default_provider or "").strip() or cfg.llm_default_provider
            model = (routing.default_model or "").strip() or cfg.llm_default_model
            return provider, model
        finally:
            db.close()
    except Exception:
        logger.exception("Failed to resolve Admin default routing; using env LLM defaults")
        return cfg.llm_default_provider, cfg.llm_default_model


__all__ = [
    "EffectiveOpenAIConfig",
    "EffectiveRouting",
    "FLAG_SIGNUP_MODE",
    "clear_settings_cache",
    "get_effective_openai_config",
    "get_effective_routing",
    "get_signup_mode",
    "list_enabled_provider_configs",
    "resolve_chat_default_route",
    "set_signup_mode",
]
