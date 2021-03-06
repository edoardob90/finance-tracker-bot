#!/usr/bin/env python
# pylint: disable=C0116,W0613
import os
import logging
import pytz
from telegram import (
    Update,
    ParseMode,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    Defaults,
)
from ptbcontrib.ptb_sqlalchemy_jobstore import PTBSQLAlchemyJobStore
from ptbcontrib.postgres_persistence import PostgresPersistence

from constants import *
import utils
import record
import settings

# Logging
logging.basicConfig(
    format=log_format, level=log_level
)
logger = logging.getLogger(__name__)

def start(update: Update, context: CallbackContext) -> None:
    """Start the bot"""
    context.user_data['start_over'] = False
    
    user_name = update.message.from_user.first_name
    update.message.reply_text(
        f"""Hello {user_name}\! I'm a bot that can help you with you personal finances\. This is what I can do for you:

\- `/record`: record a new expense or income to your Finance Tracker spreadsheet
\- `/summary`: get a summary of your spreadsheet data
\- `/settings`: manage your settings: the connection with Google Sheets, the spreadsheet, and when to append the data

Use the `/help` command to get a more extensive help\.""") 

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
    update.message.reply_text("""*Supported commands:*

\- `/start`: start the bot

\- `/record`: enter the Record Menu: add a new expense/income, show the saved records, or clear your records

\- `/settings`: enter the Settings menu: login with your Google account, set the spreadsheet where to append your data, or schedule when I should append your records to the spreadsheet

\- `/summary`: enter the Summary menu where you can query the data saved in your spreadsheet

\- `/cancel`: cancel the current command

\- `/stop`: stop and restart the bot
""")

def main() -> None:
    """Create and run the bot"""
    
    # Bot's token
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        raise RuntimeError('Telegram bot token is required!')

    # Set up the connection with the Postgres database
    DB_NAME = os.environ.get('DB_NAME')
    DB_USER = os.environ.get('DB_USER')
    DB_PASS = os.environ.get('DB_PASS')
    if not (DB_NAME and DB_USER and DB_PASS):
        raise RuntimeError("Either 'DB_NAME', 'DB_PASS', or 'DB_USER' are missing!")
    DB_URI = f'postgresql://{DB_USER}:{DB_PASS}@localhost:5432/{DB_NAME}'

    # Setup the persistence class
    persistence = PostgresPersistence(
        url=DB_URI,
        store_chat_data=False,
        store_bot_data=False
    )
    # persistence = PicklePersistence(
    #   filename=os.path.join(DATA_DIR, 'finance_tracker'),
    #   single_file=False,
    #   store_chat_data=False,
    #   store_bot_data=False
    # )

    # Bot's defaults
    defaults = Defaults(parse_mode=ParseMode.MARKDOWN_V2, tzinfo=pytz.timezone('Europe/Rome'))

    # Create an Updater
    updater = Updater(TOKEN, persistence=persistence, defaults=defaults)
    
    # Get a dispatcher to register handlers
    dispatcher = updater.dispatcher
    # Add the Postgres jobstore
    dispatcher.job_queue.scheduler.add_jobstore(
        PTBSQLAlchemyJobStore(dispatcher=dispatcher, url=DB_URI)
    )

    # A couple of helpers handlers
    start_ = CommandHandler('start', start)
    help_ = CommandHandler('help', print_help)
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
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    else:
        updater.start_polling(poll_interval=0.5)
    
    updater.idle()

if __name__ == "__main__":
    main()