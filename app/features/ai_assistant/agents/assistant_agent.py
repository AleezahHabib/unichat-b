from pathlib import Path
from agents import Agent

from app.features.ai_assistant.agents.context import AssistantContext
from app.features.ai_assistant.agents.guardrails import (
    citation_guardrail,
    scope_and_injection_guardrail,
)
from app.features.ai_assistant.agents.model_provider import get_chat_model
from app.features.ai_assistant.agents.tools import (
    get_channel_history,
    get_thread,
    list_channels,
    search_messages,
)

instructions_path = Path(__file__).parent / "instructions" / "assistant.md"
assistant_instructions = instructions_path.read_text(encoding="utf-8")


def create_assistant_agent() -> Agent[AssistantContext]:
    return Agent[AssistantContext](
        name="FistaChat Assistant",
        model=get_chat_model(),
        instructions=assistant_instructions,
        tools=[list_channels, get_channel_history, search_messages, get_thread],
        input_guardrails=[scope_and_injection_guardrail],
        output_guardrails=[citation_guardrail],
    )
