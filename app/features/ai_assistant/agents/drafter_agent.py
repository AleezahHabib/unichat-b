from pathlib import Path
from agents import Agent

from app.features.ai_assistant.agents.context import AssistantContext
from app.features.ai_assistant.agents.model_provider import get_chat_model

instructions_path = Path(__file__).parent / "instructions" / "drafter.md"
drafter_instructions = instructions_path.read_text(encoding="utf-8")


def create_drafter_agent() -> Agent[AssistantContext]:
    return Agent[AssistantContext](
        name="FistaChat Drafter Agent",
        model=get_chat_model(),
        instructions=drafter_instructions,
    )
