import typing as t

import pytz
from openai_api import OpenAI
from record import RecordHandler
from show import ShowHandler
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Defaults,
    PicklePersistence,
)
from utils import error_handler, escape_md


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

        return

    async def help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Print the help message"""
        commands = [
            f"/{command.command} - {command.description}" for command in self.commands
        ]

        help_message = (
            "Here is a list of supported commands:\n\n"
            + "\n".join(commands)
            + "\n\nYou can always use a `?` followed by a command to obtain more information about it. "
            "For example, `? record` will show you how to use the '/record' command."
        )

        if update.message:
            await update.message.reply_text(escape_md(help_message))

        return

    async def post_init(self, app: Application) -> None:
        """Post initialization"""
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
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help))

        # Custom handlers
        record = RecordHandler(self)
        application.add_handlers(record.handlers)

        show = ShowHandler(self)
        application.add_handlers(show.handlers)

        # Error handler
        application.add_error_handler(error_handler)

        application.run_polling()
