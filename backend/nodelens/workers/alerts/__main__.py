"""Alert worker entry-point (stub).

    python -m nodelens.workers.alerts

Placeholder that keeps the container healthy until the alert engine is
implemented.  Touches the healthcheck file so Docker sees it as alive.
"""

import logging
import time

from nodelens.heartbeat import touch_heartbeat

logging.basicConfig(
    level="INFO",
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("nodelens.alerts")


def main() -> None:
    logger.info("Alert worker started (not yet implemented — idling)")
    try:
        while True:
            touch_heartbeat()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Alert worker stopped.")


if __name__ == "__main__":
    main()
