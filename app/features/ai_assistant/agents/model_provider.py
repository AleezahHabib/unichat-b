from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from openai import AsyncOpenAI

from app.core.config import settings

# Disable telemetry / tracing
set_tracing_disabled(True)


def get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.GEMINI_API_KEY or "dummy-key",
        base_url=settings.GEMINI_BASE_URL,
    )


def get_chat_model() -> OpenAIChatCompletionsModel:
    client = get_openai_client()
    return OpenAIChatCompletionsModel(
        model=settings.CHAT_MODEL,
        openai_client=client,
    )
