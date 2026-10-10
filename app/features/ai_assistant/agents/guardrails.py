import re
import logging
from typing import Any
from agents import GuardrailFunctionOutput, RunContextWrapper, input_guardrail, output_guardrail
from sqlalchemy import select

from app.features.ai_assistant.agents.context import AssistantContext
from app.features.workspaces_and_channels.models import Channel

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    r"ignore\s+(previous|all)\s+instructions",
    r"reveal\s+(system\s+prompt|instructions)",
    r"act\s+as\s+",
    r"developer\s+mode",
]


@input_guardrail
async def scope_and_injection_guardrail(
    wrapper: RunContextWrapper[AssistantContext],
    agent: Any,
    data: Any,
) -> GuardrailFunctionOutput:
    ctx = wrapper.context
    text_content = ""

    if isinstance(data, str):
        text_content = data
    elif hasattr(data, "content") and isinstance(data.content, str):
        text_content = data.content
    elif isinstance(data, list):
        text_content = " ".join(str(item) for item in data)

    lower_text = text_content.lower()

    # 1. Check prompt injection phrasing
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower_text):
            logger.warning(f"Injection pattern detected: '{pattern}' in text")
            return GuardrailFunctionOutput(
                tripwire_triggered=True,
                output_info="I can only use channels you've joined.",
            )

    # 2. Check for mentioned #channel names that exist in workspace but aren't joined
    channel_mentions = re.findall(r"#([a-zA-Z0-9_-]+)", text_content)
    if channel_mentions:
        async with ctx.session_factory() as db:
            stmt = select(Channel).where(
                Channel.workspace_id == ctx.workspace_id,
                Channel.name.in_([m.lower() for m in channel_mentions]),
            )
            mentioned_channels = (await db.execute(stmt)).scalars().all()
            for ch in mentioned_channels:
                if ch.id not in ctx.allowed_channel_ids:
                    logger.warning(
                        f"User mentioned unjoined channel #{ch.name} (id={ch.id})"
                    )
                    return GuardrailFunctionOutput(
                        tripwire_triggered=True,
                        output_info="I can only use channels you've joined.",
                    )

    return GuardrailFunctionOutput(tripwire_triggered=False, output_info=None)


@output_guardrail
async def citation_guardrail(
    wrapper: RunContextWrapper[AssistantContext],
    agent: Any,
    data: Any,
) -> GuardrailFunctionOutput:
    ctx = wrapper.context
    text_content = str(data)

    # Extract cited message IDs from output text (UUID format or XML attribute id="...")
    uuid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    cited_ids = set(re.findall(uuid_pattern, text_content))

    for c_id in cited_ids:
        try:
            from uuid import UUID
            uid = UUID(c_id)
            if uid not in ctx.seen_message_ids:
                logger.warning(f"Citation guardrail trip: message {c_id} was cited without being seen in tools")
                return GuardrailFunctionOutput(
                    tripwire_triggered=True,
                    output_info="Invalid message citation detected.",
                )
        except Exception:
            pass

    return GuardrailFunctionOutput(tripwire_triggered=False, output_info=None)
