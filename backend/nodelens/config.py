from datetime import timedelta

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

ONLINE_THRESHOLD = timedelta(minutes=30)


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://nodelens:nodelens@postgres:5432/nodelens"
    REDIS_URL: str = "redis://redis:6379/0"
    LOG_LEVEL: str = "INFO"
    PLUGINS_DIR: str = "plugins"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    NO_DATA_SCAN_INTERVAL_SECONDS: int = 5

    # ── Telemetry storage policies ──────────────────────────────────
    # Defaults match diploma NF-6/NF-7. Future iterations may let DB
    # rows override these; for now config.py is the single source.
    RETENTION_DAYS: int = Field(default=365, gt=0)
    COMPRESSION_AFTER_DAYS: int = Field(default=7, gt=0)
    DISK_BUDGET_GB: int = Field(default=30, gt=0)
    RETENTION_CHECK_INTERVAL_SECONDS: int = Field(default=3600, gt=0)

    @model_validator(mode="after")
    def _compression_before_retention(self) -> "Settings":
        if self.COMPRESSION_AFTER_DAYS >= self.RETENTION_DAYS:
            raise ValueError(
                "COMPRESSION_AFTER_DAYS must be < RETENTION_DAYS — otherwise chunks "
                "are dropped before they ever get compressed."
            )
        return self

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
