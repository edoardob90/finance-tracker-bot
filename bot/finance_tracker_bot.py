import html
import json
import logging
import traceback
import typing as t
from itertools import chain

import pytz
from openai_api import OpenAI
from record import RecordHandler
from show import ShowHandler
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    BaseHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    PicklePersistence,
)
from utils import escape_md

# Set logger
logger = logging.getLogger(__name__)


class FinanceTrackerBot:
    """A class representing the Finance Tracker bot"""

    def __init__(self, config: t.Dict[str, t.Any], openai_api: OpenAI) -> None:
        self.openai_api = openai_api
        self.config = config
        self.commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Print the help message"),
            BotCommand("record", "Add a new record"),
            BotCommand("show", "Show and manage the saved records"),
            BotCommand("summary", "Obtain a summary of your records"),
            BotCommand("settings", "Manage your settings"),
            BotCommand("cancel", "Cancel the current operation"),
        ]

    async def start(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Start the bot"""
        if update.message:
            user_name = update.effective_user.first_name
            welcome_message = (
                f"Hello {user_name}, I'm a bot that helps you keep track of your finances. "
                "I can save your expenses and incomes in a spreadsheet and provide you with a summary of your records.\n\n"
                "Here is what you can do:\n\n"
                "  - You can add a new record with /record\n"
                "  - Use /show to get an overview of your records and manage them\n"
                "  - Manage your settings with /settings\n\n"
                "Use /help to have a more detailed help."
            )

            await update.message.reply_text(escape_md(welcome_message))

    async def help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Print the help message"""
        commands = [
            f"/{command.command} - {command.description}" for command in self.commands
        ]

        help_message = (
            "Here is a list of supported commands:\n\n"
            + "\n".join(commands)
            + "\n\nYou can always use a `?` followed by a command to obtain more information about it. "
            "For example, `?record` will show you how to use the '/record' command."
        )

        if update.message:
            await update.message.reply_text(escape_md(help_message))

        return

    async def error_handler(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Log any error and send a warning message"""
        developer_user_id = self.config.get("developer_user_id")

        # First, log the error before doing anything else so we can see it in the logfile
        logger.error(
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

    async def post_init(self, app: Application) -> None:
        """Post initialization"""
        # Populate/update the list of allowed users for the AI features
        ai_allowed_users: t.Set[int] = app.bot_data.setdefault(
            "ai_allowed_users", set()
        )
        if allowed_users := self.config.get("ai_allowed_users"):
            ai_allowed_users |= set(allowed_users)

        logger.info("Post-init: AI allowed user IDs: %s", ai_allowed_users)

        # Set the bot commands
        await app.bot.set_my_commands(self.commands)

    def run(self) -> None:
        """Run the bot indefinitely"""
        defaults = Defaults(
            parse_mode=ParseMode.MARKDOWN_V2, tzinfo=pytz.timezone("Europe/Rome")
        )

        persistence = PicklePersistence(
            filepath=self.config["data_dir"] / "finance_tracker_bot.pickle"
        )

        application = (
            ApplicationBuilder()
            .token(self.config["token"])
            .arbitrary_callback_data(True)
            .defaults(defaults)
            .persistence(persistence)
            .post_init(self.post_init)
            .build()
        )

        # Basic handlers
        application.add_handlers(
            {
                -1: [
                    CommandHandler("start", self.start),
                    CommandHandler("help", self.help),
                ]
            }
        )

        # Custom handlers
        # Just add each command's handlers to this list
        handlers: t.List[t.List[BaseHandler]] = [
            RecordHandler(self).handlers,
            ShowHandler(self).handlers,
        ]

        application.add_handlers(list(chain.from_iterable(handlers)))

        # Error handler
        application.add_error_handler(self.error_handler)

        application.run_polling()
