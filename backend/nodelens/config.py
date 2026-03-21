from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://nodelens:nodelens@postgres:5432/nodelens"
    REDIS_URL: str = "redis://redis:6379/0"
    LOG_LEVEL: str = "INFO"
    ENABLE_FAKE_PUBLISHER: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
