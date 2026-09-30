import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_AC_01_01_signup_success_and_duplicate(client: AsyncClient):
    signup_payload = {
        "name": "Alice Tester",
        "email": "alice@example.com",
        "password": "Password123!",
    }

    # 1. Successful signup
    response = await client.post("/auth/signup", json=signup_payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["name"] == "Alice Tester"
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["avatar_color"].startswith("#")

    # 2. Duplicate email signup
    dup_response = await client.post("/auth/signup", json=signup_payload)
    assert dup_response.status_code == 409
    dup_data = dup_response.json()
    assert dup_data["code"] == "email_taken"


@pytest.mark.asyncio
async def test_AC_01_02_login_success_and_invalid_credentials(client: AsyncClient):
    signup_payload = {
        "name": "Bob Tester",
        "email": "bob@example.com",
        "password": "SecurePassword123",
    }
    await client.post("/auth/signup", json=signup_payload)

    # 1. Successful login
    login_response = await client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "SecurePassword123"},
    )
    assert login_response.status_code == 200
    data = login_response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "bob@example.com"

    # 2. Wrong password
    wrong_pw_resp = await client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "WrongPassword"},
    )
    assert wrong_pw_resp.status_code == 401
    assert wrong_pw_resp.json()["code"] == "invalid_credentials"

    # 3. Nonexistent user
    no_user_resp = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "SecurePassword123"},
    )
    assert no_user_resp.status_code == 401
    assert no_user_resp.json()["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_AC_01_03_get_me_profile(client: AsyncClient):
    signup_payload = {
        "name": "Charlie Tester",
        "email": "charlie@example.com",
        "password": "Password123!",
    }
    signup_resp = await client.post("/auth/signup", json=signup_payload)
    token = signup_resp.json()["access_token"]

    me_resp = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    user_data = me_resp.json()
    assert user_data["name"] == "Charlie Tester"
    assert user_data["email"] == "charlie@example.com"
    assert user_data["avatar_color"].startswith("#")


@pytest.mark.asyncio
async def test_AC_01_04_protected_routes_unauthenticated(client: AsyncClient):
    # No auth header
    no_token_resp = await client.get("/auth/me")
    assert no_token_resp.status_code == 401

    # Invalid token header
    invalid_token_resp = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.payload"},
    )
    assert invalid_token_resp.status_code == 401
