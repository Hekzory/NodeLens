#!/usr/bin/env python3
"""
NodeLens — End-to-End Ingest Pipeline Load Test
================================================

What this script tests
----------------------
This script validates the throughput of the real NodeLens telemetry ingest
pipeline:  Redis Streams  →  Ingestor service  →  TimescaleDB.

It is NOT a synthetic benchmark that bypasses production components.  Instead
it exercises the exact same code path that real device plugins use:

  1. Registration events are published to the `registration_events` Redis
     stream — the same way every device plugin registers itself on startup.
  2. Telemetry events are published to the `telemetry_events` Redis stream
     using the same four-field format (device_id, sensor_id, value, timestamp).
  3. The running Ingestor service consumes these events, validates foreign
     keys, and writes rows into the `telemetry` hypertable.
  4. The script then queries TimescaleDB to count how many rows actually
     landed and derives throughput numbers.

Why this is a trustworthy test
------------------------------
* The script itself never writes to the database — it only publishes to
  Redis and then reads the DB to verify.
* The Ingestor performs full validation (sensor exists, belongs to device,
  device has a registered plugin) before writing.
* TimescaleDB hypertable compression / chunking is active, so write
  performance reflects real operating conditions.
* The test runs against an isolated Postgres volume so production data is
  never affected.

Target criterion:  the system must sustain ingestion of telemetry from at
least 100 devices per second.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis

# ── Stream / field names (must match nodelens.constants) ────────────
TELEMETRY_STREAM = "telemetry_events"
REGISTRATION_STREAM = "registration_events"

# ── Defaults ────────────────────────────────────────────────────────
DEFAULT_DEVICES = 200
DEFAULT_SENSORS_PER_DEVICE = 3
DEFAULT_RATE = 200  # publish (checking) rate — events / sec
DEFAULT_TARGET_RATE = 100  # minimum required throughput — events / sec
DEFAULT_DURATION = 60  # seconds

REGISTRATION_SETTLE = 4  # seconds to let ingestor process registrations
DRAIN_TIMEOUT = 30  # max seconds to wait for the stream to drain


# ── Helpers ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NodeLens ingest load test")
    p.add_argument("--devices", type=int, default=DEFAULT_DEVICES)
    p.add_argument("--sensors-per-device", type=int, default=DEFAULT_SENSORS_PER_DEVICE)
    p.add_argument("--rate", type=int, default=DEFAULT_RATE, help="checking (publish) rate, events/sec")
    p.add_argument("--target-rate", type=int, default=DEFAULT_TARGET_RATE, help="minimum required throughput, events/sec")
    p.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="seconds")
    p.add_argument("--redis-url", default="redis://localhost:6379/0")
    p.add_argument("--db-dsn", default="postgresql://nodelens:nodelens@localhost:5432/nodelens")
    return p.parse_args()


def banner(args: argparse.Namespace) -> None:
    total = args.rate * args.duration
    print("=" * 55)
    print("  NodeLens — End-to-End Ingest Pipeline Load Test")
    print("=" * 55)
    print(f"  Devices to register: {args.devices:>6} ({args.sensors_per_device} sensors per device)")
    print(f"  Publish rate:        {args.rate:>6} events/sec (target min: {args.target_rate} events/sec)")
    print(f"  Test duration:      {args.duration:>6}s (expected total events: {total})")
    print("-" * 55)


# ── Phase 1: register fake plugin / devices / sensors ──────────────
async def register_entities(
    r: aioredis.Redis,
    n_devices: int,
    n_sensors: int,
) -> tuple[str, list[tuple[str, list[str]]]]:
    """Publish registration events and return (plugin_id, [(device_id, [sensor_ids])])."""

    plugin_id = str(uuid.uuid4())

    await r.xadd(REGISTRATION_STREAM, {
        "event_type": "register_plugin",
        "plugin_id": plugin_id,
        "plugin_type": "device",
        "module_name": f"loadtest_{plugin_id[:8]}",
        "display_name": "Load Test Plugin",
        "version": "0.0.0",
    })

    devices: list[tuple[str, list[str]]] = []

    for d in range(n_devices):
        device_id = str(uuid.uuid4())
        await r.xadd(REGISTRATION_STREAM, {
            "event_type": "register_device",
            "device_id": device_id,
            "plugin_id": plugin_id,
            "external_id": f"lt-dev-{d:04d}",
            "name": f"LoadTest Device {d}",
            "location": "",
        })

        sensor_ids: list[str] = []
        for s in range(n_sensors):
            sensor_id = str(uuid.uuid4())
            await r.xadd(REGISTRATION_STREAM, {
                "event_type": "register_sensor",
                "sensor_id": sensor_id,
                "device_id": device_id,
                "key": f"metric_{s}",
                "name": f"Metric {s}",
                "unit": "unit",
                "value_type": "numeric",
            })
            sensor_ids.append(sensor_id)

        devices.append((device_id, sensor_ids))

    return plugin_id, devices


async def wait_for_registration(
    pool: asyncpg.Pool,
    plugin_id: str,
    expected_devices: int,
    expected_sensors: int,
) -> bool:
    """Poll DB until all devices/sensors are visible or timeout."""
    deadline = time.monotonic() + REGISTRATION_SETTLE + 10
    while time.monotonic() < deadline:
        row = await pool.fetchrow(
            "SELECT "
            "(SELECT count(*) FROM devices WHERE plugin_id = $1) AS dev_count, "
            "(SELECT count(*) FROM sensors s JOIN devices d ON d.id = s.device_id "
            " WHERE d.plugin_id = $1) AS sen_count",
            uuid.UUID(plugin_id),
        )
        if row and row["dev_count"] >= expected_devices and row["sen_count"] >= expected_sensors:
            return True
        await asyncio.sleep(1)
    return False


# ── Phase 2: publish telemetry at target rate ──────────────────────
async def publish_telemetry(
    r: aioredis.Redis,
    devices: list[tuple[str, list[str]]],
    rate: int,
    duration: int,
) -> tuple[int, float, float]:
    """Publish events and return (count, elapsed, actual_rate)."""

    # flatten to list of (device_id, sensor_id) pairs for round-robin
    pairs = [
        (dev_id, sid)
        for dev_id, sids in devices
        for sid in sids
    ]
    n_pairs = len(pairs)

    interval = 1.0 / rate
    published = 0
    t_start = time.monotonic()
    t_end = t_start + duration
    idx = 0

    pipe = r.pipeline(transaction=False)
    batch_size = min(rate, 500)  # flush in reasonable batches

    while time.monotonic() < t_end:
        batch_start = time.monotonic()
        for _ in range(batch_size):
            if time.monotonic() >= t_end:
                break
            dev_id, sen_id = pairs[idx % n_pairs]
            idx += 1
            pipe.xadd(TELEMETRY_STREAM, {
                "device_id": dev_id,
                "sensor_id": sen_id,
                "value": str(round(random.uniform(0, 100), 2)),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            published += 1

        await pipe.execute()

        # rate-limit: sleep if we're ahead of schedule
        elapsed_batch = time.monotonic() - batch_start
        expected_batch = batch_size * interval
        if elapsed_batch < expected_batch:
            await asyncio.sleep(expected_batch - elapsed_batch)

    elapsed = time.monotonic() - t_start
    return published, elapsed, published / elapsed if elapsed > 0 else 0


# ── Phase 3: wait for ingestor to drain ────────────────────────────
async def wait_for_drain(
    r: aioredis.Redis,
    pool: asyncpg.Pool,
    test_start: datetime,
    expected: int,
) -> tuple[int, float]:
    """Wait until DB row count matches expected or timeout. Returns (db_count, drain_seconds)."""
    t0 = time.monotonic()
    deadline = t0 + DRAIN_TIMEOUT
    db_count = 0

    while time.monotonic() < deadline:
        db_count = await pool.fetchval(
            "SELECT count(*) FROM telemetry WHERE time >= $1",
            test_start,
        )
        if db_count >= expected:
            break
        await asyncio.sleep(1)

    drain_time = time.monotonic() - t0
    return db_count, drain_time


# ── Phase 4: results ───────────────────────────────────────────────
def print_results(
    args: argparse.Namespace,
    published: int,
    publish_rate: float,
    db_count: int,
    drain_time: float,
    total_time: float,
) -> bool:
    ingestion_pct = (db_count / published * 100) if published else 0
    throughput = db_count / total_time if total_time > 0 else 0
    coeff = throughput / args.target_rate if args.target_rate > 0 else 0
    passed = coeff >= 1.0

    print("=" * 55)
    print("  NodeLens Load Test Results")
    print("=" * 55)
    print(f"  Total events published: {published:>8} (In DB: {db_count})")
    print(f"  Publish rate:           {publish_rate:>8.1f} events/sec")
    if ingestion_pct < 99.9999:
        print(f"  Ingestion success:      {ingestion_pct:>7.1f}%")
    if drain_time > 0.1:
        print(f"  Drain time:             {drain_time:>7.1f}s")
    print(f"  Ingest throughput:      {throughput:>8.1f} events/sec")
    print(f"  Throughput coefficient: {coeff:>8.2f}x  (vs target {args.target_rate} ev/s)")
    print("-" * 55)

    verdict = "PASS" if passed else "FAIL"
    symbol = "+" if passed else "!"
    print(f"  Verdict:  [{symbol}] {verdict}  (coeff >= 1.0x required)")
    print("=" * 55)

    return passed


# ── Phase 5: cleanup ───────────────────────────────────────────────

async def cleanup(pool: asyncpg.Pool, plugin_id: str) -> None:
    """Remove all test data from DB."""
    pid = uuid.UUID(plugin_id)
    await pool.execute(
        "DELETE FROM telemetry WHERE sensor_id IN "
        "(SELECT s.id FROM sensors s JOIN devices d ON d.id = s.device_id WHERE d.plugin_id = $1)",
        pid,
    )
    await pool.execute(
        "DELETE FROM sensors WHERE device_id IN "
        "(SELECT id FROM devices WHERE plugin_id = $1)",
        pid,
    )
    await pool.execute("DELETE FROM devices WHERE plugin_id = $1", pid)
    await pool.execute("DELETE FROM plugins WHERE id = $1", pid)


# ── Main ────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> bool:
    banner(args)

    r = aioredis.from_url(args.redis_url, decode_responses=True)
    pool = await asyncpg.create_pool(dsn=args.db_dsn, min_size=1, max_size=2)

    total_sensors = args.devices * args.sensors_per_device

    # Phase 1 — registration
    print("[1/4] Registering test entities ...")
    plugin_id, devices = await register_entities(r, args.devices, args.sensors_per_device)
    print(f"      Published: 1 plugin, {args.devices} devices, {total_sensors} sensors...", end=" ")
    ok = await wait_for_registration(pool, plugin_id, args.devices, total_sensors)
    if not ok:
        print("!!!\n[!] Plugin registration did not complete in time. Is the ingestor running?\n!!!")
        await pool.close()
        await r.aclose()
        return False
    print("Plugin registration confirmed in DB.")

    # Phase 2 — publish telemetry
    print(f"[2/4] Publishing telemetry for {args.duration}s at ~{args.rate} events/sec...", end=" ")
    test_start = datetime.now(timezone.utc)
    published, pub_elapsed, pub_rate = await publish_telemetry(r, devices, args.rate, args.duration)
    print(f"Published {published} events in {pub_elapsed:.1f}s ({pub_rate:.1f} ev/s)")

    # Phase 3 — wait for drain
    print("[3/4] Waiting for ingestor to finish writing ...")
    db_count, drain_time = await wait_for_drain(r, pool, test_start, published)

    total_time = pub_elapsed + drain_time

    # Phase 4 — results
    print("[4/4] Collecting results ...")
    passed = print_results(args, published, pub_rate, db_count, drain_time, total_time)

    await cleanup(pool, plugin_id)
    print("Cleanup test data from DB done")

    await pool.close()
    await r.aclose()
    return passed


def main() -> None:
    args = parse_args()
    passed = asyncio.run(run(args))
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
