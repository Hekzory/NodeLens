"""Telegram integration plugin — alert delivery via the Telegram Bot API.

Per-channel config keys (only ``chat_id`` required):
    chat_id:               str — Telegram chat ID. Numeric (e.g. "12345" or
                                 "-1001234567") or "@public_channel". Stored
                                 as string so the @-form is preserved.
    bot_token:             str — overrides the plugin-level token for this
                                 channel only. Leave empty to inherit.
    parse_mode:            str — "" (plain), "Markdown", "MarkdownV2", or
                                 "HTML". Overrides the plugin default.
    disable_notification:  bool — silent message (no notification sound).
                                  Overrides the plugin default.
    message_thread_id:     int — for forum/topic groups; routes the message
                                 to a specific topic.

Plugin-level config (set on the Plugins page) is merged in: ``bot_token``,
``default_parse_mode``, ``api_base_url``, ``request_timeout_s``,
``disable_notification``. Per-channel config wins on a per-key basis,
matching the email plugin's pattern.

Subscription discovery (``/start``):
    When the plugin-level token is set, the plugin long-polls
    ``getUpdates`` and replies to incoming ``/start`` commands. Chats whose
    ID appears in any active NotificationChannel.config.chat_id receive
    "you are subscribed"; every other chat gets its numeric ID echoed back
    with an instruction to ask the operator to add it. Both replies use
    the plugin-level bot identity (channel-level token overrides apply
    only to outbound alert delivery).

The plugin never retries on failure — Telegram returns descriptive errors
in the response body and the dispatch contract documented in AGENTS.md
mandates ack-on-handle. Failures (bad token, unknown chat, network error,
message-too-long) log + return False without raising.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select

from nodelens.db.models import NotificationChannel
from nodelens.db.session import async_session
from nodelens.schemas.events import AlertMessage
from nodelens.sdk.integration_plugin import IntegrationPlugin
from nodelens.sdk.integration_runtime import run_dispatch_loop

logger = logging.getLogger("nodelens.plugin.telegram")

# httpx logs the full request URL at INFO, and Telegram embeds the bot
# token in the URL path (`/bot<TOKEN>/...`). Silence it so the token never
# lands in plain-text container logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

# Telegram's hard message limit is 4096 chars; keep headroom for our header
# so we don't get cut off mid-sentence after the body is appended.
_MAX_TEXT = 4000
# Telegram side of the long-poll: server holds the connection open up to
# this many seconds before returning an empty result. The httpx client
# timeout must exceed this, otherwise the client cancels first.
_POLL_TIMEOUT_S = 30
# Cool-down after a getUpdates failure (network, 4xx, ok=false body).
_POLL_BACKOFF_S = 5

_VALID_PARSE_MODES = ("", "Markdown", "MarkdownV2", "HTML")
# MarkdownV1 special chars per Telegram docs.
_MD_V1_SPECIAL = "_*`["
# MarkdownV2 special chars per Telegram docs (broader than V1).
_MD_V2_SPECIAL = r"_*[]()~`>#+-=|{}.!"


def _escape_markdown_v1(s: str) -> str:
    return "".join("\\" + c if c in _MD_V1_SPECIAL else c for c in s)


def _escape_markdown_v2(s: str) -> str:
    return "".join("\\" + c if c in _MD_V2_SPECIAL else c for c in s)


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape(text: str, parse_mode: str) -> str:
    if parse_mode == "Markdown":
        return _escape_markdown_v1(text)
    if parse_mode == "MarkdownV2":
        return _escape_markdown_v2(text)
    if parse_mode == "HTML":
        return _escape_html(text)
    return text


def _format_body(message: AlertMessage, parse_mode: str) -> str:
    """Build the message text. User-supplied fields are escaped per parse_mode.

    Plain text uses no decoration; Markdown/HTML wrap the rule name in bold
    and put the value/timestamp in code spans for readability.
    """
    rule = _escape(message.rule_name, parse_mode)
    device = _escape(message.device_name, parse_mode)
    value = _escape(format(message.triggered_value, "g"), parse_mode)
    when = _escape(message.triggered_at.isoformat(), parse_mode)
    body = _escape(message.message, parse_mode)

    if parse_mode in ("Markdown", "MarkdownV2"):
        return (
            f"*NodeLens Alert: {rule}*\n"
            f"Device: `{device}`\n"
            f"Value: `{value}`\n"
            f"At: `{when}`\n\n"
            f"{body}"
        )
    if parse_mode == "HTML":
        return (
            f"<b>NodeLens Alert: {rule}</b>\n"
            f"Device: <code>{device}</code>\n"
            f"Value: <code>{value}</code>\n"
            f"At: <code>{when}</code>\n\n"
            f"{body}"
        )
    return (
        f"NodeLens Alert: {rule}\n"
        f"Device: {device}\n"
        f"Value: {value}\n"
        f"At: {when}\n\n"
        f"{body}"
    )


def _truncate(text: str, limit: int = _MAX_TEXT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _resolve_parse_mode(value: Any, fallback: str) -> str:
    """Coerce a value into one of the recognised parse modes (or empty).

    Empty / None on the channel side means "inherit fallback" — the empty
    string IS technically a valid parse mode (plain text), but treating it
    as "unset" is what gives operators the override-with-default semantics
    they expect from per-channel config.
    """
    if value is None or value == "":
        return fallback if fallback in _VALID_PARSE_MODES else ""
    if isinstance(value, str) and value in _VALID_PARSE_MODES:
        return value
    logger.warning("Unrecognised parse_mode %r — falling back to plain text", value)
    return ""


async def _post_send_message(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    chat_id: str,
    text: str,
    *,
    parse_mode: str = "",
    disable_notification: bool = False,
    message_thread_id: int | None = None,
) -> bool:
    """POST to ``/sendMessage``. Returns True on Telegram-confirmed success.

    Network errors, non-2xx responses, and ``ok=false`` payloads all log and
    return False. Never raises.
    """
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if disable_notification:
        payload["disable_notification"] = True
    if message_thread_id is not None:
        payload["message_thread_id"] = int(message_thread_id)

    url = f"{base_url}/bot{token}/sendMessage"
    try:
        response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        logger.error("Telegram sendMessage network error for chat=%s: %s", chat_id, exc)
        return False
    except Exception:
        logger.exception("Telegram sendMessage unexpected error for chat=%s", chat_id)
        return False

    if response.status_code >= 400:
        logger.error(
            "Telegram sendMessage failed chat=%s status=%s body=%s",
            chat_id,
            response.status_code,
            response.text[:300],
        )
        return False
    try:
        body = response.json()
    except ValueError:
        logger.error("Telegram sendMessage returned non-JSON body for chat=%s: %s", chat_id, response.text[:300])
        return False
    if not body.get("ok"):
        logger.error(
            "Telegram sendMessage ok=false for chat=%s description=%s",
            chat_id,
            body.get("description"),
        )
        return False
    return True


class TelegramIntegrationPlugin(IntegrationPlugin):
    name = "telegram"
    version = "0.1.0"

    def __init__(self) -> None:
        super().__init__()
        # Plugin-level defaults populated by ``configure``. Channel config
        # still wins on a per-key basis when ``send()`` runs.
        self._defaults: dict[str, Any] = {}
        # Coordinates a clean shutdown of the polling loop.
        self._stop = asyncio.Event()

    async def configure(self, settings: dict[str, Any]) -> None:
        self._defaults = dict(settings or {})
        if self._defaults:
            logger.info(
                "Telegram defaults loaded: token=%s parse_mode=%s base_url=%s timeout=%ss silent=%s",
                "(set)" if self._defaults.get("bot_token") else "(unset)",
                self._defaults.get("default_parse_mode") or "(plain)",
                self._defaults.get("api_base_url") or "https://api.telegram.org",
                self._defaults.get("request_timeout_s") or 15,
                bool(self._defaults.get("disable_notification")),
            )

    async def start(self) -> None:
        # Run the alert-dispatch loop and the /start listener concurrently.
        # The listener only starts when a plugin-level token is configured —
        # /start replies use that single shared bot identity, so without it
        # there's no bot to listen for.
        token = (self._defaults.get("bot_token") or "").strip()
        coros = [run_dispatch_loop(self, self.ctx.plugin_id)]
        if token:
            logger.info("Starting /start listener (long-poll getUpdates).")
            coros.append(self._poll_updates_loop(token))
        else:
            logger.info("Polling disabled — no plugin-level bot_token configured.")
        await asyncio.gather(*coros)

    async def stop(self) -> None:
        self._stop.set()

    async def send(self, channel_config: dict[str, Any], message: AlertMessage) -> bool:
        chat_id_raw = channel_config.get("chat_id")
        if chat_id_raw is None or str(chat_id_raw).strip() == "":
            logger.error("Channel config missing required 'chat_id' field")
            return False
        # Preserve the @channel_name form by staying in str.
        chat_id = str(chat_id_raw).strip()

        token = (
            (channel_config.get("bot_token") or "").strip()
            if isinstance(channel_config.get("bot_token"), str)
            else ""
        )
        if not token:
            token = (self._defaults.get("bot_token") or "").strip()
        if not token:
            logger.error("No bot_token configured (channel or plugin-level) — cannot deliver to chat=%s", chat_id)
            return False

        parse_mode = _resolve_parse_mode(
            channel_config.get("parse_mode"),
            (self._defaults.get("default_parse_mode") or ""),
        )

        if "disable_notification" in channel_config:
            disable_notification = bool(channel_config["disable_notification"])
        else:
            disable_notification = bool(self._defaults.get("disable_notification", False))

        thread_raw = channel_config.get("message_thread_id")
        message_thread_id: int | None
        if thread_raw is None or thread_raw == "":
            message_thread_id = None
        else:
            try:
                message_thread_id = int(thread_raw)
            except (TypeError, ValueError):
                logger.warning("Ignoring non-integer message_thread_id=%r for chat=%s", thread_raw, chat_id)
                message_thread_id = None

        text = _truncate(_format_body(message, parse_mode))
        base_url = (self._defaults.get("api_base_url") or "https://api.telegram.org").rstrip("/")
        timeout_s = int(self._defaults.get("request_timeout_s") or 15)

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            ok = await _post_send_message(
                client,
                base_url,
                token,
                chat_id,
                text,
                parse_mode=parse_mode,
                disable_notification=disable_notification,
                message_thread_id=message_thread_id,
            )

        if ok:
            logger.info(
                "Sent telegram message to chat=%s (rule=%s, parse_mode=%s)",
                chat_id,
                message.rule_name,
                parse_mode or "plain",
            )
        return ok

    # ------------------------------------------------------------------
    # /start subscription-check listener
    # ------------------------------------------------------------------

    async def _poll_updates_loop(self, token: str) -> None:
        """Long-poll ``getUpdates`` and reply to ``/start`` commands.

        Restart-safe: ``offset`` is in-memory only. After a restart Telegram
        re-delivers any unacked updates within ~24h, and ``/start`` replies
        are idempotent so duplicates are harmless.
        """
        base_url = (self._defaults.get("api_base_url") or "https://api.telegram.org").rstrip("/")
        timeout_s = int(self._defaults.get("request_timeout_s") or 15)
        # httpx must outlast Telegram's long-poll wait, otherwise the client
        # cancels before the server returns its (possibly empty) result.
        client_timeout = max(timeout_s, _POLL_TIMEOUT_S + 5)

        offset: int | None = None
        async with httpx.AsyncClient(timeout=client_timeout) as client:
            while not self._stop.is_set():
                try:
                    params: dict[str, Any] = {
                        "timeout": _POLL_TIMEOUT_S,
                        "allowed_updates": '["message"]',
                    }
                    if offset is not None:
                        params["offset"] = offset
                    response = await client.get(
                        f"{base_url}/bot{token}/getUpdates", params=params
                    )
                except (httpx.HTTPError, OSError) as exc:
                    logger.warning("getUpdates network error: %s — backing off %ss", exc, _POLL_BACKOFF_S)
                    await self._sleep_or_stop(_POLL_BACKOFF_S)
                    continue
                except Exception:
                    logger.exception("Unexpected error in getUpdates — backing off %ss", _POLL_BACKOFF_S)
                    await self._sleep_or_stop(_POLL_BACKOFF_S)
                    continue

                if response.status_code >= 400:
                    logger.error(
                        "getUpdates failed status=%s body=%s",
                        response.status_code,
                        response.text[:300],
                    )
                    await self._sleep_or_stop(_POLL_BACKOFF_S)
                    continue
                try:
                    body = response.json()
                except ValueError:
                    logger.error("getUpdates returned non-JSON body: %s", response.text[:300])
                    await self._sleep_or_stop(_POLL_BACKOFF_S)
                    continue
                if not body.get("ok"):
                    logger.error("getUpdates ok=false: %s", body.get("description"))
                    await self._sleep_or_stop(_POLL_BACKOFF_S)
                    continue

                for update in body.get("result", []) or []:
                    try:
                        offset = int(update["update_id"]) + 1
                    except (KeyError, TypeError, ValueError):
                        logger.warning("Update missing update_id, skipping: %r", update)
                        continue
                    try:
                        await self._handle_update(client, base_url, token, update)
                    except Exception:
                        logger.exception("Error handling update %s — continuing", offset - 1)

    async def _sleep_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return

    async def _handle_update(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        token: str,
        update: dict,
    ) -> None:
        msg = update.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return
        # Match "/start" and "/start@BotName". Anything else is ignored.
        first_word = text.split(maxsplit=1)[0] if text else ""
        if first_word != "/start" and not first_word.startswith("/start@"):
            return

        chat_id_str = str(chat_id)
        try:
            subscribed_ids = await self._configured_chat_ids()
        except Exception:
            logger.exception("Failed to load configured chat_ids — skipping /start reply.")
            return

        if chat_id_str in subscribed_ids:
            reply = (
                f"You are subscribed. NodeLens alerts for this chat "
                f"(id {chat_id_str}) will be delivered here."
            )
        else:
            reply = (
                "This chat is not subscribed.\n"
                f"Your chat ID: {chat_id_str}\n"
                "Ask the operator to add it as a Telegram channel under "
                "Alerts → Channels in NodeLens to start receiving alerts."
            )
        await _post_send_message(client, base_url, token, chat_id_str, reply)

    async def _configured_chat_ids(self) -> set[str]:
        """All chat_ids across active channels for this plugin (string-compared)."""
        plugin_uuid = uuid.UUID(self.ctx.plugin_id)
        async with async_session() as session:
            stmt = select(NotificationChannel.config).where(
                NotificationChannel.plugin_id == plugin_uuid,
                NotificationChannel.is_active.is_(True),
            )
            rows = (await session.execute(stmt)).scalars().all()
        ids: set[str] = set()
        for cfg in rows:
            cid = (cfg or {}).get("chat_id")
            if cid is not None and str(cid).strip():
                ids.add(str(cid).strip())
        return ids
