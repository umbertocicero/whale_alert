"""Tests for SQLite persistence of whale filing snapshots."""

from datetime import date
from pathlib import Path

from app import database
from app.models import Holding, WhaleFilingSnapshot


def _snapshot(accession: str) -> WhaleFilingSnapshot:
    return WhaleFilingSnapshot(
        cik="0001067983",
        company_name="Berkshire Hathaway Inc",
        accession_number=accession,
        filing_date=date(2024, 5, 15),
        total_value_usd=313_218_000_000.0,
        total_holdings=40,
        top_holdings=[
            Holding(
                issuer="APPLE INC",
                ticker="AAPL",
                cusip="037833100",
                shares=10_000,
                value_usd=1_000_000.0,
            )
        ],
    )


def test_init_db_creates_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "whale.db"

    database.init_db(db_path)

    assert db_path.exists()


def test_get_last_accession_returns_none_when_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "whale.db"
    database.init_db(db_path)

    assert database.get_last_accession(db_path, "0001067983") is None


def test_save_and_retrieve_last_accession(tmp_path: Path) -> None:
    db_path = tmp_path / "whale.db"
    database.init_db(db_path)

    database.save_filing(db_path, _snapshot("0000950123-24-007092"))

    assert database.get_last_accession(db_path, "0001067983") == "0000950123-24-007092"


def test_save_filing_ignores_duplicate_accession(tmp_path: Path) -> None:
    db_path = tmp_path / "whale.db"
    database.init_db(db_path)

    database.save_filing(db_path, _snapshot("0000950123-24-007092"))
    database.save_filing(db_path, _snapshot("0000950123-24-007092"))

    filings = database.list_filings(db_path, "0001067983", limit=10)
    assert len(filings) == 1


def test_list_filings_returns_recent_first(tmp_path: Path) -> None:
    db_path = tmp_path / "whale.db"
    database.init_db(db_path)

    database.save_filing(db_path, _snapshot("0000950123-24-007092"))
    database.save_filing(db_path, _snapshot("0000950123-24-999999"))

    filings = database.list_filings(db_path, "0001067983", limit=10)

    assert len(filings) == 2


def test_save_filing_ignores_empty_portfolio_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "whale.db"
    database.init_db(db_path)

    snapshot = WhaleFilingSnapshot(
        cik="0001067983",
        company_name="Berkshire Hathaway Inc",
        accession_number="0001193125-26-352200",
        filing_date=date(2026, 8, 14),
        total_value_usd=299_253_556_246.0,
        total_holdings=0,
        top_holdings=[],
    )

    database.save_filing(db_path, snapshot)

    assert database.list_filings(db_path, "0001067983", limit=10) == []
