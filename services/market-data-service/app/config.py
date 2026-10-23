"""Configuration settings for Market Data Service."""

from typing import Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../../Stock_Sense_Infra/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Exchange and Data Lake
    EXCHANGE_ID: str = "binance"
    DATA_STORE_DIR: str = "./data_store"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/stocksense"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    ADMIN_API_KEY: str = "dev-admin-secret-key-12345"

    # Ingestion Scope
    DEFAULT_SYMBOLS: list[str] = ["BTC/USDT", "ETH/USDT"]
    DEFAULT_TIMEFRAMES: list[str] = ["1h", "1d", "15m", "4h"]

    # Scheduler & Execution
    ENABLE_SCHEDULER: bool = True
    SCHEDULER_INTERVAL_SECONDS: int = 300

    # Logging
    LOG_LEVEL: str = "INFO"

    @field_validator("DEFAULT_SYMBOLS", "DEFAULT_TIMEFRAMES", mode="before")
    @classmethod
    def parse_comma_separated_list(cls, value: Union[str, list[str]]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
