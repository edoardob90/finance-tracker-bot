"""
Utils module
"""
import re
import json
import logging
import pathlib
from functools import partial
from typing import Tuple, Union, Dict, Any
import datetime as dtm
from dateutil.parser import parse

from telegram import Update
from telegram.ext import CallbackContext
from telegram.utils.helpers import escape_markdown as EscapeMarkdown

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import UserAccessTokenError, RefreshError

from gspread import Client

from constants import *
from spreadsheet import *

# Logging
logging.basicConfig(
    format=log_format, level=log_level
)
logger = logging.getLogger(__name__)

# Partial function with version=2 of Markdown parsing
escape_markdown = partial(EscapeMarkdown, version=2)

def stop(command: str, action: str, update: Update) -> int:
    """End a conversation altogether"""
    text = f"Use `/{command}` to {action} or `/help` to know what I can do for you\.\nBye 👋"
    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text)
    else:
        update.message.reply_text(text=text)
    return END

def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

#
# Record
#
def data_to_str(data: Dict[str, Any]) -> str:
    """Build a string concatenating all values in a data `Dict`"""
    facts = [f"*{escape_markdown(key)}:* {escape_markdown(str(value))}" for key, value in data.items() if (value and key != 'recorded_on')]
    
    return "\n".join(facts)

def currency_parser(number_str: str) -> Tuple[float, str]:
    """Parse a number string that contains a currency symbol or name"""
    # Extract the currency symbol: either the first character or €, $, £
    cur_str = re.search(r'([A-Za-z€$£])', number_str)
    cur_symbol = cur_str.group(1) if cur_str else 'X'

    # Remove any non-numeric char
    number_str = re.sub(r'[^-0-9,.]', '', number_str)
    # Remove thousand separator: `,` or `.`
    number_str = re.sub(r'[,.]', '', number_str[:-3]) + number_str[-3:]

    if '.' in number_str[-3:]:
        num = float(number_str)
    elif ',' in number_str[-3:]:
        num = float(number_str.replace(',', '.'))
    else:
        num = float(number_str)

    return round(num, 2), CURRENCIES.get(cur_symbol.upper()) or 'X'

def parse_data(key: str, value: str) -> Dict:
    """Helper function to correctly parse a detail of a new record"""
    if key == 'date':
        data = parse(value, dayfirst=True).strftime("%d/%m/%Y")
    elif key == 'amount':
        amount, cur = currency_parser(value)
        return {key: amount, 'currency': cur}
    else:
        data = str(value)
    
    return {key: data}


#
# Settings
#
def oauth(first_login: bool = False, credentials_file: str = None, token_file: str = None, code: str = None, user_data: Dict = None) -> Tuple[Union[Credentials, None], Union[None, str]]:
    """Start the authorization flow and return a valid token or refresh an expired one"""
    creds = None
    result = None

    logger.debug(f'Current auth data: {user_data}')

    if not first_login:
        # Look up credentials in `user_data` dictionary ...
        if user_data is not None and 'creds' in user_data:
            logger.debug("Loading credentials from user_data dict")
            creds = Credentials.from_authorized_user_info(json.loads(user_data['creds']), SCOPES)
        # Otherwise try to open `token_file`
        elif token_file is not None and pathlib.Path(token_file).exists():
            logger.debug("Loading credentials from JSON file")
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if creds is not None:
        logger.debug('Credentials loaded from user data or token file')
        result = 'ok'

    if not creds or not creds.valid:
        logger.debug("Credentials don't have a token or the token is expired")
        if creds and creds.expired and creds.refresh_token:
            logger.debug("Credentials are expired")
            try:
                creds.refresh(Request())
            except (UserAccessTokenError, RefreshError):
                result = 'refresh error'
                logger.error("Error while attempting to refresh the token")
                raise
            else:
                result = 'ok'
        else:
            logger.debug("New login: starting a new OAuth flow")
            try:
                flow = Flow.from_client_secrets_file(
                    credentials_file,
                    scopes=SCOPES,
                    redirect_uri='urn:ietf:wg:oauth:2.0:oob')
            except TypeError:
                logger.error("Client secret file cannot be 'None'")
                raise
            except FileNotFoundError:
                logger.error(f"Client secret file '{credentials_file}' not found")
                raise

            if code:
                logger.debug("Last OAuth step: fetching the token from the authorization code")
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
                    user_data['creds'] = creds.to_json()
                
                # as a JSON file at `token_file`
                # FIXME: is this necessary? should this backup file be removed completely?
                if token_file is not None:
                    creds_stored = True
                    user_data['token_file'] = token_file
                    with pathlib.Path(token_file).open('w') as token:
                        token.write(creds.to_json())

                if creds_stored:
                    result = 'Token has been saved\.'
            else:
                logger.debug("OAuth step: asking the user to authorize the app and enter the authorization code")
                # Tell the user to go to the authorization URL to get the authorization code
                auth_url, _ = flow.authorization_url(prompt='consent')
                result = f'Please, go to [this URL]({auth_url}) to request an authorization code\. Send me the code you obtained\.'
    
    return creds, result

def check_auth(auth_data: Dict = None) -> bool:
    """Check if the auth data for a user are valid"""
    if auth_data is None:
        return False
    
    if auth_data.get('auth_is_done'):
        # First, check if credentials have been stored in `user_data` dict
        if 'creds' in auth_data:
            return True
        # Check if a `token_file` has been saved, is a regular file and exists
        if 'token_file' in auth_data:
            token_file = pathlib.Path(auth_data['token_file'])
            if token_file.is_file() and token_file.exists():
                return True
    
    return False

def check_spreadsheet(spreadsheet_data: Dict = None) -> bool:
    """Check if the spreadsheet is set and is valid"""
    if spreadsheet_data is None:
        return False
    
    # TODO: could also check if the spreadsheet actually exists
    spreadsheet_data['is_set'] = False 
    if spreadsheet_data.get('id') and spreadsheet_data.get('sheet_name'):
        spreadsheet_data['is_set'] = True
        return True
    
    return False

def add_to_spreadsheet(context: CallbackContext) -> None:
    """Task for `telegram.ext.JobQueue` to add records saved locally to the spreadsheet"""
    user_id = context.job.context
    user_data = context.dispatcher.user_data[user_id]
    send_message = partial(context.bot.send_message, chat_id=user_id, disable_notification=True)
    
    records = user_data.get('records')
    auth_data = user_data.get('auth')
    spreadsheet_data = user_data.get('spreadsheet')
    
    if not records:
        logger.info(f"Skipping scheduled task for user_id {user_id}: no records.")
        send_message(text="You have no records to append\.")
        return None

    # Check auth and whether a spreadsheet has been set
    if not check_auth(auth_data):
        logger.warning(f"Cannot add data to spreadsheet of user {user_id}: authorization is incomplete.")
        send_message(text="⚠️ I could not add your data to the spreadsheet: *authorization is incomplete*\. Enter the `/settings` to log in\.")
        return None

    if not check_spreadsheet(spreadsheet_data):
        logger.warning(f"Cannot add data to spreadsheet of user {user_id}: spreadsheet has not been set or is invalid.")
        send_message(text="⚠️ I could not add your data to the spreadsheet: ID or sheet name *are not set*\. Enter the `/settings` to set them\.")
        return None
    
    # Fetch the credentials and check that there are no errors
    creds, result = oauth(user_data=auth_data)
    if result == 'refresh error':
        send_message(text="⚠️ Error while refreshing your credentials\. You should logout and login again\. Go to `/settings`, then *Login*, and then click *Logout*\.")
        return None
    
    # Add data to the spreadsheet
    spreadsheet = Spreadsheet(
        client=Client(auth=creds),
        spreadsheet_id=spreadsheet_data['id'],
        sheet_name=spreadsheet_data['sheet_name']
    )
    try:
        values = [list(record.values()) for record in records]
        spreadsheet.append_records(values)
    except SpreadsheetError:
        send_message(text="⚠️ An error occurred while adding records to the spreadsheet\.")
        raise
    else:
        send_message(
            text=f"{dtm.datetime.now().strftime('%d/%m/%Y, %H:%M')}: *{len(records)}* record{' has' if len(records) == 1 else 's have'} been successfully added to the spreadsheet\."
        )
        records.clear()

    return None