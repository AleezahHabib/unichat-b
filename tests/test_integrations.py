from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from app.features.integrations.echo_guard import echo_guard


import uuid

async def create_user_and_login(client: AsyncClient, name: str, email: str | None = None) -> tuple[dict, str]:
    user_email = email or f"{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}@example.com"
    if "@" in name and not email:
        user_email = name
    elif email:
        user_email = f"{email.split('@')[0]}_{uuid.uuid4().hex[:6]}@{email.split('@')[1]}"
    resp = await client.post(
        "/auth/signup",
        json={"name": name, "email": user_email, "password": "Password123!"},
    )
    data = resp.json()
    return data["user"], data["access_token"]


@pytest.mark.asyncio
async def test_AC_05_01_connect_slack_and_discord_owner_only(client: AsyncClient):
    owner, owner_token = await create_user_and_login(client, "Int Owner", "io@example.com")
    member, member_token = await create_user_and_login(client, "Int Member", "im@example.com")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    member_h = {"Authorization": f"Bearer {member_token}"}

    ws = (await client.post("/workspaces", json={"name": "Int WS"}, headers=owner_h)).json()

    with patch("app.features.integrations.service.SlackAdapter") as mock_slack:
        mock_slack.return_value.validate_credentials = AsyncMock(
            return_value={"bot_id": "B12345", "display_name": "Test Slack App"}
        )

        # Non-owner attempt -> 403
        no_owner_res = await client.post(
            "/integrations/slack/connect",
            json={"workspace_id": ws["id"], "bot_token": "xoxb-fake", "app_token": "xapp-fake"},
            headers=member_h,
        )
        assert no_owner_res.status_code == 403

        # Owner connect -> 201
        conn_res = await client.post(
            "/integrations/slack/connect",
            json={"workspace_id": ws["id"], "bot_token": "xoxb-fake", "app_token": "xapp-fake"},
            headers=owner_h,
        )
        assert conn_res.status_code == 201
        data = conn_res.json()
        assert data["platform"] == "slack"
        assert "encrypted_tokens" not in data  # Tokens never returned

    # List integrations
    list_res = await client.get(f"/integrations?workspace_id={ws['id']}", headers=owner_h)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


@pytest.mark.asyncio
async def test_AC_05_02_external_channel_discovery_and_linking(client: AsyncClient):
    owner, token = await create_user_and_login(client, "Link Owner", "lo@example.com")
    h = {"Authorization": f"Bearer {token}"}
    ws = (await client.post("/workspaces", json={"name": "Link WS"}, headers=h)).json()
    ch = (await client.get(f"/workspaces/{ws['id']}/channels", headers=h)).json()[0]

    with patch("app.features.integrations.service.SlackAdapter") as mock_slack:
        mock_slack.return_value.validate_credentials = AsyncMock(
            return_value={"bot_id": "B123", "display_name": "Slack App"}
        )
        mock_slack.return_value.list_channels = AsyncMock(
            return_value=[{"id": "C123", "name": "general-slack"}]
        )
        mock_slack.return_value.join_channel = AsyncMock()

        cp = (
            await client.post(
                "/integrations/slack/connect",
                json={"workspace_id": ws["id"], "bot_token": "xoxb-1", "app_token": "xapp-1"},
                headers=h,
            )
        ).json()

        # List external channels
        ext_res = await client.get(f"/integrations/{cp['id']}/external-channels", headers=h)
        assert ext_res.status_code == 200
        assert ext_res.json()[0]["name"] == "general-slack"

        # Link channel
        link_res = await client.post(
            f"/channels/{ch['id']}/link",
            json={
                "platform_id": cp["id"],
                "external_channel_id": "C123",
                "external_channel_name": "general-slack",
            },
            headers=h,
        )
        assert link_res.status_code == 201
        assert link_res.json()["platform"] == "slack"


@pytest.mark.asyncio
async def test_AC_05_05_echo_guard_layer1_identity_filter():
    assert echo_guard.is_identity_echo("BOT_123", own_bot_id="BOT_123") is True
    assert echo_guard.is_identity_echo("USER_456", own_bot_id="BOT_123") is False
    assert echo_guard.is_identity_echo("WH_789", own_bot_id=None, webhook_id="WH_789", own_webhook_id="WH_789") is True


@pytest.mark.asyncio
async def test_AC_05_05_echo_guard_layer2_db_unique_constraint(client: AsyncClient, fake_redis, db_session):
    from app.features.integrations.repository import integration_repository
    from app.features.workspaces_and_channels.repository import workspace_repository

    user, token = await create_user_and_login(client, "DB Guard", "dbg@example.com")
    ws = await workspace_repository.create_workspace(db_session, "DB Guard WS", user["id"])
    ch = (await workspace_repository.list_workspace_channels(db_session, ws.id))[0]

    # First insert -> succeeds
    msg1 = await integration_repository.save_external_message(
        db_session,
        channel_id=ch.id,
        external_author_name="Slack User",
        body="Test message",
        source="slack",
        external_id="ext_msg_999",
        external_channel_id="ext_ch_888",
    )
    assert msg1 is not None

    # Duplicate insert -> returns None via ON CONFLICT DO NOTHING
    msg2 = await integration_repository.save_external_message(
        db_session,
        channel_id=ch.id,
        external_author_name="Slack User",
        body="Test message duplicate",
        source="slack",
        external_id="ext_msg_999",
        external_channel_id="ext_ch_888",
    )
    assert msg2 is None


@pytest.mark.asyncio
async def test_AC_05_05_echo_guard_layer3_race_window_guard(fake_redis):
    ext_id = "msg_race_123"
    assert await echo_guard.is_race_window_echo(fake_redis, ext_id) is False

    await echo_guard.set_race_window(fake_redis, ext_id)
    assert await echo_guard.is_race_window_echo(fake_redis, ext_id) is True


@pytest.mark.asyncio
async def test_AC_05_08_health_background_status(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "background" in data
    assert data["background"] in ("leader", "follower", "off")
