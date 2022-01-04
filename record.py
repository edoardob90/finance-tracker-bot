"""
Bot functions for the `/record` command
"""
import logging
from typing import OrderedDict, Dict, Any
from datetime import datetime as dt
from dateutil.parser import parse
from telegram import (
    ReplyKeyboardMarkup,
    Update,
    ReplyKeyboardRemove,
    ParseMode
)
from telegram.ext import (
    ConversationHandler,
    CallbackContext,
)
from telegram.utils.helpers import escape_markdown
import gspread
from constants import *
import auth
import spreadsheet

# Enable logging
logging.basicConfig(
    format=log_format, level=log_level
)
logger = logging.getLogger(__name__)

# Keyboard
record_kb = [
    ['Date', 'Reason', 'Amount', 'Account'],
    ['Save', 'Cancel']
]
reply_kb = ReplyKeyboardMarkup(record_kb, one_time_keyboard=True)

def start_record(update: Update, context: CallbackContext) -> int:
    """Start the conversation and ask user the detail of a new expense/income to record"""

    # Initialize user_data
    user_data = context.user_data
    if not 'record' in user_data:
        user_data['record'] = OrderedDict.fromkeys(
            ('date',
            'reason',
            'amount',
            'currency',
            'account')
        )
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    update.message.reply_text(
        """Record a new expense/income\. *Remember* the follwing rules on the input data:
\- `Date` should be written as `dd-mm-yyyy` or `dd mm yyyy` or `dd mm yy`\. Example: `21-12-2021`
\- `Amount`: a _negative_ number is interpreted as an *expense*, while a _positive_ number as an *income*\. """
"""Example: `-150.0 EUR` means an expense of 150 euros\.
\- Currencies supported: EUR, CHF, USD\. You can also enter *a single letter*: E \= EUR, C \= CHF, U \= USD\.""",
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
    """
    if key == 'date':
        user_data['date'] = parse(value).strftime("%d/%m/%Y")
    elif key == 'amount':
        try:
            amount, cur = value.split()
        except ValueError:
            # error is raised if no currency is present
            amount = value
            cur = 'X'
        else:
            cur = CURRENCIES[cur[0]] if cur[0] in CURRENCIES else 'X'
        user_data[key] = float(amount)
        user_data['currency'] = cur
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

def save_record(update: Update, context: CallbackContext) -> int:
    """Display the gathered info, save them to the spreadsheet, and stop the conversation"""
    user_data = context.user_data.get('record')
   
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")
    
    if 'choice' in user_data:
        del user_data['choice']

    # Get the auth_data
    auth_data = context.user_data.get('auth')

    # Append the record to the spreadsheet
    if auth_data['auth_is_done'] and auth_data['spreadsheet']['is_set']:
        values = list(user_data.values())
        values.append(
            dt.now().strftime("%d.%m.%Y, %H:%M")
        )

        # FIXME: a Client is created *every time* a user saves a new record and that's poorly efficient
        # but I don't know where to store it. The persistency classes of python-telegram-bot library don't support classes
        # I should probably look into subclassing BasePersistence to something that supports a database (Redis, MongoDB)
        creds = auth.oauth(update=update, credentials_file=CREDS, token_file=auth_data['token_file'])
        client = gspread.Client(auth=creds)
        ss = spreadsheet.Spreadsheet(client,
                                    spreadsheet_id=auth_data['spreadsheet']['id'],
                                    sheet_name=auth_data['spreadsheet']['sheet_name'])
        try:
            response = ss.append_record(values)
        except:
            logger.error("Something went wrong while appending the record to the spreadsheet.")
            update.message.reply_text("Something went wrong while appending the record to the spreadsheet :-(")
            raise
        
        if 'updates' in response and response['updates']:
            update.message.reply_text(f"""This is the record just appended to the spreadsheet:
{data_to_str(user_data)}

You can add a new record with the command `/record`\. 👋""",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            user_data.clear()
    else:
        update.message.reply_text("Authentication is incomplete or the spreadsheet has not been set\. Run the command `/auth` to complete the authentication\.",
        parse_mode=ParseMode.MARKDOWN_V2)
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")
    
    return ConversationHandler.END