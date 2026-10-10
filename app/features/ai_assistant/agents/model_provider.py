import pydantic.type_adapter
from agents import OpenAIChatCompletionsModel, set_tracing_disabled
from openai import AsyncOpenAI

from app.core.config import settings

# Disable telemetry / tracing
set_tracing_disabled(True)

# Patch Pydantic TypeAdapter.validate_json to safely ignore experimental_allow_partial argument from openai-agents
_orig_validate_json = pydantic.type_adapter.TypeAdapter.validate_json


def _safe_validate_json(self, *args, **kwargs):
    kwargs.pop("experimental_allow_partial", None)
    return _orig_validate_json(self, *args, **kwargs)


pydantic.type_adapter.TypeAdapter.validate_json = _safe_validate_json


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
