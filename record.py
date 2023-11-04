# pylint: disable=invalid-name,line-too-long,anomalous-backslash-in-string,trailing-whitespace,logging-fstring-interpolation
"""
Bot functions for the `/record` command
"""
import datetime as dtm
import logging
import os
import re
from collections import OrderedDict
from copy import deepcopy
from dotenv import load_dotenv

from dateutil.parser import ParserError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
)

import utils
from constants import CURRENCIES, LOG_FORMAT, RECORD_KEYS

# Env variables
load_dotenv()
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Enable logging
logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# State definitions
END = ConversationHandler.END
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
def back_button(text: str = "Back") -> InlineKeyboardMarkup:
    """A generic 'Back' button to use in multiple `InlineKeyboard` obj"""
    return InlineKeyboardMarkup.from_button(
        InlineKeyboardButton(text=text, callback_data=str(BACK))
    )


# Entry-point keyboard
# ROW_1 = ('New record', 'Show data')
# ROW_2 = ('Back',)
entry_inline_kb = [
    [
        InlineKeyboardButton(text="➕ Add", callback_data=str(NEW)),
        InlineKeyboardButton(text="🗂️ Show", callback_data=str(SHOW)),
        InlineKeyboardButton(text="🗑 Remove", callback_data=str(CLEAR)),
    ],
    [InlineKeyboardButton(text="🚪 Exit", callback_data=str(CANCEL))],
]

# 'New record' keyboard
# ROW_1 = ('Date', 'Reason', 'Amount', 'Account')
# ROW_2 = ('Save', 'Cancel')

BUTTONS = dict(
    zip(
        (DATE, REASON, AMOUNT, ACCOUNT, SAVE, CANCEL),
        ("Date", "Reason", "Amount", "Account", "Save", "Cancel"),
    )
)

record_inline_kb = [
    [
        InlineKeyboardButton(text="Date", callback_data=str(DATE)),
        InlineKeyboardButton(text="Reason", callback_data=str(REASON)),
        InlineKeyboardButton(text="Amount", callback_data=str(AMOUNT)),
        InlineKeyboardButton(text="Account", callback_data=str(ACCOUNT)),
    ],
    [
        InlineKeyboardButton(text="Save", callback_data=str(SAVE)),
        InlineKeyboardButton(text="Cancel", callback_data=str(BACK)),
    ],
    [
        InlineKeyboardButton(text="Quick record", callback_data=str(QUICK_RECORD)),
    ],
]


def start(update: Update, context: CallbackContext) -> str:
    """Entry point for the `/record` command"""
    keyboard = InlineKeyboardMarkup(entry_inline_kb)
    text = "🗳️ *Record menu*\nWhat do you want to do?"
    user_data = context.user_data

    if user_data.get("start_over"):
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    else:
        update.message.reply_text(text=text, reply_markup=keyboard)

    user_data["start_over"] = False

    return SELECTING_ACTION


def new_record(update: Update, context: CallbackContext) -> str:
    """Ask the user the details of a new record"""
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "Enter the detail of the new expense/income record\.\n\n"
        f"Supported currencies: *{', '.join(set(CURRENCIES.values()))}*\. You can type a single letter \(case *insensitive*\) or the symbol\. Example: E or € \= EUR\.",
        reply_markup=InlineKeyboardMarkup(record_inline_kb),
    )

    # Initialize user_data
    user_data = context.user_data
    # a single record
    user_data["record"] = OrderedDict.fromkeys(RECORD_KEYS)
    # the list of all the records to append
    if "records" not in user_data:
        user_data["records"] = []

    return INPUT


def prompt(update: Update, context: CallbackContext) -> str:
    """Ask user for info about a detail of a new record"""
    reply_kb = None
    query = update.callback_query
    query.answer()
    choice = BUTTONS[query.data]
    user_data = context.user_data.get("record")
    user_data["choice"] = choice.lower()

    logger.info(
        f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}"
    )

    # create the calendar keyboard of the current month
    calendar_keyboard = utils.calendar_keyboard(dtm.datetime.today())
    calendar_keyboard.append(
        [InlineKeyboardButton(text="Cancel", callback_data=f"{CANCEL}")]
    )

    if user_data["choice"] == "date":
        reply_kb = InlineKeyboardMarkup(calendar_keyboard)
    elif (
        user_data["choice"] == "account"
        and (prefs := context.user_data.get("accounts"))
    ) or (
        user_data["choice"] == "reason"
        and (prefs := context.user_data.get("categories"))
    ):
        reply_kb = InlineKeyboardMarkup(
            [
                list(
                    map(
                        lambda y: InlineKeyboardButton(
                            text=str(y), callback_data=str(y)
                        ),
                        prefs[x : x + 3],
                    )
                )
                for x in range(0, len(prefs), 3)
            ]
        )

    reply_msg = (
        "Choose a *Date* of the new record \(✅ \= date is *today*\) "
        if user_data["choice"] == "date"
        else f"Enter the *{choice}* of the new record"
    )
    query.edit_message_text(reply_msg, reply_markup=reply_kb)

    return REPLY


def store(update: Update, context: CallbackContext) -> str:
    """Store the provided info and ask for the next"""
    record_data = context.user_data.get("record")
    category = record_data["choice"]

    if (query := update.callback_query) is not None:
        query.answer()
        data = query.data
        reply_func = query.edit_message_text
    else:
        data = update.message.text
        reply_func = update.message.reply_text

    try:
        entered_data = utils.parse_data(category, data)
        # Check if the user set a preferred currency
        if (
            (default_cur := context.user_data.get("default_cur")) is not None
            and category == "amount"
            and entered_data["currency"] == "X"
        ):
            entered_data["currency"] = default_cur

        # Update the current record
        record_data.update(entered_data)

    except ParserError:
        reply_func(f"⚠️ Date entered is *invalid*: '{data}'\. Please, try again\.")
        raise
    except:
        reply_func(f"⚠️ Data entered are *invalid*: '{data}'\. Please, try again\.")
        raise
    else:
        del record_data["choice"]
        reply_text = f"Done\! *{category.capitalize()}* has been recorded\. This is the new record so far:\n{utils.data_to_str(record_data)}"
        reply_func(reply_text, reply_markup=InlineKeyboardMarkup(record_inline_kb))

        logger.info(
            f"user_data: {str(record_data)}, context.user_data: {str(context.user_data)}"
        )

    return INPUT


def save(update: Update, context: CallbackContext) -> str:
    """Display the final record and append it to the list that will be added to the spreadsheet"""
    query = update.callback_query
    query.answer()

    record = context.user_data.get("record")
    records = context.user_data.get("records")

    logger.info(
        f"user_data: {str(record)}, context.user_data: {str(context.user_data)}"
    )

    if "choice" in record:
        del record["choice"]

    # Warn the user when trying to save an empty or invalid record
    # 'reason' and 'amount' are compulsory, the other fields are optional
    if not record:
        query.edit_message_text(
            "The new record is empty 🤔\. Try again or cancel\.",
            reply_markup=InlineKeyboardMarkup(record_inline_kb),
        )
    elif not (record.get("amount") and record.get("reason")):
        query.edit_message_text(
            "The new record is *incomplete*\. You must add at least the *reason* and the *amount*\. Try again or cancel\.",
            reply_markup=InlineKeyboardMarkup(record_inline_kb),
        )
    else:
        # Add a date placeholder if key's empty
        # 'date' field must be the first
        if not record.get("date"):
            record["date"] = "-"

        # Add timestamp
        record["recorded_on"] = dtm.datetime.now().strftime("%d-%m-%Y, %H:%M")

        # Append the current record
        # copy.deepcopy() is required because record is a dictionary
        records.append(deepcopy(record))

        query.edit_message_text(
            f"This is the record just saved:\n\n{utils.data_to_str(record)}",
            reply_markup=back_button("Ok"),
        )

        # Reset the current record to an empty record
        context.user_data["record"] = OrderedDict.fromkeys(RECORD_KEYS)

        logger.info(
            f"user_data: {str(record)}, context.user_data: {str(context.user_data)}"
        )

    return INPUT


def quick_input(update: Update, _: CallbackContext) -> str:
    """Enter the quick-save mode"""
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        """Okay, send me a message with the following format to quickly add a new record:

```
<date>, <reason>, <amount>, <account>
```
You must use commas \(`,`\) *only* to separate the fields\. You can enter *multiple* records, one per line\.""",
        reply_markup=back_button("Cancel"),
    )
    return QUICK_INPUT


def quick_save(update: Update, context: CallbackContext) -> str:
    """Quick-save a new record written on a single line. Fields must be comma-separated"""
    record_data = [
        [x.strip() for x in line.split(",")] for line in update.message.text.split("\n")
    ]
    n_records = len(record_data)

    # Fill in the new record with the input data
    for record in record_data:
        _record = OrderedDict.fromkeys(RECORD_KEYS)
        for key, val in zip(("date", "reason", "amount", "account"), record):
            _record.update(utils.parse_data(key, val))
            if (
                key == "amount"
                and _record["currency"] == "X"
                and (default_cur := context.user_data.get("default_cur")) is not None
            ):
                _record["currency"] = default_cur
        # add timestamp
        _record["recorded_on"] = dtm.datetime.now().strftime("%d-%m-%Y, %H:%M")
        # append the record
        context.user_data["records"].append(_record)

    # logger.info(f"User {update.message.from_user.id} added a quick record: {record}")

    update.message.reply_text(
        f"*{n_records}* record{'s' if n_records > 1 else ''} {'have' if n_records > 1 else 'has'} been added\. This is the *last* record saved:\n\n{utils.data_to_str(_record)}\n\n"
        "You can add a new record with the command `/record`\. 👋"
    )

    return STOPPING


def back_to_start(update: Update, context: CallbackContext) -> str:
    """Go back to the start menu"""
    update.callback_query.answer()
    context.user_data["start_over"] = True
    return start(update, context)


def show_data(update: Update, context: CallbackContext) -> str:
    """Show the records saved so far"""
    records = context.user_data.get("records")
    query = update.callback_query
    query.answer()

    logger.info(f"context.user_data: {context.user_data}")

    if records:
        records_to_str = "\n\n".join(
            [
                f"__Record \#{i}__\n{utils.data_to_str(record, prefix='  ')}"
                for i, record in enumerate(records, start=1)
            ]
        )
        query.edit_message_text(
            text=f"*The records you saved so far:*\n\n{records_to_str}",
            reply_markup=back_button(),
        )
    else:
        query.edit_message_text(
            "You have saved *no records*\.", reply_markup=back_button()
        )

    return SELECTING_ACTION


def clear_data(update: Update, context: CallbackContext) -> str:
    """Prompt the user which records to clear"""
    records = context.user_data.get("records")
    query = update.callback_query
    query.answer()

    if records:
        records_to_str = "\n\n".join(
            [
                f"__Record \#{i+1}__\n{utils.data_to_str(record, prefix='  ')}"
                for i, record in enumerate(records)
            ]
        )
        query.edit_message_text(
            "*Which records do you want to remove?* Use `/cancel` to stop\.\nExamples:\n"
            " \- `1-3` removes records *from* 1 *to* 3\n"
            " \- `1,3` removes *only* record 1 *and* 3\n"
            " \- `All` or `*` removes *every record*\.\n\n"
            f"*The records you saved so far:*\n\n{records_to_str}"
        )
        return REPLY
    else:
        query.edit_message_text(
            "You have saved *no records*\.", reply_markup=back_button()
        )
        return SELECTING_ACTION


def clear_records(update: Update, context: CallbackContext) -> str:
    """Clear one or multiple records"""
    records = context.user_data["records"]
    num_records = len(records)
    text = update.message.text.strip()

    try:
        if "-" in text:
            first, last = [int(x.strip()) for x in text.split("-")]
            del records[first - 1 : last]
        elif "," in text:
            record_idx = [int(x.strip()) - 1 for x in text.split(",")]
            # workaround to delete multiple elements of a list: create a new list omitting the elements to remove
            new_records = [i for j, i in enumerate(records) if j not in record_idx]
            context.user_data.update({"records": new_records})
        elif (idx := re.match(r"([0-9]+)", text)) is not None:
            idx = int(idx.group(0))
            del records[idx - 1]
        elif re.match(r"(all|\*)", text, re.IGNORECASE):
            records.clear()
        else:
            raise ValueError
    except IndexError:
        update.message.reply_text(
            "⚠️ Error while trying to delete a record that does not exist\."
        )
    except ValueError:
        update.message.reply_text(
            "⚠️ Invalid syntax, try again\.\n\nExamples:\n"
            " \- `1-3` removes records *from* 1 *to* 3\n"
            " \- `1,3` removes *only* record 1 *and* 3\n"
            " \- `All` or `*` removes *every record*\."
        )
    else:
        update.message.reply_text(
            f"{num_records - len(context.user_data['records'])} record{' has' if (num_records - len(context.user_data['records'])) == 1 else 's have'} been removed\."
        )

    return STOPPING


def cancel(update: Update, context: CallbackContext) -> str:
    """Cancel the `record` command"""
    record = context.user_data.get("record")
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
    return utils.stop(command="record", action="add a new record", update=update)


# 'New record' handler (2nd level)
new_record_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(new_record, pattern=f"^{NEW}$"),
    ],
    states={
        INPUT: [
            CallbackQueryHandler(
                prompt, pattern="^" + "$|^".join((DATE, REASON, AMOUNT, ACCOUNT)) + "$"
            ),
            CallbackQueryHandler(save, pattern=f"^{SAVE}$"),
            CallbackQueryHandler(quick_input, pattern=f"{QUICK_RECORD}$"),
        ],
        QUICK_INPUT: [
            MessageHandler(Filters.text & ~Filters.command, quick_save),
        ],
        REPLY: [
            MessageHandler(Filters.text & ~Filters.command, store),
            CallbackQueryHandler(store, pattern=r"(\d{2}\/\d{2}\/\d{4}|\w+)"),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(back_to_start, pattern=f"^{BACK}$"),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        CommandHandler("cancel", cancel),
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END,
    },
    name="add_record_second_level",
    persistent=False,
)

# 'Remove record' handler
clear_data_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(clear_data, pattern=f"^{CLEAR}$"),
    ],
    states={
        REPLY: [
            MessageHandler(Filters.text & ~Filters.command, clear_records),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END,
    },
    name="remove_record_second_level",
)

# Top-level conversation handler
record_handler = ConversationHandler(
    entry_points=[CommandHandler("record", start)],
    states={
        SELECTING_ACTION: [
            new_record_handler,
            clear_data_handler,
            CallbackQueryHandler(show_data, pattern=f"^{SHOW}$"),
            CallbackQueryHandler(stop, pattern=f"^{CANCEL}$"),
        ],
    },
    fallbacks=[
        CommandHandler("stop", stop),
        CallbackQueryHandler(back_to_start, pattern=f"^{BACK}$"),
    ],
    name="record_top_level",
    persistent=False,
)
