"""Unit tests for /api/auth endpoints + protected-dependency wiring."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import Depends, FastAPI
from starlette.middleware.sessions import SessionMiddleware

from nodelens.api.deps import get_db
from nodelens.api.routes.auth import router as auth_router
from nodelens.auth.dependencies import get_current_user
from nodelens.auth.security import hash_password
from tests.conftest import make_mock_db


def _make_app():
    app = FastAPI()
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key-only-for-tests",
        session_cookie="nodelens_session",
    )
    app.include_router(auth_router)
    return app


_app = _make_app()


def _make_user(username: str = "admin", password: str = "changeme123", *, is_active: bool = True):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.username = username
    user.password_hash = hash_password(password)
    user.is_active = is_active
    user.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    user.last_login_at = None
    return user


def _count_result(n: int):
    r = MagicMock()
    r.scalar.return_value = n
    return r


def _scalar_one_or_none_result(value):
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


@pytest.fixture
def mock_db():
    return make_mock_db()


@pytest.fixture
async def client(mock_db):
    _app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    _app.dependency_overrides.clear()


class TestStatus:
    async def test_no_users_setup_required(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_count_result(0))

        resp = await client.get("/api/auth/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"setup_required": True, "authenticated": False, "user": None}

    async def test_users_exist_no_session(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_count_result(1))
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.get("/api/auth/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["setup_required"] is False
        assert body["authenticated"] is False
        assert body["user"] is None


class TestSetup:
    async def test_creates_first_user_and_logs_them_in(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_count_result(0))

        resp = await client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "changeme123"},
        )
        assert resp.status_code == 201
        assert resp.json()["username"] == "admin"
        # SessionMiddleware should have written the cookie
        assert "nodelens_session" in resp.headers.get("set-cookie", "").lower()

    async def test_blocks_when_users_exist(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_count_result(1))

        resp = await client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "changeme123"},
        )
        assert resp.status_code == 409

    async def test_short_password_is_rejected(self, client, mock_db):
        resp = await client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "short"},
        )
        assert resp.status_code == 422

    async def test_invalid_username_pattern_is_rejected(self, client, mock_db):
        resp = await client.post(
            "/api/auth/setup",
            json={"username": "with spaces", "password": "changeme123"},
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_unknown_user_returns_401(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))

        resp = await client.post(
            "/api/auth/login",
            json={"username": "ghost", "password": "changeme123"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

    async def test_wrong_password_returns_401(self, client, mock_db):
        user = _make_user(password="rightpass1")
        mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(user))

        resp = await client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "wrongpass1"},
        )
        assert resp.status_code == 401

    async def test_inactive_user_returns_401(self, client, mock_db):
        user = _make_user(is_active=False)
        mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(user))

        resp = await client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "changeme123"},
        )
        assert resp.status_code == 401

    async def test_correct_password_returns_user(self, client, mock_db):
        user = _make_user(password="changeme123")
        mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(user))

        resp = await client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "changeme123"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == user.username


class TestMeAndLogout:
    async def test_me_without_session_returns_401(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_login_then_me_returns_user(self, client, mock_db):
        user = _make_user(password="changeme123")
        mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(user))

        login_resp = await client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "changeme123"},
        )
        assert login_resp.status_code == 200

        # The auth dep loads the user via db.get; mock that to return the same user.
        mock_db.get = AsyncMock(return_value=user)

        me_resp = await client.get("/api/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == user.username

    async def test_logout_clears_session(self, client, mock_db):
        user = _make_user(password="changeme123")
        mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(user))
        await client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "changeme123"},
        )

        mock_db.get = AsyncMock(return_value=user)
        logout = await client.post("/api/auth/logout")
        assert logout.status_code == 204

        # After logout, the auth dep refuses (no user_id in session).
        mock_db.get = AsyncMock(return_value=None)
        me_resp = await client.get("/api/auth/me")
        assert me_resp.status_code == 401


class TestPasswordChange:
    async def test_wrong_old_returns_400(self, client, mock_db):
        user = _make_user(password="rightpass1")
        mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(user))
        await client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "rightpass1"},
        )

        mock_db.get = AsyncMock(return_value=user)
        resp = await client.post(
            "/api/auth/password",
            json={"old_password": "wrongpass1", "new_password": "newpass456"},
        )
        assert resp.status_code == 400

    async def test_correct_old_updates_hash(self, client, mock_db):
        user = _make_user(password="rightpass1")
        mock_db.execute = AsyncMock(return_value=_scalar_one_or_none_result(user))
        await client.post(
            "/api/auth/login",
            json={"username": user.username, "password": "rightpass1"},
        )

        mock_db.get = AsyncMock(return_value=user)
        old_hash = user.password_hash

        resp = await client.post(
            "/api/auth/password",
            json={"old_password": "rightpass1", "new_password": "newpass456"},
        )
        assert resp.status_code == 204
        assert user.password_hash != old_hash


class TestProtectedDependencyWiring:
    """Verify that mounting any router with `dependencies=[Depends(get_current_user)]`
    produces a 401 when no session cookie is present. Locks in app.py wiring."""

    async def test_no_cookie_returns_401(self, mock_db):
        from nodelens.api.routes.devices import router as devices_router

        app = FastAPI()
        app.add_middleware(
            SessionMiddleware,
            secret_key="test-secret",
            session_cookie="nodelens_session",
        )
        app.include_router(devices_router, dependencies=[Depends(get_current_user)])
        app.dependency_overrides[get_db] = lambda: mock_db

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/devices")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Not authenticated"
