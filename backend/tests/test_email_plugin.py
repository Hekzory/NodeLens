"""Unit tests for the email integration plugin."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from nodelens.schemas.events import AlertMessage

# Load the plugin module directly from its file (it lives outside the import
# path because plugins are subprocess-loaded by the runner).
_PLUGIN_PATH = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "integrations"
    / "email"
    / "plugin.py"
)


# aiosmtplib is a plugin-level dep installed only in the plugins worker
# container. Stub it for unit tests so we don't require it in the backend env.
@pytest.fixture(autouse=True)
def stub_aiosmtplib():
    fake = SimpleNamespace(send=AsyncMock(return_value=None))
    sys.modules["aiosmtplib"] = fake
    yield fake
    sys.modules.pop("aiosmtplib", None)
    sys.modules.pop("nodelens_test_email_plugin", None)


def _load_plugin_module():
    spec = importlib.util.spec_from_file_location("nodelens_test_email_plugin", _PLUGIN_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["nodelens_test_email_plugin"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plugin(stub_aiosmtplib):
    mod = _load_plugin_module()
    return mod.EmailIntegrationPlugin()


def _msg():
    return AlertMessage(
        rule_name="hot",
        device_name="thermostat",
        triggered_value=42.5,
        message="Sensor exceeded threshold",
        triggered_at=datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC),
    )


class TestEmailSend:
    async def test_missing_to_returns_false(self, plugin):
        ok = await plugin.send({}, _msg())
        assert ok is False

    async def test_happy_path_calls_smtp_with_config(self, plugin, stub_aiosmtplib):
        cfg = {
            "to": "ops@example.com",
            "smtp_host": "mail.example.com",
            "smtp_port": 1025,
            "from": "alerts@nodelens.local",
        }
        ok = await plugin.send(cfg, _msg())
        assert ok is True
        mock_send = stub_aiosmtplib.send
        assert mock_send.await_count == 1

        kwargs = mock_send.await_args.kwargs
        assert kwargs["hostname"] == "mail.example.com"
        assert kwargs["port"] == 1025
        assert kwargs["use_tls"] is False
        assert kwargs["start_tls"] is False

        sent_msg = mock_send.await_args.args[0]
        assert sent_msg["To"] == "ops@example.com"
        assert sent_msg["From"] == "alerts@nodelens.local"
        assert "[NodeLens] hot" in sent_msg["Subject"]
        body = sent_msg.get_content()
        assert "thermostat" in body
        assert "42.5" in body

    async def test_smtp_failure_returns_false(self, plugin, stub_aiosmtplib):
        stub_aiosmtplib.send = AsyncMock(side_effect=ConnectionRefusedError())
        cfg = {"to": "ops@example.com", "smtp_host": "mail.example.com"}
        ok = await plugin.send(cfg, _msg())
        assert ok is False

    async def test_custom_subject_used(self, plugin, stub_aiosmtplib):
        cfg = {"to": "x@y.z", "smtp_host": "mail.example.com", "subject": "Custom!"}
        await plugin.send(cfg, _msg())
        assert stub_aiosmtplib.send.await_args.args[0]["Subject"] == "Custom!"

    async def test_direct_mx_resolution_when_smtp_host_empty(self, plugin, stub_aiosmtplib, monkeypatch):
        mod = sys.modules["nodelens_test_email_plugin"]

        async def fake_resolve(domain: str) -> str | None:
            assert domain == "yandex.ru"
            return "mx.yandex.ru"

        monkeypatch.setattr(mod, "_resolve_mx", fake_resolve)

        ok = await plugin.send({"to": "user@yandex.ru"}, _msg())
        assert ok is True
        kwargs = stub_aiosmtplib.send.await_args.kwargs
        assert kwargs["hostname"] == "mx.yandex.ru"
        assert kwargs["port"] == 25

    async def test_mx_lookup_failure_returns_false(self, plugin, stub_aiosmtplib, monkeypatch):
        mod = sys.modules["nodelens_test_email_plugin"]

        async def fake_resolve(domain: str) -> str | None:
            return None

        monkeypatch.setattr(mod, "_resolve_mx", fake_resolve)

        ok = await plugin.send({"to": "user@nonexistent.invalid"}, _msg())
        assert ok is False
        stub_aiosmtplib.send.assert_not_awaited()

    async def test_authenticated_tls_submission(self, plugin, stub_aiosmtplib):
        cfg = {
            "to": "me@yandex.ru",
            "smtp_host": "smtp.yandex.ru",
            "username": "me@yandex.ru",
            "password": "app-pwd-xxxx",
            "use_tls": True,
        }
        ok = await plugin.send(cfg, _msg())
        assert ok is True
        kwargs = stub_aiosmtplib.send.await_args.kwargs
        assert kwargs["hostname"] == "smtp.yandex.ru"
        assert kwargs["port"] == 465  # auto-picked from use_tls=True
        assert kwargs["use_tls"] is True
        assert kwargs["username"] == "me@yandex.ru"
        assert kwargs["password"] == "app-pwd-xxxx"

    async def test_starttls_submission_picks_port_587(self, plugin, stub_aiosmtplib):
        cfg = {
            "to": "me@gmail.com",
            "smtp_host": "smtp.gmail.com",
            "username": "me@gmail.com",
            "password": "app-pwd",
            "start_tls": True,
        }
        ok = await plugin.send(cfg, _msg())
        assert ok is True
        kwargs = stub_aiosmtplib.send.await_args.kwargs
        assert kwargs["port"] == 587
        assert kwargs["start_tls"] is True
        assert kwargs["use_tls"] is False


class TestPluginLevelDefaults:
    async def test_plugin_defaults_fill_missing_channel_keys(self, plugin, stub_aiosmtplib):
        await plugin.configure({
            "default_from": "noreply@nodelens.test",
            "smtp_host": "relay.nodelens.test",
            "smtp_port": 2525,
            "use_tls": True,
            "smtp_password": "shared-secret",
        })
        cfg = {"to": "ops@example.com", "username": "shared-user"}
        ok = await plugin.send(cfg, _msg())
        assert ok is True
        kwargs = stub_aiosmtplib.send.await_args.kwargs
        assert kwargs["hostname"] == "relay.nodelens.test"
        assert kwargs["port"] == 2525
        assert kwargs["use_tls"] is True
        assert kwargs["username"] == "shared-user"
        assert kwargs["password"] == "shared-secret"
        sent_msg = stub_aiosmtplib.send.await_args.args[0]
        assert sent_msg["From"] == "noreply@nodelens.test"

    async def test_channel_overrides_plugin_defaults(self, plugin, stub_aiosmtplib):
        await plugin.configure({
            "default_from": "noreply@nodelens.test",
            "smtp_host": "relay.nodelens.test",
            "smtp_port": 2525,
            "use_tls": True,
        })
        cfg = {
            "to": "ops@example.com",
            "smtp_host": "channel.example.com",
            "smtp_port": 1025,
            "from": "channel-from@example.com",
            "use_tls": False,
        }
        await plugin.send(cfg, _msg())
        kwargs = stub_aiosmtplib.send.await_args.kwargs
        assert kwargs["hostname"] == "channel.example.com"
        assert kwargs["port"] == 1025
        assert kwargs["use_tls"] is False
        sent_msg = stub_aiosmtplib.send.await_args.args[0]
        assert sent_msg["From"] == "channel-from@example.com"

    async def test_no_configure_keeps_legacy_behaviour(self, plugin, stub_aiosmtplib):
        # Plugin instantiated without configure() — defaults dict empty, the
        # hardcoded fallbacks must still kick in unchanged.
        cfg = {"to": "ops@example.com", "smtp_host": "mail.example.com"}
        await plugin.send(cfg, _msg())
        kwargs = stub_aiosmtplib.send.await_args.kwargs
        assert kwargs["hostname"] == "mail.example.com"
        assert kwargs["port"] == 25
        sent_msg = stub_aiosmtplib.send.await_args.args[0]
        assert sent_msg["From"] == "alerts@nodelens.local"
