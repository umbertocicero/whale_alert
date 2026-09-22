"""Telegram notification delivery for whale filing alerts."""

from __future__ import annotations

import logging

from telegram import Bot
from telegram.error import TelegramError

from app.config import get_settings
from app.models import InsiderTransaction, WhaleFilingSnapshot
from app.whales import whale_name

logger = logging.getLogger(__name__)

_INSIDER_ALERT_LIMIT = 10


async def send_telegram_message(text: str) -> None:
    """Send a plain-text message to the configured Telegram chat."""
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    try:
        async with bot:
            await bot.send_message(chat_id=settings.telegram_chat_id, text=text)
    except TelegramError:
        logger.exception("Failed to send Telegram message")


async def send_whale_alert(snapshot: WhaleFilingSnapshot, *, is_first_seen: bool) -> None:
    """Send a Telegram notification describing a whale's new 13F filing."""
    await send_telegram_message(_format_message(snapshot, is_first_seen=is_first_seen))


async def send_insider_alert(cik: str, transactions: list[InsiderTransaction]) -> None:
    """Send a Telegram notification describing new insider (Form 4) trades."""
    await send_telegram_message(_format_insider_message(cik, transactions))


def _format_insider_message(cik: str, transactions: list[InsiderTransaction]) -> str:
    """Build a plain-text Telegram message for insider transactions."""
    lines = [f"\U0001f9fe Insider trades: {whale_name(cik)} (CIK {cik})"]
    for txn in transactions[:_INSIDER_ALERT_LIMIT]:
        sign = "BUY " if txn.is_purchase else "SELL"
        target = txn.issuer_ticker or txn.issuer_name or "?"
        lines.append(
            f"  {sign} {target} [{txn.transaction_code}] "
            f"{txn.shares:,.0f} sh @ ${txn.price_per_share:,.2f} "
            f"(\u2248 ${txn.total_value_usd:,.0f}) on {txn.transaction_date.isoformat()}"
        )
    if len(transactions) > _INSIDER_ALERT_LIMIT:
        lines.append(f"  ... and {len(transactions) - _INSIDER_ALERT_LIMIT} more")
    return "\n".join(lines)


def _format_message(snapshot: WhaleFilingSnapshot, *, is_first_seen: bool) -> str:
    """Build a plain-text Telegram message for a filing snapshot."""
    header = "New whale filing" if not is_first_seen else "Whale tracked (first snapshot)"
    lines = [
        f"\U0001f40b {header}: {snapshot.company_name} (CIK {snapshot.cik})",
        f"Filed: {snapshot.filing_date.isoformat()}",
        f"Accession: {snapshot.accession_number}",
        f"Portfolio value: ${snapshot.total_value_usd:,.0f} "
        f"across {snapshot.total_holdings} positions",
    ]

    new_positions = snapshot.top_new_positions()
    if new_positions:
        lines.append("\nTop new buys:")
        lines.extend(
            f"  + {move.issuer} ({move.ticker}): ${move.value_usd:,.0f}" for move in new_positions
        )

    closed_positions = snapshot.top_closed_positions()
    if closed_positions:
        lines.append("\nTop closed positions:")
        lines.extend(
            f"  - {move.issuer} ({move.ticker}): ${abs(move.value_change_usd):,.0f}"
            for move in closed_positions
        )

    return "\n".join(lines)
    """Build a plain-text Telegram message for a filing snapshot."""
    header = "New whale filing" if not is_first_seen else "Whale tracked (first snapshot)"
    lines = [
        f"\U0001f40b {header}: {snapshot.company_name} (CIK {snapshot.cik})",
        f"Filed: {snapshot.filing_date.isoformat()}",
        f"Accession: {snapshot.accession_number}",
        f"Portfolio value: ${snapshot.total_value_usd:,.0f} "
        f"across {snapshot.total_holdings} positions",
    ]

    new_positions = snapshot.top_new_positions()
    if new_positions:
        lines.append("\nTop new buys:")
        lines.extend(
            f"  + {move.issuer} ({move.ticker}): ${move.value_usd:,.0f}" for move in new_positions
        )

    closed_positions = snapshot.top_closed_positions()
    if closed_positions:
        lines.append("\nTop closed positions:")
        lines.extend(
            f"  - {move.issuer} ({move.ticker}): ${abs(move.value_change_usd):,.0f}"
            for move in closed_positions
        )

    return "\n".join(lines)
