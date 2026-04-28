import logging
import secrets

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

_logger = logging.getLogger("nodelens.config")


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://nodelens:nodelens@postgres:5432/nodelens"
    REDIS_URL: str = "redis://redis:6379/0"
    LOG_LEVEL: str = "INFO"
    PLUGINS_DIR: str = "plugins"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # ── Auth / sessions ─────────────────────────────────────────────
    # Signed cookie session via Starlette's SessionMiddleware. SESSION_SECRET
    # MUST be set in production via env var; if missing, an ephemeral random
    # secret is generated at boot and a warning is logged — sessions then
    # invalidate on every API restart.
    SESSION_SECRET: str = ""
    SESSION_COOKIE_NAME: str = "nodelens_session"
    SESSION_LIFETIME_DAYS: int = Field(default=30, gt=0)
    SESSION_COOKIE_SECURE: bool = False
    CORS_ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost", "http://localhost:5173"]
    )

    NO_DATA_SCAN_INTERVAL_SECONDS: int = Field(default=5, gt=0)

    # ── Telemetry storage policies ──────────────────────────────────
    # Defaults below are the *seed* values. When a row is present in
    # `system_settings`, it overrides the corresponding field; see
    # `nodelens.system_settings`.
    RETENTION_DAYS: int = Field(default=365, gt=0)
    COMPRESSION_AFTER_DAYS: int = Field(default=7, gt=0)
    DISK_BUDGET_GB: int = Field(default=30, gt=0)
    RETENTION_CHECK_INTERVAL_SECONDS: int = Field(default=3600, gt=0)

    # ── Devices ─────────────────────────────────────────────────────
    # How many minutes since `devices.last_seen` still counts as "online".
    # Replaces the old `ONLINE_THRESHOLD = timedelta(minutes=30)` constant.
    ONLINE_THRESHOLD_MINUTES: int = Field(default=30, gt=0)

    # ── UI ──────────────────────────────────────────────────────────
    # Frontend dashboard polling cadence; the SPA fetches this on boot and
    # uses it for the TanStack Query default `refetchInterval`.
    FRONTEND_POLLING_INTERVAL_SECONDS: int = Field(default=10, gt=0)

    @model_validator(mode="after")
    def _compression_before_retention(self) -> "Settings":
        if self.COMPRESSION_AFTER_DAYS >= self.RETENTION_DAYS:
            raise ValueError(
                "COMPRESSION_AFTER_DAYS must be < RETENTION_DAYS — otherwise chunks "
                "are dropped before they ever get compressed."
            )
        return self

    @model_validator(mode="after")
    def _session_secret_fallback(self) -> "Settings":
        if not self.SESSION_SECRET:
            self.SESSION_SECRET = secrets.token_urlsafe(32)
            _logger.warning(
                "SESSION_SECRET is not set; generated an ephemeral one. "
                "Set SESSION_SECRET in .env to keep sessions across API restarts."
            )
        return self

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
