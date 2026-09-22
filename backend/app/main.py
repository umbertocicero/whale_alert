"""FastAPI application entrypoint for the whale alert backend."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from edgar import set_identity
from fastapi import FastAPI, HTTPException

from app import database
from app.config import get_settings
from app.scheduler import create_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize the database, SEC identity and scheduler on startup."""
    settings = get_settings()
    database.init_db(settings.database_path)
    set_identity(settings.sec_identity_email)

    scheduler = create_scheduler()
    scheduler.start()
    logger.info(
        "Whale alert scheduler started (every %s min) for %d whale(s)",
        settings.poll_interval_minutes,
        len(settings.whale_ciks),
    )

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="Whale Alert", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness endpoint."""
    return {"status": "ok"}


@app.get("/whales")
async def list_whales() -> dict[str, list[str]]:
    """Return the CIKs/tickers currently being tracked."""
    settings = get_settings()
    return {"whales": settings.whale_ciks}


@app.get("/whales/{cik}/filings")
async def whale_filings(cik: str, limit: int = 10) -> list[dict[str, str | float | int]]:
    """Return the most recently detected filings for a tracked whale."""
    settings = get_settings()
    if cik not in settings.whale_ciks:
        raise HTTPException(status_code=404, detail="Whale not tracked")
    return database.list_filings(settings.database_path, cik, limit)
