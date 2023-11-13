import datetime as dt
import logging
import typing as t
from calendar import Calendar, day_abbr
from functools import wraps

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)


def escape_md(text: str | t.Any) -> str:
    """Escape special characters for Markdown"""
    if not isinstance(text, str):
        return escape_markdown(str(text), version=2)
    return escape_markdown(text, version=2)


def calendar_keyboard(date: dt.date) -> t.List[t.List[InlineKeyboardButton]]:
    """Return a list of `InlineKeyboardButton` that represents a monthly calendar"""

    def calendar_day_button(day: int | str) -> InlineKeyboardButton:
        """Return an `InlineKeyboardButton` to be used in a calendar keyboard"""
        if isinstance(day, str):
            return InlineKeyboardButton(text=day, callback_data=str(None))

        if day == 0:
            return InlineKeyboardButton(text="❌", callback_data=str(None))

        return InlineKeyboardButton(
            text=str(day),
            callback_data=dt.date(date.year, date.month, day),
        )

    calendar = [list(day_abbr)] + Calendar().monthdayscalendar(date.year, date.month)

    return [list(map(calendar_day_button, row)) for row in calendar]


def requires_login(func: t.Callable) -> t.Callable:
    """Requires a user to be logged in"""

    @wraps(func)
    async def wrapper(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> t.Any | None:
        """Wrapper function"""

        logger.info("Auth request from user with ID %s", update.effective_user.id)

        allowed_users = context.bot_data.get("ai_allowed_users")

        if allowed_users and update.effective_user.id in allowed_users:
            return await func(self, update, context)
        else:
            await update.message.reply_text(
                "You are not authorized to use the AI features of this bot\. Sorry\! 😞"
            )
            return ConversationHandler.END

    return wrapper
