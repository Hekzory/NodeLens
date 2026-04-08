"""NodeLens FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nodelens import __version__
from nodelens.api.routes.alerts import router as alerts_router
from nodelens.api.routes.dashboards import router as dashboards_router
from nodelens.api.routes.devices import router as devices_router
from nodelens.api.routes.health import router as health_router
from nodelens.api.routes.plugins import router as plugins_router
from nodelens.api.routes.telemetry import router as telemetry_router
from nodelens.db import init_models
from nodelens.db.session import engine

logger = logging.getLogger("nodelens.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)s  %(levelname)s  %(message)s")
    logger.info("Ensuring database tables exist …")
    await init_models(engine)
    logger.info("NodeLens API v%s ready", __version__)
    yield
    await engine.dispose()
    logger.info("API shut down.")


app = FastAPI(
    title="NodeLens API",
    version=__version__,
    description="IoT telemetry monitoring — configuration & query plane",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS (permissive for dev; nginx will proxy in production) ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(plugins_router)
app.include_router(devices_router)
app.include_router(telemetry_router)
app.include_router(alerts_router)
app.include_router(dashboards_router)
