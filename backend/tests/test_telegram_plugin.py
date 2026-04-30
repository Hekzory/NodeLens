"""Unit tests for the Telegram integration plugin."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from nodelens.schemas.events import AlertMessage

# Plugin source lives outside the import path (subprocess-loaded by the
# runner). Load it directly from disk like test_email_plugin.py does.
_PLUGIN_PATH = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "integrations"
    / "telegram"
    / "plugin.py"
)


class _StubResponse:
    """Mimics httpx.Response surface used by the plugin."""

    def __init__(self, status_code: int = 200, json_data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {"ok": True, "result": {"message_id": 1}}
        self.text = text or ""

    def json(self) -> dict:
        return self._json


class _StubClient:
    """Async-context-manager that records POST/GET calls and returns canned responses."""

    def __init__(self) -> None:
        self.post = AsyncMock(return_value=_StubResponse())
        self.get = AsyncMock(return_value=_StubResponse(json_data={"ok": True, "result": []}))

    async def __aenter__(self) -> _StubClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None


@pytest.fixture(autouse=True)
def stub_httpx():
    """Replace the ``httpx`` module so the plugin can import it without the real dep."""

    stub_client = _StubClient()

    class _StubAsyncClient:
        """A class-style stub so each ``async with httpx.AsyncClient(...)`` returns the same recorder."""

        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self) -> _StubClient:
            return stub_client

        async def __aexit__(self, *exc: Any) -> None:
            return None

    fake = SimpleNamespace(
        AsyncClient=_StubAsyncClient,
        HTTPError=type("HTTPError", (Exception,), {}),
        TimeoutException=type("TimeoutException", (Exception,), {}),
        Response=_StubResponse,
    )
    # Make TimeoutException a subclass of HTTPError so plugin's `except HTTPError` catches both.
    fake.TimeoutException = type("TimeoutException", (fake.HTTPError,), {})
    sys.modules["httpx"] = fake
    # Expose the recorder on the fake module so tests can assert against it
    # and rewire the canned responses.
    fake._client = stub_client
    yield fake
    sys.modules.pop("httpx", None)
    sys.modules.pop("nodelens_test_telegram_plugin", None)


def _load_plugin_module():
    spec = importlib.util.spec_from_file_location("nodelens_test_telegram_plugin", _PLUGIN_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["nodelens_test_telegram_plugin"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def plugin_module(stub_httpx):
    return _load_plugin_module()


@pytest.fixture
def plugin(plugin_module):
    return plugin_module.TelegramIntegrationPlugin()


def _msg(rule_name: str = "hot", message: str = "Sensor exceeded threshold") -> AlertMessage:
    return AlertMessage(
        rule_name=rule_name,
        device_name="thermostat",
        triggered_value=42.5,
        message=message,
        triggered_at=datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------


class TestTelegramSend:
    async def test_missing_chat_id_returns_false(self, plugin, stub_httpx):
        ok = await plugin.send({}, _msg())
        assert ok is False
        stub_httpx._client.post.assert_not_awaited()

    async def test_empty_chat_id_returns_false(self, plugin, stub_httpx):
        ok = await plugin.send({"chat_id": "   "}, _msg())
        assert ok is False
        stub_httpx._client.post.assert_not_awaited()

    async def test_missing_token_returns_false(self, plugin, stub_httpx):
        # No plugin-level token, no channel token → cannot deliver.
        ok = await plugin.send({"chat_id": "12345"}, _msg())
        assert ok is False
        stub_httpx._client.post.assert_not_awaited()

    async def test_happy_path_posts_correct_url_and_body(self, plugin, stub_httpx):
        cfg = {"chat_id": "12345", "bot_token": "tkn-123"}
        ok = await plugin.send(cfg, _msg())
        assert ok is True
        stub_httpx._client.post.assert_awaited_once()
        url, kwargs = stub_httpx._client.post.await_args.args, stub_httpx._client.post.await_args.kwargs
        assert url[0] == "https://api.telegram.org/bottkn-123/sendMessage"
        body = kwargs["json"]
        assert body["chat_id"] == "12345"
        assert "NodeLens Alert: hot" in body["text"]
        assert "thermostat" in body["text"]
        # Plain text default → no parse_mode field in payload.
        assert "parse_mode" not in body
        assert "disable_notification" not in body
        assert "message_thread_id" not in body

    async def test_http_error_returns_false(self, plugin, stub_httpx):
        stub_httpx._client.post = AsyncMock(
            return_value=_StubResponse(status_code=401, text='{"ok":false,"description":"Unauthorized"}')
        )
        ok = await plugin.send({"chat_id": "12345", "bot_token": "bad"}, _msg())
        assert ok is False

    async def test_ok_false_body_returns_false(self, plugin, stub_httpx):
        stub_httpx._client.post = AsyncMock(
            return_value=_StubResponse(json_data={"ok": False, "description": "chat not found"})
        )
        ok = await plugin.send({"chat_id": "12345", "bot_token": "tkn"}, _msg())
        assert ok is False

    async def test_plugin_token_fills_missing_channel_token(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "plugin-tkn"})
        ok = await plugin.send({"chat_id": "12345"}, _msg())
        assert ok is True
        url = stub_httpx._client.post.await_args.args[0]
        assert "/botplugin-tkn/" in url

    async def test_channel_token_overrides_plugin_default(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "plugin-tkn"})
        ok = await plugin.send({"chat_id": "12345", "bot_token": "channel-tkn"}, _msg())
        assert ok is True
        url = stub_httpx._client.post.await_args.args[0]
        assert "/botchannel-tkn/" in url

    async def test_message_thread_id_propagates(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn"})
        ok = await plugin.send({"chat_id": "12345", "message_thread_id": 7}, _msg())
        assert ok is True
        body = stub_httpx._client.post.await_args.kwargs["json"]
        assert body["message_thread_id"] == 7

    async def test_disable_notification_propagates(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn"})
        ok = await plugin.send({"chat_id": "12345", "disable_notification": True}, _msg())
        assert ok is True
        body = stub_httpx._client.post.await_args.kwargs["json"]
        assert body["disable_notification"] is True

    async def test_default_parse_mode_plain_omits_field(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn"})
        ok = await plugin.send({"chat_id": "12345"}, _msg())
        assert ok is True
        body = stub_httpx._client.post.await_args.kwargs["json"]
        assert "parse_mode" not in body

    async def test_markdown_v1_escapes_underscore_in_rule_name(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn", "default_parse_mode": "Markdown"})
        ok = await plugin.send({"chat_id": "12345"}, _msg(rule_name="cpu_high_alert"))
        assert ok is True
        body = stub_httpx._client.post.await_args.kwargs["json"]
        assert body["parse_mode"] == "Markdown"
        # All three underscores should be escaped.
        assert "cpu\\_high\\_alert" in body["text"]

    async def test_markdown_v2_escapes_extended_set(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn", "default_parse_mode": "MarkdownV2"})
        ok = await plugin.send(
            {"chat_id": "12345"}, _msg(rule_name="alert.with-special!chars")
        )
        assert ok is True
        body = stub_httpx._client.post.await_args.kwargs["json"]
        assert body["parse_mode"] == "MarkdownV2"
        assert "alert\\.with\\-special\\!chars" in body["text"]

    async def test_html_escapes_lt_gt_amp(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn", "default_parse_mode": "HTML"})
        ok = await plugin.send({"chat_id": "12345"}, _msg(rule_name="<temp>&high"))
        assert ok is True
        body = stub_httpx._client.post.await_args.kwargs["json"]
        assert body["parse_mode"] == "HTML"
        assert "&lt;temp&gt;&amp;high" in body["text"]

    async def test_unknown_parse_mode_falls_back_to_plain(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn", "default_parse_mode": "Markdown"})
        ok = await plugin.send({"chat_id": "12345", "parse_mode": "Bogus"}, _msg())
        assert ok is True
        body = stub_httpx._client.post.await_args.kwargs["json"]
        assert "parse_mode" not in body  # bogus → plain → omitted

    async def test_long_message_truncated(self, plugin, plugin_module, stub_httpx):
        await plugin.configure({"bot_token": "tkn"})
        long_body = "x" * 8000
        ok = await plugin.send({"chat_id": "12345"}, _msg(message=long_body))
        assert ok is True
        body = stub_httpx._client.post.await_args.kwargs["json"]
        assert len(body["text"]) <= plugin_module._MAX_TEXT
        assert body["text"].endswith("…")

    async def test_network_error_returns_false(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn"})
        stub_httpx._client.post = AsyncMock(side_effect=stub_httpx.HTTPError("boom"))
        ok = await plugin.send({"chat_id": "12345"}, _msg())
        assert ok is False

    async def test_timeout_returns_false(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn"})
        stub_httpx._client.post = AsyncMock(side_effect=stub_httpx.TimeoutException("slow"))
        ok = await plugin.send({"chat_id": "12345"}, _msg())
        assert ok is False

    async def test_at_channel_chat_id_preserved_as_string(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn"})
        ok = await plugin.send({"chat_id": "@my_public_channel"}, _msg())
        assert ok is True
        body = stub_httpx._client.post.await_args.kwargs["json"]
        assert body["chat_id"] == "@my_public_channel"

    async def test_api_base_url_override_used(self, plugin, stub_httpx):
        await plugin.configure({"bot_token": "tkn", "api_base_url": "http://localhost:9999"})
        ok = await plugin.send({"chat_id": "12345"}, _msg())
        assert ok is True
        url = stub_httpx._client.post.await_args.args[0]
        assert url.startswith("http://localhost:9999/bot")


# ---------------------------------------------------------------------------
# /start handler — _handle_update
# ---------------------------------------------------------------------------


def _make_update(chat_id: int, text: str, update_id: int = 1) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


class TestStartHandler:
    async def test_subscribed_chat_replies_subscribed(self, plugin, stub_httpx, monkeypatch):
        monkeypatch.setattr(plugin, "_configured_chat_ids", AsyncMock(return_value={"12345"}))
        client = stub_httpx._client
        await plugin._handle_update(client, "https://api.telegram.org", "tkn", _make_update(12345, "/start"))
        client.post.assert_awaited_once()
        body = client.post.await_args.kwargs["json"]
        assert body["chat_id"] == "12345"
        assert "subscribed" in body["text"].lower()
        assert "12345" in body["text"]

    async def test_unsubscribed_chat_replies_with_chat_id(self, plugin, stub_httpx, monkeypatch):
        monkeypatch.setattr(plugin, "_configured_chat_ids", AsyncMock(return_value=set()))
        client = stub_httpx._client
        await plugin._handle_update(client, "https://api.telegram.org", "tkn", _make_update(99999, "/start"))
        client.post.assert_awaited_once()
        body = client.post.await_args.kwargs["json"]
        assert body["chat_id"] == "99999"
        assert "99999" in body["text"]
        assert "not subscribed" in body["text"].lower()
        assert "operator" in body["text"].lower() or "channels" in body["text"].lower()

    async def test_non_start_message_ignored(self, plugin, stub_httpx, monkeypatch):
        monkeypatch.setattr(plugin, "_configured_chat_ids", AsyncMock(return_value={"12345"}))
        client = stub_httpx._client
        await plugin._handle_update(client, "https://api.telegram.org", "tkn", _make_update(12345, "hello"))
        client.post.assert_not_awaited()

    async def test_start_with_bot_suffix_recognised(self, plugin, stub_httpx, monkeypatch):
        monkeypatch.setattr(plugin, "_configured_chat_ids", AsyncMock(return_value={"12345"}))
        client = stub_httpx._client
        await plugin._handle_update(client, "https://api.telegram.org", "tkn",
                                    _make_update(12345, "/start@MyNodeLensBot"))
        client.post.assert_awaited_once()

    async def test_start_with_args_recognised(self, plugin, stub_httpx, monkeypatch):
        monkeypatch.setattr(plugin, "_configured_chat_ids", AsyncMock(return_value=set()))
        client = stub_httpx._client
        await plugin._handle_update(client, "https://api.telegram.org", "tkn", _make_update(12345, "/start hello"))
        client.post.assert_awaited_once()

    async def test_db_failure_does_not_crash(self, plugin, stub_httpx, monkeypatch):
        monkeypatch.setattr(plugin, "_configured_chat_ids", AsyncMock(side_effect=RuntimeError("db down")))
        client = stub_httpx._client
        await plugin._handle_update(client, "https://api.telegram.org", "tkn", _make_update(12345, "/start"))
        # Reply skipped (no exception raised).
        client.post.assert_not_awaited()

    async def test_update_without_message_ignored(self, plugin, stub_httpx, monkeypatch):
        monkeypatch.setattr(plugin, "_configured_chat_ids", AsyncMock(return_value=set()))
        client = stub_httpx._client
        await plugin._handle_update(client, "https://api.telegram.org", "tkn", {"update_id": 1})
        client.post.assert_not_awaited()

    async def test_update_without_chat_id_ignored(self, plugin, stub_httpx, monkeypatch):
        monkeypatch.setattr(plugin, "_configured_chat_ids", AsyncMock(return_value=set()))
        client = stub_httpx._client
        update = {"update_id": 1, "message": {"text": "/start", "chat": {}}}
        await plugin._handle_update(client, "https://api.telegram.org", "tkn", update)
        client.post.assert_not_awaited()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_truncate_short_passthrough(self, plugin_module):
        assert plugin_module._truncate("short", 100) == "short"

    def test_truncate_appends_ellipsis(self, plugin_module):
        out = plugin_module._truncate("a" * 50, 10)
        assert len(out) == 10
        assert out.endswith("…")

    def test_escape_markdown_v1(self, plugin_module):
        assert plugin_module._escape_markdown_v1("a_b*c`d[e") == "a\\_b\\*c\\`d\\[e"

    def test_escape_html(self, plugin_module):
        assert plugin_module._escape_html("a<b>c&d") == "a&lt;b&gt;c&amp;d"

    def test_resolve_parse_mode_valid(self, plugin_module):
        assert plugin_module._resolve_parse_mode("Markdown", "") == "Markdown"

    def test_resolve_parse_mode_invalid_falls_back(self, plugin_module):
        assert plugin_module._resolve_parse_mode("BOGUS", "Markdown") == ""

    def test_resolve_parse_mode_empty_uses_fallback(self, plugin_module):
        assert plugin_module._resolve_parse_mode("", "MarkdownV2") == "MarkdownV2"
