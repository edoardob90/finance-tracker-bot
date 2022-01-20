#!/usr/bin/env python
# pylint: disable=C0116,W0613
import os
import traceback
import html
import json
import logging
import pytz
from datetime import time
from dateutil.parser import ParserError
from telegram import (
    Update,
    ParseMode,
)

from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    PicklePersistence,
    Defaults,
)

from constants import *
from utils import remove_job_if_exists
import record
import settings
# import summary

# Logging
logging.basicConfig(
    format=log_format, level=log_level
)
logger = logging.getLogger(__name__)

# Helpers functions
def error_handler(update: Update, context: CallbackContext) -> None:
    """Log any error and send a warning message"""
    # FIXME: this MUST NOT BE hard-coded!
    developer_user_id = os.environ.get('DEVELOPER_USER_ID')

    # First, log the error before doing anything else so we can see it in the logfile
    logger.error(msg="Exception raised while processing an update:", exc_info=context.error)

    # Format the traceback
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f'An exception was raised while handling an update\n'
        f'<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}'
        '</pre>\n\n'
        f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n'
        f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n'
        f'<pre>{html.escape(tb_string)}</pre>'
    )

    # Which kind of error?
    if isinstance(context.error, ParserError):
        update.message.reply_text("You entered an invalid date\. Try again\.")
    
    if developer_user_id:
        context.bot.send_message(chat_id=developer_user_id, text=message, parse_mode=ParseMode.HTML)

    return None

def start(update: Update, context: CallbackContext) -> None:
    """Start the bot"""
    context.user_data['start_over'] = False
    
    user_name = update.message.from_user.first_name
    update.message.reply_markdown_v2(
        f"""Hello {user_name}\! I'm a bot that can help you with you personal finances\. This is what I can do for you:

\- `/record`: record a new expense or income to your Finance Tracker spreadsheet
\- `/summary`: get a summary of your spreadsheet data
\- `/settings`: manage your settings: the connection with Google Sheets, the spreadsheet, and when to append the data

Use the `/help` command to get a more extensive help\.""")
    
    # # Setup a daily task to append to the spreadsheet all the records added so far
    # user_id = update.message.from_user.id
    # remove_job_if_exists(str(user_id) + '_append_data', context)
    # context.job_queue.run_daily(
    #     record.add_to_spreadsheet,
    #     time=time(23, 59, 59),
    #     context=(user_id, context.user_data),
    #     name=str(user_id) + '_append_data'
    # )
    
    # logger.info(f"Created a new daily task 'add_to_spreadsheet' for user {update.effective_user.full_name} ({update.effective_user.id})")

def print_help(update: Update, _: CallbackContext) -> None:
    """
    Print a more detailed help message
    
    Bot commands:

    /start - Start the bot
    /help - Print the help message
    /record - Add a new expense/income
    /query - Query your spreadsheet
    /show_data - Show the saved records
    /append_data - Add the records to the spreadsheet
    /clear_data - Erase the saved records
    /auth - Start the authentication process
    /auth_data - Show the status of the authentication
    /reset - Change the spreadsheet ID and/or name
    /cancel - Cancel the current command
    """
    update.message.reply_markdown_v2("""*Main commands:*

\- `/start`: start the bot and schedule a daily task to append the saved records to the spreadsheet\. The task runs every day at 23:59, and its time cannot be changed by the user \(*yet*\)\. You can manually append your data with the `/append_data` command \(see below\)

\- `/record`: record a new expense/income\. You can also quickly add a new record if you send me a message with the following format:

```
!<date>, <reason>, <amount>, <account>
```
The line *must* start with `!` and you *must* use commas \(`,`\) only to separate fields\.

\- `/auth`: start or check the authorization process to access Google Sheets

\- `/summary`: obtain a summary from your spreadsheet data

\- `/help`: print this message

*Other commands:*

\- `/show_data`: print all the saved records not yet appended to the spreadsheet

\- `/clear_data`: erase the saved records

\- `/append_data <when>`: append all the saved records to the spreadsheet\. If you say `/append_data now`, it will *immediately* add all your records to the spreadsheet \(if configured\), otherwise it will silently schedule a new task to be run at midnight\. It will also remove all the records saved in the bot's local storage

\- `/auth_data`: show the status of the authentication and the configured spreadsheet

\- `/reset`: reset the spreadsheet\. You can change the ID and the sheet name where to append your data""")

def main() -> None:
    """Create and run the bot with a polling mechanism"""
    
    # Bot's token
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        raise RuntimeError('Telegram bot token is required!')

    # Setup the persistence class
    persistence = PicklePersistence(filename=os.path.join(DATA_DIR, 'finance_tracker'),
                                    single_file=False,
                                    store_chat_data=False,
                                    store_bot_data=False)

    # Bot's defaults
    defaults = Defaults(parse_mode=ParseMode.MARKDOWN_V2, tzinfo=pytz.timezone('Europe/Rome'))

    # Create an Updater
    updater = Updater(TOKEN, persistence=persistence, defaults=defaults)
    
    # Get a dispatcher to register handlers
    dispatcher = updater.dispatcher

    # A couple of helpers handlers
    start_ = CommandHandler('start', start)
    help_ = CommandHandler('help', print_help)
    dispatcher.add_handler(start_)
    dispatcher.add_handler(help_)

    # Register the `/record` conversation handler
    dispatcher.add_handler(record.record_handler)
    # dispatcher.add_handler(record.quick_save_handler)

    # Register the `/settings` conversation handler
    dispatcher.add_handler(settings.settings_handler)

    # Register the `/summary` conversation handler
    # TODO: to be implemented
    # dispatcher.add_handler(CommandHandler('summary', summary.start))
    
    # Error handler
    dispatcher.add_error_handler(error_handler)

    # Run the bot
    if MODE == "webhook" and WEBHOOK_URL:
        updater.start_webhook(
            listen=LISTEN_URL,
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    else:
        updater.start_polling(poll_interval=1.0)
    
    updater.idle()

if __name__ == "__main__":
    main()