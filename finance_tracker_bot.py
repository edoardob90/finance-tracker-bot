#!/usr/bin/env python
# pylint: disable=C0116,W0613

import os
import sys
import traceback
import html
import json
import logging
import pathlib
from typing import Dict, Any

from dotenv import load_dotenv
from datetime import datetime as dt
from dateutil.parser import parse, ParserError
from google.oauth2 import credentials

import gspread
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import UserAccessTokenError

from telegram import (
    ReplyKeyboardMarkup,
    Update,
    ReplyKeyboardRemove,
    ParseMode
)

from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)
from telegram.utils.helpers import escape_markdown

import spreadsheet

# Load .env file
load_dotenv()

# Enable logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
log_level = logging.DEBUG

logging.basicConfig(
    format=log_format, level=log_level
)

logger = logging.getLogger(__name__)

# The three conversation states:
# CHOOSING = 0
# CHOICE = 1
# REPLY = 2
CHOOSING, CHOICE, REPLY = range(3)

# Path to Google API client secret file
CREDS = os.environ.get("CREDS_FILE", "credentials.json")

# Reply markup for keyboards
record_kb = [
    ['Date', 'Amount', 'Reason', 'Account'],
    ['Save', 'Cancel']
]
reply_kb = ReplyKeyboardMarkup(record_kb, one_time_keyboard=True)

auth_kb =[
    ['Auth code', 'Spreadsheet ID', 'Sheet name'],
    ['Done', 'Cancel']
]
reply_auth_kb = ReplyKeyboardMarkup(auth_kb, one_time_keyboard=True)

def error_handler(update: Update, context: CallbackContext) -> int:
    """Log any error and send a warning message"""
    # FIXME: this MUST NOT BE hard-coded!
    developer_user_id = os.environ.get('DEVELOPER_USER_ID')

    # First, log the error before doing anything else so we can see it in the logfile
    logger.error(msg="Exception raised while processing an update:", exc_info=context.error)

    # Format the traceback
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f'An exception was raised while handling an update\n'
        f'<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}'
        '</pre>\n\n'
        f'<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n'
        f'<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n'
        f'<pre>{html.escape(tb_string)}</pre>'
    )

    # Which kind of error?
    if isinstance(context.error, ParserError):
        update.message.reply_text("Whoa! You didn't enter a valid date. Try again.")
    
    if developer_user_id:
        context.bot.send_message(chat_id=developer_user_id, text=message, parse_mode=ParseMode.HTML)

    return CHOOSING

def print_help(update: Update, context: CallbackContext) -> None:
    """Print help message and a command list"""
    user_name = update.message.from_user.name
    update.message.reply_text(
        f"""Hello {user_name}\! I'm a bot that wants to help you with you personal finances\. This is what I can do for you:
\- `/record`: record a new expense or income to your Finance Tracker spreadsheet
\- `/summary`: get a summary of your spreadsheet data \(*coming soon*\)
\- `/auth`: connect me to Google Sheets with your Google account \(should be done only *once*\)""",
    parse_mode=ParseMode.MARKDOWN_V2
    )

# #########################################################
# Functions of the main conversation: /record and /summary
# #########################################################

def start_record(update: Update, context: CallbackContext) -> int:
    """Start the conversation and ask user the detail of a new expense/income to record"""

    # Initialize user_data
    user_data = context.user_data
    if not 'record' in user_data:
        user_data['record'] = {}
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    update.message.reply_text(
        """Record a new expense/income\. *Remember* the follwing rules on the input data:
\- `Date` should be written as `dd-mm-yyyy` or `dd mm yyyy` or `dd mm yy`
\- `Amount`: a _negative_ number is interpreted as an *expense*, while a _positive_ number as an *income*""",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=reply_kb
    )

    return CHOOSING

def prompt_record(update: Update, context: CallbackContext) -> int:
    """Ask user for info about a detail of a new record"""
    text = update.message.text
    user_data = context.user_data.get('record')
    user_data['choice'] = text.lower()

    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")
    
    update.message.reply_text(
        f"Enter the *{text.capitalize()}* of the new record",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return REPLY

def data_to_str(user_data: Dict[str, Any]) -> str:
    """Build a string concatenating all the user data"""
    facts = [f"*{key}:* {escape_markdown(str(value), version=2)}" for key, value in user_data.items()]
    
    return "\n".join(facts)

def parse_data(key: str, value: str, user_data: Dict[str, Any]) -> Dict:
    """
    Helper function to correctly parse a detail of a new record.
    A new record contains:
        - a `Date`: should be parsed and formatted as DD/MM/YYYY
        - an `Amount`: should be a float with +/- sign
        - a `Reason`: just a string
        - an `Account`: a string that should be restricted among a predefined choice 
    """
    if key == 'date':
        user_data['date'] = parse(value).strftime("%d/%m/%Y")
    elif key == 'amount':
        user_data[key] = float(value)
    else:
        user_data[key] = str(value)
    
    return user_data

def store_record(update: Update, context: CallbackContext) -> int:
    """Store the provided info and ask for the next"""
    user_data = context.user_data.get('record')
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")
    
    text = update.message.text
    category = user_data['choice']
    user_data = parse_data(category, text, user_data)
    del user_data['choice']

    update.message.reply_text(
        f"Done\! *{category.capitalize()}* has been recorded\. This is new record so far:\n"
        f"{data_to_str(user_data)}",
        reply_markup=reply_kb,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    return CHOOSING

def start_summary(update: Update, context: CallbackContext) -> int:
    """Ask for a summary"""
    update.message.reply_text("This is currently not implemented, sorry :-(")
    return ConversationHandler.END

def done(update: Update, context: CallbackContext) -> int:
    """Display the gathered info and stop the conversation"""
    user_data = context.user_data.get('record')
   
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")
    
    if 'choice' in user_data:
        del user_data['choice']

    
    # Get the auth_data
    auth_data = context.user_data.get('auth')

    # Append the record to the spreadsheet
    if auth_data['auth_is_done'] and auth_data['spreadsheet_is_set']:
        values = list(user_data.values())
        values.append(
            dt.now().strftime("%d.%m.%Y, %H:%M")
        )

        try:
            ss = auth_data['spreadsheet'].append_record(values)
        except:
            logger.error("Something went wrong while appending the record to the spreadsheet.")
            update.message.reply_text("Something went wrong while appending the record to the spreadsheet :-(")
            raise
        
        if 'updates' in ss and ss['updates']:
            update.message.reply_text(f"""For info, this is the record just appended to the spreadsheet:
{data_to_str(user_data)}

You can add a new record with the command `/record`\. Bye\!""",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            user_data.clear()
    else:
        update.message.reply_text("Authentication is incomplete or the spreadsheet has not been set\. Run the command `/auth` to complete the authentication\.",
        parse_mode=ParseMode.MARKDOWN_V2)
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")
    
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the current action"""
    update.message.reply_text("Action has been cancelled\. Start again with the `/record` or `/summary` commands\. Bye\!",
    parse_mode=ParseMode.MARKDOWN_V2,
    reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END

# #######################################
# Functions related to the auth process
# #######################################

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
    update.message.reply_text("Requesting authorization to access Google Sheets\. If it's a new login, you need to approve the access by entering an authorization code\.",
    parse_mode=ParseMode.MARKDOWN_V2,
    reply_markup=reply_auth_kb)

    # Fetch the user_data dict. Initialize if necessary
    user_data = context.user_data
    if 'auth' not in user_data:
        user_data['auth'] = {}
    user_data = user_data.get('auth')

    # Check if the auth step has been already done
    if user_data and user_data.get('auth_is_done'):
        update.message.reply_text("Authentication has already been completed\. You can add records with the `/record` command or query your data with `\summary`\. Use `/cancel` to stop\.",
        parse_mode=ParseMode.MARKDOWN_V2)
    else: 
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
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    if  data == 'auth code' and not user_data['auth_is_done']:
        creds = oauth(update=update, credentials_file=CREDS, token_file=user_data['token_file'], code=text)
        client = gspread.Client(auth=creds)
        ss = spreadsheet.Spreadsheet(client=client)
        user_data['spreadsheet'] = ss
        user_data['spreadsheet_is_set'] = False
        user_data['auth_is_done'] = True
    else:
        if user_data['auth_is_done']:
            ss = user_data['spreadsheet']
            if data == 'spreadsheet id':
                ss.spreadsheet_id = text
            if data == 'sheet name':
                ss.sheet_name = text
            
            if ss.spreadsheet_id and ss.sheet_name:
                user_data['spreadsheet_is_set'] = True
        else:
            update.message.reply_text("Cannot set 'Spreadsheet ID' or 'Sheet Name' if authorization is incomplete! Please, enter the 'Auth Code' first.", reply_markup=reply_auth_kb)
            return CHOOSING

    update.message.reply_text(f"*{data.capitalize()}* has been set\!", parse_mode=ParseMode.MARKDOWN_V2)

    return CHOOSING

def done_auth(update: Update, context: CallbackContext) -> int:
    """Ends the auth conversation"""
    user_data = context.user_data.get('auth')

    if user_data['auth_is_done'] and user_data['spreadsheet_is_set']:
        update.message.reply_text("Authorization is complete\! Use `/help` to know about the other commands\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    else:
        update.message.reply_text('Authorization is incomplete! You must provide all the three parameters: "Auth Code", "Spreadsheet ID" and "Sheet Name".',
        reply_markup=reply_auth_kb)
        return CHOOSING

def main() -> None:
    """Create and run the bot with a polling mechanism"""
    
    # Create an Updater with the bot's token
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    updater = Updater(TOKEN)
    
    # Get a dispatcher to register handlers
    dispatcher = updater.dispatcher

    # A couple of usage handlers
    start = CommandHandler('start', print_help)
    help_ = CommandHandler('help', print_help)
    dispatcher.add_handler(start)
    dispatcher.add_handler(help_)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('record', start_record),
            CommandHandler('summary', start_summary)
            ],
        states={
            CHOOSING: [
                MessageHandler(
                    Filters.regex('^(Date|Amount|Reason|Account)$'),
                    prompt_record
                )
            ],
            CHOICE: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^Save$')),
                    prompt_record
                )
            ],
            REPLY: [
                MessageHandler(
                   Filters.text & ~(Filters.command | Filters.regex('^Save$')),
                   store_record 
                )
            ]
            },
        fallbacks=[
            MessageHandler(Filters.regex('^Save$'), done),
            MessageHandler(Filters.regex('^Cancel$'), cancel),
            CommandHandler("cancel", cancel),
        ],
        name="main_conversation"
    )

    # The main conversation handler
    dispatcher.add_handler(conv_handler)

    # The auth conversation handler
    auth_handler = ConversationHandler(
        entry_points=[
            CommandHandler('auth', start_auth)
        ],
        states={
            CHOOSING: [
                MessageHandler(
                    Filters.regex('^(Auth code|Spreadsheet ID|Sheet name)$'),
                    auth_prompt
                )
            ],
            CHOICE: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^Done$')),
                    auth_prompt
                )
            ],
            REPLY: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^Done$')),
                    auth_store
                )
            ]
        },
        fallbacks=[
            MessageHandler(Filters.regex('^Done$'), done_auth),
            MessageHandler(Filters.regex('^Cancel$'), cancel),
            CommandHandler('cancel', cancel)
        ],
        name="auth_conversation"
    )

    dispatcher.add_handler(auth_handler)
    
    # Helpers handlers
    help_handler = CommandHandler("help", print_help)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(auth_handler)
    
    # Error handler
    dispatcher.add_error_handler(error_handler)

    # Run the bot
    # TODO: it might be better to switch from polling to webhook mechanism, but requires additional setup
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()