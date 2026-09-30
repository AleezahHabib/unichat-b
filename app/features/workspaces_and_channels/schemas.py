from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime
    member_count: int = 1

    model_config = {"from_attributes": True}


class WorkspaceMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    email: str
    avatar_color: str
    role: str
    joined_at: datetime
    online: bool = False

    model_config = {"from_attributes": True}


class CreateInviteResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    token: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InvitePreviewResponse(BaseModel):
    workspace_name: str
    inviter_name: str
    expires_at: datetime
    is_expired: bool


class AcceptInviteResponse(BaseModel):
    workspace_id: UUID


class CreateChannelRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = None


class ChannelResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None = None
    created_by: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChannelMemberResponse(BaseModel):
    user_id: UUID
    name: str
    email: str
    avatar_color: str
    joined_at: datetime
