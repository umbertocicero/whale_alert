"""Background scheduler that periodically polls tracked whales."""

from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.insider_tracker import check_all_insiders
from app.reports import send_weekly_report
from app.whale_tracker import check_all_whales


def create_scheduler() -> AsyncIOScheduler:
    """Build an APScheduler instance configured to poll whales periodically."""
    settings = get_settings()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_all_whales,
        trigger="interval",
        minutes=settings.poll_interval_minutes,
        id="whale_check",
        next_run_time=datetime.now(),
    )
    scheduler.add_job(
        check_all_insiders,
        trigger="interval",
        minutes=settings.insider_poll_interval_minutes,
        id="insider_check",
        next_run_time=datetime.now(),
    )
    scheduler.add_job(
        send_weekly_report,
        trigger="cron",
        day_of_week=settings.weekly_report_day,
        hour=settings.weekly_report_hour,
        id="weekly_report",
    )
    return scheduler
