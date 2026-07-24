"""Multi-provider LLM gateway: one adapter per enabled admin provider."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from app.core.config import Settings
from app.core.deps import get_llm_gateway, get_ollama_client, get_workflow_model_profile
from app.db.models import LlmProvider, LlmRouting
from app.services.llm_gateway import OpenAICompatibleLLMAdapter
from app.services.secret_box import encrypt_secret
from app.services.settings_store import clear_settings_cache, list_enabled_provider_configs


def test_list_enabled_provider_configs_decrypts_keys(db_session, auth_settings: Settings) -> None:
    settings = auth_settings.model_copy(update={"settings_secret_key": "multi-provider-secret"})
    db_session.add(
        LlmProvider(
            id=uuid.uuid4(),
            name="groq",
            display_name="Groq",
            base_url="https://api.groq.com/openai",
            encrypted_api_key=encrypt_secret("gsk_groq_secret_aaaa", settings),
            key_last4="aaaa",
            enabled=True,
        )
    )
    db_session.add(
        LlmProvider(
            id=uuid.uuid4(),
            name="deepseek",
            display_name="DeepSeek",
            base_url="https://api.deepseek.com",
            encrypted_api_key=encrypt_secret("sk-deepseek-bbbb", settings),
            key_last4="bbbb",
            enabled=True,
        )
    )
    db_session.add(
        LlmProvider(
            id=uuid.uuid4(),
            name="disabled_openai",
            display_name="OpenAI",
            base_url="https://api.openai.com",
            encrypted_api_key=encrypt_secret("sk-openai-cccc", settings),
            key_last4="cccc",
            enabled=False,
        )
    )
    db_session.commit()
    clear_settings_cache()

    configs = list_enabled_provider_configs(db_session, settings)
    assert [c.provider_name for c in configs] == ["groq", "deepseek"]
    assert configs[0].api_key == "gsk_groq_secret_aaaa"
    assert configs[1].base_url == "https://api.deepseek.com"


def test_get_llm_gateway_registers_each_enabled_provider(db_session, auth_settings: Settings) -> None:
    settings = auth_settings.model_copy(
        update={
            "settings_secret_key": "multi-provider-secret",
            "llm_openai_base_url": "https://api.openai.com",
            "llm_openai_api_key": "sk-env-openai",
            "llm_default_provider": "openai",
            "ollama_base_url": "http://127.0.0.1:11434",
        }
    )
    db_session.add(
        LlmProvider(
            id=uuid.uuid4(),
            name="groq",
            display_name="Groq",
            base_url="https://api.groq.com/openai",
            encrypted_api_key=encrypt_secret("gsk_groq_secret_aaaa", settings),
            key_last4="aaaa",
            enabled=True,
        )
    )
    db_session.add(
        LlmProvider(
            id=uuid.uuid4(),
            name="deepseek",
            display_name="DeepSeek",
            base_url="https://api.deepseek.com",
            encrypted_api_key=encrypt_secret("sk-deepseek-bbbb", settings),
            key_last4="bbbb",
            enabled=True,
        )
    )
    db_session.add(
        LlmRouting(
            default_provider="groq",
            default_model="llama-3.1-8b-instant",
            planner_provider="groq",
            planner_model="llama-3.1-8b-instant",
            synthesizer_provider="deepseek",
            synthesizer_model="deepseek-chat",
            reviewer_provider="groq",
            reviewer_model="llama-3.1-8b-instant",
            writer_provider="openai",
            writer_model="gpt-4o-mini",
        )
    )
    db_session.commit()

    class _SessionProxy:
        """Avoid closing the shared pytest session when gateway teardown runs."""

        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name: str):
            return getattr(self._inner, name)

        def close(self) -> None:
            return None

    clear_settings_cache()
    get_llm_gateway.cache_clear()
    get_workflow_model_profile.cache_clear()
    get_ollama_client.cache_clear()

    with (
        patch("app.core.deps.get_settings", return_value=settings),
        patch(
            "app.db.session.get_session_factory",
            return_value=lambda: _SessionProxy(db_session),
        ),
    ):
        gateway = get_llm_gateway()
        profile = get_workflow_model_profile()

    assert set(gateway._adapters) >= {"ollama", "groq", "deepseek", "openai"}
    groq = gateway._adapters["groq"]
    deepseek = gateway._adapters["deepseek"]
    openai = gateway._adapters["openai"]
    assert isinstance(groq, OpenAICompatibleLLMAdapter)
    assert isinstance(deepseek, OpenAICompatibleLLMAdapter)
    assert isinstance(openai, OpenAICompatibleLLMAdapter)
    assert groq is not deepseek
    assert groq._base_url == "https://api.groq.com/openai"
    assert deepseek._base_url == "https://api.deepseek.com"
    assert openai._base_url == "https://api.openai.com"
    assert groq._api_key == "gsk_groq_secret_aaaa"
    assert deepseek._api_key == "sk-deepseek-bbbb"
    assert gateway._default_provider == "groq"
    assert profile.planner.provider == "groq"
    assert profile.synthesizer.provider == "deepseek"
    assert profile.writer.provider == "openai"

    get_llm_gateway.cache_clear()
    get_workflow_model_profile.cache_clear()
    get_ollama_client.cache_clear()
    clear_settings_cache()
