"""NodeLens FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from nodelens import __version__
from nodelens.api.middleware import ETagMiddleware, OriginCheckMiddleware
from nodelens.api.routes.alerts import router as alerts_router
from nodelens.api.routes.auth import router as auth_router
from nodelens.api.routes.channels import router as channels_router
from nodelens.api.routes.dashboards import router as dashboards_router
from nodelens.api.routes.devices import router as devices_router
from nodelens.api.routes.health import router as health_router
from nodelens.api.routes.plugins import router as plugins_router
from nodelens.api.routes.system_settings import router as system_settings_router
from nodelens.api.routes.telemetry import router as telemetry_router
from nodelens.api.routes.users import router as users_router
from nodelens.auth.dependencies import get_current_user
from nodelens.config import settings
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

# ── CORS ─────────────────────────────────────────────────────────
# Wildcard + allow_credentials is silently rejected by browsers, so we
# always pin origins to the configured allow-list.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Session cookie ───────────────────────────────────────────────
# Signed cookie holding ``{"user_id": "<uuid>"}``. We never invalidate
# server-side; deleting / deactivating a user is enforced in the auth
# dependency (the session is functional but maps to a now-unusable user).
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    session_cookie=settings.SESSION_COOKIE_NAME,
    max_age=settings.SESSION_LIFETIME_DAYS * 86400,
    same_site="lax",
    https_only=settings.SESSION_COOKIE_SECURE,
    path="/",
)

# ── CSRF defence-in-depth ───────────────────────────────────────
app.add_middleware(OriginCheckMiddleware)

# ── ETag (304 Not Modified) ─────────────────────────────────────
app.add_middleware(ETagMiddleware)

# ── Routers ─────────────────────────────────────────────────────
# Health stays public so external uptime probes work without credentials.
# Auth is public (you need to be able to log in before you have a session).
# Everything else is gated by the get_current_user dependency.
protected = [Depends(get_current_user)]

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router, dependencies=protected)
app.include_router(plugins_router, dependencies=protected)
app.include_router(devices_router, dependencies=protected)
app.include_router(telemetry_router, dependencies=protected)
app.include_router(channels_router, dependencies=protected)
app.include_router(alerts_router, dependencies=protected)
app.include_router(dashboards_router, dependencies=protected)
app.include_router(system_settings_router, dependencies=protected)
