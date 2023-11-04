import html
import json
import logging
import os
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log any error and send a warning message"""
    developer_user_id = os.environ.get("DEVELOPER_USER_ID")

    # First, log the error before doing anything else so we can see it in the logfile
    logging.error(
        msg="Exception raised while processing an update:", exc_info=context.error
    )

    # Format the traceback
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
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
