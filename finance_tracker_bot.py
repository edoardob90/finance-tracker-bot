#!/usr/bin/env python
# pylint: disable=C0116,W0613

import os
import traceback
import html
import json
import logging
from dotenv import load_dotenv
from dateutil.parser import ParserError
from telegram import (
    Update,
    ReplyKeyboardRemove,
    ParseMode
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
    PicklePersistence,
)
from constants import *
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
        update.message.reply_text("Whoa! You didn't enter a valid date. Try again.")
    
    if developer_user_id:
        context.bot.send_message(chat_id=developer_user_id, text=message, parse_mode=ParseMode.HTML)

    return CHOOSING

def start(update: Update, _: CallbackContext) -> None:
    """Print help message and a command list"""
    user_name = update.message.from_user.first_name
    update.message.reply_text(
        f"""Hello {user_name}\! I'm a bot that can help you with you personal finances\. This is what I can do for you:
\- `/record`: record a new expense or income to your Finance Tracker spreadsheet
\- `/summary`: get a summary of your spreadsheet data \(*coming soon*\)
\- `/auth`: connect to Google Sheets with your Google account \(should be done *first and only once*\)""",
    parse_mode=ParseMode.MARKDOWN_V2
    )

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the current action"""
    update.message.reply_text("Action has been cancelled\. Start again with the `/record` or `/summary` commands\. Bye\!",
    parse_mode=ParseMode.MARKDOWN_V2,
    reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END

def main() -> None:
    """Create and run the bot with a polling mechanism"""
    
    # Create an Updater with the bot's token
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    persistence = PicklePersistence(filename='finance_tracker',
                                    single_file=False,
                                    store_chat_data=False,
                                    store_bot_data=False)
    updater = Updater(TOKEN, persistence=persistence)
    
    # Get a dispatcher to register handlers
    dispatcher = updater.dispatcher

    # A couple of helpers handlers
    start_ = CommandHandler('start', start)
    help_ = CommandHandler('help', start)
    dispatcher.add_handler(start_)
    dispatcher.add_handler(help_)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('record', record.start_record),
            CommandHandler('summary', summary.start_summary)
            ],
        states={
            CHOOSING: [
                MessageHandler(
                    Filters.regex('^(Date|Amount|Reason|Account)$'),
                    record.prompt_record
                )
            ],
            CHOICE: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^(Save|Cancel)$')),
                    record.prompt_record
                )
            ],
            REPLY: [
                MessageHandler(
                   Filters.text & ~(Filters.command | Filters.regex('^(Save|Cancel)$')),
                   record.store_record 
                )
            ]
            },
        fallbacks=[
            MessageHandler(Filters.regex('^Save$'), record.save_record),
            MessageHandler(Filters.regex('^Cancel$'), cancel),
            CommandHandler("cancel", cancel),
        ],
        name="main_conversation",
        persistent=False
    )

    # The main conversation handler
    dispatcher.add_handler(conv_handler)

    # The auth conversation handler
    auth_handler = ConversationHandler(
        entry_points=[
            CommandHandler('auth', auth.start_auth)
        ],
        states={
            CHOOSING: [
                MessageHandler(
                    Filters.regex('^(Auth code|Spreadsheet ID|Sheet name)$'),
                    auth.auth_prompt
                )
            ],
            CHOICE: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^(Done|Cancel)$')),
                    auth.auth_prompt
                )
            ],
            REPLY: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^(Done|Cancel)$')),
                    auth.auth_store
                )
            ]
        },
        fallbacks=[
            MessageHandler(Filters.regex('^Done$'), auth.auth_done),
            MessageHandler(Filters.regex('^Cancel$'), cancel),
            CommandHandler('cancel', cancel)
        ],
        name="auth_conversation",
        persistent=False
    )

    dispatcher.add_handler(auth_handler)
    
    # Error handler
    dispatcher.add_error_handler(error_handler)

    # Run the bot
    # TODO: it might be better to switch from polling to webhook mechanism, but requires additional setup
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()