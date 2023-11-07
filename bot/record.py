import datetime as dt
import logging
import typing as t
from enum import Enum

from dateutil.parser import ParserError
from models import Record, RecordSchema
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from utils import calendar_keyboard, escape_md


# Callback data
class CallbackData(Enum):
    def as_button(self) -> InlineKeyboardButton:
        """Return a button for a callback data"""
        return InlineKeyboardButton(text=self.value, callback_data=self)

    @staticmethod
    def button(name: str) -> InlineKeyboardButton:
        """Return a button for a callback data"""
        _enum = getattr(CallbackData, name.upper())
        return InlineKeyboardButton(text=_enum.value, callback_data=_enum)

    @classmethod
    def buttons(cls) -> t.List[InlineKeyboardButton]:
        """Return a list of buttons for a callback data"""
        return [member.as_button() for member in cls]


class RecordData(CallbackData):
    DATE = "📆 Date"
    DESCRIPTION = "🧾 Description"
    AMOUNT = "💰 Amount"
    ACCOUNT = "🏦 Account"


class Action(CallbackData):
    SAVE = "🔽 Save"
    BACK = "⬅️ Back"
    CANCEL = "❌ Cancel"
    OK = "🟢 OK"


# States
END = ConversationHandler.END
(INPUT, REPLY) = range(2)

# Keyboards
record_inline_kb = [
    RecordData.buttons()[:2],
    RecordData.buttons()[2:],
    [
        Action.SAVE.as_button(),
    ],
    [
        Action.CANCEL.as_button(),
    ],
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the record conversation"""
    context.user_data.setdefault("record", dict())
    context.user_data.setdefault("records", list())
    start_over: bool = context.user_data.setdefault("start_over", False)

    if context.args and "help" in context.args:
        return await print_help(update, context)
    else:
        msg = escape_md("🗳️ Enter the details of the new expense or income.")

        if start_over:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                msg, reply_markup=InlineKeyboardMarkup(record_inline_kb)
            )
        else:
            await update.message.reply_text(
                msg,
                reply_markup=InlineKeyboardMarkup(record_inline_kb),
            )

        context.user_data["start_over"] = False

    return INPUT


async def print_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    """Print the help message"""
    help_msg = (
        "*ABOUT THE* `/record` *COMMAND*\n\n"
        + escape_md(
            "Use this command to add a new record. "
            "You will be asked for the following information: "
            "date, description, amount, and account. "
            "Use the buttons to enter the information. "
            "When you are done, use the 'Save' button to save the record "
            "or the 'Cancel' button to discard it.\n\n"
            "Notes about the fields:\n\n"
        )
        + "  \- *Date*: can be entered as a date in any well\-known format, "
        "for example, '01/01/2021', '2021\-01\-01', or '6 nov 2023'\n\n"
        "  \- *Description*: a short description of the record\n\n"
        "  \- *Amount*: the amount of the record, including the currency\. "
        " A negative amount is an expense, a positive amount an income\. "
        "The currency can be entered as a currency code, for example, 'EUR', 'USD',"
        " or as a symbol, for example, '€', '$', or '£'\. "
        "You can also use a single letter for brevity: 'e' or 'E' for 'EUR', 'u' for 'USD', etc\. "
        "If you don't specify a currency, your default currency will be used \(if set\)\n\n"
        "  \- *Account*: the account associated with the record: 'Cash', 'Credit Card', etc\."
    )

    await update.message.reply_text(help_msg)

    return END


async def input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask user for info about a detail of a new record"""
    reply_kb = None

    if query := update.callback_query:
        await query.answer()

        choice = t.cast(CallbackData, query.data)
        context.user_data["choice"] = choice.value

        if choice == RecordData.DATE:
            calendar_kb = calendar_keyboard(dt.datetime.now().date())
            calendar_kb.append([Action.CANCEL.as_button()])
            reply_kb = InlineKeyboardMarkup(calendar_kb)

        elif choice == RecordData.ACCOUNT:
            # TODO: account picker
            pass

        await query.edit_message_text(
            f"Enter the *{choice.value}* of the new record\.", reply_markup=reply_kb
        )

    return REPLY


async def store(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store a property of a new record or the whole record"""
    if not (_record := context.user_data.get("record")):
        record = Record()
    else:
        record = t.cast(Record, RecordSchema().load(_record))

    if query := update.callback_query:
        # Here we are handling the date of the record, a callback query
        assert (
            context.user_data["choice"] == RecordData.DATE.value
        ), "Mismatch between choice and callback data"

        await query.answer()
        reply_func = query.edit_message_text
        data = str(query.data)
        try:
            record.date = data
        except ParserError as err:
            logging.error("Error while parsing the date: %s", err)
            return REPLY
    else:
        # All the other properties of the record are text messages
        data = str(update.message.text)
        reply_func = update.message.reply_text

        if context.user_data["choice"] == RecordData.DESCRIPTION.value:
            record.description = data
        elif context.user_data["choice"] == RecordData.AMOUNT.value:
            record.amount = data
        elif context.user_data["choice"] == RecordData.ACCOUNT.value:
            record.account = data

    await reply_func(
        f"✅ *{context.user_data['choice']}* has been recorded: {escape_md(data)}\. "
        f"This is the new record so far:\n\n{record}",
        reply_markup=InlineKeyboardMarkup(record_inline_kb),
    )

    # Update the record in the user data
    _record.update(RecordSchema().dump(record))

    logging.info("Current record: %s", _record)

    return INPUT


async def save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save the record"""
    record = t.cast(Record, RecordSchema().load(context.user_data["record"]))
    record.recorded_at = dt.datetime.now()

    if query := update.callback_query:
        await query.answer()

        try:
            record.validate()
        except ValueError as err:
            logging.error("Record validation failed: %s", err)

            await query.edit_message_text(
                f"⚠️ The record is not valid\. {err}",
                reply_markup=InlineKeyboardMarkup(record_inline_kb),
            )
        else:
            context.user_data["records"].append(RecordSchema().dump(record))
            context.user_data["record"].clear()

            await query.edit_message_text(
                escape_md("✅ The record has been saved.\n\n") + str(record),
                reply_markup=InlineKeyboardMarkup.from_button(Action.OK.as_button()),
            )

    logging.info("Records saved: %s", context.user_data["records"])

    return INPUT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the record conversation"""
    reply_text = (
        "🛑 Action *cancelled*\. "
        "You can use `/record` again or use `/record help` for more information\."
    )

    if record := context.user_data.get("record"):
        record.clear()

    if query := update.callback_query:
        await query.answer()
        await query.edit_message_text(reply_text)
    else:
        await update.message.reply_text(reply_text)

    return END


async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to the main menu"""
    context.user_data["start_over"] = True
    await update.callback_query.answer()
    return await start(update, context)


record_handler = ConversationHandler(
    entry_points=[CommandHandler("record", start)],
    states={
        INPUT: [
            CallbackQueryHandler(
                input,
                pattern=lambda data: data in RecordData,
            ),
            CallbackQueryHandler(save, pattern=lambda data: data == Action.SAVE),
        ],
        REPLY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, store),
            CallbackQueryHandler(store, pattern=r"(\d{2}\/\d{2}\/\d{4}|\w+)"),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel, pattern=lambda data: data == Action.CANCEL),
        CallbackQueryHandler(
            back_to_start, pattern=lambda data: data in (Action.BACK, Action.OK)
        ),
        CommandHandler("cancel", cancel),
    ],
    persistent=False,
    name="record_handler",
)
