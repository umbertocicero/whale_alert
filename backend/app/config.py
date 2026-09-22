"""Application configuration loaded from environment variables / a .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.whales import FAMOUS_WHALES


class Settings(BaseSettings):
    """Runtime settings for the whale alert backend."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str
    telegram_chat_id: str
    sec_identity_email: str
    whale_ciks: Annotated[list[str], NoDecode] = []
    poll_interval_minutes: int = 60
    insider_poll_interval_minutes: int = 360
    weekly_report_day: str = "mon"
    weekly_report_hour: int = 9
    enable_bot: bool = True
    database_path: Path = Path("whale_alert.db")

    @field_validator("whale_ciks", mode="before")
    @classmethod
    def _split_ciks(cls, value: object) -> object:
        """Allow WHALE_CIKS to be provided as a comma-separated string."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("whale_ciks")
    @classmethod
    def _default_to_curated(cls, value: list[str]) -> list[str]:
        """Fall back to the curated famous-whale list when none are configured."""
        return value or list(FAMOUS_WHALES)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()  # type: ignore[call-arg]
