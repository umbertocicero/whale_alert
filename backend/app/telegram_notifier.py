"""Telegram notification delivery for whale filing alerts."""

from __future__ import annotations

import logging
from html import escape

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from app.config import get_settings
from app.models import InsiderTransaction, WhaleFilingSnapshot
from app.whales import whale_name

logger = logging.getLogger(__name__)

_INSIDER_ALERT_LIMIT = 10
_TELEGRAM_MESSAGE_LIMIT = 4096


def _esc(value: object) -> str:
    """HTML-escape a value for safe inclusion in a Telegram HTML message."""
    return escape(str(value), quote=False)


def split_message(text: str, limit: int = _TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split ``text`` into chunks Telegram will accept (max ``limit`` chars each).

    Telegram rejects any message over 4096 characters with ``BadRequest:
    Message is too long``. Reports built from many whales/lines can easily
    exceed that, so splits are made on newline boundaries (each report line is
    a self-contained HTML fragment, e.g. ``<b>...</b>``) to avoid cutting an
    HTML tag in half. A single line longer than ``limit`` is hard-split as a
    last resort.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(line) <= limit:
            current = line
        else:
            for start in range(0, len(line), limit):
                chunks.append(line[start : start + limit])
            current = ""
    if current:
        chunks.append(current)
    return chunks


async def send_telegram_message(text: str, *, parse_mode: str | None = ParseMode.HTML) -> None:
    """Send a message to the configured Telegram chat, splitting it if too long."""
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token)
    try:
        async with bot:
            for chunk in split_message(text):
                await bot.send_message(
                    chat_id=settings.telegram_chat_id, text=chunk, parse_mode=parse_mode
                )
    except TelegramError:
        logger.exception("Failed to send Telegram message")


async def send_whale_alert(snapshot: WhaleFilingSnapshot, *, is_first_seen: bool) -> None:
    """Send a Telegram notification describing a whale's new 13F filing."""
    await send_telegram_message(_format_message(snapshot, is_first_seen=is_first_seen))


async def send_insider_alert(cik: str, transactions: list[InsiderTransaction]) -> None:
    """Send a Telegram notification describing new insider (Form 4) trades."""
    await send_telegram_message(_format_insider_message(cik, transactions))


def _format_insider_message(cik: str, transactions: list[InsiderTransaction]) -> str:
    """Build an HTML-formatted Telegram message for insider transactions."""
    lines = [
        f"\U0001f9fe <b>Insider trades \u2014 {_esc(whale_name(cik))}</b> (CIK <code>{cik}</code>)"
    ]
    for txn in transactions[:_INSIDER_ALERT_LIMIT]:
        emoji = "\U0001f7e2 BUY " if txn.is_purchase else "\U0001f534 SELL"
        target = txn.issuer_ticker or txn.issuer_name or "?"
        lines.append(
            f"\u2022 {emoji} <b>{_esc(target)}</b> [{txn.transaction_code}] "
            f"{txn.shares:,.0f} sh @ ${txn.price_per_share:,.2f} "
            f"(\u2248 ${txn.total_value_usd:,.0f}) on {txn.transaction_date.isoformat()}"
        )
    if len(transactions) > _INSIDER_ALERT_LIMIT:
        lines.append(f"\u2026 and {len(transactions) - _INSIDER_ALERT_LIMIT} more")
    return "\n".join(lines)


def _format_message(snapshot: WhaleFilingSnapshot, *, is_first_seen: bool) -> str:
    """Build an HTML-formatted Telegram message for a filing snapshot."""
    header = "New whale filing" if not is_first_seen else "Whale tracked (first snapshot)"
    lines = [
        f"\U0001f40b <b>{header}: {_esc(snapshot.company_name)}</b> "
        f"(CIK <code>{snapshot.cik}</code>)",
        f"Filed: {snapshot.filing_date.isoformat()}",
        f"Accession: <code>{snapshot.accession_number}</code>",
        f"Portfolio value: ${snapshot.total_value_usd:,.0f} "
        f"across {snapshot.total_holdings} positions",
    ]

    new_positions = snapshot.top_new_positions()
    if new_positions:
        lines.append("\n<b>Top new buys:</b>")
        lines.extend(
            f"\u2022 + <b>{_esc(move.issuer)}</b> ({_esc(move.ticker)}): ${move.value_usd:,.0f}"
            for move in new_positions
        )

    closed_positions = snapshot.top_closed_positions()
    if closed_positions:
        lines.append("\n<b>Top closed positions:</b>")
        lines.extend(
            f"\u2022 - <b>{_esc(move.issuer)}</b> ({_esc(move.ticker)}): "
            f"${abs(move.value_change_usd):,.0f}"
            for move in closed_positions
        )

    return "\n".join(lines)
