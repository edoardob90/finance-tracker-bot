import datetime as dt
import logging
import typing as t
from calendar import month_name
from tempfile import NamedTemporaryFile

from currencies import CURRENCIES, CurrencyParsingError
from dateutil.parser import ParserError
from handlers import HandlerBase
from models import Amount, CallbackData, Record
from telegram import InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PrefixHandler,
    filters,
)
from utils import calendar_keyboard, escape_md

if t.TYPE_CHECKING:
    from finance_tracker_bot import FinanceTrackerBot


# Callback data for the record conversation
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
    PREV = "⏪"
    NEXT = "⏩"


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

calendar_keyboard_buttons = [
    [Action.PREV.as_button(), Action.NEXT.as_button()],
    [Action.CANCEL.as_button()],
]


class RecordHandler(HandlerBase):
    """A class for the /record command"""

    def __init__(self, bot: "FinanceTrackerBot") -> None:
        super().__init__(bot)
        self._command = "record"
        self._handlers = [
            PrefixHandler(["?", "? "], self._command, self.print_help),
            ConversationHandler(
                entry_points=[
                    CommandHandler(self._command, self.start),
                ],
                states={
                    INPUT: [
                        CallbackQueryHandler(
                            self.input,
                            pattern=lambda data: data in RecordData,
                        ),
                        MessageHandler(
                            ~filters.COMMAND & (filters.TEXT | filters.VOICE),
                            self.input_natural_language,
                        ),
                        CallbackQueryHandler(
                            self.save, pattern=lambda data: data == Action.SAVE
                        ),
                    ],
                    REPLY: [
                        MessageHandler(filters.TEXT & ~filters.COMMAND, self.store),
                        CallbackQueryHandler(
                            self.store, pattern=lambda data: isinstance(data, dt.date)
                        ),
                        CallbackQueryHandler(
                            self.change_calendar_keyboard,
                            pattern=lambda data: data in (Action.PREV, Action.NEXT),
                        ),
                    ],
                },
                fallbacks=[
                    CallbackQueryHandler(
                        self.cancel, pattern=lambda data: data == Action.CANCEL
                    ),
                    CallbackQueryHandler(
                        self.back_to_start,
                        pattern=lambda data: data in (Action.BACK, Action.OK),
                    ),
                    CommandHandler("cancel", self.cancel),
                ],
                persistent=False,
                name="record_handler",
            ),
        ]

    async def print_help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Print the help message"""
        supported_currencies = escape_md(
            "\n".join(
                f"{key}: {', '.join(value['aliases'])}"
                for key, value in CURRENCIES.items()
            )
        )

        help_msg = (
            "🆘 *HELP ABOUT THE* `/record` *COMMAND*\n\n"
            "Use this command to add a new record\. "
            "You will be asked for the following information: "
            "date, description, amount, and account\. "
            "Use the buttons to enter the information\. "
            "When you are done, use the 'Save' button to save the record "
            "or the 'Cancel' button to discard it\.\n\n"
            "__About the fields:__\n\n"
            "📅 *Date \(required\)*\n"
            "You can use any well\-known format, "
            "for example, '01/01/2021', '2021\-01\-01', or '6 nov 2023'\. "
            "You can also pick a date from the calendar keyboard\.\n\n"
            "🧾 *Description* \(_optional_\)\n"
            "A short description of the record\.\n\n"
            "💰 *Amount \(required\)*\n"
            "The amount of the record, including the currency\. "
            " A negative amount is an expense, a positive amount an income\. "
            "The currency can be entered as a currency code, for example, 'EUR', 'USD',"
            " or as a symbol, for example, '€', '$', or '£'\. "
            "You can also use common abbreviations: "
            "'euro' for 'EUR', 'us$' for 'USD', 'Sfr\.' for 'CHF, etc\.\n"
            "You can set your default currency in the settings\.\n\n"
            "🏦 *Account \(required\)*\n The account associated with the record\. "
            "You can set your preferred account\(s\) in the settings\.\n\n"
            "__Supported currencies:__\n\n"
            f"{supported_currencies}"
        )

        await update.message.reply_text(help_msg)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start the record conversation"""
        context.user_data.setdefault("selected_month_year", None)
        context.user_data.setdefault("keyboard_type", None)
        context.user_data.setdefault("choice", None)
        context.user_data.setdefault("record", dict())
        context.user_data.setdefault("records", list())
        start_over: bool = context.user_data.setdefault("start_over", False)

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

    async def input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Ask user for info about a detail of a new record"""
        reply_kb = None

        if query := update.callback_query:
            await query.answer()

            choice = t.cast(CallbackData, query.data)
            context.user_data["choice"] = choice.value

            # Default reply text
            reply_text = f"Enter the *{choice.value}* of the new record\."

            if choice == RecordData.DATE:
                calendar_kb = calendar_keyboard(dt.date.today())
                calendar_kb.extend(calendar_keyboard_buttons)
                reply_kb = InlineKeyboardMarkup(calendar_kb)
                context.user_data["keyboard_type"] = "calendar"

                if not context.user_data["selected_month_year"]:
                    today = dt.date.today()
                    context.user_data["selected_month_year"] = today.year, today.month

                year, month = context.user_data["selected_month_year"]

                reply_text = (
                    "Enter the *Date* of the new record\. "
                    f"Current calendar: *{month_name[month]} {year}*\."
                )

            elif choice == RecordData.ACCOUNT:
                # TODO: account picker
                context.user_data["keyboard_type"] = "account"
                pass

            await query.edit_message_text(reply_text, reply_markup=reply_kb)

        return REPLY

    async def input_natural_language(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int | None:
        """Add a new record using natural language"""
        try:
            if audio := update.message.voice:
                logging.info("Natural language input is a voice message")

                with NamedTemporaryFile(suffix=".ogg") as tmp_file:
                    audio_file = await audio.get_file()
                    await audio_file.download_to_memory(tmp_file)  # type: ignore
                    tmp_file.seek(0)

                    transcription = await self.bot.openai_api.get_transcription(
                        tmp_file.file
                    )

                    logging.info("Transcription response: %s", transcription)
                    query = str(transcription.text)
            else:
                logging.info("Natural language input is a text message")
                query = str(update.message.text)

            response = await self.bot.openai_api.get_chat_response(query)
        except Exception as err:
            logging.error("Error while calling the OpenAI API: %s", err)
            await update.message.reply_text(
                "⚠️ Something went wrong\. Please, try again with `/record`\."
            )
            return END
        else:
            logging.info("OpenAI response: %s", response)

            if (
                isinstance(response.choices, list)
                and (response.choices[0].message.tool_calls)
                and (
                    function_call := response.choices[0].message.tool_calls[0].function
                )
            ):
                record = Record.model_validate_json(function_call.arguments)

                context.user_data["record"].update(record.model_dump())
                logging.info("Record saved to user_data: %s", record.model_dump())

                await update.message.reply_text(
                    f"🤖 Is this the record you want to save?\n\n{record}",
                    reply_markup=InlineKeyboardMarkup(record_inline_kb),
                )

    async def change_calendar_keyboard(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Change the month shown on the calendar inline keyboard"""
        if query := update.callback_query:
            await query.answer()

            today = dt.datetime.today()

            if not context.user_data["selected_month_year"]:
                year, month = today.year, today.month

            year, month = context.user_data["selected_month_year"]

            next_or_prev_month = 1 if query.data == Action.NEXT else -1
            month += next_or_prev_month

            if month > 12:
                month = 1
                year += 1
            elif month < 1:
                month = 12
                year -= 1

            context.user_data["selected_month_year"] = year, month

            calendar_kb = calendar_keyboard(today.replace(month=month, year=year))
            calendar_kb.extend(calendar_keyboard_buttons)

            await query.edit_message_text(
                (
                    "Enter the *Date* of the new record\. "
                    f"Current calendar: *{month_name[month]} {year}*\."
                ),
                reply_markup=InlineKeyboardMarkup(calendar_kb),
            )

    async def store(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Store a property of a new record or the whole record"""
        record = Record()
        reply_method = None
        reply_kb = None

        if _record := context.user_data.get("record"):
            record = Record.model_validate(_record)

        logging.info("Record read from user_data: %s", record.model_dump())

        try:
            # Pick the right keyboard to show
            if context.user_data["keyboard_type"] == "calendar":
                year, month = context.user_data["selected_month_year"]

                reply_kb = calendar_keyboard(
                    dt.date.today().replace(year=year, month=month)
                )
                reply_kb.extend(calendar_keyboard_buttons)
            elif context.user_data["keyboard_type"] == "account":
                # TODO: account keyboard
                pass
            else:
                reply_kb = record_inline_kb

            if query := update.callback_query:
                # Here we are handling the date of the record, a callback query
                assert (
                    context.user_data["choice"] == RecordData.DATE.value
                ), "Mismatch between choice and callback data"

                await query.answer()
                reply_method = query.edit_message_text
                data = {"date": str(query.data)}
            else:
                # All the other properties of the record are text messages
                _data = str(update.message.text)
                reply_method = update.message.reply_text

                if context.user_data["choice"] == RecordData.DESCRIPTION.value:
                    data = {"description": _data}
                elif context.user_data["choice"] == RecordData.AMOUNT.value:
                    data = {"amount": Amount(value=_data)}
                elif context.user_data["choice"] == RecordData.ACCOUNT.value:
                    data = {"account": _data}
                else:
                    logging.info(
                        "User '%s' entered a date manually: %s",
                        update.effective_user,
                        _data,
                    )
                    data = {"date": _data}

            # Validate the record and catch any errors
            record = Record.model_validate({**record.model_dump(), **data})

        except ParserError as err:
            logging.error("Date parsing failed: %s", err)
            msg = f"⚠️ The date is not valid: {escape_md(err)}"
        except CurrencyParsingError as err:
            logging.error("Currency parsing failed: %s", err)
            msg = f"⚠️ The amount is not valid: {escape_md(err)}"
        except Exception as err:
            logging.error("Record validation failed: %s", err)
            msg = "⚠️ The record is not valid\."
        else:
            # All good, save the record
            context.user_data["keyboard_type"] = None
            reply_kb = record_inline_kb

            await reply_method(
                f"✅ *{context.user_data['choice']}* has been recorded\. "
                f"This is the new record so far:\n\n{record}",
                reply_markup=InlineKeyboardMarkup(reply_kb),
            )

            # Update the record in the user data
            _record.update(record.model_dump())

            logging.info("Record saved to user_data: %s", _record)

            return INPUT

        # If we are here, something went wrong. Reply with an error message
        if reply_method:
            await reply_method(
                msg, reply_markup=InlineKeyboardMarkup(reply_kb) if reply_kb else None
            )

        return INPUT

    async def save(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Save the record"""
        record = Record.model_validate(context.user_data["record"])
        record.recorded_at = dt.datetime.now()

        if query := update.callback_query:
            await query.answer()

            try:
                record.check_required_fields()
            except Exception as err:
                logging.error("Record validation failed: %s", err)

                await query.edit_message_text(
                    f"⚠️ The record is not valid\. {err}",
                    reply_markup=InlineKeyboardMarkup(record_inline_kb),
                )
            else:
                context.user_data["records"].append(Record.model_dump(record))
                context.user_data["record"].clear()
                context.user_data["choice"] = None

                await query.edit_message_text(
                    escape_md("✅ The record has been saved.\n\n") + str(record),
                    reply_markup=InlineKeyboardMarkup.from_button(
                        Action.OK.as_button()
                    ),
                )

        logging.info("Records saved: %s", context.user_data["records"])

        return INPUT

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the record conversation"""
        reply_text = (
            "🛑 Action *cancelled*\. "
            "You can use `/record` again or use `? record` for more information\."
        )

        context.user_data["selected_month_year"] = None

        if record := context.user_data.get("record"):
            record.clear()

        if query := update.callback_query:
            await query.answer()
            await query.edit_message_text(reply_text)
        else:
            await update.message.reply_text(reply_text)

        return END

    async def back_to_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Go back to the main menu"""
        context.user_data["start_over"] = True
        await update.callback_query.answer()
        return await self.start(update, context)
        return await self.start(update, context)
