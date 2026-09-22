"""Telegram notification delivery for whale filing alerts."""

from __future__ import annotations

import logging

from telegram import Bot
from telegram.error import TelegramError

from app.config import get_settings
from app.models import WhaleFilingSnapshot

logger = logging.getLogger(__name__)


async def send_whale_alert(snapshot: WhaleFilingSnapshot, *, is_first_seen: bool) -> None:
    """Send a Telegram notification describing a whale's new 13F filing."""
    settings = get_settings()
    message = _format_message(snapshot, is_first_seen=is_first_seen)
    bot = Bot(token=settings.telegram_bot_token)
    try:
        async with bot:
            await bot.send_message(chat_id=settings.telegram_chat_id, text=message)
    except TelegramError:
        logger.exception("Failed to send Telegram alert for whale %s", snapshot.cik)


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
