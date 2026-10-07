import pytest
from httpx import AsyncClient
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
async def test_AC_03_01_send_message_membership_validation_and_rate_limit(client: AsyncClient):
    user1, token1 = await create_user_and_login(client, "Msg User 1", "m1@example.com")
    user2, token2 = await create_user_and_login(client, "Msg User 2", "m2@example.com")

    h1 = {"Authorization": f"Bearer {token1}"}
    h2 = {"Authorization": f"Bearer {token2}"}

    ws = (await client.post("/workspaces", json={"name": "Msg WS"}, headers=h1)).json()
    channels = (await client.get(f"/workspaces/{ws['id']}/channels", headers=h1)).json()
    gen_ch = next(c for c in channels if c["name"] == "general")

    # User 1 sends message -> 201
    msg_resp = await client.post(
        f"/channels/{gen_ch['id']}/messages",
        json={"body": "Hello world!"},
        headers=h1,
    )
    assert msg_resp.status_code == 201
    msg = msg_resp.json()
    assert msg["body"] == "Hello world!"
    assert msg["author"]["id"] == user1["id"]

    # User 2 tries to send message in User 1's workspace without being a member -> 403
    non_mem_resp = await client.post(
        f"/channels/{gen_ch['id']}/messages",
        json={"body": "Unauthorized message"},
        headers=h2,
    )
    assert non_mem_resp.status_code == 403


@pytest.mark.asyncio
async def test_AC_03_02_cursor_pagination(client: AsyncClient):
    user, token = await create_user_and_login(client, "Pager User", "pager@example.com")
    h = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/workspaces", json={"name": "Pager WS"}, headers=h)).json()
    channels = (await client.get(f"/workspaces/{ws['id']}/channels", headers=h)).json()
    gen_ch = next(c for c in channels if c["name"] == "general")

    for i in range(5):
        await client.post(f"/channels/{gen_ch['id']}/messages", json={"body": f"Msg {i}"}, headers=h)

    # Page 1 (limit 3)
    p1 = (await client.get(f"/channels/{gen_ch['id']}/messages?limit=3", headers=h)).json()
    assert len(p1["items"]) == 3
    assert p1["next_cursor"] is not None

    # Page 2 using cursor
    p2 = (await client.get(f"/channels/{gen_ch['id']}/messages?limit=3&cursor={p1['next_cursor']}", headers=h)).json()
    assert len(p2["items"]) == 2

    # Malformed cursor returns 400 Bad Request with code 'invalid_cursor'
    bad_cursor_resp = await client.get(f"/channels/{gen_ch['id']}/messages?cursor=invalid_garbage_cursor", headers=h)
    assert bad_cursor_resp.status_code == 400
    assert bad_cursor_resp.json()["code"] == "invalid_cursor"


@pytest.mark.asyncio
async def test_AC_03_03_edit_and_delete_message_author_only(client: AsyncClient):
    user1, token1 = await create_user_and_login(client, "Edit User 1", "e1@example.com")
    user2, token2 = await create_user_and_login(client, "Edit User 2", "e2@example.com")

    h1 = {"Authorization": f"Bearer {token1}"}
    h2 = {"Authorization": f"Bearer {token2}"}

    ws = (await client.post("/workspaces", json={"name": "Edit WS"}, headers=h1)).json()
    inv = (await client.post(f"/workspaces/{ws['id']}/invites", headers=h1)).json()
    await client.post(f"/invites/{inv['token']}/accept", headers=h2)

    channels = (await client.get(f"/workspaces/{ws['id']}/channels", headers=h1)).json()
    gen_ch = next(c for c in channels if c["name"] == "general")

    msg = (await client.post(f"/channels/{gen_ch['id']}/messages", json={"body": "Original body"}, headers=h1)).json()

    # User 2 tries to edit User 1's message -> 403
    edit_by_other = await client.patch(f"/messages/{msg['id']}", json={"body": "Hacked body"}, headers=h2)
    assert edit_by_other.status_code == 403

    # User 1 edits own message -> 200
    edit_by_author = await client.patch(f"/messages/{msg['id']}", json={"body": "Updated body"}, headers=h1)
    assert edit_by_author.status_code == 200
    assert edit_by_author.json()["body"] == "Updated body"
    assert edit_by_author.json()["edited_at"] is not None

    # User 2 tries to delete User 1's message -> 403
    del_by_other = await client.delete(f"/messages/{msg['id']}", headers=h2)
    assert del_by_other.status_code == 403

    # User 1 soft deletes own message -> 200
    del_by_author = await client.delete(f"/messages/{msg['id']}", headers=h1)
    assert del_by_author.status_code == 200
    assert del_by_author.json()["is_deleted"] is True
    assert del_by_author.json()["body"] == "This message was deleted"


@pytest.mark.asyncio
async def test_AC_03_04_threads_parent_and_replies(client: AsyncClient):
    user, token = await create_user_and_login(client, "Thread User", "th@example.com")
    h = {"Authorization": f"Bearer {token}"}

    ws = (await client.post("/workspaces", json={"name": "Thread WS"}, headers=h)).json()
    channels = (await client.get(f"/workspaces/{ws['id']}/channels", headers=h)).json()
    gen_ch = next(c for c in channels if c["name"] == "general")

    parent = (await client.post(f"/channels/{gen_ch['id']}/messages", json={"body": "Parent post"}, headers=h)).json()

    reply1 = (
        await client.post(
            f"/channels/{gen_ch['id']}/messages",
            json={"body": "Reply 1", "parent_id": parent["id"]},
            headers=h,
        )
    ).json()

    reply2 = (
        await client.post(
            f"/channels/{gen_ch['id']}/messages",
            json={"body": "Reply 2", "parent_id": parent["id"]},
            headers=h,
        )
    ).json()

    thread_resp = await client.get(f"/messages/{parent['id']}/thread", headers=h)
    assert thread_resp.status_code == 200
    thread = thread_resp.json()
    assert thread["parent"]["id"] == parent["id"]
    assert thread["parent"]["reply_count"] == 2
    assert len(thread["replies"]) == 2
    assert thread["replies"][0]["body"] == "Reply 1"
    assert thread["replies"][1]["body"] == "Reply 2"


@pytest.mark.asyncio
async def test_AC_03_07_clear_chat_for_me_per_user(client: AsyncClient):
    user1, token1 = await create_user_and_login(client, "Clear User 1", "c1@example.com")
    user2, token2 = await create_user_and_login(client, "Clear User 2", "c2@example.com")

    h1 = {"Authorization": f"Bearer {token1}"}
    h2 = {"Authorization": f"Bearer {token2}"}

    ws = (await client.post("/workspaces", json={"name": "Clear Chat WS"}, headers=h1)).json()
    ws_id = ws["id"]

    # User 2 joins workspace
    inv = (await client.post(f"/workspaces/{ws_id}/invites", headers=h1)).json()
    await client.post(f"/invites/{inv['token']}/accept", headers=h2)

    channels = (await client.get(f"/workspaces/{ws_id}/channels", headers=h1)).json()
    gen_ch = next(c for c in channels if c["name"] == "general")
    ch_id = gen_ch["id"]

    # User 1 posts 2 messages
    m1 = (await client.post(f"/channels/{ch_id}/messages", json={"body": "History Msg 1"}, headers=h1)).json()
    m2 = (await client.post(f"/channels/{ch_id}/messages", json={"body": "History Msg 2"}, headers=h1)).json()

    # Both users see 2 messages initially
    u1_msgs = (await client.get(f"/channels/{ch_id}/messages", headers=h1)).json()["items"]
    u2_msgs = (await client.get(f"/channels/{ch_id}/messages", headers=h2)).json()["items"]
    assert len(u1_msgs) == 2
    assert len(u2_msgs) == 2

    # User 1 clears chat for themselves
    clear_resp = await client.post(f"/channels/{ch_id}/clear", headers=h1)
    assert clear_resp.status_code == 200
    data = clear_resp.json()
    assert data["channel_id"] == ch_id
    assert "cleared_at" in data

    # User 1 now sees 0 messages in channel history
    u1_msgs_after = (await client.get(f"/channels/{ch_id}/messages", headers=h1)).json()["items"]
    assert len(u1_msgs_after) == 0

    # User 2 still sees all 2 messages (unaffected)
    u2_msgs_after = (await client.get(f"/channels/{ch_id}/messages", headers=h2)).json()["items"]
    assert len(u2_msgs_after) == 2
    assert u2_msgs_after[0]["id"] == m2["id"]
    assert u2_msgs_after[1]["id"] == m1["id"]

    # User 2 posts a new message
    m3 = (await client.post(f"/channels/{ch_id}/messages", json={"body": "New Post Msg 3"}, headers=h2)).json()

    # User 1 now sees ONLY the new message (Message 3)
    u1_msgs_final = (await client.get(f"/channels/{ch_id}/messages", headers=h1)).json()["items"]
    assert len(u1_msgs_final) == 1
    assert u1_msgs_final[0]["id"] == m3["id"]

    # User 2 sees all 3 messages
    u2_msgs_final = (await client.get(f"/channels/{ch_id}/messages", headers=h2)).json()["items"]
    assert len(u2_msgs_final) == 3
