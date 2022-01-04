"""
Bot functions for `/auth` command.
They handle Google authorization flow and Google sheet setup.
"""
from constants import *
import pathlib
import logging
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import UserAccessTokenError
from telegram import (
    Update,
    ParseMode,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler
)
import spreadsheet

logging.basicConfig(
    format=log_format, level=log_level
)
logger = logging.getLogger(__name__)


# Keyboard
auth_kb =[
    ['Auth code', 'Spreadsheet ID', 'Sheet name'],
    ['Done', 'Cancel']
]

reply_auth_kb = ReplyKeyboardMarkup(auth_kb, one_time_keyboard=True)

def oauth(update: Update,
        credentials_file,
        token_file=None,
        code=None):
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
                with (pathlib.Path.cwd() / token_file).open('w') as token:
                    token.write(creds.to_json())

                update.message.reply_text('Token saved')
            else:
                logger.info("OAuth step: asking the user to authorize the app and enter the authorization code")
                # Tell the user to go to the authorization URL to get the authorization code
                auth_url, _ = flow.authorization_url(prompt='consent')
                update.message.reply_text(
                    'Please, go to [this URL]({url}) to request the authorization code\.'.format(url=auth_url),
                parse_mode=ParseMode.MARKDOWN_V2)
    
    return creds

def start_auth(update: Update, context: CallbackContext) -> int:
    """Start the authorization flow for Google Spreadsheet"""
    # Fetch the user_data dict. Initialize if necessary
    user_data = context.user_data
    if 'auth' not in user_data:
        user_data['auth'] = {}
    user_data = user_data.get('auth')

    # Check if the auth step has been already done
    if user_data and user_data.get('auth_is_done'):
        update.message.reply_text("Authentication has already been completed\. You can add records with the `/record` command or query your data with `/summary`\. Use `/cancel` to stop\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=ReplyKeyboardRemove())
    else: 
        update.message.reply_text("Requesting authorization to access Google Sheets\. If it's a new login, you need to approve the access by entering an authorization code\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=reply_auth_kb)
        
        user_data['auth_is_done'] = False

        # Each user must have a unique token file
        user_id = update.message.from_user.id
        TOKEN = "auth_{}.json".format(user_id)
        user_data['token_file'] = TOKEN
    
        # Start the OAuth2 process
        oauth(update=update, credentials_file=CREDS, token_file=TOKEN)
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    return CHOICE

def auth_prompt(update: Update, context: CallbackContext) -> int:
    """Ask user a property of the spreadsheet to use"""
    user_data = context.user_data.get('auth')
    text = update.message.text
    user_data['choice'] = text.lower()
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    update.message.reply_text(
        f"Enter the value of *{text.capitalize()}*",
        parse_mode=ParseMode.MARKDOWN_V2
    )

    return REPLY

def auth_store(update: Update, context: CallbackContext) -> int:
    """Store a property of the spreadsheet chosen"""
    user_data = context.user_data.get('auth')
    
    text = update.message.text
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
        user_data['spreadsheet']['id'] = text
    elif data == 'sheet name':
        user_data['spreadsheet']['sheet_name'] = text

    if user_data['spreadsheet']['id'] and user_data['spreadsheet']['sheet_name']:
        user_data['spreadsheet']['is_set'] = True

    update.message.reply_text(f"*{data.capitalize()}* has been set\!", parse_mode=ParseMode.MARKDOWN_V2)
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    return CHOOSING

def auth_done(update: Update, context: CallbackContext) -> int:
    """Ends the auth conversation"""
    user_data = context.user_data.get('auth')

    if user_data['auth_is_done'] and user_data['spreadsheet']['is_set']:
        update.message.reply_text("Authorization is complete\! Use `/help` to know about the other commands\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        update.message.reply_text('Authorization is incomplete! You must provide all the three parameters: "Auth Code", "Spreadsheet ID" and "Sheet Name".',
        reply_markup=reply_auth_kb)
        return CHOOSING