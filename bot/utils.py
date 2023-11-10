import datetime as dt
import html
import json
import logging
import os
import traceback
import typing as t
from calendar import Calendar, day_abbr

from telegram import InlineKeyboardButton, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown


def escape_md(text: str | t.Any) -> str:
    """Escape special characters for Markdown"""
    if not isinstance(text, str):
        return escape_markdown(str(text), version=2)
    return escape_markdown(text, version=2)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log any error and send a warning message"""
    developer_user_id = os.environ.get("DEVELOPER_USER_ID")

    # First, log the error before doing anything else so we can see it in the logfile
    logging.error(
        msg="Exception raised while processing an update:", exc_info=context.error
    )

    # Format the traceback
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__ if context.error else None
    )
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Notify the developer about the exception
    if developer_user_id:
        await context.bot.send_message(
            chat_id=developer_user_id, text=message, parse_mode=ParseMode.HTML
        )


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
            callback_data=f"{day:02d}/{date.month:02d}/{date.year}",
        )

    calendar = [list(day_abbr)] + Calendar().monthdayscalendar(date.year, date.month)

    return [list(map(calendar_day_button, row)) for row in calendar]
