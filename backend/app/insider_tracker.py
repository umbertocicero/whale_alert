"""Fetch and evaluate insider (Form 4) transactions for tracked whales.

Form 4 filings are submitted within two business days of an insider trade, so
they provide the near real-time "what did they buy/sell this week" view that
quarterly 13F filings cannot.

edgartools' Form 4 parsing surface has changed across versions; the extraction
below is deliberately defensive (best-effort attribute/column probing wrapped in
guards) so that an unexpected shape degrades to "no transactions" rather than
crashing the scheduler.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

from edgar import Company

from app import database
from app.config import get_settings
from app.models import InsiderTransaction
from app.telegram_notifier import send_insider_alert
from app.whales import whale_name

logger = logging.getLogger(__name__)

_MAX_FORM4_PER_WHALE = 20


def _to_date(value: object) -> date | None:
    """Normalize an edgartools date (str or date) to a date, or None."""
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _first_attr(obj: object, names: tuple[str, ...]) -> Any:
    """Return the first non-empty attribute among ``names`` on ``obj``."""
    for name in names:
        value = getattr(obj, name, None)
        if value:
            return value
    return None


def _row_get(row: Any, names: tuple[str, ...]) -> Any:
    """Return the first present value among ``names`` in a mapping-like row."""
    for name in names:
        try:
            value = row[name]
        except (KeyError, TypeError, IndexError):
            value = getattr(row, name, None)
        if value is not None and str(value).strip() not in {"", "nan", "NaN"}:
            return value
    return None


def _float(value: object, default: float = 0.0) -> float:
    """Best-effort float conversion."""
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _parse_form4(cik: str, filing: Any, form4: Any) -> list[InsiderTransaction]:
    """Extract non-derivative transactions from a parsed Form 4 object."""
    accession = str(getattr(filing, "accession_number", ""))
    filing_date = _to_date(getattr(filing, "filing_date", None)) or date.today()
    owner = _first_attr(form4, ("reporting_owner_name", "owner_name")) or whale_name(cik)
    issuer_name = ""
    issuer_ticker = ""
    issuer = getattr(form4, "issuer", None)
    if issuer is not None:
        issuer_name = str(_first_attr(issuer, ("name",)) or "")
        issuer_ticker = str(_first_attr(issuer, ("ticker", "trading_symbol")) or "")
    if not issuer_name:
        issuer_name = str(_first_attr(form4, ("issuer_name",)) or getattr(filing, "company", ""))

    to_df = getattr(form4, "to_dataframe", None)
    if not callable(to_df):
        return []
    try:
        frame = to_df()
    except Exception:  # noqa: BLE001 - third-party parsing boundary
        logger.debug("Form 4 to_dataframe failed for %s (%s)", cik, accession)
        return []

    transactions: list[InsiderTransaction] = []
    for _, row in frame.iterrows():
        code = str(_row_get(row, ("TransactionCode", "transaction_code", "Code")) or "").strip()
        if not code:
            continue
        txn_date = (
            _to_date(_row_get(row, ("TransactionDate", "transaction_date", "Date"))) or filing_date
        )
        shares = _float(_row_get(row, ("Shares", "shares", "TransactionShares")))
        price = _float(_row_get(row, ("Price", "price", "TransactionPricePerShare")))
        transactions.append(
            InsiderTransaction(
                cik=cik,
                owner_name=str(owner),
                issuer_name=issuer_name,
                issuer_ticker=issuer_ticker,
                accession_number=accession,
                transaction_date=txn_date,
                filing_date=filing_date,
                transaction_code=code,
                shares=shares,
                price_per_share=price,
                total_value_usd=shares * price,
            )
        )
    return transactions


def fetch_recent_form4(cik: str, known_accessions: set[str]) -> list[InsiderTransaction]:
    """Fetch and parse new Form 4 filings for a whale (blocking network I/O)."""
    company = Company(cik)
    filings = company.get_filings(form="4")
    if not filings:
        return []

    results: list[InsiderTransaction] = []
    for filing in filings.head(_MAX_FORM4_PER_WHALE):
        accession = str(getattr(filing, "accession_number", ""))
        if not accession or accession in known_accessions:
            continue
        try:
            form4 = filing.obj()
        except Exception:  # noqa: BLE001 - third-party parsing boundary
            logger.debug("Could not parse Form 4 %s for whale %s", accession, cik)
            continue
        if form4 is None:
            continue
        results.extend(_parse_form4(cik, filing, form4))
    return results


async def check_all_insiders() -> None:
    """Poll every tracked whale for new Form 4 filings and notify on new trades."""
    settings = get_settings()
    for cik in settings.whale_ciks:
        known = database.get_known_insider_accessions(settings.database_path, cik)
        try:
            transactions = await asyncio.to_thread(fetch_recent_form4, cik, known)
        except Exception:  # noqa: BLE001 - network/parsing boundary per whale
            logger.exception("Failed to fetch Form 4 filings for whale %s", cik)
            continue

        if not transactions:
            continue

        database.save_insider_txns(settings.database_path, transactions)
        await send_insider_alert(cik, transactions)
