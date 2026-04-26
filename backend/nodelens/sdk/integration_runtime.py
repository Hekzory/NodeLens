"""Runtime helper for integration plugins — reads dispatch events and calls send()."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from nodelens.constants import ALERT_DISPATCH_STREAM
from nodelens.redis.streams import ack, ensure_consumer_group, read_stream
from nodelens.schemas.events import AlertMessage

if TYPE_CHECKING:
    import redis.asyncio as aioredis

    from nodelens.sdk.integration_plugin import IntegrationPlugin


def encode_dispatch_event(
    *,
    plugin_id: str,
    channel_id: str,
    channel_config: dict,
    message: AlertMessage,
) -> dict[str, str]:
    """Build the Redis-stream field dict for an alert dispatch event."""
    payload = dataclasses.asdict(message)
    # Datetime is not JSON-serialisable by default — flatten to ISO string.
    payload["triggered_at"] = message.triggered_at.isoformat()
    return {
        "plugin_id": plugin_id,
        "channel_id": channel_id,
        "channel_config_json": json.dumps(channel_config),
        "alert_message_json": json.dumps(payload),
    }


def _decode_alert_message(raw: str) -> AlertMessage:
    data = json.loads(raw)
    return AlertMessage(
        rule_name=data["rule_name"],
        device_name=data["device_name"],
        triggered_value=float(data["triggered_value"]),
        message=data["message"],
        triggered_at=datetime.fromisoformat(data["triggered_at"]),
    )


async def run_dispatch_loop(plugin: IntegrationPlugin, plugin_id: str) -> None:
    """Subscribe to the dispatch stream, filter by plugin_id, call plugin.send().

    Concrete integration plugins call this from their start().
    """
    logger = logging.getLogger(f"nodelens.plugin.{plugin.name}.dispatch")
    group = f"dispatch_{plugin.name}"
    consumer = f"{plugin.name}-1"

    r: aioredis.Redis = plugin.ctx._r()  # reuse the plugin's already-connected client
    await ensure_consumer_group(r, ALERT_DISPATCH_STREAM, group)
    logger.info("Dispatch loop started  stream=%s  group=%s", ALERT_DISPATCH_STREAM, group)

    while True:
        try:
            messages = await read_stream(
                r,
                group=group,
                consumer=consumer,
                stream=ALERT_DISPATCH_STREAM,
                count=20,
                block=2000,
            )
        except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
            logger.error("Redis connection error: %s. Retrying in 5s…", exc)
            await asyncio.sleep(5)
            continue

        if not messages:
            continue

        ack_ids: list[str] = []
        for msg_id, fields in messages:
            try:
                # Skip events meant for other plugins.
                if fields.get("plugin_id") != plugin_id:
                    ack_ids.append(msg_id)
                    continue
                channel_config = json.loads(fields["channel_config_json"])
                alert_message = _decode_alert_message(fields["alert_message_json"])
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                logger.warning("Dropping malformed dispatch %s: %s", msg_id, exc)
                ack_ids.append(msg_id)
                continue

            try:
                ok = await plugin.send(channel_config, alert_message)
                if not ok:
                    logger.warning(
                        "send() returned False for rule=%s channel=%s — not retrying",
                        alert_message.rule_name,
                        fields.get("channel_id"),
                    )
            except Exception:
                logger.exception(
                    "send() raised for rule=%s — not retrying",
                    alert_message.rule_name,
                )
            ack_ids.append(msg_id)

        if ack_ids:
            await ack(r, ALERT_DISPATCH_STREAM, group, *ack_ids)
