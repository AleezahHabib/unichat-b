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


@pytest.mark.asyncio
async def test_AC_05_09_slack_oauth_state_mismatch_rejected(client: AsyncClient):
    # Missing or invalid state in callback -> 302 redirect with csrf_rejected error
    res = await client.get(
        "/integrations/slack/oauth/callback?code=some_code&state=nonexistent_state_12345",
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert "error=csrf_rejected" in res.headers["location"]


@pytest.mark.asyncio
async def test_AC_05_09_slack_oauth_success_exchange_faked(
    client: AsyncClient, fake_redis, db_session
):
    from urllib.parse import parse_qs, urlparse
    from app.core.config import settings
    from app.core.security import decrypt_secret
    from app.features.integrations.repository import integration_repository
    import json

    owner, token = await create_user_and_login(client, "OAuth Owner", "oauth_owner@example.com")
    h = {"Authorization": f"Bearer {token}"}
    ws = (await client.post("/workspaces", json={"name": "OAuth WS"}, headers=h)).json()

    with patch.object(settings, "SLACK_CLIENT_ID", "test_slack_client_id"), \
         patch.object(settings, "SLACK_CLIENT_SECRET", "test_slack_client_secret"), \
         patch.object(settings, "SLACK_APP_TOKEN", "xapp-test-app-token"):

        # 1. Start OAuth
        start_res = await client.get(
            f"/integrations/slack/oauth/start?workspace_id={ws['id']}",
            headers=h,
            follow_redirects=False,
        )
        assert start_res.status_code == 302
        redirect_url = start_res.headers["location"]
        assert redirect_url.startswith("https://slack.com/oauth/v2/authorize")

        parsed = urlparse(redirect_url)
        params = parse_qs(parsed.query)
        assert "state" in params
        state = params["state"][0]
        assert params["client_id"][0] == "test_slack_client_id"

        # Verify state in Redis
        raw_state = await fake_redis.get(f"unichat:oauth:slack:{state}")
        assert raw_state is not None
        assert ws["id"] in str(raw_state)

        # 2. Callback with faked Slack token exchange
        mock_slack_response = {
            "ok": True,
            "access_token": "xoxb-fake-oauth-bot-token",
            "bot_user_id": "B_OAUTH_BOT",
            "team": {
                "id": "T_OAUTH_TEAM",
                "name": "Acme Corp Slack",
            },
        }

        mock_http_response = AsyncMock()
        mock_http_response.json = lambda: mock_slack_response

        with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_http_response)):
            callback_res = await client.get(
                f"/integrations/slack/oauth/callback?code=mock_code&state={state}",
                follow_redirects=False,
            )
            assert callback_res.status_code == 302
            assert "slack=connected" in callback_res.headers["location"]

        # State should be deleted (single use)
        assert await fake_redis.get(f"unichat:oauth:slack:{state}") is None

        # Verify database record
        platform = await integration_repository.get_workspace_platform(
            db_session, uuid.UUID(ws["id"]), "slack"
        )
        assert platform is not None
        assert platform.display_name == "Acme Corp Slack"
        assert platform.bot_identity == "B_OAUTH_BOT"

        tokens = json.loads(decrypt_secret(platform.encrypted_tokens))
        assert tokens["bot_token"] == "xoxb-fake-oauth-bot-token"
        assert tokens["team_id"] == "T_OAUTH_TEAM"
        assert tokens["app_token"] == "xapp-test-app-token"


@pytest.mark.asyncio
async def test_AC_05_10_multi_workspace_team_id_routing(client: AsyncClient, fake_redis, db_session):
    import json
    from sqlalchemy import select
    from app.core.security import encrypt_secret
    from app.features.integrations.repository import integration_repository
    from app.features.workspaces_and_channels.repository import workspace_repository
    from app.background.sync_external import process_slack_event
    from app.features.messaging.models import Message
    from slack_sdk.socket_mode.request import SocketModeRequest

    # Create two workspaces
    u1, t1 = await create_user_and_login(client, "Team A User", "ta@example.com")
    u2, t2 = await create_user_and_login(client, "Team B User", "tb@example.com")

    ws_a = await workspace_repository.create_workspace(db_session, "Workspace A", u1["id"])
    ws_b = await workspace_repository.create_workspace(db_session, "Workspace B", u2["id"])

    ch_a = (await workspace_repository.list_workspace_channels(db_session, ws_a.id))[0]
    ch_b = (await workspace_repository.list_workspace_channels(db_session, ws_b.id))[0]

    # Create connected platforms for Team A and Team B
    tokens_a = encrypt_secret(json.dumps({"bot_token": "xoxb-team-a", "team_id": "T_TEAM_A"}))
    p_a = await integration_repository.create_platform(
        db_session, ws_a.id, "slack", tokens_a, bot_identity="B_TEAM_A", display_name="Team A Slack"
    )

    tokens_b = encrypt_secret(json.dumps({"bot_token": "xoxb-team-b", "team_id": "T_TEAM_B"}))
    p_b = await integration_repository.create_platform(
        db_session, ws_b.id, "slack", tokens_b, bot_identity="B_TEAM_B", display_name="Team B Slack"
    )

    # Link channels
    await integration_repository.create_channel_link(
        db_session,
        channel_id=ch_a.id,
        platform_id=p_a.id,
        platform="slack",
        external_channel_id="C_TEAM_A_GENERAL",
        external_channel_name="general-a",
    )
    await integration_repository.create_channel_link(
        db_session,
        channel_id=ch_b.id,
        platform_id=p_b.id,
        platform="slack",
        external_channel_id="C_TEAM_B_GENERAL",
        external_channel_name="general-b",
    )

    # Simulate incoming Socket Mode message for Team A
    mock_socket_client = AsyncMock()
    mock_web_client = AsyncMock()
    mock_web_client.users_info = AsyncMock(
        return_value={"user": {"name": "alice", "real_name": "Alice Smith"}}
    )

    req = SocketModeRequest(
        type="events_api",
        envelope_id="env_123",
        payload={
            "team_id": "T_TEAM_A",
            "event": {
                "type": "message",
                "user": "U_ALICE",
                "text": "Hello Team A!",
                "channel": "C_TEAM_A_GENERAL",
                "ts": "1690000000.000100",
            },
        },
    )

    with patch("app.background.sync_external.get_redis_client", return_value=fake_redis), \
         patch("app.background.sync_external.async_session", return_value=db_session), \
         patch("app.background.sync_external.enqueue_message_embedding"), \
         patch("app.background.sync_external.AsyncWebClient", return_value=mock_web_client):
        await process_slack_event(req, mock_socket_client, mock_web_client, bot_id="B_TEAM_A", platform_id=p_a.id)

    # Verify message was routed to Workspace A's channel
    stmt_a = select(Message).where(Message.channel_id == ch_a.id)
    messages_a = (await db_session.execute(stmt_a)).scalars().all()
    assert len(messages_a) == 1
    assert messages_a[0].body == "Hello Team A!"
    assert messages_a[0].source == "slack"
    assert messages_a[0].external_author_name == "Alice Smith"

    # Workspace B's channel should have 0 messages
    stmt_b = select(Message).where(Message.channel_id == ch_b.id)
    messages_b = (await db_session.execute(stmt_b)).scalars().all()
    assert len(messages_b) == 0


@pytest.mark.asyncio
async def test_AC_05_04_discord_poller_and_echo_guard(client: AsyncClient, fake_redis, db_session):
    import json
    from sqlalchemy import select
    from app.core.security import encrypt_secret
    from app.features.integrations.repository import integration_repository
    from app.features.workspaces_and_channels.repository import workspace_repository
    from app.background.sync_external import poll_discord_channels
    from app.features.messaging.models import Message

    u, t = await create_user_and_login(client, "Discord User Test", "disc_test@example.com")
    ws = await workspace_repository.create_workspace(db_session, "Discord Poll WS", u["id"])
    ch = (await workspace_repository.list_workspace_channels(db_session, ws.id))[0]

    # Create connected platform for Discord
    tokens = encrypt_secret(json.dumps({"bot_token": "disc-bot-token"}))
    p = await integration_repository.create_platform(
        db_session, ws.id, "discord", tokens, bot_identity="BOT_DISCORD_123", display_name="Test Discord Bot"
    )

    # Link channel with initial cursor
    link = await integration_repository.create_channel_link(
        db_session,
        channel_id=ch.id,
        platform_id=p.id,
        platform="discord",
        external_channel_id="CH_DISCORD_999",
        external_channel_name="test-channel",
        encrypted_webhook_url=encrypt_secret("https://discord.com/api/webhooks/WH_123/token"),
        webhook_id="WH_123",
        last_synced_external_id="100",
    )

    fake_messages = [
        # Message 1: Normal user message with member nick
        {
            "id": "101",
            "content": "Hello from Discord member!",
            "author": {"id": "USER_555", "username": "user555", "global_name": "Global 555"},
            "member": {"nick": "Nick 555"},
        },
        # Message 2: Own webhook echo -> should be ignored by Layer 1
        {
            "id": "102",
            "content": "Echo from webhook",
            "author": {"id": "BOT_SOME", "username": "UniChat Relay", "bot": True},
            "webhook_id": "WH_123",
        },
        # Message 3: Message with global name only
        {
            "id": "103",
            "content": "Second real message",
            "author": {"id": "USER_777", "username": "user777", "global_name": "Global 777"},
        },
    ]

    mock_adapter = AsyncMock()
    mock_adapter.fetch_messages_after = AsyncMock(return_value=fake_messages)

    with patch("app.background.sync_external.get_redis_client", return_value=fake_redis), \
         patch("app.background.sync_external.async_session", return_value=db_session), \
         patch("app.background.sync_external.enqueue_message_embedding"), \
         patch("app.background.sync_external.DiscordAdapter", return_value=mock_adapter):
        await poll_discord_channels()

    # Verify messages in UniChat database
    stmt = select(Message).where(Message.channel_id == ch.id).order_by(Message.external_id)
    saved = (await db_session.execute(stmt)).scalars().all()
    assert len(saved) == 2
    assert saved[0].body == "Hello from Discord member!"
    assert saved[0].external_author_name == "Nick 555"
    assert saved[0].source == "discord"
    assert saved[0].external_id == "101"

    assert saved[1].body == "Second real message"
    assert saved[1].external_author_name == "Global 777"
    assert saved[1].source == "discord"
    assert saved[1].external_id == "103"

    # Verify link cursor advanced to 103
    fresh_link = await integration_repository.get_link_by_external_channel(db_session, "discord", "CH_DISCORD_999")
    assert fresh_link.last_synced_external_id == "103"


@pytest.mark.asyncio
async def test_AC_05_06_dynamic_byline_suffixes():
    from app.features.integrations.adapters.slack_adapter import SlackAdapter
    from app.features.integrations.adapters.discord_adapter import DiscordAdapter

    slack = SlackAdapter("xoxb-fake")
    slack.client = AsyncMock()
    slack.client.chat_postMessage = AsyncMock(return_value={"ts": "12345.67"})

    # 1. Native message to Slack -> (via FistaChat)
    await slack.send_message(
        external_channel_id="C123",
        author_name="Alice",
        body="Hello from native UniChat",
        source="unichat",
    )
    assert slack.client.chat_postMessage.call_args[1]["username"] == "Alice (via FistaChat)"

    # 2. Discord message relayed to Slack -> (via Discord)
    await slack.send_message(
        external_channel_id="C123",
        author_name="Marco",
        body="Hello from Discord",
        source="discord",
    )
    assert slack.client.chat_postMessage.call_args[1]["username"] == "Marco (via Discord)"

    # 3. Slack message relayed to Slack (edge) -> (via Slack)
    await slack.send_message(
        external_channel_id="C123",
        author_name="Priya",
        body="Hello from Slack",
        source="slack",
    )
    assert slack.client.chat_postMessage.call_args[1]["username"] == "Priya (via Slack)"

    # Discord Adapter tests
    discord = DiscordAdapter("fake-bot-token")
    mock_post = AsyncMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json = lambda: {"id": "msg_999"}

    with patch("httpx.AsyncClient.post", mock_post):
        # 1. Native message to Discord -> (via FistaChat)
        await discord.send_message(
            external_channel_id="CH_DISC",
            author_name="Alice",
            body="Hello from native UniChat",
            webhook_url="https://discord.com/api/webhooks/1/abc",
            source="unichat",
        )
        assert mock_post.call_args[1]["json"]["username"] == "Alice (via FistaChat)"

        # 2. Slack message relayed to Discord -> (via Slack)
        await discord.send_message(
            external_channel_id="CH_DISC",
            author_name="Priya",
            body="Hello from Slack",
            webhook_url="https://discord.com/api/webhooks/1/abc",
            source="slack",
        )
        assert mock_post.call_args[1]["json"]["username"] == "Priya (via Slack)"

        # 3. Discord message relayed to Discord -> (via Discord)
        await discord.send_message(
            external_channel_id="CH_DISC",
            author_name="Marco",
            body="Hello from Discord",
            webhook_url="https://discord.com/api/webhooks/1/abc",
            source="discord",
        )
        assert mock_post.call_args[1]["json"]["username"] == "Marco (via Discord)"


@pytest.mark.asyncio
async def test_AC_05_06_relay_outbound_cross_platform(fake_redis, db_session):
    from app.features.integrations.service import integration_service
    from app.features.messaging.models import Message
    from app.features.workspaces_and_channels.models import Workspace, Channel
    from app.features.authentication.models import User
    from app.features.integrations.models import ConnectedPlatform, ChannelLink
    from app.core.security import encrypt_secret
    import json

    # Set up DB records
    user = User(email=f"u_{uuid.uuid4().hex[:6]}@example.com", name="Alice", password_hash="hash", avatar_color="#6366f1")
    db_session.add(user)
    await db_session.flush()

    ws = Workspace(name="Test WS", owner_id=user.id)
    db_session.add(ws)
    await db_session.flush()

    ch = Channel(workspace_id=ws.id, name="both-linked", created_by=user.id)
    db_session.add(ch)
    await db_session.flush()

    slack_cp = ConnectedPlatform(
        workspace_id=ws.id,
        platform="slack",
        encrypted_tokens=encrypt_secret(json.dumps({"bot_token": "xoxb-fake"})),
        bot_identity="B_SLACK",
        display_name="Slack WS",
    )
    discord_cp = ConnectedPlatform(
        workspace_id=ws.id,
        platform="discord",
        encrypted_tokens=encrypt_secret(json.dumps({"bot_token": "disc-fake"})),
        bot_identity="B_DISCORD",
        display_name="Discord Server",
    )
    db_session.add_all([slack_cp, discord_cp])
    await db_session.flush()

    slack_link = ChannelLink(
        channel_id=ch.id,
        platform_id=slack_cp.id,
        platform="slack",
        external_channel_id="C_SLACK_123",
        external_channel_name="general-slack",
    )
    discord_link = ChannelLink(
        channel_id=ch.id,
        platform_id=discord_cp.id,
        platform="discord",
        external_channel_id="C_DISCORD_456",
        external_channel_name="general-discord",
        encrypted_webhook_url=encrypt_secret("https://discord.com/api/webhooks/fake"),
        webhook_id="WH_FAKE",
    )
    db_session.add_all([slack_link, discord_link])
    await db_session.commit()

    # Discord-originated message relayed to Slack
    discord_msg = Message(
        channel_id=ch.id,
        author_id=None,
        external_author_name="Marco",
        body="Hello from Discord",
        source="discord",
        external_id="disc_101",
        external_channel_id="C_DISCORD_456",
    )
    db_session.add(discord_msg)
    await db_session.commit()

    with patch("app.features.integrations.service.SlackAdapter") as mock_slack_cls, \
         patch("app.features.integrations.service.DiscordAdapter") as mock_disc_cls:

        mock_slack = AsyncMock()
        mock_slack.send_message = AsyncMock(return_value="ts_123")
        mock_slack_cls.return_value = mock_slack

        mock_disc = AsyncMock()
        mock_disc.send_message = AsyncMock(return_value="disc_out_123")
        mock_disc_cls.return_value = mock_disc

        await integration_service.relay_outbound(
            db=db_session,
            redis=fake_redis,
            message=discord_msg,
            author_name="Marco",
        )

        # Must relay to Slack with source="discord"
        mock_slack.send_message.assert_awaited_once_with(
            external_channel_id="C_SLACK_123",
            author_name="Marco",
            body="Hello from Discord",
            thread_ts=None,
            source="discord",
        )
        # Must NOT relay back to Discord
        mock_disc.send_message.assert_not_called()



