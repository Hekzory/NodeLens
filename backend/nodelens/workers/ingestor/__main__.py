"""
Ingestor entry-point.

    python -m nodelens.workers.ingestor

1. Ensures DB tables + hypertable exist (idempotent DDL only — no seed data).
2. Launches the Redis → Postgres telemetry consumer loop.
3. Launches the registration-event consumer loop.
"""

import asyncio
import logging

from nodelens.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("nodelens.ingestor")


async def main() -> None:
    from nodelens.db import apply_storage_policies, init_models
    from nodelens.db.session import engine

    await init_models(engine)
    logger.info("Database schema ready (tables + hypertable).")

    await apply_storage_policies(engine)
    from nodelens.system_settings import runtime_settings

    cfg = await runtime_settings.get_many(
        "compression_after_days", "retention_days", "disk_budget_gb"
    )
    logger.info(
        "Storage policies applied  compress_after=%dd  retain=%dd  budget=%dGB",
        cfg["compression_after_days"], cfg["retention_days"], cfg["disk_budget_gb"],
    )

    from nodelens.workers.ingestor.consumer import run_consumer
    from nodelens.workers.ingestor.registration import run_registration_consumer
    from nodelens.workers.ingestor.retention import run_disk_budget_enforcer

    tasks = [run_consumer(), run_registration_consumer(), run_disk_budget_enforcer()]

    logger.info("Starting ingestor (%d tasks) …", len(tasks))
    try:
        await asyncio.gather(*tasks)
    finally:
        from nodelens.redis.client import close_redis

        await close_redis()
        await engine.dispose()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
