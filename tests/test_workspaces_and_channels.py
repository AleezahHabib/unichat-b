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
async def test_AC_02_01_create_workspace_auto_provisions_general_and_owner_membership(client: AsyncClient):
    user, token = await create_user_and_login(client, "WS Creator", "creator@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/workspaces",
        json={"name": "Acme Corp"},
        headers=headers,
    )
    assert resp.status_code == 201
    ws = resp.json()
    assert ws["name"] == "Acme Corp"
    assert ws["owner_id"] == user["id"]

    # Verify #general channel was created
    ch_resp = await client.get(f"/workspaces/{ws['id']}/channels", headers=headers)
    assert ch_resp.status_code == 200
    channels = ch_resp.json()
    assert len(channels) == 1
    assert channels[0]["name"] == "general"


@pytest.mark.asyncio
async def test_AC_02_02_list_workspaces_and_members(client: AsyncClient):
    user, token = await create_user_and_login(client, "Member User", "member@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    ws1 = (await client.post("/workspaces", json={"name": "Workspace 1"}, headers=headers)).json()
    ws2 = (await client.post("/workspaces", json={"name": "Workspace 2"}, headers=headers)).json()

    list_resp = await client.get("/workspaces", headers=headers)
    assert list_resp.status_code == 200
    ws_list = list_resp.json()
    ws_ids = [w["id"] for w in ws_list]
    assert ws1["id"] in ws_ids
    assert ws2["id"] in ws_ids

    # Check members endpoint
    m_resp = await client.get(f"/workspaces/{ws1['id']}/members", headers=headers)
    assert m_resp.status_code == 200
    members = m_resp.json()
    assert len(members) == 1
    assert members[0]["email"] == user["email"]
    assert members[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_AC_02_03_workspace_invites_owner_only_and_accept(client: AsyncClient):
    owner, owner_token = await create_user_and_login(client, "Inviter", "inviter@example.com")
    member, member_token = await create_user_and_login(client, "Invitee", "invitee@example.com")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    member_h = {"Authorization": f"Bearer {member_token}"}

    ws = (await client.post("/workspaces", json={"name": "Invite WS"}, headers=owner_h)).json()

    # Non-owner try to create invite -> 403
    non_owner_inv = await client.post(f"/workspaces/{ws['id']}/invites", headers=member_h)
    assert non_owner_inv.status_code == 403

    # Owner creates invite -> 201
    inv_resp = await client.post(f"/workspaces/{ws['id']}/invites", headers=owner_h)
    assert inv_resp.status_code == 201
    inv = inv_resp.json()
    token = inv["token"]

    # Preview invite unauthenticated
    prev_resp = await client.get(f"/invites/{token}")
    assert prev_resp.status_code == 200
    assert prev_resp.json()["workspace_name"] == "Invite WS"

    # Accept invite -> 200
    acc_resp = await client.post(f"/invites/{token}/accept", headers=member_h)
    assert acc_resp.status_code == 200
    assert acc_resp.json()["workspace_id"] == ws["id"]

    # Re-accepting (idempotent)
    reacc_resp = await client.post(f"/invites/{token}/accept", headers=member_h)
    assert reacc_resp.status_code == 200


@pytest.mark.asyncio
async def test_AC_02_04_create_channel_name_normalization_and_uniqueness(client: AsyncClient):
    owner, token = await create_user_and_login(client, "Channel Owner", "chowner@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    ws = (await client.post("/workspaces", json={"name": "Channel WS"}, headers=headers)).json()

    # Create channel with uppercase/spaces -> normalized to kebab-case
    ch_resp = await client.post(
        f"/workspaces/{ws['id']}/channels",
        json={"name": "  Project Alpha! ", "description": "Alpha team"},
        headers=headers,
    )
    assert ch_resp.status_code == 201
    ch = ch_resp.json()
    assert ch["name"] == "project-alpha"

    # Duplicate channel name -> 409
    dup_resp = await client.post(
        f"/workspaces/{ws['id']}/channels",
        json={"name": "PROJECT alpha"},
        headers=headers,
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["code"] == "channel_exists"


@pytest.mark.asyncio
async def test_AC_02_05_join_leave_channel_rules(client: AsyncClient):
    owner, owner_token = await create_user_and_login(client, "Joiner 1", "j1@example.com")
    member, member_token = await create_user_and_login(client, "Joiner 2", "j2@example.com")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    member_h = {"Authorization": f"Bearer {member_token}"}

    ws = (await client.post("/workspaces", json={"name": "JL WS"}, headers=owner_h)).json()

    # Add member to workspace
    inv = (await client.post(f"/workspaces/{ws['id']}/invites", headers=owner_h)).json()
    await client.post(f"/invites/{inv['token']}/accept", headers=member_h)

    # Owner creates custom channel
    ch = (
        await client.post(
            f"/workspaces/{ws['id']}/channels",
            json={"name": "random"},
            headers=owner_h,
        )
    ).json()

    # Member joins custom channel
    join_resp = await client.post(f"/channels/{ch['id']}/join", headers=member_h)
    assert join_resp.status_code == 200

    # Member leaves custom channel
    leave_resp = await client.post(f"/channels/{ch['id']}/leave", headers=member_h)
    assert leave_resp.status_code == 200

    # Get general channel id
    channels = (await client.get(f"/workspaces/{ws['id']}/channels", headers=owner_h)).json()
    gen_ch = next(c for c in channels if c["name"] == "general")

    # Member attempt to leave #general -> 400 cannot_leave_general
    gen_leave_resp = await client.post(f"/channels/{gen_ch['id']}/leave", headers=member_h)
    assert gen_leave_resp.status_code == 400
    assert gen_leave_resp.json()["code"] == "cannot_leave_general"


@pytest.mark.asyncio
async def test_AC_02_03_invite_joins_as_member_not_owner(client: AsyncClient):
    owner, owner_token = await create_user_and_login(client, "Team Owner", "teamowner@example.com")
    invitee, invitee_token = await create_user_and_login(client, "New Teammate", "teammate@example.com")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    invitee_h = {"Authorization": f"Bearer {invitee_token}"}

    ws = (await client.post("/workspaces", json={"name": "Role Test WS"}, headers=owner_h)).json()

    # Owner generates invite
    inv = (await client.post(f"/workspaces/{ws['id']}/invites", headers=owner_h)).json()

    # Invitee accepts invite
    acc_resp = await client.post(f"/invites/{inv['token']}/accept", headers=invitee_h)
    assert acc_resp.status_code == 200

    # List members and verify roles
    members_resp = await client.get(f"/workspaces/{ws['id']}/members", headers=invitee_h)
    assert members_resp.status_code == 200
    members = members_resp.json()
    assert len(members) == 2

    owner_entry = next(m for m in members if m["email"] == owner["email"])
    invitee_entry = next(m for m in members if m["email"] == invitee["email"])

    assert owner_entry["role"] == "owner"
    assert invitee_entry["role"] == "member"


@pytest.mark.asyncio
async def test_AC_02_06_delete_workspace_owner_only(client: AsyncClient):
    owner, owner_token = await create_user_and_login(client, "Delete Owner", "delowner@example.com")
    member, member_token = await create_user_and_login(client, "Delete Member", "delmember@example.com")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    member_h = {"Authorization": f"Bearer {member_token}"}

    ws = (await client.post("/workspaces", json={"name": "To Delete WS"}, headers=owner_h)).json()
    ws_id = ws["id"]

    # Member joins
    inv = (await client.post(f"/workspaces/{ws_id}/invites", headers=owner_h)).json()
    await client.post(f"/invites/{inv['token']}/accept", headers=member_h)

    # Non-owner tries to delete workspace -> 403 forbidden
    non_owner_del = await client.delete(f"/workspaces/{ws_id}", headers=member_h)
    assert non_owner_del.status_code == 403
    assert non_owner_del.json()["code"] == "forbidden"

    # Non-existent workspace -> 404
    fake_id = "00000000-0000-0000-0000-000000000000"
    not_found_del = await client.delete(f"/workspaces/{fake_id}", headers=owner_h)
    assert not_found_del.status_code == 404

    # Owner deletes workspace -> 200 ok
    owner_del = await client.delete(f"/workspaces/{ws_id}", headers=owner_h)
    assert owner_del.status_code == 200
    assert owner_del.json()["status"] == "ok"

    # Workspace is no longer in user's workspaces
    ws_list_resp = await client.get("/workspaces", headers=owner_h)
    assert ws_list_resp.status_code == 200
    ws_ids = [w["id"] for w in ws_list_resp.json()]
    assert ws_id not in ws_ids


@pytest.mark.asyncio
async def test_AC_02_07_leave_workspace_non_owner(client: AsyncClient):
    owner, owner_token = await create_user_and_login(client, "Leave Owner", "lowner@example.com")
    member, member_token = await create_user_and_login(client, "Leave Member", "lmember@example.com")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    member_h = {"Authorization": f"Bearer {member_token}"}

    ws = (await client.post("/workspaces", json={"name": "Leave Test WS"}, headers=owner_h)).json()
    ws_id = ws["id"]

    # Member joins workspace
    inv = (await client.post(f"/workspaces/{ws_id}/invites", headers=owner_h)).json()
    await client.post(f"/invites/{inv['token']}/accept", headers=member_h)

    # Owner creates channel and member joins it
    ch = (await client.post(f"/workspaces/{ws_id}/channels", json={"name": "leave-chat"}, headers=owner_h)).json()
    await client.post(f"/channels/{ch['id']}/join", headers=member_h)

    # Owner attempts to leave -> 403 owner_cannot_leave
    owner_leave = await client.post(f"/workspaces/{ws_id}/leave", headers=owner_h)
    assert owner_leave.status_code == 403
    assert owner_leave.json()["code"] == "owner_cannot_leave"

    # Member leaves workspace -> 200
    member_leave = await client.post(f"/workspaces/{ws_id}/leave", headers=member_h)
    assert member_leave.status_code == 200
    assert member_leave.json()["message"] == "Successfully left workspace"

    # Member is no longer in workspace members list
    members_resp = await client.get(f"/workspaces/{ws_id}/members", headers=owner_h)
    assert members_resp.status_code == 200
    member_ids = [m["user_id"] for m in members_resp.json()]
    assert member["id"] not in member_ids

    # Member can no longer access channel in that workspace -> 403
    ch_access = await client.get(f"/channels/{ch['id']}/messages", headers=member_h)
    assert ch_access.status_code == 403


@pytest.mark.asyncio
async def test_AC_02_08_remove_member_owner_only(client: AsyncClient):
    owner, owner_token = await create_user_and_login(client, "Rem Owner", "remowner@example.com")
    member1, member1_token = await create_user_and_login(client, "Rem Member 1", "rem1@example.com")
    member2, member2_token = await create_user_and_login(client, "Rem Member 2", "rem2@example.com")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    m1_h = {"Authorization": f"Bearer {member1_token}"}
    m2_h = {"Authorization": f"Bearer {member2_token}"}

    ws = (await client.post("/workspaces", json={"name": "Remove Member WS"}, headers=owner_h)).json()
    ws_id = ws["id"]

    # Members join
    inv = (await client.post(f"/workspaces/{ws_id}/invites", headers=owner_h)).json()
    await client.post(f"/invites/{inv['token']}/accept", headers=m1_h)
    await client.post(f"/invites/{inv['token']}/accept", headers=m2_h)

    # Non-owner tries to remove another member -> 403 forbidden
    non_owner_rem = await client.delete(f"/workspaces/{ws_id}/members/{member2['id']}", headers=m1_h)
    assert non_owner_rem.status_code == 403
    assert non_owner_rem.json()["code"] == "forbidden"

    # Owner tries to remove themselves -> 400 cannot_remove_owner
    self_rem = await client.delete(f"/workspaces/{ws_id}/members/{owner['id']}", headers=owner_h)
    assert self_rem.status_code == 400
    assert self_rem.json()["code"] == "cannot_remove_owner"

    # Owner removes member 1 -> 200
    rem_resp = await client.delete(f"/workspaces/{ws_id}/members/{member1['id']}", headers=owner_h)
    assert rem_resp.status_code == 200
    assert rem_resp.json()["message"] == "Member removed successfully"

    # Verify member 1 is gone from members list
    members_resp = await client.get(f"/workspaces/{ws_id}/members", headers=owner_h)
    assert members_resp.status_code == 200
    member_ids = [m["user_id"] for m in members_resp.json()]
    assert member1["id"] not in member_ids
    assert member2["id"] in member_ids

    # Removing non-member -> 404
    rem_again = await client.delete(f"/workspaces/{ws_id}/members/{member1['id']}", headers=owner_h)
    assert rem_again.status_code == 404
    assert rem_again.json()["code"] == "member_not_found"


@pytest.mark.asyncio
async def test_AC_02_09_list_workspace_channels_joined_only_filter(client: AsyncClient):
    owner, owner_token = await create_user_and_login(client, "Filter Owner", "fowner@example.com")
    member, member_token = await create_user_and_login(client, "Filter Member", "fmember@example.com")

    owner_h = {"Authorization": f"Bearer {owner_token}"}
    member_h = {"Authorization": f"Bearer {member_token}"}

    ws = (await client.post("/workspaces", json={"name": "Filter WS"}, headers=owner_h)).json()
    ws_id = ws["id"]

    # Member joins workspace (auto-enrolled in #general)
    inv = (await client.post(f"/workspaces/{ws_id}/invites", headers=owner_h)).json()
    await client.post(f"/invites/{inv['token']}/accept", headers=member_h)

    # Owner creates two more channels: #custom-joined, #custom-unjoined
    ch_joined = (await client.post(f"/workspaces/{ws_id}/channels", json={"name": "custom-joined"}, headers=owner_h)).json()
    ch_unjoined = (await client.post(f"/workspaces/{ws_id}/channels", json={"name": "custom-unjoined"}, headers=owner_h)).json()

    # Member joins only custom-joined
    await client.post(f"/channels/{ch_joined['id']}/join", headers=member_h)

    # List all channels for member -> should see 3 (#general, #custom-joined, #custom-unjoined)
    all_channels_resp = await client.get(f"/workspaces/{ws_id}/channels", headers=member_h)
    assert all_channels_resp.status_code == 200
    all_names = [c["name"] for c in all_channels_resp.json()]
    assert "general" in all_names
    assert "custom-joined" in all_names
    assert "custom-unjoined" in all_names

    # List joined-only channels for member -> should see 2 (#general, #custom-joined), NOT #custom-unjoined
    joined_channels_resp = await client.get(f"/workspaces/{ws_id}/channels?joined_only=true", headers=member_h)
    assert joined_channels_resp.status_code == 200
    joined_names = [c["name"] for c in joined_channels_resp.json()]
    assert "general" in joined_names
    assert "custom-joined" in joined_names
    assert "custom-unjoined" not in joined_names
