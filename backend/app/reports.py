"""Text report builders shared by the Telegram bot commands and weekly digest."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from html import escape

from app import database
from app.config import get_settings
from app.telegram_notifier import send_telegram_message
from app.whales import FAMOUS_WHALES, normalize_cik, whale_name


def _esc(value: object) -> str:
    """HTML-escape a value for safe inclusion in a Telegram HTML message."""
    return escape(str(value), quote=False)


def _days_ago(days: int) -> date:
    """Return the UTC date ``days`` days before today."""
    return (datetime.now(UTC) - timedelta(days=days)).date()


def resolve_whale(token: str) -> str | None:
    """Resolve a user-supplied token (index, CIK or name fragment) to a CIK."""
    settings = get_settings()
    token = token.strip()
    if token.isdigit() and len(token) <= 3:
        index = int(token) - 1
        if 0 <= index < len(settings.whale_ciks):
            return settings.whale_ciks[index]
    normalized = normalize_cik(token)
    for cik in settings.whale_ciks:
        if normalize_cik(cik) == normalized:
            return cik
    lowered = token.lower()
    for cik, name in FAMOUS_WHALES.items():
        if lowered in name.lower() and cik in {normalize_cik(c) for c in settings.whale_ciks}:
            return cik
    return None


def build_whales_list() -> str:
    """List all tracked whales with a selection index."""
    settings = get_settings()
    lines = ["\U0001f40b <b>Tracked whales</b>:"]
    for index, cik in enumerate(settings.whale_ciks, start=1):
        lines.append(f"{index}. <b>{_esc(whale_name(cik))}</b> (CIK <code>{cik}</code>)")
    lines.append("\n\U0001f4a1 Tap a whale below for its portfolio, week or month at a glance.")
    return "\n".join(lines)


def build_portfolio(cik: str) -> str:
    """Describe the latest known 13F portfolio composition for a whale."""
    settings = get_settings()
    name = whale_name(cik)
    holdings = database.get_latest_holdings(settings.database_path, cik, limit=15)
    if not holdings:
        return (
            f"\U0001f4bc No stored 13F holdings yet for <b>{_esc(name)}</b> "
            f"(CIK <code>{cik}</code>). The next scheduled poll will populate them."
        )
    total = sum(holding.value_usd for holding in holdings)
    lines = [f"\U0001f4bc <b>Portfolio \u2014 {_esc(name)}</b> (CIK <code>{cik}</code>)"]
    for holding in holdings:
        weight = (holding.value_usd / total * 100) if total else 0.0
        target = holding.ticker or holding.issuer
        lines.append(f"\u2022 <b>{_esc(target)}</b>: ${holding.value_usd:,.0f} ({weight:.1f}%)")
    return "\n".join(lines)


def _insider_lines(cik: str | None, since: date) -> list[str]:
    settings = get_settings()
    rows = database.list_insider_txns(settings.database_path, since, cik)
    lines: list[str] = []
    for row in rows:
        code = str(row["transaction_code"])
        emoji = "\U0001f7e2 BUY " if code.upper() in {"P", "A"} else "\U0001f534 SELL"
        target = str(row["issuer_ticker"] or row["issuer_name"] or "?")
        who = "" if cik else f"<b>{_esc(whale_name(str(row['cik'])))}</b>: "
        lines.append(
            f"\u2022 {who}{emoji} <b>{_esc(target)}</b> {float(row['shares']):,.0f} sh "
            f"(\u2248 ${float(row['total_value_usd']):,.0f}) on {row['transaction_date']}"
        )
    return lines


def build_week(cik: str | None = None) -> str:
    """Insider (Form 4) activity in the last 7 days."""
    since = _days_ago(7)
    scope = _esc(whale_name(cik)) if cik else "all whales"
    lines = _insider_lines(cik, since)
    if not lines:
        return f"\U0001f4c5 No insider (Form 4) trades in the last 7 days for <b>{scope}</b>."
    return "\n".join([f"\U0001f4c5 <b>Last 7 days \u2014 insider trades</b> ({scope}):", *lines])


def build_month(cik: str | None = None) -> str:
    """Insider activity plus new 13F filings in the last 30 days."""
    settings = get_settings()
    since = _days_ago(30)
    scope = _esc(whale_name(cik)) if cik else "all whales"
    sections: list[str] = [f"\U0001f5d3 <b>Last 30 days</b> ({scope}):"]

    filings = database.recent_filings(settings.database_path, since, cik)
    if filings:
        sections.append("\n<b>New 13F filings:</b>")
        sections.extend(
            f"\u2022 <b>{_esc(whale_name(str(row['cik'])))}</b>: filed {row['filing_date']} "
            f"(${float(row['total_value_usd']):,.0f})"
            for row in filings
        )

    insider = _insider_lines(cik, since)
    if insider:
        sections.append("\n<b>Insider trades:</b>")
        sections.extend(insider)

    if not filings and not insider:
        return (
            f"\U0001f5d3 No new filings or insider trades in the last 30 days for <b>{scope}</b>."
        )
    return "\n".join(sections)


def build_weekly_report() -> str:
    """Build the automatic weekly digest across all tracked whales."""
    settings = get_settings()
    since = _days_ago(7)
    sections = ["\U0001f4f0 <b>Weekly whale report</b>"]

    filings = database.recent_filings(settings.database_path, since)
    sections.append(f"\n<b>New 13F filings this week:</b> {len(filings)}")
    sections.extend(
        f"\u2022 <b>{_esc(whale_name(str(row['cik'])))}</b>: ${float(row['total_value_usd']):,.0f}"
        for row in filings[:10]
    )

    insider = _insider_lines(None, since)
    sections.append(f"\n<b>Insider trades this week:</b> {len(insider)}")
    sections.extend(insider[:15])

    if not filings and not insider:
        sections.append("\nNo activity detected this week.")
    return "\n".join(sections)


async def send_weekly_report() -> None:
    """Send the weekly digest to the configured Telegram chat."""
    await send_telegram_message(build_weekly_report())
