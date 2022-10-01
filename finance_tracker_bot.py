#!/usr/bin/env python
# pylint: disable=C0116,W0613,anomalous-backslash-in-string,line-too-long
"""
Main module
"""
import logging
import os

import pytz
from dotenv import load_dotenv
from ptbcontrib.postgres_persistence import PostgresPersistence
from ptbcontrib.ptb_sqlalchemy_jobstore import PTBSQLAlchemyJobStore
from telegram import ParseMode, Update
from telegram.ext import CallbackContext, CommandHandler, Defaults, Updater

import record
import settings
import utils
from constants import LOG_FORMAT

# Load the .env file
load_dotenv()

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# Variables related to the getUpdates mechanism: 'polling' (default) or 'webhook'
MODE = os.environ.get("MODE", "polling")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", None)
PORT = int(os.environ.get("PORT", "5000"))
LISTEN_URL = os.environ.get("LISTEN_URL", "127.0.0.1")


def start(update: Update, context: CallbackContext) -> None:
    """Start the bot"""
    context.user_data["start_over"] = False

    user_name = update.message.from_user.first_name
    update.message.reply_text(
        f"""Hello {user_name}\! I'm a bot that can help you with you personal finances\. This is what I can do for you:

\- `/record`: record a new expense or income to your Finance Tracker spreadsheet
\- `/summary`: get a summary of your spreadsheet data
\- `/settings`: manage your settings: the connection with Google Sheets, the spreadsheet, and when to append the data

Use the `/help` command to get a more extensive help\."""
    )


def print_help(update: Update, _: CallbackContext) -> None:
    """
    Print a more detailed help message

    Bot commands:

    /start - Start the bot
    /help - Print the help message
    /record - Enter the Record menu
    /summary - Enter the Summary menu
    /settings - Manage your settings
    /cancel - Cancel the current command
    /stop - Stop the bot altogether
    """
    update.message.reply_text(
        """*Supported commands:*

\- `/start`: start the bot

\- `/record`: enter the Record Menu: add a new expense/income, show the saved records, or clear your records

\- `/settings`: enter the Settings menu: login with your Google account, set the spreadsheet where to append your data, or schedule when I should append your records to the spreadsheet

\- `/summary`: enter the Summary menu where you can query the data saved in your spreadsheet

\- `/cancel`: cancel the current command

\- `/stop`: stop and restart the bot
"""
    )


def main() -> None:
    """Create and run the bot"""

    # Bot's token
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Telegram bot token is required!")

    # Set up the connection with the Postgres database
    db_name = os.environ.get("DB_NAME")
    db_user = os.environ.get("DB_USER")
    db_pass = os.environ.get("DB_PASS")
    if not (db_name and db_user and db_pass):
        raise RuntimeError("Either 'DB_NAME', 'DB_PASS', or 'DB_USER' are missing!")
    db_uri = f"postgresql://{db_user}:{db_pass}@localhost:5432/{db_name}"

    # Setup the persistence class
    persistence = PostgresPersistence(
        url=db_uri, store_chat_data=False, store_bot_data=False
    )
    # persistence = PicklePersistence(
    #   filename=os.path.join(DATA_DIR, 'finance_tracker'),
    #   single_file=False,
    #   store_chat_data=False,
    #   store_bot_data=False
    # )

    # Bot's defaults
    defaults = Defaults(
        parse_mode=ParseMode.MARKDOWN_V2, tzinfo=pytz.timezone("Europe/Rome")
    )

    # Create an Updater
    updater = Updater(token, persistence=persistence, defaults=defaults)

    # Get a dispatcher to register handlers
    dispatcher = updater.dispatcher
    # Add the Postgres jobstore
    dispatcher.job_queue.scheduler.add_jobstore(
        PTBSQLAlchemyJobStore(dispatcher=dispatcher, url=db_uri)
    )

    # A couple of helpers handlers
    start_ = CommandHandler("start", start)
    help_ = CommandHandler("help", print_help)
    dispatcher.add_handler(start_)
    dispatcher.add_handler(help_)

    # Register the `/record` conversation handler
    dispatcher.add_handler(record.record_handler)

    # Register the `/settings` conversation handler
    dispatcher.add_handler(settings.settings_handler)

    # Register the `/summary` conversation handler
    # TODO: to be implemented

    # Error handler
    dispatcher.add_error_handler(utils.error_handler)

    # Run the bot
    if MODE == "webhook" and WEBHOOK_URL:
        updater.start_webhook(
            listen=LISTEN_URL,
            port=PORT,
            url_path=token,
            webhook_url=f"{WEBHOOK_URL}/{token}",
        )
    else:
        updater.start_polling(poll_interval=0.5)

    updater.idle()


if __name__ == "__main__":
    main()
