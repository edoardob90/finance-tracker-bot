# pylint: disable=invalid-name,line-too-long,anomalous-backslash-in-string,trailing-whitespace,logging-fstring-interpolation
"""
Bot functions for `/settings` command.
"""
import datetime as dtm
import logging
import pathlib
import re
from random import randrange

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
from constants import *

logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# State definitions
(
    SELECTING_ACTION,
    NEW_LOGIN,
    EDIT_LOGIN,
    SET_SCHEDULE,
    REPLY,
    INPUT,
    STOPPING,
    SET_ACCOUNTS,
) = map(chr, range(8))

# Constants for CallbackQuery data
(
    LOGIN,
    SPREADSHEET,
    SCHEDULE,
    SHOW,
    BACK,
    UP_ONE_LEVEL,
    CANCEL,
    SAVE,
    STOP,
    RESET,
    ID,
    SHEET_NAME,
    DEFAULT_SCHEDULE,
    CUSTOM_SCHEDULE,
    REMOVE_SCHEDULE,
    ACCOUNTS,
    MODIFY_ACCOUNTS,
    CURRENCY,
) = map(chr, range(8, 26))

#
# Inline Keyboards
#
# Entry-point keyboard
# ROW_1 = ('Login', 'Spreadsheet', 'Schedule', 'Accounts')
# ROW_2 = ('Back',)
entry_inline_kb = [
    [
        InlineKeyboardButton(text="👤 Login", callback_data=str(LOGIN)),
        InlineKeyboardButton(text="📊 Spreadsheet", callback_data=str(SPREADSHEET)),
        InlineKeyboardButton(text="📆 Schedule", callback_data=str(SCHEDULE)),
    ],
    [
        InlineKeyboardButton(text="🏦 Accounts", callback_data=str(ACCOUNTS)),
        InlineKeyboardButton(text="💶 Currency", callback_data=str(CURRENCY)),
    ],
    [InlineKeyboardButton(text="🚪 Exit", callback_data=str(CANCEL))],
]

# Login keyboard
edit_login_inline_kb = [
    [
        InlineKeyboardButton(text="Logout", callback_data=str(RESET)),
        InlineKeyboardButton(text="Login status", callback_data=str(SHOW)),
    ],
    [InlineKeyboardButton(text="Back", callback_data=str(BACK))],
]

# Spreadsheet keyboard
spreadsheet_inline_kb = [
    [
        InlineKeyboardButton(text="Set the ID", callback_data=str(ID)),
        InlineKeyboardButton(text="Set the Sheet name", callback_data=str(SHEET_NAME)),
    ],
    [InlineKeyboardButton(text="Back", callback_data=str(BACK))],
]

# Schedule keyboard
schedule_inline_kb = [
    [
        InlineKeyboardButton(text="Default", callback_data=str(DEFAULT_SCHEDULE)),
        InlineKeyboardButton(
            text="Custom schedule", callback_data=str(CUSTOM_SCHEDULE)
        ),
        InlineKeyboardButton(
            text="Remove schedule", callback_data=str(REMOVE_SCHEDULE)
        ),
    ],
    [InlineKeyboardButton(text="Back", callback_data=str(BACK))],
]

# Accounts keyboard
accounts_inline_kb = [
    [InlineKeyboardButton(text="Add/Modify", callback_data=str(MODIFY_ACCOUNTS))],
    [InlineKeyboardButton(text="Back", callback_data=str(BACK))],
]

#
# Handler-related functions
#
def start(update: Update, context: CallbackContext) -> str:
    """Entry point for the `/settings` command"""
    keyboard = InlineKeyboardMarkup(entry_inline_kb)
    text = "⚙️ *Settings menu*\nWhat do you want to do?"
    user_data = context.user_data

    if user_data.get("start_over"):
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    else:
        update.message.reply_markdown_v2(text=text, reply_markup=keyboard)

    user_data["start_over"] = False

    return SELECTING_ACTION


#
# Login functions
#
def start_login(update: Update, context: CallbackContext) -> str:
    """Check user's login data and start a new OAuth flow"""
    user_data = context.user_data
    query = update.callback_query
    query.answer()

    # Initialize user data
    if "auth" not in user_data:
        user_data["auth"] = {}

    auth_data = user_data.get("auth")

    # Each user must have a unique token file
    if "token_file" not in auth_data:
        auth_data["token_file"] = f"{DATA_DIR}/auth_{str(query.from_user.id)}.json"

    # Check if the auth step has been already done
    if not utils.check_auth(auth_data):
        # Start the OAuth2 process
        creds, result = utils.oauth(
            service_account=SERVICE_ACCOUNT,
            first_login=True,
            credentials_file=CREDS if not SERVICE_ACCOUNT else SERVICE_ACCOUNT_FILE,
            token_file=auth_data["token_file"],
            user_data=auth_data,
        )
        if SERVICE_ACCOUNT:
            result = f"""⚠️ This is only a __*temporary*__ login method

To complete the login:

  1\. Open your spreadsheet on Google Sheet

  2\. Share the spreadsheet with the following account: `{creds.service_account_email}`

  3\. Make sure to set the role to *Editor* or the bot will not be able to modify your spreadsheet

After that, you can use the bot normally\. Bye 👋"""
            auth_data["auth_is_done"] = True
            auth_data["creds"] = {"service_account_email": creds.service_account_email}

        query.edit_message_text(text=result)

        return STOPPING if SERVICE_ACCOUNT else NEW_LOGIN

    query.edit_message_text(
        "You already logged in\. What do you want to do?",
        reply_markup=InlineKeyboardMarkup(edit_login_inline_kb),
    )

    return EDIT_LOGIN


def store_auth_code(update: Update, context: CallbackContext) -> int:
    """Handle the authorization code of a new login"""
    keyboard = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton(text="Back", callback_data=str(END))
    )

    auth_data = context.user_data.get("auth")
    code = update.message.text
    creds, result = utils.oauth(
        first_login=True,
        credentials_file=CREDS,
        token_file=auth_data["token_file"],
        user_data=auth_data,
        code=code,
    )

    if creds and result:
        auth_data["auth_is_done"] = True
        update.message.reply_text(text=result, reply_markup=keyboard)
    else:
        auth_data["auth_is_done"] = False
        update.message.reply_text(
            text="⚠️ I could not save your token\!", reply_markup=keyboard
        )

    return END


def reset_login(update: Update, context: CallbackContext) -> int:
    """Reset user's login data"""
    auth_data = context.user_data.get("auth")
    # Remove the token file
    pathlib.Path(auth_data["token_file"]).unlink(missing_ok=True)
    # Clear the dictionary
    auth_data.clear()

    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "Your login data have been reset\. You can login again from the `/settings` menu\.",
        reply_markup=InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(text="Ok", callback_data=str(END))
        ),
    )
    return END


def show_login(update: Update, context: CallbackContext) -> int:
    """Show auth data stored"""
    auth_data = context.user_data.get("auth")
    spreadsheet_data = context.user_data.get("spreadsheet")

    logger.info(f"auth_data: {str(auth_data)}")
    logger.info(f"spreadsheet_data: {str(spreadsheet_data)}")

    auth_data_str = """*Auth status*: {auth_status}

*Spreadsheet*: {ss_status}
    *ID*: {id}
    *Sheet name*: {name}"""

    status = dict.fromkeys(("auth_status", "ss_status", "id", "name"), "❌")

    # Check the login
    if utils.check_auth(auth_data):
        status["auth_status"] = "✅"

    # Check the spreadsheet
    if utils.check_spreadsheet(spreadsheet_data):
        sheet_id, sheet_name = spreadsheet_data.get("id"), spreadsheet_data.get(
            "sheet_name"
        )
        if None not in (sheet_id, sheet_name):
            status["ss_status"] = "✅"
        status["id"] = utils.escape_markdown(sheet_id or "❌")
        status["name"] = utils.escape_markdown(sheet_name or "❌")

    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "Here's your login data:\n\n"
        f"{auth_data_str.format(**status)}\n\n"
        "✅ \= OK\n❌ \= missing data",
        reply_markup=InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(text="Ok", callback_data=str(END))
        ),
    )

    return END


#
# Spreadsheet functions
#
def start_spreadsheet(update: Update, context: CallbackContext) -> str:
    """Prompt the spreadsheet menu"""
    # Initialize user data
    user_data = context.user_data
    if "spreadsheet" not in user_data:
        user_data["spreadsheet"] = {}

    query = update.callback_query
    query.answer()
    query.edit_message_text(
        "Set or reset your spreadsheet:",
        reply_markup=InlineKeyboardMarkup(spreadsheet_inline_kb),
    )
    return INPUT


def prompt_spreadsheet(update: Update, context: CallbackContext) -> str:
    """Prompt which property of a spreadsheet to set/reset"""
    BUTTONS = {
        ID: "ID",
        SHEET_NAME: "Sheet name",
    }
    query = update.callback_query
    user_data = context.user_data.get("spreadsheet")

    choice = BUTTONS[query.data]
    user_data["choice"] = choice.lower().replace(" ", "_")

    query.answer()
    query.edit_message_text(f"Set the *{choice}* of the spreadsheet")

    return REPLY


def set_spreadsheet(update: Update, context: CallbackContext) -> str:
    """Set or reset a spreadsheet property"""
    spreadsheet_data = context.user_data.get("spreadsheet")

    logger.info(f"spreadsheet_data: {str(spreadsheet_data)}")

    data = str(update.message.text)
    choice = str(spreadsheet_data["choice"])
    spreadsheet_data.update({choice: data})
    del spreadsheet_data["choice"]

    logger.info(f"spreadsheet_data: {str(spreadsheet_data)}")

    update.message.reply_text(
        f"Done\! Spreadsheet *{choice.upper() if choice == 'id' else choice.replace('_', ' ').capitalize()}* has been set\.",
        reply_markup=InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(text="Back", callback_data=str(UP_ONE_LEVEL))
        ),
    )
    return INPUT


def up_one_level(update: Update, context: CallbackContext) -> str:
    """Go back/up one level"""
    update.callback_query.answer()
    return start_spreadsheet(update, context)


#
# Schedule functions
#
def start_schedule(update: Update, context: CallbackContext) -> str:
    """Prompt the schedule menu"""
    query = update.callback_query
    query.answer()

    # Check if there's a scheduled job to append data
    jobs = context.job_queue.get_jobs_by_name("append_data_" + str(query.from_user.id))
    logger.info(f"Queued jobs: {str(jobs)}")
    next_time = (
        f"{jobs[0].next_t.strftime('%d/%m/%Y, %H:%M')}"
        if (jobs and jobs[0] is not None)
        else "never"
    )

    text = f"Your data will be added to the spreadsheet on: *{next_time}*\.\nDo you want to change the schedule?"
    query.edit_message_text(
        text=text, reply_markup=InlineKeyboardMarkup(schedule_inline_kb)
    )

    return SET_SCHEDULE


def set_default_schedule(update: Update, context: CallbackContext) -> str:
    """Set the default schedule: every day at midnight"""
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id
    utils.remove_job_if_exists("append_data_" + str(user_id), context)
    context.job_queue.run_daily(
        utils.add_to_spreadsheet,
        time=dtm.time(23, 59, randrange(0, 60)),
        context=(user_id, True),
        name="append_data_" + str(user_id),
        job_kwargs={
            "id": str(user_id),
            "replace_existing": True,
        },
    )

    query.edit_message_text(
        "Okay, I will add your data to the spreadsheet *every day at 23:59*\.\nBye 👋"
    )

    return STOPPING


def prompt_custom_schedule(update: Update, _: CallbackContext) -> str:
    """Prompt the user to enter a new schedule time/date"""
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "Okay, tell me when you want me to append your data to the spreadsheet\. You can use the following time specifications:\n"
        "\- `now`: immediately\n"
        "\- `SS`: within this many seconds from now\n"
        "\- `HH:MM`: today *only* at the specified time \(or tomorrow if time has already passed\)\n"
        "\- `d HH:MM`: every day at the specified time\n"
        "\- `d D HH:MM`: every week at the specified day and time\. `D=1` corresponds to Monday and `D=7` to Sunday\n"
        "\- `m DD HH:MM`: every month at the specified day \(`DD`\) and time\n\n"
        "Use the command `/cancel` to cancel the operation\."
    )

    return INPUT


def set_custom_schedule(update: Update, context: CallbackContext) -> str:
    """
    Set a custom schedule

    Supported formats:
        - `now`: run once almost immediately
        - `SS`: run this many seconds from now
        - `HH:MM`: run once at the specified time
        - `daily DD HH:MM`: run daily or weekly at the specified time
        - `monthly DD HH:MM`: run monthly at the specified day `DD` and time
    """
    WEEKDAYS = (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    )
    recurring = False
    schedule_is_valid = False
    when_text = update.message.text
    user_id = update.message.from_user.id
    job_name = f"append_data_{user_id}"
    job_when = None
    job_kwargs = {
        "id": str(user_id),
        "replace_existing": True,
    }

    # Remove any previous job, if any
    utils.remove_job_if_exists(job_name, context)

    # Parse the new time/date
    once_pattern = re.compile(
        r"(now|(?P<hour>\d{2}):(?P<minute>\d{2})|(?P<seconds>\d{1,2}))", re.IGNORECASE
    )
    daily_pattern = re.compile(
        r"(d|daily)\s*(?P<dow>[1-7])?\s*(?P<hour>\d{2}):(?P<minute>\d{2})",
        re.IGNORECASE,
    )
    monthly_pattern = re.compile(
        r"(m|monthly) (?P<day>\d{2}) (?P<hour>\d{2}):(?P<minute>\d{2})", re.IGNORECASE
    )

    # Try the the 'once' pattern (non-recurring task)
    if (match := once_pattern.match(when_text)) is not None:
        recurring = False
        schedule_is_valid = True
        hour, minute, seconds = match.groupdict().values()
        if hour and minute:
            hour, minute = int(hour), int(minute)
            job_when = dtm.time(hour, minute)
            when = f"*once* at *{hour:02d}:{minute:02d}*"
        elif seconds:
            job_when = int(seconds)
            when = f"in *{seconds} second{'s' if job_when > 1 else ''}* from now"
        else:
            job_when = dtm.datetime.now() + dtm.timedelta(seconds=0.5)
            when = "*now*"

        context.job_queue.run_once(
            utils.add_to_spreadsheet,
            when=job_when,
            context=(user_id, recurring),
            name=job_name,
            job_kwargs=job_kwargs,
        )
    # Try the 'daily' or 'monthly' time specs
    elif (
        match := (daily_pattern.match(when_text) or monthly_pattern.match(when_text))
    ) is not None:
        schedule_is_valid = True
        recurring = True
        job_when = {
            key: int(value) for key, value in match.groupdict().items() if value
        }
        if (day := job_when.pop("day", None)) is not None:
            context.job_queue.run_monthly(
                utils.add_to_spreadsheet,
                when=dtm.time(**job_when),
                day=day,
                context=(user_id, recurring),
                name=job_name,
                job_kwargs=job_kwargs,
            )
            when = f"on *{day}* every month at *{job_when['hour']:02d}:{job_when['minute']:02d}*"
        elif (dow := job_when.pop("dow", None)) is not None:
            context.job_queue.run_daily(
                utils.add_to_spreadsheet,
                days=(dow - 1,),
                time=dtm.time(**job_when),
                context=(user_id, recurring),
                name=job_name,
                job_kwargs=job_kwargs,
            )
            when = f"every *{WEEKDAYS[dow - 1]}* at *{job_when['hour']:02d}:{job_when['minute']:02d}*"
        else:
            context.job_queue.run_daily(
                utils.add_to_spreadsheet,
                time=dtm.time(**job_when),
                context=(user_id, recurring),
                name=job_name,
                job_kwargs=job_kwargs,
            )
            when = f"every day at *{job_when['hour']:02d}:{job_when['minute']:02d}*"

    if schedule_is_valid:
        update.message.reply_text(f"Your data will be appended {when}\.\nBye 👋")
        return STOPPING
    else:
        update.message.reply_text(
            "⚠️ You entered an invalid time specification\. Try again or use `/cancel` to stop\.\n"
            "You can use the following time specifications:\n"
            "\- `now`: immediately\n"
            "\- `SS`: within `SS` seconds from now\n"
            "\- `HH:MM`: today *only* at the specified time \(or tomorrow if time has already passed\)\n"
            "\- `d\[aily\] HH:MM`: every day at the specified time\n"
            "\- `m\[onthly\] DD HH:MM`: every month at the specified day \(`DD`\) and time \(`HH:MM`\)\n"
        )
        return INPUT


def remove_schedule(update: Update, context: CallbackContext) -> str:
    """Remove any scheduled job"""
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    job_name = f"append_data_{user_id}"

    if utils.remove_job_if_exists(job_name, context):
        text = "Any scheduled job to add data to your spreadsheet has been *removed*\."
    else:
        text = (
            "⚠️ I did not find any scheduled job to remove\. Have you ever added one?"
        )

    query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(text="Ok", callback_data=str(BACK))
        ),
    )

    return INPUT


#
# Bank accounts setting
#
def get_accounts(update: Update, context: CallbackContext) -> str:
    """Get the preferred bank accounts for a user"""
    # get the 'accounts' from the user_data dictionary
    if "accounts" not in (user_data := context.user_data):
        user_data["accounts"] = []

    # did the user already saved any accounts?
    if (num_accounts := len(user_data["accounts"])) > 0:
        accounts_str = "\n".join(
            [
                f"  {i}\. {account.strip()}"
                for i, account in enumerate(user_data["accounts"], start=1)
            ]
        )
        reply_msg = f"You saved *{num_accounts}* account{'s' if num_accounts > 1 else ''}:\n\n{accounts_str}"
    else:
        reply_msg = "You have saved *no accounts*\."

    query = update.callback_query
    query.answer()
    query.edit_message_text(
        text=reply_msg, reply_markup=InlineKeyboardMarkup(accounts_inline_kb)
    )

    return SET_ACCOUNTS


def set_accounts(update: Update, context: CallbackContext) -> str:
    """Set the preferred accounts for a user"""
    # Either append or replace data to the accounts list. Default is replace
    replace = True

    accounts = context.user_data["accounts"]

    if (query := update.callback_query) is not None:
        query.answer()
        query.edit_message_text(
            "Enter your preferred accounts, *one per line* or separated *by comma*\.\n\n*Notes:*\n"
            "  \- By default, the old accounts are *replaced*\n"
            "  \- If the message starts with `+`, the new accounts are *added* to the list\n"
            "  \- Type `erase`, `remove`, or `clear` to *delete all* your saved accounts"
        )
        return INPUT

    if (message := update.message) is not None:
        text = message.text
        if re.match(r"(remove|clear|erase)", text, re.IGNORECASE) is not None:
            reply_msg = f"*{len(accounts)}* account{'s have' if len(accounts) > 1 else ' has'} been removed\."
            accounts.clear()
        else:
            if text.startswith("+"):
                replace = False
                text = text[1:]
            if "," in text:
                text = text.split(",")
            else:
                text = text.split("\n")

            # replace or append the newly inserted accounts
            if replace:
                accounts.clear()

            accounts.extend([s.strip() for s in text])

            reply_msg = f"*{len(accounts)}* account{'s have' if len(accounts) > 1 else ' has'} been saved\."

        message.reply_text(
            text=reply_msg,
            reply_markup=InlineKeyboardMarkup.from_button(
                InlineKeyboardButton(text="Back", callback_data=str(BACK))
            ),
        )

        return SET_ACCOUNTS


#
# Default/preferred currencies
#
def get_preferred_currency(update: Update, context: CallbackContext) -> str:
    """Get the currently set preferred currency (if any)"""

    if "default_cur" not in (user_data := context.user_data):
        user_data["default_cur"] = None

    currencies = set(CURRENCIES.values())
    reply_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text=str(x), callback_data=str(x))
                for x in currencies
            ],
            [InlineKeyboardButton(text="Reset", callback_data=str(RESET))],
            [InlineKeyboardButton(text="Back", callback_data=str(BACK))],
        ]
    )

    query = update.callback_query
    reply_text = (
        f'*{user_data["default_cur"]}* is your default currency\. Change your default currency:'
        if user_data["default_cur"] is not None
        else "Choose your default currency:"
    )
    query.answer()
    query.edit_message_text(text=reply_text, reply_markup=reply_kb)

    return INPUT


def set_preferred_currency(update: Update, context: CallbackContext) -> str:
    """Set a preferred currency"""

    user_data = context.user_data
    query = update.callback_query
    query.answer()

    # Set the default currency
    if query.data == str(RESET):
        reply_text = "Your default currency has been *reset*"
        user_data["default_cur"] = None
    else:
        reply_text = f"Your default currency has been set to *{query.data}*"
        user_data["default_cur"] = query.data

    query.edit_message_text(
        text=reply_text,
        reply_markup=InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(text="Back", callback_data=str(BACK))
        ),
    )

    return INPUT


#
# Other functions
#
def cancel(update: Update, _: CallbackContext) -> str:
    """Cancel the `settings` command"""
    text = "Action cancelled\. Use `/settings` to enter the settings or `/help` to know what I can do for you\.\nBye 👋"
    if (query := update.callback_query) is not None:
        query.answer()
        query.edit_message_text(text)
    else:
        update.message.reply_text(text)
    return STOPPING


def stop(update: Update, _: CallbackContext) -> int:
    """End the conversation altogether"""
    return utils.stop(command="settings", action="enter your settings", update=update)


def back_to_start(update: Update, context: CallbackContext) -> str:
    """Go back to the start menu"""
    update.callback_query.answer()
    context.user_data["start_over"] = True
    return start(update, context)


# Login conversation handler
login_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_login, pattern=f"^{LOGIN}$")],
    states={
        NEW_LOGIN: [MessageHandler(Filters.text & ~Filters.command, store_auth_code)],
        EDIT_LOGIN: [
            CallbackQueryHandler(reset_login, pattern=f"^{RESET}$"),
            CallbackQueryHandler(show_login, pattern=f"^{SHOW}$"),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        CallbackQueryHandler(back_to_start, pattern=f"^{BACK}$"),
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END,
    },
    name="login_second_level",
    persistent=False,
)

# Spreadsheet handler
spreadsheet_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_spreadsheet, pattern=f"^{SPREADSHEET}$")],
    states={
        INPUT: [
            CallbackQueryHandler(prompt_spreadsheet, pattern=f"^{ID}$|^{SHEET_NAME}$"),
        ],
        REPLY: [MessageHandler(Filters.text & ~Filters.command, set_spreadsheet)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        CallbackQueryHandler(up_one_level, pattern=f"^{UP_ONE_LEVEL}$"),
        CallbackQueryHandler(back_to_start, pattern=f"^{BACK}$"),
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END,
    },
    name="spreadsheet_second_level",
    persistent=False,
)

# Schedule handler
schedule_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_schedule, pattern=f"^{SCHEDULE}$")],
    states={
        SET_SCHEDULE: [
            CallbackQueryHandler(set_default_schedule, pattern=f"^{DEFAULT_SCHEDULE}$"),
            CallbackQueryHandler(
                prompt_custom_schedule, pattern=f"^{CUSTOM_SCHEDULE}$"
            ),
            CallbackQueryHandler(remove_schedule, pattern=f"^{REMOVE_SCHEDULE}$"),
        ],
        INPUT: [
            MessageHandler(Filters.text & ~Filters.command, set_custom_schedule),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        CallbackQueryHandler(back_to_start, pattern=f"^{BACK}$"),
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END,
    },
    name="schedule_second_level",
    persistent=False,
)

# Accounts handler
accounts_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(get_accounts, pattern=f"^{ACCOUNTS}$"),
    ],
    states={
        SET_ACCOUNTS: [
            CallbackQueryHandler(set_accounts, pattern=f"^{MODIFY_ACCOUNTS}$")
        ],
        INPUT: [MessageHandler(Filters.text & ~Filters.command, set_accounts)],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        CallbackQueryHandler(back_to_start, pattern=f"^{BACK}$"),
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END,
    },
)

# Default currency handler
currency_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(get_preferred_currency, pattern=f"^{CURRENCY}$"),
    ],
    states={
        INPUT: [
            CallbackQueryHandler(
                set_preferred_currency,
                pattern="^"
                + "$|^".join(set(CURRENCIES.values()))
                + "$|^"
                + str(RESET)
                + "$",
            ),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
        CallbackQueryHandler(cancel, pattern=f"^{CANCEL}$"),
        CallbackQueryHandler(back_to_start, pattern=f"^{BACK}$"),
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        SELECTING_ACTION: SELECTING_ACTION,
        STOPPING: END,
    },
)

# Top-level conversation handler
settings_handler = ConversationHandler(
    entry_points=[
        CommandHandler("settings", start),
    ],
    states={
        SELECTING_ACTION: [
            login_handler,
            spreadsheet_handler,
            schedule_handler,
            accounts_handler,
            currency_handler,
            CallbackQueryHandler(back_to_start, pattern="^" + str(END) + "$"),
        ],
    },
    fallbacks=[
        CommandHandler("stop", stop),
        CallbackQueryHandler(stop, pattern=f"^{CANCEL}$"),
    ],
    name="settings_top_level",
    persistent=False,
)
