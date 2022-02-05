"""
Bot functions for the `/record` command
"""
import logging
from collections import OrderedDict
from copy import deepcopy
import datetime as dtm

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

from constants import *
import utils

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
    QUICK_INPUT,
    REPLY,
    STOPPING,
) = map(chr, range(5))

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
    QUICK_RECORD,
    CANCEL,
    BACK,
    STOP,
) = map(chr, range(5, 17))

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
        InlineKeyboardButton(text='🚪 Exit', callback_data=str(CANCEL))
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
        InlineKeyboardButton(text='Quick record', callback_data=str(QUICK_RECORD)),
        InlineKeyboardButton(text='Cancel', callback_data=str(CANCEL))
    ]
]

def start(update: Update, context: CallbackContext) -> str:
    """Entry point for the `/record` command"""
    keyboard = InlineKeyboardMarkup(entry_inline_kb)
    text = "🗳️ *Record menu*\nWhat do you want to do?"
    user_data = context.user_data
    
    if user_data.get('start_over'):
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    else:
        update.message.reply_text(text=text, reply_markup=keyboard)
    
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
        user_data['record'] = OrderedDict()
    # the list of all the records to append
    if 'records' not in user_data:
        user_data['records'] = []

    return INPUT

def prompt(update: Update, context: CallbackContext) -> str:
    """Ask user for info about a detail of a new record"""
    query = update.callback_query
    choice = BUTTONS[query.data]
    user_data = context.user_data.get('record')
    user_data['choice'] = choice.lower()

    query.answer()

    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    query.edit_message_text(f"Enter the *{choice}* of the new record") 

    return REPLY

def store(update: Update, context: CallbackContext) -> str:
    """Store the provided info and ask for the next"""
    user_data = context.user_data.get('record')
    
    data = update.message.text
    category = user_data['choice']
    user_data.update(utils.parse_data(category, data))
    del user_data['choice']

    update.message.reply_text(
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
    query.answer()

    logger.info(f"user_data: {str(record)}, context.user_data: {str(context.user_data)}")

    if 'choice' in record:
        del record['choice']

    # Warn the user when trying to save an empty or invalid record
    # 'reason' and 'amount' are compulsory, the other fields are optional
    if not record:
        query.edit_message_text(
            "The new record is empty 🤔\. Try again or cancel\.",
            reply_markup=InlineKeyboardMarkup(record_inline_kb)
        )
    elif 'amount' not in record or 'reason' not in record:
        query.edit_message_text(
            "The new record is *incomplete*\. You must tell me at least the *reason* and the *amount*\. Try again or cancel\.",
            reply_markup=InlineKeyboardMarkup(record_inline_kb)
        )
    else:
        # Add a date placeholder if key's empty
        # 'date' field must be the first
        if 'date' not in record:
            record = OrderedDict({'date': '-', **record})

        # Add timestamp 
        record['recorded_on'] = dtm.datetime.now().strftime("%d-%m-%Y, %H:%M")

        # Append the current record
        # copy.deepcopy() is required because record is a dictionary
        records.append(deepcopy(record)) 

        query.edit_message_text(
            f"This is the record just saved:\n\n{utils.data_to_str(record)}",
            reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Ok', callback_data=str(BACK)))
        )
        
        # Reset the current record to an empty record
        # TODO: this will erase *EVERYTHING* from the dictionary, keys included. Maybe retain the keys?
        record.clear()
        
        logger.info(f"user_data: {str(record)}, context.user_data: {str(context.user_data)}")

    return INPUT

def quick_input(update: Update, _: CallbackContext) -> str:
    """Enter the quick-save mode"""
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        """Okay, send me a message with the following format to quickly add a new record:

```
<date>, <reason>, <amount>, <account>
```
You must use commas \(`,`\) *only* to separate the fields\.""",
        reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Cancel', callback_data=str(CANCEL)))
    )
    return QUICK_INPUT

def quick_save(update: Update, context: CallbackContext) -> str:
    """Quick-save a new record written on a single line. Fields must be comma-separated"""
    record_data = [x.strip() for x in update.message.text.split(',')]
    
    # Fill in the new record with the input data
    record = OrderedDict.fromkeys(RECORD_KEYS)
    for key, val in zip(('date', 'reason', 'amount', 'account'), record_data):
        record.update(utils.parse_data(key, val))
    
    record['recorded_on'] = dtm.datetime.now().strftime("%d-%m-%Y, %H:%M")
    
    logger.info(f"User {update.message.from_user.id} added a quick record: {record}")
    
    context.user_data['records'].append(record)
    
    update.message.reply_text(
        f"This is the record just saved:\n\n{utils.data_to_str(record)}\n\n"
        "You can add a new record with the command `/record`\. 👋"
    )

    return STOPPING

def back_to_start(update: Update, context: CallbackContext) -> str:
    """Go back to the start menu"""
    update.callback_query.answer()
    context.user_data['start_over'] = True
    return start(update, context)

def show_data(update: Update, context: CallbackContext) -> str:
    """Show the records saved so far"""
    query = update.callback_query
    query.answer()
    keyboard = InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Back', callback_data=str(BACK)))

    logger.info(f"context.user_data: {context.user_data}")
    
    records = context.user_data.get('records')
    if records:
        records_to_str = '\n\=\=\=\n'.join(map(utils.data_to_str, records))
        
        logger.info("Records:\n{}".format(records))
        
        query.edit_message_text(
            text=f"These are the records added so far:\n\n{records_to_str}",
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
        query.edit_message_text("There are no records to clear\.", reply_markup=keyboard)

    return SELECTING_ACTION

def cancel(update: Update, context: CallbackContext) -> str:
    """Cancel the `record` command"""
    record = context.user_data.get('record')
    if record:
        record.clear()
    update.callback_query.answer()
    update.callback_query.edit_message_text("Use `/record` to start again or `/help` to know what I can do\.\nBye 👋")
    return STOPPING

def stop(update: Update, _: CallbackContext) -> int:
    """End the conversation altogether"""
    return utils.stop(command='record', action='add a new record', update=update)

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
                CallbackQueryHandler(quick_input, pattern=f'{QUICK_RECORD}$'),
                CallbackQueryHandler(back_to_start, pattern=f'^{BACK}$'),
            ],
            QUICK_INPUT: [
                MessageHandler(Filters.text & ~Filters.command, quick_save),
            ],
            REPLY: [
                MessageHandler(Filters.text & ~Filters.command, store)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(cancel, pattern=f'^{CANCEL}$'),
        ],
        map_to_parent={
            END: SELECTING_ACTION,
            SELECTING_ACTION: SELECTING_ACTION,
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
        ],
    },
    fallbacks=[
        CommandHandler('stop', stop),
        CallbackQueryHandler(back_to_start, pattern=f'^{BACK}$'),
    ],
    name="record_top_level",
    persistent=False
)