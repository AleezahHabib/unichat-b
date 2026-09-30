import asyncio
import httpx

BASE_URL = "http://127.0.0.1:8000"


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        print("1. Checking server health...", flush=True)
        r = await client.get("/health")
        print("   Health response:", r.json(), flush=True)

        print("\n2. Signing up Alice (alice_e2e@example.com)...", flush=True)
        r = await client.post(
            "/auth/signup",
            json={"name": "Alice", "email": "alice_e2e@example.com", "password": "Password123!"},
        )
        if r.status_code == 409:
            print("   Alice already exists, logging in...", flush=True)
            r = await client.post(
                "/auth/login",
                json={"email": "alice_e2e@example.com", "password": "Password123!"},
            )
        alice_data = r.json()
        alice_token = alice_data["access_token"]
        alice_headers = {"Authorization": f"Bearer {alice_token}"}
        print("   Alice Token obtained.", flush=True)

        print("\n3. Creating workspace 'E2E Demo Workspace'...", flush=True)
        r = await client.post(
            "/workspaces",
            json={"name": "E2E Demo Workspace"},
            headers=alice_headers,
        )
        if r.status_code == 201:
            ws = r.json()
        else:
            r_ws = await client.get("/workspaces", headers=alice_headers)
            ws = next(w for w in r_ws.json() if w["name"] == "E2E Demo Workspace")
        ws_id = ws["id"]
        print(f"   Workspace created ID: {ws_id}", flush=True)

        print("\n4. Getting #general channel...", flush=True)
        r_ch = await client.get(f"/workspaces/{ws_id}/channels", headers=alice_headers)
        channels = r_ch.json()
        gen_ch = next(c for c in channels if c["name"] == "general")
        gen_id = gen_ch["id"]
        print(f"   #general Channel ID: {gen_id}", flush=True)

        print("\n5. Generating Workspace Invite Link...", flush=True)
        r_inv = await client.post(f"/workspaces/{ws_id}/invites", headers=alice_headers)
        inv = r_inv.json()
        inv_token = inv["token"]
        print(f"   Invite Token: {inv_token}", flush=True)
        print(f"   Invite URL: http://localhost:3000/invite/{inv_token}", flush=True)

        print("\n6. Signing up Bob (bob_e2e@example.com)...", flush=True)
        r = await client.post(
            "/auth/signup",
            json={"name": "Bob", "email": "bob_e2e@example.com", "password": "Password123!"},
        )
        if r.status_code == 409:
            r = await client.post(
                "/auth/login",
                json={"email": "bob_e2e@example.com", "password": "Password123!"},
            )
        bob_token = r.json()["access_token"]
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        print("\n7. Bob accepting workspace invite...", flush=True)
        await client.post(f"/invites/{inv_token}/accept", headers=bob_headers)
        print("   Bob joined 'E2E Demo Workspace'.", flush=True)

        print("\n8. Seeding 65 messages for cursor pagination test...", flush=True)
        for i in range(1, 66):
            await client.post(
                f"/channels/{gen_id}/messages",
                json={"body": f"Pagination Test Message #{i:02d}"},
                headers=alice_headers,
            )
            if i % 15 == 0 or i == 65:
                print(f"   Seeded {i}/65 messages...", flush=True)

        print("\n9. Testing REST pagination fetch...", flush=True)
        r_p1 = await client.get(f"/channels/{gen_id}/messages?limit=50", headers=alice_headers)
        p1 = r_p1.json()
        print(f"   Page 1 items returned: {len(p1['items'])} (Expected 50)", flush=True)
        print(f"   Page 1 next_cursor: {p1['next_cursor']}", flush=True)

        r_p2 = await client.get(
            f"/channels/{gen_id}/messages?limit=50&cursor={p1['next_cursor']}",
            headers=alice_headers,
        )
        p2 = r_p2.json()
        print(f"   Page 2 items returned: {len(p2['items'])} (Expected 15+)", flush=True)

        print("\n=======================================================", flush=True)
        print("SEEDING COMPLETE!", flush=True)
        print("=======================================================", flush=True)
        print("Demo Accounts:", flush=True)
        print("  User A (Alice): alice_e2e@example.com / Password123!", flush=True)
        print("  User B (Bob):   bob_e2e@example.com   / Password123!", flush=True)
        print(f"  Workspace URL:  http://localhost:3000/workspace/{ws_id}/channel/{gen_id}", flush=True)
        print(f"  Invite URL:     http://localhost:3000/invite/{inv_token}", flush=True)
        print("=======================================================", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
