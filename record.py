"""
Bot functions for the `/record` command
"""
import datetime as dtm
import logging
import re
from collections import OrderedDict
from copy import deepcopy

from dateutil.parser import ParserError

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, ConversationHandler, Filters,
                          MessageHandler)

import utils
from constants import *

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
# A single 'Back' button
def back_button(text: str = 'Back') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup.from_button(InlineKeyboardButton(text=text, callback_data=str(BACK)))

# Entry-point keyboard
# ROW_1 = ('New record', 'Show data')
# ROW_2 = ('Back',)
entry_inline_kb = [
    [
        InlineKeyboardButton(text='➕ Add', callback_data=str(NEW)),
        InlineKeyboardButton(text='🗂️ Show', callback_data=str(SHOW)),
        InlineKeyboardButton(text='🗑 Remove', callback_data=str(CLEAR))
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
        InlineKeyboardButton(text='Cancel', callback_data=str(BACK))
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
        user_data['record'] = OrderedDict.fromkeys(RECORD_KEYS)
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

    reply_kb = InlineKeyboardMarkup.from_button(InlineKeyboardButton(text="Today", callback_data=dtm.datetime.today().strftime("%d/%m/%Y"))) if user_data['choice'] == 'date' else None
    query.edit_message_text(f"Enter the *{choice}* of the new record", reply_markup=reply_kb) 

    return REPLY

def store(update: Update, context: CallbackContext) -> str:
    """Store the provided info and ask for the next"""
    user_data = context.user_data.get('record')
    category = user_data['choice']

    if update.callback_query:
        update.callback_query.answer()
        data = update.callback_query.data
        reply_func = update.callback_query.edit_message_text
    else:
        data = update.message.text
        reply_func =  update.message.reply_text

    try:
        user_data.update(utils.parse_data(category, data))
    except ParserError:
        reply_func(f"⚠️ You entered an invalid date: '{data}'\. Please, try again\.")
        raise
    except:
        reply_func(f"⚠️ You entered invalid data: '{data}'\. Please, try again\.")
        raise
    else:
        del user_data['choice']
        reply_text = f"Done\! *{category.capitalize()}* has been recorded\. This is the new record so far:\n{utils.data_to_str(user_data)}"
        reply_func(reply_text, reply_markup=InlineKeyboardMarkup(record_inline_kb))
        logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    return INPUT

def save(update: Update, context: CallbackContext) -> str:
    """Display the final record and append it to the list that will be added to the spreadsheet"""
    query = update.callback_query
    query.answer()

    record = context.user_data.get('record')
    records = context.user_data.get('records')

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
    elif not record['amount'] or not record['reason']:
        query.edit_message_text(
            "The new record is *incomplete*\. You must add at least the *reason* and the *amount*\. Try again or cancel\.",
            reply_markup=InlineKeyboardMarkup(record_inline_kb)
        )
    else:
        # Add a date placeholder if key's empty
        # 'date' field must be the first
        if not record['date']:
            record['date'] = '-'

        # Add timestamp 
        record['recorded_on'] = dtm.datetime.now().strftime("%d-%m-%Y, %H:%M")

        # Append the current record
        # copy.deepcopy() is required because record is a dictionary
        records.append(deepcopy(record)) 

        query.edit_message_text(
            f"This is the record just saved:\n\n{utils.data_to_str(record)}",
            reply_markup=back_button('Ok')
        )
        
        # Reset the current record to an empty record
        context.user_data['record'] = OrderedDict.fromkeys(RECORD_KEYS)
        
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
        reply_markup=back_button('Cancel')
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
    records = context.user_data.get('records')
    query = update.callback_query
    query.answer()

    logger.info(f"context.user_data: {context.user_data}")
    
    if records:
        records_to_str = '\n\n'.join([f"__Record \#{i+1}__\n{utils.data_to_str(record, prefix='  ')}" for i, record in enumerate(records)])
        query.edit_message_text(
            text=f"*The records you saved so far:*\n\n{records_to_str}",
            reply_markup=back_button()
        )
    else:
        query.edit_message_text("You have saved *no records*\.", reply_markup=back_button())

    return SELECTING_ACTION

def clear_data(update: Update, context: CallbackContext) -> str:
    """Prompt the user which records to clear"""
    records = context.user_data.get('records')
    query = update.callback_query
    query.answer()

    if records:
        records_to_str = '\n\n'.join([f"__Record \#{i+1}__\n{utils.data_to_str(record, prefix='  ')}" for i, record in enumerate(records)])
        query.edit_message_text(
            "*Which records do you want to remove?* Use `/cancel` to stop\.\nExamples:\n"
            " \- `1-3` removes records *from* 1 *to* 3\n"
            " \- `1,3` removes *only* record 1 *and* 3\n"
            " \- `All` or `*` removes *every record*\.\n\n"
            f"*The records you saved so far:*\n\n{records_to_str}"
        )
        return REPLY
    else:
        query.edit_message_text("You have saved *no records*\.", reply_markup=back_button())
        return SELECTING_ACTION


def clear_records(update: Update, context: CallbackContext) -> str:
    """Clear one or multiple records"""
    records = context.user_data['records']
    num_records = len(records)
    text = update.message.text.strip()
    
    try:
        if '-' in text:
            first, last = [int(x.strip()) for x in text.split('-')]
            del records[first-1:last]
        elif ',' in text:
            record_idx = [int(x.strip())-1 for x in text.split(',')]
            # workaround to delete multiple elements of a list: create a new list omitting the elements to remove
            new_records = [i for j, i in enumerate(records) if j not in record_idx]
            context.user_data.update({'records': new_records})
        elif (idx := re.match(r'([0-9]+)', text)) is not None:
            idx = int(idx.group(0))
            del records[idx-1]
        elif re.match(r'(all|\*)', text, re.IGNORECASE):
            records.clear()
        else:
            raise ValueError
    except IndexError:
        update.message.reply_text(f"⚠️ Error while trying to delete a record that does not exist\.")
    except ValueError:
        update.message.reply_text("⚠️ Invalid syntax, try again\.\n\nExamples:\n"
            " \- `1-3` removes records *from* 1 *to* 3\n"
            " \- `1,3` removes *only* record 1 *and* 3\n"
            " \- `All` or `*` removes *every record*\.")
    else:
        update.message.reply_text(f"{num_records - len(context.user_data['records'])} record{' has' if (num_records - len(context.user_data['records'])) == 1 else 's have'} been removed\.")
    
    return STOPPING

def cancel(update: Update, context: CallbackContext) -> str:
    """Cancel the `record` command"""
    record = context.user_data.get('record')
    if record:
        record.clear()
    msg = "Action cancelled\. Use `/record` to start again or `/help` to know what I can do\.\nBye 👋"
    if (query := update.callback_query) is not None:
        query.answer()
        query.edit_message_text(msg)
    else:
        update.message.reply_text(msg)
    return STOPPING

def stop(update: Update, _: CallbackContext) -> int:
    """End the conversation altogether"""
    return utils.stop(command='record', action='add a new record', update=update)

# 'New record' handler (2nd level)
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
            ],
            QUICK_INPUT: [
                MessageHandler(Filters.text & ~Filters.command, quick_save),
            ],
            REPLY: [
                MessageHandler(Filters.text & ~Filters.command, store),
                CallbackQueryHandler(store, pattern=r'\d{2}\/\d{2}\/\d{4}')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(back_to_start, pattern=f'^{BACK}$'),
            CallbackQueryHandler(cancel, pattern=f'^{CANCEL}$'),
            CommandHandler('cancel', cancel),
        ],
        map_to_parent={
            END: SELECTING_ACTION,
            SELECTING_ACTION: SELECTING_ACTION,
            STOPPING: END,
        },
        name="add_record_second_level",
        persistent=False
)

# 'Remove record' handler
clear_data_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(clear_data, pattern=f'^{CLEAR}$'),
    ],
    states={
        REPLY: [
            MessageHandler(Filters.text & ~Filters.command, clear_records),
        ],
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
    name='remove_record_second_level'
)

# Top-level conversation handler
record_handler = ConversationHandler(
    entry_points=[
        CommandHandler('record', start)
    ],
    states = {
        SELECTING_ACTION: [
            new_record_handler,
            clear_data_handler,
            CallbackQueryHandler(show_data, pattern=f'^{SHOW}$'),
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
