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
    from nodelens.db import init_models
    from nodelens.db.session import engine

    await init_models(engine)
    logger.info("Database schema ready (tables + hypertable).")

    from nodelens.workers.ingestor.consumer import run_consumer
    from nodelens.workers.ingestor.registration import run_registration_consumer

    tasks = [run_consumer(), run_registration_consumer()]

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
