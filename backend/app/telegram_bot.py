"""Interactive Telegram bot exposing whale data through slash commands.

Runs via long polling inside the FastAPI event loop (started/stopped in the
application lifespan). Commands:

* ``/start`` / ``/help`` - usage overview
* ``/list_whales``       - list tracked whales with a selection index
* ``/portfolio <n>``     - latest 13F portfolio composition of a whale
* ``/week [<n>]``        - insider (Form 4) trades in the last 7 days
* ``/month [<n>]``       - filings + insider trades in the last 30 days
* ``/report``            - the weekly digest on demand

Every reply also carries an inline keyboard with one row per tracked whale, so
users can tap straight into a whale's portfolio/week/month without typing its
CIK (the callback data already embeds it, e.g. ``portfolio:0001067983``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from app import reports
from app.config import get_settings
from app.whales import whale_name

logger = logging.getLogger(__name__)

_HELP_TEXT = (
    "\U0001f40b <b>Whale Alert bot</b>\n"
    "/list_whales \u2014 tracked whales (with quick-action buttons)\n"
    "/portfolio &lt;n&gt; \u2014 portfolio composition of a whale\n"
    "/week [&lt;n&gt;] \u2014 insider trades (last 7 days)\n"
    "/month [&lt;n&gt;] \u2014 filings + insider trades (last 30 days)\n"
    "/report \u2014 weekly digest\n"
    "\n"
    "<code>&lt;n&gt;</code> is the whale index from /list_whales (or a CIK / name).\n"
    "\U0001f4a1 Tip: tap the buttons under any reply to jump straight to a "
    "whale's portfolio, week or month \u2014 no typing needed."
)

_ACTION_BUILDERS: dict[str, Callable[[str], str]] = {
    "portfolio": reports.build_portfolio,
    "week": reports.build_week,
    "month": reports.build_month,
}


def _whales_keyboard() -> InlineKeyboardMarkup:
    """Build an inline keyboard with one row of quick actions per tracked whale."""
    settings = get_settings()
    rows = [
        [
            InlineKeyboardButton(f"\U0001f3e6 {whale_name(cik)}", callback_data=f"portfolio:{cik}"),
            InlineKeyboardButton("\U0001f4c5 Week", callback_data=f"week:{cik}"),
            InlineKeyboardButton("\U0001f5d3 Month", callback_data=f"month:{cik}"),
        ]
        for cik in settings.whale_ciks
    ]
    return InlineKeyboardMarkup(rows)


async def _help(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        await update.message.reply_text(_HELP_TEXT, parse_mode=ParseMode.HTML)


async def _list_whales(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        await update.message.reply_text(
            reports.build_whales_list(), parse_mode=ParseMode.HTML, reply_markup=_whales_keyboard()
        )


async def _portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    if not context.args:
        await update.message.reply_text(
            "Tap a whale below, or use <code>/portfolio &lt;index, CIK or name&gt;</code>.",
            parse_mode=ParseMode.HTML,
            reply_markup=_whales_keyboard(),
        )
        return
    cik = reports.resolve_whale(" ".join(context.args))
    if cik is None:
        await update.message.reply_text("Whale not found. Try /list_whales.")
        return
    await update.message.reply_text(
        reports.build_portfolio(cik), parse_mode=ParseMode.HTML, reply_markup=_whales_keyboard()
    )


async def _week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    cik = reports.resolve_whale(" ".join(context.args)) if context.args else None
    await update.message.reply_text(
        reports.build_week(cik), parse_mode=ParseMode.HTML, reply_markup=_whales_keyboard()
    )


async def _month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    cik = reports.resolve_whale(" ".join(context.args)) if context.args else None
    await update.message.reply_text(
        reports.build_month(cik), parse_mode=ParseMode.HTML, reply_markup=_whales_keyboard()
    )


async def _report(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is not None:
        await update.message.reply_text(
            reports.build_weekly_report(),
            parse_mode=ParseMode.HTML,
            reply_markup=_whales_keyboard(),
        )


async def _on_whale_action(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle taps on the inline quick-action buttons (e.g. ``portfolio:0001067983``)."""
    query = update.callback_query
    if query is None or not query.data:
        return

    action, _sep, cik = query.data.partition(":")
    settings = get_settings()
    builder = _ACTION_BUILDERS.get(action)
    if builder is None or cik not in settings.whale_ciks:
        await query.answer("Unknown action or whale.", show_alert=True)
        return

    await query.answer()
    text = builder(cik)
    if isinstance(query.message, Message):
        await query.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=_whales_keyboard()
        )


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
    application.add_handler(CallbackQueryHandler(_on_whale_action))
    return application
