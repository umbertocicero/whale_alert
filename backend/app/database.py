"""SQLite persistence for whale 13F filings and insider (Form 4) transactions."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from app.models import Holding, InsiderTransaction, WhaleFilingSnapshot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
    cik TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    company_name TEXT NOT NULL,
    filing_date TEXT NOT NULL,
    total_value_usd REAL NOT NULL,
    total_holdings INTEGER NOT NULL,
    detected_at TEXT NOT NULL,
    PRIMARY KEY (cik, accession_number)
);

CREATE TABLE IF NOT EXISTS holdings (
    cik TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    issuer TEXT NOT NULL,
    ticker TEXT NOT NULL,
    cusip TEXT NOT NULL,
    shares INTEGER NOT NULL,
    value_usd REAL NOT NULL,
    PRIMARY KEY (cik, accession_number, cusip)
);

CREATE TABLE IF NOT EXISTS insider_txns (
    cik TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    issuer_name TEXT NOT NULL,
    issuer_ticker TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    filing_date TEXT NOT NULL,
    transaction_code TEXT NOT NULL,
    shares REAL NOT NULL,
    price_per_share REAL NOT NULL,
    total_value_usd REAL NOT NULL,
    detected_at TEXT NOT NULL,
    PRIMARY KEY (cik, accession_number, issuer_ticker, transaction_date, transaction_code, shares)
);
"""


def init_db(db_path: Path) -> None:
    """Create the database schema if it does not already exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_SCHEMA)


# --------------------------------------------------------------------------- #
# 13F filings
# --------------------------------------------------------------------------- #


def get_last_accession(db_path: Path, cik: str) -> str | None:
    """Return the most recently stored accession number for a whale, if any."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT accession_number FROM filings WHERE cik = ? "
            "ORDER BY detected_at DESC LIMIT 1",
            (cik,),
        ).fetchone()
    return row[0] if row else None


def save_filing(db_path: Path, snapshot: WhaleFilingSnapshot) -> None:
    """Persist a whale filing snapshot and its holdings, ignoring duplicates."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO filings "
            "(cik, accession_number, company_name, filing_date, total_value_usd, "
            "total_holdings, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                snapshot.cik,
                snapshot.accession_number,
                snapshot.company_name,
                snapshot.filing_date.isoformat(),
                snapshot.total_value_usd,
                snapshot.total_holdings,
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.executemany(
            "INSERT OR IGNORE INTO holdings "
            "(cik, accession_number, issuer, ticker, cusip, shares, value_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    snapshot.cik,
                    snapshot.accession_number,
                    holding.issuer,
                    holding.ticker,
                    holding.cusip,
                    holding.shares,
                    holding.value_usd,
                )
                for holding in snapshot.top_holdings
            ],
        )


def list_filings(db_path: Path, cik: str, limit: int = 10) -> list[dict[str, str | float | int]]:
    """Return the most recently detected filings for a whale, newest first."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM filings WHERE cik = ? ORDER BY detected_at DESC LIMIT ?",
            (cik, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_latest_holdings(db_path: Path, cik: str, limit: int = 10) -> list[Holding]:
    """Return the stored holdings of a whale's most recent filing."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        latest = conn.execute(
            "SELECT accession_number FROM filings WHERE cik = ? "
            "ORDER BY detected_at DESC LIMIT 1",
            (cik,),
        ).fetchone()
        if latest is None:
            return []
        rows = conn.execute(
            "SELECT issuer, ticker, cusip, shares, value_usd FROM holdings "
            "WHERE cik = ? AND accession_number = ? ORDER BY value_usd DESC LIMIT ?",
            (cik, latest["accession_number"], limit),
        ).fetchall()
    return [
        Holding(
            issuer=row["issuer"],
            ticker=row["ticker"],
            cusip=row["cusip"],
            shares=int(row["shares"]),
            value_usd=float(row["value_usd"]),
        )
        for row in rows
    ]


def recent_filings(
    db_path: Path, since: date, cik: str | None = None
) -> list[dict[str, str | float | int]]:
    """Return filings detected on or after ``since`` (optionally for one whale)."""
    query = "SELECT * FROM filings WHERE detected_at >= ?"
    params: list[str] = [since.isoformat()]
    if cik is not None:
        query += " AND cik = ?"
        params.append(cik)
    query += " ORDER BY detected_at DESC"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


# --------------------------------------------------------------------------- #
# Insider (Form 4) transactions
# --------------------------------------------------------------------------- #


def get_known_insider_accessions(db_path: Path, cik: str) -> set[str]:
    """Return the set of Form 4 accession numbers already stored for a whale."""
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT accession_number FROM insider_txns WHERE cik = ?",
            (cik,),
        ).fetchall()
    return {row[0] for row in rows}


def save_insider_txns(db_path: Path, transactions: list[InsiderTransaction]) -> None:
    """Persist a batch of insider transactions, ignoring duplicates."""
    if not transactions:
        return
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO insider_txns "
            "(cik, accession_number, owner_name, issuer_name, issuer_ticker, "
            "transaction_date, filing_date, transaction_code, shares, price_per_share, "
            "total_value_usd, detected_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    txn.cik,
                    txn.accession_number,
                    txn.owner_name,
                    txn.issuer_name,
                    txn.issuer_ticker,
                    txn.transaction_date.isoformat(),
                    txn.filing_date.isoformat(),
                    txn.transaction_code,
                    txn.shares,
                    txn.price_per_share,
                    txn.total_value_usd,
                    now,
                )
                for txn in transactions
            ],
        )


def list_insider_txns(
    db_path: Path, since: date, cik: str | None = None
) -> list[dict[str, str | float | int]]:
    """Return insider transactions with a transaction date on/after ``since``."""
    query = "SELECT * FROM insider_txns WHERE transaction_date >= ?"
    params: list[str] = [since.isoformat()]
    if cik is not None:
        query += " AND cik = ?"
        params.append(cik)
    query += " ORDER BY transaction_date DESC"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
