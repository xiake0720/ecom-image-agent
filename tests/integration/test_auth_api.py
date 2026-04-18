from __future__ import annotations

import importlib

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.core.config import reset_settings_cache
from backend.db.base import Base
from backend.db.models.audit import AuditLog
from backend.db.session import dispose_async_engine, get_async_engine, get_async_session_factory


@pytest_asyncio.fixture
async def auth_client(tmp_path, monkeypatch):
    db_path = tmp_path / "auth-test.sqlite3"
    monkeypatch.setenv("ECOM_DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("ECOM_AUTH_JWT_SECRET_KEY", "test-jwt-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ECOM_AUTH_TOKEN_HASH_SECRET", "test-token-hash-secret-with-at-least-thirty-two-bytes")
    monkeypatch.setenv("ECOM_AUTH_REFRESH_COOKIE_SECURE", "false")
    monkeypatch.setenv("ECOM_CORS_ORIGINS", '["http://testserver"]')

    reset_settings_cache()
    await dispose_async_engine()

    engine = get_async_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    import backend.main as backend_main

    backend_main = importlib.reload(backend_main)
    transport = ASGITransport(app=backend_main.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await dispose_async_engine()
    reset_settings_cache()


@pytest.mark.asyncio
async def test_auth_endpoints_full_flow(auth_client: AsyncClient) -> None:
    register_response = await auth_client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "StrongPass123", "nickname": "测试用户"},
    )
    assert register_response.status_code == 200
    register_body = register_response.json()
    assert register_body["code"] == 0
    assert register_body["data"]["user"]["email"] == "user@example.com"
    assert "access_token" in register_body["data"]

    me_response = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {register_body['data']['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["data"]["nickname"] == "测试用户"

    login_response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    login_body = login_response.json()
    assert login_body["data"]["user"]["email"] == "user@example.com"

    refresh_response = await auth_client.post("/api/v1/auth/refresh")
    assert refresh_response.status_code == 200
    refresh_body = refresh_response.json()
    assert refresh_body["data"]["token_type"] == "bearer"

    logout_response = await auth_client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["data"]["logged_out"] is True

    refresh_after_logout = await auth_client.post("/api/v1/auth/refresh")
    assert refresh_after_logout.status_code == 401

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(AuditLog.action).order_by(AuditLog.created_at.asc()))
        actions = list(result.scalars().all())
    assert set(actions) == {"auth.register", "auth.login", "auth.logout"}
    assert len(actions) == 3


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "AnotherStrong123"},
    )

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == 4011
