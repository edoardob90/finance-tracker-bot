"""
Bot functions for the `/record` command
"""
import logging
import re
from typing import OrderedDict
from copy import deepcopy
from datetime import datetime as dt
from telegram import (
    Update,
    ParseMode,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ConversationHandler,
    CallbackContext,
    Filters,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
)
import gspread

from constants import *
import utils
import auth
import spreadsheet

# Enable logging
logging.basicConfig(format=log_format, level=log_level)
logger = logging.getLogger(__name__)

# A new record's fields
RECORD_KEYS = ('date',
            'reason',
            'amount',
            'currency',
            'account',
            'recorded_on'
            )

# Inline keyboard
ROW_1 = ('Date', 'Reason', 'Amount', 'Account')
ROW_2 = ('Save', 'Cancel')
BUTTONS = dict(
    zip(
        map(str, range(len(ROW_1 + ROW_2))),
        ROW_1 + ROW_2
    )
)

record_inline_kb = [
    utils.inline_kb_row(ROW_1),
    utils.inline_kb_row(ROW_2, offset=len(ROW_1))
]

def start(update: Update, context: CallbackContext) -> int:
    """Ask the user the details of a new record"""
    update.message.reply_markdown_v2(
        """Record a new expense/income\. *Remember* the follwing rules on the input data:
\- `Date` should be written as `dd-mm-yyyy` or `dd mm yyyy` or `dd mm yy`\. Example: `21-12-2021`
\- `Amount`: a _negative_ number is interpreted as an *expense*, while a _positive_ number as an *income*\. """
"""Example: `-150.0 EUR` means an expense of 150 euros\.
\- Currencies supported: EUR, CHF, USD\. You can also enter *a single letter*: E \= EUR, C \= CHF, U \= USD\.""",
        reply_markup=InlineKeyboardMarkup(record_inline_kb)
    )

    # Initialize user_data
    user_data = context.user_data
    if 'record' not in user_data:
        # a single empty record
        user_data['record'] = OrderedDict.fromkeys(RECORD_KEYS)
    # the list of all the records to append
    if 'records' not in user_data:
        user_data['records'] = []

    return CHOOSING

def prompt(update: Update, context: CallbackContext) -> int:
    """Ask user for info about a detail of a new record"""
    query = update.callback_query
    data = query.data
    user_data = context.user_data.get('record')
    user_data['choice'] = BUTTONS[data].lower()

    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")
    
    query.answer()
    query.edit_message_text(
        f"Enter the *{BUTTONS[data]}* of the new record",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return REPLY

def store(update: Update, context: CallbackContext) -> int:
    """Store the provided info and ask for the next"""
    user_data = context.user_data.get('record')
    
    data = update.message.text
    category = user_data['choice']
    user_data.update(utils.parse_data(category, data))
    del user_data['choice']

    update.message.reply_markdown_v2(
        f"Done\! *{category.capitalize()}* has been recorded\. This is the new record so far:\n"
        f"{utils.data_to_str(user_data)}",
        reply_markup=InlineKeyboardMarkup(record_inline_kb)
    )
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    return CHOOSING

def save(update: Update, context: CallbackContext) -> int:
    """Display the final record and append it to the list that will be added to the spreadsheet"""
    record = context.user_data.get('record')
    records = context.user_data.get('records')
    query = update.callback_query

    logger.info(f"user_data: {str(record)}, context.user_data: {str(context.user_data)}")

    if 'choice' in record:
        del record['choice']

    logger.info(f"record: {record}, records: {records}")

    # Append the current record
    record['recorded_on'] = dt.now().strftime("%d-%m-%Y, %H:%M")
    # Using deepcopy() because record is a mutable object!
    records.append(deepcopy(record))

    query.answer()
    query.edit_message_text(
        text=f"This is the record just saved:\n\n{utils.data_to_str(record)}\n\n"
              "You can add a new record with the command `/record`\. 👋",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # Reset the current record to an empty record
    # TODO: this will erase *EVERYTHING* from the dictionary, keys included. Maybe retain the keys?
    record.clear()
    
    logger.info(f"user_data: {str(record)}, context.user_data: {str(context.user_data)}")

    return ConversationHandler.END

def quick_save(update: Update, context: CallbackContext) -> None:
    """Quick-save a new record written on a single line. Fields must be comma-separated"""
    match = re.match(r'^!\s*(.*)', update.message.text)
    
    if not match:
        update.message.reply_markdown_v2("Invalid record format\! Remember: it *must* start with a `!` and each field must be separated by a comma\. Example: `!10-3-2022, Cena in pizzeria, -100 EUR, BPM`\.")
        return None 
    
    KEYS = ('date', 'reason', 'amount', 'account')
    record = OrderedDict(zip(
            KEYS,
            [x.strip() for x in match.group(1).split(',')]
        ))
    for key in KEYS:
        record.update(utils.parse_data(key, record[key]))

    record['recorded_on'] = dt.now().strftime("%d-%m-%Y, %H:%M")
    
    logger.info(f"User {update.message.from_user.id} added a quick record: {record}")

    # Needed if the user never ran the `/record` command
    if 'records' not in context.user_data:
        context.user_data['records'] = []    
    
    context.user_data['records'].append(record)

    logger.info(f"records: {context.user_data['records']}, record: {record}")

    update.message.reply_markdown_v2(
        f"This is the record just saved:\n\n{utils.data_to_str(record)}\n\n"
        "You can add a new record with the command `/record`\. 👋"
        )

def show_data(update: Update, context: CallbackContext) -> int:
    """Show the records saved so far"""
    records = context.user_data.get('records')

    logger.info(f"context.user_data: {context.user_data}")
    
    if records:
        records_to_str = '\n\=\=\=\n'.join(map(utils.data_to_str, records))
        logger.info("Records:\n{}".format(records))
        update.message.reply_markdown_v2(
            text=f"These are the records added so far:\n\n{records_to_str}\n\nThese have *not yet* been added to the spreadsheet\."
        )
    else:
        update.message.reply_text("You have not added any records yet!")

    return ConversationHandler.END

def add_to_spreadsheet(context: CallbackContext) -> None:
    """Daily task for `telegram.ext.JobQueue` to add records to the spreadsheet"""
    user_id, user_data = context.job.context
    records = user_data.get('records')
   
    logger.info(f"user_data: {str(user_data)}, records: {str(records)}")

    if not records:
        logger.info(f"Skipping scheduled task for user_id {user_id}: no records to append.")
        context.bot.send_message(user_id, "There are no records to append.", disable_notification=True)
    else:
        # Get the auth_data
        auth_data = user_data.get('auth')

        # Append the record to the spreadsheet
        if auth_data and auth_data['auth_is_done'] and auth_data['spreadsheet']['is_set']:
            # Get the credentials and open the connection with the spreadsheet
            creds = auth.oauth(credentials_file=CREDS, token_file=auth_data['token_file'])
            client = gspread.Client(auth=creds)
            ss = spreadsheet.Spreadsheet(
                    client=client,
                    spreadsheet_id=auth_data['spreadsheet']['id'],
                    sheet_name=auth_data['spreadsheet']['sheet_name']) 
            try:
                values = [list(record.values()) for record in records]
                ss.append_records(values)
            except:
                    logger.error("Something went wrong while appending the record to the spreadsheet.")
                    context.bot.send_message(user_id, text="Something went wrong while appending the record to the spreadsheet :-(", show_alert=True)
                    raise
            else:
                context.bot.send_message(
                    user_id,
                    text=f"On {dt.now().strftime('%d/%m/%Y, %H:%M')}, *{len(records)}* record{' has' if len(records) == 1 else 's have'} been successfully added to the spreadsheet\.",
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_notification=True
                )
                records.clear()
        else:
            context.bot.send_message(user_id, text="Cannot add records to the spreadsheet because the authorization was incomplete or you did not set the spreadsheet ID and/or name\. "
            "Use the command `/auth` complete the authentication or `/reset` to set the spreadsheet ID and/or name\.",
            parse_mode=ParseMode.MARKDOWN_V2)

    return None

def force_add_to_spreadsheet(update: Update, context: CallbackContext) -> None:
    """Force the append to the spreadsheet"""
    user_id = update.message.from_user.id

    if not context.user_data['records']:
        update.message.reply_text("There are no records to append.")
    else:
        utils.remove_job_if_exists(str(user_id) + '_force_append_data', context)
        context.job_queue.run_once(
            add_to_spreadsheet,
            when=1,
            context=(user_id, context.user_data),
            name=str(user_id) + '_force_append_data')

    return None

def clear(update: Update, context: CallbackContext) -> int:
    """Manually clear the records"""
    records = context.user_data.get('records')
    
    if records:
        update.message.reply_text(f"{len(records)} record{' has' if len(records) == 1 else 's have'} been cleared.")
        records.clear()

    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the `record` command"""
    user_data = context.user_data.get('record')
    user_data.clear()
    return utils.cancel(update, command='record')

# `record` handlers
# Conversation handler
conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('record', start),
            CommandHandler('show_data', show_data),
            CommandHandler('clear_data', clear),
            CommandHandler('append_data', force_add_to_spreadsheet)
        ],
        states={
            CHOOSING: [
                CallbackQueryHandler(
                    prompt,
                    pattern='^' + '$|^'.join(map(str, range(4))) + '$'
                ),
                CallbackQueryHandler(save, pattern='^4$'),
                CallbackQueryHandler(cancel, pattern='^5$')
            ],
            REPLY: [
                MessageHandler(
                   Filters.text & ~(Filters.command | Filters.regex('^(Save|Cancel)$')),
                   store
                )
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('show_data', show_data),
            CommandHandler('clear_data', clear),
            CommandHandler('append_data', force_add_to_spreadsheet),
        ],
        name="record_conversation",
        persistent=False
    )

# An additional handler for the quick-save command
quick_save_handler = MessageHandler(Filters.regex(r'^!'), quick_save)