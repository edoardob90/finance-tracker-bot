"""
Bot functions for `/auth` command.
They handle Google authorization flow and Google sheet setup.
"""
import pathlib
import logging
import json
from typing import Union, Dict, Tuple
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import UserAccessTokenError, RefreshError

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
)

from constants import *
import utils
import spreadsheet

logging.basicConfig(
    format=log_format, level=log_level
)
logger = logging.getLogger(__name__)

# State definitions
(
    SELECTING_ACTION,
    NEW_LOGIN,
    EDIT_LOGIN,
    REPLY,
    STOPPING,
) = map(chr, range(5))

# Constants for CallbackQuery data
(
    LOGIN,
    SPREADSHEET,
    SCHEDULE,
    SHOW,
    BACK,
    CANCEL,
    SAVE,
    STOP,
    RESET,
    ID,
    NAME,
) = map(chr, range(5, 16))

#
# Inline Keyboards
#
# Entry-point keyboard
# ROW_1 = ('Login', 'Spreadsheet', 'Schedule')
# ROW_2 = ('Back',)
entry_inline_kb = [
    [
        InlineKeyboardButton(text='👤 Login', callback_data=str(LOGIN)),
        InlineKeyboardButton(text='📊 Spreadsheet', callback_data=str(SPREADSHEET)),
        InlineKeyboardButton(text='📆 Schedule', callback_data=str(SCHEDULE)),
    ],
    [InlineKeyboardButton(text='Cancel', callback_data=str(CANCEL))]
]

# Login keyboard
edit_login_inline_kb = [
    [
       InlineKeyboardButton(text='Reset login', callback_data=str(RESET)),
       InlineKeyboardButton(text='Login status', callback_data=str(SHOW)) 
    ],
    [InlineKeyboardButton(text='Back', callback_data=str(BACK))]
]

# Spreadsheet keyboard
spreadsheet_inline_kb = [
    [ 
        InlineKeyboardButton(text='ID', callback_data=str(ID)),
        InlineKeyboardButton(text='Sheet name', callback_data=str(NAME))
    ],
    [InlineKeyboardButton(text='Back', callback_data=str(BACK))]
]

# Utility functions

class AuthError(Exception):
    """Exception for an authentication error"""

def oauth(credentials_file: str, token_file: str = None, code: str = None, user_data: Dict = None) -> Tuple[Union[Credentials, None], Union[None, str]]:
    """Start the authorization flow and return a valid token or refresh an expired one"""
    creds = None
    result = None

    logger.info(f'Current auth data: {user_data}')

    # Look up credentials in `user_data` dictionary ...
    if user_data is not None and 'creds' in user_data:
        logger.info("Loading credentials from user_data dict")
        creds = Credentials.from_authorized_user_info(json.loads(user_data['creds']), spreadsheet.SCOPES)
    
    # ... otherwise try to open `token_file`
    elif token_file is not None and pathlib.Path(token_file).exists():
        logger.info("Loading credentials from JSON file")
        creds = Credentials.from_authorized_user_file(token_file, spreadsheet.SCOPES)

    if creds is not None:
        result = 'Credentials loaded from user data or a valid file\.'

    if not creds or not creds.valid:
        logger.info("Creds are invalid")
        if creds and creds.expired and creds.refresh_token:
            logger.info("Creds are expired")
            try:
                creds.refresh(Request())
            except (UserAccessTokenError, RefreshError):
                raise
        else:
            logger.info("New login: starting a new OAuth flow")
            flow = Flow.from_client_secrets_file(
                credentials_file,
                scopes=spreadsheet.SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob')

            if code:
                logger.info("Last OAuth step: fetching the token from the authorization code")
                # We have an authorization code. This code is used to get the
                # access token.
                flow.fetch_token(code=code)
                
                # Get the credentials
                try:
                    creds=flow.credentials
                except ValueError:
                    logger.error("No valid token found in session")
                    raise

                # Store credentials
                creds_stored = False
                # in user_data dict ...
                if user_data is not None:
                    creds_stored = True
                    user_data['creds'] = creds.to_json()

                # ... and to a JSON file `token_file`
                if token_file is not None:
                    creds_stored = True
                    user_data['token_file'] = token_file
                    with pathlib.Path(token_file).open('w') as token:
                        token.write(creds.to_json())

                if creds_stored:
                    result = 'Token has been saved\.'
            else:
                logger.info("OAuth step: asking the user to authorize the app and enter the authorization code")
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

def check_spreadsheet(auth_data: Dict = None) -> bool:
    """Check if the spreadsheet is set and is valid"""
    # If auth has never been done, whether a spreadsheet is set is irrelevant
    if check_auth(auth_data):
        spreadsheet = auth_data.get('spreadsheet')
        if spreadsheet and spreadsheet.get('is_set'):
            return True

    return False

# Handler-related functions

def start(update: Update, context: CallbackContext) -> str:
    """Entry point for the `/settings` command"""
    keyboard = InlineKeyboardMarkup(entry_inline_kb)
    text = "⚙️ *Settings menu*\nWhat do you want to do?"
    user_data = context.user_data
    
    if user_data.get('start_over'):
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    else:
        update.message.reply_markdown_v2(text=text, reply_markup=keyboard)
    
    user_data['start_over'] = False

    return SELECTING_ACTION

def start_login(update: Update, context: CallbackContext) -> str:
    """Check user's login data and start a new OAuth flow"""
    user_data = context.user_data
    query = update.callback_query
    query.answer()
    
    # Initialize user data
    if 'auth' not in user_data:
        user_data['auth'] = {}
    
    auth_data = user_data.get('auth')
    
    # Each user must have a unique token file
    if 'token_file' not in auth_data:
        auth_data['token_file'] = f"{DATA_DIR}/auth_{str(query.from_user.id)}.json"

    # Check if the auth step has been already done
    if not check_auth(auth_data):
        # Start the OAuth2 process
        _, result = oauth(
            credentials_file=CREDS,
            token_file=auth_data['token_file'],
            user_data=auth_data
        )
        query.edit_message_text(text=result)
        return NEW_LOGIN
    else:
        query.edit_message_text(
            "You already logged in\. What do you want to do?",
            reply_markup=InlineKeyboardMarkup(edit_login_inline_kb)
        )
        return EDIT_LOGIN

def store_auth_code(update: Update, context: CallbackContext) -> int:
    """Handle the authorization code of a new login"""
    keyboard = InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Back', callback_data=str(END)))
    
    auth_data = context.user_data.get('auth')
    code = update.message.text
    creds, result = oauth(
        credentials_file=CREDS,
        token_file=auth_data['token_file'],
        user_data=auth_data,
        code=code
    )
    
    if creds and result:
        auth_data['auth_is_done'] = True
        update.message.reply_text(text=result, reply_markup=keyboard)
    else:
        auth_data['auth_is_done'] = False
        update.message.reply_text(
            text='⚠️ I could not save your token\!',
            reply_markup=keyboard
        )

    return END

def reset_login(update: Update, context: CallbackContext) -> int:
    """Reset the spreadsheet ID and/or sheet name"""
    auth_data = context.user_data.get('auth')
    # Remove the token file
    pathlib.Path(auth_data['token_file']).unlink(missing_ok=True)
    # Clear the dictionary
    auth_data.clear()
    
    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "Your login data have been reset\. You can login again from the `/settings` menu\.",
        reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Ok', callback_data=str(END)))
    )
    return END

def show_login(update: Update, context: CallbackContext) -> int:
    """Show auth data stored"""
    auth_data = context.user_data.get('auth')

    auth_data_str = """*Auth status*: {auth_status}

*Spreadsheet*: {ss_status}
    *ID*: {id}
    *Sheet name*: {name}"""

    status = dict.fromkeys(('auth_status', 'ss_status', 'id', 'name'), '❌')
    
    if check_auth(auth_data):
        status['auth_status'] = '✅'
        if check_spreadsheet(auth_data):
            status['ss_status'] = '✅'
            status['id'] = utils.escape_markdown(auth_data['spreadsheet']['id'])
            status['name'] = utils.escape_markdown(auth_data['spreadsheet']['sheet_name'])

    update.callback_query.answer()
    update.callback_query.edit_message_text(
        "Here's your login data:\n\n"
        f"{auth_data_str.format(**status)}\n\n"
        "✅ = OK\n❌ = missing data",
        reply_markup=InlineKeyboardMarkup.from_button(InlineKeyboardButton(text='Ok', callback_data=str(END)))
    )

    return END

def cancel(update: Update, _: CallbackContext) -> str:
    """Cancel the `settings` command"""
    update.callback_query.answer()
    update.callback_query.edit_message_text("Use `/settings` to enter the settings again or `/help` to know what I can do for you\.\nBye 👋")
    return STOPPING

def stop(update: Update, _: CallbackContext) -> int:
    """End the conversation altogether"""
    return utils.stop(command='settings', action='enter your settings', update=update)

def back_to_start(update: Update, context: CallbackContext) -> str:
    """Go back to the start menu"""
    update.callback_query.answer()
    context.user_data['start_over'] = True
    return start(update, context)

# Login conversation handler
login_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_login, pattern=f'^{LOGIN}$')
    ],
    states={
        NEW_LOGIN: [
            MessageHandler(Filters.text & ~Filters.command, store_auth_code)
        ],
        EDIT_LOGIN: [
            CallbackQueryHandler(reset_login, pattern=f'^{RESET}$'),
            CallbackQueryHandler(show_login, pattern=f'^{SHOW}$')
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel),
        CallbackQueryHandler(cancel, pattern=f'^{CANCEL}$')
    ],
    map_to_parent={
        END: SELECTING_ACTION,
        STOPPING: END,
    },
    name="login_second_level",
    persistent=False
)

# Top-level conversation handler
settings_handler = ConversationHandler(
        entry_points=[
            CommandHandler('settings', start),
        ],
        states={
            SELECTING_ACTION: [
                login_handler,
                CallbackQueryHandler(stop, pattern=f'^{CANCEL}$'),
                CallbackQueryHandler(back_to_start, pattern='^' + str(END) + '$')
            ],
        },
        fallbacks=[
            CommandHandler('stop', stop),
        ],
        name="settings_top_level",
        persistent=False
)
