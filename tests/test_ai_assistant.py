import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from fastapi import status
from httpx import AsyncClient

from app.core.config import settings
from app.features.authentication.schemas import SignupRequest
from app.features.authentication.service import auth_service
from app.features.workspaces_and_channels.schemas import CreateWorkspaceRequest, CreateChannelRequest
from app.features.workspaces_and_channels.service import workspace_service
from app.features.messaging.schemas import CreateMessageRequest
from app.features.messaging.service import message_service


@pytest.mark.asyncio
async def test_AC_06_01_chat_with_grounded_citations(client: AsyncClient, db_session, fake_redis):
    # Setup user & workspace
    owner = await auth_service.signup(db_session, SignupRequest(email="alice_ai@demo.com", name="Alice", password="password123"))
    ws = await workspace_service.create_workspace(db_session, CreateWorkspaceRequest(name="AI Workspace"), owner.user.id)
    channels = await workspace_service.list_workspace_channels(db_session, ws.id)
    general_ch = channels[0]

    # Add message
    msg = await message_service.create_message(
        db_session, fake_redis, general_ch.id, owner.user.id, CreateMessageRequest(body="Launch date is October 14", parent_id=None)
    )

    token = owner.access_token

    # Mock Runner.run response
    mock_run_result = AsyncMock()
    mock_run_result.final_output = f"The launch date is October 14 based on message {msg.id}."

    with patch("app.features.ai_assistant.service.is_ai_enabled", return_value=True), \
         patch("agents.Runner.run", return_value=mock_run_result):

        resp = await client.post(
            "/assistant/chat",
            json={
                "workspace_id": str(ws.id),
                "session_id": "session-123",
                "message": "When is the launch date?",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "October 14" in data["content"]
        assert data["session_id"] == "session-123"

        # Check history endpoint
        hist_resp = await client.get(
            f"/assistant/history?workspace_id={ws.id}&session_id=session-123",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert hist_resp.status_code == status.HTTP_200_OK
        hist_data = hist_resp.json()
        assert len(hist_data) >= 1


@pytest.mark.asyncio
async def test_AC_06_02_channel_summarization(client: AsyncClient, db_session, fake_redis):
    owner = await auth_service.signup(db_session, SignupRequest(email="sum_owner@demo.com", name="Owner", password="password123"))
    ws = await workspace_service.create_workspace(db_session, CreateWorkspaceRequest(name="Sum Workspace"), owner.user.id)
    channels = await workspace_service.list_workspace_channels(db_session, ws.id)
    ch = channels[0]

    await message_service.create_message(db_session, fake_redis, ch.id, owner.user.id, CreateMessageRequest(body="Refund fix is ready", parent_id=None))

    mock_run_result = AsyncMock()
    mock_run_result.final_output = AsyncMock(
        summary="Refund fix discussion",
        key_points=["Refund fix is ready"],
        decisions=["Ship on Oct 14"],
        open_questions=["Who writes notes?"],
    )

    with patch("app.features.ai_assistant.service.is_ai_enabled", return_value=True), \
         patch("agents.Runner.run", return_value=mock_run_result):

        resp = await client.post(
            "/assistant/summarize",
            json={"channel_id": str(ch.id), "since_hours": 24},
            headers={"Authorization": f"Bearer {owner.access_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "message_count" in data
        assert data["message_count"] >= 1


@pytest.mark.asyncio
async def test_AC_06_03_draft_reply(client: AsyncClient, db_session, fake_redis):
    owner = await auth_service.signup(db_session, SignupRequest(email="draft_user@demo.com", name="User", password="password123"))
    ws = await workspace_service.create_workspace(db_session, CreateWorkspaceRequest(name="Draft Workspace"), owner.user.id)
    channels = await workspace_service.list_workspace_channels(db_session, ws.id)
    ch = channels[0]

    msg = await message_service.create_message(
        db_session, fake_redis, ch.id, owner.user.id, CreateMessageRequest(body="Can someone check the checkout bug?", parent_id=None)
    )

    mock_run_result = AsyncMock()
    mock_run_result.final_output = "I can take a look at the checkout bug right now."

    with patch("app.features.ai_assistant.service.is_ai_enabled", return_value=True), \
         patch("agents.Runner.run", return_value=mock_run_result):

        resp = await client.post(
            "/assistant/draft-reply",
            json={"message_id": str(msg.id)},
            headers={"Authorization": f"Bearer {owner.access_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "draft" in data
        assert "checkout bug" in data["draft"]


@pytest.mark.asyncio
async def test_AC_06_04_semantic_search_with_keyword_fallback(client: AsyncClient, db_session, fake_redis):
    owner = await auth_service.signup(db_session, SignupRequest(email="search_user@demo.com", name="Searcher", password="password123"))
    ws = await workspace_service.create_workspace(db_session, CreateWorkspaceRequest(name="Search Workspace"), owner.user.id)
    channels = await workspace_service.list_workspace_channels(db_session, ws.id)
    ch = channels[0]

    await message_service.create_message(
        db_session, fake_redis, ch.id, owner.user.id, CreateMessageRequest(body="Critical payment refund bug found", parent_id=None)
    )

    # Test keyword fallback when AI embedding is disabled / returns None
    with patch("app.features.ai_assistant.service.is_ai_enabled", return_value=False):
        resp = await client.get(
            f"/search?workspace_id={ws.id}&q=refund",
            headers={"Authorization": f"Bearer {owner.access_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data) >= 1
        assert "payment refund" in data[0]["body"]
        assert data[0]["is_semantic"] is False


@pytest.mark.asyncio
async def test_AC_06_05_unjoined_channel_hostile_prompt_security_boundary(client: AsyncClient, db_session, fake_redis):
    # Alice owns workspace with #general and #leadership channels
    alice = await auth_service.signup(db_session, SignupRequest(email="alice_lead@demo.com", name="Alice", password="password123"))
    ws = await workspace_service.create_workspace(db_session, CreateWorkspaceRequest(name="Secure Workspace"), alice.user.id)

    leadership_ch = await workspace_service.create_channel(
        db_session, ws.id, CreateChannelRequest(name="leadership", description="Private discussion"), alice.user.id
    )
    await message_service.create_message(
        db_session, fake_redis, leadership_ch.id, alice.user.id, CreateMessageRequest(body="marketing budget cut to $12k", parent_id=None)
    )

    # Sara joins workspace but is NOT a member of #leadership
    sara = await auth_service.signup(db_session, SignupRequest(email="sara_guest@demo.com", name="Sara", password="password123"))
    # Add Sara to workspace
    from app.features.workspaces_and_channels.repository import workspace_repository
    await workspace_repository.add_workspace_member(db_session, ws.id, sara.user.id)

    # Sara attempts hostile prompt asking about #leadership budget
    resp = await client.get(
        f"/search?workspace_id={ws.id}&q=marketing%20budget",
        headers={"Authorization": f"Bearer {sara.access_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    # Sara must NOT see messages from #leadership
    assert len(data) == 0


@pytest.mark.asyncio
async def test_AC_06_06_disabled_ai_state(client: AsyncClient, db_session, fake_redis):
    owner = await auth_service.signup(db_session, SignupRequest(email="dis_user@demo.com", name="DisabledTest", password="password123"))
    ws = await workspace_service.create_workspace(db_session, CreateWorkspaceRequest(name="Disabled Workspace"), owner.user.id)

    with patch("app.features.ai_assistant.service.is_ai_enabled", return_value=False):
        resp = await client.post(
            "/assistant/chat",
            json={"workspace_id": str(ws.id), "session_id": "s1", "message": "hello"},
            headers={"Authorization": f"Bearer {owner.access_token}"},
        )
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert resp.json()["code"] == "ai_disabled"
