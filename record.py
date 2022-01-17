"""
Bot functions for the `/record` command
"""
import logging
import re
from tracemalloc import stop
from typing import OrderedDict
from copy import deepcopy
import datetime as dtm
from random import randrange

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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
# import auth
# import spreadsheet
# from spreadsheet import SpreadsheetError

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

# State definitions
(
    SELECTING_ACTION,
    INPUT,
    REPLY,
    STOPPING,
) = map(chr, range(4))

# Constants for CallbackQuery data
( 
    NEW,
    SHOW,
    CLEAR,
    DATE,
    REASON,
    AMOUNT,
    ACCOUNT,
    SAVE,
    CANCEL,
    BACK,
    STOP,
) = map(chr, range(4, 15))

# Shortcut to conversation end state
END = ConversationHandler.END

#
# Inline keyboards
#
# Entry-point keyboard
# ROW_1 = ('New record', 'Show data')
# ROW_2 = ('Back',)
entry_inline_kb = [
    [
        InlineKeyboardButton(text='➕ New record', callback_data=str(NEW)),
        InlineKeyboardButton(text='🗂️ Show records', callback_data=str(SHOW)),
        InlineKeyboardButton(text='🗑 Clear records', callback_data=str(CLEAR))
    ],
    [
        InlineKeyboardButton(text='Cancel', callback_data=str(CANCEL))
    ]
]

# 'New record' keyboard
# ROW_1 = ('Date', 'Reason', 'Amount', 'Account')
# ROW_2 = ('Save', 'Cancel')

BUTTONS = dict(
    zip(
       (DATE, REASON, AMOUNT, ACCOUNT, SAVE, CANCEL),
       ('Date', 'Reason', 'Amount', 'Account', 'Save', 'Cancel')
    )
)

record_inline_kb = [
    [
        InlineKeyboardButton(text='Date', callback_data=str(DATE)),
        InlineKeyboardButton(text='Reason', callback_data=str(REASON)),
        InlineKeyboardButton(text='Amount', callback_data=str(AMOUNT)),
        InlineKeyboardButton(text='Account', callback_data=str(ACCOUNT)),
    ],
    [
        InlineKeyboardButton(text='Save', callback_data=str(SAVE)),
        InlineKeyboardButton(text='Cancel', callback_data=str(CANCEL))
    ]
]

def start(update: Update, context: CallbackContext) -> str:
    """Entry point for the `/record` command"""
    keyboard = InlineKeyboardMarkup(entry_inline_kb)
    text = "*Record menu*\nWhat do you want to do?"
    user_data = context.user_data
    
    if user_data.get('start_over'):
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    else:
        update.message.reply_markdown_v2(text=text, reply_markup=keyboard)
    user_data['start_over'] = False
    
    return SELECTING_ACTION

def new_record(update: Update, context: CallbackContext) -> str:
    """Ask the user the details of a new record"""
    update.callback_query.edit_message_text(
        """Record a new expense/income\. *Remember* the follwing rules on the input data:

\- `Date` should be written as `dd-mm-yyyy` or `dd mm yyyy` or `dd mm yy`\. Example: `21-12-2021`

\- `Amount`: a _negative_ number is interpreted as an *expense*, while a _positive_ number as an *income*\. Example: `-150.0 EUR` means an expense of 150 euros\.\n\n"""
f"""\- Currencies supported: '{', '.join(set(CURRENCIES.values()))}'\. You can also enter *a single letter* or the symbol: E or € → EUR, U or $ → USD\.""",
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

    return INPUT

def prompt(update: Update, context: CallbackContext) -> str:
    """Ask user for info about a detail of a new record"""
    query = update.callback_query
    data = query.data
    user_data = context.user_data.get('record')
    user_data['choice'] = BUTTONS[data].lower()

    query.answer()

    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    query.edit_message_text(f"Enter the *{BUTTONS[data]}* of the new record") 

    return REPLY

def store(update: Update, context: CallbackContext) -> str:
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

    return INPUT

def save(update: Update, context: CallbackContext) -> str:
    """Display the final record and append it to the list that will be added to the spreadsheet"""
    record = context.user_data.get('record')
    records = context.user_data.get('records')
    query = update.callback_query

    logger.info(f"user_data: {str(record)}, context.user_data: {str(context.user_data)}")

    if 'choice' in record:
        del record['choice']

    query.answer()

    # Warn the user when trying to save an empty record
    if not record:
        query.edit_message_text(
            "The new record is empty, I don't know what to save 🤔\. Try again or cancel\.",
            reply_markup=InlineKeyboardMarkup(record_inline_kb)
        )
        return INPUT

    # Append the current record
    record['recorded_on'] = dtm.datetime.now().strftime("%d-%m-%Y, %H:%M")
    
    # Using deepcopy() because record is a dictionary (i.e., mutable object)
    records.append(deepcopy(record))

    query.edit_message_text(
        f"This is the record just saved:\n\n{utils.data_to_str(record)}\n\n"
        "You can add a new record with the command `/record`\. Bye 👋",
        reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Ok', callback_data=str(END)))
    )
    
    # Reset the current record to an empty record
    # TODO: this will erase *EVERYTHING* from the dictionary, keys included. Maybe retain the keys?
    record.clear()
    
    logger.info(f"user_data: {str(record)}, context.user_data: {str(context.user_data)}")

    return INPUT

def back_to_start(update: Update, context: CallbackContext) -> int:
    """Go back to the start menu of `/record`"""
    update.callback_query.answer()
    context.user_data['start_over'] = True
    return start(update, context)

def quick_save(update: Update, context: CallbackContext) -> None:
    """Quick-save a new record written on a single line. Fields must be comma-separated"""
    match = re.match(r'^!\s*(.*)', update.message.text)
    record_data = [x.strip() for x in match.group(1).split(',')]
    
    if not match:
        update.message.reply_markdown_v2("Invalid record format\! Remember: it *must* start with a `!` and each field must be separated by a comma\. Example: `!10-3-2022, Cena in pizzeria, -100 EUR, BPM`\.")
        return None 
    
    # Fill in the new record with the input data
    record = OrderedDict.fromkeys(RECORD_KEYS)
    for key, val in zip(('date', 'reason', 'amount', 'account'), record_data):
        record.update(utils.parse_data(key, val))
    
    logger.info(f"record_data: {record_data}, record: {record}")
    
    record['recorded_on'] = dtm.datetime.now().strftime("%d-%m-%Y, %H:%M")
    
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

def show_data(update: Update, context: CallbackContext) -> str:
    """Show the records saved so far"""
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Back', callback_data=str(BACK)))

    logger.info(f"context.user_data: {context.user_data}")
    
    records = context.user_data.get('records')
    if records:
        # Check if there's a scheduled job to append data
        jobs = context.job_queue.get_jobs_by_name(str(query.from_user.id) + '_append_data')
        next_time = f"{jobs[0].next_t.strftime('%d/%m/%Y, %H:%M')}" if (jobs and jobs[0] is not None) else 'never'
        records_to_str = '\n\=\=\=\n'.join(map(utils.data_to_str, records))
        
        logger.info("Records:\n{}".format(records))
        
        query.edit_message_text(
            text=f"These are the records added so far:\n\n{records_to_str}\n\nThese will be added to the spreadsheet on: *{next_time}*\.",
            reply_markup=keyboard
        )
    else:
        query.edit_message_text("You have not added any records yet\!", reply_markup=keyboard)

    return SELECTING_ACTION

def clear_data(update: Update, context: CallbackContext) -> str:
    """Manually clear the records"""
    keyboard = InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Back', callback_data=str(BACK)))
    records = context.user_data.get('records')
    query = update.callback_query
    query.answer()
    
    if records:
        query.edit_message_text(
            f"{len(records)} record{' has' if len(records) == 1 else 's have'} been cleared\.",
            reply_markup=keyboard
        )
        records.clear()
    else:
        query.edit_message_text("There are no data to clear\.", reply_markup=keyboard)

    return SELECTING_ACTION

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the `record` command"""
    record = context.user_data.get('record')
    if record:
        record.clear()
    update.callback_query.edit_message_text("Use `/record` to start again or `/help` to know what I can do\.\nBye 👋")
    return STOPPING

def stop(update: Update, context: CallbackContext) -> int:
    """End the conversation altogether"""
    text = "Use `/record` to add a new record or `/help` to know what I can do\.\nBye 👋"
    if update.callback_query:
        update.callback_query.edit_message_text(text=text)
    else:
        update.message.reply_text(text=text)
    return END

# `record` handlers
# Second-level conversation handler
new_record_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(new_record, pattern=f'^{NEW}$'),
        ],
        states={
            INPUT: [
                CallbackQueryHandler(
                    prompt,
                    pattern='^' + '$|^'.join((DATE, REASON, AMOUNT, ACCOUNT)) + '$'
                ),
                CallbackQueryHandler(save, pattern=f'^{SAVE}$'),
                CallbackQueryHandler(back_to_start, pattern=f'^' + str(END) + '$')
            ],
            REPLY: [
                MessageHandler(Filters.text & ~Filters.command, store)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(cancel, pattern=f'^{CANCEL}$')
        ],
        map_to_parent={
            END: SELECTING_ACTION,
            STOPPING: END,
        },
        name="record_second_level",
        persistent=False
)

# Top-level conversation handler
record_handler = ConversationHandler(
    entry_points=[
        CommandHandler('record', start)
    ],
    states = {
        SELECTING_ACTION: [
            new_record_handler,
            CallbackQueryHandler(show_data, pattern=f'^{SHOW}$'),
            CallbackQueryHandler(clear_data, pattern=f'^{CLEAR}$'),
            CallbackQueryHandler(stop, pattern=f'^{CANCEL}$'),
            CallbackQueryHandler(back_to_start, pattern=f'^{BACK}$'),
        ],
    },
    fallbacks=[
        CommandHandler('stop', stop)
    ],
    name="record_top_level",
    persistent=False
)

# An additional handler for the quick-save command
# quick_save_handler = MessageHandler(Filters.regex(r'^!'), quick_save)



# def add_to_spreadsheet(context: CallbackContext) -> None:
#     """Daily task for `telegram.ext.JobQueue` to add records to the spreadsheet"""
#     user_id, user_data = context.job.context
#     records = user_data.get('records')
   
#     logger.info(f"user_data: {str(user_data)}, records: {str(records)}")

#     if not records:
#         logger.info(f"Skipping scheduled task for user_id {user_id}: no records to append.")
#         context.bot.send_message(user_id, "There are no records to append\.", disable_notification=True)
#     else:
#         # Get the auth_data
#         auth_data = user_data.get('auth')

#         # Append the record to the spreadsheet
#         if auth.check_spreadsheet(auth_data):
#             # Get the credentials and open the connection with the spreadsheet
#             creds = auth.oauth(
#                 credentials_file=CREDS,
#                 token_file=auth_data['token_file'],
#                 user_data=auth_data
#             )
#             client = gspread.Client(auth=creds)
#             ss = spreadsheet.Spreadsheet(
#                     client=client,
#                     spreadsheet_id=auth_data['spreadsheet']['id'],
#                     sheet_name=auth_data['spreadsheet']['sheet_name']) 
#             try:
#                 values = [list(record.values()) for record in records]
#                 ss.append_records(values)
#             except:
#                     logger.error("Something went wrong while appending the record to the spreadsheet")
#                     context.bot.send_message(user_id, text="⚠️ Something went wrong while appending the record to the spreadsheet\. ⚠️")
#                     raise
#             else:
#                 context.bot.send_message(
#                     user_id,
#                     text=f"On {dtm.datetime.now().strftime('%d/%m/%Y, %H:%M')}, *{len(records)}* record{' has' if len(records) == 1 else 's have'} been successfully added to the spreadsheet\.",
#                     disable_notification=True
#                 )
#                 records.clear()
#         else:
#             context.bot.send_message(user_id, text="I cannot add the records to the spreadsheet because the authorization was incomplete or you did not set the spreadsheet ID and/or name\. "
#             "Use the command `/auth` to complete the authentication or `/reset` to set the spreadsheet ID and/or name\.")

#     return None

# def append_data(update: Update, context: CallbackContext) -> int:
#     """Force/schedule the append to the spreadsheet"""
#     user_id = update.message.from_user.id

#     if not context.user_data['records']:
#         update.message.reply_text("There are no records to append\.")
#     else:
#         if context.args and context.args[0] == 'now':
#             # Append immediately (within ~1 second)
#             utils.remove_job_if_exists(str(user_id) + '_force_append_data', context)
#             context.job_queue.run_once(
#                 add_to_spreadsheet,
#                 when=dtm.datetime.now() + dtm.timedelta(seconds=0.1),
#                 context=(user_id, context.user_data),
#                 name=str(user_id) + '_force_append_data')
            
#         else:
#             # Schedule the append at midnight
#             utils.remove_job_if_exists(str(user_id) + '_append_data', context)
#             context.job_queue.run_daily(
#                 add_to_spreadsheet,
#                 time=dtm.time(23, 59, randrange(0, 60)),
#                 context=(user_id, context.user_data),
#                 name=str(user_id) + '_append_data'
#             )

#             update.message.reply_markdown_v2(f"Your data will be added to the spreadsheet on {dtm.datetime.today().strftime('%d/%m/%Y')} at 23:59\.")

#     return ConversationHandler.END




## Create a reply markup with buttons corresponding to the 'Accounts' saved in the 'Categories' sheet of the spreadsheet
# if user_data['choice'] == 'account':
#     # Fetch the accounts list the first time
#     if 'accounts' not in context.user_data:
#         auth_data = context.user_data.get('auth')
#         if auth.check_spreadsheet(auth_data):
#             creds = auth.oauth(
#                 credentials_file=CREDS,
#                 user_data=auth_data,
#                 token_file=auth_data['token_file'])
            
#             ss = spreadsheet.Spreadsheet(
#                 client=gspread.Client(auth=creds),
#                 spreadsheet_id=auth_data['spreadsheet']['id'],
#                 sheet_name='Categories'
#             )

#             try:
#                 # 'Accounts' column must be between cell O3 and O30
#                 accounts = [x[0] for x in ss.get_records(range_='O3:O30')]
#             except SpreadsheetError:
#                 logger.warning("An error occurred while trying to fetch the 'Accounts' column in the 'Categories' sheet")
#             else:
#                 context.user_data['accounts'] = accounts
    
#     # Accounts have been already fetched from the spreadsheet
#     accounts = context.user_data.get('accounts')
    
#     # Delete the message associated with the callback query
#     query.delete_message()
    
#     reply_markup = ReplyKeyboardMarkup([accounts], one_time_keyboard=True) if accounts else None
#     context.bot.send_message(
#         query.from_user.id,
#         f"{'Choose' if reply_markup else 'Enter'} the *Account*",
#         reply_markup=reply_markup
#     )
# else:
#   ...