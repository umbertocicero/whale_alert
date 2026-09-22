"""FastAPI application entrypoint for the whale alert backend."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from edgar import set_identity
from fastapi import FastAPI, HTTPException
from telegram.ext import Application

from app import database, reports
from app.config import get_settings
from app.insider_tracker import backfill_insider_history
from app.scheduler import create_scheduler
from app.telegram_bot import build_application
from app.whales import whale_name

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _start_bot() -> Application | None:  # type: ignore[type-arg]
    """Start the interactive Telegram bot via long polling, if enabled."""
    settings = get_settings()
    if not settings.enable_bot:
        return None
    application = build_application()
    try:
        await application.initialize()
        await application.start()
        if application.updater is not None:
            await application.updater.start_polling()
        logger.info("Telegram command bot started (long polling)")
    except Exception:  # noqa: BLE001 - network boundary; must not block startup
        logger.exception("Telegram bot could not start (continuing without it)")
        return None
    return application


async def _stop_bot(application: Application | None) -> None:  # type: ignore[type-arg]
    """Gracefully stop the Telegram bot if it is running."""
    if application is None:
        return
    try:
        if application.updater is not None:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
    except Exception:  # noqa: BLE001 - best-effort shutdown
        logger.exception("Error while stopping the Telegram bot")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize the database, SEC identity, scheduler and Telegram bot."""
    settings = get_settings()
    database.init_db(settings.database_path)
    set_identity(settings.sec_identity_email)

    scheduler = create_scheduler()
    scheduler.start()
    logger.info(
        "Whale alert scheduler started (13F every %s min, Form 4 every %s min) for %d whale(s)",
        settings.poll_interval_minutes,
        settings.insider_poll_interval_minutes,
        len(settings.whale_ciks),
    )

    application = await _start_bot()

    backfill_task = asyncio.create_task(backfill_insider_history(days=30))

    yield

    await _stop_bot(application)
    if not backfill_task.done():
        backfill_task.cancel()
    scheduler.shutdown(wait=False)


app = FastAPI(title="Whale Alert", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple liveness endpoint."""
    return {"status": "ok"}


@app.get("/whales")
async def list_whales() -> list[dict[str, str]]:
    """Return the whales currently being tracked, with their names."""
    settings = get_settings()
    return [{"cik": cik, "name": whale_name(cik)} for cik in settings.whale_ciks]


@app.get("/whales/{cik}/filings")
async def whale_filings(cik: str, limit: int = 10) -> list[dict[str, str | float | int]]:
    """Return the most recently detected filings for a tracked whale."""
    settings = get_settings()
    if cik not in settings.whale_ciks:
        raise HTTPException(status_code=404, detail="Whale not tracked")
    return database.list_filings(settings.database_path, cik, limit)


@app.get("/whales/{cik}/portfolio")
async def whale_portfolio(cik: str) -> dict[str, str]:
    """Return the latest known 13F portfolio composition of a whale."""
    settings = get_settings()
    if cik not in settings.whale_ciks:
        raise HTTPException(status_code=404, detail="Whale not tracked")
    return {"cik": cik, "name": whale_name(cik), "portfolio": reports.build_portfolio(cik)}


@app.get("/insider/week")
async def insider_week(cik: str | None = None) -> dict[str, str]:
    """Return insider (Form 4) activity over the last 7 days."""
    return {"summary": reports.build_week(cik)}


@app.get("/insider/month")
async def insider_month(cik: str | None = None) -> dict[str, str]:
    """Return filings and insider activity over the last 30 days."""
    return {"summary": reports.build_month(cik)}


@app.get("/report/weekly")
async def weekly_report() -> dict[str, str]:
    """Return the weekly digest text without sending it to Telegram."""
    return {"report": reports.build_weekly_report()}
