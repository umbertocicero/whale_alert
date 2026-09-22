"""Application configuration loaded from environment variables / a .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the whale alert backend."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str
    telegram_chat_id: str
    sec_identity_email: str
    whale_ciks: Annotated[list[str], NoDecode]
    poll_interval_minutes: int = 60
    database_path: Path = Path("whale_alert.db")

    @field_validator("whale_ciks", mode="before")
    @classmethod
    def _split_ciks(cls, value: object) -> object:
        """Allow WHALE_CIKS to be provided as a comma-separated string."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()  # type: ignore[call-arg]
