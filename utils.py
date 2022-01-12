"""
Utils module
"""
import re
from functools import partial
from typing import List, Tuple, Union, Dict, Any
from dateutil.parser import parse
from telegram import InlineKeyboardButton, Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext, ConversationHandler
from telegram.utils.helpers import escape_markdown
from constants import *

escape_markdown = partial(escape_markdown, version=2)

def inline_kb_row(buttons: Union[Tuple, List], offset: int = 0) -> List[InlineKeyboardButton]:
    """Build a keyboard row from a list of buttons"""
    _buttons = [{'text': x, 'callback_data': str(y)} for y, x in enumerate(buttons, start=offset)]
    return list(map(lambda x: InlineKeyboardButton(**x), _buttons))

def remove_job_if_exists(name: str, context: CallbackContext) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

def data_to_str(data: Dict[str, Any]) -> str:
    """Build a string concatenating all values in a data `Dict`"""
    facts = [f"*{escape_markdown(key)}:* {escape_markdown(str(value))}" for key, value in data.items()]
    
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

def cancel(update: Update, command: str) -> int:
    """Cancel a command"""
    text = f"Command `/{command}` has been cancelled\. Use `/help` to know about available commands\. Bye\!"
    if update.callback_query:
        update.callback_query.answer()
        update.callback_query.edit_message_text(text=text)
    else:
        update.message.reply_markdown_v2(text=text, reply_markup=ReplyKeyboardRemove())

    return ConversationHandler.END
