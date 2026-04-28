"""Unit tests for /api/users admin endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

from nodelens.api.deps import get_db
from nodelens.api.routes.users import router as users_router
from nodelens.auth.dependencies import get_current_user
from nodelens.auth.security import hash_password
from tests.conftest import make_execute_result, make_mock_db

_app = FastAPI()
_app.include_router(users_router)


def _make_user(username: str = "admin", *, is_active: bool = True):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.username = username
    user.password_hash = hash_password("dummy-old-password")
    user.is_active = is_active
    user.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    user.last_login_at = None
    return user


@pytest.fixture
def current_user():
    return _make_user(username="me")


@pytest.fixture
def mock_db():
    return make_mock_db()


@pytest.fixture
async def client(mock_db, current_user):
    _app.dependency_overrides[get_db] = lambda: mock_db
    _app.dependency_overrides[get_current_user] = lambda: current_user
    transport = httpx.ASGITransport(app=_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    _app.dependency_overrides.clear()


class TestListUsers:
    async def test_returns_users(self, client, mock_db):
        users = [_make_user("alice"), _make_user("bob")]
        mock_db.execute = AsyncMock(return_value=make_execute_result(scalars_all=users))

        resp = await client.get("/api/users")
        assert resp.status_code == 200
        assert {u["username"] for u in resp.json()} == {"alice", "bob"}


class TestCreateUser:
    async def test_creates_user(self, client, mock_db):
        resp = await client.post(
            "/api/users",
            json={"username": "alice", "password": "alice-pass-1"},
        )
        assert resp.status_code == 201
        assert resp.json()["username"] == "alice"

    async def test_duplicate_username_returns_409(self, client, mock_db):
        mock_db.commit = AsyncMock(
            side_effect=IntegrityError("dup", params=None, orig=Exception())
        )

        resp = await client.post(
            "/api/users",
            json={"username": "alice", "password": "alice-pass-1"},
        )
        assert resp.status_code == 409


class TestUpdateUser:
    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.patch(
            f"/api/users/{uuid.uuid4()}", json={"is_active": False}
        )
        assert resp.status_code == 404

    async def test_rename_user(self, client, mock_db):
        target = _make_user("oldname")
        mock_db.get = AsyncMock(return_value=target)

        resp = await client.patch(
            f"/api/users/{target.id}", json={"username": "newname"}
        )
        assert resp.status_code == 200
        assert target.username == "newname"

    async def test_cannot_deactivate_self(self, client, mock_db, current_user):
        mock_db.get = AsyncMock(return_value=current_user)

        resp = await client.patch(
            f"/api/users/{current_user.id}", json={"is_active": False}
        )
        assert resp.status_code == 400

    async def test_cannot_deactivate_last_active_user(self, client, mock_db):
        target = _make_user("solo")
        mock_db.get = AsyncMock(return_value=target)
        # _active_count returns 1
        mock_db.execute = AsyncMock(return_value=make_execute_result())
        mock_db.execute.return_value.scalar.return_value = 1

        resp = await client.patch(
            f"/api/users/{target.id}", json={"is_active": False}
        )
        assert resp.status_code == 400


class TestDeleteUser:
    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.delete(f"/api/users/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_cannot_delete_self(self, client, mock_db, current_user):
        mock_db.get = AsyncMock(return_value=current_user)

        resp = await client.delete(f"/api/users/{current_user.id}")
        assert resp.status_code == 400
        assert "logged in" in resp.json()["detail"].lower()

    async def test_cannot_delete_last_active_user(self, client, mock_db):
        target = _make_user("solo")
        mock_db.get = AsyncMock(return_value=target)
        result = make_execute_result()
        result.scalar.return_value = 1
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.delete(f"/api/users/{target.id}")
        assert resp.status_code == 400

    async def test_deletes_other_user(self, client, mock_db):
        target = _make_user("victim")
        mock_db.get = AsyncMock(return_value=target)
        result = make_execute_result()
        result.scalar.return_value = 5  # plenty of active users
        mock_db.execute = AsyncMock(return_value=result)

        resp = await client.delete(f"/api/users/{target.id}")
        assert resp.status_code == 204
        mock_db.delete.assert_awaited_once_with(target)


class TestAdminPasswordReset:
    async def test_not_found_returns_404(self, client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await client.post(
            f"/api/users/{uuid.uuid4()}/password",
            json={"new_password": "newpass456"},
        )
        assert resp.status_code == 404

    async def test_resets_hash(self, client, mock_db):
        target = _make_user("victim")
        old_hash = target.password_hash
        mock_db.get = AsyncMock(return_value=target)

        resp = await client.post(
            f"/api/users/{target.id}/password",
            json={"new_password": "newpass456"},
        )
        assert resp.status_code == 204
        assert target.password_hash != old_hash
