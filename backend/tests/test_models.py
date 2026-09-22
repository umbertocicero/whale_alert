"""Tests for whale filing domain models."""

from datetime import date

from app.models import Holding, HoldingMove, WhaleFilingSnapshot


def _snapshot(moves: list[HoldingMove]) -> WhaleFilingSnapshot:
    return WhaleFilingSnapshot(
        cik="0001067983",
        company_name="Berkshire Hathaway Inc",
        accession_number="0000950123-24-007092",
        filing_date=date(2024, 5, 15),
        total_value_usd=313_218_000_000.0,
        total_holdings=40,
        top_holdings=[
            Holding(issuer="APPLE INC", ticker="AAPL", cusip="037833100", shares=1, value_usd=1.0)
        ],
        moves=moves,
    )


def test_top_new_positions_sorted_by_value() -> None:
    moves = [
        HoldingMove(issuer="A", ticker="A", status="NEW", value_usd=100.0, value_change_usd=100.0),
        HoldingMove(issuer="B", ticker="B", status="NEW", value_usd=500.0, value_change_usd=500.0),
        HoldingMove(
            issuer="C", ticker="C", status="UNCHANGED", value_usd=10.0, value_change_usd=0.0
        ),
    ]
    snapshot = _snapshot(moves)

    result = snapshot.top_new_positions(limit=5)

    assert [move.issuer for move in result] == ["B", "A"]


def test_top_new_positions_respects_limit() -> None:
    moves = [
        HoldingMove(
            issuer=str(i),
            ticker=str(i),
            status="NEW",
            value_usd=float(i),
            value_change_usd=float(i),
        )
        for i in range(10)
    ]
    snapshot = _snapshot(moves)

    result = snapshot.top_new_positions(limit=3)

    assert len(result) == 3
    assert [move.issuer for move in result] == ["9", "8", "7"]


def test_top_closed_positions_sorted_by_absolute_change() -> None:
    moves = [
        HoldingMove(
            issuer="A", ticker="A", status="CLOSED", value_usd=0.0, value_change_usd=-100.0
        ),
        HoldingMove(
            issuer="B", ticker="B", status="CLOSED", value_usd=0.0, value_change_usd=-500.0
        ),
    ]
    snapshot = _snapshot(moves)

    result = snapshot.top_closed_positions(limit=5)

    assert [move.issuer for move in result] == ["B", "A"]


def test_top_positions_ignore_other_statuses() -> None:
    moves = [
        HoldingMove(
            issuer="A", ticker="A", status="INCREASED", value_usd=100.0, value_change_usd=50.0
        ),
        HoldingMove(
            issuer="B", ticker="B", status="DECREASED", value_usd=100.0, value_change_usd=-50.0
        ),
    ]
    snapshot = _snapshot(moves)

    assert snapshot.top_new_positions() == []
    assert snapshot.top_closed_positions() == []
