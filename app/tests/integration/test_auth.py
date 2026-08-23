from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def register_user(client: AsyncClient) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "guest@example.com", "password": "strong-password"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.usefixtures("clean_users")
async def test_register_user(client: AsyncClient) -> None:
    user = await register_user(client)

    assert user["email"] == "guest@example.com"
    assert user["id"] > 0
    assert "created_at" in user
    assert "hashed_password" not in user


@pytest.mark.usefixtures("clean_users")
async def test_duplicate_email_is_rejected(client: AsyncClient) -> None:
    await register_user(client)

    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "guest@example.com", "password": "strong-password"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "A user with this email already exists"}


@pytest.mark.usefixtures("clean_users")
async def test_bearer_token_authenticates_user(client: AsyncClient) -> None:
    user = await register_user(client)

    token_response = await client.post(
        "/api/v1/auth/token",
        data={"username": "guest@example.com", "password": "strong-password"},
    )
    assert token_response.status_code == 200
    access_token = token_response.json()["access_token"]
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert token_response.json()["token_type"] == "bearer"
    assert me_response.status_code == 200
    assert me_response.json()["id"] == user["id"]
    assert me_response.json()["email"] == user["email"]


@pytest.mark.usefixtures("clean_users")
async def test_invalid_password_is_rejected(client: AsyncClient) -> None:
    await register_user(client)

    response = await client.post(
        "/api/v1/auth/token",
        data={"username": "guest@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Invalid authentication credentials"}


async def test_me_requires_bearer_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
