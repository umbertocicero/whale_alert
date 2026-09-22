"""SQLite persistence for whale 13F filing snapshots."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.models import WhaleFilingSnapshot

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
"""


def init_db(db_path: Path) -> None:
    """Create the database schema if it does not already exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(_SCHEMA)


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
    """Persist a whale filing snapshot, ignoring duplicates."""
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


def list_filings(db_path: Path, cik: str, limit: int = 10) -> list[dict[str, str | float | int]]:
    """Return the most recently detected filings for a whale, newest first."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM filings WHERE cik = ? ORDER BY detected_at DESC LIMIT ?",
            (cik, limit),
        ).fetchall()
    return [dict(row) for row in rows]
