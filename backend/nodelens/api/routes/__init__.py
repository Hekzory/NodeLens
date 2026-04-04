"""Route sub-package — re-exports all routers for convenience."""

from nodelens.api.routes.health import router as health_router
from nodelens.api.routes.plugins import router as plugins_router
from nodelens.api.routes.devices import router as devices_router
from nodelens.api.routes.telemetry import router as telemetry_router
from nodelens.api.routes.alerts import router as alerts_router
from nodelens.api.routes.dashboards import router as dashboards_router

__all__ = [
    "health_router",
    "plugins_router",
    "devices_router",
    "telemetry_router",
    "alerts_router",
    "dashboards_router",
]
