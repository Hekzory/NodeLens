"""Integration tests against a real Postgres (testcontainers).

Drives the REAL FastAPI app, so requests flow through the actual middleware
stack (ETag, Origin/CSRF check, sessions) and router wiring — not a hand-built
mini-app. Run in the same pytest session as the unit tests; auto-skipped when
Docker is unavailable (see container fixtures in conftest.py).
"""

import uuid
from datetime import UTC, datetime

import httpx
import pytest

import nodelens.workers.ingestor.writer as writer_module
from nodelens.api.app import app
from nodelens.api.deps import get_db
from nodelens.auth.dependencies import get_current_user
from nodelens.db.models import Device, Plugin, Sensor, TelemetryRecord
from nodelens.schemas.events import TelemetryEvent

pytestmark = pytest.mark.integration


def _bypass_auth():
    """Override the auth dependency for protected routers under test."""
    return object()


@pytest.fixture
async def client(db_sessionmaker):
    """httpx client against the real app; DB + auth dependencies overridden."""

    async def _get_db():
        async with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _bypass_auth
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def test_dashboard_create_then_list(client):
    """POST then GET flows through the real app → SQLAlchemy → Postgres."""
    created = await client.post(
        "/api/dashboards", json={"name": "Greenhouse", "description": "env"}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Greenhouse"
    assert body["widget_count"] == 0

    listed = await client.get("/api/dashboards")
    assert listed.status_code == 200
    assert body["id"] in {d["id"] for d in listed.json()}


async def test_etag_middleware_returns_304(client):
    """ETagMiddleware serves a 304 when the client echoes back the ETag."""
    first = await client.get("/api/health")
    assert first.status_code == 200
    etag = first.headers["etag"]

    cached = await client.get("/api/health", headers={"If-None-Match": etag})
    assert cached.status_code == 304


async def test_origin_check_middleware_rejects_foreign_origin(client):
    """OriginCheckMiddleware blocks a state-changing request from a foreign origin."""
    resp = await client.post(
        "/api/dashboards",
        json={"name": "x"},
        headers={"Origin": "http://evil.invalid"},
    )
    assert resp.status_code == 403


async def test_ingestor_writer_persists_telemetry(db_sessionmaker, monkeypatch):
    """write_batch validates against and inserts into a real DB, updating last_seen."""
    plugin_id, device_id, sensor_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with db_sessionmaker() as session, session.begin():
        session.add(
            Plugin(
                id=plugin_id,
                plugin_type="device",
                module_name=f"m-{plugin_id}",
                display_name="M",
                is_active=True,
            )
        )
        session.add(Device(id=device_id, plugin_id=plugin_id, external_id="ext", name="Dev"))
        session.add(Sensor(id=sensor_id, device_id=device_id, key="temp", name="Temp"))

    # Point the writer's module-level sessionmaker at the container DB
    # (mirrors the existing unit test in test_ingestor_writer_db.py).
    monkeypatch.setattr(writer_module, "async_session", db_sessionmaker)

    ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    written = await writer_module.write_batch(
        [TelemetryEvent(device_id=str(device_id), sensor_id=str(sensor_id), value=21.5, timestamp=ts)]
    )
    assert written == 1

    async with db_sessionmaker() as session:
        row = await session.get(TelemetryRecord, (ts, sensor_id))
        assert row is not None
        assert row.value_numeric == 21.5
        device = await session.get(Device, device_id)
        assert device.last_seen == ts
