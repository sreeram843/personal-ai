from app.services.sentiment_routing import detect_sentiment, tone_instruction_for_sentiment
from app.services.prompt_context import augment_system_prompt
from app.core.config import Settings


def test_detect_sentiment_frustrated():
    assert detect_sentiment("This is broken again!!!") == "frustrated"


def test_detect_sentiment_urgent():
    assert detect_sentiment("Need this ASAP for production outage") == "urgent"


def test_tone_instruction_for_frustrated():
    text = tone_instruction_for_sentiment("frustrated")
    assert "frustrated" in text.lower()


def test_augment_system_prompt_adds_tone():
    settings = Settings(enable_sentiment_tone=True, enable_user_memory=False)
    prompt = augment_system_prompt(
        "Base prompt",
        user_query="This is broken",
        user_id="u1",
        settings=settings,
        user_memory_store=None,
    )
    assert "Base prompt" in prompt
    assert "Tone guidance" in prompt
