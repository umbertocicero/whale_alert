"""Text report builders shared by the Telegram bot commands and weekly digest."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app import database
from app.config import get_settings
from app.telegram_notifier import send_telegram_message
from app.whales import FAMOUS_WHALES, normalize_cik, whale_name


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
    lines = ["\U0001f40b Tracked whales:"]
    for index, cik in enumerate(settings.whale_ciks, start=1):
        lines.append(f"  {index}. {whale_name(cik)} (CIK {cik})")
    lines.append("\nUse /portfolio <n>, /week <n> or /month <n>.")
    return "\n".join(lines)


def build_portfolio(cik: str) -> str:
    """Describe the latest known 13F portfolio composition for a whale."""
    settings = get_settings()
    holdings = database.get_latest_holdings(settings.database_path, cik, limit=15)
    if not holdings:
        return (
            f"No stored 13F holdings yet for {whale_name(cik)} (CIK {cik}). "
            "The next scheduled poll will populate them."
        )
    total = sum(holding.value_usd for holding in holdings)
    lines = [f"\U0001f4bc Portfolio (top holdings): {whale_name(cik)} (CIK {cik})"]
    for holding in holdings:
        weight = (holding.value_usd / total * 100) if total else 0.0
        target = holding.ticker or holding.issuer
        lines.append(f"  {target}: ${holding.value_usd:,.0f} ({weight:.1f}%)")
    return "\n".join(lines)


def _insider_lines(cik: str | None, since: date) -> list[str]:
    settings = get_settings()
    rows = database.list_insider_txns(settings.database_path, since, cik)
    lines: list[str] = []
    for row in rows:
        code = str(row["transaction_code"])
        sign = "BUY " if code.upper() in {"P", "A"} else "SELL"
        target = str(row["issuer_ticker"] or row["issuer_name"] or "?")
        who = "" if cik else f"{whale_name(str(row['cik']))}: "
        lines.append(
            f"  {who}{sign} {target} {float(row['shares']):,.0f} sh "
            f"(\u2248 ${float(row['total_value_usd']):,.0f}) on {row['transaction_date']}"
        )
    return lines


def build_week(cik: str | None = None) -> str:
    """Insider (Form 4) activity in the last 7 days."""
    since = _days_ago(7)
    scope = whale_name(cik) if cik else "all whales"
    lines = _insider_lines(cik, since)
    if not lines:
        return f"No insider (Form 4) trades in the last 7 days for {scope}."
    return "\n".join([f"\U0001f4c5 Last 7 days insider trades ({scope}):", *lines])


def build_month(cik: str | None = None) -> str:
    """Insider activity plus new 13F filings in the last 30 days."""
    settings = get_settings()
    since = _days_ago(30)
    scope = whale_name(cik) if cik else "all whales"
    sections: list[str] = [f"\U0001f5d3 Last 30 days ({scope}):"]

    filings = database.recent_filings(settings.database_path, since, cik)
    if filings:
        sections.append("\nNew 13F filings:")
        sections.extend(
            f"  {whale_name(str(row['cik']))}: filed {row['filing_date']} "
            f"(${float(row['total_value_usd']):,.0f})"
            for row in filings
        )

    insider = _insider_lines(cik, since)
    if insider:
        sections.append("\nInsider trades:")
        sections.extend(insider)

    if not filings and not insider:
        return f"No new filings or insider trades in the last 30 days for {scope}."
    return "\n".join(sections)


def build_weekly_report() -> str:
    """Build the automatic weekly digest across all tracked whales."""
    settings = get_settings()
    since = _days_ago(7)
    sections = ["\U0001f4f0 Weekly whale report"]

    filings = database.recent_filings(settings.database_path, since)
    sections.append(f"\nNew 13F filings this week: {len(filings)}")
    sections.extend(
        f"  {whale_name(str(row['cik']))}: ${float(row['total_value_usd']):,.0f}"
        for row in filings[:10]
    )

    insider = _insider_lines(None, since)
    sections.append(f"\nInsider trades this week: {len(insider)}")
    sections.extend(insider[:15])

    if not filings and not insider:
        sections.append("\nNo activity detected this week.")
    return "\n".join(sections)


async def send_weekly_report() -> None:
    """Send the weekly digest to the configured Telegram chat."""
    await send_telegram_message(build_weekly_report())
