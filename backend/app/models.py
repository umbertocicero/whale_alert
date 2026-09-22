"""Domain models for whale (institutional investor) 13F tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class Holding:
    """A single position reported in a 13F filing."""

    issuer: str
    ticker: str
    cusip: str
    shares: int
    value_usd: float


@dataclass(frozen=True, slots=True)
class HoldingMove:
    """A quarter-over-quarter change in a single 13F holding."""

    issuer: str
    ticker: str
    status: str  # "NEW", "CLOSED", "INCREASED", "DECREASED", "UNCHANGED"
    value_usd: float
    value_change_usd: float


@dataclass(frozen=True, slots=True)
class WhaleFilingSnapshot:
    """A snapshot of a tracked whale's latest 13F-HR filing."""

    cik: str
    company_name: str
    accession_number: str
    filing_date: date
    total_value_usd: float
    total_holdings: int
    top_holdings: list[Holding] = field(default_factory=list)
    moves: list[HoldingMove] = field(default_factory=list)

    def top_new_positions(self, limit: int = 5) -> list[HoldingMove]:
        """Return the largest newly opened positions, sorted by value."""
        new_moves = [move for move in self.moves if move.status == "NEW"]
        return sorted(new_moves, key=lambda move: move.value_usd, reverse=True)[:limit]

    def top_closed_positions(self, limit: int = 5) -> list[HoldingMove]:
        """Return the largest closed positions, sorted by absolute value change."""
        closed_moves = [move for move in self.moves if move.status == "CLOSED"]
        return sorted(closed_moves, key=lambda move: abs(move.value_change_usd), reverse=True)[
            :limit
        ]
