"""Tests for application settings parsing."""

from app.config import Settings


def test_whale_ciks_parsed_from_comma_separated_string() -> None:
    settings = Settings(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        sec_identity_email="me@example.com",
        whale_ciks="BRK.A, 0001067983 ,AAPL",  # type: ignore[arg-type]
    )

    assert settings.whale_ciks == ["BRK.A", "0001067983", "AAPL"]


def test_whale_ciks_accepts_list_directly() -> None:
    settings = Settings(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        sec_identity_email="me@example.com",
        whale_ciks=["BRK.A", "AAPL"],
    )

    assert settings.whale_ciks == ["BRK.A", "AAPL"]


def test_default_poll_interval() -> None:
    settings = Settings(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        sec_identity_email="me@example.com",
        whale_ciks=["BRK.A"],
    )

    assert settings.poll_interval_minutes == 60
