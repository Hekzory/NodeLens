import redis.asyncio as aioredis

from nodelens.schemas.events import TelemetryEvent


async def publish_event(r: aioredis.Redis, stream: str, event: TelemetryEvent) -> str:
    """XADD a TelemetryEvent to the given stream. Returns the message ID."""
    fields = {
        "device_id": event.device_id,
        "sensor_id": event.sensor_id,
        "value": str(event.value),
        "timestamp": event.timestamp.isoformat(),
    }
    return await r.xadd(stream, fields)


async def ensure_consumer_group(r: aioredis.Redis, stream: str, group: str) -> None:
    """Create the consumer group (and the stream itself) if they don't exist yet."""
    try:
        await r.xgroup_create(stream, group, id="0", mkstream=True)
    except aioredis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def read_stream(
    r: aioredis.Redis,
    group: str,
    consumer: str,
    stream: str,
    count: int = 100,
    block: int = 2000,
) -> list[tuple[str, dict]]:
    """XREADGROUP — returns list of (message_id, field_dict)."""
    results = await r.xreadgroup(
        groupname=group,
        consumername=consumer,
        streams={stream: ">"},
        count=count,
        block=block,
    )
    if not results:
        return []
    messages: list[tuple[str, dict]] = []
    for _stream_name, entries in results:
        for msg_id, fields in entries:
            messages.append((msg_id, fields))
    return messages


async def ack(r: aioredis.Redis, stream: str, group: str, *msg_ids: str) -> None:
    """Acknowledge one or more messages."""
    if msg_ids:
        await r.xack(stream, group, *msg_ids)
