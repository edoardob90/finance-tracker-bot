# pylint: disable=invalid-name,line-too-long,anomalous-backslash-in-string,trailing-whitespace,logging-fstring-interpolation
"""
Utils module
"""
import html
import json
import logging
import os
import pathlib
import re
import traceback
from calendar import Calendar
from datetime import datetime
from functools import partial
from typing import Any, Callable, Dict, Tuple, Union

from dateutil.parser import parse
from google.auth.exceptions import RefreshError, UserAccessTokenError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import Flow
from gspread import Client
from telegram import InlineKeyboardButton, ParseMode, Update
from telegram.ext import CallbackContext, ConversationHandler
from telegram.utils.helpers import escape_markdown as EscapeMarkdown

from constants import CURRENCIES, LOG_FORMAT, SCOPES
from spreadsheet import Spreadsheet, SpreadsheetError

# Env variables
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
SERVICE_ACCOUNT = bool(os.environ.get("SERVICE_ACCOUNT", False))
SERVICE_ACCOUNT_FILE = os.environ.get(
    "SERVICE_ACCOUNT_FILE",
    os.path.join(os.path.dirname(__file__), "service_account.json"),
)

# Logging
logging.basicConfig(
    format=LOG_FORMAT,
    level=LOG_LEVEL,
)
logger = logging.getLogger(__name__)

# Utilities

# Partial function with version=2 of Markdown parsing
escape_markdown = partial(EscapeMarkdown, version=2)


def stop(update: Update, command: str, action: str) -> int:
    """End a conversation altogether"""
    text = f"Use `/{command}` to {action} or `/help` to know what I can do for you\.\nBye 👋"
    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text)
    else:
        update.message.reply_text(text=text)
    return ConversationHandler.END


def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def up_one_level(update: Update, context: CallbackContext, func: Callable):
    """Go back or up one level in a menu"""
    update.callback_query.answer()
    return func(update, context)


# Error handler
def error_handler(update: Update, context: CallbackContext) -> None:
    """Log any error and send a warning message"""
    developer_user_id = os.environ.get("DEVELOPER_USER_ID")

    # First, log the error before doing anything else so we can see it in the logfile
    logger.error(
        msg="Exception raised while processing an update:", exc_info=context.error
    )

    # Format the traceback
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Notify the developer about the exception
    if developer_user_id:
        context.bot.send_message(
            chat_id=developer_user_id, text=message, parse_mode=ParseMode.HTML
        )

    return None


#
# Record
#
def data_to_str(data: Dict[str, Any], prefix: str = "") -> str:
    """Build a string concatenating all values in a data `Dict`"""
    facts = [
        f"{prefix}*{escape_markdown(key)}:* {escape_markdown(str(value))}"
        for key, value in data.items()
        if (value and key != "recorded_on")
    ]
    return "\n".join(facts)


def currency_parser(number_str: str) -> Tuple[float, str]:
    """Parse a number string that contains a currency symbol or name"""
    # Extract the currency symbol: either the first character or €, $, £
    cur_str = re.search(r"([A-Za-z€$£])", number_str)
    cur_symbol = cur_str.group(1) if cur_str else "X"

    # Remove any non-numeric char
    number_str = re.sub(r"[^-0-9,.']", "", number_str)
    # Remove thousand separator: `,`, `.`, or `'`
    number_str = re.sub(r"[,.']", "", number_str[:-3]) + number_str[-3:]

    if "," in number_str[-3:]:
        number_str = number_str.replace(",", ".")
    amount = float(number_str)

    return round(amount, 2), CURRENCIES.get(cur_symbol.upper(), "X")


def parse_data(key: str, value: str) -> Dict:
    """Helper function to correctly parse a detail of a new record"""
    if key == "date":
        data = parse(value, dayfirst=True).strftime("%d/%m/%Y")
    elif key == "amount":
        amount, cur = currency_parser(value)
        return {key: amount, "currency": cur}
    else:
        data = str(value)

    return {key: data}


def calendar_keyboard(date: datetime):
    """Return a InlineKeyboardMarkup with a calendar of days of the given month"""
    year, month, today, *_ = date.timetuple()

    def calendar_day_button(day: int):
        """Return a InlineKeyboardButton to be used in a calendar keyboard"""
        if day == 0:
            return InlineKeyboardButton(text="❌", callback_data=str(None))
        return InlineKeyboardButton(
            text=("✅" if day == today else str(day)),
            callback_data=f"{day:02d}/{month:02d}/{year}",
        )

    calendar = Calendar().monthdayscalendar(year, month)

    return [list(map(calendar_day_button, row)) for row in calendar]


#
# Settings
#
def oauth(
    first_login: bool = False,
    credentials_file: str = None,
    token_file: str = None,
    code: str = None,
    user_data: Dict = None,
    service_account: bool = False,
) -> Tuple[Union[Credentials, None], Union[None, str]]:
    """Start the authorization flow and return a valid token or refresh an expired one"""
    creds = None
    result = None

    logger.debug(f"Current auth data: {user_data}")

    # TODO: this is *temporary* until I have the app approved by Google
    if service_account:
        if first_login:
            user_data["auth_type"] = "service_account"
        creds = ServiceAccountCredentials.from_service_account_file(
            filename=credentials_file, scopes=SCOPES
        )
        result = "service account"
    else:
        if first_login:
            user_data["auth_type"] = "user_account"
        else:
            # Look up credentials in `user_data` dictionary ...
            if user_data is not None and "creds" in user_data:
                logger.debug("Loading credentials from user_data dict")
                creds = Credentials.from_authorized_user_info(
                    info=json.loads(user_data["creds"]), scopes=SCOPES
                )
            # Otherwise try to open `token_file`
            elif token_file is not None and pathlib.Path(token_file).exists():
                logger.debug("Loading credentials from JSON file")
                creds = Credentials.from_authorized_user_file(
                    filename=token_file, scopes=SCOPES
                )

        if creds is not None:
            logger.debug("Credentials loaded from user data or token file")
            result = "ok"

        if not creds or not creds.valid:
            logger.debug("Credentials don't have a token or the token is expired")
            if creds and creds.expired and creds.refresh_token:
                logger.debug("Credentials are expired")
                try:
                    creds.refresh(Request())
                except (UserAccessTokenError, RefreshError):
                    result = "error"
                    logger.error("Error while attempting to refresh the token")
                    raise
                else:
                    result = "ok"
            else:
                logger.debug("New login: starting a new OAuth flow")
                try:
                    flow = Flow.from_client_secrets_file(
                        credentials_file,
                        scopes=SCOPES,
                        redirect_uri="urn:ietf:wg:oauth:2.0:oob",
                    )
                except TypeError:
                    result = "error"
                    logger.error("Client secret file cannot be 'None'")
                    raise
                except FileNotFoundError:
                    result = "error"
                    logger.error(f"Client secret file '{credentials_file}' not found")
                    raise

                if code:
                    logger.debug(
                        "Last OAuth step: fetching the token from the authorization code"
                    )
                    # We have an authorization code. This code is used to get the
                    # access token.
                    flow.fetch_token(code=code)

                    # Get the credentials
                    try:
                        creds = flow.credentials
                    except ValueError:
                        logger.error("No valid token found in session")
                        raise

                    # Store credentials
                    creds_stored = False
                    # in the `user_data` dict
                    if user_data is not None:
                        creds_stored = True
                        user_data["creds"] = creds.to_json()

                    # as a JSON file at `token_file`
                    # FIXME: is this necessary? should this backup file be removed completely?
                    if token_file is not None:
                        creds_stored = True
                        user_data["token_file"] = token_file
                        with pathlib.Path(token_file).open(
                            "w", encoding="utf-8"
                        ) as token:
                            token.write(creds.to_json())

                    if creds_stored:
                        result = "Token has been saved\."
                else:
                    logger.debug(
                        "OAuth step: asking the user to authorize the app and enter the authorization code"
                    )
                    # Tell the user to go to the authorization URL to get the authorization code
                    auth_url, _ = flow.authorization_url(
                        prompt="consent",
                        access_type="offline",
                        include_granted_scopes="true",
                    )
                    result = f"Please, go to [this URL]({auth_url}) to request an authorization code\. Send me the code you obtained\."

    return creds, result


def check_auth(auth_data: Dict = None) -> bool:
    """Check if the auth data for a user are valid"""
    if not auth_data:
        return False

    # Check if the auth process has ever been started
    if not auth_data.get("auth_type"):
        return False

    # Check if the auth process has been completed once
    if auth_data.get("auth_is_done"):
        # First, check if credentials have been stored in `user_data` dict
        if "creds" in auth_data:
            return True
        # Check if a `token_file` has been saved, is a regular file and exists
        if "token_file" in auth_data:
            token_file = pathlib.Path(auth_data["token_file"])
            if token_file.is_file() and token_file.exists():
                return True

    return False


def check_spreadsheet(spreadsheet_data: Dict = None) -> bool:
    """Check if the spreadsheet is set and is valid"""
    if not spreadsheet_data:
        return False

    # TODO: could also check if the spreadsheet actually exists
    spreadsheet_data["is_set"] = False
    if spreadsheet_data.get("id") and spreadsheet_data.get("sheet_name"):
        spreadsheet_data["is_set"] = True
        return True

    return False


def add_to_spreadsheet(context: CallbackContext) -> None:
    """Task for `telegram.ext.JobQueue` to add records saved locally to the spreadsheet"""
    user_id, recurring = context.job.context
    user_data = context.dispatcher.user_data[user_id]
    send_message = partial(
        context.bot.send_message, chat_id=user_id, disable_notification=True
    )

    msg_header = f"📆{'🔁' if recurring else ''} *Running scheduled task*"

    records = user_data.get("records")
    auth_data = user_data.get("auth")
    spreadsheet_data = user_data.get("spreadsheet")

    if not records:
        logger.info(f"Skipping scheduled task for user_id {user_id}: no records.")
        send_message(text=f"{msg_header}\nThere are no records to append\.")
        return None

    # Check auth and whether a spreadsheet has been set
    if not check_auth(auth_data):
        logger.error(
            f"Cannot add data to spreadsheet of user {user_id}: authorization is incomplete."
        )
        send_message(
            text="⚠️ I could not add your data to the spreadsheet: *authorization is incomplete*\. Enter the `/settings` to log in\."
        )
        return None

    if not check_spreadsheet(spreadsheet_data):
        logger.error(
            f"Cannot add data to spreadsheet of user {user_id}: spreadsheet has not been set or is invalid."
        )
        send_message(
            text="⚠️ I could not add your data to the spreadsheet: ID or sheet name *are not set*\. Enter the `/settings` to set them\."
        )
        return None

    # Fetch the credentials and check that there are no errors
    try:
        if SERVICE_ACCOUNT:
            creds, _ = oauth(
                service_account=SERVICE_ACCOUNT, credentials_file=SERVICE_ACCOUNT_FILE
            )
        else:
            creds, _ = oauth(user_data=auth_data)
    except RefreshError:
        send_message(
            text="⚠️ Error while refreshing your credentials\. You should logout and login again\. Go to `/settings`, then *Login*, and then click *Logout*\."
        )
        return None
    except Exception:
        send_message(
            text="⚠️ An error occurred\. Please, contact the developer to find a solution\. Sorry 😞"
        )
        return None
    else:
        # Open the spreadsheet
        spreadsheet = Spreadsheet(
            client=Client(auth=creds),
            spreadsheet_id=spreadsheet_data["id"],
            sheet_name=spreadsheet_data["sheet_name"],
        )
        spreadsheet.range = "A2:G500"

    # Add the records to the spreadsheet
    try:
        values = [list(record.values()) for record in records]
        spreadsheet.append_records(values)
    except SpreadsheetError:
        send_message(
            text="⚠️ An error occurred while adding records to the spreadsheet\."
        )
        raise
    else:
        send_message(
            text=f"{msg_header}\n*{len(records)}* record{' has' if len(records) == 1 else 's have'} been successfully added to the spreadsheet\."
        )
        records.clear()

    return None
