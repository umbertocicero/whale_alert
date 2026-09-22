"""Fetch and evaluate 13F filings for tracked whale investors."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from edgar import Company

from app import database
from app.config import get_settings
from app.models import Holding, HoldingMove, WhaleFilingSnapshot
from app.telegram_notifier import send_whale_alert

logger = logging.getLogger(__name__)

_TOP_HOLDINGS_LIMIT = 10


def fetch_latest_filing(cik: str) -> WhaleFilingSnapshot | None:
    """Fetch and parse the latest 13F-HR filing for a whale.

    This performs blocking network I/O via edgartools and must be run off
    the event loop (see `check_all_whales`).
    """
    company = Company(cik)
    filings = company.get_filings(form="13F-HR")
    if not filings:
        return None

    filing = filings.latest()
    report = filing.obj()
    if report is None or not report.has_infotable():
        return None

    top_holdings = [
        Holding(
            issuer=str(row["Issuer"]),
            ticker=str(row.get("Ticker") or ""),
            cusip=str(row["Cusip"]),
            shares=int(row["SharesPrnAmount"]),
            value_usd=float(row["Value"]),
        )
        for _, row in report.holdings.sort_values("Value", ascending=False)
        .head(_TOP_HOLDINGS_LIMIT)
        .iterrows()
    ]

    moves: list[HoldingMove] = []
    if report.previous_holding_report() is not None:
        comparison = report.compare_holdings().data
        moves = [
            HoldingMove(
                issuer=str(row.get("Issuer", "")),
                ticker=str(row.get("Ticker") or ""),
                status=str(row["Status"]),
                value_usd=float(row.get("Value", 0.0) or 0.0),
                value_change_usd=float(row.get("ValueChange", 0.0) or 0.0),
            )
            for _, row in comparison.iterrows()
        ]

    return WhaleFilingSnapshot(
        cik=cik,
        company_name=str(report.management_company_name),
        accession_number=str(report.accession_number),
        filing_date=_to_date(report.filing_date),
        total_value_usd=float(report.total_value),
        total_holdings=int(report.total_holdings),
        top_holdings=top_holdings,
        moves=moves,
    )


def _to_date(value: object) -> date:
    """Normalize an edgartools filing date (str or date) to a date instance."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


async def check_all_whales() -> None:
    """Poll every tracked whale for a new 13F filing and notify on changes."""
    settings = get_settings()
    for cik in settings.whale_ciks:
        try:
            snapshot = await asyncio.to_thread(fetch_latest_filing, cik)
        except Exception:
            # Network calls and third-party parsing (edgartools/SEC) are a
            # system boundary: one whale's failure must not stop the others
            # or crash the scheduler.
            logger.exception("Failed to fetch 13F filing for whale %s", cik)
            continue

        if snapshot is None:
            logger.info("No 13F-HR filing found for whale %s", cik)
            continue

        last_accession = database.get_last_accession(settings.database_path, cik)
        if last_accession == snapshot.accession_number:
            continue

        database.save_filing(settings.database_path, snapshot)
        await send_whale_alert(snapshot, is_first_seen=last_accession is None)
