from pathlib import Path
from pydantic import BaseModel, Field
from agents import Agent

from app.features.ai_assistant.agents.context import AssistantContext
from app.features.ai_assistant.agents.model_provider import get_chat_model

instructions_path = Path(__file__).parent / "instructions" / "qa.md"
qa_instructions = instructions_path.read_text(encoding="utf-8")


class AnswerOutput(BaseModel):
    answer: str = Field(description="Answer grounded in retrieved messages")
    citation_ids: list[str] = Field(default_factory=list, description="List of message UUIDs cited in the answer")


def create_qa_agent() -> Agent[AssistantContext]:
    return Agent[AssistantContext](
        name="FistaChat QA Agent",
        model=get_chat_model(),
        instructions=qa_instructions,
        output_type=AnswerOutput,
    )
