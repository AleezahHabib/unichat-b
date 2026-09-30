from pathlib import Path
from pydantic import BaseModel, Field
from agents import Agent

from app.features.ai_assistant.agents.context import AssistantContext
from app.features.ai_assistant.agents.model_provider import get_chat_model

instructions_path = Path(__file__).parent / "instructions" / "summarizer.md"
summarizer_instructions = instructions_path.read_text(encoding="utf-8")


class SummaryOutput(BaseModel):
    key_points: list[str] = Field(default_factory=list, description="Key discussion points and highlights")
    decisions: list[str] = Field(default_factory=list, description="Decisions made by team members")
    open_questions: list[str] = Field(default_factory=list, description="Unresolved questions or action items")


def create_summarizer_agent() -> Agent[AssistantContext]:
    return Agent[AssistantContext](
        name="UniChat Summarizer",
        model=get_chat_model(),
        instructions=summarizer_instructions,
        output_type=SummaryOutput,
    )
