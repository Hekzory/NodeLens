"""
Alert worker entry-point.

    python -m nodelens.workers.alerts

1. Ensures DB tables exist (idempotent).
2. Launches the alert evaluation loop (consumes telemetry_events,
   writes alert_history, publishes alert_dispatch_events).
"""

import asyncio
import logging

from nodelens.config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("nodelens.alerts")


async def main() -> None:
    from nodelens.db import init_models
    from nodelens.db.session import engine

    await init_models(engine)
    logger.info("Database schema ready (alerts).")

    from nodelens.workers.alerts.engine import run_engine
    from nodelens.workers.alerts.no_data_scanner import run_no_data_scanner

    logger.info("Starting alert engine and no_data scanner …")
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(run_engine(), name="alert-engine")
            tg.create_task(run_no_data_scanner(), name="no-data-scanner")
    finally:
        from nodelens.redis.client import close_redis

        await close_redis()
        await engine.dispose()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
