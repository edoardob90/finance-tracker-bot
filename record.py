"""
Bot functions for the `/record` command
"""
import logging
from typing import OrderedDict, Dict, Any, List, Tuple
from copy import deepcopy
from datetime import datetime as dt
from zoneinfo import ZoneInfo
from dateutil.parser import parse
from telegram import (
    Update,
    ParseMode,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ConversationHandler,
    CallbackContext,
)
from telegram.utils.helpers import escape_markdown
import gspread

from constants import *
from utils import inline_kb_row
import auth
import spreadsheet

# Enable logging
logging.basicConfig(
    format=log_format, level=log_level
)
logger = logging.getLogger(__name__)

# Inline keyboard
ROW_1 = ('Date', 'Reason', 'Amount', 'Account')
ROW_2 = ('Save', 'Cancel')
BUTTONS = dict(
    zip(
        map(str, range(len(ROW_1 + ROW_2))),
        ROW_1 + ROW_2
    )
)

record_inline_kb = [
    inline_kb_row(ROW_1),
    inline_kb_row(ROW_2, offset=len(ROW_1))
]

# Utils
def data_to_str(user_data: Dict[str, Any]) -> str:
    """Build a string concatenating all the user data"""
    facts = [f"*{key}:* {escape_markdown(str(value), version=2)}" for key, value in user_data.items()]
    
    return "\n".join(facts)

def parse_data(key: str, value: str, user_data: Dict[str, Any]) -> Dict:
    """Helper function to correctly parse a detail of a new record"""
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

# Bot functions 
def start(update: Update, context: CallbackContext) -> int:
    """Ask the user the details of a new record"""
    update.message.reply_text(
        """Record a new expense/income\. *Remember* the follwing rules on the input data:
\- `Date` should be written as `dd-mm-yyyy` or `dd mm yyyy` or `dd mm yy`\. Example: `21-12-2021`
\- `Amount`: a _negative_ number is interpreted as an *expense*, while a _positive_ number as an *income*\. """
"""Example: `-150.0 EUR` means an expense of 150 euros\.
\- Currencies supported: EUR, CHF, USD\. You can also enter *a single letter*: E \= EUR, C \= CHF, U \= USD\.""",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup(record_inline_kb)
    )

    # Initialize user_data
    user_data = context.user_data
    if 'record' not in user_data:
        # a single empty record
        user_data['record'] = OrderedDict.fromkeys(
            ('date',
            'reason',
            'amount',
            'currency',
            'account',
            'recorded_on')
        )
    # the list of all the records to append
    if 'records' not in user_data:
        user_data['records'] = []

    return CHOOSING

def prompt(update: Update, context: CallbackContext) -> int:
    """Ask user for info about a detail of a new record"""
    query = update.callback_query
    data = query.data
    user_data = context.user_data.get('record')
    user_data['choice'] = BUTTONS[data].lower()

    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")
    
    query.answer()
    query.edit_message_text(
        f"Enter the *{BUTTONS[data]}* of the new record",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return REPLY

def store(update: Update, context: CallbackContext) -> int:
    """Store the provided info and ask for the next"""
    user_data = context.user_data.get('record')
    
    data = update.message.text
    category = user_data['choice']
    user_data = parse_data(category, data, user_data)
    del user_data['choice']

    update.message.reply_text(
        f"Done\! *{category.capitalize()}* has been recorded\. This is new record so far:\n"
        f"{data_to_str(user_data)}",
        reply_markup=InlineKeyboardMarkup(record_inline_kb),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    logger.info(f"user_data: {str(user_data)}, context.user_data: {str(context.user_data)}")

    return CHOOSING

def save(update: Update, context: CallbackContext) -> int:
    """Display the final record and append it to the list that will be added to the spreadsheet"""
    record = context.user_data.get('record')
    records = context.user_data.get('records')
    query = update.callback_query

    logger.info(f"user_data: {str(record)}, context.user_data: {str(context.user_data)}")

    if 'choice' in record:
        del record['choice']

    logger.info(f"record: {record}, records: {records}")

    # Append the current record
    record['recorded_on'] = dt.now().strftime("%d-%m-%Y, %H:%M")
    # Using deepcopy() because record is a mutable object!
    records.append(deepcopy(record))

    query.answer()
    query.edit_message_text(
        text=f"""This is the record just saved:
{data_to_str(record)}

You can add a new record with the command `/record`\. 👋""",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    # Reset the current record to an empty record
    record = OrderedDict.fromkeys(
            ('date',
            'reason',
            'amount',
            'currency',
            'account',
            'recorded_on')
        )
    
    logger.info(f"user_data: {str(record)}, context.user_data: {str(context.user_data)}")

    return ConversationHandler.END

def show_data(update: Update, context: CallbackContext) -> int:
    """Show the records saved so far"""
    records = context.user_data.get('records')

    logger.info(f"context.user_data: {context.user_data}")
    
    if records:
        records_to_str = '\n\=\=\=\n'.join(map(data_to_str, records))
        logger.info("Records:\n{}".format(records))
        update.message.reply_text(
            text=f"These are the records added so far:\n\n{records_to_str}\n\nThese have *not yet* been added to the spreadsheet\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        update.message.reply_text("You have not added any records yet!")

    return ConversationHandler.END

def add_to_spreadsheet(context: CallbackContext) -> None:
    """Daily task for `telegram.ext.JobQueue` to add records to the spreadsheet"""
    user_id, user_data = context.job.context
    records = user_data.get('records')
   
    logger.info(f"user_data: {str(user_data)}, records: {str(records)}")

    if not records:
        logger.info(f"Skipping scheduled task for user_id {user_id}: no records to append.")
    else:
        # Get the auth_data
        auth_data = user_data.get('auth')

        # Append the record to the spreadsheet
        if auth_data and auth_data['auth_is_done'] and auth_data['spreadsheet']['is_set']:
            # Get the credentials and open the connection with the spreadsheet
            creds = auth.oauth(credentials_file=CREDS, token_file=auth_data['token_file'])
            client = gspread.Client(auth=creds)
            ss = spreadsheet.Spreadsheet(
                    client=client,
                    spreadsheet_id=auth_data['spreadsheet']['id'],
                    sheet_name=auth_data['spreadsheet']['sheet_name'])
            
            try:
                for record in records:
                    values = list(record.values())
                    ss.append_record(values)
            except:
                    logger.error("Something went wrong while appending the record to the spreadsheet.")
                    context.bot.send_message(user_id, text="Something went wrong while appending the record to the spreadsheet :-(", show_alert=True)
                    raise
            else:
                records.clear()
                context.bot.send_message(user_id,
                    text="On {}, *{}* records have been successfully added to the spreadsheet\."
                        .format(dt.now().strftime("%d/%m/%Y, %H:%M"), len(user_data)),
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        else:
            context.bot.send_message(user_id, text="Cannot add records to the spreadsheet because the authorization was incomplete or you did not set the spreadsheet ID and/or name\. "
            "Use the command `/auth` complete the authentication or `/reset` to set the spreadsheet ID and/or name\.",
            parse_mode=ParseMode.MARKDOWN_V2)

    return None

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the current `/record` action"""
    user_data = context.user_data.get('record')
    query = update.callback_query
    text = "Action has been cancelled\. Start again with the `/record` or `/summary` commands\. Bye\!"
    query.answer()
    query.edit_message_text(text=text, parse_mode=ParseMode.MARKDOWN_V2)
    user_data.clear()

    return ConversationHandler.END