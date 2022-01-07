#!/usr/bin/env python
# pylint: disable=C0116,W0613

import os
import traceback
import html
import json
import logging
from dotenv import load_dotenv
from datetime import time
from dateutil.parser import ParserError
from telegram import (
    Update,
    ParseMode,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
    PicklePersistence,
)

from constants import *
from utils import remove_job_if_exists
import record
import auth
import summary

# Load .env file
load_dotenv()

# Logging
logging.basicConfig(
    format=log_format, level=log_level
)
logger = logging.getLogger(__name__)

# Helpers functions
def error_handler(update: Update, context: CallbackContext) -> int:
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
        update.message.reply_text("You entered an invalid date. Try again.")
    
    if developer_user_id:
        context.bot.send_message(chat_id=developer_user_id, text=message, parse_mode=ParseMode.HTML)

    return CHOOSING

def start(update: Update, context: CallbackContext) -> None:
    """Start the bot"""
    user_name = update.message.from_user.first_name
    update.message.reply_text(
        f"""Hello {user_name}\! I'm a bot that can help you with you personal finances\. This is what I can do for you:

\- `/record`: record a new expense or income to your Finance Tracker spreadsheet
\- `/summary`: get a summary of your spreadsheet data \(*coming soon*\)
\- `/auth`: connect to Google Sheets with your Google account

Use the `/help` command to get a more extensive help\.
""",
    parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # Setup a daily task to append to the spreadsheet all the records added so far
    user_id = update.message.from_user.id
    remove_job_if_exists(str(user_id) + '_append_data', context)
    context.job_queue.run_daily(
        record.add_to_spreadsheet,
        time=time(22, 59), # UTC time
        context=(user_id, context.user_data),
        name=str(user_id) + '_append_data'
    )
    
    logger.info(f"Created a new daily task 'add_to_spreadsheet' for user {update.effective_user.full_name} ({update.effective_user.id})")

def print_help(update: Update, _: CallbackContext) -> None:
    """Print a more detailed help message"""
    help_msg = """*Main commands:*

\- `/start`: start the bot and schedule a daily task to append the saved records to the spreadsheet\. The task runs every day at 23:59, and its time cannot be changed \(*yet*\) by the user\. You can force the append action with the `/append_data` command \(see below\)
\- `/record`: record a new expense/income
\- `/auth`: start or check the authorization process to access Google Sheets
\- `/summary`: obtain a summary from your spreadsheet data \(*not implemented yet*\)
\- `/help`: print this message

*Other commands:*

\- `/show_data`: print all the saved records not yet appended to the spreadsheet
\- `/clear_data`: erase the saved records
\- `/append_data`: immediately append all the saved records to the spreadsheet\. It will also remove all the records saved in the bot's local storage
\- `/auth_data`: show the status of the authentication and the configured spreadsheet
\- `/reset`: reset the spreadsheet\. You can change the ID and the sheet name where to append your data"""

    update.message.reply_text(help_msg, parse_mode=ParseMode.MARKDOWN_V2)

def cancel(update: Update, _: CallbackContext) -> int:
    """Cancel the current action"""
    text = "Action has been cancelled\. Start again with the `/record` or `/summary` commands\. Bye\!"
    if update.callback_query:
        update.callback_query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        update.message.reply_text(text=text, parse_mode=ParseMode.MARKDOWN_V2)

    return ConversationHandler.END

def main() -> None:
    """Create and run the bot with a polling mechanism"""
    
    # Create an Updater with the bot's token
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    persistence = PicklePersistence(filename=os.path.join(DATA_DIR, 'finance_tracker'),
                                    single_file=False,
                                    store_chat_data=False,
                                    store_bot_data=False)
    if not TOKEN:
        raise RuntimeError('Telegram bot token is required!')

    updater = Updater(TOKEN, persistence=persistence)
    
    # Get a dispatcher to register handlers
    dispatcher = updater.dispatcher

    # A couple of helpers handlers
    start_ = CommandHandler('start', start)
    help_ = CommandHandler('help', print_help)
    dispatcher.add_handler(start_)
    dispatcher.add_handler(help_)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('record', record.start),
            CommandHandler('summary', summary.start),
            CommandHandler('show_data', record.show_data),
            CommandHandler('clear_data', record.clear),
            CommandHandler('append_data', record.force_add_to_spreadsheet)
        ],
        states={
            CHOOSING: [
                CallbackQueryHandler(
                    record.prompt,
                    pattern='^' + '$|^'.join(map(str, range(4))) + '$'
                    # [
                    #   '0': 'Date', '1': 'Amount', '2': 'Reason', '3': 'Account' <-- ROW_1
                    #   '4': 'Save', '5': 'Cancel' <-- ROW_2
                    # ]
                ),
                CallbackQueryHandler(record.save, pattern='^4$'),
                CallbackQueryHandler(cancel, pattern='^5$')
            ],
            REPLY: [
                MessageHandler(
                   Filters.text & ~(Filters.command | Filters.regex('^(Save|Cancel)$')),
                   record.store
                )
            ]
        },
        fallbacks=[
            CommandHandler('cancel', record.cancel),
            CommandHandler('show_data', record.show_data),
            CommandHandler('clear_data', record.clear),
            CommandHandler('append_data', record.force_add_to_spreadsheet),
            CommandHandler('help', print_help)
        ],
        name="main_conversation",
        persistent=False
    )

    # The main conversation handler
    dispatcher.add_handler(conv_handler)

    # The auth conversation handler
    auth_handler = ConversationHandler(
        entry_points=[
            CommandHandler('auth', auth.start),
            CommandHandler('auth_data', auth.show_data),
            CommandHandler('reset', auth.reset)
        ],
        states={
            CHOOSING: [
                CallbackQueryHandler(
                    auth.prompt,
                    pattern='^' + '$|^'.join(map(str, range(3))) + '$' # 'Auth code', 'Spreadsheet ID', 'Sheet name' buttons
                ),
                CallbackQueryHandler(auth.done, pattern='^3$'), # 'Done' button
                CallbackQueryHandler(cancel, pattern='^4$') # 'Cancel' button
            ],
            REPLY: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^(Done|Cancel)$')),
                    auth.store
                )
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('reset', auth.reset),
            CommandHandler('auth_data', auth.show_data),
            CommandHandler('help', print_help)
        ],
        name="auth_conversation",
        persistent=False
    )

    dispatcher.add_handler(auth_handler)
    
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