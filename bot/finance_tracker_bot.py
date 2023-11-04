import typing as t
from functools import partial

import pytz
from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Defaults,
)
from telegram.helpers import escape_markdown
from utils import error_handler

escape = partial(escape_markdown, version=2)


class FinanceTrackerBot:
    """A class representing the Finance Tracker bot"""

    def __init__(self, config: t.Dict[str, t.Any]) -> None:
        self.config = config
        self.commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Print the help message"),
            BotCommand("record", "Add a new record"),
            BotCommand("show", "Show and manage the saved records"),
            BotCommand("summary", "Obtain a summary of your records"),
            BotCommand("settings", "Manage your settings"),
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
                "  - Manager your settings with /settings\n\n"
                "Use /help to have a more detailed help."
            )

            await update.message.reply_text(escape(welcome_message))

        return

    async def help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Print the help message"""
        commands = [
            f"/{command.command} - {command.description}" for command in self.commands
        ]

        help_message = (
            "Here is a list of supported commands:\n\n"
            + "\n".join(commands)
            + "\n\nYou can always use a command followed by 'help' to obtain more information about it. "
            "For example, '/record help' will show you how to use the '/record' command."
        )

        if update.message:
            await update.message.reply_text(escape(help_message))

        return

    async def post_init(self, app: Application) -> None:
        """Post initialization"""
        await app.bot.set_my_commands(self.commands)

    def run(self) -> None:
        """Run the bot indefinitely"""
        defaults = Defaults(
            parse_mode=ParseMode.MARKDOWN_V2, tzinfo=pytz.timezone("Europe/Rome")
        )
        application = (
            ApplicationBuilder()
            .token(self.config["token"])
            .defaults(defaults)
            .post_init(self.post_init)
            .build()
        )

        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help))

        application.add_error_handler(error_handler)

        application.run_polling()
