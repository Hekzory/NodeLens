"""Entry-point: python -m nodelens.api"""

import uvicorn

from nodelens.config import settings

uvicorn.run(
    "nodelens.api.app:app",
    host=settings.API_HOST,
    port=settings.API_PORT,
    log_level=settings.LOG_LEVEL.lower(),
)
