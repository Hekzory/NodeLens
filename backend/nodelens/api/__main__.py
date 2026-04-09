"""Entry-point: python -m nodelens.api"""

from granian import Granian
from granian.constants import HTTPModes, Interfaces

from nodelens.config import settings

# Initialize Granian
server = Granian(
    target="nodelens.api.app:app",
    address=settings.API_HOST,
    port=settings.API_PORT,
    interface=Interfaces.ASGI,  # Explicitly set the interface (ASGI is standard for FastAPI/Starlette)
    log_level=settings.LOG_LEVEL.lower(),
    http=HTTPModes.auto
)

if __name__ == "__main__":
    server.serve()
