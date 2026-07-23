from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ecommerce_autogen"
    app_env: Literal["development", "testing", "production"] = "development"
    debug: bool = True

    mock_mode: bool = True
    allow_external_actions: bool = False
    allow_payments: bool = False

    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/ecommerce_autogen.db",
        min_length=1,
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return one cached Settings instance for the current application process."""

    return Settings()