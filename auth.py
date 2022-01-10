"""
Bot functions for `/auth` command.
They handle Google authorization flow and Google sheet setup.
"""
import pathlib
import logging
from os.path import join
from typing import Any, Union
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import UserAccessTokenError
from telegram import (
    Update,
    InlineKeyboardMarkup,
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


# Inline Keyboard
ROW_1 = 'Auth code', 'Spreadsheet ID', 'Sheet name'
ROW_2 = 'Done', 'Cancel'
BUTTONS = dict(
    zip(
        map(str, range(len(ROW_1 + ROW_2))),
        ROW_1 + ROW_2
    )
)

auth_inline_kb = [
    utils.inline_kb_row(ROW_1),
    utils.inline_kb_row(ROW_2, offset=len(ROW_1))
]

def oauth(
    credentials_file: str,
    token_file: str = None,
    code: str = None,
    update: Update = None) -> Union[Credentials, None]:
    """Start the authorization flow and return a valid token or refresh an expired one"""
    creds = None

    if token_file is not None and pathlib.Path(token_file).exists():
        logger.info("Token file exists")
        creds = Credentials.from_authorized_user_file(token_file, spreadsheet.SCOPES)

    if not creds or not creds.valid:
        logger.info("Creds are invalid")
        if creds and creds.expired and creds.refresh_token:
            logger.info("Creds are expired")
            try:
                creds.refresh(Request())
            except UserAccessTokenError:
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
                creds=flow.credentials

                # Write the token to a file for the next run
                with pathlib.Path(token_file).open('w') as token:
                    token.write(creds.to_json())

                if update:
                    update.message.reply_text('Token saved')
            else:
                logger.info("OAuth step: asking the user to authorize the app and enter the authorization code")
                # Tell the user to go to the authorization URL to get the authorization code
                auth_url, _ = flow.authorization_url(prompt='consent')
                if update:
                    update.message.reply_markdown_v2(
                        text='Please, go to [this URL]({url}) to request the authorization code\.'.format(url=auth_url)
                    )
    
    return creds

def start(update: Update, context: CallbackContext) -> int:
    """Start the authorization flow for Google Spreadsheet"""
    do_auth = True
    
    # Initialize user data
    user_data = context.user_data
    if 'auth' not in user_data:
        user_data['auth'] = {}
    
    auth_data = user_data.get('auth')

    # Check if the auth step has been already done
    if auth_data and auth_data.get('auth_is_done'):
        # Must check if the token file is valid/exists
        if not pathlib.Path(auth_data['token_file']).exists():
            update.message.reply_text("Your authorization file is missing, probably it was deleted. You must do the authentication again.")
            auth_data['auth_is_done'] = False
            msg = f'Token file of user {update.message.from_user.full_name} ({update.message.from_user.id}) is moved or missing!'
            raise FileNotFoundError(msg)
        else:
            do_auth = False
            update.message.reply_markdown_v2("Authentication has already been completed\. You can add records with the `/record` command or query your data with `/summary`\. You can change the spreadsheet with `/reset`\. Use `/cancel` to stop any action\.")

        return ConversationHandler.END
    
    if do_auth: 
        auth_data['auth_is_done'] = False

        # Each user must have a unique token file
        user_id = update.message.from_user.id
        TOKEN = join(DATA_DIR, f"auth_{user_id}.json")
        auth_data['token_file'] = TOKEN
    
        # Start the OAuth2 process
        oauth(update=update, credentials_file=CREDS, token_file=TOKEN)
    
        logger.info(f"auth_data: {str(auth_data)}, context.user_data: {str(context.user_data)}")

        update.message.reply_markdown_v2(
            "Requesting authorization to access Google Sheets\. If it's a new login, you need to approve the access by entering an authorization code\.",
            reply_markup=InlineKeyboardMarkup(auth_inline_kb)
        )

        return CHOOSING

def prompt(update: Update, context: CallbackContext) -> int:
    """Ask user a property of the spreadsheet to use"""
    user_data = context.user_data.get('auth')
    query = update.callback_query
    data = query.data
    user_data['choice'] = BUTTONS[data].lower()
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    query.answer()
    query.edit_message_text(f"Enter the value of *{BUTTONS[data]}*")

    return REPLY

def store(update: Update, context: CallbackContext) -> int:
    """Store a property of the spreadsheet chosen"""
    user_data = context.user_data.get('auth')
    
    text = update.message.text.strip()
    data = user_data['choice']
    del user_data['choice']

    if  data == 'auth code' and not user_data['auth_is_done']:
        creds = oauth(update=update, credentials_file=CREDS, token_file=user_data['token_file'], code=text)
        user_data['spreadsheet'] = {
            'is_set': False,
            'id': '',
            'sheet_name': ''
        }
        if creds:
            user_data['auth_is_done'] = True
    elif data == 'spreadsheet id':
        user_data['spreadsheet']['id'] = text.replace('/', '') # remove any forward slash in the ID
    elif data == 'sheet name':
        user_data['spreadsheet']['sheet_name'] = text

    if user_data['spreadsheet']['id'] and user_data['spreadsheet']['sheet_name']:
        user_data['spreadsheet']['is_set'] = True

    update.message.reply_markdown_v2(
        f"*{data.capitalize()}* has been set\!",
        reply_markup=InlineKeyboardMarkup(auth_inline_kb)
    )
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    return CHOOSING

def done(update: Update, context: CallbackContext) -> int:
    """Ends the auth conversation"""
    user_data = context.user_data.get('auth')
    query = update.callback_query
    query.answer()

    if user_data['auth_is_done'] and user_data['spreadsheet']['is_set']:
        query.edit_message_text("Authorization is complete\! Use `/help` to know available commands\.")
        return ConversationHandler.END
    
    else:
        query.edit_message_text('Authorization is incomplete! You must provide all the three parameters: "Auth Code", "Spreadsheet ID" and "Sheet Name"\.',
        reply_markup=InlineKeyboardMarkup(auth_inline_kb))
        return CHOOSING

def reset(update: Update, context: CallbackContext) -> int:
    """Reset the spreadsheet ID and/or sheet name"""
    user_data = context.user_data.get('auth')
    if user_data:
        if not user_data['spreadsheet']['is_set']:
            update.message.reply_markdown_v2("The spreadsheet has *never* been set\. You have to omplete the authorization step before\.")
        else:
            keyboard = [
                auth_inline_kb[0][1:],
                auth_inline_kb[1]
            ]
            update.message.reply_text(
                text="You can reset the spreadsheet ID and/or the sheet name",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            return CHOOSING
    else:
        update.message.reply_markdown_v2("The authorization step has never been completed\. You should first use the command `/auth`\.")

    return ConversationHandler.END

def show_data(update: Update, context: CallbackContext) -> int:
    """Show auth data stored"""
    auth_data = context.user_data.get('auth')
    auth_status = f"{'✅' if auth_data and auth_data['auth_is_done'] else '❌'}"
    if auth_data:
        auth_data_str = f"""*auth status*: {auth_status}
*spreadsheet*:
    *ID*: {utils.escape_markdown(auth_data['spreadsheet']['id'])}
    *sheet name*: {utils.escape_markdown(auth_data['spreadsheet']['sheet_name'])}"""
        
        update.message.reply_markdown_v2(f"Here's your authorization data:\n\n{auth_data_str}")
    else:
        update.message.reply_markdown_v2(f"Auth status: {auth_status}\nYou should first use the command `/auth` to go through the authorization step\.")

    return ConversationHandler.END

def cancel(update: Update, _: CallbackContext) -> int:
    """Cancel the `auth` command"""
    return utils.cancel(update, command='auth')

# Define the conversation handler for this command
conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('auth', start),
            CommandHandler('auth_data', show_data),
            CommandHandler('reset', reset)
        ],
        states={
            CHOOSING: [
                CallbackQueryHandler(
                    prompt,
                    pattern='^' + '$|^'.join(map(str, range(3))) + '$' # 'Auth code', 'Spreadsheet ID', 'Sheet name' buttons
                ),
                CallbackQueryHandler(done, pattern='^3$'), # 'Done' button
                CallbackQueryHandler(cancel, pattern='^4$') # 'Cancel' button
            ],
            REPLY: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^(Done|Cancel)$')),
                    store
                )
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('reset', reset),
            CommandHandler('auth_data', show_data),
        ],
        name="auth_conversation",
        persistent=False
    )
