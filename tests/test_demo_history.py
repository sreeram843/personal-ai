"""Tests for demo chat history shaping."""

from app.api.demo_routes import _demo_chat_history, _is_demo_intro_message
from app.core.config import Settings
from app.schemas.chat import ChatMessage
from app.schemas.demo import DemoChatRequest
from app.services.demo_live_teaser import default_demo_intro


def test_is_demo_intro_message_matches_default_intro():
    intro = default_demo_intro(5)
    assert _is_demo_intro_message(intro, intro) is True
    assert _is_demo_intro_message("What teams do you play for?", intro) is False
    assert _is_demo_intro_message("Try CurieAI — custom override text", intro) is True


def test_is_demo_intro_message_rejects_unrelated():
    intro = default_demo_intro(5)
    assert _is_demo_intro_message("Ask about cricket stats", intro) is False


def test_demo_chat_history_skips_intro_and_limits_turns():
    settings = Settings(demo_enabled=True, demo_max_history_messages=4, demo_intro="")
    intro = default_demo_intro(settings.demo_max_questions)
    body = DemoChatRequest(
        session_id="demo-session-1",
        message="Third question",
        messages=[
            ChatMessage(role="assistant", content=intro),
            ChatMessage(role="user", content="First"),
            ChatMessage(role="assistant", content="Answer one"),
            ChatMessage(role="user", content="Second"),
            ChatMessage(role="assistant", content="Answer two"),
            ChatMessage(role="user", content="Third question"),
        ],
    )
    history = _demo_chat_history(body, settings)
    assert history[0] == {"role": "assistant", "content": "Answer one"}
    assert history[-1] == {"role": "user", "content": "Third question"}
    assert len(history) == 4
    assert not any(item["content"] == intro for item in history)


def test_demo_chat_history_uses_custom_intro_setting():
    settings = Settings(
        demo_enabled=True,
        demo_max_history_messages=6,
        demo_intro="Ask me anything about the portfolio.",
    )
    body = DemoChatRequest(
        session_id="demo-session-custom",
        message="Hi",
        messages=[
            ChatMessage(role="assistant", content="Ask me anything about the portfolio."),
            ChatMessage(role="user", content="Hi"),
        ],
    )
    history = _demo_chat_history(body, settings)
    assert history == [{"role": "user", "content": "Hi"}]
