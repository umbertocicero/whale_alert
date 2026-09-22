"""Interactive Telegram bot exposing whale data through slash commands.

Runs via long polling inside the FastAPI event loop (started/stopped in the
application lifespan). Commands:

* ``/start`` / ``/help`` - usage overview
* ``/list_whales``       - list tracked whales with a selection index
* ``/portfolio <n>``     - latest 13F portfolio composition of a whale
* ``/week [<n>]``        - insider (Form 4) trades in the last 7 days
* ``/month [<n>]``       - filings + insider trades in the last 30 days
* ``/report``            - the weekly digest on demand
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from app import reports
from app.config import get_settings

logger = logging.getLogger(__name__)

_HELP_TEXT = (
    "\U0001f40b Whale Alert bot\n"
    "/list_whales - tracked whales\n"
    "/portfolio <n> - portfolio composition of a whale\n"
    "/week [<n>] - insider trades (last 7 days)\n"
    "/month [<n>] - filings + insider trades (last 30 days)\n"
    "/report - weekly digest\n"
    "<n> is the whale index from /list_whales (or a CIK / name)."
)


async def _help(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        await update.message.reply_text(_HELP_TEXT)


async def _list_whales(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        await update.message.reply_text(reports.build_whales_list())


async def _portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    if not context.args:
        await update.message.reply_text("Usage: /portfolio <whale index, CIK or name>")
        return
    cik = reports.resolve_whale(" ".join(context.args))
    if cik is None:
        await update.message.reply_text("Whale not found. Try /list_whales.")
        return
    await update.message.reply_text(reports.build_portfolio(cik))


async def _week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    cik = reports.resolve_whale(" ".join(context.args)) if context.args else None
    await update.message.reply_text(reports.build_week(cik))


async def _month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    cik = reports.resolve_whale(" ".join(context.args)) if context.args else None
    await update.message.reply_text(reports.build_month(cik))


async def _report(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        await update.message.reply_text(reports.build_weekly_report())


def build_application() -> Application:  # type: ignore[type-arg]
    """Create the Telegram bot application with all command handlers registered."""
    settings = get_settings()
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(CommandHandler(["start", "help"], _help))
    application.add_handler(CommandHandler("list_whales", _list_whales))
    application.add_handler(CommandHandler("portfolio", _portfolio))
    application.add_handler(CommandHandler("week", _week))
    application.add_handler(CommandHandler("month", _month))
    application.add_handler(CommandHandler("report", _report))
    return application
