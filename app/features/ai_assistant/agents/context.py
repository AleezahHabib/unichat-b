from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class AssistantContext:
    user_id: UUID
    workspace_id: UUID
    allowed_channel_ids: set[UUID]
    session_factory: Any
    seen_message_ids: set[UUID] = field(default_factory=set)
