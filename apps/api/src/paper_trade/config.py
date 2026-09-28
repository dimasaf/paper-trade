"""Runtime configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://paper_trade:paper_trade@127.0.0.1:5432/paper_trade"
    redis_url: str = "redis://127.0.0.1:6379/0"
    web_origin: str = "http://127.0.0.1:3000"
    worker_heartbeat_key: str = "paper-trade:worker:heartbeat"
    worker_heartbeat_max_age_seconds: float = 15.0
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="PAPER_TRADE_",
        env_file=".env",
        extra="ignore",
    )
